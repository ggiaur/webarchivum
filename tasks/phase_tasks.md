# FEWA V3.1 — Atomikus Fejlesztési Feladatlista & Acceptance Tesztek

> **Verzió:** 3.1.0 | **Dátum:** 2026-07-28
> **Szerző:** @architect (AI Agent)
> **Alapelv:** Spec-first + AI-native TDD. Minden feladathoz gépileg futtatható acceptance teszt tartozik.

---

## Áttekintő Fázistérkép

```
Fázis 5.1: Core Infrastructure & Configuration (FastAPI, asyncpg, Redis, MinIO)
        ↓
Fázis 5.2: Authentication & RBAC (JWT RS256, Middleware, Auth endpoints)
        ↓
Fázis 5.3: Core Domain Services (Sites, Snapshots, Municipalities, Thesaurus)
        ↓
Fázis 5.4: AI Pipeline Services (Extraction, NER, Summary, Embedding, QC, Dedup)
        ↓
Fázis 5.5: Arq Worker Engine & Async Job Handlers (Crawl, Enrich, Reembed)
        ↓
Fázis 5.6: Search & RAG Services (Hybrid Search, RAG Guardrails, OAI-PMH Provider)
        ↓
Fázis 5.7: Frontend SSR (Next.js 15) & Admin SPA (React + Vite)
```

---

## FÁZIS 5.1 — Core Infrastructure & Config

### Feladat 5.1.1: Environment Configuration & Pydantic Settings

- **Bemenet**: `.env.example`
- **Kimenet**:
  - `fewa-v3-backend/app/core/config.py` (`Settings` class)
  - `fewa-v3-backend/tests/test_config.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_config.py` — PASS
  - Hibás `.env` esetén a rendszer indításkor azonnal letilt és hibaüzenetet ad.
- **Tiltott**: Hardcoded jelszó/secret használata.

### Feladat 5.1.2: PostgreSQL Async Connection Pool & Database Healthcheck

- **Bemenet**: `spec/schema.sql`, `app/core/config.py`
- **Kimenet**:
  - `fewa-v3-backend/app/core/db.py` (asyncpg connection pool)
  - `fewa-v3-backend/tests/test_db.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_db.py` — PASS
  - `GET /api/health` az adatbázis kapcsolatot "ok"-ként jelzi.

### Feladat 5.1.3: Redis Szétválasztás (db=0 Queue, db=1 Cache)

- **Bemenet**: `app/core/config.py`
- **Kimenet**:
  - `fewa-v3-backend/app/core/redis.py` (`get_queue_redis()`, `get_cache_redis()`)
  - `fewa-v3-backend/tests/test_redis.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_redis.py` — PASS
  - A `db=0`-ra írt kulcs nem érhető el `db=1`-ből (izoláció igazolt).

### Feladat 5.1.4: MinIO S3 Kliens & Bucket Versioning/Lock Client

- **Bemenet**: `app/core/config.py`
- **Kimenet**:
  - `fewa-v3-backend/app/core/minio_client.py`
  - `fewa-v3-backend/tests/test_minio.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_minio.py` — PASS
  - Teszt WACZ fájl feltöltése, SHA-256 ellenőrzése és letöltése.

---

## FÁZIS 5.2 — Authentication & RBAC

### Feladat 5.2.1: JWT RS256 Kulcspár & Token Szolgáltatás

- **Bemenet**: `spec/openapi.yaml` (LoginRequest, TokenResponse)
- **Kimenet**:
  - `fewa-v3-backend/app/core/security.py` (bcrypt hashing, JWT encode/decode)
  - `fewa-v3-backend/tests/test_security.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_security.py` — PASS
  - Érvénytelen aláírású vagy lejárt token dekódolása `JWTError`-t dob.

### Feladat 5.2.2: RBAC Decorator & Security Middleware

- **Bemenet**: `spec/openapi.yaml` (SecuritySchemes, User Roles)
- **Kimenet**:
  - `fewa-v3-backend/app/api/deps.py` (`require_role(RoleEnum)`)
  - `fewa-v3-backend/tests/test_rbac.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_rbac.py` — PASS
  - `viewer` szerepkörű token HTTP 403-at kap a `/api/admin/queue` hívásakor.

### Feladat 5.2.3: Auth API Végpontok (Login, Refresh, Logout)

