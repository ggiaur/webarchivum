"""Real quality-index computation: archived content vs. the live original page.

This replaces the fixed `"qc_score": 95` in fewa-v3-backend/app/workers/
arq_worker.py (which returns the same number regardless of what was actually
archived) with a genuine 0-100% score derived from comparing the text
Browsertrix actually captured against what the live page currently shows.

Deliberately NOT wired into fewa-v3-backend yet — this is a new, standalone
module so it can be tested and verified in isolation before anything decides
to depend on it. See fewa-automation/README.md for how it fits together.
"""

import difflib
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List

import httpx


@dataclass
class QualityIndexResult:
    score: float  # 0-100
    archived_length: int
    live_length: int
    reasons: List[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace — so formatting differences (extra
    blank lines, trailing spaces) don't masquerade as content differences."""
    return re.sub(r"\s+", " ", text.strip().lower())


class _VisibleTextExtractor(HTMLParser):
    """Minimal stdlib-only visible-text extractor — no extra dependency.
    Skips <script>/<style>/<noscript> content, keeps everything else."""

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self.chunks.append(data)


def extract_visible_text(html: str) -> str:
    """Extract visible page text the same simple way for both the archived
    and the live copy, so the comparison is apples-to-apples."""
    extractor = _VisibleTextExtractor()
    extractor.feed(html)
    return " ".join(extractor.chunks)


def compute_similarity(archived_text: str, live_text: str) -> float:
    """0-100 similarity between two normalized text blobs.

    difflib.SequenceMatcher.ratio() on whitespace-split tokens (not raw
    characters) — robust to minor reflow/whitespace differences while still
    genuinely penalizing missing or substituted content, unlike a fixed score
    that never reflects what was actually captured.
    """
    a_tokens = normalize_text(archived_text).split()
    b_tokens = normalize_text(live_text).split()
    if not a_tokens and not b_tokens:
        return 100.0
    if not a_tokens or not b_tokens:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a_tokens, b_tokens).ratio()
    return round(ratio * 100, 2)


def evaluate_against_live(archived_text: str, live_url: str, timeout: float = 20.0) -> QualityIndexResult:
    """Fetch the live original page right now and score the archived text
    against it. This is the real, end-to-end version of what
    arq_worker.py::run_enrich_job currently fakes as `qc_score: 95`.
    """
    reasons = []

    if not archived_text.strip():
        return QualityIndexResult(
            score=0.0, archived_length=0, live_length=0,
            reasons=["Archived text is empty — nothing was actually captured."],
        )

    try:
        resp = httpx.get(live_url, timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": "FEWA-QualityIndex/1.0"})
        resp.raise_for_status()
        live_text = extract_visible_text(resp.text)
    except httpx.HTTPError as e:
        return QualityIndexResult(
            score=0.0, archived_length=len(archived_text), live_length=0,
            reasons=[f"Could not fetch live original for comparison: {e}"],
        )

    score = compute_similarity(archived_text, live_text)

    if score < 40:
        reasons.append("Archived content diverges substantially from the live page.")
    elif score < 80:
        reasons.append("Archived content partially matches the live page — the "
                        "live site may have changed since archiving, or the "
                        "crawl missed some content.")
    else:
        reasons.append("Archived content closely matches the live page.")

    return QualityIndexResult(
        score=score,
        archived_length=len(archived_text),
        live_length=len(live_text),
        reasons=reasons,
    )
