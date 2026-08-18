# Webarchivum — Élő fejlesztési kollaboráció

**Előzmények (lezárt, teljes archívum, NE itt keress aktuális feladatot):**
- [`COLLAB_GEMINI.old.md`](COLLAB_GEMINI.old.md) — ARCH-01 audit- és handoff-napló (2026-08-13 előtt)
- [`COLLAB_GEMINI.archive-2026-08-17.md`](COLLAB_GEMINI.archive-2026-08-17.md) — a teljes W-sprint, a login-incidens, a docker-guard smuggling-javítás, és minden 2026-08-17-i review/incidens, szó szerint

**Ez a fájl mostantól KIZÁRÓLAG az aktuálisan nyitott feladatokat
tartalmazza.** Ha egy feladat lezárul (BEÉPÍTVE vagy elutasítva), a
bejegyzés ide kerül át az archívumba, nem marad itt. Cél: bárki (ember
vagy AI) egy pillantással lássa, mi van hátra — ne kelljen 5000 sort
végigolvasnia.

**Beszúráskor: mindig a fájl VÉGÉRE fűzz hozzá, vagy egy adott feladat
teljes szakaszát cseréld le egyben — soha ne szúrj be egy másik pont
listaeleme KÖZEPÉBE.** Ez ma már kétszer eltörte a fájl szerkezetét.

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

## 1. Crawl-progress — TTY-javítás ELFOGADVA (Sonnet, teljes API-n át igazolva); ÚJ HIBA menet közben: depth/max_pages elveszik jóváhagyáskor

Státusz: **BEÉPÍTHETŐ, ha a `-t` diff commitolva lesz** — a progress
rész működik, de egy MÁSIK, súlyos hiba is előkerült, l. lent.

**TTY-javítás elfogadva.** Gemini javítása (`docker run -t --rm ...`)
helyes. Sonnet saját, teljes `POST /api/admin/ingest` →
`POST /api/admin/candidates/{id}/approve` → valódi arq job → valódi
Browsertrix-konténer útvonalon tesztelte (nem csak egy közvetlen
függvényhívással, mint Gemini): `debian.org`, `snapshot_id=
1735115d-3e77-46b6-b069-7acd96bfc15f`. Élő eredmény, sokszor
megfigyelve, folyamatosan növekedve: `crawling|1|1` →
`crawling|4|1` → `crawling|11|1` → `crawling|13|1` (még fut). **Ez
bizonyítottan valódi, élő progress-frissítés a teljes appon keresztül.**

### ÚJ, VALÓDI HIBA a fenti teszt közben derült ki: a kért `depth`/`max_pages` elvész jóváhagyáskor

`POST /api/admin/ingest`-nél `depth:1, max_pages:4`-et kértem — a
ténylegesen elindult Browsertrix-konténer parancsa
(`docker inspect <id> --format '{{.Config.Cmd}}'`) viszont
`--depth 2 --pageLimit 20`-at futtatott. Megnéztem a kódot
(`app/api/v1/jobs.py`): a kötelező-jóváhagyás policy-átalakítás óta
`trigger_ingest` csak candidate-et hoz létre, a tényleges job-indítás
**külön, az `approve_candidate_endpoint`-ban történik — ami
`"depth": 2, "max_pages": 20`-at hardcode-ol** (109-120. sor), sosem
olvassa vissza, mit kért eredetileg a kurátor ingestkor. **A kurátor
által megadott mélység/oldalszám érvénytelen, mindig figyelmen kívül
marad.**

**Kért javítás:** `depth`/`max_pages` mentése a candidate/snapshot
rekordra `create_candidate_snapshot`-nál, és `approve_candidate_endpoint`-
ban ebből olvasva, ne hardcode-olt `2`/`20`-szal.

Státusz: **RÁD VÁR (Builder)** — ezt még senki nem javította.

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

## 5. Sonnet független ellenőrzésre vár (kódban/teszttel megvan, élő API-n át nincs próbálva)

Státusz: **Sonnet review-ra vár, alacsony prioritás** — Gemini szerint
2026-08-18 05:33-kor lefutott a teljes `test_jobs_api.py` +
`test_users_api.py` + `test_sites_api.py` (18/18 PASSED), köztük
`test_approved_by_records_user_id`, `test_withdraw_published_snapshot_endpoint`,
`test_rights_holder_fields_create_and_update`,
`test_create_and_update_user_flow` (self-demotion védelem). Ez jó jel,
de a pytest-fixture-ös teszt nem ugyanaz, mint egy élő, böngészőből/API-n
át indított próba — Sonnet ezt még nem futtatta újra saját maga:
- `withdraw_published_snapshot` — publikált snapshot → withdraw hívás →
  publikus keresésben eltűnik, élőben.
- Users API önvédelem — élőben, valós admin-jelszóval (ma nem volt
  dokumentált admin jelszó sehol, ezt is pótolni kell egy teszthez).
- Proxy-lefedettség audit (Task 1) — Gemini szerint kész
  (`scripts/test_frontend_proxy_audit.js`, `test_frontend_e2e.js` 14/14,
  `test_frontend_functional_dom.js` 9/9, mind PASSED, `npm run build`
  8/8 route) — Sonnet nem futtatta újra saját maga.

---

**Aktuális infrastruktúra-állapot:** a fejlesztői stack fut (backend,
frontend, worker, docker-guard, postgres, redis, minio), helyi portokon
(8001/3001), lásd `.env`. Login működik (`curator@vmk.hu` /
`SecretPassword123!`). Production deploy továbbra sincs autorizálva.
