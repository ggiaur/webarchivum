"""Visitor-visible replay quality inspection, evidence extraction, and safe remediation.

Detects broken images, broken links, missing sub-resources, pywb/WACZ replay mismatches,
and CSS embedded background-image / font resource losses from the visitor-visible replay path.
Replaces synthetic/HTTP-only scores with real DOM & resource inspection evidence, and
provides safe remediation / hold loops.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

# Regular expression to extract url(...) references from inline CSS styles or <style> tags
CSS_URL_REGEX = re.compile(r'url\(\s*[\'"]?([^\'")\s]+)[\'"]?\s*\)', re.IGNORECASE)
# Regular expressions to extract WebSocket (ws://, wss://) and Server-Sent Events (EventSource) real-time streams
WS_REGEX = re.compile(r'wss?://[^\s\'"<>)]+', re.IGNORECASE)
SSE_REGEX = re.compile(r'(?:new\s+EventSource|EventSource)\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
# Regular expressions to extract Web Storage, state hydration, and Service Worker cache endpoints
SW_REGEX = re.compile(r'navigator\.serviceWorker\.register\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
HYDRATION_REGEX = re.compile(r'(?:__NEXT_DATA__|__INITIAL_STATE__|__STATE_URL__)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)


@dataclass(frozen=True)
class BrokenResource:
    url: str
    resource_type: str  # "image" | "link" | "script" | "style" | "media" | "lazy_image" | "rewrite_mismatch" | "css_image" | "css_font" | "iframe" | "video" | "audio" | "media_stream" | "script_bundle" | "style_sheet" | "shadow_dom" | "custom_element" | "websocket" | "sse_stream" | "web_storage" | "state_hydration" | "service_worker"
    element_tag: str
    reason: str  # "missing_in_cdx" | "http_404" | "net_failed" | "replay_bad" | "pywb_rewrite_mismatch" | "dynamic_lazyload_missing" | "css_background_missing" | "css_font_missing" | "iframe_embedded_missing" | "media_resource_missing" | "media_stream_missing" | "script_bundle_missing" | "style_sheet_missing" | "shadow_dom_resource_missing" | "shadow_dom_template_missing" | "websocket_endpoint_missing" | "sse_stream_missing" | "storage_state_missing" | "hydration_data_missing" | "service_worker_missing"
    context: str  # HTML snippet or context description


@dataclass(frozen=True)
class VisitorReplayQualityResult:
    passed: bool
    quality_score: float  # 0.0 to 100.0
    total_resources_checked: int
    replay_good_count: int
    replay_bad_count: int
    broken_image_count: int
    broken_link_count: int
    broken_css_count: int
    broken_media_count: int
    broken_script_count: int
    broken_style_count: int
    broken_shadow_dom_count: int
    broken_realtime_count: int = 0
    broken_storage_count: int = 0
    broken_resources: Tuple[BrokenResource, ...] = ()
    reasons: Tuple[str, ...] = ()
    actionable_evidence: Dict[str, Any] = field(default_factory=dict)
    remediation_suggestion: Optional[str] = None



class _DOMResourceExtractor(HTMLParser):
    """Extracts img, script, link[rel=stylesheet], a, lazyload, CSS url(...), iframe, video/audio/stream, Shadow DOM, WebSocket/SSE, and Web Storage/Service Worker assets from HTML."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.images: List[Tuple[str, str]] = []         # (resolved_url, raw_src)
        self.lazy_images: List[Tuple[str, str]] = []    # (resolved_url, raw_attr)
        self.links: List[Tuple[str, str]] = []          # (resolved_url, raw_href)
        self.styles: List[Tuple[str, str]] = []         # (resolved_url, raw_href)
        self.scripts: List[Tuple[str, str]] = []        # (resolved_url, raw_src)
        self.css_urls: List[Tuple[str, str, str]] = []  # (resolved_url, raw_url, type: 'css_image'|'css_font')
        self.media_urls: List[Tuple[str, str, str]] = [] # (resolved_url, raw_url, type: 'iframe'|'video'|'audio'|'media_stream')
        self.shadow_dom_urls: List[Tuple[str, str, str]] = [] # (resolved_url, raw_url, type: 'shadow_dom'|'custom_element')
        self.realtime_urls: List[Tuple[str, str, str]] = []  # (resolved_url, raw_url, type: 'websocket'|'sse_stream')
        self.storage_state_urls: List[Tuple[str, str, str]] = [] # (resolved_url, raw_url, type: 'web_storage'|'state_hydration'|'service_worker')
        self._in_style_tag = False
        self._style_content_chunks: List[str] = []
        self._in_script_tag = False
        self._script_content_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}
        tag_lower = tag.lower()

        effective_base = self.base_url
        if effective_base.startswith("//"):
            effective_base = "https:" + effective_base

        if tag_lower == "style":
            self._in_style_tag = True
        elif tag_lower == "script":
            self._in_script_tag = True

        # Check inline style="background: url(...)" attributes on any element
        if "style" in attr_dict:
            style_str = attr_dict["style"]
            for match in CSS_URL_REGEX.finditer(style_str):
                raw_url = match.group(1).strip()
                if raw_url and not raw_url.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_url, effective_base)
                    res_type = "css_font" if _is_font_url(resolved) else "css_image"
                    self.css_urls.append((resolved, raw_url, res_type))

        # Check explicit WebSocket & SSE attributes or tags
        if tag_lower in ("event-source", "eventsource"):
            for s_attr in ("src", "data-src", "href"):
                if s_attr in attr_dict:
                    raw_val = attr_dict[s_attr].strip()
                    if raw_val:
                        resolved = resolve_protocol_relative(raw_val, effective_base)
                        self.realtime_urls.append((resolved, raw_val, "sse_stream"))

        for rt_attr in ("data-websocket-url", "data-ws-src", "websocket-src", "data-sse-src", "data-sse-endpoint", "data-eventsource-src", "sse-src"):
            if rt_attr in attr_dict:
                raw_val = attr_dict[rt_attr].strip()
                if raw_val:
                    resolved = resolve_protocol_relative(raw_val, effective_base)
                    r_type = "websocket" if ("ws" in rt_attr or raw_val.startswith(("ws://", "wss://"))) else "sse_stream"
                    self.realtime_urls.append((resolved, raw_val, r_type))

        for check_attr in ("src", "href"):
            if check_attr in attr_dict:
                val = attr_dict[check_attr].strip()
                if val.startswith(("ws://", "wss://")):
                    self.realtime_urls.append((val, val, "websocket"))

        # Check Service Worker & Web Storage state hydration attributes/elements
        if tag_lower == "link" and (attr_dict.get("rel") in ("serviceworker", "manifest")):
            if "href" in attr_dict:
                raw_val = attr_dict["href"].strip()
                if raw_val and not raw_val.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_val, effective_base)
                    res_t = "service_worker" if attr_dict.get("rel") == "serviceworker" or raw_val.endswith((".js", "sw.js")) else "state_hydration"
                    self.storage_state_urls.append((resolved, raw_val, res_t))

        for st_attr in ("data-sw-src", "data-sw-url", "data-service-worker", "data-hydration-src", "data-storage-src", "data-state-url", "data-initial-state-url", "storage-src"):
            if st_attr in attr_dict:
                raw_val = attr_dict[st_attr].strip()
                if raw_val and not raw_val.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_val, effective_base)
                    st_type = "service_worker" if "sw" in st_attr or "service" in st_attr else ("web_storage" if "storage" in st_attr else "state_hydration")
                    self.storage_state_urls.append((resolved, raw_val, st_type))

        if tag_lower == "img":
            if "src" in attr_dict:
                raw_src = attr_dict["src"].strip()
                if raw_src and not raw_src.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_src, effective_base)
                    self.images.append((resolved, raw_src))

            for lazy_attr in ("data-src", "data-lazy-src", "data-original", "data-url"):
                if lazy_attr in attr_dict:
                    raw_lazy = attr_dict[lazy_attr].strip()
                    if raw_lazy and not raw_lazy.startswith("data:"):
                        resolved = resolve_protocol_relative(raw_lazy, effective_base)
                        self.lazy_images.append((resolved, raw_lazy))

            if "srcset" in attr_dict:
                raw_srcset = attr_dict["srcset"].strip()
                for entry in raw_srcset.split(","):
                    parts = entry.strip().split()
                    if parts and not parts[0].startswith("data:"):
                        resolved = resolve_protocol_relative(parts[0], effective_base)
                        self.lazy_images.append((resolved, parts[0]))

        elif tag_lower in ("iframe", "frame"):
            for src_attr in ("src", "data-src"):
                if src_attr in attr_dict:
                    raw_src = attr_dict[src_attr].strip()
                    if raw_src and not raw_src.startswith(("javascript:", "about:", "data:")):
                        resolved = resolve_protocol_relative(raw_src, effective_base)
                        self.media_urls.append((resolved, raw_src, "iframe"))

        elif tag_lower in ("video", "audio", "source", "embed", "object"):
            media_src = attr_dict.get("src") or attr_dict.get("data")
            if media_src:
                raw_src = media_src.strip()
                if raw_src and not raw_src.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_src, effective_base)
                    res_type = "media_stream" if _is_media_stream_url(resolved) else (tag_lower if tag_lower in ("video", "audio") else "media")
                    self.media_urls.append((resolved, raw_src, res_type))

        elif tag_lower == "template" and ("shadowrootmode" in attr_dict or "shadowroot" in attr_dict or "data-shadow-src" in attr_dict):
            shadow_src = attr_dict.get("data-shadow-src") or attr_dict.get("src")
            if shadow_src:
                raw_src = shadow_src.strip()
                if raw_src and not raw_src.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_src, effective_base)
                    self.shadow_dom_urls.append((resolved, raw_src, "shadow_dom"))

        elif "-" in tag_lower:  # Custom Elements / Web Components (e.g. <custom-card>, <app-header>)
            for custom_attr in ("src", "data-src", "shadow-src", "asset-url", "icon-src"):
                if custom_attr in attr_dict:
                    raw_src = attr_dict[custom_attr].strip()
                    if raw_src and not raw_src.startswith("data:"):
                        resolved = resolve_protocol_relative(raw_src, effective_base)
                        self.shadow_dom_urls.append((resolved, raw_src, "custom_element"))

        elif tag_lower == "a" and "href" in attr_dict:
            raw_href = attr_dict["href"].strip()
            if raw_href and not raw_href.startswith(("javascript:", "mailto:", "tel:", "#")):
                resolved = resolve_protocol_relative(raw_href, effective_base)
                self.links.append((resolved, raw_href))

        elif tag_lower == "link" and attr_dict.get("rel") == "stylesheet" and "href" in attr_dict:
            raw_href = attr_dict["href"].strip()
            if raw_href and not raw_href.startswith("data:"):
                resolved = resolve_protocol_relative(raw_href, effective_base)
                self.styles.append((resolved, raw_href))

        elif tag_lower == "script" and "src" in attr_dict:
            raw_src = attr_dict["src"].strip()
            if raw_src and not raw_src.startswith("data:"):
                resolved = resolve_protocol_relative(raw_src, effective_base)
                self.scripts.append((resolved, raw_src))


    def handle_data(self, data: str):
        if self._in_style_tag:
            self._style_content_chunks.append(data)
        if self._in_script_tag:
            self._script_content_chunks.append(data)

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower == "style":
            self._in_style_tag = False
            style_text = "".join(self._style_content_chunks)
            self._style_content_chunks.clear()

            effective_base = self.base_url
            if effective_base.startswith("//"):
                effective_base = "https:" + effective_base

            for match in CSS_URL_REGEX.finditer(style_text):
                raw_url = match.group(1).strip()
                if raw_url and not raw_url.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_url, effective_base)
                    res_type = "css_font" if _is_font_url(resolved) else "css_image"
                    self.css_urls.append((resolved, raw_url, res_type))

        elif tag_lower == "script":
            self._in_script_tag = False
            script_text = "".join(self._script_content_chunks)
            self._script_content_chunks.clear()

            effective_base = self.base_url
            if effective_base.startswith("//"):
                effective_base = "https:" + effective_base

            for match in WS_REGEX.finditer(script_text):
                raw_url = match.group(0).strip()
                self.realtime_urls.append((raw_url, raw_url, "websocket"))

            for match in SSE_REGEX.finditer(script_text):
                raw_url = match.group(1).strip()
                if raw_url and not raw_url.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_url, effective_base)
                    self.realtime_urls.append((resolved, raw_url, "sse_stream"))

            for match in SW_REGEX.finditer(script_text):
                raw_url = match.group(1).strip()
                if raw_url and not raw_url.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_url, effective_base)
                    self.storage_state_urls.append((resolved, raw_url, "service_worker"))

            for match in HYDRATION_REGEX.finditer(script_text):
                raw_url = match.group(1).strip()
                if raw_url and not raw_url.startswith("data:"):
                    resolved = resolve_protocol_relative(raw_url, effective_base)
                    self.storage_state_urls.append((resolved, raw_url, "state_hydration"))


