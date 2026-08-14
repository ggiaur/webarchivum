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


def test_catalog_import_requires_proof_that_detail_id_was_in_the_list_response():
    """A self-consistent hand-built detail must not bypass list enumeration."""
    import json

    raw = json.dumps(
        [{"Eredeti webcím (URL)": "https://unlisted.example/"}],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    provenance = tuple(sorted({
        "catalogue_origin": "https://fewa.vmk.hu",
        "detail_endpoint": "https://fewa.vmk.hu/tmp/all_unique_data.php",
        "detail_request": '{"id":999999,"ip":""}',
        "record_id": "999999",
        "original_url_field": "Eredeti webcím (URL)",
        "detail_response": raw,
        "detail_response_sha256": sha256(raw.encode()).hexdigest(),
    }.items()))
    unlisted = CatalogRecord(
        "https://fewa.vmk.hu/tmp/all_unique_data.php#record=999999",
        "https://unlisted.example/",
        "now",
        raw,
        "999999",
        provenance,
    )
    item = import_catalog(
        [unlisted],
        lambda _pinned: "Fejer",
        PositiveLLM(),
        budget_available=True,
        resolver=PUBLIC,
    )[0]
    assert item.pinned_url is None
    assert item.decision.state != "prequalified"


def test_manifest_rejects_eligible_capture_with_denied_policy_facts():
    seed = "https://example.org/"
    child = "https://example.org/child"
    contradictory = EdgeEvent(
        child,
        child,
        seed,
        1,
        True,
        "capture",
        None,
        "plan",
        final_url=child,
        edge_source_page=seed,
        policy_decision="denied",
        robots_decision="denied",
        security_decision="rejected",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    manifest = build_manifest(
        seed,
        "plan",
        [contradictory],
        {seed: True, child: True},
    )
    assert manifest["status"] == "crawl_incomplete"


def test_warc_parser_rejects_invalid_version_line():
    target = "https://example.org/"
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "archive/data.warc",
            ("WARC/not-a-version\r\nWARC-Type: response\r\n"
             f"WARC-Target-URI: {target}\r\nContent-Length: 0\r\n\r\n").encode(),
        )
        archive.writestr(
            "indexes/index.cdxj",
            f'org,example)/ 20260814000000 {{"url":"{target}"}}\n',
        )
    body = stream.getvalue()
    assert not verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok


@pytest.mark.parametrize(
    ("canonical_url", "final_url", "captured_url"),
    [
        ("https://evil.example/child", "https://evil.example/child", "https://evil.example/child"),
        ("https://example.org/child", "https://evil.example/final", "https://example.org/child"),
    ],
)
def test_manifest_derives_external_scope_from_urls_not_caller_claim(
    canonical_url, final_url, captured_url
):
    """External canonical or redirect-final URLs can never be captured."""
    seed = "https://example.org/"
    forged_in_scope = EdgeEvent(
        canonical_url,
        canonical_url,
        seed,
        1,
        True,
        "capture",
        None,
        "plan",
        final_url=final_url,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="in_scope",
        observed_at="2026-08-14T00:00:00Z",
    )
    manifest = build_manifest(
        seed,
        "plan",
        [forged_in_scope],
        {seed: True, captured_url: True},
    )
    assert manifest["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    ("canonical_url", "final_url"),
    [
        ("not-a-url", "https://evil.example/final"),
        ("https://example.org/child", "not-a-url"),
    ],
)
def test_manifest_does_not_treat_malformed_url_as_valid_external_evidence(
    canonical_url, final_url
):
    seed = "https://example.org/"
    malformed = EdgeEvent(
        canonical_url,
        canonical_url,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=final_url,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    manifest = build_manifest(seed, "plan", [malformed], {seed: True})
    assert manifest["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    ("seed", "canonical_url", "final_url"),
    [
        ("not-a-url", "https://evil.example/a", "https://evil.example/a"),
        ("https://example.org/", "http://2130706433/", "https://evil.example/a"),
        ("https://example.org/", "https://user@example.org/a", "https://evil.example/a"),
        ("https://example.org/", "https://example.org:8443/a", "https://evil.example/a"),
    ],
)
def test_manifest_invalid_url_mutations_never_become_external_skip_evidence(
    seed, canonical_url, final_url
):
    event = EdgeEvent(
        canonical_url,
        canonical_url,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=final_url,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    assert build_manifest(seed, "plan", [event], {seed: True})["status"] == "crawl_incomplete"


def test_terminal_dns_dot_is_same_authority_not_external_skip():
    seed = "https://example.org/"
    same_authority = "https://EXAMPLE.org.:443/child"
    forged_external = EdgeEvent(
        same_authority,
        same_authority,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=same_authority,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    manifest = build_manifest(seed, "plan", [forged_external], {seed: True})
    assert manifest["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    "url",
    ["https://0x7f000001./", "https://0x7f.0x0.0x0.0x1./"],
)
def test_terminal_dot_cannot_bypass_alternative_numeric_host_rejection(url):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(url, PUBLIC)


@pytest.mark.parametrize("url", ["https://example.org../", "https://example.org.../"])
def test_only_one_terminal_dns_root_dot_is_normalized(url):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(url, PUBLIC)


@pytest.mark.parametrize("separator", ["\u3002", "\uff0e", "\uff61"])
def test_idna_dot_variant_cannot_bypass_numeric_host_rejection(separator):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(f"https://0x7f000001{separator}/", PUBLIC)


@pytest.mark.parametrize("separator", ["\u3002", "\uff0e", "\uff61"])
def test_idna_terminal_dot_variant_is_not_forged_external_scope(separator):
    seed = "https://example.org/"
    same_authority = f"https://EXAMPLE.org{separator}/child"
    forged_external = EdgeEvent(
        same_authority,
        same_authority,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=same_authority,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    assert build_manifest(seed, "plan", [forged_external], {seed: True})["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    "url",
    [
        "https://0x7f\u30020x0\uff0e0x0\uff610x1/",
        "https://0177\uff610000\u30020000\uff0e0001/",
        "https://2130706433\u3002/",
    ],
)
def test_mixed_idna_dot_numeric_forms_remain_fail_closed(url):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(url, PUBLIC)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.org/a\u3002b", "https://example.org/a\u3002b"),
        ("https://example.org/a\uff0eb", "https://example.org/a\uff0eb"),
        ("https://example.org/a\uff61b", "https://example.org/a\uff61b"),
        ("https://example.org/a?q=x\u3002y", "https://example.org/a?q=x\u3002y"),
        ("https://example.org/a?q=x\uff0ey", "https://example.org/a?q=x\uff0ey"),
        ("https://example.org/a?q=x\uff61y", "https://example.org/a?q=x\uff61y"),
    ],
)
def test_idna_dot_translation_is_limited_to_hostname(url, expected):
    from url_security import normalize_url

    assert normalize_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://example .org/",
        "https://exa%zzmple.org/",
        "https://-example.org/",
        "https://example-.org/",
        "https://" + ".".join(["a" * 63] * 5) + "/",
    ],
)
def test_invalid_dns_hostname_syntax_is_rejected_before_resolution(url):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(url, PUBLIC)


def test_invalid_dns_hostname_cannot_be_recorded_as_external_skip():
    seed = "https://example.org/"
    invalid = "https://invalid host.example/"
    event = EdgeEvent(
        invalid,
        invalid,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=invalid,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    assert build_manifest(seed, "plan", [event], {seed: True})["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://münich.example/", "https://xn--mnich-kva.example/"),
        ("https://例え.テスト/", "https://xn--r8jz45g.xn--zckzah/"),
        ("https://árvíztűrő.hu/út?q=ő", "https://xn--rvztr-wqa0gx3bwi.hu/út?q=ő"),
    ],
)
def test_valid_international_dns_labels_remain_accepted(url, expected):
    from url_security import normalize_url

    assert normalize_url(url) == expected


