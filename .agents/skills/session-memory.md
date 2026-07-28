# Skill: Session Memory (STATUS.md)

## Mikor használod
Minden session elején és végén. Ez az egyetlen módja annak,
hogy a következő session (Claude vagy Gemini) tudja, hol tartunk.

---

## Session ELEJÉN — kötelező lépések

1. Olvasd el a `docs/STATUS.md` fájlt
2. Azonosítsd: `### KÖVETKEZŐ BELÉPÉSI PONT` szekció
3. Ellenőrizd: `### NYITOTT KÉRDÉSEK` — van-e köztük blocker?
4. Ellenőrizd: `### TILTOTT` lista — ne nyúlj ezekhez a fájlokhoz
5. Ha STATUS.md nem létezik → azonnal hozd létre az alábbi sablonnal

```markdown
## STATUS — [DÁTUM IDŐBÉLYEG]

### AKTUÁLIS FÁZIS
Phase: 1 — Domain Model
Step: 1.1 — Inicializálás
Status: IN_PROGRESS

### KÖVETKEZŐ BELÉPÉSI PONT
docs/DOMAIN_MODEL.md létrehozása — Archive bounded context definíciójával kezd.

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] (üres)

### LEZÁRT FELADATOK
(még nincs)

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
(még nincs)

### DÖNTÉSEK (ADR összefoglaló)
(még nincs)
```

---

## Session VÉGÉN — kötelező lépések

Frissítsd a `docs/STATUS.md` fájlt PONTOSAN ebben a formátumban:

```markdown
## STATUS — [YYYY-MM-DD HH:MM]

### AKTUÁLIS FÁZIS
Phase: [szám] — [fázis neve]
Step: [szám.szám] — [lépés neve]
Status: IN_PROGRESS | BLOCKED | COMPLETED

### KÖVETKEZŐ BELÉPÉSI PONT
[Egyetlen konkrét mondat: melyik fájl, melyik szekció, mi a teendő]

### NYITOTT KÉRDÉSEK (döntést igényel)
- [ ] [kérdés — elegendő kontextussal hogy a következő session értse]

### LEZÁRT FELADATOK
- [x] [fázis.lépés] — [leírás] → [érintett fájlok vesszővel]

### TILTOTT (ne nyúlj hozzá — lezárt, tesztelt)
- [fájlnév] — LEZÁRVA [dátum]

### DÖNTÉSEK (ADR összefoglaló)
- [NNNN] [téma röviden] → docs/adr/NNNN-tema.md
```

---

## Szabályok

- A formátum **szó szerint** kötelező — Gemini és Claude egyaránt parseolja
- A `### KÖVETKEZŐ BELÉPÉSI PONT` mindig egyetlen, konkrét mondat
- Nyitott kérdést nem hagysz válasz nélkül — vagy döntesz, vagy blocker
- TILTOTT listából soha nem törölsz ki — csak hozzáadsz