def resolve_protocol_relative(raw_url: str, base_url: str) -> str:
    """Resolve relative, protocol-relative (//example.com), and absolute URLs against base_url."""
    raw = raw_url.strip()
    if raw.startswith("//"):
        base_scheme = urlparse(base_url).scheme or "https"
        return f"{base_scheme}:{raw}"
    return urljoin(base_url, raw)


def extract_dom_resources(html_content: str, base_url: str) -> _DOMResourceExtractor:
    """Parse HTML and return DOM resource lists."""
    parser = _DOMResourceExtractor(base_url)
    parser.feed(html_content)
    return parser


def canonicalize_cdx_index_for_pywb(cdx_urls: Set[str]) -> Set[str]:
    """Build scheme-agnostic & query-stripping lookup set to resolve pywb rewrite mismatches.

    Adds http://, https://, ws://, wss://, and query-stripped variants of every CDX URL.
    """
    canonical_set = set(cdx_urls)
    for url in list(cdx_urls):
        norm = _normalize_url_for_cdx(url)
        canonical_set.add(norm)
        if url.startswith("https://"):
            canonical_set.add("http://" + url[8:])
            canonical_set.add("http://" + norm[8:])
            canonical_set.add("wss://" + url[8:])
            canonical_set.add("ws://" + url[8:])
        elif url.startswith("http://"):
            canonical_set.add("https://" + url[7:])
            canonical_set.add("https://" + norm[7:])
            canonical_set.add("ws://" + url[7:])
            canonical_set.add("wss://" + url[7:])
        elif url.startswith("wss://"):
            canonical_set.add("https://" + url[6:])
            canonical_set.add("http://" + url[6:])
            canonical_set.add("ws://" + url[6:])
        elif url.startswith("ws://"):
            canonical_set.add("http://" + url[5:])
            canonical_set.add("https://" + url[5:])
            canonical_set.add("wss://" + url[5:])
        query_stripped = _strip_query_params(url)
        canonical_set.add(query_stripped)
    return canonical_set


