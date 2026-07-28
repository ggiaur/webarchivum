# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 12:35

### AKTUÁLIS FÁZIS
Phase: 5 — Implementáció
Step: 5.2 — Authentication & RBAC (JWT RS256, Security Middleware, Auth endpoints)
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
Phase 5.2.1 indítása: `tasks/phase_tasks.md` Feladat 5.2.1 — JWT RS256 kulcspár & Security szolgáltatás (`fewa-v3-backend/app/core/security.py` és `tests/test_security.py`).

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] Nincs nyitott blocker.

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1–1.6 — Phase 1 APPROVED: Domain Model (7 bounded context, eseményfolyam, ADR-0001)
- [x] 2.1–2.4 — Phase 2 APPROVED: PostgreSQL DDL schema (15 tábla, 3 trigger, 3 nézet, municipalities FK)
- [x] 3.1–3.3 — Phase 3 APPROVED: OpenAPI 3.1.0 contract (25 endpoint, /api/auth/login, /refresh, /logout)
- [x] 4.1 — `spec/pipeline_schemas.py` megírva: AI pipeline sémák (Extraction, NER, Summary, Embedding, QC, Dedup, Jobs)
- [x] 4.2 — `tasks/phase_tasks.md` megírva: atomikus feladatok gépileg futtatható pytest acceptance tesztekkel
- [x] 5.1.1 — Environment Config & Pydantic Settings → `app/core/config.py`, `tests/test_config.py` (4/4 pytest PASS)
- [x] 5.1.2 — PostgreSQL asyncpg pool & healthcheck → `app/core/db.py`, `tests/test_db.py` (2/2 pytest PASS)
- [x] 5.1.3 — Redis szétválasztás (db=0 queue, db=1 cache) → `app/core/redis.py`, `tests/test_redis.py` (2/2 pytest PASS)
- [x] 5.1.4 — MinIO S3 client & WACZ stream SHA-256 → `app/core/minio_client.py`, `tests/test_minio.py` (3/3 pytest PASS)

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

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK) → elfogadva Phase 2-ben
- [0003] SimHash Hamming-küszöb default=3 → elfogadva Phase 2-ben
- [0004] Explicit Auth API végpontok (/api/auth/login, /refresh, /logout) → elfogadva Phase 3-ban
