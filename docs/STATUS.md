# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 11:52

### AKTUÁLIS FÁZIS
Phase: 3 — OpenAPI YAML contract
Step: 3.3 — Approval gate — felhasználói jóváhagyás várása
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
`spec/openapi.yaml` jóváhagyása után: Phase 4 — `spec/pipeline_schemas.py` Pydantic I/O sémák minden AI pipeline lépésre.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] **APPROVAL GATE**: Az OpenAPI contract (`spec/openapi.yaml`) felülvizsgálata szükséges
- [ ] Auth végpont: szükséges-e `/api/auth/login` és `/api/auth/refresh` endpoint a spec-ben? (jelenleg nincs, JWT generálást a FastAPI security modul kezeli)

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1–1.5 — Domain Model fázis minden lépése
- [x] 1.6 — Phase 1 APPROVED: Municipality→Archive, AI önálló context, Collections→Archive
- [x] 2.1 — `spec/` könyvtár létrehozva
- [x] 2.2 — `spec/schema.sql` megírva: 15 tábla (+ municipalities), 3 trigger, 3 nézet
- [x] 2.3 — Phase 2 APPROVED: municipalities lookup tábla + FK, simhash_threshold=3 default
- [x] 2.4 — `spec/schema.sql` frissítve: municipality VARCHAR → municipality_id UUID FK
- [x] 3.1 — `spec/openapi.yaml` megírva: OpenAPI 3.1.0, 22 endpoint, teljes schema-könyvtár

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
- `docs/DOMAIN_MODEL.md` — LEZÁRVA 2026-07-28 (Phase 1 APPROVED)
- `docs/adr/0001-domain-boundaries.md` — LEZÁRVA 2026-07-28

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
- [0002] Municipality lookup tábla (DB szintű FK, nem VARCHAR) → elfogadva Phase 2 APPROVED-ban
- [0003] SimHash Hamming-küszöb default=3, éles adatokon hangolható → elfogadva Phase 2 APPROVED-ban