def inspect_visitor_replay_dom(
    html_content: str,
    page_url: str,
    cdx_index_urls: Optional[Set[str]] = None,
    max_allowed_broken_images: int = 0,
    max_allowed_broken_links: int = 0,
    max_allowed_broken_css: int = 0,
    max_allowed_broken_media: int = 0,
    max_allowed_broken_scripts: int = 0,
    max_allowed_broken_styles: int = 0,
    max_allowed_broken_realtime: int = 0,
    max_allowed_broken_storage: int = 0,
    canonicalize_cdx: bool = True,
) -> VisitorReplayQualityResult:
    """Inspect visitor-visible DOM for broken images, missing links, pywb rewrite mismatches, lazy-load, CSS embedded assets, iframe/media streams, critical script/style bundles, and WebSocket/SSE real-time streams.

    Checks rendered DOM elements (img, lazyload, a, link, script, CSS url(...), iframe, video/audio/streams, Shadow DOM, WebSocket/SSE) against CDX.
    Returns structured VisitorReplayQualityResult with actionable evidence.
    """
    extractor = extract_dom_resources(html_content, page_url)
    page_host = urlparse(page_url).netloc.lower()

    canonical_cdx = cdx_index_urls
    if cdx_index_urls is not None and canonicalize_cdx:
        canonical_cdx = canonicalize_cdx_index_for_pywb(cdx_index_urls)

    broken: List[BrokenResource] = []
    reasons: List[str] = []

    # 1. Check Standard Images
    broken_images = 0
    for resolved_url, raw_src in extractor.images:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                broken_images += 1
                reason_code = "pywb_rewrite_mismatch" if _is_scheme_or_param_mismatch(resolved_url, cdx_index_urls) else "missing_in_cdx"
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type="image",
                        element_tag=f'<img src="{raw_src}">',
                        reason=reason_code,
                        context=f"Image URL {resolved_url} was not captured or failed pywb rewrite matching.",
                    )
                )

    # 2. Check Lazy-Loaded Images
    lazy_broken = 0
    for resolved_url, raw_attr in extractor.lazy_images:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                lazy_broken += 1
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type="lazy_image",
                        element_tag=f'<img data-src/srcset="{raw_attr}">',
                        reason="dynamic_lazyload_missing",
                        context=f"Lazy-loaded asset {resolved_url} was not captured prior to scroll/interaction.",
                    )
                )

    # 3. Check CSS Embedded Background Images and Fonts
    css_broken = 0
    for resolved_url, raw_url, res_type in extractor.css_urls:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                css_broken += 1
                reason_code = "css_font_missing" if res_type == "css_font" else "css_background_missing"
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type=res_type,
                        element_tag=f'style="...url({raw_url})..."',
                        reason=reason_code,
                        context=f"CSS embedded resource ({res_type}) {resolved_url} missing in WACZ archive.",
                    )
                )

    # 4. Check Internal Links
    broken_links = 0
    for resolved_url, raw_href in extractor.links:
        link_host = urlparse(resolved_url).netloc.lower()
        if link_host == page_host or not link_host:
            if cdx_index_urls is not None:
                if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                    broken_links += 1
                    broken.append(
                        BrokenResource(
                            url=resolved_url,
                            resource_type="link",
                            element_tag=f'<a href="{raw_href}">',
                            reason="missing_in_cdx",
                            context=f"Internal link {resolved_url} missing in WACZ archive.",
                        )
                    )

    # 5. Check Embedded iFrames and Video/Audio Media Streams
    media_broken = 0
    for resolved_url, raw_url, res_type in extractor.media_urls:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                media_broken += 1
                if res_type == "iframe":
                    reason_code = "iframe_embedded_missing"
                    tag_repr = f'<iframe src="{raw_url}">'
                elif res_type == "media_stream":
                    reason_code = "media_stream_missing"
                    tag_repr = f'<source src="{raw_url}">'
                else:
                    reason_code = "media_resource_missing"
                    tag_repr = f'<{res_type} src="{raw_url}">'

                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type=res_type,
                        element_tag=tag_repr,
                        reason=reason_code,
                        context=f"Embedded {res_type} resource {resolved_url} missing in WACZ archive.",
                    )
                )

    # 6. Check Critical Script Bundles
    script_broken = 0
    for resolved_url, raw_src in extractor.scripts:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                script_broken += 1
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type="script",
                        element_tag=f'<script src="{raw_src}">',
                        reason="script_bundle_missing",
                        context=f"Critical script bundle {resolved_url} missing in WACZ archive.",
                    )
                )

    # 7. Check External Stylesheets
    style_broken = 0
    for resolved_url, raw_href in extractor.styles:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                style_broken += 1
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type="style",
                        element_tag=f'<link rel="stylesheet" href="{raw_href}">',
                        reason="style_sheet_missing",
                        context=f"External stylesheet {resolved_url} missing in WACZ archive.",
                    )
                )

    # 8. Check Shadow DOM & Custom Element Assets
    shadow_broken = 0
    for resolved_url, raw_url, res_type in extractor.shadow_dom_urls:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                shadow_broken += 1
                reason_code = "shadow_dom_template_missing" if res_type == "shadow_dom" else "shadow_dom_resource_missing"
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type=res_type,
                        element_tag=f'<{res_type} src="{raw_url}">',
                        reason=reason_code,
                        context=f"Shadow DOM / Custom Element resource ({res_type}) {resolved_url} missing in WACZ archive.",
                    )
                )

    # 9. Check WebSocket & Server-Sent Events (SSE) Real-Time API Streams
    realtime_broken = 0
    for resolved_url, raw_url, res_type in extractor.realtime_urls:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                realtime_broken += 1
                reason_code = "websocket_endpoint_missing" if res_type == "websocket" else "sse_stream_missing"
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type=res_type,
                        element_tag=f'<{res_type} url="{raw_url}">',
                        reason=reason_code,
                        context=f"Real-time {res_type} API stream endpoint {resolved_url} missing in WACZ archive.",
                    )
                )

    # 10. Check Web Storage State Hydration & Service Worker Cache Assets
    storage_broken = 0
    for resolved_url, raw_url, res_type in extractor.storage_state_urls:
        if cdx_index_urls is not None:
            if not _is_url_in_cdx(resolved_url, cdx_index_urls, canonical_cdx):
                storage_broken += 1
                if res_type == "service_worker":
                    reason_code = "service_worker_missing"
                elif res_type == "web_storage":
                    reason_code = "storage_state_missing"
                else:
                    reason_code = "hydration_data_missing"
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type=res_type,
                        element_tag=f'<{res_type} url="{raw_url}">',
                        reason=reason_code,
                        context=f"Client state {res_type} asset/manifest {resolved_url} missing in WACZ archive.",
                    )
                )

    total_checked = (
        len(extractor.images)
        + len(extractor.lazy_images)
        + len(extractor.css_urls)
        + len(extractor.links)
        + len(extractor.media_urls)
        + len(extractor.styles)
        + len(extractor.scripts)
        + len(extractor.shadow_dom_urls)
        + len(extractor.realtime_urls)
        + len(extractor.storage_state_urls)
    )
    total_broken = len(broken)
    replay_good = total_checked - total_broken
    replay_bad = total_broken

    quality_score = 100.0 if total_checked == 0 else round((replay_good / total_checked) * 100.0, 2)

    total_bad_images = broken_images + lazy_broken

    if total_bad_images > max_allowed_broken_images:
        reasons.append(f"broken_images_detected ({total_bad_images} > {max_allowed_broken_images})")

    if broken_links > max_allowed_broken_links:
        reasons.append(f"broken_internal_links_detected ({broken_links} > {max_allowed_broken_links})")

    if css_broken > max_allowed_broken_css:
        reasons.append(f"broken_css_resources_detected ({css_broken} > {max_allowed_broken_css})")

    if media_broken > max_allowed_broken_media:
        reasons.append(f"broken_embedded_media_detected ({media_broken} > {max_allowed_broken_media})")

    if script_broken > max_allowed_broken_scripts:
        reasons.append(f"broken_script_bundles_detected ({script_broken} > {max_allowed_broken_scripts})")

    if style_broken > max_allowed_broken_styles:
        reasons.append(f"broken_stylesheets_detected ({style_broken} > {max_allowed_broken_styles})")

    if realtime_broken > max_allowed_broken_realtime:
        reasons.append(f"broken_realtime_api_detected ({realtime_broken} > {max_allowed_broken_realtime})")

    if storage_broken > max_allowed_broken_storage:
        reasons.append(f"broken_web_storage_hydration_detected ({storage_broken} > {max_allowed_broken_storage})")

    if any(b.reason == "pywb_rewrite_mismatch" for b in broken):
        reasons.append("pywb_rewrite_mismatch_detected")

    if any(b.reason == "dynamic_lazyload_missing" for b in broken):
        reasons.append("dynamic_lazyload_missing_detected")

    if any(b.reason in ("css_background_missing", "css_font_missing") for b in broken):
        reasons.append("css_embedded_resources_missing_detected")

    if any(b.reason in ("iframe_embedded_missing", "media_resource_missing", "media_stream_missing") for b in broken):
        reasons.append("embedded_media_resources_missing_detected")

    if any(b.reason == "script_bundle_missing" for b in broken):
        reasons.append("critical_script_bundle_missing_detected")

    if any(b.reason == "style_sheet_missing" for b in broken):
        reasons.append("critical_stylesheet_missing_detected")

    if any(b.reason in ("shadow_dom_resource_missing", "shadow_dom_template_missing") for b in broken):
        reasons.append("shadow_dom_resources_missing_detected")

    if any(b.reason in ("websocket_endpoint_missing", "sse_stream_missing") for b in broken):
        reasons.append("realtime_api_resources_missing_detected")

    if any(b.reason in ("storage_state_missing", "hydration_data_missing", "service_worker_missing") for b in broken):
        reasons.append("web_storage_hydration_missing_detected")

    passed = len(reasons) == 0

    remediation = None
    if not passed:
        remediation = suggest_remediation(broken)

    actionable_evidence = {
        "page_url": page_url,
        "total_checked": total_checked,
        "replay_good": replay_good,
        "replay_bad": replay_bad,
        "broken_image_count": total_bad_images,
        "broken_link_count": broken_links,
        "broken_css_count": css_broken,
        "broken_media_count": media_broken,
        "broken_script_count": script_broken,
        "broken_style_count": style_broken,
        "broken_shadow_dom_count": shadow_broken,
        "broken_realtime_count": realtime_broken,
        "broken_storage_count": storage_broken,
        "quality_score": quality_score,
        "broken_resources": [
            {
                "url": b.url,
                "type": b.resource_type,
                "tag": b.element_tag,
                "reason": b.reason,
                "context": b.context,
            }
            for b in broken
        ],
    }

    return VisitorReplayQualityResult(
        passed=passed,
        quality_score=quality_score,
        total_resources_checked=total_checked,
        replay_good_count=replay_good,
        replay_bad_count=replay_bad,
        broken_image_count=total_bad_images,
        broken_link_count=broken_links,
        broken_css_count=css_broken,
        broken_media_count=media_broken,
        broken_script_count=script_broken,
        broken_style_count=style_broken,
        broken_shadow_dom_count=shadow_broken,
        broken_realtime_count=realtime_broken,
        broken_storage_count=storage_broken,
        broken_resources=tuple(broken),
        reasons=tuple(reasons),
        actionable_evidence=actionable_evidence,
        remediation_suggestion=remediation,
    )


