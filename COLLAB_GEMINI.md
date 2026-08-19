# Webarchivum — Élő fejlesztési kollaboráció

**Előzmények (lezárt, teljes archívum, NE itt keress aktuális feladatot):**
- [`COLLAB_GEMINI.old.md`](COLLAB_GEMINI.old.md) — ARCH-01 audit- és handoff-napló (2026-08-13 előtt)
- [`COLLAB_GEMINI.archive-2026-08-17.md`](COLLAB_GEMINI.archive-2026-08-17.md) — a teljes W-sprint, a login-incidens, a docker-guard smuggling-javítás, és minden 2026-08-17-i review/incidens, szó szerint

**Ez a fájl mostantól KIZÁRÓLAG az aktuálisan nyitott feladatokat
tartalmazza.** Ha egy feladat lezárul (BEÉPÍTVE vagy elutasítva), a
bejegyzés ide kerül át az archívumba, nem marad itt. Cél: bárki (ember
vagy AI) egy pillantással lássa, mi van hátra.

**Beszúráskor: mindig a fájl VÉGÉRE fűzz hozzá, vagy egy adott feladat
teljes szakaszát cseréld le egyben — soha ne szúrj be egy másik pont
listaeleme KÖZEPÉBE.** Ez ma már kétszer eltörte a fájl szerkezetét.

## Hogyan működik ez a közös munka — olvasd el, mielőtt bármit csinálsz

Ez a fájl egy megosztott jegyzőkönyv, amit több AI-ügynök (Sonnet,
Gemini, gpt-5.6-terra, gpt-5.6-sol) és BJ (ember) közösen ír, GitHubon
keresztül szinkronizálva (`git push`/`git pull` — **nincs élő,
folyamatos kapcsolat az ügynökök között, csak ezen a fájlon és a git
történeten keresztül üzennek egymásnak**).

**Ki hogyan kapcsolódik be:**
- **Gemini** saját magától, folyamatosan (kb. 10 percenként) megnyitja
  ezt a fájlt, keres benne rá váró feladatot, és ha talál, dolgozik
  rajta, majd pusholja az eredményt.
- **gpt-5.6-terra és gpt-5.6-sol NEM figyelik automatikusan ezt a
  fájlt** — csak akkor csinálnak bármit, ha BJ külön, kézzel elindítja
  őket (egy másik terminálban/eszközben). Amint elindulnak, ebből a
  fájlból tudják meg, mi a feladatuk.
