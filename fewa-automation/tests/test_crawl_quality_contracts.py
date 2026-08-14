import sys
from pathlib import Path
from io import BytesIO
import zipfile
sys.path.insert(0, str(Path(__file__).parent.parent))
from crawl_manifest import EdgeEvent, build_manifest
from qa_gate import ReplayEvidence, evaluate
from wacz_integrity import verify_wacz
from wacz_integrity import WaczVerification
from executor import build_plan
from url_security import resolve_and_pin
from hashlib import sha256


def event(url, parent, hop, eligible=True, plan="p"):
    return EdgeEvent(
        url, url, parent, hop, eligible, "capture" if eligible else "skip", None if eligible else "depth_limit", plan,
        final_url=url, edge_source_page=parent or url, policy_decision="allowed",
        robots_decision="allowed", security_decision="allowed", scope_decision="in_scope",
        observed_at="2026-08-13T00:00:00Z",
    )


def test_h0_h1_h2_manifest_is_complete_and_h3_is_evidence_only():
    seed = "https://fewa.vmk.hu/"
    manifest = build_manifest(seed, "p", [event("https://fewa.vmk.hu/a", seed, 1),
                                           event("https://fewa.vmk.hu/b", "https://fewa.vmk.hu/a", 2),
                                           event("https://fewa.vmk.hu/c", "https://fewa.vmk.hu/b", 3, eligible=False)],
                              {seed: True, "https://fewa.vmk.hu/a": True, "https://fewa.vmk.hu/b": True})
    assert manifest["status"] == "complete"
    assert "https://fewa.vmk.hu/c" not in manifest["required_capture_urls"]


def test_missing_h1_is_review_required_not_success():
    seed = "https://fewa.vmk.hu/"
    manifest = build_manifest(seed, "p", [event("https://fewa.vmk.hu/a", seed, 1)], {seed: True})
    gate = evaluate(manifest, wacz_ok=True, replay_ok=True, telemetry_complete=True)
    assert (manifest["status"], gate.outcome) == ("crawl_incomplete", "review_required")


def test_manifest_requires_explicit_policy_robots_security_scope_and_timestamp_facts():
    seed = "https://example.org/"
    incomplete = EdgeEvent("https://example.org/a", "https://example.org/a", seed, 1, True,
                           "capture", None, "p", final_url="https://example.org/a",
                           edge_source_page=seed, policy_decision="allowed")
    manifest = build_manifest(seed, "p", [incomplete], {seed: True, "https://example.org/a": True})
    assert manifest["status"] == "crawl_incomplete"


def test_every_deny_or_unknown_policy_fact_forces_ineligible_skip():
    seed = "https://example.org/"
    child = "https://example.org/a"
    for field, value, skip in (
        ("policy_decision", "denied", "policy_denied"),
        ("robots_decision", "denied", "robots_denied"),
        ("security_decision", "rejected", "security_rejected"),
    ):
        facts = {"policy_decision": "allowed", "robots_decision": "allowed",
                 "security_decision": "allowed", "scope_decision": "in_scope"}
        facts[field] = value
        candidate = EdgeEvent(child, child, seed, 1, False, "skip", skip, "p", final_url=child,
                              edge_source_page=seed, observed_at="now", **facts)
        status = build_manifest(seed, "p", [candidate], {seed: True})["status"]
        # A correctly evidenced exclusion can be a complete exploration, but
        # it never becomes a capture requirement or eligible page.
        assert status == "complete"
        assert child not in build_manifest(seed, "p", [candidate], {seed: True})["required_capture_urls"]
    # Scope is derived from URLs; a same-host edge cannot self-label external.
    forged_scope = EdgeEvent(child, child, seed, 1, False, "skip", "external", "p", final_url=child,
                             edge_source_page=seed, observed_at="now", policy_decision="allowed",
                             robots_decision="allowed", security_decision="allowed", scope_decision="external")
    assert build_manifest(seed, "p", [forged_scope], {seed: True})["status"] == "crawl_incomplete"
    unknown = EdgeEvent(child, child, seed, 1, False, "skip", "policy_denied", "p", final_url=child,
                        edge_source_page=seed, observed_at="now", policy_decision="unknown",
                        robots_decision="allowed", security_decision="allowed", scope_decision="in_scope")
    assert build_manifest(seed, "p", [unknown], {seed: True})["status"] == "crawl_incomplete"


def test_scope_is_derived_from_canonical_and_redirect_final_urls_not_caller_claim():
    seed = "https://example.org/"
    for canonical, final in (("https://evil.example/a", "https://evil.example/a"),
                             ("https://example.org/a", "https://evil.example/final")):
        forged = EdgeEvent(canonical, canonical, seed, 1, True, "capture", None, "p",
                            final_url=final, edge_source_page=seed, policy_decision="allowed",
                            robots_decision="allowed", security_decision="allowed", scope_decision="in_scope",
                            observed_at="2026-08-14T00:00:00Z")
        assert build_manifest(seed, "p", [forged], {seed: True, canonical: True})["status"] == "crawl_incomplete"