- **Bemenet**: `spec/openapi.yaml` (`/api/auth/*`)
- **Kimenet**:
  - `fewa-v3-backend/app/api/v1/auth.py`
  - `fewa-v3-backend/tests/test_auth_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_auth_api.py` — PASS
  - `/api/auth/login` érvényes credentiallal HTTP 200 + `access_token` + `refresh_token` ad.
  - `/api/auth/logout` után a `refresh_token` használata HTTP 401-et ad.

---

## FÁZIS 5.3 — Core Domain Services & APIs

### Feladat 5.3.1: Municipalities API Végpont

- **Bemenet**: `spec/schema.sql` (`municipalities`), `spec/openapi.yaml` (`GET /api/municipalities`)
- **Kimenet**:
  - `fewa-v3-backend/app/api/v1/municipalities.py`
  - `fewa-v3-backend/tests/test_municipalities.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_municipalities.py` — PASS
  - Csak az `is_active = true` rekordok jelennek meg `sort_order` szerint rendezve.

### Feladat 5.3.2: Sites CRUD Service & API

- **Bemenet**: `spec/schema.sql` (`sites`), `spec/openapi.yaml` (`/api/admin/sites`)
- **Kimenet**:
  - `fewa-v3-backend/app/crud/sites.py`
  - `fewa-v3-backend/app/api/v1/sites.py`
  - `fewa-v3-backend/tests/test_sites_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_sites_api.py` — PASS
  - Új site beszúrása `priority`, `category`, `municipality_id` és `oszk_status` adatokkal. Duplicate domain esetén HTTP 409.

### Feladat 5.3.3: SKOS Tezaurusz Service & API

- **Bemenet**: `spec/schema.sql` (`skos_concepts`), `spec/openapi.yaml` (`/api/thesaurus`)
- **Kimenet**:
  - `fewa-v3-backend/app/crud/thesaurus.py`
  - `fewa-v3-backend/app/api/v1/thesaurus.py`
  - `fewa-v3-backend/tests/test_thesaurus_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_thesaurus_api.py` — PASS
  - Fulltext keresés a `pref_label_hu` és `alt_labels` mezőkben trigram/GIN index-el.

---

## FÁZIS 5.4 — AI Pipeline Services

### Feladat 5.4.1: Text Extraction Engine (WARC/WACZ → Raw Text)

- **Bemenet**: `spec/pipeline_schemas.py` (`ExtractionInput`, `ExtractionOutput`)
- **Kimenet**:
  - `fewa-v3-backend/app/pipeline/extraction.py` (`trafilatura` + `warcio`)
  - `fewa-v3-backend/tests/test_pipeline_extraction.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_pipeline_extraction.py` — PASS
  - Teszt WACZ fájlból tiszta magyar szöveg és SHA-256 / SimHash számítása.

### Feladat 5.4.2: NER & Keyword Extraction (huSpaCy)

- **Bemenet**: `spec/pipeline_schemas.py` (`NERInput`, `NEROutput`)
- **Kimenet**:
  - `fewa-v3-backend/app/pipeline/ner.py`
  - `fewa-v3-backend/tests/test_pipeline_ner.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_pipeline_ner.py` — PASS
  - Személyek, szervezetek és helyszínek kinyerése teszt magyar szövegből.

### Feladat 5.4.3: Ollama Summarization & AI Cache Engine

- **Bemenet**: `spec/pipeline_schemas.py` (`SummarizationInput`, `SummarizationOutput`)
- **Kimenet**:
  - `fewa-v3-backend/app/pipeline/summarization.py`
  - `fewa-v3-backend/tests/test_pipeline_summary.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_pipeline_summary.py` — PASS
  - Második futtatásra a Redis `db=1` cache-ből 0ms alatt adja vissza az eredményt, Ollama hívás nélkül.

### Feladat 5.4.4: Chunking & pgvector Embedding Engine (nomic-embed-text)

- **Bemenet**: `spec/pipeline_schemas.py` (`ChunkingInput`, `EmbeddingOutput`)
- **Kimenet**:
  - `fewa-v3-backend/app/pipeline/embedding.py`
  - `fewa-v3-backend/tests/test_pipeline_embedding.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_pipeline_embedding.py` — PASS
  - 600 tokenes mondathatár-alapú chunking, 768-dimenziós vektorok generálása és mentése a `page_chunks` táblába.

### Feladat 5.4.5: Quality Control (QC) & SimHash Dedup Engine

