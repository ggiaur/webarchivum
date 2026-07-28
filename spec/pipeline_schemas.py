# =============================================================================
# FEWA V3.1 — AI Pipeline & Worker Job Pydantic Sémák
# Vörösmarty Mihály Könyvtár, Székesfehérvár
# Verzió: 3.1.0 | Dátum: 2026-07-28
# Phase 4 — spec-first megközelítés
# =============================================================================

from typing import Literal, Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


# -----------------------------------------------------------------------------
# 1. Extraction Step Schemas (warcio + trafilatura)
# -----------------------------------------------------------------------------

class ExtractionInput(BaseModel):
    snapshot_id: UUID
    wacz_minio_path: str
    language: Literal["hu", "en"] = "hu"


class ExtractionOutput(BaseModel):
    snapshot_id: UUID
    raw_text: str
    page_count: int
    char_count: int
    content_hash: str = Field(description="SHA-256 a normalizált szövegre")
    simhash: str = Field(description="64-bit SimHash hex string (16 karakter)")
    extraction_method: Literal["trafilatura", "fallback_bs4"] = "trafilatura"
    extracted_at: datetime = Field(default_factory=datetime.now)


# -----------------------------------------------------------------------------
# 2. Metadata & NER Step Schemas (huSpaCy)
# -----------------------------------------------------------------------------

class NERInput(BaseModel):
    snapshot_id: UUID
    raw_text: str
    language: Literal["hu", "en"] = "hu"


class NEROutput(BaseModel):
    snapshot_id: UUID
    persons: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    misc_entities: List[str] = Field(default_factory=list)
    model_version: str = "hu_core_news_lg-3.7.0"
    processing_time_ms: int


# -----------------------------------------------------------------------------
# 3. Summarization & Keyword Step Schemas (Ollama LLM)
# -----------------------------------------------------------------------------

class SummarizationInput(BaseModel):
    snapshot_id: UUID
    raw_text: str
    llm_profile: Literal["fast", "balanced", "high_quality"] = "balanced"


class SummarizationOutput(BaseModel):
    snapshot_id: UUID
    summary: str
    ai_keywords: List[str] = Field(default_factory=list)
    matched_skos_concept_ids: List[UUID] = Field(default_factory=list)
    ollama_model: str = Field(description="pl. qwen2.5:7b")
    prompt_template_version: str = "summary-v2.1"
    llm_latency_ms: int


# -----------------------------------------------------------------------------
# 4. Chunking & Embedding Step Schemas (nomic-embed-text)
# -----------------------------------------------------------------------------

class ChunkingInput(BaseModel):
    snapshot_id: UUID
    raw_text: str
    chunk_size: int = Field(default=600, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)
    min_chunk_len: int = Field(default=50, ge=10)


class SingleChunkEmbedding(BaseModel):
    chunk_index: int
    text: str
    token_count: int
    embedding: List[float] = Field(description="768-dimenziós float tömb")
    page_url: Optional[str] = None
    char_offset: Optional[int] = None


class EmbeddingOutput(BaseModel):
    snapshot_id: UUID
    chunks: List[SingleChunkEmbedding]
    embedding_model: str = "nomic-embed-text"
    embedding_version: str = "1.5"
    total_tokens: int
    embedding_latency_ms: int


# -----------------------------------------------------------------------------
# 5. Quality Control (QC) Engine Schemas
# -----------------------------------------------------------------------------

class QCInput(BaseModel):
    snapshot_id: UUID
    raw_text: str
    char_count: int
    page_count: int
    has_summary: bool
    chunk_count: int


class QCOutput(BaseModel):
    snapshot_id: UUID
    score: int = Field(ge=0, le=100, description="Minőségértékelés 0-100 között")
    auto_reject: bool = Field(description="True ha score < 40")
    reasons: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.now)


# -----------------------------------------------------------------------------
# 6. Deduplication Check Schemas
# -----------------------------------------------------------------------------

class DedupCheckInput(BaseModel):
    content_hash: str
    simhash: str
    simhash_threshold: int = Field(default=3, ge=0, le=64)


class DedupCheckOutput(BaseModel):
    is_exact_duplicate: bool
    exact_match_snapshot_id: Optional[UUID] = None
    is_near_duplicate: bool
    near_match_snapshot_id: Optional[UUID] = None
    hamming_distance: Optional[int] = None


# -----------------------------------------------------------------------------
# 7. Arq Worker Job Payloads
# -----------------------------------------------------------------------------

class CrawlJobPayload(BaseModel):
    job_id: UUID
    site_id: UUID
    snapshot_id: UUID
    seed_url: HttpUrl
    depth: int = Field(default=3, ge=1, le=5)
    max_pages: int = Field(default=5000, ge=1)
    llm_profile: Literal["fast", "balanced", "high_quality"] = "balanced"
    retry_count: int = 0
    max_retries: int = 3


class EnrichJobPayload(BaseModel):
    job_id: UUID
    snapshot_id: UUID
    wacz_minio_path: str
    llm_profile: Literal["fast", "balanced", "high_quality"] = "balanced"
    force_reprocess: bool = False
    retry_count: int = 0
    max_retries: int = 3


class ReembedJobPayload(BaseModel):
    job_id: UUID
    target_embedding_model: str = "nomic-embed-text"
    target_embedding_version: str = "1.5"
    batch_size: int = Field(default=100, ge=1, le=1000)