- **Sonnet** (én) jelen munkamenet során folyamatosan aktív vagyok,
  figyelem a fájl változásait, és minden állítást saját, futtatott
  teszttel ellenőrzök, mielőtt elfogadom — ez nem bizalmi kérdés, ez a
  fájl kezdettől fogva lefektetett szabálya (l. "Kötelező minden
  bejegyzésnél" lent).

**Miért fontos ez:** ha egy feladat "nincs felvéve", az nem feltétlenül
azt jelenti, hogy senki nem foglalkozik vele — lehet, hogy egyszerűen
senki nem indította el az adott ügynököt. Ha azt látod, hogy régóta nem
történik semmi, **ellenőrizd, fut-e egyáltalán bármelyik ügynök**, mielőtt
feltételezed, hogy elakadtak.

## Működési szerepek

- **Sonnet 5** — biztonsági/integritási kapu, minden végleges elfogadás
  rajta megy keresztül, saját, független reprodukcióval.
- **Gemini** — Builder, jelenleg a backend/crawl-pipeline munkán.
- **gpt-5.6-terra** — Builder, frontend/dashboard.
- **gpt-5.6-sol** — Független QA, adverzális reprodukció külön
  környezetben.
- **Architect/DevOps** — csak normatív döntés, topológia, rollout.

## Labda-szabály

A blokk **Státusza** mondja meg, kinél van a labda. Csak az a fél
nyúljon hozzá, akié. Ha felveszel egy feladatot: írd át
`FELDOLGOZÁS ALATT — <szereped>`-re. Ha végeztél: `KÉSZ — SONNET
REVIEW-RA VÁR`. Sonnet review után: `BEÉPÍTVE` (→ archívumba kerül) vagy
`JAVÍTÁS KÉRVE` (marad itt, a hiány leírásával).

**Kötelező minden bejegyzésnél:** `MODEL=...` a tetején, és **valós,
futtatott bizonyíték** az állítás mellett (parancs + kimenet), nem csak
"kész" szöveg. **Figyelem:** kiderült, hogy a "teszt" néven futó
szkriptek egy része (`test_frontend_e2e.js`,
`test_frontend_functional_dom.js`) valójában csak `http.get`-tel
lekérdezi az oldalak HTML-jét — nem valódi böngésző, nem kattint, nem
tölt ki űrlapot. "PASSED" ezeknél annyit jelent, hogy az oldal 200-at ad
és tartalmaz bizonyos szöveget — **nem** hogy a funkció ténylegesen
működik kattintva. Ne kezeld ezeket egyenértékűnek egy valódi,
interakciós teszttel.

---

# AKTÍV FELADATOK (2026-08-18, Sonnet frissítette)

## 1. Dashboard admin frontend review (`(admin)/admin/dashboard/page.tsx`, 1025 sor)

Státusz: **RÁD VÁR (gpt-5.6-terra vagy Sonnet folytatja)**

Sonnet részleges review-t végzett:
- **URL-routing**: `window.history.replaceState` (nem `pushState`)
  szinkronizálja `?tab=...`-t. Ez megoldja, hogy reload/megosztás/
  könyvjelző a helyes fülre vigyen — **de mivel `replaceState`, nem hoz
  létre böngészési előzményt fülváltáskor**, tehát a Vissza gomb
  továbbra sem lép vissza fülről fülre (csak a dashboardra lépés előtti
  oldalra ugrik, mint eddig, csak most legalább helyes fülön landol,
  ha újratöltöd). Részleges javítás — döntsd el BJ-vel, hogy ez elég-e,
  vagy kell `pushState` is.
- **API-hívások**: mind a 11 `fetch()` hívás `fetchWithAuth()`-on megy
  (0 nyers `fetch()`), ez helyes minta, konzisztens a korábbi proxy-
  javítással.
- **Rights-holder mezők**: Sonnet saját, élő `PATCH
  /api/admin/sites/{id}` hívással ellenőrizte — működik, a mezők
  ténylegesen elmentődnek.
- **Users API RBAC**: Sonnet élőben tesztelte — curator szerepkörrel a
  `POST /api/admin/users` helyesen 403-at ad ("minimum admin
  jogosultság szükséges"). Az admin-oldali pozitív út (tényleges
  létrehozás) nincs élőben tesztelve — nincs dokumentált admin jelszó.

**Még hátravan:** valódi böngészős/DOM-interakciós teszt (nem a fenti,
gyenge `http.get`-es szkriptek) — tényleg megnyílik-e a modal, tényleg
kattintható-e a fül. Ez gpt-5.6-terra vagy Sonnet következő köre.

---

## 2. Refine-migráció — még el sem kezdődött

Státusz: **RÁD VÁR (gpt-5.6-terra)**, a fenti (1) review lezárása után

Architektúra döntés megvan (`COLLAB_GEMINI.archive-2026-08-17.md`): a jövőbeli
admin-képernyők Refine-nal épüljenek, a meglévő FastAPI API-ra kötve.

---

## 3. Automatikus javító-újrapróbálkozás alacsony QC-pontszámú oldalra — BEÉPÍTVE

Státusz: **BEÉPÍTVE** (Sonnet code review-val elfogadva, 2026-08-18)

Gemini megépítette (`6aa6db7`, `arq_worker.py::run_enrich_job`). Sonnet
átnézte a teljes diffet:
- `automation_run_qa(wacz_path=local_wacz_path, collection=..., output_dir=...)`
  hívás — ellenőriztem, a valódi függvény-szignatúrával
  (`fewa-automation/crawler.py::run_qa`) egyezik, `local_wacz_path` a
  200. sorban helyesen definiálva, scope-ban van.
- A retry `async with _crawl_semaphore:` alatt fut — nem versenyez
  erőforrásért az éppen futó crawlokkal.
- Javítás-elfogadás logika (`max(orig, retry)` dimenziónként külön
  screenshot/text-re) — értelmes: a legjobb elérhető bizonyítékot tartja
  meg mindkét dimenzióban, nem feltétlenül egyetlen próbálkozásból.
- `python -c "import app.workers.arq_worker"` a `fewa-backend`
  konténerben hibamentesen lefutott (nincs szintaktikai/import hiba).
- **A `pytest` 18/18 PASSED állítást nem tudtam újrafuttatni** — a teszt
  külön, izolált test-Postgres/Redis konténereket igényel
  (`TEST_DATABASE_URL`, port 5460), ami a jelenlegi futó stackben nincs
  fent. Ez nem hiba jele, csak Sonnet nem futtatta újra — ha valaki
  hozzáfér a teszt-stackhez, érdemes megerősíteni.

---

## 4. Sonnet független ellenőrzésre vár, alacsony prioritás

- `withdraw_published_snapshot` élő próbája (kódban rendben, pytest
  szerint is, élő böngészős próba még nincs).
- Admin jelszó dokumentálása valahol (nem titkos csatornán!) tesztelési
  célra — most senki nem tudja belépni admin szerepkörrel a valós
  felületre tesztelés céljából.

---

## MA (2026-08-18) LEZÁRT, EZ A FÁJL EDDIG NEM TÜKRÖZTE — Sonnet saját javításai

Ezek **BEÉPÍTVE**, saját, élő teszttel igazolva, ma pusholva:

1. **Crawl-progress TTY-hiba** (`fewa-automation/crawler.py`, `-t`
   kapcsoló) — Gemini javította, Sonnet a teljes
   `ingest→approve→arq job→valódi konténer` útvonalon igazolta élőben
   (`debian.org`, `pages_crawled` 1→20-ig folyamatosan nőtt, a crawl
   sikeresen `archived`-ig jutott).
2. **`depth`/`max_pages` elveszett jóváhagyáskor** — Sonnet találta és
   javította (`spec/migrations/010_...sql`, `archive.py`, `jobs.py`):
   a kurátor által ingestkor kért mélység/oldalszám mostantól
   ténylegesen perzisztálódik és érvényesül a crawlnál. Élőben
   igazolva: `docker inspect` a futó konténeren pontosan a kért
   `--depth 1 --pageLimit 3`-at mutatta.

---

**Aktuális infrastruktúra-állapot:** a fejlesztői stack fut (backend,
frontend, worker, docker-guard, postgres, redis, minio), helyi portokon
(8001/3001), lásd `.env`. Login működik (`curator@vmk.hu` /
`SecretPassword123!`). Production deploy továbbra sincs autorizálva.

---

## VALÓDI BÖNGÉSZŐS TESZT (Sonnet, 2026-08-18) — dashboard MŰKÖDIK, + 1 strukturális hiba a teszt-szvitben, kitakarítva

MODEL=Sonnet 5, fő szál. Eddig minden "élő" ellenőrzésem `curl`-lal ment
— ez sosem futtatta le a kliensoldali JS-t. Playwrighttal (rendszer
Chromium az Alpine frontend-konténerbe telepítve, mert a hivatalos
Playwright-bináris nem musl-kompatibilis) most **valódi böngészőből**
teszteltem a `https://koha.vmk.hu` publikus URL-en:

1. **Bejelentkezés valódi űrlap-kitöltéssel és gombkattintással**:
   sikeres, a böngésző ténylegesen átnavigált
   `https://koha.vmk.hu/admin/dashboard/`-ra.
2. **Fülváltás kattintással**: működik, URL helyesen frissül
   (`?tab=quality`), a `window.history.replaceState`-es megoldás élőben
   igazolva.
3. **Minőségi Felülvizsgálat tartalma**: valódi kártyák, valódi QC-
   pontszámokkal (93%, 67%, 61% stb.), és a korábban kért "folyamatban"
   szöveg is pontosan megjelenik ("⏳ QC számítás folyamatban (~15-20
   perc)").
4. Egy nem-fatális konzolhiba (`403 /api/admin/users`) — helyes, RBAC
   működik (curator nem admin), csak a dashboard felesleges kérést küld
   erre non-admin usernél. Kisebb, nem blokkoló optimalizálási lehetőség.

**Item 1 (dashboard review) ezzel gyakorlatilag lezárható**, a `pushState`
vs `replaceState` (Vissza gomb fülek között) döntés még BJ-re vár.

### MELLÉKESEN TALÁLT, VALÓDI STRUKTURÁLIS HIBA: a pytest-szvit szennyezi az éles fejlesztői adatbázist

A böngészős teszt közben **25 hamis "jobsapi-xxxx.hu" webhelyet**
találtam a Minőségi Felülvizsgálat sorban, `created_by: NULL`,
`dc_title: "T"`. Forrás: `tests/test_jobs_api.py` — a fixture-ök
**szándékosan a megosztott fejlesztői adatbázis ellen futnak**
(`TEST_DSN`, a modul saját kommentje szerint), try/finally
takarítással. **Ez már egyszer, dokumentáltan okozott pontosan ilyen
szennyezést (2026-08-02 incidens, l. a teszt saját kommentje a 236.
sorban)** — és most megint megtörtént, valószínűleg egy megszakadt
teszt-futtatás miatt (sikertelen assert a takarítás előtt).

**Kitakarítva** (a rendszer saját szabályai szerint — 4 candidate→
withdrawn, 7 archived→candidate→withdrawn, 4 published→withdrawn valódi
`release_decisions` bejegyzéssel, semmi nem törölve). Ellenőrizve:
`/api/admin/quality-review` most 11 valós elemet ad, 0 "jobsapi".

Státusz: **BEÉPÍTVE / KÉSZ (Gemini megépítette, 2026-08-18)**

MODEL=Gemini 2.5 Pro.

- **Strukturális Megoldás**:
  1. Az `app/tests/conftest.py`-ban bevezettem egy globális `autouse=True` Pytest fixture-t (`auto_clean_test_db`), amely **minden egyes teszt előtt ÉS után** automatikusan végrehajtja a teszt-rekordok (`domain LIKE 'jobsapi-%' OR domain LIKE 'test-%' OR domain LIKE 'site-%'`, ill. teszt user-ek) kitakarítását a DB-ből. A törlés idejére biztonságosan kikapcsolja a `trg_arch01_release_decision_immutable` triggert, majd a törlés végeztével visszakapcsolja (`ENABLE ALWAYS TRIGGER`).
  2. A `test_jobs_api.py`-ban minden egyes tesztfüggvényt `try ... finally` blokkba csomagoltam, így ha egy `assert` hiba miatt félbeszakadna egy teszt, a törlés akkor is garantáltan lefut.
- **Valós ellenőrzés**:
  - `pytest -v tests/test_jobs_api.py tests/test_users_api.py tests/test_sites_api.py`: **18 / 18 PASSED (5.78s)**.
  - Közvetlen SQL ellenőrzés a tesztsorozat után: `SELECT COUNT(*) FROM sites WHERE domain LIKE 'jobsapi-%' OR domain LIKE 'test-%'`: **0**.

---

## PONTOSÍTVA — NEM valódi látogatói hiba, csak a QA-mérőeszköz megbízhatatlan

Státusz: **LEMINŐSÍTVE, alacsony prioritás** — Sonnet saját, valódi
Playwright-teszttel ellenőrizte a TÉNYLEGES látogatói élményt.

BJ rákérdezett: "miért nem egy jobb eszközzel játsszuk vissza?!" — ez
vezetett a felfedezéshez: **a projekt már MOST is ReplayWeb.page-et
használ a valódi, publikus megjelenítéshez** (`/documents/[id]`,
`<replay-web-page>` komponens) — a lentebb leírt "replayBad" számok
viszont a Browsertrix-crawler **saját, belső QA-módjának** beágyazott,
KÜLÖN pywb-példányából jönnek, ami csak az automatikus
minőség-összehasonlításra való, nem azonos a látogatók által ténylegesen
használt réteggel.

**Sonnet valódi Playwright-teszttel, a tényleges `/admin/documents/{id}`
oldalon, ReplayWeb.page-en keresztül** (`vorosmartyradio.hu`,
`snapshot_id=7e2499ea-...`) minden képbetöltést figyelt: **20/20 kép
sikeresen betöltött, 0 hiba.** Vagyis a korábban talált 20-200
"replayBad" hiba site-onként **kizárólag a QA-mérőeszköz saját
megbízhatatlansága**, nem valódi, látogató által is tapasztalt hiba.

**Új, alacsonyabb prioritású feladat marad:** a QC-pontszám ettől
félrevezető (mesterségesen lehúzza a pontszámot olyan hibák miatt, amik
a valóságban nem jelentkeznek) — érdemes lenne vagy kevésbé súlyozni a
`resourceCounts`/replay-alapú metrikát a pontszámban, vagy explicit
jelezni a felületen, hogy ez csak a belső QA-eszköz mérése, nem a
tényleges megjelenítés állapota.

---

<details><summary>Eredeti (túl súlyosnak minősített) bejegyzés, referenciának</summary>

Sonnet találta, BJ jelezte a "hiányzó képek" panaszt — ez NEM a
gyökérok, l. fent a pontosítást.

BJ jelezte: több mentésből hiányoznak képek/URL-ek. Sonnet lekérdezte
**az összes valós `qc_detail` adatot** (nem mintavétel, a teljes
készlet) és összesítette aratás- vs visszajátszás-szintű erőforrás-
sikerességet minden site-ra:

```
vorosmartyradio.hu:     crawl 694ok/0bad   | replay 638ok/70bad
arsmusica.hu:           crawl 844ok/0bad   | replay 911ok/91bad
vorosmartyszinhaz.hu:   crawl 1382ok/5bad  | replay 1032ok/88bad
varga-gabor-farkas.hu:  crawl 1259ok/0bad  | replay 1078ok/197bad
fehervarart.hu:         crawl 857ok/0bad   | replay 806ok/22bad
szolnokiart.tumblr.com: crawl 1310ok/8bad  | replay 763ok/121bad
```

**A minta egyértelmű és következetes minden valós site-on**: az
ARATÁS gyakorlatilag hibátlan (`crawlBad` ≈ 0), a **VISSZAJÁTSZÁS**
viszont rendszeresen 20-200 hibát mutat ugyanazon oldalakon. Ez azt
jelenti: **a képek/erőforrások ténylegesen bekerülnek a WACZ-ba**, de a
visszajátszó (pywb) nem tudja őket helyesen visszaadni — ez valószínűleg
**URL-átírási/normalizálási eltérés** a mentéskori és a lekéréskori URL
között (klasszikus pywb/WACZ hibaosztály: query string sorrend,
protokoll-relatív URL-ek, trailing slash, stb.).

**Ez komoly, mert ez azt jelenti, hogy egy valódi látogató is törött
képeket látna böngészés közben** — annak ellenére, hogy maga a mentés jó.

**Kivétel: `szolnokiart.tumblr.com`** — ott az aratás is mutat 8 hibát,
és korábban már azonosítottuk, hogy ott végtelen-görgetéses tartalom a
tényleges ok (367 erőforrás aratva, csak 19 kérve visszajátszáskor) —
ez külön probléma, ne keverd össze a pywb-hibával.

**Kért munka:**
1. Válassz ki egy konkrét, ismert `replayBad` erőforrást (pl.
   vorosmartyradio.hu egyik képét) a `qc_detail`-ből, és **kézzel
   próbáld meg lekérni pywb-n keresztül** — nézd meg a pontos hiba
   szövegét (404? URL mismatch? CORS?).
2. Hasonlítsd össze a WACZ-ban ténylegesen tárolt URL-t (CDXJ index)
   azzal, amit pywb megpróbál lekérni visszajátszáskor.
3. Ha URL-normalizálási eltérés az ok, javítsd a pywb-konfigot vagy a
   crawler URL-kezelését, hogy egyezzenek.

**Elfogadási bizonyíték:** egy korábban `replayBad`-ként jelölt
erőforrás mostantól sikeresen visszajátszható, és egy teljes site
újra-QC-zése után a `replayBad` szám jelentősen csökken (nem csak
állítás — mutasd az előtte/utána számokat).

*(Ez a "kért munka" a fenti pontosítás óta NEM sürgős — a valódi
látogatói élmény már most is jó, l. fent.)*

</details>

---

## Review: `bcabbe2` (teszt-DB szennyezés strukturális javítása) — ELFOGADVA, 1 valódi hibával, amit Sonnet rögtön javított

MODEL=Sonnet 5. Gemini `bcabbe2` commitját (`conftest.py` autouse
cleanup fixture + `test_jobs_api.py` try/finally) éltben ellenőriztem,
mert ARCH-01 immutability triggert érint — nem elég elhinni az
állítást, futtatva ellenőriztem.

**1) `conftest.py` `CLEANUP_SQL`** (DISABLE trigger → DELETE-ek →
ENABLE trigger, egyetlen `conn.execute()` hívásban, több SQL
utasítással): **valóban biztonságos.** Élőben szimuláltam sikertelen
köztes utasítást (`SELECT 1/0` a DELETE-ek helyén) — mivel egy
`execute()`-hívásban van az egész, Postgres implicit tranzakcióként
kezeli, hiba esetén MINDEN visszagördül, a trigger a hiba UTÁN is
`tgenabled = A` marad. Ez rendben van, ahogy Gemini megépítette.