- **Bemenet**: `spec/pipeline_schemas.py` (`QCInput`, `QCOutput`, `DedupCheckInput`, `DedupCheckOutput`)
- **Kimenet**:
  - `fewa-v3-backend/app/pipeline/qc_dedup.py`
  - `fewa-v3-backend/tests/test_pipeline_qc_dedup.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_pipeline_qc_dedup.py` — PASS
  - Hamming-távolság ≤ 3 esetén duplikátum jelzése, score < 40 esetén `auto_reject = true`.

---

## FÁZIS 5.5 — Arq Worker Engine & Async Jobs

### Feladat 5.5.1: Arq Worker Architecture & Job Registry

- **Bemenet**: `spec/pipeline_schemas.py` (Job Payloads)
- **Kimenet**:
  - `fewa-v3-backend/app/workers/arq_worker.py`
  - `fewa-v3-backend/tests/test_arq_worker.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_arq_worker.py` — PASS
  - Feladat feladása a queue-ra, sikeres lefutás, `jobs` tábla `duration_ms` és státusz frissítése.

### Feladat 5.5.2: Ingest & Crawl Trigger API (`/api/admin/ingest`)

- **Bemenet**: `spec/openapi.yaml` (`POST /api/admin/ingest`)
- **Kimenet**:
  - `fewa-v3-backend/app/api/v1/jobs.py`
  - `fewa-v3-backend/tests/test_jobs_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_jobs_api.py` — PASS
  - HTTP 202 Accepted válasz Arq job azonosítóval.

---

## FÁZIS 5.6 — Search, RAG & OAI-PMH

### Feladat 5.6.1: Hibrid Search Engine (tsvector BM25 + pgvector HNSW + RRF)

- **Bemenet**: `spec/openapi.yaml` (`GET /api/search`)
- **Kimenet**:
  - `fewa-v3-backend/app/services/search_service.py`
  - `fewa-v3-backend/app/api/v1/search.py`
  - `fewa-v3-backend/tests/test_search_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_search_api.py` — PASS
  - Keresés kulcsszóra és leíró szövegre, találati lista rrf_score szerint rendezve < 100ms válaszidővel.

### Feladat 5.6.2: RAG Engine with Strict Guardrails (`/api/rag`)

- **Bemenet**: `spec/openapi.yaml` (`POST /api/rag`)
- **Kimenet**:
  - `fewa-v3-backend/app/services/rag_service.py`
  - `fewa-v3-backend/app/api/v1/rag.py`
  - `fewa-v3-backend/tests/test_rag_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_rag_api.py` — PASS
  - `confidence_score < 0.6` esetén `"Nincs elegendő bizonyíték az archívumban."` válasz.
  - `ai_traces` bejegyzés automatikus mentése.

### Feladat 5.6.3: OAI-PMH 2.0 Provider (`/oai`)

- **Bemenet**: `spec/openapi.yaml` (`GET /oai`), Dublin Core specifikáció
- **Kimenet**:
  - `fewa-v3-backend/app/services/oaipmh_service.py`
  - `fewa-v3-backend/app/api/v1/oaipmh.py`
  - `fewa-v3-backend/tests/test_oaipmh_api.py`
- **Acceptance kritérium**:
  - `pytest fewa-v3-backend/tests/test_oaipmh_api.py` — PASS
  - Mind a 6 OAI-PMH ige W3C valid XML-t ad vissza `oai_dc` formátumban. Keyset pagination `resumptionToken`-nel.

---

## FÁZIS 5.7 — Frontend & Admin UI

### Feladat 5.7.1: Next.js 15 SSR Publikus Kereső & Replay UI

- **Bemenet**: `spec/openapi.yaml` (Public APIs)
- **Kimenet**:
  - `fewa-v3-frontend/` (Next.js App Router, Tailwind/Vanilla CSS)
  - WCAG 2.1 AA accessibility audit report
- **Acceptance kritérium**:
  - Lighthouse Accessibility ≥ 95, axe-core 0 kritikus hiba.

### Feladat 5.7.2: React Admin SPA (Vite + React Router + TanStack Query)

- **Bemenet**: `spec/openapi.yaml` (Admin APIs)
- **Kimenet**:
  - `fewa-v3-admin/` (Kurátori várólista, Sites prioritás kezelő, SKOS tezaurusz szerkesztő)
- **Acceptance kritérium**:
  - Role-based routing, JWT token auto-refresh, Queue approve/reject akciók azonnali státuszfrissítéssel.
