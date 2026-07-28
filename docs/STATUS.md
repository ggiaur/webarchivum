# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 11:45

### AKTUÁLIS FÁZIS
Phase: 2 — Adatbázis séma (teljes DDL)
Step: 2.7 — Approval gate — felhasználói jóváhagyás várása
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
`spec/schema.sql` jóváhagyása után: Phase 3 indítása — `spec/openapi.yaml` API contract megírása.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] **APPROVAL GATE**: A DB séma (`spec/schema.sql`) felülvizsgálata és jóváhagyása szükséges a folytatáshoz
- [ ] Municipality értékkészlet: alkalmazás szintű enum vagy DB lookup tábla legyen? (jelenleg: VARCHAR + alkalmazás-szintű validáció)
- [ ] `simhash_threshold` (Hamming-küszöb) default értéke 3 — megfelelő-e a Fejér vm. webtartalmakra?

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1 — Session inicializálás, STATUS.md olvasva, nyitott kérdések azonosítva
- [x] 1.2 — Nyitott kérdések eldöntve (@architect): Municipality→Archive, AI→önálló context, Collections→Archive
- [x] 1.3 — `docs/DOMAIN_MODEL.md` létrehozva — 7 bounded context, eseményfolyam, Pydantic I/O sémák
- [x] 1.4 — `docs/adr/0001-domain-boundaries.md` megírva
- [x] 1.5 — .gitignore létrehozva, commit: 4e805d5
- [x] 1.6 — Phase 1 APPROVED (user jóváhagyta): Municipality→Archive (kontrollált lista), AI önálló context, Collections→Archive
- [x] 2.1 — `spec/` könyvtár létrehozva
- [x] 2.2 — `spec/schema.sql` megírva: 14 tábla, 3 trigger, 3 nézet, minden index és constraint

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
- `docs/DOMAIN_MODEL.md` — LEZÁRVA 2026-07-28 (Phase 1 APPROVED)
- `docs/adr/0001-domain-boundaries.md` — LEZÁRVA 2026-07-28

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md