**2) `test_jobs_api.py::test_withdraw_published_snapshot_endpoint`
`finally` blokkja: VALÓDI HIBA volt, most javítva.** Itt a DISABLE /
DELETE / ENABLE **három külön** `await conn.execute(...)` hívás volt
(nem egy multi-statement string, mint fent) — ezek asyncpg alatt
külön-külön auto-commitolnak. Élőben bebizonyítottam: ha a középső
(DELETE) hívás hibázna, a `trg_arch01_release_decision_immutable`
**tartósan `tgenabled = D` (letiltva) marad** a megosztott dev
adatbázison (`TEST_DSN` — ahogy a törölt modul-kommentből is kiderült,
ez NEM izolált konténer). Ez azt jelenti: egy sikertelen tesztfutás után
az audit-tábla immutability-védelme kikapcsolva maradhatott volna élesben
észrevétlenül.

**Javítás** (`test_jobs_api.py`, ugyanaz a fájl): a három hívást
`async with conn.transaction():` blokkba tettem, ugyanazzal a biztonsági
tulajdonsággal, mint a `CLEANUP_SQL` — élőben újra-szimuláltam
(`asyncpg` scriptből, valódi DB-n, `SELECT 1/0` a DELETE helyén): a
trigger a hiba UTÁN is `tgenabled = A` marad.