def inspect_visitor_replay_qa_log(
    per_page_qa_data: List[Dict[str, Any]],
    max_allowed_replay_bad: int = 0,
    min_quality_ratio: float = 0.95,
) -> VisitorReplayQualityResult:
    """Inspect Browsertrix / pywb QA log telemetry for visitor-visible resource failures."""
    total_replay_good = 0
    total_replay_bad = 0
    broken: List[BrokenResource] = []
    reasons: List[str] = []

    for page_entry in per_page_qa_data:
        url = page_entry.get("url", "unknown")
        rc = page_entry.get("resourceCounts") or {}
        r_good = rc.get("replayGood") or 0
        r_bad = rc.get("replayBad") or 0

        total_replay_good += r_good
        total_replay_bad += r_bad

        if r_bad > max_allowed_replay_bad:
            broken.append(
                BrokenResource(
                    url=url,
                    resource_type="page_resources",
                    element_tag="<page>",
                    reason="replay_bad_exceeded",
                    context=f"Page {url} suffered {r_bad} failed replay resource loads.",
                )
            )

    total_resources = total_replay_good + total_replay_bad
    quality_ratio = 1.0 if total_resources == 0 else (total_replay_good / total_resources)
    quality_score = round(quality_ratio * 100.0, 2)

    if total_replay_bad > max_allowed_replay_bad:
        reasons.append(f"replay_bad_resources_detected (total {total_replay_bad} > {max_allowed_replay_bad})")

    if quality_ratio < min_quality_ratio:
        reasons.append(f"replay_quality_ratio_below_threshold ({quality_score}% < {min_quality_ratio * 100}%)")

    passed = len(reasons) == 0

    remediation = None
    if not passed:
        remediation = suggest_remediation(broken)

    actionable_evidence = {
        "total_resources": total_resources,
        "total_replay_good": total_replay_good,
        "total_replay_bad": total_replay_bad,
        "quality_score": quality_score,
        "per_page_summary": per_page_qa_data,
        "failed_pages": [b.url for b in broken],
    }

    return VisitorReplayQualityResult(
        passed=passed,
        quality_score=quality_score,
        total_resources_checked=total_resources,
        replay_good_count=total_replay_good,
        replay_bad_count=total_replay_bad,
        broken_image_count=len(broken),
        broken_link_count=0,
        broken_css_count=0,
        broken_media_count=0,
        broken_script_count=0,
        broken_style_count=0,
        broken_shadow_dom_count=0,
        broken_realtime_count=0,
        broken_storage_count=0,
        broken_resources=tuple(broken),
        reasons=tuple(reasons),
        actionable_evidence=actionable_evidence,
        remediation_suggestion=remediation,
    )