def test_objectively_external_edge_is_only_valid_as_external_skip_evidence():
    seed = "https://example.org/"
    external = "https://evil.example/a"
    skipped = EdgeEvent(external, external, seed, 1, False, "skip", "external", "p", final_url=external,
                        edge_source_page=seed, policy_decision="allowed", robots_decision="allowed",
                        security_decision="allowed", scope_decision="external", observed_at="now")
    manifest = build_manifest(seed, "p", [skipped], {seed: True})
    assert manifest["status"] == "complete"
    assert external not in manifest["required_capture_urls"]


def test_malformed_canonical_or_redirect_final_is_not_a_valid_external_skip():
    seed = "https://example.org/"
    for canonical, final in (("https://example.org:not-a-port/", "https://evil.example/a"),
                             ("https://example.org/a", "https://evil.example:not-a-port/")):
        malformed = EdgeEvent(canonical, canonical, seed, 1, False, "skip", "external", "p", final_url=final,
                              edge_source_page=seed, policy_decision="allowed", robots_decision="allowed",
                              security_decision="allowed", scope_decision="external", observed_at="now")
        assert build_manifest(seed, "p", [malformed], {seed: True})["status"] == "crawl_incomplete"


def test_hash_bound_replay_evidence_is_required_for_a_positive_gate():
    seed = "https://example.org/"
    manifest = build_manifest(seed, "p", [event("https://example.org/a", seed, 1)],
                              {seed: True, "https://example.org/a": True})
    replay = ReplayEvidence.create(manifest["manifest_sha256"], "a" * 64, "now", "browsertrix-qa/1.14.1", "passed")
    verification = WaczVerification(True, "a" * 64)
    assert evaluate(manifest, wacz_ok=verification, replay_ok=replay, telemetry_complete=True,
                    verified_wacz_sha256="a" * 64).outcome == "qc_passed_pending_release"
    assert evaluate(manifest, wacz_ok=verification, replay_ok=replay, telemetry_complete=True,
                    verified_wacz_sha256="b" * 64).outcome == "review_required"
    assert evaluate(manifest, wacz_ok=True, replay_ok=replay, telemetry_complete=True,
                    verified_wacz_sha256="a" * 64).outcome == "review_required"


class Store:
    def __init__(self, body): self.body = body
    def read_version(self, key, version): return self.body


def test_wacz_is_reread_and_requires_warc_and_cdxj():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("archive/data.warc", b"WARC/1.0\r\nWARC-Type: response\r\nWARC-Record-ID: <urn:uuid:1>\r\nWARC-Date: 2026-08-14T00:00:00Z\r\nWARC-Target-URI: https://example.org/\r\nContent-Length: 0\r\n\r\n")
        z.writestr("indexes/index.cdxj", 'org,example)/ 20260813000000 {"url":"https://example.org/"}\n')
    body = stream.getvalue()
    assert verify_wacz(Store(body), "x", "v1", sha256(body).hexdigest()).ok
    assert verify_wacz(Store(body), "x", "v2", "0" * 64).reason == "object_hash_mismatch"


def test_browsertrix_compressed_cdx_index_is_a_valid_replay_index():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("archive/data.warc", b"WARC/1.0\r\nWARC-Type: response\r\nWARC-Record-ID: <urn:uuid:2>\r\nWARC-Date: 2026-08-14T00:00:00Z\r\nWARC-Target-URI: https://example.org/\r\nContent-Length: 0\r\n\r\n")
        z.writestr("indexes/index.cdx", "com,example)/ 20260813000000 https://example.org/ text/html 200 abc - - 0 1 x.warc\n")
    body = stream.getvalue()
    assert verify_wacz(Store(body), "x", "v1", sha256(body).hexdigest()).ok


def test_warc_content_length_cannot_claim_more_bytes_than_the_record_contains():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("archive/data.warc", b"WARC/1.0\r\nWARC-Type: response\r\n"
                   b"WARC-Target-URI: https://example.org/\r\nContent-Length: 100\r\n\r\n")
        z.writestr("indexes/index.cdx", "com,example)/ 20260813000000 https://example.org/ text/html 200 x - - 0 1 x.warc\n")
    body = stream.getvalue()
    assert verify_wacz(Store(body), "x", "v1", sha256(body).hexdigest()).reason == "warc_parse_failed"


def test_warc_requires_exact_version_and_record_identity_headers():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("archive/data.warc", b"WARC/1.2\r\nWARC-Type: response\r\nWARC-Date: 2026-08-14T00:00:00Z\r\nWARC-Target-URI: https://example.org/\r\nContent-Length: 0\r\n\r\n")
        z.writestr("indexes/index.cdxj", 'org,example)/ 20260814000000 {"url":"https://example.org/"}\n')
    body = stream.getvalue()
    assert verify_wacz(Store(body), "x", "v", sha256(body).hexdigest()).reason == "warc_parse_failed"


def test_executor_is_pinned_and_does_not_accept_tag_only_image():
    seed = resolve_and_pin("https://example.org/", lambda _: ["93.184.216.34"])
    assert build_plan(seed, "browsertrix@sha256:" + "a" * 64, "egress-v1").seed.pinned_ip == "93.184.216.34"
    import pytest
    with pytest.raises(ValueError): build_plan(seed, "browsertrix:latest", "egress-v1")
