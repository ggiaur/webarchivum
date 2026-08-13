"""Independent adversarial QA regressions for the isolated ARCH-01 S2 candidate.

These tests encode the normative ADR-0002 sections 2--4 and the product rule
that FEWA is catalogue provenance only.  They intentionally stay separate
from the builder-authored acceptance tests.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawl_manifest import EdgeEvent, build_manifest
from discovery_llm import Inspection, classify_locality
from discovery_worker import discover, import_catalog
from executor import build_plan
from qa_gate import ReplayEvidence, evaluate
from search_provider import CatalogRecord, ProviderResult
from url_security import URLSecurityError, resolve_and_pin
from wacz_integrity import verify_wacz


PUBLIC = lambda _hostname: ["93.184.216.34"]


class PositiveLLM:
    model_id = "qa-model"
    model_digest = "sha256:" + "a" * 64

    def classify(self, prompt):
        quote = "Fejer"
        return {
            "verdict": "fejer_positive",
            "evidence_spans": [
                {"start": 0, "end": len(quote), "quote": quote},
            ],
        }


def full_edge(url, parent, hop, *, eligible=True, plan="plan"):
    return EdgeEvent(
        url, url, parent, hop, eligible, "capture" if eligible else "skip", None, plan,
        final_url=url, edge_source_page=parent or url, policy_decision="allowed",
        robots_decision="allowed", security_decision="allowed", scope_decision="in_scope",
        observed_at="2026-08-13T00:00:00Z",
    )


def test_fewa_catalogue_portal_can_never_become_a_discovery_candidate():
    class FewaSearch:
        def search(self, _query):
            return [
                ProviderResult(
                    "fewa-catalogue",
                    "FEWA",
                    "catalogue",
                    "https://fewa.vmk.hu/",
                    "2026-08-13T00:00:00Z",
                )
            ]

    candidate = discover(
        "query",
        FewaSearch(),
        lambda _pinned: "Fejer catalogue",
        PositiveLLM(),
        budget_available=True,
        resolver=PUBLIC,
    )[0]
    assert candidate.decision.state != "prequalified"


def test_positive_llm_verdict_requires_at_least_one_exact_evidence_span():
    class EmptyEvidenceLLM(PositiveLLM):
        def classify(self, _prompt):
            return {"verdict": "fejer_positive", "evidence_spans": []}

    decision = classify_locality(
        Inspection("https://example.org/", "Fejer", "now", "result-1"),
        EmptyEvidenceLLM(),
        budget_available=True,
    )
    assert (decision.state, decision.reason_code) == (
        "uncertain",
        "model_invalid_output",
    )


def test_non_json_model_output_fails_closed_instead_of_crashing_worker():
    class NonJsonLLM(PositiveLLM):
        def classify(self, _prompt):
            return {
                "verdict": "fejer_positive",
                "evidence_spans": [{"start": 0, "end": 5, "quote": "Fejer"}],
                "not_json": {1, 2},
            }

    decision = classify_locality(
        Inspection("https://example.org/", "Fejer", "now", "result-1"),
        NonJsonLLM(),
        budget_available=True,
    )
    assert (decision.state, decision.reason_code) == (
        "uncertain",
        "model_invalid_output",
    )


@pytest.mark.parametrize(
    "url",
    ["https://0x7f000001/", "https://0x7f.0x0.0x0.0x1/"],
)
def test_alternative_hex_numeric_hosts_are_rejected_before_resolution(url):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(url, PUBLIC)


def test_malformed_port_is_a_security_rejection_not_an_uncaught_value_error():
    with pytest.raises(URLSecurityError):
        resolve_and_pin("https://example.org:not-a-port/", PUBLIC)


def test_empty_edge_stream_cannot_claim_a_complete_zero_page_crawl():
    seed = "https://example.org/"
    manifest = build_manifest(seed, "plan", [], {seed: True})
    assert manifest["status"] == "crawl_incomplete"


def test_tampered_manifest_hash_forces_review():
    seed = "https://example.org/"
    child = "https://example.org/child"
    manifest = build_manifest(
        seed,
        "plan",
        [full_edge(child, seed, 1)],
        {seed: True, child: True},
    )
    assert manifest["status"] == "complete"
    manifest["manifest_sha256"] = "0" * 64
    gate = evaluate(
        manifest,
        wacz_ok=True,
        replay_ok=True,
        telemetry_complete=True,
    )
    assert gate.outcome == "review_required"


class Store:
    def __init__(self, body):
        self.body = body

    def read_version(self, _key, _version):
        return self.body


def test_filename_only_fake_warc_and_replay_index_are_not_valid_wacz():
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("archive/data.warc.gz", b"not a WARC")
        archive.writestr("indexes/index.cdx.gz", b"not a replay index")
    body = stream.getvalue()
    assert not verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok


@pytest.mark.parametrize(
    "image",
    [
        "browsertrix@sha256:abc",
        "browsertrix@sha256:" + "g" * 64,
        "@sha256:" + "a" * 64,
    ],
)
def test_executor_rejects_malformed_or_missing_image_digest(image):
    seed = resolve_and_pin("https://example.org/", PUBLIC)
    with pytest.raises(ValueError):
        build_plan(seed, image, "egress-v1")


def test_fewa_detail_evidence_cannot_be_rebound_to_a_different_source_url():
    """The detail body's original URL, not a parallel field, is authoritative."""
    import json

    raw = json.dumps(
        [{"Eredeti webcím (URL)": "https://evidence.example/"}],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    provenance = tuple(sorted({
        "catalogue_origin": "https://fewa.vmk.hu",
        "detail_endpoint": "https://fewa.vmk.hu/tmp/all_unique_data.php",
        "detail_request": '{"id":1,"ip":""}',
        "record_id": "1",
        "original_url_field": "Eredeti webcím (URL)",
        "detail_response": raw,
        "detail_response_sha256": sha256(raw.encode()).hexdigest(),
    }.items()))
    rebound = CatalogRecord(
        "https://fewa.vmk.hu/tmp/all_unique_data.php#record=1",
        "https://attacker.example/",
        "now",
        raw,
        "1",
        provenance,
    )
    item = import_catalog(
        [rebound],
        lambda _pinned: "Fejer",
        PositiveLLM(),
        budget_available=True,
        resolver=PUBLIC,
    )[0]
    assert item.pinned_url is None
    assert item.decision.state != "prequalified"


def test_fewa_fully_qualified_trailing_dot_alias_is_also_self_portal():
    seed = resolve_and_pin("https://fewa.vmk.hu./", PUBLIC)
    with pytest.raises(ValueError, match="FEWA"):
        build_plan(seed, "browsertrix@sha256:" + "a" * 64, "egress-v1")


def test_missing_normative_edge_fields_cannot_produce_complete_manifest():
    seed = "https://example.org/"
    child = "https://example.org/child"
    event_without_source_policy_or_timestamp = EdgeEvent(
        child, child, seed, 1, True, "capture", None, "plan"
    )
    manifest = build_manifest(
        seed,
        "plan",
        [event_without_source_policy_or_timestamp],
        {seed: True, child: True},
    )
    assert manifest["status"] == "crawl_incomplete"


def test_replay_evidence_must_be_bound_to_the_verified_wacz_hash():
    seed = "https://example.org/"
    child = "https://example.org/child"
    manifest = build_manifest(
        seed,
        "plan",
        [full_edge(child, seed, 1)],
        {seed: True, child: True},
    )
    replay = ReplayEvidence.create(
        manifest["manifest_sha256"],
        "0" * 64,
        "now",
        "qa-checker",
        "passed",
    )
    # A bare boolean carries no digest, so it cannot prove that replay tested
    # the same versioned object whose WACZ verification supposedly succeeded.
    gate = evaluate(manifest, wacz_ok=True, replay_ok=replay, telemetry_complete=True)
    assert gate.outcome == "review_required"


def test_warc_declared_content_length_must_match_the_record_body():
    target = "https://example.org/"
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "archive/data.warc",
            ("WARC/1.0\r\nWARC-Type: response\r\n"
             f"WARC-Target-URI: {target}\r\nContent-Length: 999\r\n\r\n").encode(),
        )
        archive.writestr(
            "indexes/index.cdxj",
            f'org,example)/ 20260813000000 {{"url":"{target}"}}\n',
        )
    body = stream.getvalue()
    assert not verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok
