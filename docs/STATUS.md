# FEWA — Session Memória
> Ezt a fájlt az AI agent tartja karban. Ne szerkeszd kézzel.
> Minden session elején és végén frissítendő.

---

## STATUS — 2026-07-28 00:00

### AKTUÁLIS FÁZIS
Phase: 0 — Inicializálás
Step: 0.1 — Projekt induló állapot
Status: COMPLETED

### KÖVETKEZŐ BELÉPÉSI PONT
Futtasd a `/fewa-start` parancsot az agy-cli-ben a Domain Model fázis megkezdéséhez.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] A Municipality entity az Archive vagy a Search domain része?
- [ ] Az AI pipeline saját bounded context (AI) vagy az Archive aldomainje?
- [ ] A Collections feature Users-hez vagy Archive-hoz tartozik?

### LEZÁRT FELADATOK
- [x] 0.1 — Repository struktúra létrehozva → .agents/, docs/

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
(még nincs lezárt komponens)

### DÖNTÉSEK (ADR összefoglaló)
(még nincs)

---

## FÁZIS TÉRKÉP

| Fázis | Név | Státusz |
|---|---|---|
| 0 | Inicializálás | ✅ |
| 1 | Domain Model + Bounded Contexts | ⬜ |
| 2 | Adatbázis séma (teljes DDL) | ⬜ |
| 3 | OpenAPI YAML (API contract) | ⬜ |
| 4 | Pydantic sémák (pipeline I/O) | ⬜ |
| 5 | Atomikus feladatok + acceptance tesztek | ⬜ |
| 6 | Implementáció (backend) | ⬜ |
| 7 | Integráció + E2E tesztek | ⬜ |
| 8 | DevOps + CI/CD | ⬜ |

⬜ várakozik · 🔄 folyamatban · ✅ kész · 🔴 blokkolt
