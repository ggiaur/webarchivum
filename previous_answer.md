# Javítva — az én hibám volt, most már működik mindkét oldal

A hiba valódi volt, és az én hibám okozta: többször futtattam éles build-et (`npm run build`) úgy, hogy közben a fejlesztői szerver (`npm run dev`) is futott ugyanarra a `.next` mappára — ez összekeverte a build gyorsítótárat, ezért hiányzott egy belső modul (`403.js`).

## A javítás

1. Leállítottam az összes elakadt frontend-folyamatot.
2. Töröltem a sérült `.next` gyorsítótár mappát.
3. Tisztán újraindítottam a fejlesztői szervert.
4. Böngészőben ténylegesen leellenőriztem mindkét oldalt (főoldal + admin bejelentkezés+dashboard) — nincs hiba, a 42 jelölt továbbra is ott van, minden működik.

## Ami most látszik a főoldalon

"0 megőrzött archív dokumentum" — ez helyes és őszinte állapot: a 44 jelöltből eddig csak 1-et hagytam jóvá (tesztelés közben), de az sem lett még ténylegesen archiválva (nem futott le rá a Browsertrix crawl), így a nyilvános keresésben egyik sem jelenik meg még. Ha szeretnéd, hogy egy jelöltet végig is vigyek a teljes folyamaton (jóváhagyás → archiválás → publikálás), hogy lásd az egészet működés közben, szólj.

Mostantól óvatosabb leszek a build és dev szerver egyidejű futtatásával, hogy ez ne forduljon elő újra.

---
_Generálva: 2026-07-31 17:38:40 +0200_
