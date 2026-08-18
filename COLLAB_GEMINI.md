# Webarchivum — Élő fejlesztési kollaboráció

**Előzmények (lezárt, teljes archívum, NE itt keress aktuális feladatot):**
- [`COLLAB_GEMINI.old.md`](COLLAB_GEMINI.old.md) — ARCH-01 audit- és handoff-napló (2026-08-13 előtt)
- [`COLLAB_GEMINI.archive-2026-08-17.md`](COLLAB_GEMINI.archive-2026-08-17.md) — a teljes W-sprint, a login-incidens, a docker-guard smuggling-javítás, és minden 2026-08-17-i review/incidens, szó szerint

**Ez a fájl mostantól KIZÁRÓLAG az aktuálisan nyitott feladatokat
tartalmazza.** Ha egy feladat lezárul (BEÉPÍTVE vagy elutasítva), a
bejegyzés ide kerül át az archívumba, nem marad itt. Cél: bárki (ember
vagy AI) egy pillantással lássa, mi van hátra — ne kelljen 5000 sort
végigolvasnia.

## Működési szerepek

- **Sonnet 5** — biztonsági/integritási kapu, minden végleges elfogadás
  rajta megy keresztül, saját, független reprodukcióval.
- **Gemini** — Builder, jelenleg a backend/crawl-pipeline munkán.
- **gpt-5.6-terra** — Builder, jelenleg a frontend/dashboard reviewon.
  **Fontos:** nem pollozza automatikusan ezt a fájlt — csak akkor lát
  bármit, ha valaki (BJ) explicit elindítja.
- **gpt-5.6-sol** — Független QA, adverzális reprodukció külön
  környezetben. Szintén nem pollozik automatikusan.
- **Architect/DevOps** — csak normatív döntés, topológia, rollout.

## Labda-szabály

A blokk **Státusza** mondja meg, kinél van a labda. Csak az a fél
nyúljon hozzá, akié. Ha felveszel egy feladatot: írd át
`FELDOLGOZÁS ALATT — <szereped>`-re. Ha végeztél: `KÉSZ — SONNET
REVIEW-RA VÁR`. Sonnet review után: `BEÉPÍTVE` (→ archívumba kerül) vagy
`JAVÍTÁS KÉRVE` (marad itt, a hiány leírásával).

**Kötelező minden bejegyzésnél:** `MODEL=...` a tetején, és **valós,
futtatott bizonyíték** az állítás mellett (parancs + kimenet), nem csak
"kész" szöveg — ez a fájl egész eddigi működésének alapelve, ez nem
változik.

---

# AKTÍV FELADATOK (2026-08-18 állapot szerint)

## 1. Crawl-progress (`pages_crawled`/`current_depth`) élesben lefagy

Státusz: **RÁD VÁR (Builder)**

A JSON-mezőnevek javítva vannak (`fewa-automation/crawler.py`,
`rec["details"]["crawled"]` + `pendingPages`-ből mélység — ellenőrizve
valós Browsertrix-kimenettel). **De egy valós, éles crawl job 7+ percig
lefagyva állt, sosem adott vissza semmit**, miközben ugyanaz a docker
parancs kézzel futtatva azonnal működött. Gyanú: Node.js teljes
kimenet-pufferelése pipe esetén, ami blokkolja a Python
`Popen.readline()`-t.

Két javítási irány (részletesen: `COLLAB_GEMINI.archive-2026-08-17.md`,
a legutolsó Sonnet-bejegyzések):
1. `stdbuf -oL` a `docker run` elé, VAGY
2. Ne stdout-ot parse-olj — olvasd periodikusan a Browsertrix saját,
   lemezre írt crawl-állapot fájlját.

**Elfogadási kritérium:** egy valós aratás **végig fut**, és
`pages_crawled`/`current_depth` ténylegesen növekszik közben (nem csak
a végén ugrik egyre) — mutasd meg a köztes állapotokat is, nem csak a
végeredményt.

---

## 2. Dashboard admin frontend review (`(admin)/admin/dashboard/page.tsx`, 708 sor)

Státusz: **RÁD VÁR (gpt-5.6-terra vagy Sonnet)**

Gemini commitolta (`49f8e1d`), állítása szerint tartalmazza: URL-hez
kötött fülnavigáció (`?tab=...`), Felhasználók fül + modal, webhely
jogtulajdonos-mezők inline szerkesztése, minőségi felülvizsgálat
oldalankénti bontással. **Sonnet ezt még nem nézte át** (a
progress-hibára koncentrált). Kell egy független review:
- Tényleg működik-e böngészőben (screenshot vagy valós DOM-teszt)?
- A URL-routing tényleg javítja-e a Vissza gomb problémát (élőben
  tesztelve, nem csak kódolvasással)?
- A users/rights-holder UI ténylegesen hívja-e a helyes API
  végpontokat?

---

## 3. Refine-migráció — még el sem kezdődött

Státusz: **RÁD VÁR (gpt-5.6-terra)**, a fenti (2) review lezárása után

Architektúra döntés megvan (`COLLAB_GEMINI.archive-2026-08-17.md`): a
jövőbeli admin-képernyők Refine-nal épüljenek, a meglévő FastAPI API-ra
kötve, nem a DB-re közvetlenül. Ne kezdd el, amíg a (2) review nem zárt le
— ne építs a még nem ellenőrzött kódra.

---

## 4. Automatikus javító-újrapróbálkozás alacsony QC-pontszámú oldalra

Státusz: **RÁD VÁR (Gemini vagy gpt-5.6-terra)** — nincs jele, hogy ez
elkészült volna (Gemini Task 7/8 jelentése csak a kemény alsó küszöböt
említi, az automatikus retry-t nem)

Ha egy oldal screenshot/text match a küszöb alatt van, a rendszer
próbálja újra azt a konkrét oldalt (hosszabb JS-render várakozással),
és ha a második próbálkozás jobb, azt használja. Részletek:
`COLLAB_GEMINI.archive-2026-08-17.md`, "hiányzó automatikus
javító-újrapróbálkozás" bejegyzés.

---

## 5. Sonnet független ellenőrzésre vár (kódban megvan, élőben nincs próbálva)

Státusz: **Sonnet review-ra vár, alacsony prioritás** — ezek valószínűleg
rendben vannak kódból nézve, csak élő reprodukció hiányzik:
- `withdraw_published_snapshot` — publikált snapshot → withdraw hívás →
  publikus keresésben eltűnik, élőben.
- Users API önvédelem (saját admin ne fokozza le magát) — élőben, valós
  admin-jelszóval (ma nem volt dokumentált admin jelszó sehol, ezt is
  pótolni kell egy teszthez).
- Proxy-lefedettség audit (Task 1, Gemini állítása szerint kész,
  `scripts/test_frontend_proxy_audit.js` PASSED) — Sonnet nem futtatta
  újra saját maga.

---

**Aktuális infrastruktúra-állapot:** a fejlesztői stack fut (backend,
frontend, worker, docker-guard, postgres, redis, minio), helyi portokon
(8001/3001), lásd `.env`. Login működik (`curator@vmk.hu` /
`SecretPassword123!`). Production deploy továbbra sincs autorizálva.
