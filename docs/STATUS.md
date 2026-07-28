# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 11:36

### AKTUÁLIS FÁZIS
Phase: 1 — Domain Model + Bounded Contexts
Step: 1.6 — Approval gate — felhasználói jóváhagyás várása
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
A `docs/DOMAIN_MODEL.md` jóváhagyása után: `docs/adr/0002-fastapi-vs-alternatives.md` megírása, majd DB séma fázis (Phase 2) indítása.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] **APPROVAL GATE**: A domain modell (`docs/DOMAIN_MODEL.md`) felülvizsgálata és jóváhagyása szükséges a folytatáshoz
- [ ] Municipality kontrollált lista: melyek a konkrét értékek? (Fejér vm. összes önkormányzata? Vagy csak az archiválandó?) — ADR előtt kell dönteni

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/
- [x] 1.1 — Session inicializálás, STATUS.md olvasva, nyitott kérdések azonosítva
- [x] 1.2 — Nyitott kérdések eldöntve (@architect): Municipality→Archive, AI→önálló context, Collections→Archive
- [x] 1.3 — `docs/DOMAIN_MODEL.md` létrehozva — 7 bounded context, eseményfolyam, Pydantic I/O sémák
- [x] 1.4 — `docs/adr/0001-domain-boundaries.md` megírva
- [x] 1.5 — .gitignore létrehozva, összes fájl commitolva és pushba küldve (commit: 4e805d5)

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
(még nincs lezárt komponens — Phase 1 approval gate folyamatban)

### DÖNTÉSEK (ADR összefoglaló)
- [0001] Domain határok és bounded contextek → docs/adr/0001-domain-boundaries.md

---

## FÁZIS TÉRKÉP

| Fázis | Név | Státusz |
|---|---|---|
| 0 | Inicializálás | ✅ |
| 1 | Domain Model + Bounded Contexts | 🔄 (approval gate) |
| 2 | Adatbázis séma (teljes DDL) | ⬜ |
| 3 | OpenAPI YAML (API contract) | ⬜ |
| 4 | Pydantic sémák (pipeline I/O) | ⬜ |
| 5 | Atomikus feladatok + acceptance tesztek | ⬜ |
| 6 | Implementáció (backend) | ⬜ |
| 7 | Integráció + E2E tesztek | ⬜ |
| 8 | DevOps + CI/CD | ⬜ |

⬜ várakozik · 🔄 folyamatban · ✅ kész · 🔴 blokkolt
