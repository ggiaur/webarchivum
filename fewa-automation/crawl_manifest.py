"""Append-only, deterministic, hash-bound H0/H1/H2 crawl evidence."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from urllib.parse import urlsplit


@dataclass(frozen=True)
class EdgeEvent:
    original_url: str
    canonical_url: str
    parent_canonical_url: str | None
    hop: int
    eligible: bool
    decision: str
    skip_reason: str | None
    plan_hash: str
    final_url: str | None = None
    edge_source_page: str | None = None
    policy_decision: str | None = None
    robots_decision: str | None = None
    security_decision: str | None = None
    scope_decision: str | None = None
    observed_at: str | None = None


def _hash(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("manifest_sha256", None)
    return sha256(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_manifest(manifest: dict) -> bool:
    supplied = manifest.get("manifest_sha256")
    return isinstance(supplied, str) and supplied == _hash(manifest)


def _same_host(left: str, right: str) -> bool:
    return urlsplit(left).hostname == urlsplit(right).hostname


def build_manifest(seed: str, plan_hash: str, events: list[EdgeEvent], captures: dict[str, bool], *,
                   stream_complete: bool = True) -> dict:
    """Derive a manifest only from a complete deterministic edge stream.

    H3 and all external edges remain auditable stream entries but are never
    capture requirements.  Same-hop parents are preserved as aliases; duplicate
    observations of the same parent/canonical/hop are malformed.
    """
    valid = bool(stream_complete and events)
    seen_edges: set[tuple[str, int, str | None]] = set()
    aliases: dict[tuple[str, int], set[str]] = {}
    minimum_hop: dict[str, int] = {seed: 0}
    ordered = sorted(events, key=lambda event: (event.hop, event.canonical_url, event.parent_canonical_url or "", event.original_url))
    for event in ordered:
        # Every observed edge needs all normative facts, including explicit
        # denials; absent data is not equivalent to an allowed edge.
        required = (event.original_url, event.canonical_url, event.final_url,
                    event.edge_source_page, event.policy_decision,
                    event.robots_decision, event.security_decision,
                    event.scope_decision, event.observed_at)
        if event.plan_hash != plan_hash or event.hop not in {1, 2, 3} or not all(required):
            valid = False
            continue
        key = (event.canonical_url, event.hop, event.parent_canonical_url)
        if key in seen_edges:
            valid = False
            continue
        seen_edges.add(key)
        aliases.setdefault((event.canonical_url, event.hop), set()).add(event.parent_canonical_url or "")
        if event.hop == 1 and event.parent_canonical_url != seed:
            valid = False
        elif event.hop > 1 and minimum_hop.get(event.parent_canonical_url or "") != event.hop - 1:
            valid = False
        external = not _same_host(seed, event.canonical_url)
        if event.hop == 3 and event.eligible:
            valid = False
        if external and event.eligible:
            valid = False
        if event.eligible and event.hop <= 2 and not external:
            previous = minimum_hop.get(event.canonical_url)
            if previous is not None and previous < event.hop:
                # An observation cannot replace a previous smaller-hop page.
                valid = False
            minimum_hop[event.canonical_url] = min(previous, event.hop) if previous is not None else event.hop

    required = {seed} | {url for url, hop in minimum_hop.items() if hop in {1, 2}}
    captured = {url for url, ok in captures.items() if ok}
    # Capturing H3, external URLs, or a URL absent from the aggregate means
    # capture telemetry is not aligned with the normative edge stream.
    if not captured.issubset(required):
        valid = False
    complete = valid and required.issubset(captured)
    payload = {
        "schema": "crawl_manifest.v1",
        "seed": seed,
        "plan_hash": plan_hash,
        "edge_stream_sha256": sha256(json.dumps([asdict(event) for event in ordered], sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest(),
        "edge_stream_complete": stream_complete,
        "edges": [asdict(event) for event in ordered],
        "parent_aliases": {f"{url}@{hop}": sorted(parent for parent in parents if parent)
                           for (url, hop), parents in sorted(aliases.items())},
        "required_capture_urls": sorted(required),
        "captured_urls": sorted(captured),
        "status": "complete" if complete else "crawl_incomplete",
    }
    payload["manifest_sha256"] = _hash(payload)
    return payload
