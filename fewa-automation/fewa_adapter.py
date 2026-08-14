"""Evidence-preserving adapter for the FEWA catalogue.

FEWA is a catalogue, never an archiving target.  Its list response contains
record identifiers and titles; the original source URL is resolved only from
the corresponding detail response's ``Eredeti webcím (URL)`` field.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Protocol, Sequence

from search_provider import CatalogRecord
from url_security import URLSecurityError, is_fewa_catalogue_url, normalize_url


FEWA_ORIGIN = "https://fewa.vmk.hu"
LIST_ENDPOINT = f"{FEWA_ORIGIN}/tmp/search_form_data.php"
DETAIL_ENDPOINT = f"{FEWA_ORIGIN}/tmp/all_unique_data.php"
ORIGINAL_URL_FIELD = "Eredeti webcím (URL)"


class FewaTransport(Protocol):
    def post_json(self, url: str, payload: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class FewaResolution:
    record_id: str
    title: str
    state: str  # resolved | review_required
    reason: str | None
    record: CatalogRecord | None
    provenance: tuple[tuple[str, str], ...]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class FewaCatalogueAdapter:
    """Enumerate FEWA and resolve every listed id via its detail endpoint."""

    def __init__(self, transport: FewaTransport, *, retrieved_at: str):
        self._transport = transport
        self._retrieved_at = retrieved_at

    def enumerate_resolutions(self) -> Sequence[FewaResolution]:
        list_request = {"category": "s_all", "autocomplete": ""}
        try:
            rows = self._transport.post_json(LIST_ENDPOINT, list_request)
        except Exception as exc:
            raise RuntimeError("FEWA catalogue list request failed") from exc
        if not isinstance(rows, list):
            raise RuntimeError("FEWA catalogue list response is not a list")

        list_body = _canonical_json(rows)
        output: list[FewaResolution] = []
        seen_ids: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or row.get("id") is None:
                raise RuntimeError("FEWA catalogue row lacks an id")
            record_id = str(row["id"])
            if not record_id or record_id in seen_ids:
                raise RuntimeError("FEWA catalogue ids must be unique and non-empty")
            seen_ids.add(record_id)
            title = str(row.get("uniform_title", ""))
            detail_request = {"id": row["id"], "ip": ""}
            try:
                detail = self._transport.post_json(DETAIL_ENDPOINT, detail_request)
            except Exception:
                output.append(self._review(record_id, title, "detail_request_failed", list_body, detail_request, None, row))
                continue
            output.append(self._resolve(record_id, title, list_body, row, detail_request, detail))
        return tuple(output)

    def enumerate_records(self) -> Sequence[CatalogRecord]:
        """Return only source URLs verified from per-record raw detail evidence.

        Callers that need audit visibility for rejected rows use
        :meth:`enumerate_resolutions`; malformed/missing details never become
        candidates merely because they appeared in the catalogue list.
        """
        return tuple(item.record for item in self.enumerate_resolutions() if item.record is not None)

    def _resolve(self, record_id: str, title: str, list_body: str, list_row: dict[str, Any],
                 detail_request: dict[str, Any], detail: Any) -> FewaResolution:
        if not isinstance(detail, list) or not detail or not isinstance(detail[0], dict):
            return self._review(record_id, title, "detail_invalid", list_body, detail_request, detail, list_row)
        original = detail[0].get(ORIGINAL_URL_FIELD)
        if not isinstance(original, str) or not original.strip():
            return self._review(record_id, title, "original_url_missing", list_body, detail_request, detail, list_row)
        raw_url = original.strip()
        try:
            canonical = normalize_url(raw_url)
            if is_fewa_catalogue_url(canonical):
                raise URLSecurityError("FEWA catalogue URL is not an archive candidate")
        except URLSecurityError:
            return self._review(record_id, title, "original_url_rejected", list_body, detail_request, detail, list_row)
        raw_detail = _canonical_json(detail)
        provenance = self._provenance(record_id, list_body, list_row, detail_request, raw_detail)
        record_url = f"{DETAIL_ENDPOINT}#record={record_id}"
        return FewaResolution(record_id, title, "resolved", None,
                              CatalogRecord(record_url, canonical, self._retrieved_at, raw_detail,
                                            record_id, provenance), provenance)

    def _review(self, record_id: str, title: str, reason: str, list_body: str,
                detail_request: dict[str, Any], detail: Any, list_row: dict[str, Any] | None = None) -> FewaResolution:
        raw_detail = _canonical_json(detail) if detail is not None else ""
        return FewaResolution(record_id, title, "review_required", reason, None,
                              self._provenance(record_id, list_body, list_row, detail_request, raw_detail))

    def _provenance(self, record_id: str, list_body: str, list_row: dict[str, Any] | None, detail_request: dict[str, Any],
                    raw_detail: str) -> tuple[tuple[str, str], ...]:
        return tuple(sorted({
            "catalogue_origin": FEWA_ORIGIN,
            "list_endpoint": LIST_ENDPOINT,
            "list_request": _canonical_json({"category": "s_all", "autocomplete": ""}),
            # The full canonical response is an immutable input artifact in
            # this isolated adapter.  S3 may replace this with a
            # content-addressed object reference, but must preserve the hash
            # and exact row evidence below.
            "list_response": list_body,
            "list_response_sha256": sha256(list_body.encode()).hexdigest(),
            "list_row": _canonical_json(list_row) if list_row is not None else "",
            "list_row_sha256": sha256(_canonical_json(list_row).encode()).hexdigest() if list_row is not None else "",
            "detail_endpoint": DETAIL_ENDPOINT,
            "detail_request": _canonical_json(detail_request),
            "detail_response": raw_detail,
            "detail_response_sha256": sha256(raw_detail.encode()).hexdigest(),
            "record_id": record_id,
            "original_url_field": ORIGINAL_URL_FIELD,
            "retrieved_at": self._retrieved_at,
        }.items()))
