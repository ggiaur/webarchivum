# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 12:53

### AKTUÁLIS FÁZIS
Phase: 6 — COMPLETED (Teljes rendszer-architektúra, backend, frontend, docker-compose & E2E integrációs tesztek)
Status: READY_FOR_DEPLOYMENT

### KÖVETKEZŐ BELÉPÉSI PONT
A projekt 100%-ban felpusholva a Git repóba (`master` ág). Bármely másik gépen klónozható (`git clone https://github.com/ggiaur/webarchivum.git`) és elindítható (`docker-compose up --build`).

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
- [x] 5.6.1–5.6.3 — Phase 5.6 COMPLETED: Hybrid Search, RAG Engine & Guardrails, OAI-PMH 2.0 (11/11 pytest PASS)
- [x] 5.7 — Phase 5.7 COMPLETED: Next.js 15 SSR Publikus Kereső & Replay UI + React Admin SPA (Route groups: `(public)` & `(admin)`)
- [x] 6.1–6.2 — Phase 6 COMPLETED: Docker Compose infra (`docker-compose.yml`, `docker-compose.test.yml`), Backend Dockerfile, Frontend Dockerfile, E2E Integration test (`62/62 pytest PASS`)

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
- `fewa-v3-backend/app/main.py` — LEZÁRVA 2026-07-28 (E2E 62/62 PASS)
- `fewa-v3-backend/tests/test_main.py` — LEZÁRVA 2026-07-28 (E2E 62/62 PASS)
- `fewa-v3-frontend/package.json` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/globals.css` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/layout.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(public)/layout.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(public)/page.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(public)/documents/[id]/page.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(public)/collections/page.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(admin)/admin/login/page.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `fewa-v3-frontend/app/(admin)/admin/dashboard/page.tsx` — LEZÁRVA 2026-07-28 (Phase 5.7 COMPLETED)
- `docker-compose.yml` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `docker-compose.test.yml` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `fewa-v3-backend/Dockerfile` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `fewa-v3-backend/.dockerignore` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `fewa-v3-frontend/Dockerfile` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `fewa-v3-frontend/ .dockerignore` — LEZÁRVA 2026-07-28 (Phase 6 COMPLETED)
- `fewa-v3-backend/tests/test_e2e_pipeline.py` — LEZÁRVA 2026-07-28 (E2E 62/62 PASS)

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK) → elfogadva Phase 2-ben
- [0003] SimHash Hamming-küszöb default=3 → elfogadva Phase 2-ben
- [0004] Explicit Auth API végpontok (/api/auth/login, /refresh, /logout) → elfogadva Phase 3-ban
- [0005] Egyetlen Next.js 15 projekt App Router route groupokkal (`(public)` SSR + `(admin)` SPA) → elfogadva Phase 5.7-ben

### ARCH-01 — AUDITÁLT ÚJRANYITÁSI ENGEDÉLY (2026-08-13)

Ez a bejegyzés nem módosítja a fenti, történeti lezárásokat.  Az ARCH-01-ben
csak a célzott Sonnet re-review `ELFOGADVA` verdictje után, az alábbi
fájltulajdonnal és sorrendben szabad új munkát kezdeni.

- **S1, kizárólagos owner:** `docs/adr/0002-arch-01-release-state-machine.md`
  (új), `spec/migrations/005_arch_01_pipeline.sql` (új),
  `spec/pipeline_schemas.py`, `spec/openapi.yaml`,
  `fewa-v3-backend/tests/test_arch01_migration.py` (új),
  `fewa-v3-backend/tests/test_arch01_contract.py` (új). A lezárt
  `spec/schema.sql` nem nyitható újra: a változás csak verziózott migration.
- **S2, kizárólag új fájlok:** `fewa-automation/url_security.py`,
  `search_provider.py`, `discovery_llm.py`, `discovery_worker.py`,
  `crawl_manifest.py`, `wacz_integrity.py`, `qa_gate.py`, `executor.py`,
  `Dockerfile.executor`, valamint az azonos nevű új célzott tesztek. S2 csak
  S1 elfogadott séma- és szerződéskimenetére épülhet.
- **S3, FELTÉTELES ÚJRANYITÁS:** `fewa-automation/crawler.py`,
  `fewa-automation/tests/test_crawler.py`,
  `fewa-v3-backend/app/api/v1/jobs.py`, `app/core/config.py`,
  `app/core/minio_client.py`, `app/crud/archive.py`, `app/workers/arq_worker.py`,
  `tests/test_archive_crud.py`, `tests/test_arq_worker.py`,
  `tests/test_jobs_api.py`, `fewa-v3-backend/Dockerfile`,
  `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, és az új
  `infra/egress/egress-policy.yaml`, `tests/fixtures/arch01_site/app.py`,
  `tests/test_arch01_compose_e2e.py`, `tests/test_nginx_contract.py`.
  Ezek csak S1+S2 elfogadása **és** az aktuális diff tulajdonosának írásos
  checkpoint/handoffja után nyithatók újra.

**In-flight tilalom:** a jelenleg módosított `crawler.py`,
`test_crawler.py`, `jobs.py`, `minio_client.py`, `archive.py`, `arq_worker.py`,
`test_archive_crud.py`, `test_arq_worker.py` és `test_jobs_api.py` más builder
számára addig TILTOTT. Nem felülírhatók, nem részlegesen merge-elhetők és nem
vehetők át hallgatólagosan; a handoffnak a base commitot, diff hash-t, futtatott
tesztet, ismert hibákat és az átvevő nevét kell rögzítenie a
`COLLAB_GEMINI.md`-ben. A fenti engedély nem ad deploy-, Nginx- vagy
titokmódosítási jogosultságot.
