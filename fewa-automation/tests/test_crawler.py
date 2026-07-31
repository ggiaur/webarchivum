"""Tests for crawler.py's command construction and result handling.

Does NOT invoke real Docker/Browsertrix here (slow, needs the image pulled).
The real end-to-end proof already happened manually — see README.md's run
log. This just proves the wrapper logic (command building, success
detection, timeout handling) is correct in isolation.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler import DEFAULT_COOKIE_CONSENT_SELECTOR, run_crawl, run_qa


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def test_run_crawl_defaults_are_scope_limited_not_unrestricted(tmp_path, monkeypatch):
    """Never scopeType=any by default — a crawler that can wander off the
    target site is the exact runaway-collection risk this must prevent."""
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "mycol").mkdir(parents=True, exist_ok=True)
        (tmp_path / "mycol" / "mycol.wacz").write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_crawl("https://example.hu/", "mycol", tmp_path)
    cmd = captured["cmd"]

    assert "--scopeType" in cmd
    scope_value = cmd[cmd.index("--scopeType") + 1]
    assert scope_value in ("host", "page", "prefix", "domain")
    assert scope_value != "any"

    assert "--pageLimit" in cmd
    page_limit = int(cmd[cmd.index("--pageLimit") + 1])
    assert 0 < page_limit <= 100  # some finite, sane cap

    assert "--depth" in cmd
    assert "--sizeLimit" in cmd
    assert "--timeLimit" in cmd


def test_run_crawl_includes_required_shm_size_flag(tmp_path, monkeypatch):
    """--shm-size=1g is not optional — omitting it is what caused the
    original hang (see module docstring)."""
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "mycol").mkdir(parents=True, exist_ok=True)
        (tmp_path / "mycol" / "mycol.wacz").write_bytes(b"fake wacz content")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_crawl("https://example.hu/", "mycol", tmp_path)

    assert "--shm-size=1g" in captured["cmd"]
    assert result.success is True
    assert result.wacz_path == tmp_path / "mycol" / "mycol.wacz"


def test_run_crawl_reports_failure_when_wacz_missing(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return _FakeCompletedProcess(returncode=0)  # exits 0 but produced nothing

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_crawl("https://example.hu/", "mycol", tmp_path)

    assert result.success is False
    assert result.wacz_path is None


def test_run_crawl_handles_timeout_with_clear_message(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_crawl("https://example.hu/", "mycol", tmp_path, timeout_seconds=5)

    assert result.success is False
    assert "shm-size" in result.stderr_tail.lower()


def test_run_crawl_reports_nonzero_exit_code(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, timeout):
        return _FakeCompletedProcess(returncode=1, stderr="docker: error something")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_crawl("https://example.hu/", "mycol", tmp_path)

    assert result.success is False
    assert result.returncode == 1


# --- Cookie-consent autoclick ---------------------------------------------

def test_run_crawl_enables_autoclick_with_default_cookie_selector(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "mycol").mkdir(parents=True, exist_ok=True)
        (tmp_path / "mycol" / "mycol.wacz").write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_crawl("https://example.hu/", "mycol", tmp_path)
    cmd = captured["cmd"]

    assert "--behaviors" in cmd
    behaviors_value = cmd[cmd.index("--behaviors") + 1]
    assert "autoclick" in behaviors_value
    # The other default behaviors must not get silently dropped just
    # because autoclick was added.
    for expected in ("autoplay", "autofetch", "autoscroll", "siteSpecific"):
        assert expected in behaviors_value

    assert "--clickSelector" in cmd
    assert cmd[cmd.index("--clickSelector") + 1] == DEFAULT_COOKIE_CONSENT_SELECTOR


def test_run_crawl_can_disable_autoclick(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "mycol").mkdir(parents=True, exist_ok=True)
        (tmp_path / "mycol" / "mycol.wacz").write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_crawl("https://example.hu/", "mycol", tmp_path, click_selector="")
    cmd = captured["cmd"]

    behaviors_value = cmd[cmd.index("--behaviors") + 1]
    assert "autoclick" not in behaviors_value
    assert "--clickSelector" not in cmd


def test_run_crawl_captures_screenshots_and_warc_text(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        (tmp_path / "mycol").mkdir(parents=True, exist_ok=True)
        (tmp_path / "mycol" / "mycol.wacz").write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_crawl("https://example.hu/", "mycol", tmp_path)
    cmd = captured["cmd"]

    assert "--screenshot" in cmd
    assert cmd[cmd.index("--screenshot") + 1] == "view"
    assert "--text" in cmd
    assert "to-warc" in cmd[cmd.index("--text") + 1]


# --- run_qa (official Browsertrix QA mode) ---------------------------------

def _write_fake_qa_log(logs_dir: Path, url: str, screenshot_match: float,
                        text_match: float, replay_bad: int) -> None:
    """Mimics the REAL Browsertrix QA log format (verified live,
    Browsertrix-Crawler 1.14.1, 2026-07-31) — three separate log lines per
    URL, not a single 'comparison' record."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        {"context": "replay", "message": "Screenshot Diff",
         "details": {"url": url, "diff": 100, "matchPercent": screenshot_match}},
        {"context": "general", "message": "Levenshtein Dist",
         "details": {"url": url, "dist": 5, "matchPercent": text_match, "maxLen": 1000}},
        {"context": "replay", "message": "Resource counts",
         "details": {"url": url, "crawlGood": 10, "crawlBad": 0,
                     "replayGood": 10 - replay_bad, "replayBad": replay_bad}},
    ]
    (logs_dir / "run.log").write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def test_run_qa_parses_per_page_comparison_scores(tmp_path, monkeypatch):
    wacz_path = tmp_path / "source" / "mycol.wacz"
    wacz_path.parent.mkdir(parents=True)
    wacz_path.write_bytes(b"fake wacz")

    output_dir = tmp_path / "qa-out"

    def fake_run(cmd, capture_output, text, timeout):
        _write_fake_qa_log(
            output_dir / "mycol" / "logs", "https://example.hu/",
            screenshot_match=0.95, text_match=0.91, replay_bad=1,
        )
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_qa(wacz_path, "mycol", output_dir)

    assert result.success is True
    assert len(result.per_page) == 1
    assert result.per_page[0]["screenshotMatch"] == 0.95
    assert result.per_page[0]["textMatch"] == 0.91
    assert result.per_page[0]["resourceCounts"]["replayBad"] == 1


