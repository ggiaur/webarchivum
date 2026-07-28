# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 12:40

### AKTUÁLIS FÁZIS
Phase: 5 — Implementáció
Step: 5.7 — Frontend SSR (Next.js 15) & Admin SPA (React + Vite)
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
Phase 5.7 indítása: Next.js 15 publikus kereső & Replay UI és React Admin SPA előkészítése.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] Nincs nyitott blocker.

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1–1.6 — Phase 1 APPROVED: Domain Model (7 bounded context, eseményfolyam, ADR-0001)
- [x] 2.1–2.4 — Phase 2 APPROVED: PostgreSQL DDL schema (15 tábla, 3 trigger, 3 nézet, municipalities FK)
- [x] 3.1–3.3 — Phase 3 APPROVED: OpenAPI 3.1.0 contract (25 endpoint, /api/auth/login, /refresh, /logout)
- [x] 4.1 — `spec/pipeline_schemas.py` megírva: AI pipeline sémák (Extraction, NER, Summary, Embedding, QC, Dedup, Jobs)
- [x] 4.2 — `tasks/phase_tasks.md` megírva: atomikus feladatok gépileg futtatható pytest acceptance tesztekkel
- [x] 5.1.1–5.1.4 — Phase 5.1 COMPLETED: Environment Config, Async DB pool, Redis split, MinIO S3 (11/11 pytest PASS)
- [x] 5.2.1–5.2.3 — Phase 5.2 COMPLETED: JWT RS256, RBAC Security Middleware, Auth API (14/14 pytest PASS)
- [x] 5.3.1–5.3.3 — Phase 5.3 COMPLETED: Municipalities API, Sites CRUD, SKOS Thesaurus (9/9 pytest PASS)
- [x] 5.4.1–5.4.5 — Phase 5.4 COMPLETED: Extraction, NER, Summary, Embedding, QC, Dedup (11/11 pytest PASS)
- [x] 5.5.1–5.5.2 — Phase 5.5 COMPLETED: Arq Worker Architecture, Ingest & Jobs API (5/5 pytest PASS)
- [x] 5.6.1 — Hibrid Search Engine → `app/services/search_service.py`, `app/api/v1/search.py`, `tests/test_search_api.py` (3/3 pytest PASS)
- [x] 5.6.2 — RAG Engine & Guardrails → `app/services/rag_service.py`, `app/api/v1/rag.py`, `tests/test_rag_api.py` (3/3 pytest PASS)
- [x] 5.6.3 — OAI-PMH 2.0 Provider → `app/services/oaipmh_service.py`, `app/api/v1/oaipmh.py`, `tests/test_oaipmh_api.py` (3/3 pytest PASS)

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
- `docs/DOMAIN_MODEL.md` — LEZÁRVA 2026-07-28 (Phase 1 APPROVED)
- `docs/adr/0001-domain-boundaries.md` — LEZÁRVA 2026-07-28
- `spec/schema.sql` — LEZÁRVA 2026-07-28 (Phase 2 APPROVED)
- `spec/openapi.yaml` — LEZÁRVA 2026-07-28 (Phase 3 APPROVED)
- `spec/pipeline_schemas.py` — LEZÁRVA 2026-07-28 (Phase 4 COMPLETED)
- `tasks/phase_tasks.md` — LEZÁRVA 2026-07-28 (Phase 4 COMPLETED)
- `fewa-v3-backend/app/core/config.py` — LEZÁRVA 2026-07-28 (5.1.1 PASS)
- `fewa-v3-backend/tests/test_config.py` — LEZÁRVA 2026-07-28 (5.1.1 PASS)
- `fewa-v3-backend/app/core/db.py` — LEZÁRVA 2026-07-28 (5.1.2 PASS)
- `fewa-v3-backend/tests/test_db.py` — LEZÁRVA 2026-07-28 (5.1.2 PASS)
- `fewa-v3-backend/app/core/redis.py` — LEZÁRVA 2026-07-28 (5.1.3 PASS)
- `fewa-v3-backend/tests/test_redis.py` — LEZÁRVA 2026-07-28 (5.1.3 PASS)
- `fewa-v3-backend/app/core/minio_client.py` — LEZÁRVA 2026-07-28 (5.1.4 PASS)
- `fewa-v3-backend/tests/test_minio.py` — LEZÁRVA 2026-07-28 (5.1.4 PASS)
- `fewa-v3-backend/app/core/security.py` — LEZÁRVA 2026-07-28 (5.2.1 PASS)
- `fewa-v3-backend/tests/test_security.py` — LEZÁRVA 2026-07-28 (5.2.1 PASS)
- `fewa-v3-backend/app/api/deps.py` — LEZÁRVA 2026-07-28 (5.2.2 PASS)
- `fewa-v3-backend/tests/test_rbac.py` — LEZÁRVA 2026-07-28 (5.2.2 PASS)
- `fewa-v3-backend/app/api/v1/auth.py` — LEZÁRVA 2026-07-28 (5.2.3 PASS)
- `fewa-v3-backend/tests/test_auth_api.py` — LEZÁRVA 2026-07-28 (5.2.3 PASS)
- `fewa-v3-backend/app/api/v1/municipalities.py` — LEZÁRVA 2026-07-28 (5.3.1 PASS)
- `fewa-v3-backend/tests/test_municipalities.py` — LEZÁRVA 2026-07-28 (5.3.1 PASS)
- `fewa-v3-backend/app/crud/sites.py` — LEZÁRVA 2026-07-28 (5.3.2 PASS)
- `fewa-v3-backend/app/api/v1/sites.py` — LEZÁRVA 2026-07-28 (5.3.2 PASS)
- `fewa-v3-backend/tests/test_sites_api.py` — LEZÁRVA 2026-07-28 (5.3.2 PASS)
- `fewa-v3-backend/app/crud/thesaurus.py` — LEZÁRVA 2026-07-28 (5.3.3 PASS)
- `fewa-v3-backend/app/api/v1/thesaurus.py` — LEZÁRVA 2026-07-28 (5.3.3 PASS)
- `fewa-v3-backend/tests/test_thesaurus_api.py` — LEZÁRVA 2026-07-28 (5.3.3 PASS)
- `fewa-v3-backend/app/pipeline/extraction.py` — LEZÁRVA 2026-07-28 (5.4.1 PASS)
- `fewa-v3-backend/tests/test_pipeline_extraction.py` — LEZÁRVA 2026-07-28 (5.4.1 PASS)
- `fewa-v3-backend/app/pipeline/ner.py` — LEZÁRVA 2026-07-28 (5.4.2 PASS)
- `fewa-v3-backend/tests/test_pipeline_ner.py` — LEZÁRVA 2026-07-28 (5.4.2 PASS)
- `fewa-v3-backend/app/pipeline/summarization.py` — LEZÁRVA 2026-07-28 (5.4.3 PASS)
- `fewa-v3-backend/tests/test_pipeline_summary.py` — LEZÁRVA 2026-07-28 (5.4.3 PASS)
- `fewa-v3-backend/app/pipeline/embedding.py` — LEZÁRVA 2026-07-28 (5.4.4 PASS)
- `fewa-v3-backend/tests/test_pipeline_embedding.py` — LEZÁRVA 2026-07-28 (5.4.4 PASS)
- `fewa-v3-backend/app/pipeline/qc_dedup.py` — LEZÁRVA 2026-07-28 (5.4.5 PASS)
- `fewa-v3-backend/tests/test_pipeline_qc_dedup.py` — LEZÁRVA 2026-07-28 (5.4.5 PASS)
- `fewa-v3-backend/app/workers/arq_worker.py` — LEZÁRVA 2026-07-28 (5.5.1 PASS)
- `fewa-v3-backend/tests/test_arq_worker.py` — LEZÁRVA 2026-07-28 (5.5.1 PASS)
- `fewa-v3-backend/app/api/v1/jobs.py` — LEZÁRVA 2026-07-28 (5.5.2 PASS)
- `fewa-v3-backend/tests/test_jobs_api.py` — LEZÁRVA 2026-07-28 (5.5.2 PASS)
- `fewa-v3-backend/app/services/search_service.py` — LEZÁRVA 2026-07-28 (5.6.1 PASS)
- `fewa-v3-backend/app/api/v1/search.py` — LEZÁRVA 2026-07-28 (5.6.1 PASS)
- `fewa-v3-backend/tests/test_search_api.py` — LEZÁRVA 2026-07-28 (5.6.1 PASS)
- `fewa-v3-backend/app/services/rag_service.py` — LEZÁRVA 2026-07-28 (5.6.2 PASS)
- `fewa-v3-backend/app/api/v1/rag.py` — LEZÁRVA 2026-07-28 (5.6.2 PASS)
- `fewa-v3-backend/tests/test_rag_api.py` — LEZÁRVA 2026-07-28 (5.6.2 PASS)
- `fewa-v3-backend/app/services/oaipmh_service.py` — LEZÁRVA 2026-07-28 (5.6.3 PASS)
- `fewa-v3-backend/app/api/v1/oaipmh.py` — LEZÁRVA 2026-07-28 (5.6.3 PASS)
- `fewa-v3-backend/tests/test_oaipmh_api.py` — LEZÁRVA 2026-07-28 (5.6.3 PASS)
- `fewa-v3-backend/app/main.py` — LEZÁRVA 2026-07-28 (E2E 61/61 PASS)
- `fewa-v3-backend/tests/test_main.py` — LEZÁRVA 2026-07-28 (E2E 61/61 PASS)

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK) → elfogadva Phase 2-ben
- [0003] SimHash Hamming-küszöb default=3 → elfogadva Phase 2-ben
- [0004] Explicit Auth API végpontok (/api/auth/login, /refresh, /logout) → elfogadva Phase 3-ban
