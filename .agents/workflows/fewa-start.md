---
description: FEWA projekt indítása — Domain Model fázis (zöldmezős)
---

Amikor a user beírja `/fewa-start`, végezd el az alábbiakat sorrendben.

## Végrehajtási sorrend

1. Olvasd el a `.agents/skills/session-memory.md` skillt
2. Hozd létre a `docs/STATUS.md` fájlt (ha nem létezik)
3. Olvasd el a `.agents/skills/domain-model.md` skillt
4. Cselekedj mint **@architect** és dolgozd ki a `docs/DOMAIN_MODEL.md` fájlt
5. Olvasd el a `.agents/skills/adr.md` skillt
6. Írd meg a `docs/adr/0001-domain-boundaries.md` ADR-t
7. Frissítsd a `docs/STATUS.md`-t session checkpoint formátumban

**Approval gate**: Megállsz és megkérdezed:
> "A domain modell elkészült. Kérlek ellenőrizd a `docs/DOMAIN_MODEL.md` fájlt —
> ha bármit módosítanál, írd bele kommentként és jelezd nekem.
> Ha rendben van, írd: 'Approved' — és folytatom a DB séma tervezésével."

Csak "Approved" után lépsz tovább.
