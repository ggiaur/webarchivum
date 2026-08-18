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
