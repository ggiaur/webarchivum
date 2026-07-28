# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 12:37

### AKTUÁLIS FÁZIS
Phase: 5 — Implementáció
Step: 5.4 — AI Pipeline Services (Extraction, NER, Summary, Embedding, QC, Dedup)
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
Phase 5.4.1 indítása: `tasks/phase_tasks.md` Feladat 5.4.1 — Text Extraction Engine (WARC/WACZ → Raw Text, SHA-256, SimHash) → `fewa-v3-backend/app/pipeline/extraction.py` és `tests/test_pipeline_extraction.py`.

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
- [x] 5.3.1 — Municipalities API (`GET /api/municipalities`) → `app/api/v1/municipalities.py`, `tests/test_municipalities.py` (2/2 pytest PASS)
- [x] 5.3.2 — Sites CRUD Service & API (`/api/admin/sites`) → `app/crud/sites.py`, `app/api/v1/sites.py`, `tests/test_sites_api.py` (4/4 pytest PASS)
- [x] 5.3.3 — SKOS Tezaurusz API (`/api/thesaurus`) → `app/crud/thesaurus.py`, `app/api/v1/thesaurus.py`, `tests/test_thesaurus_api.py` (3/3 pytest PASS)

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

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK) → elfogadva Phase 2-ben
- [0003] SimHash Hamming-küszöb default=3 → elfogadva Phase 2-ben
- [0004] Explicit Auth API végpontok (/api/auth/login, /refresh, /logout) → elfogadva Phase 3-ban
