"""Real Browsertrix crawl invocation — the exact command proven to work
end-to-end on 2026-07-31 (see fewa-automation/README.md for the full run
log): a fixed `--shm-size=1g` was required, without it the headless Chrome
inside the container silently hangs and the crawl times out. This is not
optional — omit it and crawls WILL hang.

SCOPE SAFETY (critical): without explicit limits, a crawler that follows
links can wander off the target site entirely and start pulling in
unrelated pages across the web. Every crawl here is domain-restricted AND
hard-capped on pages/depth/size/time — never scopeType="any". Flag names
verified against `docker run webrecorder/browsertrix-crawler crawl --help`
(2026-07-31) — do not guess these from memory, they've changed between
Browsertrix versions before.

COOKIE CONSENT: real, visually-confirmed testing (2026-07-31, real
non-headless Chrome via Selenium, screenshots reviewed by hand) showed a
crawl of vmk.hu getting stuck showing an unclicked cookie-consent banner
in the ARCHIVED page — this is exactly what --behaviors autoclick with a
--clickSelector targeting consent buttons is for. Default behaviors list
must be given explicitly once autoclick is added, or the other defaults
(autoplay/autofetch/autoscroll/siteSpecific) get silently dropped.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Best-effort selector covering common cookie-consent-plugin "accept" buttons
# (CookieYes, OneTrust, Cookiebot, Complianz, generic patterns). This is a
# heuristic, not exhaustive — a given site's consent widget may still need a
# site-specific selector passed explicitly.
DEFAULT_COOKIE_CONSENT_SELECTOR = (
    "#onetrust-accept-btn-handler, "
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, "
    "button[id*='accept-cookie' i], button[class*='accept-cookie' i], "
    "button[id*='cookie-accept' i], button[class*='cookie-accept' i], "
    "button[id*='cookie' i][id*='accept' i], "
    ".cc-allow, .cc-accept, .cookie-consent button, a"
)


@dataclass
class CrawlResult:
    success: bool
    wacz_path: Path | None
    returncode: int
    stderr_tail: str


@dataclass
class QAResult:
    success: bool
    per_page: list = field(default_factory=list)  # [{"url":..., "screenshotMatch":..., "textMatch":..., "resourceCounts":...}]
    returncode: int = 0
    stderr_tail: str = ""


def run_crawl(
    url: str,
    collection: str,
    output_dir: Path,
    scope_type: str = "host",
    depth: int = 2,
    page_limit: int = 25,
    size_limit_bytes: int = 500_000_000,
    time_limit_seconds: int = 600,
    timeout_seconds: int = 900,
    click_selector: str = DEFAULT_COOKIE_CONSENT_SELECTOR,
) -> CrawlResult:
    """Run a real, SCOPE-LIMITED Browsertrix crawl of `url`.

    Defaults are deliberately conservative — this archives "a site", not
    "the web reachable from a site":

    - scope_type="host": only follows links on the SAME hostname as the
      seed (e.g. www.vmk.hu stays on www.vmk.hu; it will NOT follow an
      external link to facebook.com or another town's site). Use "page"
      for a single page with no link-following at all (what the original
      proof-of-concept crawl used).
    - depth=2: follows links at most 2 clicks from the seed page.
    - page_limit=25: hard cap on total pages captured, regardless of what
      depth/scope would otherwise allow.
    - size_limit_bytes=500MB / time_limit_seconds=600: extra safety nets —
      the crawler saves what it has and stops if either is exceeded (e.g.
      a page with unexpectedly large embedded media).
    - click_selector: autoclick target, defaults to common cookie-consent
      accept buttons plus a fallback to any link — see
      DEFAULT_COOKIE_CONSENT_SELECTOR. Pass "" to disable autoclick.

    Also captures a viewport screenshot per page (--screenshot view) and
    both to-pages and to-warc text extraction, so the resulting WACZ can
    later be fed into run_qa() (Browsertrix's own official QA comparison)
    as well as fewa-automation's quality_index.py.

    These are defaults for "archive one site reasonably", not universal
    constants — tune per-seed if a site genuinely needs deeper/shallower
    coverage, but never remove the caps entirely.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    behaviors = "autoplay,autofetch,autoscroll,siteSpecific"
    if click_selector:
        behaviors += ",autoclick"

    cmd = [
        "docker", "run", "--rm",
        "--shm-size=1g",
        "-v", f"{output_dir.resolve()}:/crawls/collections",
        "webrecorder/browsertrix-crawler", "crawl",
        "--url", url,
        "--collection", collection,
        "--scopeType", scope_type,
        "--depth", str(depth),
        "--pageLimit", str(page_limit),
        "--sizeLimit", str(size_limit_bytes),
        "--timeLimit", str(time_limit_seconds),
        "--generateWACZ",
        "--text", "to-pages,to-warc",
        "--screenshot", "view",
        "--behaviors", behaviors,
    ]
    if click_selector:
        cmd += ["--clickSelector", click_selector]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return CrawlResult(
            success=False, wacz_path=None, returncode=-1,
            stderr_tail="Crawl timed out — check --shm-size is set (see module docstring).",
        )

    wacz_path = output_dir / collection / f"{collection}.wacz"
    success = result.returncode == 0 and wacz_path.exists()

    return CrawlResult(
        success=success,
        wacz_path=wacz_path if wacz_path.exists() else None,
        returncode=result.returncode,
        stderr_tail=result.stderr[-2000:] if result.stderr else "",
    )


def run_qa(
    wacz_path: Path,
    collection: str,
    output_dir: Path,
    timeout_seconds: int = 900,
) -> QAResult:
    """Run Browsertrix's OFFICIAL, purpose-built QA comparison: re-crawls the
    original URLs live and compares against the WACZ replay, producing real
    screenshot-match and text-match (Levenshtein-based) similarity scores per
    page — from the same team that built the crawler, not a hand-rolled
    approximation. Requires the source WACZ to have been crawled with
    --generateWACZ --text to-warc --screenshot view (run_crawl() sets these
    by default).

    IMPORTANT (verified live, 2026-07-31, Browsertrix-Crawler 1.14.1): the
    per-page scores are NOT in pages.jsonl/extraPages.jsonl despite what the
    hosted docs suggest — they're only in the run's log file, as three
    separate log messages per page:
      context="replay" message="Screenshot Diff" details={url, diff, matchPercent}
      context="general" message="Levenshtein Dist" details={url, dist, matchPercent, maxLen}
      context="replay" message="Resource counts" details={url, crawlGood, crawlBad, replayGood, replayBad}
    This parses the log file directly. Re-verify against the actual log
    output if you upgrade the browsertrix-crawler image — this is exactly
    the kind of detail that silently drifts between versions.

    Docs: https://crawler.docs.browsertrix.com/user-guide/qa/
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "--shm-size=1g",
        "-v", f"{wacz_path.resolve().parent}:/crawls/collections/{collection}_source",
        "-v", f"{output_dir.resolve()}:/crawls/collections",
        "webrecorder/browsertrix-crawler", "qa",
        "--qaSource", f"/crawls/collections/{collection}_source/{wacz_path.name}",
        "--collection", collection,
        "--generateWACZ",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return QAResult(
            success=False, returncode=-1,
            stderr_tail="QA run timed out.",
        )

    per_page = _parse_qa_log(output_dir / collection / "logs")

    return QAResult(
        success=result.returncode == 0,
        per_page=per_page,
        returncode=result.returncode,
        stderr_tail=result.stderr[-2000:] if result.stderr else "",
    )


def _parse_qa_log(logs_dir: Path) -> list:
    """Extract per-URL screenshotMatch/textMatch/resourceCounts from
    Browsertrix's QA log output — see run_qa()'s docstring for why this
    reads the log instead of pages.jsonl."""
    by_url: dict = {}

    if not logs_dir.exists():
        return []

    for log_file in sorted(logs_dir.glob("*.log")):
        for line in log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = rec.get("message")
            details = rec.get("details")
            if not isinstance(details, dict):
                continue  # some log lines (e.g. "Link Selectors") have array details, not a url
            url = details.get("url")
            if not url:
                continue

            entry = by_url.setdefault(url, {"url": url, "screenshotMatch": None,
                                              "textMatch": None, "resourceCounts": None})

            if message == "Screenshot Diff":
                entry["screenshotMatch"] = details.get("matchPercent")
            elif message == "Levenshtein Dist":
                entry["textMatch"] = details.get("matchPercent")
            elif message == "Resource counts":
                entry["resourceCounts"] = {
                    "crawlGood": details.get("crawlGood"),
                    "crawlBad": details.get("crawlBad"),
                    "replayGood": details.get("replayGood"),
                    "replayBad": details.get("replayBad"),
                }

    return list(by_url.values())
