"""Proves the quality index actually discriminates good vs. degraded archives
— not a fixed number like the current arq_worker.py::run_enrich_job's
`qc_score: 95` (which never reflects what was really captured).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pytest

from quality_index import (
    compute_similarity,
    evaluate_against_live,
    extract_visible_text,
    normalize_text,
)


def test_identical_text_scores_100():
    text = "Vörösmarty Mihály Könyvtár Székesfehérvár és Fejér megye legnagyobb könyvtára"
    assert compute_similarity(text, text) == 100.0


def test_completely_different_text_scores_low():
    archived = "Vörösmarty Mihály Könyvtár Székesfehérvár nyitvatartás elérhetőségek"
    live = "Teljesen más tartalom egy másik weboldalról szóló hosszú szöveg"
    score = compute_similarity(archived, live)
    assert score < 30


def test_partial_overlap_scores_in_between():
    archived = "Vörösmarty Mihály Könyvtár Székesfehérvár nyitvatartás elérhetőségek galéria"
    live = "Vörösmarty Mihály Könyvtár Székesfehérvár friss hírek és programok"
    score = compute_similarity(archived, live)
    assert 20 < score < 90


def test_both_empty_is_not_penalized_as_mismatch():
    assert compute_similarity("", "") == 100.0


def test_archived_empty_but_live_has_content_scores_zero():
    assert compute_similarity("", "some real content here") == 0.0


def test_normalize_text_ignores_whitespace_and_case_differences():
    a = "Hello   World\n\n"
    b = "hello world"
    assert normalize_text(a) == normalize_text(b)


def test_extract_visible_text_skips_script_and_style():
    html = """
    <html><head><style>body{color:red}</style></head>
    <body>
      <script>var x = "hidden script content";</script>
      <h1>Valódi Cím</h1>
      <p>Valódi bekezdés szöveg.</p>
    </body></html>
    """
    text = extract_visible_text(html)
    assert "Valódi Cím" in text
    assert "Valódi bekezdés szöveg" in text
    assert "hidden script content" not in text
    assert "color:red" not in text


def test_evaluate_against_live_empty_archive_scores_zero_without_network():
    result = evaluate_against_live("", "https://example.invalid/")
    assert result.score == 0.0
    assert "empty" in result.reasons[0].lower()


def test_evaluate_against_live_reports_fetch_failure_gracefully(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(httpx, "get", fake_get)

    result = evaluate_against_live("some archived text", "https://example.invalid/")
    assert result.score == 0.0
    assert "could not fetch" in result.reasons[0].lower()


def test_evaluate_against_live_matches_real_archived_content(monkeypatch):
    """Simulates the real scenario: archived text closely matches a live
    fetch that returns nearly the same content."""

    class _FakeResponse:
        text = "<html><body><h1>Vörösmarty Mihály Könyvtár</h1><p>Nyitvatartás és elérhetőségek</p></body></html>"

        def raise_for_status(self):
            pass

    def fake_get(*args, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    archived_text = "Vörösmarty Mihály Könyvtár Nyitvatartás és elérhetőségek"
    result = evaluate_against_live(archived_text, "https://www.vmk.hu/")

    assert result.score > 70
    assert "closely matches" in result.reasons[0].lower() or "partially" in result.reasons[0].lower()
