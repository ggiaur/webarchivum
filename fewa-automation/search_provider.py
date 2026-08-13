"""Injected discovery-search contract; no provider credential is embedded."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Sequence


class SearchProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    provider_result_id: str
    title: str
    snippet: str
    url: str
    retrieved_at: str


class SearchProvider(Protocol):
    def search(self, query: str) -> Sequence[ProviderResult]: ...


@dataclass(frozen=True)
class CatalogRecord:
    """A source site listed by an external catalogue such as FEWA.

    ``catalog_url`` is provenance only; it is never emitted as the discovered
    archive candidate.  ``raw_evidence`` preserves the rendered catalogue row
    used to locate the source URL.
    """
    catalog_record_url: str
    source_url: str
    retrieved_at: str
    raw_evidence: str
    catalog_record_id: str | None = None
    provenance: tuple[tuple[str, str], ...] = ()


class CatalogProvider(Protocol):
    def enumerate_records(self) -> Sequence[CatalogRecord]: ...


def county_queries() -> tuple[str, ...]:
    """Broad, real query families for county-wide discovery, not just FEWA."""
    topics = ("helytörténet", "intézmény", "önkormányzat", "civil szervezet", "kulturális örökség")
    return tuple(f'"Fejér vármegye" {topic}' for topic in topics)