def suggest_remediation(broken_resources: List[BrokenResource]) -> str:
    """Provide specific, actionable remediation options based on failure class."""
    if not broken_resources:
        return "No remediation needed."

    has_storage = any(
        b.reason in ("storage_state_missing", "hydration_data_missing", "service_worker_missing")
        or b.resource_type in ("web_storage", "state_hydration", "service_worker")
        for b in broken_resources
    )
    has_realtime = any(
        b.reason in ("websocket_endpoint_missing", "sse_stream_missing")
        or b.resource_type in ("websocket", "sse_stream")
        for b in broken_resources
    )
    has_shadow_dom = any(
        b.reason in ("shadow_dom_resource_missing", "shadow_dom_template_missing")
        or b.resource_type in ("shadow_dom", "custom_element")
        for b in broken_resources
    )
    has_bundles = any(
        b.reason in ("script_bundle_missing", "style_sheet_missing")
        or b.resource_type in ("script", "style")
        for b in broken_resources
    )
    has_media = any(
        b.reason in ("iframe_embedded_missing", "media_resource_missing", "media_stream_missing")
        or b.resource_type in ("iframe", "video", "audio", "media_stream")
        for b in broken_resources
    )
    has_rewrite_mismatch = any(b.reason == "pywb_rewrite_mismatch" for b in broken_resources)
    has_lazyload = any(b.reason == "dynamic_lazyload_missing" or b.resource_type == "lazy_image" for b in broken_resources)
    has_css = any(b.reason in ("css_background_missing", "css_font_missing") or b.resource_type in ("css_image", "css_font") for b in broken_resources)
    has_images = any(b.resource_type in ("image", "page_resources") for b in broken_resources)
    has_links = any(b.resource_type == "link" for b in broken_resources)

    suggestions = []
    if has_storage:
        suggestions.append(
            "Re-crawl with Web Storage & Service Worker state preservation enabled '--behaviors autoclick,autofetch,autoscroll,storage' and WACZ client-side state snapshotting enabled."
        )
    if has_realtime:
        suggestions.append(
            "Re-crawl with WebSocket frame recording '--behaviors autoclick,autofetch,autoscroll,websocket' and Server-Sent Event stream buffering enabled."
        )
    if has_shadow_dom:
        suggestions.append(
            "Re-crawl with Shadow DOM expansion enabled '--behaviors autoclick,autofetch,autoscroll' and WACZ DOM snapshotting enabled."
        )
    if has_bundles:
        suggestions.append(
            "Re-crawl with JS execution enabled '--behaviors autoclick,autofetch,autoscroll' and expanded sub-resource capture '--media max'."
        )
    if has_media:
        suggestions.append(
            "Re-crawl with expanded media & iframe behaviors '--behaviors autoclick,autofetch,autoscroll,media' and video extraction enabled."
        )
    if has_css:
        suggestions.append(
            "Re-crawl with expanded CSS & font capture rules `--media max` and sub-resource fetching enabled."
        )
    if has_rewrite_mismatch:
        suggestions.append(
            "Enable pywb scheme-canonicalization & query-string alias rewriting (map http/https and strip cache-busting params in CDX index)."
        )
    if has_lazyload:
        suggestions.append(
            "Enable `--behaviors autoclick,autofetch,autoscroll` with scroll delays to trigger and capture dynamic lazy-loaded images."
        )
    if has_images and not has_lazyload and not has_rewrite_mismatch and not has_css and not has_media and not has_bundles and not has_shadow_dom and not has_realtime and not has_storage:
        suggestions.append(
            "Re-crawl with expanded behaviors `--behaviors autoclick,autofetch,autoscroll` and `--media max` "
            "to capture lazy-loaded images, responsive srcset images, and dynamic consent-shielded assets."
        )
    if has_links:
        suggestions.append(
            "Increase crawl depth or page limit `--depth 3 --pageLimit 50` to capture linked sub-pages."
        )
    if not suggestions:
        suggestions.append("Hold publication for manual curator review due to unverified replay resource failures.")

    return " | ".join(suggestions)




