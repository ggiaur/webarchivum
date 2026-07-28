# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 12:04

### AKTUÁLIS FÁZIS
Phase: 4 — Pydantic sémák & Atomikus feladatlista
Step: 4.2 — Spec-first fázis lezárva, implementációra kész
Status: COMPLETED

### KÖVETKEZŐ BELÉPÉSI PONT
Phase 5.1 indítása: `tasks/phase_tasks.md` Feladat 5.1.1 — `fewa-v3-backend/app/core/config.py` és `.env.example` létrehozása.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] Nincs nyitott blocker. A specifikáció (Domain Model, DDL schema, OpenAPI YAML, Pydantic sémák, feladatlista) hiánytalan és jóváhagyott.

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1–1.6 — Phase 1 APPROVED: Domain Model (7 bounded context, eseményfolyam, ADR-0001)
- [x] 2.1–2.4 — Phase 2 APPROVED: PostgreSQL DDL schema (15 tábla, 3 trigger, 3 nézet, municipalities FK)
- [x] 3.1–3.3 — Phase 3 APPROVED: OpenAPI 3.1.0 contract (25 endpoint, /api/auth/login, /refresh, /logout)
- [x] 4.1 — `spec/pipeline_schemas.py` megírva: AI pipeline sémák (Extraction, NER, Summary, Embedding, QC, Dedup, Jobs)
- [x] 4.2 — `tasks/phase_tasks.md` megírva: atomikus feladatok gépileg futtatható pytest acceptance tesztekkel

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
- `docs/DOMAIN_MODEL.md` — LEZÁRVA 2026-07-28 (Phase 1 APPROVED)
- `docs/adr/0001-domain-boundaries.md` — LEZÁRVA 2026-07-28
- `spec/schema.sql` — LEZÁRVA 2026-07-28 (Phase 2 APPROVED)
- `spec/openapi.yaml` — LEZÁRVA 2026-07-28 (Phase 3 APPROVED)
- `spec/pipeline_schemas.py` — LEZÁRVA 2026-07-28 (Phase 4 COMPLETED)
- `tasks/phase_tasks.md` — LEZÁRVA 2026-07-28 (Phase 4 COMPLETED)

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK) → elfogadva Phase 2-ben
- [0003] SimHash Hamming-küszöb default=3 → elfogadva Phase 2-ben
- [0004] Explicit Auth API végpontok (/api/auth/login, /refresh, /logout) → elfogadva Phase 3-ban
