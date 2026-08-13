"""Strict structured locality classification with hash-bound provenance."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import base64
import json
from types import MappingProxyType
from typing import Any, Mapping, Protocol
import unicodedata


INJECTION_MARKERS = ("ignore previous", "system prompt", "utasításokat hagyd", "ignore all")
NORMALIZATION_VERSION = "unicode-nfc-utf8.v1"
TRUNCATION_VERSION = "none.v1"
SCHEMA_VALIDATOR_VERSION = "arch01-locality-schema.v2"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _json(value: Any) -> str:
    """Canonical serialisation; unsupported model values are invalid output."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Inspection:
    canonical_url: str
    rendered_text: str
    retrieved_at: str
    provider_result_id: str
    source_url: str | None = None


@dataclass(frozen=True)
class LocalityDecision:
    state: str  # prequalified | rejected | uncertain
    decision_source: str
    reason_code: str
    provenance: Mapping[str, Any]


class LLMProvider(Protocol):
    model_id: str
    model_digest: str
    def classify(self, prompt: dict[str, Any]) -> dict[str, Any]: ...


def _input_provenance(inspection: Inspection) -> dict[str, Any]:
    normalised = unicodedata.normalize("NFC", inspection.rendered_text).encode("utf-8")
    digest = sha256(normalised).hexdigest()
    return {
        "provider_result_id": inspection.provider_result_id,
        "canonical_url": inspection.canonical_url,
        "source_url": inspection.source_url or inspection.canonical_url,
        "retrieved_at": inspection.retrieved_at,
        "normalization_version": NORMALIZATION_VERSION,
        "truncation_version": TRUNCATION_VERSION,
        # The complete normalised artifact is immutable by its digest and kept
        # with the decision for independent exact-span verification.
        "input_artifact_ref": f"sha256:{digest}",
        "input_artifact_base64": base64.b64encode(normalised).decode("ascii"),
        "input_sha256": digest,
        "input_bytes": len(normalised),
    }


def _uncertain(source: str, reason: str, inspection: Inspection, **extra: Any) -> LocalityDecision:
    return LocalityDecision("uncertain", source, reason, _freeze({**_input_provenance(inspection), **extra}))


def _valid_spans(spans: Any, text: str) -> tuple[bool, tuple[dict[str, Any], ...]]:
    if not isinstance(spans, list) or not spans:
        return False, ()
    normalised = unicodedata.normalize("NFC", text)
    converted: list[dict[str, Any]] = []
    for span in spans:
        if not isinstance(span, dict):
            return False, ()
        start, end, quote = span.get("start"), span.get("end"), span.get("quote")
        if not isinstance(start, int) or not isinstance(end, int) or not isinstance(quote, str):
            return False, ()
        if not 0 <= start < end <= len(normalised) or normalised[start:end] != quote:
            return False, ()
        converted.append({"start": start, "end": end, "byte_start": len(normalised[:start].encode("utf-8")),
                          "byte_end": len(normalised[:end].encode("utf-8")), "quote": quote})
    return True, tuple(converted)


def classify_locality(inspection: Inspection, provider: LLMProvider | None, *, budget_available: bool,
                      prompt_template_version: str = "arch01-locality-v1") -> LocalityDecision:
    """Classify rendered content. Invalid/missing evidence can never approve."""
    if not budget_available:
        return _uncertain("budget_exhausted", "budget_exhausted", inspection)
    normalised_text = unicodedata.normalize("NFC", inspection.rendered_text)
    if any(marker in normalised_text.lower() for marker in INJECTION_MARKERS):
        return _uncertain("security_rejected", "prompt_injection_signal", inspection)
    if provider is None:
        return _uncertain("provider_failure", "provider_failed", inspection)
    prompt = {"schema_version": "arch01.locality.v1", "instruction": "Classify Fejér county relevance from rendered text only.",
              "url": inspection.canonical_url, "rendered_text": normalised_text}
    try:
        prompt_json = _json(prompt)
        output = provider.classify(prompt)
        output_json = _json(output)
    except Exception:
        return _uncertain("model_failure", "model_invalid_output", inspection,
                          model_id=getattr(provider, "model_id", "unknown"))
    verdict = output.get("verdict") if isinstance(output, dict) else None
    valid_spans, evidence_spans = _valid_spans(output.get("evidence_spans") if isinstance(output, dict) else None,
                                                normalised_text)
    provenance = {
        **_input_provenance(inspection),
        "prompt_sha256": sha256(prompt_json.encode()).hexdigest(),
        "prompt_template_version": prompt_template_version,
        "schema_validator_version": SCHEMA_VALIDATOR_VERSION,
        "model_id": getattr(provider, "model_id", "unknown"),
        "model_digest": getattr(provider, "model_digest", "unknown"),
        "model_parameters": _freeze(getattr(provider, "parameters", {})),
        "output_json": output_json,
        "output_sha256": sha256(output_json.encode()).hexdigest(),
        "evidence_spans": evidence_spans,
    }
    if verdict not in {"fejer_positive", "non_local", "uncertain"} or not valid_spans:
        return LocalityDecision("uncertain", "model_failure", "model_invalid_output", _freeze(provenance))
    if verdict == "fejer_positive":
        return LocalityDecision("prequalified", "llm", "locality_match", _freeze(provenance))
    if verdict == "non_local":
        return LocalityDecision("rejected", "llm", "non_local", _freeze(provenance))
    return LocalityDecision("uncertain", "llm", "content_uncertain", _freeze(provenance))