def _is_font_url(url: str) -> bool:
    """Check if URL points to a web font asset."""
    path = urlparse(url).path.lower()
    return path.endswith((".woff2", ".woff", ".ttf", ".otf", ".eot"))


def _is_media_stream_url(url: str) -> bool:
    """Check if URL points to an HLS, DASH, or media stream manifest."""
    path = urlparse(url).path.lower()
    return path.endswith((".m3u8", ".mpd", ".f4m")) or "manifest" in path or "master.m3u8" in path


def _is_url_in_cdx(url: str, raw_cdx: Set[str], canonical_cdx: Optional[Set[str]]) -> bool:
    """Check if URL exists in raw or canonicalized CDX index."""
    if url in raw_cdx:
        return True
    norm = _normalize_url_for_cdx(url)
    if norm in raw_cdx:
        return True
    if canonical_cdx and (url in canonical_cdx or norm in canonical_cdx or _strip_query_params(url) in canonical_cdx):
        return True
    if url.startswith("ws://"):
        http_url = "http://" + url[5:]
        if http_url in raw_cdx or (canonical_cdx and http_url in canonical_cdx):
            return True
    elif url.startswith("wss://"):
        https_url = "https://" + url[6:]
        if https_url in raw_cdx or (canonical_cdx and https_url in canonical_cdx):
            return True
    return False



def _is_scheme_or_param_mismatch(url: str, raw_cdx: Set[str]) -> bool:
    """Detect if asset exists in CDX under different scheme (http vs https) or stripped query param."""
    stripped = _strip_query_params(url)
    if stripped in raw_cdx:
        return True
    if url.startswith("https://"):
        alt = "http://" + url[8:]
        if alt in raw_cdx or _strip_query_params(alt) in raw_cdx:
            return True
    elif url.startswith("http://"):
        alt = "https://" + url[7:]
        if alt in raw_cdx or _strip_query_params(alt) in raw_cdx:
            return True
    return False


def _strip_query_params(url: str) -> str:
    """Strip query parameters from URL."""
    idx = url.find("?")
    return url[:idx] if idx != -1 else url


def _normalize_url_for_cdx(url: str) -> str:
    """Simple URL normalization for CDX lookup comparison."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = parsed.query
    return f"{scheme}://{netloc}{path}" + (f"?{query}" if query else "")
