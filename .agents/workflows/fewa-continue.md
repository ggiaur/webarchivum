---
description: FEWA projekt folytatása — új session indítása STATUS.md alapján
---

Amikor a user beírja `/fewa-continue`, végezd el az alábbiakat.

## Végrehajtási sorrend

1. Olvasd el a `.agents/skills/session-memory.md` skillt
2. Olvasd el a `docs/STATUS.md` fájlt
3. Azonosítsd a `### KÖVETKEZŐ BELÉPÉSI PONT` szekciót
4. Ellenőrizd a `### NYITOTT KÉRDÉSEK` listát:
   - Ha van BLOCKER → listázd ki és várj döntésre, ne folytasd
   - Ha nincs BLOCKER → folytasd a következő feladattal
5. Ellenőrizd a `### TILTOTT` listát — ezekhez NEM nyúlsz
6. Folytasd a munkát a megfelelő skill fájl alapján

## Mikor melyik skill-t olvasod

| Aktuális fázis | Skill fájl |
|---|---|
| Phase 1 — Domain Model | `.agents/skills/domain-model.md` |
| Phase 2 — DB séma | `.agents/skills/spec-first.md` |
| Phase 3 — OpenAPI | `.agents/skills/spec-first.md` |
| Phase 4 — Pydantic sémák | `.agents/skills/spec-first.md` |
| Phase 5+ — Implementáció | `.agents/skills/acceptance-testing.md` |
| Bármikor — döntés | `.agents/skills/adr.md` |

## Session végén mindig

Frissítsd a `docs/STATUS.md`-t a session-memory.md skillben leírt formátumban.
Soha ne fejezd be a sessiont STATUS.md frissítés nélkül.