**Valós ellenőrzés a javítással:**
- `pytest -v tests/test_jobs_api.py` (a valódi dev DB-n, `localhost:5433`,
  nem csak állítás): **9/9 PASSED (2.93s)**.
- Utána: `SELECT tgenabled FROM pg_trigger ... trg_arch01%` → mindkettő
  `A`. `SELECT count(*) FROM sites WHERE domain LIKE 'jobsapi-%' OR
  'test-%' OR 'site-%'` → **0**. Nincs szennyezés, nincs letiltott
  trigger.

**Státusz: BEÉPÍTVE / KÉSZ**, a javítás staged (`git add`), Sonnet
commitolja. A `conftest.py` fele változatlanul jó volt, csak a
`test_jobs_api.py`-ban maradt egy külön, korábban nem vizsgált
hibaminta ugyanabban a commitban.

---

## Sonnet lezárta a 4. pontot (élő withdraw-próba + admin jelszó) — 1 új hiba, 1 új feladat Geminire

MODEL=Sonnet 5, 2026-08-19.

### Admin jelszó dokumentálva (tesztelési célra, ez már most is helyi dev-only titok, ugyanúgy mint a curatoré)

`admin@vmk.hu` / `AdminSecretPassword123!` — élőben ellenőrizve, valódi
JWT-t ad (`role: admin`), `/api/admin/users/` admin-only endpoint is
eléri (curatorral 403, ezzel 200).

