"""Provider-injected, fail-closed ARCH-01 discovery orchestration."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Iterable
from discovery_llm import Inspection, LocalityDecision, LLMProvider, classify_locality
from search_provider import SearchProvider, ProviderResult, CatalogRecord
from url_security import PinnedURL, URLSecurityError, is_fewa_catalogue_url, normalize_url, resolve_and_pin


def _verified_fewa_record(record: CatalogRecord) -> bool:
    """Accept only a record tied to the actual FEWA detail response.

    ``CatalogRecord`` is intentionally a generic data shape; this boundary
    must not turn a hand-built record with a claimed ``source_url`` into a
    FEWA import.  The adapter's response body, request and hashes are checked
    again immediately before it reaches URL validation/rendering.
    """
    provenance = dict(record.provenance)
    try:
        detail = json.loads(record.raw_evidence)
        detail_request = json.loads(provenance.get("detail_request", ""))
        original = detail[0]["Eredeti webcím (URL)"]
        canonical_original = normalize_url(original)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return False
    # A record URL is provenance only, but its fragment must identify the same
    # detail row.  The candidate URL is independently re-derived from the raw
    # detail response; a parallel CatalogRecord.source_url cannot rebind it.
    expected_record_url = f"https://fewa.vmk.hu/tmp/all_unique_data.php#record={record.catalog_record_id}"
    return (
        record.catalog_record_id is not None
        and provenance.get("catalogue_origin") == "https://fewa.vmk.hu"
        and provenance.get("detail_endpoint") == "https://fewa.vmk.hu/tmp/all_unique_data.php"
        and provenance.get("record_id") == str(record.catalog_record_id)
        and set(detail_request) == {"id", "ip"}
        and str(detail_request.get("id")) == str(record.catalog_record_id)
        and detail_request.get("ip") == ""
        and record.catalog_record_url == expected_record_url
        and provenance.get("original_url_field") == "Eredeti webcím (URL)"
        and provenance.get("detail_response") == record.raw_evidence
        and provenance.get("detail_response_sha256") == sha256(record.raw_evidence.encode()).hexdigest()
        and isinstance(original, str)
        and record.source_url == canonical_original
    )


@dataclass(frozen=True)
class DiscoveryCandidate:
    source: ProviderResult
    pinned_url: PinnedURL | None
    decision: LocalityDecision
    catalog_provenance: CatalogRecord | None = None


class DiscoveryRun(list[DiscoveryCandidate]):
    """Candidates plus visible run-level failure semantics for orchestrators."""
    def __init__(self, candidates: Iterable[DiscoveryCandidate] = (), *, state: str = "complete"):
        super().__init__(candidates)
        self.state = state  # complete | partial | failed


def _rejected(result: ProviderResult, reason: str, *, catalog: CatalogRecord | None = None) -> DiscoveryCandidate:
    decision = LocalityDecision("rejected", "security_rejected", reason,
                                {"canonical_url": result.url, "provider_result_id": result.provider_result_id})
    return DiscoveryCandidate(result, None, decision, catalog)


def discover(query: str, search: SearchProvider, renderer: Callable[[PinnedURL], str], llm: LLMProvider | None,
             *, budget_available: bool, resolver: Callable[[str], Iterable[str]]) -> DiscoveryRun:
    candidates: list[DiscoveryCandidate] = []
    try:
        results = search.search(query)
    except Exception:
        # No fabricated candidate is created for an unknown provider result.
        return DiscoveryRun(state="failed")
    run_state = "complete"
    for result in results:
        if is_fewa_catalogue_url(result.url):
            candidates.append(_rejected(result, "policy_rejected"))
            run_state = "partial"
            continue
        try:
            pinned = resolve_and_pin(result.url, resolver)
        except URLSecurityError:
            candidates.append(_rejected(result, "security_rejected"))
            run_state = "partial"
            continue
        try:
            text = renderer(pinned)
        except Exception:
            decision = LocalityDecision("uncertain", "provider_failure", "provider_failed",
                                        {"canonical_url": pinned.canonical_url,
                                         "provider_result_id": result.provider_result_id})
            run_state = "partial"
        else:
            decision = classify_locality(Inspection(pinned.canonical_url, text, result.retrieved_at,
                                                     result.provider_result_id, result.url), llm,
                                        budget_available=budget_available)
            if decision.decision_source in {"provider_failure", "budget_exhausted", "model_failure", "security_rejected"}:
                run_state = "partial"
        candidates.append(DiscoveryCandidate(result, pinned, decision))
    return DiscoveryRun(candidates, state=run_state)


def import_catalog(records: list[CatalogRecord], renderer: Callable[[PinnedURL], str], llm: LLMProvider | None,
                   *, budget_available: bool, resolver: Callable[[str], Iterable[str]]) -> DiscoveryRun:
    """Import only externally verified original URLs from FEWA detail evidence."""
    candidates: list[DiscoveryCandidate] = []
    run_state = "complete"
    for record in records:
        source = ProviderResult(record.catalog_record_id or record.source_url, "", record.raw_evidence,
                                record.source_url, record.retrieved_at)
        if not _verified_fewa_record(record):
            decision = LocalityDecision("uncertain", "security_rejected", "policy_rejected",
                                        {"catalog_record_url": record.catalog_record_url,
                                         "provider_result_id": source.provider_result_id})
            candidates.append(DiscoveryCandidate(source, None, decision, record))
            run_state = "partial"
            continue
        if is_fewa_catalogue_url(record.source_url):
            candidates.append(_rejected(source, "policy_rejected", catalog=record))
            run_state = "partial"
            continue
        try:
            pinned = resolve_and_pin(record.source_url, resolver)
        except URLSecurityError:
            candidates.append(_rejected(source, "security_rejected", catalog=record))
            run_state = "partial"
            continue
        try:
            rendered = renderer(pinned)
        except Exception:
            decision = LocalityDecision("uncertain", "provider_failure", "provider_failed",
                                        {"catalog_record_url": record.catalog_record_url,
                                         "raw_evidence": record.raw_evidence,
                                         "provenance": record.provenance})
            run_state = "partial"
        else:
            decision = classify_locality(Inspection(pinned.canonical_url, rendered, record.retrieved_at,
                                                     source.provider_result_id, record.source_url), llm,
                                        budget_available=budget_available)
            if decision.decision_source != "llm":
                run_state = "partial"
        candidates.append(DiscoveryCandidate(source, pinned, decision, record))
    return DiscoveryRun(candidates, state=run_state)
