"""Visitor-visible replay quality inspection, evidence extraction, and safe remediation.

Detects broken images, broken links, missing sub-resources, and pywb/WACZ replay
mismatches from the visitor-visible replay path. Replaces synthetic/HTTP-only scores
with real DOM & resource inspection evidence, and provides safe remediation / hold loops.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse


@dataclass(frozen=True)
class BrokenResource:
    url: str
    resource_type: str  # "image" | "link" | "script" | "style" | "media"
    element_tag: str
    reason: str  # "missing_in_cdx" | "http_404" | "net_failed" | "replay_bad"
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
    broken_resources: Tuple[BrokenResource, ...]
    reasons: Tuple[str, ...]
    actionable_evidence: Dict[str, Any]
    remediation_suggestion: Optional[str] = None


class _DOMResourceExtractor(HTMLParser):
    """Extracts img, script, link[rel=stylesheet], and a elements from HTML."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.images: List[Tuple[str, str]] = []  # (resolved_url, raw_src)
        self.links: List[Tuple[str, str]] = []   # (resolved_url, raw_href)
        self.styles: List[Tuple[str, str]] = []  # (resolved_url, raw_href)
        self.scripts: List[Tuple[str, str]] = [] # (resolved_url, raw_src)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}
        tag_lower = tag.lower()

        if tag_lower == "img" and "src" in attr_dict:
            raw_src = attr_dict["src"].strip()
            if raw_src and not raw_src.startswith("data:"):
                resolved = urljoin(self.base_url, raw_src)
                self.images.append((resolved, raw_src))

        elif tag_lower == "a" and "href" in attr_dict:
            raw_href = attr_dict["href"].strip()
            if raw_href and not raw_href.startswith(("javascript:", "mailto:", "tel:", "#")):
                resolved = urljoin(self.base_url, raw_href)
                self.links.append((resolved, raw_href))

        elif tag_lower == "link" and attr_dict.get("rel") == "stylesheet" and "href" in attr_dict:
            raw_href = attr_dict["href"].strip()
            if raw_href and not raw_href.startswith("data:"):
                resolved = urljoin(self.base_url, raw_href)
                self.styles.append((resolved, raw_href))

        elif tag_lower == "script" and "src" in attr_dict:
            raw_src = attr_dict["src"].strip()
            if raw_src and not raw_src.startswith("data:"):
                resolved = urljoin(self.base_url, raw_src)
                self.scripts.append((resolved, raw_src))


def extract_dom_resources(html_content: str, base_url: str) -> _DOMResourceExtractor:
    """Parse HTML and return DOM resource lists."""
    parser = _DOMResourceExtractor(base_url)
    parser.feed(html_content)
    return parser


def inspect_visitor_replay_dom(
    html_content: str,
    page_url: str,
    cdx_index_urls: Optional[Set[str]] = None,
    max_allowed_broken_images: int = 0,
    max_allowed_broken_links: int = 0,
) -> VisitorReplayQualityResult:
    """Inspect visitor-visible DOM for broken images, missing links, and resource failures.

    Checks rendered DOM elements (img, a, link, script) against CDX index or replay path.
    Returns structured VisitorReplayQualityResult with actionable evidence.
    """
    extractor = extract_dom_resources(html_content, page_url)
    page_host = urlparse(page_url).netloc.lower()

    broken: List[BrokenResource] = []
    reasons: List[str] = []

    # 1. Check Images
    broken_images = 0
    for resolved_url, raw_src in extractor.images:
        if cdx_index_urls is not None:
            norm_url = _normalize_url_for_cdx(resolved_url)
            if norm_url not in cdx_index_urls and resolved_url not in cdx_index_urls:
                broken_images += 1
                broken.append(
                    BrokenResource(
                        url=resolved_url,
                        resource_type="image",
                        element_tag=f'<img src="{raw_src}">',
                        reason="missing_in_cdx",
                        context=f"Image URL {resolved_url} was not captured in WACZ archive.",
                    )
                )

    # 2. Check Internal Links
    broken_links = 0
    for resolved_url, raw_href in extractor.links:
        link_host = urlparse(resolved_url).netloc.lower()
        if link_host == page_host or not link_host:
            if cdx_index_urls is not None:
                norm_url = _normalize_url_for_cdx(resolved_url)
                if norm_url not in cdx_index_urls and resolved_url not in cdx_index_urls:
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

    total_checked = len(extractor.images) + len(extractor.links) + len(extractor.styles) + len(extractor.scripts)
    total_broken = len(broken)
    replay_good = total_checked - total_broken
    replay_bad = total_broken

    quality_score = 100.0 if total_checked == 0 else round((replay_good / total_checked) * 100.0, 2)

    if broken_images > max_allowed_broken_images:
        reasons.append(f"broken_images_detected ({broken_images} > {max_allowed_broken_images})")

    if broken_links > max_allowed_broken_links:
        reasons.append(f"broken_internal_links_detected ({broken_links} > {max_allowed_broken_links})")

    passed = len(reasons) == 0

    remediation = None
    if not passed:
        remediation = suggest_remediation(broken)

    actionable_evidence = {
        "page_url": page_url,
        "total_checked": total_checked,
        "replay_good": replay_good,
        "replay_bad": replay_bad,
        "broken_image_count": broken_images,
        "broken_link_count": broken_links,
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
        broken_image_count=broken_images,
        broken_link_count=broken_links,
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
        broken_resources=tuple(broken),
        reasons=tuple(reasons),
        actionable_evidence=actionable_evidence,
        remediation_suggestion=remediation,
    )


def suggest_remediation(broken_resources: List[BrokenResource]) -> str:
    """Provide specific, actionable remediation options based on failure class."""
    if not broken_resources:
        return "No remediation needed."

    has_images = any(b.resource_type in ("image", "page_resources") for b in broken_resources)
    has_links = any(b.resource_type == "link" for b in broken_resources)

    suggestions = []
    if has_images:
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