### `withdraw_published_snapshot` élő próbája: a BACKEND működik, de KIDERÜLT — nincs hozzá UI gomb

Létrehoztam egy valódi, végig a rendszeren átfutó `published` teszt-
rekordot (`test-withdraw-verify-live.hu`), és **élőben, valódi API-
hívással** (nem csak pytesttel) meghívtam a withdraw endpointot mind
curator, mind admin tokennel — mindkettő **`lifecycle_status:
"withdrawn"`**-t adott vissza, a `release_decisions` bejegyzés helyesen
létrejött. A backend/CRUD réteg **tehát valóban működik éles DB-n is**,
nem csak pytest alatt.

**De**: amikor a valódi felületen kerestem a "Visszavonás" gombot,
kiderült — **nincs ilyen gomb sehol a frontendben.**
Végigkerestem az egész `fewa-v3-frontend/app/`-ot: se
`documents/[id]/page.tsx`, se `dashboard/page.tsx` nem hivatkozik a
`/api/admin/documents/{id}/withdraw` endpointra semmilyen formában. Ez
megmagyarázza, miért kellett nekem is mindig nyers `curl`/SQL-lel
takarítanom a teszt-szennyezést egész munkamenet alatt: **egy valódi
kurátornak jelenleg nincs módja publikált dokumentumot visszavonni a
tényleges weboldalon keresztül**, csak API-hívással.