def test_run_qa_ignores_log_lines_with_non_dict_details(tmp_path, monkeypatch):
    """Real Browsertrix logs include lines like 'Link Selectors' whose
    'details' is a LIST, not an object with a url — must not crash on these."""
    wacz_path = tmp_path / "source" / "mycol.wacz"
    wacz_path.parent.mkdir(parents=True)
    wacz_path.write_bytes(b"fake wacz")

    output_dir = tmp_path / "qa-out"

    def fake_run(cmd, capture_output, text, timeout):
        logs_dir = output_dir / "mycol" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            {"message": "Link Selectors", "details": [{"selector": "a[href]"}]},
            {"message": "Screenshot Diff", "details": {"url": "https://example.hu/", "matchPercent": 0.8}},
        ]
        (logs_dir / "run.log").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_qa(wacz_path, "mycol", output_dir)

    assert result.success is True
    assert len(result.per_page) == 1
    assert result.per_page[0]["screenshotMatch"] == 0.8


def test_run_qa_reports_failure_on_nonzero_exit(tmp_path, monkeypatch):
    wacz_path = tmp_path / "source" / "mycol.wacz"
    wacz_path.parent.mkdir(parents=True)
    wacz_path.write_bytes(b"fake wacz")

    def fake_run(cmd, capture_output, text, timeout):
        return _FakeCompletedProcess(returncode=1, stderr="qa failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_qa(wacz_path, "mycol", tmp_path / "qa-out")

    assert result.success is False
    assert result.per_page == []
