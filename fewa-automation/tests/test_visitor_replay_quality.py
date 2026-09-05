"""Visitor-visible replay quality repair tests for WEBARCHIVUM-REPLAY-QUALITY-REPAIR-001 and REPAIR-002."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawl_manifest import EdgeEvent, build_manifest
from qa_gate import ReplayEvidence, evaluate
from replay_qa import (
    BrokenResource,
    VisitorReplayQualityResult,
    canonicalize_cdx_index_for_pywb,
    inspect_visitor_replay_dom,
    inspect_visitor_replay_qa_log,
    suggest_remediation,
)
from wacz_integrity import WaczVerification


def test_visitor_replay_dom_detects_broken_images_and_links():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
        <h1>Fejér Archives</h1>
        <img src="/images/banner.jpg" alt="Banner">
        <img src="https://example.org/photos/history.jpg" alt="History">
        <a href="/about.html">About Us</a>
        <a href="https://example.org/missing-doc.html">Missing Doc</a>
    </body>
    </html>
    """
    page_url = "https://example.org/index.html"
    # CDX index contains only base page and style.css, missing banner.jpg, history.jpg, and missing-doc.html
    cdx_set = {"https://example.org/index.html", "https://example.org/css/style.css", "https://example.org/about.html"}

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_image_count == 2
    assert result.broken_link_count == 1
    assert result.replay_bad_count == 3
    assert result.quality_score < 80.0
    assert "broken_images_detected (2 > 0)" in result.reasons
    assert "broken_internal_links_detected (1 > 0)" in result.reasons
    assert "autoclick,autofetch,autoscroll" in result.remediation_suggestion


def test_visitor_replay_dom_passes_when_all_resources_exist_in_archive():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Good Page</title></head>
    <body>
        <img src="/images/good.png">
        <a href="/contact">Contact</a>
    </body>
    </html>
    """
    page_url = "https://example.org/"
    cdx_set = {
        "https://example.org/",
        "https://example.org/images/good.png",
        "https://example.org/contact",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert result.passed
    assert result.broken_image_count == 0
    assert result.broken_link_count == 0
    assert result.replay_bad_count == 0
    assert result.quality_score == 100.0
    assert len(result.reasons) == 0


def test_visitor_replay_dom_resolves_protocol_relative_and_lazyload_attributes():
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <!-- Protocol-relative asset -->
        <img src="//example.org/assets/header.png">
        <!-- Dynamic lazyload attribute -->
        <img src="data:image/svg+xml;base64,123" data-src="/assets/photo_large.jpg">
        <!-- Responsive srcset -->
        <img srcset="/assets/small.jpg 320w, /assets/large.jpg 800w">
    </body>
    </html>
    """
    page_url = "https://example.org/article"
    # CDX has header.png and small.jpg, but missing photo_large.jpg and large.jpg
    cdx_set = {
        "https://example.org/article",
        "https://example.org/assets/header.png",
        "https://example.org/assets/small.jpg",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_image_count == 2
    assert "dynamic_lazyload_missing_detected" in result.reasons
    assert any(b.reason == "dynamic_lazyload_missing" for b in result.broken_resources)
    assert "autoclick,autofetch,autoscroll" in result.remediation_suggestion


def test_pywb_rewrite_mismatch_and_canonical_cdx_fallback():
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <!-- Asset captured under http:// but requested via https:// -->
        <img src="https://example.org/legacy_logo.png?v=2.0">
    </body>
    </html>
    """
    page_url = "https://example.org/"
    # CDX has http:// (not https://) and without query param
    cdx_set = {
        "https://example.org/",
        "http://example.org/legacy_logo.png",
    }

    # 1. Strict non-canonical match fails
    result_strict = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set, canonicalize_cdx=False)
    assert not result_strict.passed
    assert result_strict.broken_resources[0].reason == "pywb_rewrite_mismatch"
    assert "pywb_rewrite_mismatch_detected" in result_strict.reasons

    # 2. Canonicalized CDX fallback resolves scheme & query parameter mismatch
    result_canonical = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set, canonicalize_cdx=True)
    assert result_canonical.passed
    assert result_canonical.broken_image_count == 0


def test_visitor_replay_qa_log_detects_replay_bad_failures():
    qa_log_data = [
        {
            "url": "https://example.org/page1",
            "resourceCounts": {"crawlGood": 50, "crawlBad": 0, "replayGood": 40, "replayBad": 10},
        },
        {
            "url": "https://example.org/page2",
            "resourceCounts": {"crawlGood": 30, "crawlBad": 0, "replayGood": 20, "replayBad": 10},
        },
    ]

    result = inspect_visitor_replay_qa_log(qa_log_data, max_allowed_replay_bad=0)

    assert not result.passed
    assert result.replay_bad_count == 20
    assert result.replay_good_count == 60
    assert result.quality_score == 75.0
    assert "replay_bad_resources_detected (total 20 > 0)" in result.reasons
    assert result.actionable_evidence["total_replay_bad"] == 20
    assert "https://example.org/page1" in result.actionable_evidence["failed_pages"]


def test_qa_gate_holds_release_when_visitor_replay_quality_fails():
    seed = "https://example.org/"
    child = "https://example.org/a"
    event = EdgeEvent(
        child, child, seed, 1, True, "capture", None, "plan",
        final_url=child, edge_source_page=seed, policy_decision="allowed",
        robots_decision="allowed", security_decision="allowed", scope_decision="in_scope",
        observed_at="2026-08-14T00:00:00Z",
    )
    manifest = build_manifest(seed, "plan", [event], {seed: True, child: True})
    wacz_sha = "a" * 64
    wacz_verif = WaczVerification(True, wacz_sha)

    # 1. Defective replay evidence (10 broken images/resources detected)
    failed_replay_ev = ReplayEvidence.create(
        manifest_sha256=manifest["manifest_sha256"],
        wacz_sha256=wacz_sha,
        checked_at="2026-08-14T10:00:00Z",
        checker_id="browsertrix-qa/1.14.1",
        result="failed",
        replay_bad_count=10,
        broken_resources=["https://example.org/img1.jpg", "https://example.org/img2.jpg"],
        quality_score=75.0,
        max_allowed_replay_bad=0,
    )

    gate_result_fail = evaluate(
        manifest,
        wacz_ok=wacz_verif,
        replay_ok=failed_replay_ev,
        telemetry_complete=True,
        verified_wacz_sha256=wacz_sha,
    )

    assert gate_result_fail.outcome == "review_required"
    assert "replay_broken_resources_detected" in gate_result_fail.reasons

    # 2. Remediated replay evidence (0 broken resources after remediation)
    remediated_replay_ev = ReplayEvidence.create(
        manifest_sha256=manifest["manifest_sha256"],
        wacz_sha256=wacz_sha,
        checked_at="2026-08-14T10:15:00Z",
        checker_id="browsertrix-qa/1.14.1",
        result="passed",
        replay_bad_count=0,
        broken_resources=[],
        quality_score=100.0,
        max_allowed_replay_bad=0,
    )

    gate_result_pass = evaluate(
        manifest,
        wacz_ok=wacz_verif,
        replay_ok=remediated_replay_ev,
        telemetry_complete=True,
        verified_wacz_sha256=wacz_sha,
    )

    assert gate_result_pass.outcome == "qc_passed_pending_release"
    assert len(gate_result_pass.reasons) == 0


def test_suggest_remediation_provides_actionable_guidance():
    broken_images = [
        BrokenResource(
            url="https://example.org/missing.jpg",
            resource_type="image",
            element_tag='<img src="/missing.jpg">',
            reason="missing_in_cdx",
            context="Missing image",
        )
    ]
    suggestion = suggest_remediation(broken_images)
    assert "autoclick,autofetch,autoscroll" in suggestion
    assert "--media max" in suggestion


def test_visitor_replay_dom_detects_css_background_images_and_fonts():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @font-face {
                font-family: 'CustomFont';
                src: url('/fonts/custom-font.woff2') format('woff2');
            }
            .hero {
                background-image: url('https://example.org/images/hero-banner.png');
            }
        </style>
    </head>
    <body>
        <div class="header" style="background: url(//example.org/images/header-bg.jpg) no-repeat;">
            <h1>Headline</h1>
        </div>
        <div class="hero">
            <p>Welcome</p>
        </div>
    </body>
    </html>
    """
    page_url = "https://example.org/page.html"
    # CDX index contains page.html and header-bg.jpg, but misses custom-font.woff2 and hero-banner.png
    cdx_set = {
        "https://example.org/page.html",
        "https://example.org/images/header-bg.jpg",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_css_count == 2
    assert "css_embedded_resources_missing_detected" in result.reasons
    reasons_codes = [b.reason for b in result.broken_resources]
    assert "css_font_missing" in reasons_codes
    assert "css_background_missing" in reasons_codes
    assert "--media max" in result.remediation_suggestion