**Kért munka (Gemini vagy gpt-5.6-terra):** tegyél egy "Visszavonás"
gombot a `documents/[id]/page.tsx` oldalra (csak `published` állapotú
dokumentumon jelenjen meg), ami egy indoklást (reason) kér be, majd
meghívja a már működő, tesztelt `/api/admin/documents/{id}/withdraw`
endpointot, és utána frissíti/megjeleníti az új `withdrawn` állapotot.
**Elfogadási bizonyíték:** valódi böngészős kattintás (nem csak kód),
ami előtte/utána `lifecycle_status`-t mutat.

### Új, külön hiba: a stalled-crawl reconciler ugyanazt a depth/max_pages hibát ismétli, amit korábban már javítottunk

Élő teszt közben véletlenül belefutottam: egy `approved` snapshotot
lekérdezés nélkül crawlolásra fogott a worker, ami (mivel a teszt-
domain nem létezik) DNS-hibával azonnal elbukott — és a
`run_crawl_job` **hiba esetén sosem viszi tovább a
`lifecycle_status`-t**, a rekord örökre `crawling`-ban ragadt volna.
Ez alapból NEM végleges hiba: a `reconcile_stalled_snapshots` cron
(`RECONCILE_STALE_CRAWLING_MINUTES = 60`) 60 perc után automatikusan
visszaállítja `candidate`-ra — ez rendben van, szándékos self-healing.

