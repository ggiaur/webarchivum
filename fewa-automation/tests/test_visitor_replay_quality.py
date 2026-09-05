"""Visitor-visible replay quality repair tests for WEBARCHIVUM-REPLAY-QUALITY-REPAIR-001 and REPAIR-002."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawl_manifest import EdgeEvent, build_manifest
from qa_gate import ReplayEvidence, evaluate
from replay_qa import (
    BrokenResource,
    RemediationEvaluationResult,
    TargetedRemediationPlan,
    VisitorReplayQualityResult,
    canonicalize_cdx_index_for_pywb,
    evaluate_targeted_remediation,
    generate_targeted_remediation_plan,
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


def test_visitor_replay_dom_detects_embedded_iframes_and_media_streams():
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Media & iFrame Page</h1>
        <iframe src="/embed/player.html" data-src="/embed/fallback.html"></iframe>
        <video src="https://example.org/videos/archive.mp4">
            <source src="https://example.org/streams/live.m3u8" type="application/x-mpegURL">
        </video>
        <audio src="/audio/interview.mp3"></audio>
    </body>
    </html>
    """
    page_url = "https://example.org/media.html"
    # CDX contains media.html and audio/interview.mp3, but misses iframe embed, archive.mp4, and live.m3u8
    cdx_set = {
        "https://example.org/media.html",
        "https://example.org/audio/interview.mp3",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_media_count >= 3
    assert "embedded_media_resources_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "iframe_embedded_missing" in reason_codes
    assert "media_stream_missing" in reason_codes
    assert "media_resource_missing" in reason_codes
    assert "'--behaviors autoclick,autofetch,autoscroll,media'" in result.remediation_suggestion


def test_visitor_replay_dom_detects_missing_script_bundles_and_stylesheets():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="/assets/app.css">
        <script src="https://example.org/js/app.bundle.js"></script>
        <script src="/js/vendor.js"></script>
    </head>
    <body>
        <div id="app"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/spa"
    # CDX index contains page and vendor.js, but misses app.css and app.bundle.js
    cdx_set = {
        "https://example.org/spa",
        "https://example.org/js/vendor.js",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_script_count == 1
    assert result.broken_style_count == 1
    assert "critical_script_bundle_missing_detected" in result.reasons
    assert "critical_stylesheet_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "script_bundle_missing" in reason_codes
    assert "style_sheet_missing" in reason_codes
    assert "JS execution enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_shadow_dom_and_custom_element_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Web Components Page</h1>
        <template shadowrootmode="open" data-shadow-src="/templates/header.html">
            <img src="/images/shadow_logo.png">
        </template>
        <custom-card asset-url="https://example.org/assets/card_bg.png"></custom-card>
    </body>
    </html>
    """
    page_url = "https://example.org/components"
    # CDX index contains base page, but misses header.html template and card_bg.png asset
    cdx_set = {
        "https://example.org/components",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_shadow_dom_count >= 2
    assert "shadow_dom_resources_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "shadow_dom_template_missing" in reason_codes
    assert "shadow_dom_resource_missing" in reason_codes
    assert "Shadow DOM expansion enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_websocket_and_sse_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Real-Time Feeds Page</h1>
        <div data-websocket-url="wss://example.org/ws/live"></div>
        <event-source src="/api/v1/feed/stream"></event-source>
        <script>
            const socket = new WebSocket('wss://example.org/ws/tickers');
            const sse = new EventSource('/api/v1/alerts/stream');
        </script>
    </body>
    </html>
    """
    page_url = "https://example.org/realtime"
    # CDX index contains base page and /api/v1/feed/stream (as http/https), but misses wss:// endpoints and alerts/stream
    cdx_set = {
        "https://example.org/realtime",
        "https://example.org/api/v1/feed/stream",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_realtime_count >= 3
    assert "realtime_api_resources_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "websocket_endpoint_missing" in reason_codes
    assert "sse_stream_missing" in reason_codes
    assert "WebSocket frame recording" in result.remediation_suggestion


def test_visitor_replay_dom_detects_web_storage_and_service_worker_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="serviceworker" href="/sw.js">
        <script data-storage-src="/state/user_session.json"></script>
    </head>
    <body>
        <h1>App Hydration Page</h1>
        <script>
            navigator.serviceWorker.register('/offline-worker.js');
            window.__INITIAL_STATE__ = '/api/v1/hydration_state.json';
        </script>
    </body>
    </html>
    """
    page_url = "https://example.org/pwa"
    # CDX index contains base page and sw.js, but misses user_session.json, offline-worker.js, and hydration_state.json
    cdx_set = {
        "https://example.org/pwa",
        "https://example.org/sw.js",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_storage_count >= 3
    assert "web_storage_hydration_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "service_worker_missing" in reason_codes
    assert "storage_state_missing" in reason_codes
    assert "hydration_data_missing" in reason_codes
    assert "Web Storage & Service Worker state preservation" in result.remediation_suggestion


def test_visitor_replay_dom_detects_canvas_and_webgl_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const texture = loadTexture('https://example.org/textures/metal.png');
            const model = load3DModel('/models/vehicle.gltf');
            const shader = loadShader('/shaders/water.glsl');
        </script>
    </head>
    <body>
        <h1>3D Interactive Replay Page</h1>
        <canvas id="renderCanvas" data-canvas-snapshot="/snapshots/canvas_frame01.png" data-webgl-model="https://example.org/models/character.glb"></canvas>
    </body>
    </html>
    """
    page_url = "https://example.org/interactive3d"
    # CDX index contains base page and metal.png, but misses canvas snapshot, character.glb, vehicle.gltf, and water.glsl
    cdx_set = {
        "https://example.org/interactive3d",
        "https://example.org/textures/metal.png",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_canvas_count >= 3
    assert "canvas_webgl_render_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "canvas_snapshot_missing" in reason_codes
    assert "webgl_model_missing" in reason_codes
    assert "shader_source_missing" in reason_codes
    assert "Canvas 2D / WebGL frame snapshotting" in result.remediation_suggestion


def test_visitor_replay_dom_detects_webxr_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const xrSession = navigator.xr.requestSession('/xr/session_config.json');
            const envMap = loadXREnvironment('/xr/environments/museum_hall.hdr');
            const spatialAudio = loadSpatialAudio('/xr/audio/guide.spatial.wav');
        </script>
    </head>
    <body>
        <h1>WebXR Immersive Archive Page</h1>
        <a-sky src="/xr/skyboxes/sky_panorama.jpg"></a-sky>
        <div data-spatial-anchor="/xr/anchors/exhibit_anchor.spatial.json"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/vr_tour"
    # CDX index contains base page and sky_panorama.jpg, but misses session_config.json, museum_hall.hdr, guide.spatial.wav, and exhibit_anchor.spatial.json
    cdx_set = {
        "https://example.org/vr_tour",
        "https://example.org/xr/skyboxes/sky_panorama.jpg",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_webxr_count >= 3
    assert "webxr_environment_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "webxr_environment_missing" in reason_codes
    assert "spatial_audio_missing" in reason_codes
    assert "spatial_anchor_missing" in reason_codes
    assert "WebXR / VR immersive session snapshotting" in result.remediation_suggestion


def test_visitor_replay_dom_detects_pdf_and_pdfjs_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            window.PDFViewerApplication = { file: '/documents/fejer_gazette_1924.pdf' };
            PDFJS.workerSrc = '/pdfjs/pdf.worker.js';
        </script>
    </head>
    <body>
        <h1>Digital Library Gazette Archive</h1>
        <embed type="application/pdf" src="/documents/historical_map.pdf">
        <object type="application/pdf" data="/documents/charter_1688.pdf"></object>
    </body>
    </html>
    """
    page_url = "https://example.org/library/gazette"
    # CDX index contains base page and historical_map.pdf, but misses fejer_gazette_1924.pdf, pdf.worker.js, and charter_1688.pdf
    cdx_set = {
        "https://example.org/library/gazette",
        "https://example.org/documents/historical_map.pdf",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_pdf_count >= 3
    assert "pdf_document_viewer_missing_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "pdf_document_missing" in reason_codes
    assert "pdfjs_worker_missing" in reason_codes
    assert "PDF document & digital library attachment" in result.remediation_suggestion


def test_visitor_replay_dom_detects_consent_shield_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://example.org/scripts/onetrust-banner.js"></script>
        <script src="https://example.org/js/didomi-host.js"></script>
    </head>
    <body>
        <h1>News Portal Archive Page</h1>
        <div id="cookie-banner" data-consent-shield="https://example.org/api/consent_config.json">
            <button>Accept All</button>
        </div>
        <div class="consent-modal" data-modal-overlay="/assets/gdpr_overlay.js"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/news/article"
    # CDX index contains base page and onetrust-banner.js, but misses didomi-host.js, consent_config.json, and gdpr_overlay.js
    cdx_set = {
        "https://example.org/news/article",
        "https://example.org/scripts/onetrust-banner.js",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_consent_count >= 3
    assert "consent_shield_replay_blocking_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "consent_shield_blocking" in reason_codes
    assert "modal_overlay_blocking" in reason_codes
    assert "cookie / GDPR consent banner auto-dismissal rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_pagination_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const page2 = fetchPage('https://example.org/api/v1/articles?page=2');
            const feed = loadMoreArticles('/api/v1/news_feed.json?offset=20');
        </script>
    </head>
    <body>
        <h1>Municipal News Listing Page</h1>
        <div id="feed-pagination" data-page-url="/news/archive/page_02.html"></div>
        <button class="load-more" data-infinite-scroll="https://example.org/api/v1/infinite_articles.json">Load More</button>
    </body>
    </html>
    """
    page_url = "https://example.org/news/listing"
    # CDX index contains base page and page=2, but misses news_feed.json, page_02.html, and infinite_articles.json
    cdx_set = {
        "https://example.org/news/listing",
        "https://example.org/api/v1/articles?page=2",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_pagination_count >= 3
    assert "dynamic_pagination_feed_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "pagination_feed_missing" in reason_codes
    assert "infinite_scroll_missing" in reason_codes
    assert "dynamic AJAX pagination & infinite-scroll behavior rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_search_form_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const results = fetchSearch('https://example.org/api/v1/search?q=helytortenet');
        </script>
    </head>
    <body>
        <h1>Digital Library Search Page</h1>
        <form id="search-form" action="/kereses/talalatok.html" data-search-api="https://example.org/api/v1/search_suggest.json">
            <input type="search" name="q" placeholder="Keresés...">
            <button type="submit">Keresés</button>
        </form>
        <div data-query-endpoint="/api/v1/filtered_query.json"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/kereses"
    # CDX index contains base page and search_suggest.json, but misses talalatok.html, search?q=helytortenet, and filtered_query.json
    cdx_set = {
        "https://example.org/kereses",
        "https://example.org/api/v1/search_suggest.json",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_search_count >= 3
    assert "search_query_form_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "search_form_missing" in reason_codes
    assert "search_api_missing" in reason_codes
    assert "search form submission & query-parameter behavior rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_multilingual_defects():
    html = """
    <!DOCTYPE html>
    <html lang="hu">
    <head>
        <link rel="alternate" hreflang="en" href="https://example.org/en/portal_home.html">
        <link rel="alternate" hreflang="de" href="https://example.org/de/portal_home.html">
        <script>
            const bundle = loadLocale('https://example.org/i18n/locales/de.json');
            const translation = fetchI18n('/i18n/translations_en.json');
        </script>
    </head>
    <body>
        <h1>Hungarian Public Library Portal</h1>
        <div class="lang-switch">
            <a href="/hu/index.html" hreflang="hu">Magyar</a>
            <a href="/en/index.html" data-locale-url="https://example.org/en/index.html">English</a>
        </div>
        <div data-i18n-bundle="/i18n/bundle_hu.json"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/hu/portal_home.html"
    # CDX index contains base page and bundle_hu.json, but misses de/portal_home.html, en/portal_home.html, de.json, translations_en.json, and en/index.html
    cdx_set = {
        "https://example.org/hu/portal_home.html",
        "https://example.org/i18n/bundle_hu.json",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_multilingual_count >= 3
    assert "multilingual_locale_subpath_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "alternate_language_missing" in reason_codes
    assert "locale_bundle_missing" in reason_codes
    assert "multi-language locale selector & alternate language subpath capture rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_lightbox_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const fullPhoto = openLightbox('https://example.org/gallery/fullres_01.jpg');
            const galleryMetadata = fetchGalleryData('/gallery/metadata_exhibition.json');
        </script>
    </head>
    <body>
        <h1>Local History Museum Exhibition Photo Gallery</h1>
        <div class="gallery-grid">
            <a href="/gallery/item1.html" data-lightbox-src="https://example.org/gallery/highres_museum_01.jpg" data-full-src="/gallery/full_museum_01.jpg">
                <img src="/gallery/thumb_museum_01.jpg" alt="Exhibition Item 1">
            </a>
            <div data-gallery-api="/api/v1/gallery_manifest.json"></div>
        </div>
    </body>
    </html>
    """
    page_url = "https://example.org/gallery/exhibition"
    # CDX index contains base page and thumb_museum_01.jpg, but misses fullres_01.jpg, metadata_exhibition.json, highres_museum_01.jpg, full_museum_01.jpg, and gallery_manifest.json
    cdx_set = {
        "https://example.org/gallery/exhibition",
        "https://example.org/gallery/thumb_museum_01.jpg",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_lightbox_count >= 3
    assert "lightbox_gallery_image_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "lightbox_image_missing" in reason_codes
    assert "gallery_metadata_missing" in reason_codes
    assert "dynamic lightbox gallery & image collection viewer behavior rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_gis_map_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const geojson = loadGeoJSON('https://example.org/gis/district_boundaries.geojson');
            const tiles = fetchVectorTiles('/gis/tiles/{z}/{x}/{y}.vector.pbf');
        </script>
    </head>
    <body>
        <h1>Municipal Cadastral GIS & Historical City Map</h1>
        <div id="gis-map" data-tile-url="https://example.org/gis/tiles/{z}/{x}/{y}.pbf" data-geojson-url="/gis/cadastral_1890.geojson"></div>
        <canvas id="leaflet-layer" data-map-layer="/gis/historical_layers_manifest.json"></canvas>
    </body>
    </html>
    """
    page_url = "https://example.org/map/cadastral"
    # CDX index contains base page and historical_layers_manifest.json, but misses district_boundaries.geojson, {z}/{x}/{y}.vector.pbf, {z}/{x}/{y}.pbf, and cadastral_1890.geojson
    cdx_set = {
        "https://example.org/map/cadastral",
        "https://example.org/gis/historical_layers_manifest.json",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_gis_count >= 3
    assert "gis_vector_tile_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "geojson_layer_missing" in reason_codes
    assert "vector_tile_missing" in reason_codes
    assert "interactive map & GIS vector tile / GeoJSON capture rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_embedded_document_reader_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const book = loadFlipbook('https://example.org/documents/archive_vol_01.pdf');
            const pageTile = fetchPageTile('/viewer/tiles/page_02_tile_01.png');
        </script>
    </head>
    <body>
        <h1>Municipal Archive Flipbook Document Viewer</h1>
        <div id="dearflip" data-flipbook-src="https://example.org/documents/charter_1720.pdf" data-page-tile-template="/viewer/tiles/{page}.svg"></div>
        <canvas id="turnjs" data-document-pages="/viewer/pages_manifest.json"></canvas>
    </body>
    </html>
    """
    page_url = "https://example.org/archive/viewer"
    # CDX index contains base page and pages_manifest.json, but misses archive_vol_01.pdf, page_02_tile_01.png, charter_1720.pdf, and {page}.svg
    cdx_set = {
        "https://example.org/archive/viewer",
        "https://example.org/viewer/pages_manifest.json",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_flipbook_count >= 3
    assert "embedded_document_reader_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "flipbook_page_missing" in reason_codes or "page_tile_missing" in reason_codes
    assert "embedded document reader & flipbook viewer behavior rules enabled" in result.remediation_suggestion


def test_visitor_replay_dom_detects_dynamic_audio_stream_defects():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const podcastFeed = loadPodcastFeed('https://example.org/audio/local_history_podcast.xml');
            const oralHistory = fetchOralHistoryAudio('/oralhistory/interview_1974_part1.mp3');
        </script>
    </head>
    <body>
        <h1>Municipal Archives Oral History & Audio Streaming Portal</h1>
        <div id="audio-player" data-audio-src="https://example.org/audio/city_council_1985.mp3" data-podcast-feed="/audio/episodes.json"></div>
        <audio id="oral-history" data-oral-history-audio="/oralhistory/interview_1974_part2.mp3"></audio>
    </body>
    </html>
    """
    page_url = "https://example.org/audio/oral_history"
    # CDX index contains base page and interview_1974_part1.mp3, but misses local_history_podcast.xml, city_council_1985.mp3, episodes.json, and interview_1974_part2.mp3
    cdx_set = {
        "https://example.org/audio/oral_history",
        "https://example.org/oralhistory/interview_1974_part1.mp3",
    }

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)

    assert not result.passed
    assert result.broken_audio_count >= 3
    assert "dynamic_audio_stream_loss_detected" in result.reasons
    reason_codes = [b.reason for b in result.broken_resources]
    assert "podcast_feed_missing" in reason_codes or "oral_history_audio_missing" in reason_codes or "audio_stream_missing" in reason_codes
    assert "dynamic audio/podcast player & oral history archive stream behavior rules enabled" in result.remediation_suggestion


def test_targeted_remediation_plan_generation():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const podcast = loadPodcastFeed('https://example.org/audio/podcast.xml');
            const book = loadFlipbook('https://example.org/viewer/flipbook.pdf');
        </script>
    </head>
    <body>
        <div data-audio-src="https://example.org/audio/council.mp3"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/portal"
    cdx_set = {"https://example.org/portal"}

    result = inspect_visitor_replay_dom(html, page_url, cdx_index_urls=cdx_set)
    assert not result.passed
    assert result.targeted_remediation_plan is not None

    plan = result.targeted_remediation_plan
    assert plan.publication_gate_decision == "HOLD_REJECT"
    assert len(plan.target_urls) >= 3
    assert "audio" in plan.required_behaviors
    assert "flipbook" in plan.required_behaviors
    assert "--behaviors" in plan.recommended_flags[0]
    assert "HOLD_REJECT" in plan.remediation_summary


def test_targeted_remediation_evaluation_and_safe_hold():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script>
            const podcast = loadPodcastFeed('https://example.org/audio/podcast.xml');
            const tile = fetchPageTile('https://example.org/viewer/tile1.png');
        </script>
    </head>
    <body>
        <div data-audio-src="https://example.org/audio/council.mp3"></div>
    </body>
    </html>
    """
    page_url = "https://example.org/portal"
    initial_cdx = {"https://example.org/portal"}

    # 1. Partial patch CDX missing council.mp3 -> must remain HELD (HOLD_REJECT)
    partial_patch = {"https://example.org/audio/podcast.xml", "https://example.org/viewer/tile1.png"}
    eval_held = evaluate_targeted_remediation(html, page_url, initial_cdx, partial_patch)

    assert eval_held.status == "REMEDIATION_HELD"
    assert eval_held.publication_decision == "HOLD_REJECT"
    assert "https://example.org/audio/council.mp3" in eval_held.unresolved_urls
    assert eval_held.remediation_plan is not None

    # 2. Complete patch CDX including all assets -> transitions to FIXED (PASS_RELEASE)
    full_patch = {
        "https://example.org/audio/podcast.xml",
        "https://example.org/viewer/tile1.png",
        "https://example.org/audio/council.mp3",
    }
    eval_fixed = evaluate_targeted_remediation(html, page_url, initial_cdx, full_patch)

    assert eval_fixed.status == "REMEDIATION_FIXED"
    assert eval_fixed.publication_decision == "PASS_RELEASE"
    assert eval_fixed.remaining_broken_count == 0
    assert len(eval_fixed.fixed_urls) >= 3