@pytest.mark.parametrize("label", ["xn--a", "xn--abc", "xn--0", "xn--a-ecp"])
def test_malformed_ascii_idna_alabel_is_rejected(label):
    with pytest.raises(URLSecurityError):
        resolve_and_pin(f"https://{label}.example/", PUBLIC)


def test_malformed_ascii_idna_alabel_cannot_be_external_manifest_evidence():
    seed = "https://example.org/"
    invalid = "https://xn--a.example/"
    event = EdgeEvent(
        invalid,
        invalid,
        seed,
        1,
        False,
        "skip",
        "external",
        "plan",
        final_url=invalid,
        edge_source_page=seed,
        policy_decision="allowed",
        robots_decision="allowed",
        security_decision="allowed",
        scope_decision="external",
        observed_at="2026-08-14T00:00:00Z",
    )
    assert build_manifest(seed, "plan", [event], {seed: True})["status"] == "crawl_incomplete"


@pytest.mark.parametrize(
    ("address", "accepted"),
    [
        ("::ffff:93.184.216.34", True),
        ("::ffff:127.0.0.1", False),
        ("::ffff:169.254.169.254", False),
        ("::ffff:100.64.0.1", False),
        ("64:ff9b::5db8:d822", True),
        ("64:ff9b::7f00:1", False),
        ("64:ff9b::a9fe:a9fe", False),
        ("64:ff9b::6440:1", False),
        ("::5db8:d822", True),
        ("::7f00:1", False),
        ("::a9fe:a9fe", False),
        ("::6440:1", False),
    ],
)
def test_embedded_ipv4_publicness_is_decisive_for_all_supported_ipv6_forms(
    address, accepted
):
    if accepted:
        assert resolve_and_pin("https://example.org/", lambda _host: [address]).pinned_ip == address
    else:
        with pytest.raises(URLSecurityError):
            resolve_and_pin("https://example.org/", lambda _host: [address])