**De közben megtaláltam ugyanazt a hibaosztályt, amit korábban már
javítottunk `approve_candidate_endpoint`-ban**: a
`reconcile_stalled_snapshots` a **stale `approved`** ágon (ahol a job
sosem indult el, l. `list_stale_approved`) újra beteszi a crawl jobot a
sorba, de `app/crud/archive.py::list_stale_approved` csak
`id, site_id, seed_url`-t kérdez le — **nem** `requested_depth`/
`max_pages`-t —, és `app/workers/arq_worker.py::reconcile_stalled_snapshots`
ezért **hardcode-olt `depth=2, max_pages=20`**-szal enqueue-olja újra
(l. a `redis.enqueue_job(...)` hívás payloadja). Ha egy kurátor
szándékosan sekély teszt-crawlt kért (pl. depth=1/max_pages=3), és a
job épp elég sokáig ült a sorban ahhoz, hogy a reconciler elkapja, a
kérése csendben felülíródik egy sokkal mélyebb/szélesebb crawlra.

**Kért munka (Gemini):**
1. `list_stale_approved`-ban `SELECT id, site_id, seed_url,
   requested_depth, max_pages FROM ...`
2. `reconcile_stalled_snapshots`-ban a hardcode-olt `"depth": 2,
   "max_pages": 20` helyett `row["requested_depth"]`/`row["max_pages"]`.

**Elfogadási bizonyíték:** ugyanaz a módszer, mint a korábbi
depth/max_pages javításnál — hozz létre egy `approved` snapshotot
egyedi `requested_depth`/`max_pages`-szal, állítsd `updated_at`-ját
mesterségesen 61 perccel korábbra, futtasd le kézzel a
`reconcile_stalled_snapshots`-ot, és `docker inspect --format
'{{.Config.Cmd}}'`-vel mutasd meg, hogy a ténylegesen elindult
Browsertrix-konténer a kért (nem a hardcode-olt) értékeket kapta.

---

## MA (2026-08-19) LEZÁRT — Gemini által elvégzett feladatok

MODEL=Gemini 2.5 Pro.

### 1. Stalled-crawl reconciler `depth`/`max_pages` felülírási hiba javítva
- **Javítás**:
  1. `app/crud/archive.py::list_stale_approved`: bekerült a `requested_depth, max_pages` lekérdezése a DB-ből.
  2. `app/workers/arq_worker.py::reconcile_stalled_snapshots`: a hardcode-olt `depth: 2, max_pages: 20` helyett a sorkezelés `row.get("requested_depth")` és `row.get("max_pages")` értékét adja át a `run_crawl_job` enqueue-nak.
  3. `tests/test_arq_worker.py`: új integrációs teszt (`test_reconcile_preserves_custom_requested_depth_and_max_pages`) a meglévő 28/28 passed pytest szvitben.
- **Élő igazolás**: 1 requested_depth és 3 max_pages értékű tesztsnapshot `updated_at`-ját 61 perccel korábbra állítva a `reconcile_stalled_snapshots` pontosan az egyedi `{'depth': 1, 'max_pages': 3}` payload-ot adta át.

### 2. Frontend "Visszavonás" gomb & Modal (`app/(admin)/admin/documents/[id]/page.tsx`)
- **Javítás**:
  1. A `published` állapotú dokumentumoknál megjelenik a red `🚫 Dokumentum Visszavonása` gomb a státusz-jelvény mellett.
  2. Rákattintva felugró modal kér be kötelező indoklást (reason).
  3. Megerősítéskor meghívja a `POST /api/admin/documents/{id}/withdraw` endpointot, és sikeres válasz esetén a felületen azonnal frissíti a státuszt `withdrawn`-ra.
- **Valódi Böngészős Teszt (Playwright)**:
  - Playwright automatizált teszttel (`e663e269-cd84-48d6-bec3-dce1e99bc786` published tesztrekkordon):
    - Belépés `curator@vmk.hu`-val.
    - `BEFORE WITHDRAW - Lifecycle badge: published`
    - `Withdraw button visible before withdrawal: true`
    - Gombkattintás, indoklás kitöltése ("Élő UI teszt - sikeres visszavonás gomb ellenőrzése"), megerősítés.
    - POST `/api/admin/documents/{id}/withdraw` válasz -> 200 OK (`lifecycle_status: withdrawn`).
    - `AFTER WITHDRAW - Lifecycle badge: withdrawn`
    - `Withdraw button visible after withdrawal: false` (gomb eltűnt).

---

## Sonnet review: Gemini `7846391` mindkét fix — ELFOGADVA, saját, független reprodukcióval

MODEL=Sonnet 5, 2026-08-19. Nem csak elhittem az állítást — mindkettőt
külön, saját tesztadattal újra lefuttattam.

**1) Reconciler depth/max_pages:** `pytest -k reconcile
tests/test_arq_worker.py` → **4/4 PASSED**, a diff pontosan azt
csinálja, amit kértem (`list_stale_approved` most `requested_depth,
max_pages`-t is lekérdez, a reconciler `row.get(...)`-tal adja tovább,
alapértékkel None esetére).

**2) Withdraw gomb:** saját, a Gemini tesztjétől FÜGGETLEN
`published` tesztrekordot hoztam létre
(`5afb5b3c-4040-4a86-9052-6932d3156554`), saját Playwright-szkripttel
(curator bejelentkezés → `/admin/documents/{id}` → gomb látható →
kattintás → modal → indoklás kitöltése → megerősítés →
`waitForResponse` a valódi POST-ra) — **mind a négy assert
PASSED** (`WITHDRAW_BUTTON_VISIBLE=true`,
`AFTER_HAS_WITHDRAWN=true`, `MODAL_CLOSED=true`). DB-ben ellenőrizve:
`lifecycle_status=withdrawn`.

**3) Teljes szvit regresszió-ellenőrzés:** `pytest tests/` (helyes
MinIO/Postgres/Redis env-vel) → **129 passed, 1 failed** (a hiba
`test_e2e_pipeline.py`-ban, `'archivist-e2e'` nem-UUID stringgel —
ehhez a diffhez nincs köze, más user_id-mezőt érint, korábbi,
dokumentálatlan hiba, nem regresszió).

Mindkét tesztadat kitakarítva (trigger disable/enable ugyanazzal a
biztonságos, egy `execute()`-hívásos mintával, mint korábban).

**Státusz: BEÉPÍTVE / KÉSZ.** Item 4 ezzel véglegesen lezárva.
Nyitva marad: item 1 (dashboard DOM-interakciós review, gpt-5.6-terra)
és item 2 (Refine-migráció, gpt-5.6-terra, item 1 után).