def test_mixed_public_nat64_and_nonpublic_answer_fails_closed():
    with pytest.raises(URLSecurityError):
        resolve_and_pin(
            "https://example.org/",
            lambda _host: ["64:ff9b::5db8:d822", "64:ff9b::a9fe:a9fe"],
        )


def _wacz_with_record_types(records, index_target):
    chunks = []
    for number, (record_type, target) in enumerate(records, 1):
        chunks.append(
            (
                "WARC/1.1\r\n"
                f"WARC-Type: {record_type}\r\n"
                f"WARC-Record-ID: <urn:uuid:qa-{number}>\r\n"
                "WARC-Date: 2026-08-14T00:00:00Z\r\n"
                f"WARC-Target-URI: {target}\r\n"
                "Content-Length: 0\r\n\r\n"
            ).encode()
        )
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("archive/data.warc", b"\r\n\r\n".join(chunks))
        archive.writestr(
            "indexes/index.cdxj",
            f'org,example)/ 20260814000000 {{"url":"{index_target}"}}\n',
        )
    return stream.getvalue()


@pytest.mark.parametrize(
    ("record_type", "accepted"),
    [
        ("warcinfo", False),
        ("request", False),
        ("metadata", False),
        ("response", True),
        ("resource", True),
        ("revisit", True),
    ],
)
def test_only_captured_content_record_types_bind_wacz_to_replay_index(
    record_type, accepted
):
    target = "https://example.org/"
    body = _wacz_with_record_types([(record_type, target)], target)
    assert verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok is accepted


def test_metadata_target_cannot_mask_different_captured_content_target():
    metadata_target = "https://example.org/metadata-only"
    captured_target = "https://example.org/captured"
    records = [("warcinfo", metadata_target), ("response", captured_target)]

    body = _wacz_with_record_types(records, metadata_target)
    assert not verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok

    body = _wacz_with_record_types(records, captured_target)
    assert verify_wacz(Store(body), "object", "version", sha256(body).hexdigest()).ok
