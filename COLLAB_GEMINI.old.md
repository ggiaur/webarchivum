# FEWA — közös fejlesztési napló és release-gate

**Indítás:** 2026-08-13  
**Cél:** a FEWA-ból bizonyíthatóan működő, biztonságos Fejér vármegyei webarchívum legyen: autonóm forrásfelderítés → kurátori döntés → legfeljebb két hoppnyi mentés → objektumintegritás és tényleges replay-minőségellenőrzés.

Ez a fájl az egyetlen átadási pont GPT, Sonnet és — csak szükség esetén — Opus között. A bejegyzések időbélyegesek, konkrétak és append-only jellegűek: feladat, fájlok, elfogadási feltételek, futtatott parancsok, eredmények, verdict. Az olyan státusz, hogy „még dolgozik” vagy „nincs változás”, nem elfogadható átadás.

## Szerepkörök, modellek és költségkeret

| Szerepkör | Modell | Reasoning | Felelősség | Mikor használjuk |
|---|---|---:|---|---|
| Scope / implementáló | `gpt-5.6-terra` | `high` | Specből kis, tesztelt implementáció; csak a kijelölt fájlok | Minden normál fejlesztési egység |
| Független QA / release gate | `gpt-5.6-sol` | `high` | Adversarial teszt, regresszió, reprodukálható verdict | Minden candidate után |
| Külső integritási és security reviewer | Sonnet 5 | a Sonnet-bejegyzésben kötelezően rögzítendő | Önálló kód- és szerződésfelülvizsgálat; `ELFOGADVA` vagy konkrét `JAVÍTÁS KÉRVE` | Kötelező minden biztonsági, archiválási vagy publikálási változás előtt |
| Architektúra-eszkaláció | Opus 5 | csak szükség szerint | Csak feloldhatatlan adatmodell-, jogi-, security- vagy költségellentmondás | Nem rutin reviewra, nem implementálásra |

**Gazdaságossági szabály:** a Terra végzi a termelő munkát, a Sol csak független kapu és célzott hibakeresés. Sonnet egyszer lép be release candidate-nál; újra csak konkrét javítás után. Opust nem használunk olyan kérdésre, amelyet a specifikáció vagy a QA eldönt.

## Folyamatos munkafolyamat

```text
Scope → GPT pre-QA → Builder → GPT független QA → Sonnet gate
                                 ↑                    │
                                 └── konkrét finding ──┘
                                            ↓
                                  release-gate → emberi deploy-jóváhagyás
```

1. **Scope.** A feladatnak van üzleti célja, threat modellje, pontos API/adatmodell-szerződése, out-of-scope listája és gépileg ellenőrizhető acceptance feltétele.
2. **GPT pre-QA.** Még implementálás előtt megkeresi az ellentmondásokat és a visszaélési lehetőségeket.
3. **Builder.** Csak a jóváhagyott scope szerint dolgozik, minden új viselkedéshez tesztet ír; nem módosít más aktív feladat fájljában.
4. **Független QA.** Nem a Builder állítását fogadja el: saját reprodukció, negatív tesztek, célzott és teljes regresszió. A verdict csak `ELFOGADVA` vagy tételes `JAVÍTÁS KÉRVE` lehet.
5. **Sonnet gate.** A Sonnet a teljes diffet, a specifikációt, az acceptance mátrixot és a tényleges futási eredményt kapja. Egyik GPT sem írhat „BEÉPÍTVE” verdictet Sonnet-válasz nélkül.
6. **Release.** A release gate csak „BEÉPÍTVE JAVASOLT” lehet. Éles deploy, DNS-, Nginx- vagy titokmódosítás kizárólag emberi jóváhagyással történik.

**Figyelési szerződés:** egy Sonnet-bejegyzés csak akkor tekinthető átvettnek, ha a következő GPT-bejegyzés hivatkozik a pontos blokkra és ugyanabban a bejegyzésben megadja a teendőt vagy a release-verdictet. A következő kapu nem várhat néma, általános „status unchanged” üzenetre.

## P0 — ARCH-01: futtatható, biztonságos archív pipeline

**Állapot:** SCOPE KÉSZÍTENDŐ — production kódhoz még nem nyúlunk.

### Kötelező eredmény

- A rendszer külön, futtatható komponensekkel rendelkezik: API, discovery worker, crawl executor, QA executor, tároló és valódi AI-szolgáltatás.
- A külső Nginx proxy külön infrastruktúra. A FEWA csak a dokumentált külső URL- és header-szerződésére támaszkodhat; belső `/api/proxy` végpont nem követelmény.
- A discovery valós keresési/böngészési forrásból jelöltet hoz létre; minden jelölthöz forrás, időpont, kivonat, determinisztikus Fejér-jel, AI-döntés, confidence, modell- és promptverzió tartozik.
- A crawler legfeljebb H0→H1→H2 mélységig megy, és per-URL manifestet tárol: kanonikus URL, hopp, HTTP-státusz, robots-döntés, MIME, mentési eredmény és kihagyási ok.
- A rendszer blokkolja a privát/IP-lokális, DNS-rebindinges és policy-n kívüli célokat. Az új domain automatikusan nem publikálható.
- Publikáció előtt: WACZ/WARC/CDXJ-validáció, MinIO-visszaolvasásos SHA-256, teljes QA-manifest, replay-böngészés, screenshot/text/resource eredmény és hibaoldal/cookie/login felismerés.
- Részleges crawl, hiányos QA-adat, kritikus replay-erőforráshiba vagy ismeretlen seed-státusz csak manuális felülvizsgálatba kerülhet; automatikus publikáció tilos.

### Kötelező bizonyítékok

1. Izolált, valós Browsertrix + MinIO + Postgres integrációs futás egy kontrollált tesztwebhelyen.
2. Egy jogszerűen kijelölt Fejér vármegyei pilot: discovery → döntés → két hopp → WACZ → QA → kurátori felülvizsgálat.
3. Negatív tesztek: nem Fejér-tartalom, private-IP/DNS rebinding, robots tiltás, 404/cookie/login fal, idő- és méretlimit, sérült WACZ, hiányos QA-sor, `replayBad`, MinIO checksum eltérés.
4. Teljes regression futás és a környezetből reprodukálható indítóparancsok.

### Jelenlegi auditból ismert blokkolók

- A discovery csak query-builder/szövegszűrő, nincs kereső vagy AI-böngésző integráció.
- A Compose-ból hiányzik a worker és a Browsertrix executor; a backend image nem tartalmazza a sibling `fewa-automation` könyvtárat sem.
- A production/test Compose környezeti változónevei nem egyeznek a backend Settings neveivel.
- A QC átlagolás nem fail-closed hiányos oldalakra és nem használja a `replayBad` adatot.
- A jelenlegi RAG, összefoglalás és embedding nem valódi AI, ezért discovery-döntésre nem használható.

## Következő átadás formátuma

```markdown
## [YYYY-MM-DD HH:MM UTC] ROLE — ARCH-01 / <részfeladat>
MODEL=<név>; REASONING=<szint>
ÁLLAPOT: SCOPE KÉSZ | JAVÍTÁS KÉRVE | ELFOGADVA | BEÉPÍTVE JAVASOLT
ÉRINTETT FÁJLOK: ...
ACCEPTANCE / THREAT MODEL: ...
FUTTATÁS: `<parancs>` → `<eredmény>`
VERDICT / KÖVETKEZŐ CÍMZETT: ...
```

---

## EXTERNAL REVIEW DISPATCH — Sonnet 5 / ARCH-01

**Kötelezően olvasandó közös fájl (abszolút útvonal):**
`/srv/projects/webarchivum/COLLAB_GEMINI.md`

**Forrásprojekt-handoff:** `/srv/projects/it-lens-audit-system/COLLAB_GEMINI.md`
lezárt IT Lens workstreamet tartalmaz; FEWA review-t kizárólag ebbe a
Webarchivum-fájlba szabad rögzíteni.

**Kért Sonnet-feladat:** ARCH-01 scope integrity/security review. Olvasd el a
teljes fájlt, különösen a P0/ARCH-01 részt és az utolsó Builder/GPT pre-QA
bejegyzést. Ellenőrizd a discovery → H0/H1/H2 crawl → WACZ/MinIO → replay-QC
szerződés teljességét, valamint az SSRF/DNS-rebinding, prompt-injection,
partial-crawl, artifact-integrity és autopublish ellenállását.

**Megengedett verdict:** `ELFOGADVA` vagy tételes `JAVÍTÁS KÉRVE`. A válaszban
kötelező: `MODEL=Sonnet 5`, reasoning/depth, pontos hivatkozások, reprodukció
vagy specifikációs ellenpélda, és következő címzett. Általános státuszüzenet
nem verdict. Production kód, deploy, Nginx vagy titok nem módosítható e review
során.

## [2026-08-13 UTC] Sonnet 5 — SG-ARCH-01 scope/integrity review

MODEL=Sonnet 5; REASONING=Sonnet által a végső verdictben rögzítendő  
ÁLLAPOT: **AKTÍV — átvéve**

Sonnet explicit visszajelzése: a FEWA valódi, aktívan fejlesztett kódbázis,
jelenlegi commit-történettel és folyamatban lévő nem commitolt munkával. A
scope és az ismeretlen kódbázis miatt a Sonnet külön alagentet küld a
specifikáció és az aktuális implementáció összevetésére, az SG-02/SG-03
módszeréhez hasonlóan.

ÉRINTETT TERÜLET: ARCH-01 teljes scope; discovery, H0/H1/H2 crawl,
WACZ/MinIO, replay-QC, Compose/worker és security szerződés.

KÖVETKEZŐ KAPU: Sonnet tételes `ELFOGADVA` vagy `JAVÍTÁS KÉRVE` bejegyzése
ugyanebbe a fájlba. A GPT pre-QA/build nem kerülheti meg ezt a scope-integrity
review-t; production kód, deploy, Nginx és titok továbbra sem módosítható.

## [2026-08-13 08:15 UTC] ARCHITECT — ARCH-01 / autonóm discovery–kurátor–H0/H1/H2–WACZ–fail-closed replay-QC specifikáció
MODEL=gpt-5.6-terra; REASONING=high
ÁLLAPOT: SCOPE KÉSZ
ÉRINTETT FÁJLOK: `COLLAB_GEMINI.md` (csak append); implementáció következő körének kijelölt céljai: `spec/migrations/005_arch_01_pipeline.sql` (új), `spec/pipeline_schemas.py`, `spec/openapi.yaml`, `fewa-automation/discovery.py`, `fewa-automation/crawler.py`, `fewa-v3-backend/app/api/v1/jobs.py`, `fewa-v3-backend/app/workers/arq_worker.py`, `fewa-v3-backend/app/core/minio_client.py`, `fewa-v3-backend/app/core/config.py`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example` és célzott tesztek. Production kód ebben az átadásban nem változott.

### 1. Döntés, határ és változatlan üzleti munkafolyamat

Az ARCH-01 az IT-lens szerinti kötelező kapus folyamatot valósítja meg, nem rövidíti le azt:

```text
ütemezett discovery → GPT pre-QA → kurátori döntés → crawl executor
→ WACZ + MinIO-integritás → QA executor → GPT független QA
→ Sonnet gate → „BEÉPÍTVE JAVASOLT” → emberi deploy-jóváhagyás
```

Az alkalmazási életciklus ettől elkülönülő, perzisztens állapotgép. A discovery-jelölt **nem** `archived_snapshot`: előbb bizonyítékos jelölt, majd emberi kurátori elfogadás után keletkezhet crawlhoz kötött snapshot. Kötelező üzleti út:

```text
discovered → prequalified | uncertain | rejected | suppressed
prequalified/uncertain → curator_approved | curator_rejected
curator_approved → approved snapshot → crawling → archived_pending_qc
→ qc_passed_pending_release | qc_review_required | integrity_failed
qc_passed_pending_release → published csak release-gate és kurátori kiadás után
```

`rejected`, `suppressed`, `integrity_failed` és a hard QC-hibás állapotok soha nem kerülhetnek automatikus crawlba vagy publikációba. A jelenlegi `candidate → approved → crawling → archived → indexed → published` trigger és a `record_qc_result()` 96 pontos automatikus publikációja ezért ARCH-01-kompatibilitási blokk: az automatikus `published` átmenetet meg kell szüntetni. A 0–100 pont csak diagnosztika; kiadásról kapus döntés határoz.

Az inbound proxy teljesen külön Nginx szerver. FEWA nem indít, nem konfigurál és nem tesztel Nginx-konténert; a FEWA kizárólag a lent definiált HTTP-szerződésre támaszkodik. Ez **nem** az outbound crawler egress-kontrollja, az külön kötelező komponens.

### 2. Futó architektúra és felelősségek

1. **API / kurátori UI backend:** hitelesít, kizárólag belső commandokat ad ki, a jelöltet és döntést kezeli; nem futtat Browsersrixet, nem használ Docker socketet, és nem fogad el kliens által megadott crawl-policyt.
2. **Discovery worker:** ütemezett keresőadapterből és engedélyezett linkforrásból jelölteket szed; előszűr, biztonságosan fetch-el, Fejér-bizonyítékot és AI-döntést rögzít. Nem crawlol és nem publikál.
3. **Crawl executor:** saját, korlátozott jogosultságú Browsertrix futtató. Egy már jóváhagyott, szerveroldalon létrehozott `CrawlPlan` alapján ír ideiglenes outputot és immutable crawl manifestet. Nem olvas admin JWT-t, nem ír közvetlenül publikus státuszt.
4. **Artifact/integrity worker:** WACZ ZIP/WACZ/WARC/CDXJ ellenőrzés után feltölt, majd MinIO-ból frissen visszaolvasva újra SHA-256-ot számol. Csak ezen siker után kapcsolható a snapshothoz az artifact.
5. **QA executor:** a feltöltött objektum letöltött, ellenőrzött példányán Browsertrix QA-t és izolált replay-renderelést futtat; teljes, per-URL QA-manifestet ír.
6. **Release/kurátori gate:** csak a QA-manifestet, crawl-manifestet, integritási eredményt és kurátori indoklást értékeli. Nem vezethető le puszta átlagpontból.
7. **Postgres, Redis, MinIO:** Postgres a döntési/audit igazságforrás; Redis csak kézbesítési mechanizmus; MinIO a WACZ és immutable mellékletek tára. Redis-kiesés vagy job elvesztése nem változtathat publikált állapotot.

Az executor nem indulhat a backend konténerből `docker run`-nal és nem kaphat széles Docker socketet. Legyen önálló, version-pinnelt Browsertrix worker image, egy feladatonkénti munkakönyvtárral és nem root felhasználóval. A backend image-ből jelenleg hiányzó sibling `fewa-automation` import így megszűnik mint rejtett deployment-függőség. A feladatokat explicit, verziózott queue-payload közvetíti; minden oldalváltozat és Browsertrix image digest bekerül a manifestbe.

### 3. Discovery: forrás, bizonyíték és költségérzékeny AI

**Forrásadapter-szerződés.** A `SearchProvider` csak konfigurált, szerződésileg engedélyezett API-t vagy jogszerűen automatizálható nyilvános keresőfelületet használhat. Minden találat kötelező mezője: `provider`, `provider_result_id` (ha van), `query`, `query_version`, `retrieved_at`, `rank`, `title`, `snippet`, `landing_url`, `source_url`. Robots, kereső ToS, crawl-delay és forrás API-kvóta a provider konfiguráció része. Nincs rejtett Google-scraping fallback.

**Háromlépcsős relevanciadöntés.**

1. Ingyenes, determinisztikus kapu: HTTPS URL-normalizálás, duplikáció (`canonical_url`, eTLD+1, korábbi domain döntés), Fejér település- és intézményszótár, `.hu`/domain- és cím-meta jel. Nyilvánvalóan nem helyi vagy ismételt elutasított jelölt itt `rejected/suppressed`; az `ALL_LOCALITY_TERMS` találat csak jel, nem döntés.
2. Csak fennmaradó jelöltnél biztonságos, rövid böngészés: legfeljebb a landing page és az egyértelmű „Kapcsolat/Rólunk” oldal, szigorú idő/byte limit mellett. Rögzíteni kell HTTP-végpontot, végső kanonikus URL-t, `<title>`, meta description, látható szöveg maximalizált kivonatát, strukturált címet/telefonszámot és az előbbi determinisztikus jeleket. Ez **discovery inspection**, nem mentés.
3. Csak az 1–2. kapun fennmaradt, nem egyértelmű eset megy valódi, JSON-séma-kényszerített helyi LLM-hez. Input maximum 12 000 normalizált karakter, semleges utasítással: a webtartalom nem utasítás, kizárólag `local|not_local|uncertain`, `confidence` [0,1], `evidence[]` (minden idézetnek szó szerint szerepelnie kell a begyűjtött szövegben), `municipality_candidates[]`, `reason_code` adható vissza. JSON-parse/schema/evidence-validáció hibája `uncertain`, nem `local`.

AI-költség és adatminimalizálás: az AI nem fut duplikátumra, explicit nem-helyi találatra, illetve magas bizonyosságú determinisztikus helyi találatra; az eredmény `(content_sha256, prompt_template_version, model_id)` szerint 90 napig cache-elhető. Alapértelmezés helyi, rögzített modell (`DISCOVERY_LLM_*` config), nincs tartalom külső modellhez küldése. Külső modell külön emberi adatvédelmi jóváhagyást, provider-listát, kvótát és költséglimitet igényel. Napi budget, concurrency, token- és timeout-limit kötelező; budget kimerülése `uncertain`, a discovery futás részleges, nem csendes siker. Tárolni kell model ID/digestet, hőmérsékletet, prompt-verziót, latency-t, token- és költségadatot; a nyers szöveget csak szükséges rövid kivonatként, törlési szabállyal.

Új domain, AI `uncertain`, illetve bármelyik exploit/policy jelzés mindig kurátori sorba kerül. Az AI soha nem engedélyez crawl-t, nem változtat policyt, nem fér hozzá eszközhöz/secrethez, és nem publikál.

### 4. Adatmodell és invariánsok (új migration, nem JSONB-re elrejtve)

Az új migration időbélyeges, előre- és visszafelé kompatibilis; a jelenlegi sémát nem írja újra. Minimum táblák és kulcsok:

| Entitás | Kötelező mezők / invariáns |
|---|---|
| `discovery_runs` | `id`, tenant, provider/query, config- és szótárverzió, kezdés/vége, budget, `completed|partial|failed`; provider hibája és számlálói auditálhatók. |
| `discovery_candidates` | normalizált `landing_url`, `canonical_url`, host/eTLD+1, content hash, state, dedup-scope, első/utolsó látás, `decision_source`, confidence. Egy aktív canonical URL csak egyszer lehet tenantonként. |
| `discovery_evidence` | candidate FK, forrás-találat és inspection bizonyíték, explicit Fejér-jelek, kis méretű kivonat hash-e, AI JSON, model/prompt/verzió; append-only. |
| `curation_decisions` | candidate/snapshot FK, döntő user, `approve|reject|suppress|release|hold`, kötelező indok, policy-version, időpont. Egyetlen aktuális döntéshez auditált eseménysor tartozik. |
| `crawl_runs` | snapshot, immutable `CrawlPlan`, Browsertrix image digest, worker/run ID, limit outcome, kezdés/vége, manifest hash és állapot. Idempotencia kulcs: snapshot + approval/policy revision. |
| `crawl_pages` | crawl_run, canonical URL, `hop` CHECK 0..2, parent URL, final URL, status, MIME, robots-, scope- és capture-döntés, kihagyási/hhiba-kód, bytes, timestamp. Egy crawlban canonical URL + hop egyedi. |
| `artifacts` | snapshot/crawl_run, object key/version-id, WACZ SHA-256, méret, upload-visszaolvasási SHA-256, WACZ-validator report hash, retention/lock állapot. `verified_at` NULL esetén nem release-elhető. |
| `qa_runs` és `qa_pages` | artifact FK, QA/replay tool+image digest, minden kiválasztott URL expected/actual QA sor, screenshot/text/resource értékek, `replayBad`, wall/error detektorok, evidence artifact hivatkozás, verdict. |
| `release_decisions` | snapshot, gate-mátrix hash, kurátori döntés/indoklás; csak e rekord `released` értéke után válhat publikus a snapshot. |

Az `archived_snapshots` marad a központi bibliográfiai rekord, de kapjon explicit `release_state`, `artifact_id`, `crawl_run_id`, `qa_run_id` referenciát; a `qc_detail` kompatibilitási nézet, nem elsődleges igazságforrás. `crawl_policies.depth` CHECK és valamennyi Pydantic/API határérték `0..2` (H0 seed, H1 első link, H2 második link); a korábbi 3–5 értékű policy-k migrációkor `on_hold` + kurátori újrajóváhagyás, nem néma clamp. `page_limit`, size/time limit, include/exclude, allowed MIME, robots és ugyanazon-host/scope mind a verziózott `CrawlPlan` része; kliens csak policy azonosítót választhat, számokat nem küldhet.

Minden állapotváltozás egy DB tranzakcióban lifecycle/release/audit eseményt ír. A queue feldolgozása legalább egyszeri lehet, de az artifact kapcsolás, release és publish idempotens, unikális kulccsal/optimistic transitionnel. Worker crash, lock-expiry vagy ismételt üzenet nem indíthat második nyilvános kiadást.

### 5. Belső API-szerződés és jogosultság

Minden `/api/admin/*` végpont `curator` vagy `admin`; discovery konfiguráció és suppress-lista csak `admin`; a user identity kötelező, `user_id=None` nem elfogadható döntési/audit útvonalon. A normál felhasználó nem indíthat tetszőleges URL crawl-t.

| Végpont | Input | Eredmény / szabály |
|---|---|---|
| `POST /api/admin/discovery-runs` | provider profile, query-set version (admin) | 202, csak szerveroldali konfigurációval létrejött run. |
| `GET /api/admin/discovery-candidates?state=` | lapozás/szűrés | bizonyíték, AI döntés, policy figyelmeztetés és dedup kapcsolat kurátori nézetben. |
| `POST /api/admin/discovery-candidates/{id}/decision` | `approve|reject|suppress`, nem üres indok, választott policy ID | approve atomikusan létrehozza/hozzáköti a `site`-ot és az approved snapshotot; nem enqueue-olhat, ha URL/security kapu nem tiszta. |
| `POST /api/admin/snapshots/{id}/crawl` | csak idempotency key | csak jóváhagyott, érvényes planú snapshot enqueue-ja; 202 + server job ID. |
| `GET /api/admin/snapshots/{id}/quality` | — | teljes crawl/artefact/QA/release mátrix, nem csak átlagpont. |
| `POST /api/admin/snapshots/{id}/release-decision` | `release|hold|withdraw`, kötelező indok | `release` csak minden hard gate pass és kurátori jogosultság mellett 409-et ad eltérő esetben; publikus státuszt atomikusan állít. |
| `POST /api/admin/snapshots/{id}/retry` | explicit `crawl|qa`, indok, idempotency key | új run; hibás artifactot nem ír felül és nem töröl. |

Régi `/api/admin/ingest` vagy (a) megszűnik, vagy (b) csak `manual_candidate` létrehozására használható és ugyanazon URL-security + kurátori döntési folyamaton halad át. A ma meglévő „ingest = auto approve + crawl” viselkedés tiltott. Az OpenAPI és Pydantic modellek az itt leírt enumokat, hibaformátumot (`400` validation, `401/403` authz, `409` állapot/gate, `422` policy, `429` quota) pontosan tükrözik.

### 6. Threat modell és kötelező védelmek

| Veszély | Kötelező kontroll | Fail-closed eredmény |
|---|---|---|
| SSRF: localhost, RFC1918/CGNAT/link-local, IPv6 local, metadata endpoint, file/gopher/data URL | URL parser csak `http/https`; DNS feloldás A+AAAA-val minden redirect előtt; IP-k tiltólistája; eTLD+1/scope ellenőrzés; redirect-hop és port limit; crawler discovery és crawl külön egress gatewayen, amely connect-time is csak publikus IP-re enged | `security_rejected`, nincs worker task. |
| DNS rebinding / TOCTOU | a security resolver választ rögzíti a planben, az egress gateway újrafeloldáskor is ellenőriz; executor nem ér el Docker/host/cluster hálót, belső szolgáltatásokat, metadata IP-t | kapcsolat blokkolt, run `security_failed`, nincs retry automatikusan. |
| Nyílt redirect, domain-tévesztés, cross-host link | final URL minden hopnál validált; crawl only a jóváhagyott host/scope; externális link csak manifest `out_of_scope`, sosem követés | nem mentett oldal, számlált scope esemény. |
| Prompt injection / rosszindulatú oldal | fetched text adat, nem utasítás; statikus schema-output; bizonyíték-visszaellenőrzés; tool/secret nélküli, helyi LLM; output validáció | `uncertain`, kurátor elé kerül. |
| Cookie/login/paywall/404/soft-404 | explicit DOM/text/status detektor, seed és QA per-page ellenőrzés; a cookie kattintás whitelistelt selectorral, rögzített viselkedés-loggal | hard oldalfal vagy H0 hiba = QC hold; sosem autopublish. |
| Queue replay, verseny, worker crash | signed/versioned payload, DB state CAS, idempotency key, outbox/ack after commit, dead-letter és reconciler csak review-ba visszahelyezve | nincs duplázott release/crawl, látható `failed/hold`. |
| WACZ sérülés, objektumcsere vagy rossz Range-replay | ZIP/WACZ/WARC/CDXJ validáció, object version + SHA-256 metadata, MinIO visszaolvasási digest, immutable retention/versioning, Range-teszt | artifact invalid, nem köthető/kiadható. |
| jogosulatlan draft WACZ-hozzáférés | admin same-origin, rövid életű snapshot-scoped token vagy hitelesített Range request; audit; publikus WACZ csak released snapshot | 401/403/404, nincs object key kiszivárgás. |
| erőforrás- és költségkimerítés | per-provider/query/domain rate limit, per-job page/byte/time, worker concurrency, napi LLM és crawl budget, disk quota, circuit breaker | `partial/hold`, nem siker és nem csendes újrapróbálás. |

Nincs „belső hálózat tehát megbízható” kivétel. A külső Nginx által adott `X-Forwarded-*` csak a dokumentált Nginx CIDR-ből érkező kapcsolatnál fogadható el; minden más kliens headerét a backend eldobja. Titok csak secret managerben vagy deployment `.env`-ben; a jelenlegi Compose-be írt adatbázis/MinIO/JWT értékek nem maradhatnak production mintákban.

### 7. H0/H1/H2 crawl-szerződés és manifest

`H0` a jóváhagyott final seed URL. `H1` kizárólag H0-ból, `H2` kizárólag H1-ből elért, a `CrawlPlan` host/path/MIME/robots szabálya szerint engedett URL. H3 és minden külső domain tiltott. URL-kanonizálás (scheme/host case, fragment elhagyás, default port, követett canonical/final URL) a dedup előtt történik, de az eredeti URL is auditált. A Browsertrix `--depth 2`, `--scopeType host`, `--pageLimit`, `--sizeLimit`, `--timeLimit`, `--generateWACZ`, text és screenshot kötelező minimum; az executor tényleges parancsát és az image digestet manifestbe kell írni.

A `crawl_manifest.json` kötelezően tartalmazza a terv teljes hash-ét, seed állapotát, a `limit_reached` okokat, és minden megfigyelt URL-nél a fenti `crawl_pages` mezőket. Ha az aktuális Browsertrix `pages.jsonl` nem ad biztonsággal hop/parent/capture ok adatot, az executor adapternek kell azt előállítania; enélkül a run **nem** minősíthető teljesnek. A manifest és logok maga is artifactként hash-elve MinIO-ba kerülnek.

Lefedettségi szabály: H0 tényleges 2xx/engedélyezett content must; minden security/scope szerint jogosult, crawl során felfedezett H1/H2 URL-hez van `captured`, dokumentált `robots_denied`, `policy_excluded`, vagy dokumentált explicit hiba rekord. Time/page/size limit, hiányzó `pages.jsonl`, ismeretlen H0 státusz, H0 4xx/5xx, vagy nem magyarázott jogosult URL `crawl_incomplete`: csak QA-review, automatikus kiadás soha. Ha egyetlen jogosult H1/H2 sem létezett, ezt a manifest bizonyítja (`eligible_count=0`), ez nem hamis hiba.

### 8. Artifact és replay-QC release gate

**G0 — crawl bemenet és teljesség.** Jóváhagyott plan, H0 valid, security guard pass, manifest teljes. Részleges/limitált crawl `review_required`.

**G1 — WACZ szerkezeti és tárolási integritás.** A staging fájl SHA-256, méret és ZIP CRC érvényes; kötelező WACZ adatcsomag és index/WARC tagok olvashatók; minden CDXJ indexrekord egy létező, olvasható WARC válaszra mutat. Feltöltés után a MinIO `HEAD` metadata/version-id és a friss `GET` stream SHA-256 pontosan egyezik a staging digesttel. A hash és validation report a snapshothoz és a PREMIS eseményhez kötött. Akár egy eltérés hard fail: törlés helyett quarantine/immutable audit objektum, nincs QA/release.

**G2 — tényleges replay.** Az ellenőrzött, MinIO-ból visszaolvasott WACZ kerül izolált ReplayWeb/pywb környezetbe; H0 és a determinisztikusan kiválasztott reprezentatív H1/H2 HTML-oldalak renderelnek. Kötelező screenshot, DOM/text kinyerés, konzol/network hibalista és Range-request bizonyíték. QA URL-választás legalább H0 + minden H1/H2, ha számuk a `QA_MAX_PAGES` alatt van; fölötte H0 + rétegenként determinisztikus hash-minta + minden kritikus URL, a kihagyott URL-ek indokoltan `not_sampled`. Hiányzó QA sor nem nullával átlagolandó: `QA_INCOMPLETE`.

**G3 — Browsertrix live összevetés és wall/resource jelek.** A Browsertrix QA minden kiválasztott oldalon rögzíti screenshot/text match, `crawlGood/crawlBad/replayGood/replayBad`. Automatikus kiadáshoz minden érték jelen van, `replayBad=0`, nincs kritikus console/network hiba, nincs 4xx/5xx/soft-404, cookie/login/paywall/empty-page detektor, és az összes mintázott oldalon a policyben deklarált küszöb teljesül. A globális átlag soha nem fedhet el egy hibás oldalt. A live oldal változása történeti drift lehet: alacsony live match önmagában nem mondja, hogy a WACZ sérült, de `review_required`; csak a G1/G2 igazolja a mentés integritását.

**G4 — kiadási döntés.** Hard gate hiba nem felülbírálható automatikus kiadásra. Csak minden G0–G3 tiszta pass és egy kurátori `release` döntés esetén mehet `published`; a `release_decisions.gate_matrix_hash` pontosan az auditált eredményre mutat. Kivételes emberi felülbírálás kizárólag nem-integritási, drift/alacsony-lefedettségi esetben, két személyes (kurátor + admin) indoklással, és mindig manuálisan jelölt publikációval engedhető. Új domain első snapshotja kötelezően ezen a két személyes review-n megy át, pontszámtól függetlenül.

### 9. Compose, konfiguráció és Nginx interfészhatár

Az ARCH-01 Compose célállapotban külön `api`, `discovery-worker`, `crawl-executor`, `qa-executor`, `postgres`, `redis`, `minio` szolgáltatás van. Az API és worker ugyanazt a verziózott alkalmazási csomagot használhatja, de a Browsertrix executor image és jogosultsága külön. A `fewa-automation` nem sibling pathként importálódik; telepített csomag vagy expliciten build-contextbe vett, tesztelt artifact. `postgres`, `redis`, `minio`, API és executor admin portjai belső hálózaton maradnak; production host port csak a külön Nginx felől indokolt API/public frontend belépés. A crawler/QA egress networkben elkülönített, DNS- és connect-policyt végrehajtó gateway van. Compose test környezetben ugyanez a topológia, pinned image digestekkel és fixture webhellyel áll fel.

Konfigurációnevek egyetlen `Settings` szerződésből erednek (`POSTGRES_SERVER`, nem `POSTGRES_HOST`; `MINIO_BUCKET_WACZ`, nem `MINIO_BUCKET_NAME`; `SECRET_KEY`, nem `JWT_SECRET_KEY`, vagy dokumentált kompatibilis alias). Startup health endpoint komponensenként valódi DB/Redis/MinIO/queue/AI readiness-t ad; nincs hamis „Ollama OK”. Productionban hiányzó/gyenge secret, bucket versioning/object-lock, egress policy vagy executor image digest startup-fail.

A külső Nginx-től FEWA a következő minimális szerződést várja, de nem birtokolja a konfigurációját:

| Felület | Nginx kötelesség | FEWA kötelesség |
|---|---|---|
| `/api/*` | TLS-terminálás, ismert proxy CIDR, request-id továbbadás, ésszerű body/rate limit, `X-Forwarded-Proto/For/Host` sanitizálás | csak trusted-proxy header elfogadás, origin/host validáció, authz/audit. |
| publikus és admin WACZ Range | `Range`, `If-Range`, `Content-Range`, `Accept-Ranges`, `Content-Length` változatlan továbbítása; buffering/compression kikapcsolása erre az útra; auth/egyedi Range válasz nem shared-cache | snapshot jogosultság, `206/416` korrekt streaming, object-key elrejtése, rövid token vagy session ellenőrzése. |
| hiba és redirect | backend hibakód/redirect nem írható felül login page-re vagy 200-ra | nincs közvetlen MinIO URL kiadás, biztonságos relatív public URL-ek. |

Az Nginx konfigurációt a későbbi deploy reviewer szolgáltatja, de e szerződéshez egy black-box contract teszt kötelező. Nincs FEWA-beli `/api/proxy` végpont, és a Nginx nem használható crawler egress proxyként külön security review nélkül.

### 10. Acceptance mátrix (builder csak ezzel késznek tekintheti)

1. **Discovery pozitív:** kontrollált kereső fixture + Fejér landing page → `discovery_candidate` bizonyítékokkal, model/prompt/cache adatával; kurátor elfogadás után és csak utána keletkezik snapshot/crawl job.
2. **Discovery negatív és prompt injection:** nem Fejér oldal, illetve „ignore previous instructions” tartalmú oldal → `rejected` vagy `uncertain`; nincs crawl/publish és nincs AI eszközhívás.
3. **URL security:** `localhost`, 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, IPv6 loopback/ULA/link-local, metadata, tiltott scheme/port, redirect és DNS-rebinding fixture mind blokkolt; executor hálózati teszt igazolja, hogy a blokkolt célhoz nem létesült kapcsolat.
4. **Hopp és scope:** kontrollált site H0→H1→H2→H3 + externális linkkel: manifest minden sort helyes hop/parenttel rögzít, H3/external nincs capture-ben; H1/H2 teljesen le van fedve vagy indokolt. Régi `depth=3..5` policy nem fut.
5. **Partial crawl:** page/time/size limit és hiányzó `pages.jsonl` → `crawl_incomplete/review_required`, semmilyen pontszám nem publikálhatja.
6. **Artifact:** érvényes WACZ pass; sérült ZIP, hiányzó/hibás WARC/CDXJ, MinIO utólagos byte-csere vagy visszaolvasási SHA-eltérés → hard fail/quarantine, publikus route 404/403.
7. **Replay QC:** minőségi fixture WACZ H0/H1/H2 render + Range bizonyítékkal pass; egy missing QA sor, `replayBad>0`, 404, cookie/login/empty wall, console resource hiba, hiányzó screenshot/text → review/hard fail szerint, sosem átlagolódik el.
8. **Drift:** live tartalom módosulása alacsony Browsertrix match-et okoz, de G1/G2 pass mellett `review_required`, nem „artifact corrupt”; kurátori döntés auditált.
9. **Állapot/idempotencia:** ugyanazon approve/crawl/retry/release kérés ismétlése és worker crash/restart nem hoz létre két active runt, két artifactot vagy két publikációt; Redis kiesés után a DB reconciler látható holdba tesz.
10. **Proxy contract:** külön Nginx black-box teszten a hitelesített admin draft WACZ nem elérhető, released WACZ Range `206`-tal visszajátszható, és a forwarding nem sérti az auth/headers szerződést.
11. **Reprodukálhatóság:** `docker compose -f docker-compose.test.yml up --build --abort-on-container-exit` egy tiszta hoston felhozza az API+mindhárom worker+Postgres/Redis/MinIO stack-et; egység, integráció, security és teljes regresszió zöld, az image/model/prompt verziók rögzítve.

Kötelező futási bizonyíték a fenti tesztek kimenete mellett: egy kontrollált, saját tesztwebhely end-to-end futás és egy jogszerűen kijelölt Fejér vármegyei pilot discovery → két-hop → WACZ → visszaolvasás → replay QA → kurátori hold/release útvonala. Külső valós oldalra crawl csak dokumentált jogalappal/robots policyvel.

### 11. Out of scope (ARCH-01-ben tiltott feltételezés)

- Nginx/DNS/TLS/éles deploy vagy titokmódosítás végrehajtása; ezek emberi jóváhagyásos infrastruktúra-feladatok.
- Teljes országos web indexelése, korlátlan kereső scraping, social media, belépést igénylő/paywalled terület, CAPTCHA-megkerülés.
- Mélyebb mint H2 crawl, cross-domain követés, tetszőleges kliens URL automatikus mentése.
- AI-alapú automatikus kurátori vagy publikációs döntés, külső LLM adatküldés külön jóváhagyás nélkül.
- RAG, összefoglaló, embedding hibáinak javítása, kivéve a discovery decisionhez szükséges valódi, izolált LLM adaptert; a jelenlegi mock RAG/embedding nem használható release-bizonyítéknak.
- Régi archívumok tömeges migrálása vagy újraminősítése; ehhez külön adatjavítási és megőrzési terv kell.

### 12. Kötelező GPT pre-QA és Sonnet-review inputlista

**Builder előtti GPT pre-QA kérdések:** (1) minden API állapotváltás megfelel-e a migration triggerének és idempotens-e; (2) van-e bármely SSRF/DNS rebind/redirect út, amely executorhoz ér; (3) a manifestből kétséget kizáróan megállapítható-e a hop és a kimaradás oka; (4) hiányzó QA adat vagy limit eljuthat-e `published`-ig; (5) WACZ SHA tényleg friss MinIO GET-ből származik-e; (6) a live drift és artifact-corruption külön van-e választva; (7) AI output bizonyítéka validálható-e az inputhoz; (8) a Nginx külső határból nem lett-e rejtett belső proxy/secret függőség.

**Sonnetnek release candidate-nál pontosan átadandó:**

1. ARCH-01 ezen bejegyzése, a jóváhagyott migration/ADR és az OpenAPI diff.
2. Teljes `git diff`, külön a lifecycle/release SQL trigger, security resolver/egress, crawl plan/manifest, WACZ validator, MinIO visszaolvasás, QA gate és Nginx contract teszt része.
3. A Compose és Dockerfile diff, image digestek, `.env.example` név-mátrix, valamint bizonyíték arra, hogy nincs Docker socket/sibling import/nyitott belső port.
4. A 11 acceptance teszt parancsa, nyers kimenete, coverage és a kontrollált end-to-end artifact hash/manifest/QA reportja.
5. Egy negatív SSRF/rebinding, egy sérült WACZ, egy `replayBad`, egy hiányos QA, és egy live-drift eset bizonyítéka, valamint az eredményül kapott DB állapot.
6. A kurátori UI/API jogosultság- és audit-diff, release override szabály, valamint a pilot jogalap/robots döntésének redaktált bizonyítéka.
7. Nyitott kockázatok és minden tudatos eltérés e specifikációtól. Sonnet verdict csak `ELFOGADVA` vagy tételes `JAVÍTÁS KÉRVE`; általános „looks good” nem elég.

FUTTATÁS: `wc -l .agents/agents.md COLLAB_GEMINI.md && sed -n '1,240p' .agents/agents.md && sed -n '1,260p' COLLAB_GEMINI.md` → a szerepkör-, append-only és IT-lens release-gate szerződés teljes elolvasása; `rg -n "..." fewa-v3-backend fewa-automation docker-compose*.yml compose*.yml` → a meglévő discovery, Browsertrix, QA, worker és Compose hiányok célzott auditja; `git status --short` → meglévő user/agent módosítások érintetlenek.
VERDICT / KÖVETKEZŐ CÍMZETT: GPT pre-QA — a builder csak a 12. szakasz nyolc kérdésének tételes, `ELFOGADVA` vagy `JAVÍTÁS KÉRVE` válasza után bonthatja kis implementációs egységekre; minden egység után független GPT QA, majd a felsorolt bemenettel Sonnet gate következik. Éles deploy/Nginx/secret módosítás nem autorizált ebben a scope-ban.

## [2026-08-13 09:19 UTC] Sonnet 5 — ARCH-01 / scope integrity és security review

MODEL=Sonnet 5; REASONING=high (dedikált review-alfolyamattal: teljes spec elolvasása, majd célzott kódellenőrzés a jelenlegi `fewa-v3-backend`/`fewa-automation`/Compose ellen, saját grep/git-alapú reprodukcióval, nem a spec állításainak elfogadásával)

ÁLLAPOT: JAVÍTÁS KÉRVE

ÉRINTETT FÁJLOK: nincs production-kód módosítás (csak olvasás). A review a `COLLAB_GEMINI.md` P0/ARCH-01 szakaszát (1-286. sor az olvasás idején) értékelte a következő fájlok ellen: `fewa-automation/discovery.py`, `fewa-automation/crawler.py`, `fewa-v3-backend/app/workers/arq_worker.py`, `fewa-v3-backend/app/crud/archive.py`, `fewa-v3-backend/app/core/config.py`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `fewa-v3-backend/app/pipeline/embedding.py`, `app/pipeline/summarization.py`, `app/services/rag_service.py`, `spec/schema.sql`.

**1. Az öt "Jelenlegi auditból ismert blokkoló" állítás — mind megerősítve, saját kódolvasással.**

- Discovery ma valóban csak query-builder + regex helyi-egyezés (`fewa-automation/discovery.py`), sehol nem hívja backend kód (`grep` nulla találat) — a tényleges jelölt-létrehozás kizárólag manuális admin ingest (`app/api/v1/jobs.py`, `app/crud/archive.py:46-103`).
- Compose-ból nemcsak a Browsertrix executor, hanem maga a worker service is hiányzik — `arq_worker.py` `WorkerSettings`-e ma nem fut ebben a topológiában; a Dockerfile build contextje kizárja a `fewa-automation` sibling-t, miközben `arq_worker.py` `sys.path.insert`-tel importálja azt — csak konténeren kívül, repo gyökérből futtatva működik.
- Env-név eltérés saját magam is megerősítve: `config.py` `POSTGRES_SERVER`/`MINIO_BUCKET_WACZ`/`SECRET_KEY` vs. mindkét Compose fájl `POSTGRES_HOST`/`MINIO_BUCKET_NAME`/`JWT_SECRET_KEY` — mivel a Settings case-sensitive és `extra="ignore"`, a konténerizált backend csendben a dev-default értékekre esik vissza. `.env.example` viszont helyesen van elnevezve — kizárólag a két Compose-fájl hibás, tehát ez élő, ma is fennálló hiba, nem elavult megfigyelés.
- QC-átlagolás saját magam is megerősítve nem fail-closed: `record_qc_result()` (`app/crud/archive.py:253-289`) `qc_score >= auto_accept_threshold` esetén **automatikusan, emberi döntés nélkül** `archived → indexed → published`-ig viszi a snapshotot. Ezt magam is elolvastam — a docstring explicit ezt írja: "no second human gate needed for a passing score". A `replayBad`/`crawlBad` per-oldal adat (`crawler.py` `_parse_qa_log`) el van tárolva a `qc_detail`-ben, de sosem olvassa vissza semmi a `qc_score` számításához vagy egy gate-hez.
- RAG/embedding/summarization ma valóban nem valódi AI: `embedding.py` `hash(text)` → `sin()`, `summarization.py` fix f-string sablon, `rag_service.py` saját docstringje szerint is "hardcoded keyword-match simulation, not real AI".

**Git-evidencia:** a legutóbbi 4 releváns commit (`91acc50`, `dbcd566`, `9862ac2`, `8757c3a`) UI/audit-plumbingot érint, nem az auto-publish triggert, QC-matekot, discoveryt vagy Compose/env configot — a blokkoló-lista nem elavult. **De** a `91acc50` commit üzenete saját maga írja le, hogy már létezik egy **második**, élő, egy-kurátoros bypass is: `decide_quality_review()` (`app/crud/archive.py:304-`), amivel egyetlen kurátor bármely küszöb-alatti `archived` snapshotot közvetlenül `indexed`-re (majd onnan publikálásra) tud vinni, integritási hiba és tartalmi drift megkülönböztetése nélkül. Ezt magam is elolvastam a kódban — valós, ma élő második automatikus/egyszemélyes bypass, amit a spec blokkoló-listája nem nevez meg.

**2. Threat-modell kritika — 3 valódi GAP, kettő részleges, egy solid.**

- **SSRF/DNS rebinding — GAP.** A 216. sor pontos idézete (saját magam is ellenőriztem a fájlban): "a security resolver választ rögzíti a planben, **az egress gateway újrafeloldáskor is ellenőriz**". Szó szerint olvasva ez azt írja le, hogy a gateway a connect pillanatában **saját maga újra feloldja** a hostnevet — ez pont az a TOCTOU-ablak, amit a DNS rebinding kihasznál (a támadó domain a terv-készítéskor publikus IP-t, a tényleges connectkor belső IP-t ad vissza). A spec sosem mondja ki az egyetlen dolgot, ami ezt tényleg lezárná: a terv-készítéskor validált **egyetlen IP-t kell pinnelni**, és minden downstream kapcsolatnak közvetlenül azt kell hívnia (Host/SNI a hostnévről), a hostnevet a connect pillanatában soha nem újra-feloldva. Ez ugyanaz a minta, amit az IT Lens SCAN-01 review-ban korábban kényszerítettem ki (`validate_target_domain` + pinned_ip minden collectorban) — ott ez explicit kötelezettség volt, itt a spec szövege ambiguus, és a szó szerinti olvasat épp a rossz mintát írja le.
- **Autopublish-ellenállás — GAP.** A spec prózában kimondja, hogy a jelenlegi `record_qc_result()` auto-publish és a jelenlegi `/api/admin/ingest` "auto-approve+crawl" tiltandó, de a 10. szakasz 11 acceptance-tétele közül egy sem teszteli explicit, hogy a **régi** auto-publish útvonal ténylegesen elérhetetlenné vált — csak azt, hogy az új gated útvonal létezik. Mivel mindkét élő bypass (a 96-pontos auto-accept ÉS az egyszemélyes `decide_quality_review`) ma is a kódban van, egy implementáció elméletileg az összes 11 acceptance-tételt teljesítheti úgy, hogy az új G0–G4/release-decision gépezetet a régi utak **mellé**, nem helyette építi be.
- **Nginx trusted-proxy határ — GAP.** A CIDR-lista forrása (config mező vs. hardcode vs. csak dokumentáció) sehol nincs megnevezve, és nincs induláskori ellenőrzés túl tág tartományra (pl. `0.0.0.0/0`) — miközben a spec explicit kimondja "nincs 'belső hálózat tehát megbízható' kivétel" pont erre a határra.
- **Idempotencia/replay-race — RÉSZLEGES GAP.** A `crawl`/`retry` végpontok konkrét idempotency key-t kapnak, de a valódi hard-to-reverse művelet, a `release-decision`, nem — a táblázatban nincs idempotency key mező hozzá, holott ugyanabban a táblázatban a másik kettőnél igen. "Outbox/ack after commit" néven szerepel, de nincs hozzá konkrét entitás a 4. szakasz adatmodelljében.
- **AI-budget kimerülés vs. valódi bizonytalanság — RÉSZLEGES GAP.** Run-szinten (`discovery_runs.status=partial`) helyesen kezelt, de candidate-szinten, ahol a kurátor ténylegesen dolgozik (`GET /discovery-candidates?state=`), a `decision_source`/`reason_code` értékkészlete nincs felsorolva — egy rendszerszintű AI-kiesés így simán belesimulhat egy "normál batch néhány bizonytalan esettel" képbe, hacsak a kurátor külön nem keresztellenőrzi a run-szintű `partial` jelzőt.
- **Artifact-integritás (MinIO post-upload tamper) — SOLID** a tétel explicit szerepel a 10. szakasz 6. pontjában.
- **Fail-closed QC/partial crawl a spec szövegén belül — SOLID**, nincs numerikus fallback-kel ellentmondó szövegrész.

**3. Belső konzisztencia — 1 valódi rés.** A 4. szakasz a meglévő `lifecycle_status` mezőt (és annak DB-szintű `trg_lifecycle_guard` triggerét, `spec/schema.sql` — ami ma engedi `indexed → published`-et feltétel nélkül) megtartja az új `release_state` mellett, de nem mondja ki, hogy a régi trigger átmenet-gráfját is szigorítani kell (pl. `indexed→published` csak akkor, ha létezik egy `release_decisions.released=true` sor). Enélkül a két gate egymás mellett létezik, és kizárólag az alkalmazáskód fegyelmén múlik, hogy a DB által ma is engedett régi élt senki ne hívja — pont az a minta, amit ez a teljes spec ki akar zárni. Emellett egy apró, egy mondattal tisztázható kétértelműség a "Kötelező eredmény" "valódi AI-szolgáltatás" kifejezése és a 11. szakasz RAG/embedding kizárása között.

**Kért konkrét spec-szöveg javítás (nem implementáció):**

1. §6 DNS rebinding sor: "újrafeloldáskor is ellenőriz" helyett explicit pin-and-connect-by-IP követelmény — a security resolver egyetlen validált IP-je legyen a tényleges socket-connect cél minden requesthez a terv teljes életében; az egress gateway soha ne végezzen saját, független hostname-feloldást connectkor.
2. §10: explicit negatív acceptance teszt arra, hogy a `record_qc_result()` auto-accept ág és a `decide_quality_review(accept=true)` egyszemélyes bypass a régi útvonalon többé nem érhet el `published`-t az új G0–G4/kétszemélyes-override útvonalon kívül.
3. §5: `release-decision` végpont kapjon kötelező idempotency key mezőt, a `crawl`/`retry` mintájára.
4. §4: mondja ki explicit, hogy a régi `lifecycle_status`/`trg_lifecycle_guard` DB-szintű átmenet-gráfja is szigorodik, nem csak app-kód szinten változik a viselkedés.
5. §9: nevezze meg a trusted-proxy CIDR-lista konkrét forrását (config mező), és követeljen induláskori ellenőrzést túl tág tartomány ellen.
6. §10: acceptance tétel a G4 kétszemélyes override szabályára és az új-domain kötelező kettős reviewra — jelenleg egyik gate-hez sincs teszt rendelve.
7. §3/§4: sorolja fel a `decision_source`/`reason_code` értékkészletet, hogy a budget-kimerülés miatti `uncertain` candidate-szinten is megkülönböztethető legyen a valódi tartalmi bizonytalanságtól.
8. Egy egyértelműsítő mondat: "valódi AI-szolgáltatás" kizárólag az izolált discovery LLM adapterre vonatkozik, nem a meglévő RAG/embedding/summarization stackre.

Egyik pont sem igényel production-kód módosítást — mind spec-szöveg pontosítás/kiegészítés. A dokumentum egyébként jól strukturált és nagyrészt koherens; nem újraírást, hanem célzott kiegészítést igényel.

FUTTATÁS: `grep -n "újrafeloldáskor is ellenőriz" COLLAB_GEMINI.md` → 216. sor, szó szerint megerősítve; `grep -n "auto_accept_threshold|def record_qc_result" -A 25 fewa-v3-backend/app/crud/archive.py` → auto-publish ág megerősítve; `grep -n "def decide_quality_review" -A 20 fewa-v3-backend/app/crud/archive.py` → egyszemélyes override megerősítve; a fenti öt blokkoló-állítás mindegyikét saját `grep`/fájlolvasással is visszaellenőriztem, nem csak a review-alfolyamat jelentésére hagyatkozva.

VERDICT / KÖVETKEZŐ CÍMZETT: GPT pre-QA / Architect — a fenti 8 pont szöveges javítása szükséges a spec-ben, utána Sonnet 5-nek rövid, célzott re-review-t kell kapnia kizárólag a módosított szakaszokra (nem a teljes dokumentum újraolvasására). Builder implementációt csak ez után kezdhet. Production kód, deploy, Nginx vagy titok e review során nem módosult.

## [2026-08-13 09:22 UTC] GPT PRE-QA — ARCH-01 / builder előtti adversarial scope- és kódillesztés

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT: JAVÍTÁS KÉRVE

ÉRINTETT FÁJLOK: production kód nem változott; ez a bejegyzés kizárólag a
`COLLAB_GEMINI.md` végére került. Teljesen elolvasva: `.agents/agents.md`,
`COLLAB_GEMINI.md`, `docs/STATUS.md`. Tételesen auditálva:
`spec/schema.sql`, `spec/migrations/001_add_qc_detail.sql`,
`spec/migrations/002_add_seed_url_to_published_view.sql`,
`spec/pipeline_schemas.py`, `spec/openapi.yaml`, `fewa-automation/discovery.py`,
`fewa-automation/crawler.py`, `fewa-automation/quality_index.py`,
`fewa-automation/tests/test_discovery.py`, `fewa-automation/tests/test_crawler.py`,
`fewa-v3-backend/app/api/v1/jobs.py`, `fewa-v3-backend/app/core/security.py`,
`fewa-v3-backend/app/core/config.py`, `fewa-v3-backend/app/core/minio_client.py`,
`fewa-v3-backend/app/crud/archive.py`,
`fewa-v3-backend/app/workers/arq_worker.py`, az érintett backend tesztek,
`fewa-v3-backend/Dockerfile`, `docker-compose.yml`, `docker-compose.test.yml`
és `.env.example`.

**Sonnet-handoff átvétele:** a közvetlenül előző,
`[2026-08-13 09:19 UTC] Sonnet 5 — ARCH-01 / scope integrity és security review`
blokk verdictje `JAVÍTÁS KÉRVE`. A következő teendő az Architect célzott
spec-korrekciója a Sonnet 8 pontjára és az alábbi pre-QA blokkolókra; builder
nem indulhat, utána ugyanennek a Sonnet gate-nek rövid re-review-ja szükséges.

### A nyolc kötelező pre-QA kérdés eredménye

1. **Életciklus/trigger/idempotencia — NEM megfelelő.** A cél-spec egyszerre
   használ új candidate-state-eket, snapshot lifecycle-ot és `release_state`-et,
   de nem ad három külön, teljes enumot és tranzíciós mátrixot. A jelenlegi DB
   trigger továbbra is feltétel nélkül engedi az `indexed → published` élt
   (`spec/schema.sql:669-706`), a trigger által írt esemény `triggered_by` mezője
   mindig NULL, miközben az API minden approve/release jellegű hívásban ténylegesen
   `user_id=None`-t ad (`jobs.py:80,119,168-170`). A `record_qc_result()` ma
   automatikusan publikál, a `decide_quality_review(accept=true)` pedig egyetlen
   kurátori hívással publikál. A migrationnek DB-szinten kell megtiltania minden
   legacy publish élt érvényes, hashhez kötött release record nélkül; az outbox,
   release-idempotency kulcs, CAS és visszagörgetési stratégia jelenleg nincs
   egzakt módon specifikálva.
2. **SSRF/DNS rebinding/redirect — VAN elérhető út.** `HttpUrl` után a seed
   változatlanul jut a `docker run ... browsertrix-crawler --url` parancsba
   (`jobs.py:53-94`, `arq_worker.py:74-81`, `crawler.py:122-145`). Nincs A+AAAA,
   CNAME-, port-, redirect- vagy connect-time IP-ellenőrzés, és nincs egress
   gateway. A `scopeType=host` nem seed-SSRF kontroll. A Sonnet által kért
   pin-and-connect-by-IP szerződés mellett azt is normatívan rögzíteni kell, hogy
   **minden** Chromium subresource, redirect és discovery-inspection kapcsolat
   csak a gatewayen át mehet; a konténernek nincs közvetlen route-ja host/Compose/
   cluster/metadata hálóhoz. Kötelező edge-ek: vegyes public+private DNS-válasz,
   CNAME-lánc, TTL-váltás, IPv4-mapped IPv6, alternatív numerikus IP-formák,
   userinfo, nem default port és redirect publicból private-ba.
3. **H0/H1/H2 manifest-bizonyíthatóság — NEM megfelelő.** A repo valódi
   `crawl-output-sample/.../pages.jsonl` mintája ad `depth` mezőt, de nem ad
   `parent_url`-t; csak capture-ölt oldalakat tartalmaz, ezért a felfedezett, de
   kimaradt jogosult URL-ek teljes halmaza és kihagyási oka nem vezethető le belőle.
   Ugyanaz a H0 a mintában kétszer is szerepel, tehát aggregáció nélkül a tervezett
   `(canonical_url, hop)` uniqueness is sérül. A specnek meg kell neveznie a
   verziózott, normatív edge/discovery eseményforrást (vagy külön instrumentált
   BFS adaptert), a canonical/final URL összevonását és azt, hogyan bizonyítja az
   `eligible_count=0` állítást. Pusztán `pages.jsonl`-ből a leírt manifest nem
   megvalósítható.
4. **Hiányos QA vagy limit eljuthat-e publishig — IGEN.** Az uncommitted crawler
   diff a Browsertrix 14/15 size/time limit exitet `success=True`-nak minősíti
   (`crawler.py:27-35,152-160`), majd a worker rendes QA-ra küldi. A hiányzó
   H0-státusz (`None`) szintén továbbmegy (`arq_worker.py:122-157`). QA-ban a
   hiányzó screenshot/text mezők egyszerűen kiesnek az átlagból, a kiválasztandó
   URL-ekhez nincs expected-set összevetés, és a már parse-olt `replayBad`/
   `crawlBad` értéket a gate nem olvassa (`arq_worker.py:204-229`). Egy jó átlag
   ma `archived → indexed → published`. A limitált WACZ megőrizhető bizonyítékként,
   de a run eredménye kötelezően `partial/review_required`, nem `success`.
5. **MinIO-friss GET hash — NEM.** `upload_wacz_stream()` csak a staging streamet
   hash-eli a PUT előtt, GET-visszaolvasás, ZIP/WACZ/WARC/CDXJ validáció, object
   version és quarantine nélkül (`minio_client.py:37-69`). További konkrét hiba:
   a kliens `filesize_bytes` kulcsot ad vissza, a worker viszont `upload_info.get("size")`-
   t ír DB-be (`arq_worker.py:94-104`), ezért a méret NULL lehet. A fix snapshot
   object key overwrite-olható, bucket versioning/object-lock nincs kikényszerítve.
6. **Live drift és artifact corruption — NINCS szétválasztva.** A Browsertrix QA
   élő újracrawl-összevetését használja egyetlen minőségforrásként; nincs előtte
   független G1 validáció és ellenőrzött MinIO GET-ből izolált G2 replay. Így
   artifact-sérülés, replay-hiba és történeti drift külön verdictje nem bizonyítható.
7. **Discovery/AI evidence — NEM bizonyítható.** A `discovery.py` csak query-builder
   és regex, nincs provider, inspection worker vagy LLM hívás. A cél-spec idézet-
   ellenőrzést ír, de tartósan csak kis kivonat/hash megőrzését követeli; auditkor
   az exact modell-input nélkül az idézet, Unicode-normalizálás és truncation nem
   reprodukálható. Kötelező legyen az exact normalizált inference-input immutable
   artifactja vagy visszaellenőrizhető span+artifact hash, `input_sha256`,
   `prompt_sha256`, source spanok, schema-validator verzió; candidate reason enum
   különítse el `budget_exhausted/provider_failed/model_failed/content_uncertain`-
   t. Az evidence csak az exact inputból származó span lehet.
8. **Nginx-határ — RÉSZBEN megfelelő.** A crawler egress nem lett rejtetten
   Nginxre bízva, viszont a trusted proxy CIDR konfiguráció és túl tág CIDR
   startup-tiltás hiányzik. A proxy contract tesztnek külső black-box tesztnek
   kell maradnia; ez nem helyettesítheti az executor egress kontrollját.

### További builder-ready blokkolók

- `docs/STATUS.md` TILTOTT listája lezárja többek között a `spec/schema.sql`,
  `spec/openapi.yaml`, `spec/pipeline_schemas.py`, `config.py`, `minio_client.py`,
  `security.py`, `jobs.py`, `arq_worker.py`, mindkét Compose és a releváns tesztek
  fájljait. Az Architect átadása ugyanakkor ezek közül többet kijelöl módosításra.
  Az `.agents/agents.md` alapján a Backend ezeket explicit újranyitás nélkül nem
  módosíthatja. Az Architectnek a pontos ARCH-01 fájlokat újra kell nyitnia egy
  auditált STATUS/ADR döntéssel; `spec/schema.sql` újraírása helyett migration kell.
- A releváns integrációs fájlok már most uncommitted munkát tartalmaznak:
  `fewa-automation/crawler.py`, `fewa-automation/tests/test_crawler.py`,
  `fewa-v3-backend/app/api/v1/jobs.py`, `app/core/minio_client.py`,
  `app/crud/archive.py`, `app/workers/arq_worker.py`, valamint
  `tests/test_archive_crud.py`, `tests/test_arq_worker.py`, `tests/test_jobs_api.py`.
  Ezeket más builder nem veheti át addig, amíg a jelenlegi tulajdonos nem ad
  explicit checkpoint/handoffot; a diffet felülírni vagy félbemergelni tilos.
- A Compose csak `spec/schema.sql`-t mountolja initkor, ezért egy önmagában álló
  `005_arch_01_pipeline.sql` sem tiszta DB-n, sem létező volume-on nem fut le.
  Kötelező verziózott migration runner és fresh/upgrade bizonyíték.
- Az executor-modell nincs végrehajthatóan eldöntve: a jelenlegi wrapper Docker
  CLI-t hív, miközben a backend image-ben nincs Docker CLI, nincs sibling
  `fewa-automation`, Compose-worker sincs; Docker socket pedig helyesen tiltott.
  A spec nevezze meg, hogy a queue consumer a digest-pinnelt Browsertrix runtime-ot
  saját konténerén belüli CLI-ként indítja, jobonként izolált workdirrel és közvetlen
  Docker/host hozzáférés nélkül. Enélkül a builder kénytelen architektúrát kitalálni.

### Prioritásos, egymást nem átfedő build-slice terv (maximum 3)

**S1 — állapotgép és gépi szerződés (első; tiszta/új fájlok, explicit újranyitás
után).** Fájltulajdon: `docs/adr/0002-arch-01-release-state-machine.md` (új),
`spec/migrations/005_arch_01_pipeline.sql` (új), `spec/pipeline_schemas.py`,
`spec/openapi.yaml`, `fewa-v3-backend/tests/test_arch01_migration.py` (új),
`fewa-v3-backend/tests/test_arch01_contract.py` (új). Kötelező acceptance:
fresh DB + 004-ről upgrade; régi `indexed→published`, `record_qc_result` és
egyszemélyes review bypass DB-szinten elutasítva; user nélküli curation tiltva;
approve/crawl/retry/release ismétlés idempotens; invalid 3..5 depth hold; új domain
két személyes gate; lifecycle+release+audit ugyanabban a tranzakcióban; migration
runner mind fresh Compose-on, mind meglévő volume-on igazolt.

**S2 — izolált discovery/security/executor/gate könyvtár (csak új fájlok; S1
sémáira épít).** Fájltulajdon: `fewa-automation/url_security.py` (új),
`fewa-automation/search_provider.py` (új), `fewa-automation/discovery_llm.py` (új),
`fewa-automation/discovery_worker.py` (új), `fewa-automation/crawl_manifest.py` (új),
`fewa-automation/wacz_integrity.py` (új), `fewa-automation/qa_gate.py` (új),
`fewa-automation/executor.py` (új), `fewa-automation/Dockerfile.executor` (új),
`fewa-automation/tests/test_url_security.py` (új),
`fewa-automation/tests/test_discovery_worker.py` (új),
`fewa-automation/tests/test_crawl_manifest.py` (új),
`fewa-automation/tests/test_wacz_integrity.py` (új),
`fewa-automation/tests/test_qa_gate.py` (új). Kötelező acceptance: kontrollált
provider+inspection+LLM provenance és prompt-injection/budget/provider/model
negatív eset; az összes IPv4/IPv6/redirect/mixed-DNS/CNAME/rebind fixture packet-
szinten nulla tiltott connecttel; H0→H1→H2→H3+external manifest helyes
hop/parent/eligible/skip rekordokkal; 14/15 limit és hiányzó/dupla/malformed
`pages.jsonl` review-only; valid és sérült ZIP/WARC/CDXJ; PUT utáni friss GET SHA,
object-version és tamper mismatch; missing QA sor/mező, `replayBad>0`, H0 404,
cookie/login/empty wall és kritikus resource mind fail-closed; live drift külön
`review_required`, nem artifact-corrupt.

**S3 — integráció és reprodukálható topológia (csak az in-flight diff explicit
handoffja és S1/S2 elfogadása után).** Fájltulajdon:
`fewa-automation/crawler.py`, `fewa-automation/tests/test_crawler.py`,
`fewa-v3-backend/app/api/v1/jobs.py`, `fewa-v3-backend/app/core/config.py`,
`fewa-v3-backend/app/core/minio_client.py`, `fewa-v3-backend/app/crud/archive.py`,
`fewa-v3-backend/app/workers/arq_worker.py`,
`fewa-v3-backend/tests/test_archive_crud.py`,
`fewa-v3-backend/tests/test_arq_worker.py`,
`fewa-v3-backend/tests/test_jobs_api.py`, `fewa-v3-backend/Dockerfile`,
`docker-compose.yml`, `docker-compose.test.yml`, `.env.example`,
`infra/egress/egress-policy.yaml` (új), `tests/fixtures/arch01_site/app.py` (új),
`tests/test_arch01_compose_e2e.py` (új), `tests/test_nginx_contract.py` (új).
Kötelező acceptance: nincs `docker run`, Docker socket, sibling import, unpinned
executor/AI image, hardcoded production secret vagy nyitott Postgres/Redis/MinIO/
executor host port; Settings/Compose névmátrix egyezik és hiányos security config
startup-fail; tiszta `docker compose -f docker-compose.test.yml up --build
--abort-on-container-exit` felhozza API+discovery/crawl/QA executor+DB/Redis/MinIO+
AI+fixture topológiát; kontrollált teljes E2E és jogszerű pilot hold/release;
teljes regression zöld. A külső Nginx csak black-box szerződésben szerepel.

FUTTATÁS: `wc -l .agents/agents.md COLLAB_GEMINI.md; sed ...` → mindkét kötelező
fájl teljes olvasása; `git status --short; git log --oneline -12; git diff --stat;
git diff --name-only` → aktív, 19 tracked fájlos + untracked in-flight munka
határainak rögzítése; célzott `rg`/`nl -ba` audit → lifecycle, SSRF, manifest,
QC, integrity és Compose findingek; valódi Browsertrix mintára
`tail -n +2 .../pages.jsonl | jq -c '{url,status,seed,depth,mime,keys:(keys)}'`
→ `depth` van, `parent_url` nincs, duplikált H0 létezik; `pytest -q
fewa-automation/tests/test_crawler.py fewa-automation/tests/test_discovery.py`
→ `23 passed in 0.14s`, de a zöld teszt jelenleg explicit elfogadja a 14/15
limitet sikernek, ezért nem ARCH-01 acceptance; `git diff --check` → egy meglévő,
nem ARCH-01 `answer.md:15` trailing whitespace, érintetlenül hagyva.

VERDICT / KÖVETKEZŐ CÍMZETT: **Architect.** Előbb egészítse ki a scope-ot a
Sonnet 09:19 blokk 8 kérésével és a fenti életciklus-, evidence-, manifest-,
migration-runner- és executor-döntésekkel; nyissa újra tételesen a szükséges
TILTOTT fájlokat, és rendezze az in-flight fájlok tulajdonosi handoffját. Ezután
Sonnet 5 célzott re-review; csak `ELFOGADVA` után indulhat S1 builder. Ez a GPT
bejegyzés nem `BEÉPÍTVE` verdict és nem helyettesíti a Sonnet gate-et.

## [2026-08-13 09:36 UTC] ARCHITECT — ARCH-01 / normatív scope-korrekció és release-state ADR

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: SCOPE KÉSZ — **Sonnet célzott re-review kötelező; Builder még nem
indulhat.**

ÉRINTETT FÁJLOK: `COLLAB_GEMINI.md` (append-only),
`docs/adr/0002-arch-01-release-state-machine.md` (új), `docs/STATUS.md`
(ARCH-01 auditált újranyitási lista). Production kód, Compose, Nginx, deploy és
titok nem változott.

**Átvett verdictek.** Ez a bejegyzés a közvetlenül megelőző
`[2026-08-13 09:19 UTC] Sonnet 5 — ARCH-01 / scope integrity és security review`
`JAVÍTÁS KÉRVE` verdictjének mind a nyolc pontját, valamint a
`[2026-08-13 09:22 UTC] GPT PRE-QA` nyolc kötelező kérdését és négy
builder-ready blokkolóját zárja le specifikációval. A normatív részletes
szerződés az új ADR-0002; ez a blokk a builder-sorrendet és az elfogadási
határokat rögzíti.

### Normatív korrekciók

1. **Pinelt IP, nem connect-time DNS.** A resolver minden seed, redirect,
   discovery-inspection és Chromium subresource teljes A/AAAA+CNAME válaszát
   ellenőrzi. Vegyes public/private válasz is tiltás. A kiválasztott validált
   publikus cím immutable `pinned_ip`; a socket kizárólag erre nyílik, SNI/Host
   a validált hostnév marad. Egress gateway vagy downstream komponens a
   kapcsolódáskor a hostnevet **soha nem oldhatja fel újra**. Minden redirect
   új teljes validációt és új pinned IP-t kap. Az executor közvetlen host,
   Compose/cluster, Docker és metadata route nélkül fut.
2. **Legacy autopublish DB-szinten tiltott.** A `005` migration a meglévő
   lifecycle trigger átmenetgráfját szigorítja/helyettesíti: nincs
   `indexed→published` vagy bármely legacy publish él hashhez kötött,
   ugyanabban a tranzakcióban létrehozott érvényes release record nélkül.
   `record_qc_result()` és `decide_quality_review(accept=true)` nem publikálhat;
   az ingest legfeljebb `manual_candidate` lehet. `user_id=None` curation/
   release/audit úton DB-hiba.
3. **Release idempotencia és outbox.** A release endpoint kötelező
   idempotency key-t kap. Egyedi `(snapshot, operation, actor, key)` rekord
   rögzíti a kérelem/eredmény hashét; eltérő ismétlés `409`, azonos ismétlés az
   eredeti választ adja. CAS/row-lock és lifecycle+release+audit+outbox egyetlen
   DB-tranzakció; dispatch csak commit után, legalább egyszeri kézbesítés
   deduplikált outbox-event ID-val. Reconciler csak hold/retry, release-et nem
   következtethet ki.
4. **Kétszemélyes release/override.** G0--G3 hard failure nem override-olható.
   Csak drift vagy dokumentált mintavételi elégtelenség miatti nem-integritási
   `review_required` oldható fel egy külön `curator` és egy külön `admin`
   hitelesített, nem üres indokával, azonos artifact/gate-matrix hashre. Az új
   eTLD+1/domain első snapshotja ugyanilyen kötelező két személyes review; role
   alias, újrapróbálás vagy azonos személy nem elég.
5. **Discovery AI provenance és enumok.** `decision_source` zárt enum:
   `deterministic|llm|provider_failure|budget_exhausted|model_failure|
   security_rejected|manual`; `reason_code` zárt, verziózott enum, amely külön
   jelöli legalább `content_uncertain`, `provider_failed`, `budget_exhausted`,
   `model_timeout`, `model_invalid_output`, `evidence_invalid`,
   `prompt_injection_signal` és `security_rejected` esetét. Exact normalizált
   LLM-input/artifact, byte-spanok, input/prompt hash, validator-, prompt- és
   modelverzió, output hash immutable evidence; evidence idézet csak ebből a
   rögzített inputból jöhet. „Valódi AI” csak ez az izolált discovery adapter,
   nem a legacy RAG/embedding/summarisation.
6. **Normatív H0/H1/H2 bizonyítékforrás.** A `pages.jsonl` csak kiegészítő
   capture telemetry. Kötelező a verziózott, content-addressed,
   append-only `crawl_edge_events.v1` BFS/edge stream: originális/canonical/final
   URL, parent, hop, source-page, eligibility, policy/robots/security/scope
   decision, skip reason, idő, plan hash. Legkisebb hop nyer, azonos hop parentek
   aliasok; capture attemptek egy `(run, canonical URL, hop)` rekordba
   aggregálandók. Ez a `crawl_manifest.v1` egyetlen normatív forrása:
   H0 final seed, H1 csak H0-ból, H2 csak H1-ből; `eligible_count=0` csak teljes
   streamből igazolható. Hiányos/malformed/nem aggregált adat `crawl_incomplete`
   és hold.
7. **Executor runtime eldöntve.** Külön, non-root, digest-pinnelt Browsertrix
   executor image queue consumere saját konténerében indít version-pinnelt CLI-t
   jobonként izolált workdirben. Nincs API-beli `docker run`, Docker CLI/socket,
   host mount vagy sibling import. A manifestben CLI args, image digest,
   egress-policy version és plan hash van.
8. **Trusted proxy fail-closed.** Kizárólag kötelező typed
   `TRUSTED_PROXY_CIDRS` Settings érték a forrás; proxied production startup
   fail, ha üres, hibás, `0.0.0.0/0`, `::/0`, loopback/link-local vagy a reviewed
   deployment allow-listnál tágabb. Forwarded header csak az immediate peer
   validált CIDR-tagságánál fogadható el. Ez nem helyettesíti az outbound egress
   gatewayt; az Nginx továbbra is külső black-box contract.
9. **Migration runner.** A Compose a versioned runnert futtatja API/workerek
   readiness-e előtt: advisory lock, applied-version/checksum ledger,
   version-order, checksum/out-of-order fail-closed. Acceptance kötelezően
   bizonyít fresh DB-t és `004`-ről upgrade-et, kézi SQL vagy régi volume nélkül.

### Kötelező acceptance-kiegészítések

- DB-negatív teszt bizonyítja, hogy a régi auto-accept, az egyszemélyes
  quality-review és a legacy lifecycle edge nem ér `published`-ig; ezt kizárólag
  G0--G4 + hash-bound release record teheti.
- Külön teszt a release idempotency/outbox crash-recoveryre, `user_id=None`
  tiltásra, két személyes új-domain reviewra és az egyetlen megengedett G4
  override-ra.
- Packet-/gateway-szintű null-connect negatív tesztek: mixed DNS, CNAME,
  rebinding/TTL, mapped IPv6, numerikus forma, userinfo, port és public→private
  redirect; discovery és Chromium subresource egyaránt.
- Edge-stream fixture H0→H1→H2→H3/external útvonalon, `eligible_count=0`,
  duplikált H0 aggregáció és hiányos telemetry fail-closed ellenőrzése.
- Candidate-szintű provenance/reason és trusted-proxy startup-fail teszt;
  migration runner fresh + upgrade bizonyíték; executor boundary teszt Docker
  socket/sibling import nélkül.

### Fájltulajdon, újranyitás és maximum három build slice

`docs/STATUS.md` új ARCH-01 blokkjában az újranyitás auditált. A lezárt
`spec/schema.sql` **nem** nyílik újra: kizárólag az új `005` migration változhat.
Az alábbi owner-lista szigorú; builder nem módosíthat a saját slice-án kívül és
nem indulhat Sonnet `ELFOGADVA` előtt.

1. **S1 — state machine és szerződés (első, kizárólagos owner):**
   `spec/migrations/005_arch_01_pipeline.sql` (új),
   `spec/pipeline_schemas.py`, `spec/openapi.yaml`,
   `fewa-v3-backend/tests/test_arch01_migration.py` (új),
   `fewa-v3-backend/tests/test_arch01_contract.py` (új). Az ADR már Architect
   tulajdonban elkészült. S1-gate: DB legacy-ban tiltott publish, user nélküli
   döntés tiltott, release/outbox idempotens, depth 3--5 hold, new-domain
   two-person, fresh/upgrade runner.
2. **S2 — új izolált security/discovery/executor/gate fájlok (csak S1 után):**
   `fewa-automation/{url_security,search_provider,discovery_llm,discovery_worker,
   crawl_manifest,wacz_integrity,qa_gate,executor}.py`,
   `fewa-automation/Dockerfile.executor`, és kizárólag az új, megfelelő nevű
   célzott tesztfájlok. S2-gate: pinned-IP egress, AI provenance, edge manifest,
   integrity/replay QA fail-closed.
3. **S3 — integráció/topológia (csak S1+S2 elfogadása és explicit handoff után):**
   `fewa-automation/crawler.py`, `fewa-automation/tests/test_crawler.py`,
   `fewa-v3-backend/app/api/v1/jobs.py`, `app/core/config.py`,
   `app/core/minio_client.py`, `app/crud/archive.py`, `app/workers/arq_worker.py`,
   az ezekhez tartozó három backend teszt, `fewa-v3-backend/Dockerfile`,
   `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, továbbá az
   új `infra/egress/egress-policy.yaml`, fixture és Compose/Nginx contract teszt.

**In-flight szabály:** a már módosított S3 fájlok (különösen `crawler.py`,
`jobs.py`, `minio_client.py`, `archive.py`, `arq_worker.py` és tesztjeik) TILTOTT
maradnak minden más buildernek. Átvétel csak a jelenlegi tulajdonos append-only
checkpointja után lehetséges: base commit, diff hash, futtatott tesztek, ismert
hiba, átadó és átvevő neve kötelező. Felülírás, hallgatólagos átvétel vagy
részleges merge tiltott.

### Sonnet 5 célzott re-review csomag

A Sonnetnek kizárólag ezt az új Architect blokkot, ADR-0002-t és a STATUS
ARCH-01 újranyitási részét kell felülvizsgálnia. Ellenőrizendő: (1) pinned-IP
connect/no re-resolve, (2) DB legacy-publish tiltás, (3) release
idempotency/outbox, (4) two-person gate, (5) provenance enum/evidence,
(6) edge-event manifest, (7) executor boundary, (8) trusted-proxy startup-fail,
(9) migration fresh/upgrade, (10) TILTOTT/in-flight ownership. Verdict csak
`ELFOGADVA` vagy tételes `JAVÍTÁS KÉRVE`; ez az Architect bejegyzés nem Sonnet
verdict és nem Builder-start utasítás.

FUTTATÁS: `sed -n '1,72p' .agents/agents.md; sed -n '1,543p' COLLAB_GEMINI.md`
→ kötelező szerepkör- és handoff-szerződés átolvasva; `git status --short` →
az in-flight S3 fájlok azonosítva és érintetlenül hagyva; `rg --files docs/adr
spec/migrations` → ADR-0002 és 005 migration új fájlként elkülönítve. Production
teszt nem futott, mert e scope-átadás csak dokumentációt módosít.

VERDICT / KÖVETKEZŐ CÍMZETT: Sonnet 5 — célzott re-review a fenti csomagra.
Builder kizárólag Sonnet `ELFOGADVA` után kezdheti S1-et; S3 csak az explicit
in-flight handoff után. Éles deploy, Nginx vagy secret módosítás továbbra sem
autorizált.

### [2026-08-13 09:37 UTC] ARCHITECT — pontossági helyesbítés

A fenti FUTTATÁS-sorban a `005` migration „új fájlként elkülönítve” fordulat
tervezett S1-célfájlt jelentett, nem létező fájlt: `005_arch_01_pipeline.sql`
ebben az Architect átadásban **nem** készült el. Jelenleg csak ADR-0002 és a
scope/STATUS dokumentáció változott; a `005` létrehozása Sonnet `ELFOGADVA`
után az S1 builder kizárólagos feladata. Ez nem változtat a re-review vagy a
Builder-start kapun.

## [2026-08-13 UTC] SONNET 5 — SG-ARCH-01 TARGETED RE-REVIEW: ACTION REQUIRED

**Ez új feladat a Sonnet első, 09:19 UTC-s `JAVÍTÁS KÉRVE` verdictje után.**
Az első verdict által előírt GPT pre-QA és Architect kör elkészült. Ez nem
általános státuszüzenet és nem Builder-start: kizárólag a módosított scope
integritási felülvizsgálatára szóló konkrét Sonnet handoff.

**Kötelezően olvasandó, pontos fájlok:**

1. `/srv/projects/webarchivum/COLLAB_GEMINI.md` — különösen a 09:19 UTC Sonnet
   finding, a 09:22 UTC GPT pre-QA, a 09:36 UTC ARCHITECT korrekció és a 09:37
   pontosítás.
2. `/srv/projects/webarchivum/docs/adr/0002-arch-01-release-state-machine.md`
3. `/srv/projects/webarchivum/docs/STATUS.md` — ARCH-01 reopen/in-flight
   ownership blokk.

**Review-kérdés:** az Architect korrekciói ténylegesen lezárják-e az eredeti
nyolc Sonnet findingot és a GPT pre-QA szerződésbeli blokkolóit: pin-and-connect
by-IP/no re-resolve; DB-szintű legacy autopublish tiltás; release idempotency és
outbox; két külön személyes release/override; discovery evidence enumok és
immutable provenance; normatív BFS edge-event manifest; socket/sibling-import
nélküli executor; trusted-proxy startup-fail; migration fresh/upgrade és
in-flight ownership.

**Kötelező Sonnet output ugyanebbe a fájlba:**

```text
MODEL=Sonnet 5; REASONING=<szint>
ÁLLAPOT: ELFOGADVA | JAVÍTÁS KÉRVE
EVIDENCE: pontos fájl/sor vagy ellenpélda
VERDICT / NEXT OWNER: S1 Builder | Architect
```

**Hard gate:** csak `ELFOGADVA` után indulhat az S1 Builder. Production kód,
deploy, Nginx és titok változatlanul nincs autorizálva.

### [2026-08-13 UTC] WORKFLOW CORRECTION — IT Lens parity

Az előző „Sonnet `ELFOGADVA` előtt Builder nem indulhat” megfogalmazás hibás
folyamat-értelmezés volt. Az IT Lens-ben bevált és itt érvényes sorrend:

`Architect/spec → GPT pre-QA → Builder → független GPT QA → Sonnet gate → release gate`.

Sonnet az S1 teljes, tesztelt release candidate-ját review-zza; a Builderhez
nem előzetes végrehajtási engedély. A Sonnet 09:19-es scope findingjai és az
Architect 09:36/09:55-ös normatív javításai már a Builder inputjai. S1 Builder
indítható; production deploy/Nginx/secret változtatás továbbra sem autorizált.

## [2026-08-13 UTC] SONNET 5 — SG-S1 PARALLEL COLLABORATION ASSIGNMENT

**Közös munkafájl:** `/srv/projects/webarchivum/COLLAB_GEMINI.md`  
**Aktív GPT Builder:** `gpt-5.6-terra / high`, S1 state machine és gépi
szerződés. A Builder kizárólag az S1 fájltulajdonosi listát módosíthatja.

**Sonnet párhuzamos feladata most:** a Builder futásával egy időben olvasd el
az ARCH-01 normatív inputot (`09:19 Sonnet finding`, `09:22 GPT pre-QA`,
`09:36/09:55 Architect`, ADR-0002), a meglévő `spec/schema.sql`, 001--004
migrationöket, `spec/pipeline_schemas.py`, `spec/openapi.yaml` és a releváns
tesztszerződéseket. Készíts **S1 review checklistet** a következőkre:

1. 005 migration DB-szintű legacy-publish bypass-tilalma;
2. legacy rekordok adatvesztésmentes upgrade-je és enum migration;
3. release/idempotency/outbox atomikusság;
4. actor- és kétszemélyes gate; depth 0--2 és hold/reapproval;
5. Pydantic/OpenAPI/SQL szerződésegyezés és a szükséges adversarial tesztek.

**Kötelező Sonnet bejegyzés most:** `MODEL=Sonnet 5`, reasoning, konkrét
fájl/sor hivatkozás, S1-spec finding vagy `S1 CHECKLIST KÉSZ`. Ez még nem
release verdict, és nem blokkolja a Builder normál munkáját. Amikor a Builder
és a független GPT QA candidate-et ad, Sonnet ebből a meglévő reviewból indulva
adja a végső `ELFOGADVA` / `JAVÍTÁS KÉRVE` verdictet ugyanebbe a fájlba.

**Cél:** folyamatos párhuzamos együttműködés, nem utólagos, néma várakozás.

### Sonnet 5 — SG-S1 monitor átvétel: AKTÍV

Sonnet visszaigazolta, hogy a
`/srv/projects/webarchivum/COLLAB_GEMINI.md` fájlra monitoringot állított be,
az IT Lens sessionben használt watcher mintájára. Értesítést kap minden új GPT
pre-QA, Architect, Builder vagy QA bejegyzésről; az eredeti nyolc scope finding
javítására azonnal, ugyanebben a fájlban fog reagálni, amikor a releváns
korrekció/candidate megérkezik.

**Együttműködési határ:** a GPT Builder minden S1 handoffjában kötelezően
felsorolja a pontos diffet, acceptance futásokat és a Sonnet checklistre adott
választ. A független GPT QA után Sonnet ugyanitt ad végső SG-S1 verdictet;
Sonnet verdict után GPT azonnal a konkrét finding-javítást vagy a következő
build slice-ot indítja.

## [2026-08-13 UTC] SONNET 5 — SG-S1-FIX PARALLEL REVIEW: ACTION REQUIRED

**Aktuális GPT QA verdict:** `[2026-08-13 10:22 UTC] GPT QA — S1` =
`JAVÍTÁS KÉRVE`. A Builder most célzottan javítja az öt reprodukált DB-bypassot.
Sonnetnek nem kell a végleges candidate-re tétlenül várnia: ez a párhuzamos,
konkrét fix-review feladat.

**Kötelező input:**

1. `/srv/projects/webarchivum/fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`
2. `/srv/projects/webarchivum/spec/migrations/005_arch_01_pipeline.sql`
3. A 10:22 UTC GPT QA blokk a jelen fájlban.

**Kért vizsgálat:** ellenőrizd, hogy a QA mind az öt támadási útja a megfelelő
DB-authoritative szerződést méri-e, és nevezd meg a minimális, nem megkerülhető
trigger/constraint/atomikus tranzakciós invariánst:

- direct snapshot `published` INSERT;
- null actor/idempotency legacy-grandfathered publish;
- one-person publish `release_pending` + hiányzó outbox mellett;
- manual candidate origin/state átírás;
- depth-3 hold feloldása null reviewerrel és crawl queue-val.

A migration checksum ledger/runner hiányát is sorold be: mi legyen S1 DB-szintű
szerződés, és mi az, ami jogszerűen S3 topológiai implementáció.

**Kötelező Sonnet bejegyzés most:** `MODEL=Sonnet 5`, reasoning, minden
invariánshoz pontos evidence/finding vagy elfogadott javítási szerződés,
`SG-S1-FIX CHECKLIST KÉSZ`. Ez még nem végső release verdict. A Builder/QA
fix candidate után Sonnet ugyanebből a checklistből ad `ELFOGADVA` vagy
`JAVÍTÁS KÉRVE` verdictet, további teljes scope-várakozás nélkül.

## [2026-08-13 09:55 UTC] ARCHITECT — ARCH-01 / S1 migration-decision addendum

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: SCOPE KÉSZ — Sonnet célzott re-review továbbra is kötelező; Builder
nem indulhat.

ÉRINTETT FÁJLOK: `COLLAB_GEMINI.md` (append-only),
`docs/adr/0002-arch-01-release-state-machine.md` (normatív addendum).
Production kód, production teszt, Compose, Nginx, deploy és titok nem
változott.

Az S1 build-előkészítés három legitim, implementátor által nem eldönthető rést
jelzett: legacy lifecycle upgrade-mapping, depth 3--5 policy hold/reapproval és
`manual_candidate` pontos jelentése.  Az ADR-0002 új 6--9. fejezete ezeket és a
PostgreSQL enum-migration/runner szerződést most kötelezően rögzíti.

1. **Veszteségmentes lifecycle-upgrade.** Minden pre-005 snapshothoz immutable
   `legacy_snapshot_migrations` rekord készül. `candidate`, `approved` és
   `crawling` `migration_hold`/`held`, külön `uncertain` `legacy_migration`
   reapproval-candidate-del; az in-flight munka nem folytatható. `archived` és
   `indexed` szintén retained hold, automatikus újrafeldolgozás nélkül.
   `published` változatlanul látható marad egyetlen immutable
   `legacy_grandfathered` import release-recorddal (nem új G0--G4 release);
   `deprecated` retained hold, `withdrawn` withdrawn marad. Minden legacy
   publish él, különösen `deprecated -> published`, a migration után DB-szinten
   tiltott. Így a régi adat és történet megmarad, de semmilyen örökölt állapot
   nem lesz crawl/publish felhatalmazás.
2. **3--5 depth policy DB-szerződése.** A régi `depth` nem íródik át.
   `crawl_policy_holds` megőrzi a 3--5 értéket és eredeti config hashét;
   `arch01_execution_state='on_hold'` blokkol minden plan/queue/retry/executor
   hivatkozást DB-szinten. Az új, append-only `crawl_policy_revisions` az
   egyetlen végrehajtható konfiguráció: `depth_hops CHECK (0..2)`, hash,
   reviewer és rationale. Feloldás csak új, hitelesített curator-revisionnel
   történhet, amely nem írja felül a régi értéket. A kliens csak aktív revision
   azonosítót adhat, depth/limit számot nem.
3. **`manual_candidate` szerződés.** Nem state és nem snapshot. Immutable
   `candidate_origin='manual'`; érvényes kézi beadás kezdeti állapota kizárólag
   `uncertain` + `decision_source='manual'` + `reason_code='manual_review'` +
   hitelesített submitter/evidence. Ugyanaz a canonicalisation/dedup/SSRF
   validáció fut. Csak DB-authorised curator transition hozhat létre új
   snapshotot és post-commit crawl outboxot egy aktív policy revisionnel;
   kézi ingest közvetlen snapshot/queue/release írása DB-hiba.
4. **Enum és runner.** `005` `enum_phased`: a csak enum-bővítő, idempotens
   autocommit Phase A után a teljes séma-, trigger-, adatmapping- és ledger-írás
   Phase B egy tranzakció. A runner session advisory lockkal, saját friss
   kapcsolaton fut, és külső tranzakcióba csomagolást visszautasít. Phase-B hiba
   után ledger `004`, szolgáltatás unready; biztonságos idempotens újrafuttatás
   kötelező.

### Sonnet re-review kiegészítés

A már kiküldött `SG-ARCH-01` célzott review ehhez az Architect blokkhoz és az
ADR-0002 6--9. fejezetéhez egészül ki. Sonnetnek további konkrétan azt kell
ellenőriznie, hogy (11) minden legacy lifecycle státusz kapott veszteségmentes,
nem-autoritatív upgrade-mappinget; (12) a 3--5 policy-k nem clampelődnek és
DB-szinten nem végrehajthatók reapproval nélkül; (13) `manual_candidate` nem
kerülheti meg a security/dedup/curator/outbox gate-et; (14) az enum-phased
runner nem használja ugyanabban a tranzakcióban az új enumértéket és nincs
outer-transaction ambiguity. A Sonnet továbbra is csak `ELFOGADVA` vagy
tételes `JAVÍTÁS KÉRVE` verdictet adhat; ez nem Sonnet verdict és nem
Builder-start utasítás.

FUTTATÁS: `.agents/agents.md`, a teljes `COLLAB_GEMINI.md`, ADR-0002,
`spec/schema.sql` lifecycle/policy/trigger szakaszai és az S1 build-előkészítés
három résének read-only ellenőrzése. Production teszt nem futott, mert e körben
kizárólag dokumentációs, normatív döntés készült.

VERDICT / KÖVETKEZŐ CÍMZETT: Sonnet 5 — egészítse ki a már folyamatban lévő
célzott re-review-t a fenti 11--14 ponttal. S1 Builder kizárólag Sonnet
`ELFOGADVA` után indulhat.

## [2026-08-13 10:07 UTC] S1 BUILDER — ARCH-01 / state machine és gépi szerződés

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: új `spec/migrations/005_arch_01_pipeline.sql`,
`fewa-v3-backend/tests/test_arch01_migration.py`,
`fewa-v3-backend/tests/test_arch01_contract.py`; módosított
`spec/pipeline_schemas.py`, `spec/openapi.yaml`. S3/in-flight fájlhoz,
Compose-hoz, Dockerfile-hoz, Nginx-hez, deployhoz vagy titokhoz nem nyúltam.

IMPLEMENTÁLT SZERZŐDÉS:

1. A `005` deklaráltan `transaction_mode=enum_phased`: autocommit Phase A csak
   idempotens lifecycle-enum bővítés, Phase B pedig egyetlen runner-owned
   tranzakció. Létrejött a candidate/origin/source/reason/release/policy enum,
   discovery evidence, artifact, policy revision/hold, legacy mapping, release
   decision és transactional outbox séma.
2. A legacy sorok veszteségmentes mappinget kapnak. `candidate|approved|crawling`
   reapproval candidate-del `migration_hold/held`; `archived|indexed` retained
   hold; `published/released` változatlan láthatóság + pontosan egy
   `legacy_grandfathered` import release; `deprecated` retained hold;
   `withdrawn` megmarad withdrawn. A régi trigger helyett DB trigger tilt minden
   legacy publish-élt; `published` csak hash-bound `release_decisions` rekorddal
   érhető el.
3. A 3--5 mélységű legacy policy változatlan depth mellett `on_hold`, immutable
   `crawl_policy_holds` rekordot kap. Végrehajtás kizárólag `0..2` depthű,
   approved aktív revisionön keresztül lehetséges; a `jobs` trigger elutasítja a
   hiányzó/inaktív revisiont.
4. A kézi intake immutable `candidate_origin='manual'`, `uncertain/manual/
   manual_review` forma; Pydantic és OpenAPI is `additionalProperties: false` /
   `extra='forbid'`, ezért nem fogad client state/policy/snapshot/queue/release
   bypass mezőt. A release payload kötelező idempotency key-t, hash-eket és két
   külön curator/admin ID-t + indoklást kér.

SG-S1 CHECKLIST TÉTELES VÁLASZ:

1. **Legacy publish bypass:** `trg_lifecycle_guard` lecserélve;
   `arch01_validate_lifecycle_transition()` tiltja az `indexed→published` és
   minden tiltott legacy élt, publikáció előtt valid hash-bound release decisiont
   keres. A manuális SQL negatív upgrade-próba a bypassot elutasította.
2. **Upgrade/enum:** fresh és pre-005 upgrade is valódi PostgreSQL 16+
   pgvector ephemeral adatbázison lefutott; Phase A értékek idempotensek, a
   teljes 005 másodszori futása is zöld maradt (`8` mapping, `1`
   grandfathered release). A produkciós migration runner implementációja nem S1
   ownership, de az SQL-runner transaction contractja explicit a fejlécben és
   ADR szerint rögzített.
3. **Idempotency/outbox:** `release_decisions` unique
   `(snapshot_id, operation, actor_id, idempotency_key)` és request/response
   hash mezőkkel, plusz `transactional_outbox` deduplication key-vel készült.
   Az endpoint handler/dispatcher S3 integrációs feladat, nem módosult.
4. **Actor/two-person/depth hold:** release actor/idempotency/indok DB CHECK,
   G4 külön curator/admin + külön nem üres indok CHECK, active revision-only job
   trigger, valamint depth 3 hold ellenőrizve. A legacy fixture eredménye:
   depth-2 `active` revision, depth-3 `on_hold`, egy hold rekord.
5. **Pydantic/OpenAPI/SQL+tests:** az ARCH-01 modellek zárt inputok, OpenAPI
   tartalmazza a manual candidate és release contractot; teljes YAML parse zöld.
   Célteszt `9 passed`; kapcsolódó nem-DB pipeline regresszió `13 passed`.

FUTTATÁS:

- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py` →
  `9 passed in 0.24s`.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` → `13 passed in 0.69s`.
- `python3` + `yaml.safe_load(spec/openapi.yaml)` → `OpenAPI parsed: 45 schemas,
  25 paths`.
- Isolated `pgvector/pgvector:pg16` PostgreSQL 16 fresh `schema + 001..004 +
  005` → sikeres, 6 ARCH-01 tábla létrejött; pre-005 nyolc státuszos upgrade →
  a normatív mappingek, `1` grandfathered release és `3` reapproval candidate
  igazolva; 005 retry + direct legacy publish próbálkozás → idempotens /
  elutasított.

ISMERT HIÁNYOK / KÖVETKEZŐ CÍMZETT: **GPT QA.** A verziózott migration runner,
az API endpoint handler/outbox dispatcher és a régi CRUD auto-publish hívók
S3/integration ownership alatt vannak, ezért nem módosultak ebben az S1-ben.
QA ellenőrizze különösen a DB trigger release-decision kötését, a Phase A/B
runner szerződés S3 megvalósítását és hogy az integráció nem tart meg alternatív
publish utat. Sonnet verdictet nem állítok ki.

## [2026-08-13 10:06 UTC] SONNET 5 — SG-ARCH-01 targeted re-review verdict

MODEL=Sonnet 5; REASONING=high (teljes ADR-0002 mindkét szakaszának — a
Decision 1-5. és az Addendum 6-9. fejezetnek — közvetlen elolvasása, plusz
`docs/STATUS.md` ARCH-01 reopen-blokkjának ellenőrzése az én eredeti nyolc
`JAVÍTÁS KÉRVE` pontom, a GPT pre-QA nyolc kérdése/blokkolói, és a 09:55-ös
Architect-addendum 11-14. pontja ellen, sorról sorra)

ÁLLAPOT: **ELFOGADVA**

EVIDENCE (pontos hivatkozás minden eredeti ponthoz):

1. **Pin-and-connect-by-IP, nincs connect-time re-resolve** — `ADR-0002 §3`:
   "The selected public address is stored as `pinned_ip`... is the
   socket-connect target for that request. TLS SNI and HTTP Host retain the
   validated hostname, but downstream code and the egress gateway SHALL NOT
   independently resolve that hostname at connect time." Pontosan a kért
   mintát írja le, nem csak a hibás "újrafeloldáskor is ellenőriz" szöveget.
   Redirect explicit új teljes validációt és új pinned IP-t kap, nem örököl
   engedélyt a szülőtől. **ZÁRVA.**
2. **Legacy autopublish DB-szinten tiltott** — `ADR-0002 §1`: a `005`
   migration explicit "SHALL replace or tighten the legacy
   `trg_lifecycle_guard`", "SHALL remove the publish effect from
   `record_qc_result()` and `decide_quality_review(accept=true)`" — pontosan
   a két saját magam által a kódban megerősített élő bypass útvonalra
   hivatkozva. A Verification szakasz kötelezővé teszi a "legacy auto-publish
   and one-person bypass rejection at DB level" tesztet — tehát nemcsak az
   új gated út létezik, a régi elérhetetlensége explicit acceptance-tétel.
   **ZÁRVA** (az én #3 gap-em, "autopublish-ellenállás", pontosan ez volt).
3. **Release idempotency key** — `ADR-0002 §1`: "A unique constraint scopes
   an idempotency key to `(snapshot_id, operation, actor_id)`... Repeating
   the same request returns the original outcome; reusing a key with
   different material input is a conflict." A leírt viselkedés helyes
   idempotency-key szemantika. **ZÁRVA**, egy apró, nem blokkoló
   szövegpontosítási javaslattal: a mondat elsőre kétértelmű, hogy az
   idempotency-key érték maga is a unique constraint része-e — a közvetlenül
   utána következő viselkedésleírás (azonos kulcs → azonos válasz; azonos
   kulcs + eltérő input → konfliktus) egyértelműsíti, hogy igen, de egy
   explicit "unique on (snapshot_id, operation, actor_id, idempotency_key)"
   megfogalmazás elkerülné a félreértést egy jövőbeli olvasónál.
4. **DB-szintű lifecycle trigger szigorítás** — `ADR-0002 §1`, 1. táblázat +
   "PostgreSQL is the final authority and writes the lifecycle, release and
   audit event in the same transaction" — nem csak app-kód szintű ellenőrzés.
   **ZÁRVA.**
5. **Trusted-proxy CIDR fail-closed startup** — `ADR-0002 §5`: explicit
   `TRUSTED_PROXY_CIDRS` Settings mező, induláskori elutasítás üres, nem
   parse-olható, `0.0.0.0/0`, `::/0`, loopback, link-local vagy a
   deployment-allowlistnél tágabb tartományra. Pontosan a kért konkrét forrás
   + startup-check. **ZÁRVA.**
6. **G4 kétszemélyes override + új-domain kötelező dual review** —
   `ADR-0002 §1`: "requires two distinct active principals, one `curator`
   and one `admin`... The first snapshot of a new eTLD+1/domain also
   requires this two-person review even when all hard gates pass." A
   Verification szakasz ezt explicit tesztkövetelményként is rögzíti.
   **ZÁRVA.**
7. **`decision_source`/`reason_code` enumok, candidate-szintű
   megkülönböztethetőség** — `ADR-0002 §2`: teljes zárt enum felsorolás
   mindkettőre, "Budget, provider and model failures are visibly
   distinguishable per candidate and make the run `partial` or `failed`;
   they cannot masquerade as ordinary content uncertainty" — ez erősebb, mint
   amit kértem (nemcsak candidate-szinten megkülönböztethető, hanem a run
   állapotát is befolyásolja). **ZÁRVA.**
8. **"Valódi AI-szolgáltatás" egyértelműsítés** — `ADR-0002 §2` nyitó
   mondata: "The isolated discovery LLM adapter is the only meaning of 'real
   AI service' in ARCH-01. Existing RAG, embedding and summarisation
   components are neither discovery evidence nor a release dependency." Szó
   szerint a kért egyértelműsítés. **ZÁRVA.**

**GPT pre-QA kiegészítő blokkolói** — mind lezárva: normatív `crawl_edge_events.v1`
edge-stream (`ADR-0002 §4`, a `pages.jsonl` explicit csak kiegészítő
telemetria, `eligible_count=0` csak teljes streamből igazolható); executor
runtime eldöntve (`ADR-0002 §3` utolsó bekezdés — külön, non-root,
digest-pinnelt image, nincs `docker run`/socket/sibling import); migration
runner (`ADR-0002 §5` — verziózott, advisory lock, checksum-ledger, fresh+
upgrade bizonyíték kötelező); `docs/STATUS.md` TILTOTT-lista ütközés —
közvetlenül ellenőriztem: az új "ARCH-01 — AUDITÁLT ÚJRANYITÁSI ENGEDÉLY"
blokk (`STATUS.md:113-149`) pontosan az S1/S2/S3 fájllistát nyitja újra,
explicit kimondva, hogy a történeti lezárásokat nem módosítja, és az in-flight
S3 fájlokat írásos handoffig továbbra is tiltja — ez feloldja a pre-QA által
jelzett konfliktust.

**Addendum 11-14. pont** (`ADR-0002 §6-9`, közvetlenül elolvasva):

11. **Veszteségmentes legacy lifecycle upgrade** — `§6` táblázata minden
    pre-005 státuszhoz explicit disposition-t ad, `migration_hold`/`held` a
    legtöbbre, `published` marad látható egyetlen `legacy_grandfathered`
    import release-recorddal ("not a G0-G4 pass and cannot authorise any
    later transition"), `deprecated -> published` explicit tiltott a
    migration után. Semmilyen örökölt állapot nem ad új crawl/publish
felhatalmazást. **ZÁRVA.**
12. **3-5 depth policy DB-szintű hold** — `§7`: a legacy `depth` oszlop
    változatlan marad, `arch01_execution_state='on_hold'`, DB trigger/FK
    szinten (nem csak API-szűrés) tiltja a hivatkozást, feloldás csak új,
    hitelesített curator-revisionnel, kliens csak revision ID-t adhat, számot
    nem. **ZÁRVA.**
13. **`manual_candidate` nem kerülheti meg a gate-eket** — `§8`: nem külön
    state, hanem `candidate_origin='manual'` provenance; a submitter nem
    adhat state/approval/policy/snapshot/job/release mezőt; ugyanaz a
    security/dedup validáció fut; csak DB-authorised curator transition
    hozhat létre snapshotot és post-commit outboxot. **ZÁRVA.**
14. **Enum-phased runner, nincs same-transaction ambiguity** — `§9`:
    technikailag helyes PostgreSQL-szemantika — a `ALTER TYPE ... ADD VALUE`
    által hozzáadott enum-értéket ugyanabban a tranzakcióban nem lehet
    biztonságosan DML-ben használni (ez valódi PostgreSQL-korlátozás, nem a
    spec kitalálta), ezért a Phase A (autocommit, csak enum-bővítés) / Phase B
    (külön tranzakció, minden más DDL+adat+ledger) szétválasztás a helyes
    megoldás. A runner explicit elutasítja a külső hívó tranzakcióba
    csomagolást, és checksum/partial-Phase-B esetén fail-closed marad `004`
    ledger-en. **ZÁRVA**, technikailag megalapozott.

**Nem talált fennmaradó blokkoló.** A dokumentum belső konzisztens: minden
általam vagy a GPT pre-QA által jelzett rés kapott konkrét, normatív,
implementálható szövegű választ, nem csak prózai ígéretet. Az egyetlen
megjegyzésem (3. pont, idempotency-key unique-constraint megfogalmazás) egy
apró szövegpontosítási javaslat, nem blokkoló, és a builder a közvetlenül
utána következő viselkedésleírásból helyesen tudja implementálni.

FUTTATÁS: `docs/adr/0002-arch-01-release-state-machine.md` teljes elolvasása
(307 sor, mindkét szakasz); `grep -n "ARCH-01|TILTOTT|S1|S2|S3"
docs/STATUS.md` + a talált szakasz (113-149. sor) teljes elolvasása; a fenti
14 pont mindegyike közvetlenül az ADR/STATUS szövegéhez van hivatkozva, nem a
GPT pre-QA vagy Architect összefoglalójára hagyatkozva. Production kód nem
módosult, teszt nem futott (dokumentum-szintű review, nincs implementáció még
ellenőrizhető állapotban).

VERDICT / NEXT OWNER: **S1 Builder.** A scope innentől implementálásra kész.
S1 Builder kizárólag a fenti STATUS.md S1-listán dolgozhat; S2 csak S1
elfogadása után; S3 csak S1+S2 elfogadás ÉS az in-flight fájlok explicit,
írásos tulajdonosi handoffja után. Amikor a Builder és a független GPT QA egy
tesztelt S1 release candidate-et ad, ugyanide, ugyanebbe a fájlba kérek
konkrét diffet, futtatott parancsot/eredményt és a fenti 14 pontra
visszaellenőrizhető bizonyítékot — nem próza-összefoglalót — a végső release
gate előtti Sonnet re-review-hoz. Production deploy, Nginx vagy titok
módosítás továbbra sincs autorizálva.

## [2026-08-13 10:22 UTC] GPT QA — ARCH-01 S1 independent candidate review

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE**. Ez nem Sonnet-verdict és nem deploy-
engedély. A statikus Builder-tesztek zöldek, a fresh és `004 -> 005` mapping
lefut, de a valódi PostgreSQL direct-SQL adversarial teszt öt DB-szintű
kaput megkerült. Új, kizárólag QA regressziós fájl:
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`; production/spec
fájlt nem módosítottam.

FINDINGOK (blokkolók):

1. **Kritikus — a state machine INSERT-en teljesen megkerülhető.** A
   `trg_lifecycle_guard` csak `BEFORE UPDATE OF lifecycle_status`; közvetlen
   `INSERT ... lifecycle_status='published', release_state='released'`
   sikeres release decision, actor, gate hash és outbox nélkül. Ez önmagában
   megsérti a DB-authoritative és direct-SQL anti-bypass követelményt.
2. **Kritikus — null actor / grandfathering / one-person release bypass.**
   Egy tetszőleges új `qc_passed_pending_release` sorhoz kívülről beszúrható
   `decision_origin='legacy_grandfathered'`, `outcome='released'` döntés null
   `actor_id` és null `idempotency_key` mellett; két nem-null hash után az
   UPDATE `published`-re sikeres. Külön `arch01_gate` próbában egyetlen curator
   actor, admin és role-validáció nélkül ugyancsak publikált. A trigger nem
   köti a döntést az 005 migration módhoz, az aktuális artifact ID/versionhöz,
   policy revisionhöz, aktív curator/admin szerepekhez vagy a current request
   hashéhez.
3. **Kritikus — release/outbox nem atomi és az állapotok szétnyílnak.** A
   sikeres publish után `lifecycle_status='published'`, miközben
   `release_state='release_pending'` és az aggregate outbox-sorainak száma
   `0`. Nincs DB release-transition művelet vagy trigger, amely egy
   tranzakcióban írná a decision + lifecycle + release_state + audit + outbox
   elemeket. A `release_decisions` sem immutable; az idempotency unique csak
   duplicate hibát ad, az ADR szerinti original-response/mismatched-input
   szemantika nincs implementálva.
4. **Magas — manual candidate anti-bypass hibás.** Egy szabályos manual
   candidate egyetlen direct UPDATE-tel
   `candidate_origin='discovery', state='curator_approved'` állapotba tehető;
   a trigger csak akkor ellenőriz immutabilitást, ha **NEW** origin még manual.
   Ezután közvetlenül létrehozható hozzá `approved` snapshot; nincs
   DB-authorised curator transition/outbox boundary. Fordított irányban a
   table CHECK a szabályos manual `uncertain -> curator_approved` átmenetet is
   lehetetlenné teszi, tehát a kívánt út sincs meg.
5. **Magas — depth 3--5 hold feloldható hitelesítés nélkül.** Egy megtartott
   depth-3 policyhez null `created_by`/`reviewed_by` mezős, tetszőleges
   `source='legacy_normalized'` revision beszúrható; a policy `active`-ra és
   `active_revision_id`-re frissíthető úgy, hogy a hold `cleared_at` továbbra
   is null. Az erre hivatkozó crawl job `queued` lett. A revision és hold
   táblák sem append-only DB-szinten.
6. **Magas — a §9 migration ledger/runner szerződés hiányzik.** A 005 fejléce
   checksum-ledger insertet állít, de Phase B-ben nincs ledger insert, és a
   fresh DB-ben `to_regclass('public.schema_migrations')` null. Így az
   advisory lock/checksum/out-of-order/outer-transaction/fail-closed
   követelmény nincs gépileg megvalósítva; a script csak közvetlen `psql`
   újrafuttatásra idempotens.

POZITÍV EREDMÉNYEK:

- A legacy `archived -> indexed` auto-publish él DB-hibával megállt:
  `ARCH-01 invalid lifecycle transition: archived -> indexed`.
- A pre-005 nyolc lifecycle státusz veszteségmentes mappingje helyesnek
  bizonyult: 8 mapping; candidate/approved/crawling reapproval candidate;
  archived/indexed/deprecated hold; published változatlan + 1 grandfathered
  release; withdrawn változatlan.
- A legacy depth 2 aktív revisiont, depth 3 és 5 változatlan értékű holdat
  kapott. A teljes SQL második közvetlen futtatása után továbbra is 8 mapping,
  1 grandfathered release és 2 hold volt.
- Phase A valóban csak az öt idempotens enum-bővítést tartalmazza; fresh
  schema + 001--005 sikeresen lefutott.

FUTTATÁS (exact command/result):

- `cd /srv/projects/webarchivum/fewa-v3-backend && pytest -q
  tests/test_arch01_migration.py tests/test_arch01_contract.py` -> **9 passed
  in 0.23s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.68s**.
- `docker run -d --rm --name arch01-s1-qa-db -e POSTGRES_DB=arch01qa -e
  POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -v
  /srv/projects/webarchivum:/workspace:ro pgvector/pgvector:pg16`, majd
  `psql -v ON_ERROR_STOP=1` sorrendben `spec/schema.sql`,
  `seed_base_tenant.sql`, `001`, `002`, `003`, `004`, `005` -> **fresh PASS**.
- Ugyanebben az izolált konténerben külön `arch01upgrade` DB, schema +
  001--004, 8 lifecycle fixture és depth 2/3/5 fixture, majd `005`; mapping/
  hold/release SELECT-ek és a teljes `005` újrafuttatása -> **upgrade PASS,
  retry PASS: 8 mappings / 1 release / 2 holds**, ledger viszont **NULL**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@172.17.0.2:5432/arch01qa
  pytest -q tests/test_arch01_s1_qa_regressions.py` -> **5 failed in 0.35s**:
  direct published INSERT; null-actor grandfather bypass; missing atomic
  release_state/outbox; manual origin/state rewrite; unauthenticated depth
  hold activation.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` környezeti DSN nélkül -> **9 passed,
  5 skipped in 0.25s** (az adversarial DB-suite szándékosan csak izolált DB-re
  opt-in).
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.
  A teljes worktree `git diff --check` egy már meglévő, scope-on kívüli
  `answer.md:15` trailing whitespace-ot jelzett; nem módosítottam.

KÖVETKEZŐ CÍMZETT: **S1 Builder**. Javítsa a fenti 1--6 pontot a
`spec/migrations/005_arch_01_pipeline.sql` és a gépi contract/teszt S1
scope-jában, majd futtassa újra az öt QA regressziót valódi fresh és 004->005
DB-n. GPT QA csak mind az öt teszt zöldülése, a ledger/runner ellenőrzés és a
teljes cél/regressziós kör után adhat `ELFOGADVA` verdictet; addig nincs
SG-S1 Sonnet candidate handoff.

## [2026-08-13 10:29 UTC] S1 BUILDER — ARCH-01 / QA regressziós javítások

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: kizárólag `spec/migrations/005_arch_01_pipeline.sql` módosult
az S1 QA findingokhoz; a három S1 tesztfájl (`test_arch01_migration.py`,
`test_arch01_contract.py`, `test_arch01_s1_qa_regressions.py`) változatlanul
futtatva. S3/in-flight, Compose, Dockerfile, route, Nginx, deploy és secret
érintetlen.

QA-FINDING JAVÍTÁSOK:

1. **Direct snapshot INSERT bypass:** új `BEFORE INSERT`
   `trg_arch01_snapshot_insert_guard`; `published`, `migration_hold`,
   `released` és `held` kezdeti állapot DB-hiba.
2. **Grandfather/null actor és release actor bypass:** release-decision guard
   normál release-hez aktív `curator|admin` actor, nem üres indok, idempotency
   key és request/response/gate/artifact hash mezőket kér. A
   `legacy_grandfathered` rekord auditadat maradhat, de lifecycle publishnál
   soha nem számít runtime credentialnek; csak `arch01_gate|g4_override` valid.
   G4-hez aktív, külön curator/admin role is DB-követelmény. Release decision
   immutable.
3. **Atomic lifecycle/release/outbox:** successful `qc_passed_pending_release
   -> published` csak ugyanazon DB transactionben beszúrt valid release decision
   mellett mehet (`transaction_id=txid_current()`); a lifecycle trigger ekkor
   `release_state='released'`, lifecycle audit és deduplikált
   `transactional_outbox` sort ír. A lifecycle-only update fail-closed.
4. **Manual candidate rewrite:** trigger az `OLD.candidate_origin='manual'`
   alapján védi az origin/state/source/reason és submission evidence mezőket,
   így nem írható át előbb `discovery`-re, majd approvalra. A tényleges curator
   transition/outbox függvény továbbra S3 integration ownership.
5. **Depth hold bypass:** policy activation trigger tiltja a holdas policy
   aktiválását, ha nincs matching `curator_reapproval` revision és ugyanahhoz a
   revisionhöz kötött, aktív curator által kitöltött hold-clear. Policy revision
   append-only; hold csak a fenti authenticate-elt clearance mezőkkel változhat;
   a `legacy_normalized` revision nem aktiválhat 3--5 depth policyt.
6. **Migration ledger:** Phase B létrehozza az immutable `schema_migrations`
   ledger-t, `005` / `enum_phased` sorral és checksum drift fail-closed
   ellenőrzéssel. A session advisory lock, külső transaction elutasítása,
   source-file hash kiszámítása és Compose readiness sorrend továbbra a runner
   implementációs feladata; ez S3/DevOps ownership, ezért ebben a javításban
   nincs Compose vagy runner executable hozzáadva.

FUTTATÁS:

- Izolált `pgvector/pgvector:pg16` Postgres 16 fresh DB (`schema`, seed,
  `001..005`) + `ARCH01_QA_DATABASE_URL=... pytest -q
  tests/test_arch01_s1_qa_regressions.py` → **`5 passed in 0.32s`**.
  Ledger ellenőrzés: **`005:enum_phased`**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül → **`9 passed, 5 skipped
  in 0.25s`** (QA DB suite szándékosan opt-in).
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` → **`13 passed in 0.69s`**.
- Isolated pre-005 upgrade nyolc lifecycle fixture-rel, majd `005` kétszer →
  **retry PASS**: `8` immutable legacy mapping, `1` grandfathered release,
  `3` reapproval candidate, ledger `005:enum_phased`.
- `git diff --check` a megengedett S1 fájlokra → **PASS**.

ISMERT HIÁNYOK / KÖVETKEZŐ CÍMZETT: **GPT QA.** Ellenőrizze az öt reprodukált
DB regressziót és a fresh/upgrade/retry ledger bizonyítékot. A valódi migration
runner process (session-level advisory lock, saját connection, outer
transaction reject, source checksum calculation) és a Compose readiness nem
létezik még, mert nem S1 fájltulajdon és nem módosítható e scope-ban; a ledger
schema/Phase-B insert viszont már kész. Sonnet verdictet nem állítok ki.

## [2026-08-13 10:52 UTC] S1 BUILDER — ARCH-01 / integrity re-QA javítások

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: csak `spec/migrations/005_arch_01_pipeline.sql` és
`fewa-v3-backend/tests/test_arch01_migration.py`. S3/in-flight, Compose,
Dockerfile, route, Nginx, deploy és secret érintetlen.

QA 10:44 JAVÍTÁSOK:

1. **Verified artifact/version binding:** a publish lifecycle trigger csak
   akkor fogad el release decisiont, ha `rd.artifact_id =
   snapshot.artifact_id`, az artifact a snapshothoz tartozik, `verified_at`
   nem NULL, `readback_sha256 = sha256`, validator report létezik, és a
   decision `artifact_sha256` pontosan egyezik a tárolt SHA-256-tal. Puszta
   kliens hash szöveg vagy másik artifact nem publikálhat.
2. **Első domain dual gate:** az első, még publikált snapshot nélküli domain
   release-je DB-szinten külön, aktív `curator` és `admin` principal ID-t kér;
   null, azonos vagy rossz szerepű approval fail-closed. A domain összevetés a
   site domain normalizált (`www.` nélküli) értéke alapján történik.
3. **Tényleges source checksum:** a ledger nem hardcoded hash-et ír. Phase B a
   runner által megadott `arch01.migration_source_path` read-only forrásfájlt
   SHA-256-olja; az izolált fixture fallbackje `/workspace/spec/migrations/
   005_arch_01_pipeline.sql`. Hiányzó/olvashatatlan source path fail-closed.
   A futáskor a `schema_migrations.checksum` és az actual
   `sha256sum 005_arch_01_pipeline.sql` egyaránt
   `2cfdb76d631510370ee7bb502bf1a53f6e3b41547131b5fa8ba4ab65212ad0da`.

FUTTATÁS:

- Isolated, read-only source-mounted `pgvector/pgvector:pg16` PostgreSQL 16
  fresh DB + `ARCH01_QA_DATABASE_URL=... pytest -q
  tests/test_arch01_s1_qa_regressions.py` → **`7 passed in 0.46s`**.
- Fresh ledger query és host `sha256sum` → ugyanaz a fenti 64-hexa checksum.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül → **`9 passed, 7 skipped
  in 0.26s`** (QA DB suite szándékosan opt-in).
- Pipeline regresszió (`extraction`, `ner`, `summary`, `embedding`,
  `qc_dedup`, `main`) → **`13 passed in 0.68s`**.
- Isolated pre-005 nyolc lifecycle fixture, `005`, majd teljes `005` retry →
  **PASS**: `8` mapping, `1` grandfathered release, `3` reapproval candidate,
  ledger checksum current source-szal egyezik.
- OpenAPI full YAML parse → **45 schema, 25 path**; `git diff --check` az
  engedélyezett S1 fájlokra → **PASS**.

ISMERT HIÁNY / KÖVETKEZŐ CÍMZETT: **GPT QA.** A ledger rekord most a tényleges
read-only migration source tartalmát rögzíti; a még nem S1-owned executable
migration runnernek kell a session advisory lockot, saját connectiont,
outer-transaction elutasítást és `arch01.migration_source_path` beállítását
biztosítania. Ez nem Compose- vagy route-változás ebben a slice-ban. Kérlek,
futtasd újra a teljes 7 DB regressziót, fresh és 004->005/retry kört. Sonnet
verdictet nem állítok ki.

## [2026-08-13 10:44 UTC] GPT QA — ARCH-01 S1 fix re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE**. Ez nem Sonnet-verdict és nem deploy-
engedély. Production/spec fájlt nem módosítottam. A már meglévő QA-only
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` fájlban a pozitív
release fixture-t teljes, verified artifact + curator/admin adatra szigorítottam,
és két új reprodukciós tesztet adtam a kódaudit során talált fennmaradó
bypassokhoz.

RE-QA EREDMÉNY:

- Az előző öt reprodukció **mind zöld**: direct published INSERT tiltott;
  null-actor grandfather rekord nem jogosít publishra; a teljes valid release
  ugyanabban a tranzakcióban `release_state='released'` és pontosan 1 outbox
  sort hoz létre; manual origin/state rewrite tiltott; depth-3 hold
  hitelesítés nélküli aktiválása tiltott.
- A kibővített, 7 tesztes valódi PostgreSQL kör eredménye azonban **5 passed,
  2 failed**, ezért az S1 gate nem zárható.

FENNMARADÓ BLOKKOLÓK:

1. **Kritikus — nincs artifact/version binding.** Egy
   `qc_passed_pending_release` snapshot teljes curator/admin mezőkkel is
   publikálható úgy, hogy sem a snapshotnak, sem a release decisionnek nincs
   `artifact_id` értéke és a megadott `artifact_sha256` mögött nincs artifacts
   rekord. A lifecycle trigger csak a nem-null hash szöveget vizsgálja; nem
   követeli meg, hogy `rd.artifact_id = snapshot.artifact_id`, a referenced
   artifact a snapshothoz tartozzon, verified legyen, és a tárolt SHA egyezzen.
   Reprodukció:
   `test_release_must_bind_the_snapshots_current_verified_artifact` ->
   **DID NOT RAISE**.
2. **Kritikus — first-domain két-személyes gate hiányzik.** Egy teljesen új
   domain első snapshotja egyetlen aktív curator `actor_id`-jával, null
   `curator_id`/`admin_id` mezőkkel publikálható. A két szerep ellenőrzése csak
   `decision_origin='g4_override'` esetén fut; az ADR-0002 szerint viszont új
   eTLD+1/domain első snapshotjánál hard-gate pass mellett is két külön aktív
   curator/admin szükséges. Reprodukció:
   `test_first_domain_release_cannot_use_one_principal` -> **DID NOT RAISE**.
3. **Magas — a ledger checksum nem a vizsgált source fájl hash-e.** A DB
   `schema_migrations.checksum` értéke
   `b62cb368c736c0edfa2c8f7444d724957f456c9817c88d1a334bac37abf0cd8f`,
   miközben `sha256sum spec/migrations/005_arch_01_pipeline.sql` eredménye
   `0768ccd992533cfde614374badfaf291b8ca56eafff39a7a18101815e20cdbfb`.
   A Phase-B sor és immutability trigger létezik, de a helyi migráció nem
   igazolja saját tényleges forrását; a Builder-handoff is rögzíti, hogy a
   source-checksumot ellenőrző runner még nem létezik. Ezt a későbbi runnernek
   valódi, runner által számított és DB-vel összevetett identitássá kell tennie.

POZITÍV DB-BIZONYÍTÉK:

- Fresh PostgreSQL 16 `schema + seed + 001..005` sikeresen lefutott; ledger
  sor: `005:enum_phased`.
- Pre-005 nyolc lifecycle fixture frissítése helyes: 8 mapping; 3 reapproval
  candidate; 1 grandfathered release; published és withdrawn megőrzött;
  minden más normatív holdba került.
- Depth 2 aktív revisiont kapott; depth 3 és 5 változatlan maradt és `on_hold`
  lett. A teljes 005 második futása után a számlálók változatlanok:
  `8|1|3|2|1` = mapping | grandfathered release | legacy candidate | hold |
  ledger.
- A teljes verified artifacttal, külön curator/admin mezőkkel létrehozott
  release pozitív út `released` állapotot és 1 outbox sort adott.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-reqa-db -e POSTGRES_DB=arch01qa -e
  POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p 55432:5432 -v
  /srv/projects/webarchivum:/workspace:ro pgvector/pgvector:pg16`, majd
  `psql -q -v ON_ERROR_STOP=1` sorrendben `spec/schema.sql`, seed,
  `001..005` -> **fresh PASS**, ledger
  `005:enum_phased:b62cb368...`.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55432/arch01qa
  pytest -q tests/test_arch01_s1_qa_regressions.py` az eredeti öt teszttel ->
  **5 passed in 0.30s**.
- Ugyanez a parancs a teljes release-adatot auditáló két új QA-teszttel ->
  **5 passed, 2 failed in 0.48s**; a két failure a fenti artifact-binding és
  first-domain dual-review bypass.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py` ->
  **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.69s**.
- Külön `arch01upgrade` DB-n schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, majd `005` kétszer `ON_ERROR_STOP=1` mellett ->
  **upgrade PASS, retry PASS**, végső számláló `8|1|3|2|1`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 7 skipped
  in 0.26s** (DB QA szándékosan izolált DSN-re opt-in).
- `sha256sum spec/migrations/005_arch_01_pipeline.sql` ->
  `0768ccd992533cfde614374badfaf291b8ca56eafff39a7a18101815e20cdbfb`, nem
  egyezik a ledger értékével.
- `git diff --check -- fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py
  COLLAB_GEMINI.md` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**. Kötelező javítás: a runtime release
decisiont a snapshot aktuális, verified, azonos SHA-jú artifact/version
rekordjához kell kötni; az új domain első snapshotjánál DB-szinten két külön,
aktív, megfelelő curator/admin principal szükséges. A checksum-ledger valódi
source-integritását a runner ownership handoffban explicit, futtatható gate-ként
kell lezárni. Ezután GPT QA újrafuttatja mind a 7 DB regressziót, fresh és
004->005/retry kört. **SG-S1 Sonnet final review csomag nincs**, mert a
candidate nem elfogadott.

## [2026-08-13 11:03 UTC] GPT QA — ARCH-01 S1 integrity fix re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE**. Ez nem Sonnet-verdict és nem deploy-
engedély. Production/spec fájlt nem módosítottam. Egy új, reprodukáló QA-only
regresszió került a meglévő
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` fájlba.

KÖTELEZŐ HÉT ACCEPTANCE EREDMÉNYE:

1. Direct `published/released` snapshot INSERT: **tiltott**.
2. Null-actor `legacy_grandfathered` rekord runtime publish credentialként:
   **tiltott**.
3. Teljes, ugyanazon tranzakcióban írt release decision + lifecycle transition:
   **PASS**, `release_state='released'` és pontosan 1 outbox sor.
4. Current verified artifact binding hiánya / puszta kliens SHA: **tiltott**.
5. First-domain egy-személyes release: **tiltott**; distinct aktív curator és
   admin szükséges.
6. Manual candidate origin/state direct rewrite: **tiltott**.
7. Depth-3 hold hitelesítés nélküli aktiválása: **tiltott**.

Az előírt hét eset izolált PostgreSQL 16-on **7 passed in 0.44s**. A fresh és
upgrade ledger checksum bitre egyezett a ténylegesen futtatott 005 source
SHA-256 értékével:
`2cfdb76d631510370ee7bb502bf1a53f6e3b41547131b5fa8ba4ab65212ad0da`.
Eltérő runtime source path/hash mellett a retry fail-closed
`ARCH-01 migration 005 checksum mismatch` hibát adott.

ÚJ BLOKKOLÓ — ARTIFACT VERSION IMMUTABILITY:

- A publish pillanatában fennálló artifact/hash kötés helyes, de nem marad
  igaz. Egy teljesen valid, released snapshothoz tartozó `artifacts` rekord
  `object_version_id` mezője közvetlen SQL UPDATE-tel utólag szabadon
  átírható (`v1 -> v2-after-release`). A lifecycle továbbra `published`, a
  release state továbbra `released`, az immutable release decision ugyanarra
  az artifact UUID-ra mutat, de az UUID mögötti objektumverzió már más.
- Ez megsérti az ADR-0002 immutable artifact/version reference követelményét,
  és a Builder 10:52-es „verified artifact/version binding” állítását. A
  `release_decisions` immutability önmagában nem elég, ha a hivatkozott
  artifacts rekord vagy a published snapshot `artifact_id` kötése mutálható.
- Új reprodukció:
  `test_released_artifact_version_reference_is_immutable` -> **DID NOT
  RAISE**. A teljes kibővített DB suite eredménye ezért **7 passed, 1 failed
  in 0.59s**.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-integrity-qa -e
  POSTGRES_DB=arch01qa -e POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p
  55433:5432 -v /srv/projects/webarchivum:/workspace:ro
  pgvector/pgvector:pg16`, majd `psql -q -v ON_ERROR_STOP=1` sorrendben
  `spec/schema.sql`, seed, `001..005` -> **fresh PASS**.
- Host `sha256sum spec/migrations/005_arch_01_pipeline.sql` és DB
  `SELECT checksum FROM schema_migrations WHERE version='005'` összevetése ->
  **CHECKSUM_MATCH
  2cfdb76d631510370ee7bb502bf1a53f6e3b41547131b5fa8ba4ab65212ad0da**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55433/arch01qa
  pytest -q tests/test_arch01_s1_qa_regressions.py` a kért 7 esettel ->
  **7 passed in 0.44s**; az új immutability regresszió hozzáadása után ->
  **7 passed, 1 failed in 0.59s**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py` ->
  **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.69s**.
- Külön `arch01upgrade` DB: schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, majd a teljes `005` kétszer `ON_ERROR_STOP=1` mellett
  -> **upgrade PASS, retry PASS**. Végső számláló:
  `8|1|3|2|1|2cfdb76d...` = mapping | grandfathered release | legacy
  candidate | hold | ledger | checksum. Mapping:
  candidate/approved/crawling/archived/indexed/deprecated ->
  `migration_hold/held`, published -> `published/released`, withdrawn ->
  `withdrawn/withdrawn`; policy: `2>active,3>on_hold,5>on_hold`.
- `docker exec -e PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'
  ... psql -v ON_ERROR_STOP=1 -f
  /workspace/spec/migrations/005_arch_01_pipeline.sql` -> **EXPECTED REJECT**:
  `ARCH-01 migration 005 checksum mismatch`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 8 skipped
  in 0.25s**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**. Tegye DB-szinten immutábilissá a released
decision által hivatkozott artifact lényegi mezőit (`snapshot_id`, object key,
`object_version_id`, SHA/readback/validator/verified adatok), és akadályozza
meg egy published snapshot `artifact_id` kötésének utólagos cseréjét. A javítás
után GPT QA a teljes 8 DB-regressziót, fresh és 004->005/retry kört újrafuttatja.
**SG-S1 Sonnet final-review csomag nincs**, mert a candidate nem elfogadott.

## [2026-08-13 12:37 UTC] GPT QA — append-order canonical handoff

MODEL=gpt-5.6-sol; REASONING=high

VERDICT: **JAVÍTÁS KÉRVE**; NEXT OWNER: **S1 Builder**. Ez a fájl valódi
végéhez írt canonical pointer a részletes, append-only `12:36 UTC` GPT QA
blokkhoz (a párhuzamos írások miatt az a Builder blokkok elé került, tartalma
nem lett átírva vagy törölve).

A 12:36-os részletes evidence változatlanul irányadó: az előírt **9 DB / 9 S1
/ 13 pipeline** teszt zöld; fresh, `004->005`, retry, source-checksum match és
checksum-drift rejection zöld; withdrawal után historical artifact mutation és
snapshot relink tiltott, `release_state='withdrawn'` helyes. A fennmaradó
blokkoló reprodukció viszont direct SQL-lel igazolta:
`withdrawn|withdrawn|null actor|0 withdrawal outbox|0 withdrawal decision`;
az új `test_withdrawal_rejects_null_actor_and_missing_atomic_decision` ezért
**DID NOT RAISE**, a kibővített DB-suite **9 passed, 1 failed in 0.68s**.

Kötelező javítás: withdrawal csak ugyanazon tranzakcióban írt authenticated,
nem-null actor + reason + idempotent withdrawal decisionnel mehessen, és írjon
deduplikálható withdrawal outboxot; lifecycle-only/null-actor út fail-closed.
**SG-S1 Sonnet final-review csomag nincs**, mert ez a candidate nem elfogadott.

## [2026-08-13 12:36 UTC] GPT QA — ARCH-01 S1 withdrawal fix re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE**. Ez nem Sonnet-verdict és nem deploy-
engedély. Production/spec fájlt nem módosítottam; egy új, reprodukáló QA-only
tesztet adtam a meglévő
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` fájlhoz.

ELŐÍRT GATE-EK — MIND ZÖLD:

- A teljes, handoffban kért kilences izolált PostgreSQL 16 DB suite:
  **9 passed in 0.58s**.
- S1 migration + contract: **9 passed in 0.22s**.
- Pipeline regresszió: **13 passed in 0.72s**.
- Fresh schema + seed + `001..005`: **PASS**; host source SHA és ledger
  checksum egyezik:
  `a3318ae0202613bcfbff63128e51c468220c464a4e86c6ad3ee5a9083c4f62cf`.
- `004 -> 005` nyolc lifecycle + depth 2/3/5 fixture és teljes `005` retry:
  **PASS**, végső számláló `8|1|3|2|1|a3318ae...` = mapping |
  grandfathered release | legacy candidate | hold | ledger | checksum.
- Eltérő runtime source path/hash: **EXPECTED REJECT**,
  `ARCH-01 migration 005 checksum mismatch`.

WITHDRAWAL/HISTORIC INTEGRITY KÓDAUDIT:

- `published -> withdrawn` után a snapshot most helyesen, egyetlen DB UPDATE
  commitban `lifecycle_status='withdrawn'` és `release_state='withdrawn'`.
- A történeti `release_decisions(outcome='released')` artifact referenciája
  withdrawal után is védi a release-hez kötött artifact identity/integrity
  mezőit: `object_version_id` direct UPDATE **EXPECTED_REJECT**.
- A történeti released decision withdrawal után is védi a snapshot
  `artifact_id` kötését: relink/nullázás **EXPECTED_REJECT**.
- Pre-release artifact unbind/mutate/rebind a korábbi célzott körben továbbra
  **EXPECTED_ACCEPT**, tehát a normál capture-integrity előkészítés nem fagyott
  be.

ÚJ BLOKKOLÓ — A WITHDRAWAL AUTHORIZATION/OUTBOX TOVÁBBRA IS MEGKERÜLHETŐ:

- Egy valid released snapshot direct SQL `published -> withdrawn` átmenete
  üres `arch01.actor_id` mellett sikeres. Eredmény:
  `withdrawn|withdrawn|null withdrawal_actor|0 withdrawal_outbox|0
  withdrawal_decisions`.
- Vagyis a két állapotmező ugyan atomikusan változik, de a DB nem követeli meg
  az ADR-0002 által explicit előírt nem-null authenticated withdrawal actort,
  idempotency/decision evidence-et, és nem ír ugyanabban a commitban
  deduplikálható withdrawal outbox eseményt. A lifecycle audit sor
  `triggered_by` értéke null, a consumer/reconciler pedig nem kap eseményt.
- Új reprodukció:
  `test_withdrawal_rejects_null_actor_and_missing_atomic_decision` ->
  **DID NOT RAISE**. A kibővített DB suite: **9 passed, 1 failed in 0.68s**.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-withdrawal-qa -e
  POSTGRES_DB=arch01qa -e POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p
  55435:5432 -v /srv/projects/webarchivum:/workspace:ro
  pgvector/pgvector:pg16`, majd `psql -q -v ON_ERROR_STOP=1` sorrendben
  `spec/schema.sql`, seed, `001..005` -> **FRESH_PASS CHECKSUM_MATCH
  a3318ae0202613bcfbff63128e51c468220c464a4e86c6ad3ee5a9083c4f62cf**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55435/arch01qa
  pytest -q tests/test_arch01_s1_qa_regressions.py` a kért 9 esettel ->
  **9 passed in 0.58s**; az új null-actor withdrawal teszttel -> **9 passed,
  1 failed in 0.68s**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py` ->
  **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.72s**.
- Külön `arch01upgrade` DB, schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, majd `005` kétszer -> **UPGRADE_RETRY_CHECKSUM_MATCH
  a3318ae0202613bcfbff63128e51c468220c464a4e86c6ad3ee5a9083c4f62cf**;
  számláló `8|1|3|2|1|a3318ae...`.
- `docker exec -e PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'
  ... psql -v ON_ERROR_STOP=1 -f
  /workspace/spec/migrations/005_arch_01_pipeline.sql` -> **EXPECTED REJECT**:
  `ARCH-01 migration 005 checksum mismatch`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 10 skipped
  in 0.26s**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**. A withdrawal kizárólag ugyanazon
tranzakcióban létrejött, nem-null aktív actorhoz és nem üres reasonhöz kötött,
idempotens withdrawal decisionnel mehessen; az állapot/lifecycle audit mellett
ugyanabban a commitban írjon deduplikálható withdrawal outbox eseményt. Null
actor, korábbi release decision vagy lifecycle-only UPDATE fail-closed legyen.
A javítás után GPT QA a teljes 10 DB-regressziót és minden fenti gate-et
újrafuttatja. **SG-S1 Sonnet final-review csomag nincs**, mert a candidate nem
elfogadott.

## [2026-08-13 11:34 UTC] S1 BUILDER — ARCH-01 / released artifact immutability

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: kizárólag `spec/migrations/005_arch_01_pipeline.sql` és a
meglévő `fewa-v3-backend/tests/test_arch01_migration.py`. S3/in-flight,
Compose, Dockerfile, route, Nginx, deploy és secret érintetlen.

QA 11:03 JAVÍTÁS:

- Új DB trigger a published/released snapshot által hivatkozott artifacton
  tiltja a `snapshot_id`, object key, `object_version_id`, SHA-256,
  filesize, readback SHA, validator report és `verified_at` direct update-jét.
  Így a release decision UUID-ja mögötti object-version és integritási rekord
  release után nem cserélhető ki.
- Új snapshot trigger tiltja a `published/released` snapshot `artifact_id`
  relinkjét. Release előtti `artifact_id` kapcsolás továbbra megengedett, így
  a verified artifact → release tranzakció nem sérül.

FUTTATÁS:

- Isolated, read-only source-mounted `pgvector/pgvector:pg16` PostgreSQL 16
  fresh DB + `ARCH01_QA_DATABASE_URL=... pytest -q
  tests/test_arch01_s1_qa_regressions.py` → **`8 passed in 0.51s`**.
- Ledger checksum fresh DB-ben és host `sha256sum` azonos:
  `55021b58c3b21b462aede51719898aef987bc1e4f2c403781dcd1d52c61b3311`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül → **`9 passed, 8 skipped
  in 0.27s`** (DB QA suite szándékosan opt-in).
- Pipeline regresszió (`extraction`, `ner`, `summary`, `embedding`,
  `qc_dedup`, `main`) → **`13 passed in 0.71s`**.
- Isolated 004->005 nyolc lifecycle fixture + teljes 005 retry → **PASS**:
  `8` mapping, `1` grandfathered release, `3` reapproval candidate, ledger
  checksum source-szal egyezik.
- `git diff --check` a megengedett S1 fájlokra → **PASS**.

ISMERT HIÁNY / KÖVETKEZŐ CÍMZETT: **GPT QA.** Kérlek futtasd újra a teljes
8-es DB regressziót, fresh és 004->005/retry kört. A session advisory-lockos,
outer-transactiont visszautasító executable migration runner továbbra nem S1
fájltulajdon; a DB ledger és tényleges source-checksum gate készen áll hozzá.
Sonnet verdictet nem állítok ki.

## [2026-08-13 12:32 UTC] S1 BUILDER — ARCH-01 / withdrawal historical integrity

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: csak `spec/migrations/005_arch_01_pipeline.sql` és
`fewa-v3-backend/tests/test_arch01_migration.py`. S3/in-flight, Compose,
Dockerfile, route, Nginx, deploy és secret érintetlen.

JAVÍTÁS:

- Artifact immutability már nem az aktuális `published/released` státuszt,
  hanem a snapshothoz kötött, meglévő `released` ARCH-01 decisiont vizsgálja.
  Emiatt egy későbbi withdrawal sem nyitja vissza a historical object key,
  `object_version_id`, SHA/readback/validator/verified mezőket.
- Snapshot `artifact_id` relink ugyanígy a historic release decisionhez kötött,
  ezért `withdrawn` lifecycle után sem cserélhető ki vagy nullázható a release
  evidence.
- A megengedett `published → withdrawn` lifecycle tranzakció most konzisztensen
  `release_state='withdrawn'` értéket állít. A withdrawal üzleti út továbbra
  használható, de nem gyengíti a megőrzött artifact-evidence kötést.

FUTTATÁS:

- Isolated, read-only source-mounted PG16 + teljes
  `test_arch01_s1_qa_regressions.py` → **`9 passed in 0.62s`** (az új
  withdrawal utáni artifact-version mutáció tiltott; withdrawal maga sikeres).
- S1 test kör DSN nélkül → **`9 passed, 9 skipped in 0.27s`** (a DB QA suite
  szándékosan opt-in).
- Pipeline regresszió → **`13 passed in 0.72s`**.
- Fresh és pre-005 nyolc lifecycle fixture `005` + retry → **PASS**:
  `8` mapping, `1` grandfathered release, `3` reapproval candidate, checksum
  a mounted source-szal egyezik.
- Aktuális 005 SHA-256:
  `a3318ae0202613bcfbff63128e51c468220c464a4e86c6ad3ee5a9083c4f62cf`.
  `git diff --check` a megengedett S1 fájlokra → **PASS**.

KÖVETKEZŐ CÍMZETT: **GPT QA.** Kérlek futtasd a teljes 9 DB regressziót,
fresh és 004->005/retry/checksum kört. Sonnet final review még nincs kérve.

## [2026-08-13 12:39 UTC] S1 BUILDER — ARCH-01 / atomic withdrawal decision gate

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)

ÉRINTETT FÁJLOK: csak `spec/migrations/005_arch_01_pipeline.sql`,
`fewa-v3-backend/tests/test_arch01_migration.py`, és a QA regressziós pozitív
withdrawal fixture-je (`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`)
frissült a most kötelező, legitim withdraw decision útvonalra. S3/in-flight,
Compose, Dockerfile, route, Nginx, deploy és secret érintetlen.

JAVÍTÁS:

- A `release_decisions.operation` most explicit `withdraw` értéket is kezel.
  `published → withdrawn` lifecycle transition kizárólag ugyanabban a DB
  tranzakcióban beszúrt `operation='withdraw'`, `outcome='withdrawn'`, aktív
  actorral, nem üres indokkal, idempotency key-jel és request/response hash-ekkel
  rendelkező immutable decision mellett érvényes.
- Lifecycle-only vagy null-actor withdrawal DB-hiba. A legitim transition
  `release_state='withdrawn'`-t, audit actor-t és deduplikált
  `snapshot.withdrawn` transactional outbox rekordot ír egy commitban.
- A historical artifact/version és snapshot artifact binding immutability a
  withdrawal után továbbra változatlanul érvényes.

FUTTATÁS:

- Isolated, read-only source-mounted PG16 + teljes
  `test_arch01_s1_qa_regressions.py` → **`10 passed in 0.70s`**. A valid
  withdrawal decision út létrehozza a withdrawn outboxot; a direct null-actor
  lifecycle withdrawal fail-closed.
- S1 kör DSN nélkül → **`9 passed, 10 skipped in 0.27s`** (a DB QA suite
  szándékosan opt-in).
- Pipeline regresszió → **`13 passed in 0.70s`**.
- Fresh és isolated pre-005 nyolc lifecycle fixture `005` + teljes retry →
  **PASS**: `8` mapping, `1` grandfathered release, `3` reapproval candidate,
  checksum current source-szal egyezik.
- Aktuális 005 SHA-256:
  `e690edff753c84db636303e7ac56dd406e89c9261a68113ddb4996a66c67af06`.
  `git diff --check` az engedélyezett S1 fájlokra → **PASS**.

KÖVETKEZŐ CÍMZETT: **GPT QA.** Kérlek futtasd újra a teljes 10-es DB
regressziót, fresh és 004->005/retry/checksum kört. Sonnet final review továbbra
nem kérhető QA `ELFOGADVA` előtt.

## [2026-08-13 12:30 UTC] GPT QA — ARCH-01 S1 final integrity re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE**. Ez nem Sonnet-verdict és nem deploy-
engedély. Production/spec fájlt nem módosítottam; egy új, reprodukáló QA-only
tesztet adtam a meglévő
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` fájlhoz.

KÖTELEZŐ GATE-EK — MIND ZÖLD:

- A teljes, kért nyolcas izolált PostgreSQL 16 suite: **8 passed in 0.53s**.
  Direct published INSERT, grandfather/null actor, atomic release/outbox,
  current verified artifact binding, first-domain dual principal, released
  artifact version mutation, manual rewrite és depth hold bypass mind tiltott.
- S1 migration + contract: **9 passed in 0.22s**.
- Releváns pipeline regresszió: **13 passed in 0.69s**.
- Fresh schema + seed + `001..005`: **PASS**. Host source SHA és ledger
  checksum egyezik:
  `55021b58c3b21b462aede51719898aef987bc1e4f2c403781dcd1d52c61b3311`.
- `004 -> 005` nyolc lifecycle + depth 2/3/5 fixture és teljes 005 retry:
  **PASS**. Végső számláló `8|1|3|2|1|55021b58...` = mapping |
  grandfathered release | legacy candidate | hold | ledger | checksum.
  Mapping: candidate/approved/crawling/archived/indexed/deprecated ->
  `migration_hold/held`, published -> `published/released`, withdrawn ->
  `withdrawn/withdrawn`; policy: `2>active,3>on_hold,5>on_hold`.
- Eltérő runtime source path/hash: **EXPECTED REJECT**, `ARCH-01 migration 005
  checksum mismatch`.
- Kódaudit direct-SQL mezőmátrix: a currently published/released artifact
  `snapshot_id`, object key, object version, SHA, filesize, readback SHA,
  validator report és verified time mezője külön-külön **EXPECTED_REJECT**;
  published snapshot artifact relink **EXPECTED_REJECT**; pre-release
  unbind/mutate/rebind **EXPECTED_ACCEPT**.

ÚJ BLOKKOLÓ — WITHDRAWAL UTÁN ELVÉSZ A TÖRTÉNETI RELEASE BINDING:

- A guardok csak olyan artifactot védenek, amelyre pillanatnyilag egy
  `lifecycle_status='published' AND release_state='released'` snapshot mutat.
  Egy valid release után a megengedett `published -> withdrawn` transition
  sikeres, de `release_state` hibásan **`released` marad**, nem vált
  `withdrawn`-ra.
- Ezután ugyanazon, immutable released decision által hivatkozott artifact
  `object_version_id` mezője direct SQL-lel sikeresen átírható
  (`v1 -> v3-after-withdrawal`), és a withdrawn snapshot `artifact_id` mezője
  más artifact UUID-ra relinkelhető. Így az immutable történeti release
  evidence ismét más objektumverzióra mutat; a fix csak az aktuálisan publikált
  állapotot védi, nem a released decision által rögzített identitást.
- Új reprodukció:
  `test_withdrawal_preserves_released_artifact_identity` -> **DID NOT RAISE**.
  A kibővített teljes DB suite eredménye: **8 passed, 1 failed in 0.61s**.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-final-qa -e POSTGRES_DB=arch01qa -e
  POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p 55434:5432 -v
  /srv/projects/webarchivum:/workspace:ro pgvector/pgvector:pg16`, majd
  `psql -q -v ON_ERROR_STOP=1` sorrendben `spec/schema.sql`, seed,
  `001..005` -> **FRESH_PASS CHECKSUM_MATCH 55021b58...**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55434/arch01qa
  pytest -q tests/test_arch01_s1_qa_regressions.py` a kért nyolc esettel ->
  **8 passed in 0.53s**; az új withdrawal-history teszttel -> **8 passed,
  1 failed in 0.61s**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py` ->
  **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.69s**.
- Külön `arch01upgrade` DB, schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, `005`, majd `005` retry -> **UPGRADE_RETRY_CHECKSUM_MATCH
  55021b58c3b21b462aede51719898aef987bc1e4f2c403781dcd1d52c61b3311**;
  számláló és mapping a fenti.
- `docker exec -e PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'
  ... psql -v ON_ERROR_STOP=1 -f
  /workspace/spec/migrations/005_arch_01_pipeline.sql` -> **EXPECTED REJECT**:
  `ARCH-01 migration 005 checksum mismatch`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 8 skipped
  in 0.26s**.
- `python3` + `yaml.safe_load(spec/openapi.yaml)` -> **OPENAPI_PARSE_PASS:
  45 schemas, 25 paths**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**. Az artifact immutability-t ne az aktuális
published snapshot státuszához, hanem bármely immutable `release_decisions`
`outcome='released'` artifact referenciájához kösse; az ilyen artifact
identity/integrity mezői withdrawal után is változtathatatlanok. A released
snapshot withdrawal transitionje atomikusan állítsa `release_state='withdrawn'`
értékre, és a történeti artifact binding withdrawal után se legyen relinkelhető.
Ezután GPT QA a teljes 9 DB-regressziót és minden fenti gate-et újrafuttatja.
**SG-S1 Sonnet final-review csomag nincs**, mert a candidate nem elfogadott.

## [2026-08-13 12:38 UTC] GPT QA — latest canonical verdict

MODEL=gpt-5.6-sol; REASONING=high

VERDICT: **JAVÍTÁS KÉRVE**; NEXT OWNER: **S1 Builder**. A részletes evidence a
fenti `12:36 UTC` GPT QA blokkban van. A kért 9 DB, 9 S1 és 13 pipeline teszt,
fresh/upgrade/retry/checksum gate zöld, továbbá a withdrawal utáni historic
artifact- és snapshot-binding immutábilis. A kibővített QA-suite új tizedik
tesztje viszont **FAIL**: null actor, withdrawal decision és withdrawal outbox
nélkül direct SQL withdrawal sikerül (`withdrawn|withdrawn|null|0|0`). A
withdrawalnak authenticated, idempotens, same-transaction decision + audit +
outbox műveletnek kell lennie; lifecycle-only út fail-closed. Sonnet final
review csomag nincs, amíg ez nem zöld.

## [2026-08-13 14:29 UTC] GPT QA — Sonnet findings #2–5 targeted re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE** kizárólag a Sonnet #2–5 S1 corrective
candidate-re. Ez nem Sonnet-verdict, nem production deploy-engedély és nem ad
all-cleart az Architect/Sonnet #1 DB-role/runner kérdésére. Az ADR §10–12,
R1 és a külön `006_arch_01_db_roles.sql` workstream továbbra is **NYITOTT ÉS
BLOKKOLÓ**, ezen QA-kör nem vizsgálta és nem fogadta el.

Production/spec fájlt nem módosítottam. Egy új reprodukáló QA-only tesztet
adtam a meglévő
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` fájlhoz.

ELŐÍRT GATE-EK:

- Friss, izolált PostgreSQL 16-on a Builder által átadott teljes 15 DB
  adversarial teszt: **15 passed in 0.97s**.
- S1 migration + contract: **9 passed in 0.22s**.
- Pipeline regresszió: **13 passed in 0.69s**.
- Fresh schema + seed + `001..005`: **PASS**; host source SHA és ledger
  checksum egyezik:
  `774b00ca5b81c06cfe3904ef75d08f595319fe1dbbf9c00fd34c7f5d7aa7fb86`.
- Pre-005 lifecycle/depth fixture, `005`, majd teljes `005` retry: **PASS**;
  végső számláló `8|1|3|2|1|774b00ca...` = mapping | grandfathered release |
  legacy candidate | policy hold | ledger | checksum.
- Eltérő runtime source path/hash: **EXPECTED REJECT**,
  `ARCH-01 migration 005 checksum mismatch`.
- DSN nélküli S1 kör: **9 passed, 16 skipped in 0.28s**.
- OpenAPI parse: **45 schemas, 25 paths**; manual request properties pontosan
  `immutable_submission_evidence`, `landing_url`, `submitter_rationale`.
  Pydantic explicit kliens `candidate_origin='manual'`: **REJECT PASS**;
  server-default nélkül létrehozott modell originje: **manual PASS**.

SONNET #2, #4, #5 — ZÖLD:

- Discovery/legacy candidate direct `curator_approved` UPDATE actor és policy
  nélkül tiltott; aktív actor önmagában policy nélkül is tiltott. A legitim
  manual `uncertain -> curator_approved` active site-policy revisionnel egy
  tranzakcióban approved snapshotot és pontosan egy `candidate.approved`
  outboxot hozott létre. Candidate state, policy, snapshot és outbox együtt
  rollbackolható DB-trigger tranzakcióban történik.
- Manual `landing_url`, `canonical_url`, host, eTLD+1 és content hash
  immutábilis; a legitim state transition kivétel csak változatlan submission
  identity mellett él.
- Pydantic `candidate_origin` `Literal['manual']`, explicit kliensmezőt a
  before-validator tilt; OpenAPI ezt a belső mezőt nem exponálja és
  `additionalProperties: false`, tehát a két contract igazodik.

FENNMARADÓ BLOKKOLÓ — SONNET #3 VERIFIED ARTIFACT KÉTLÉPCSŐS BYPASS:

- A `trg_arch01_verified_artifact_binding_immutable` ugyan `UPDATE OF
  ... verified_at` trigger, de az `arch01_reject_verified_artifact_rebind()`
  tiltott változáslistájából maga a `verified_at` változása kimaradt. Emiatt
  egy verified artifacton `UPDATE artifacts SET verified_at=NULL` sikeres.
- A következő tranzakcióban `OLD.verified_at` és `NEW.verified_at` is null,
  ezért a `snapshot_id` rebind is sikeres. Valódi PG16 reprodukcióban A
  snapshot verified artifactja így B snapshothoz került:
  `snapshot_id=...122 | verified_at=NULL |
  seed_url=https://artifact-unverify.example/b`.
- Új regresszió:
  `test_verified_artifact_cannot_be_unverified_then_rebound` -> **DID NOT
  RAISE**. A kibővített teljes DB-suite ezért **15 passed, 1 failed in
  1.08s**.
- Kötelező fix: ha `OLD.verified_at IS NOT NULL`, `verified_at` ne legyen
  nullázható vagy módosítható; a verification state és az összes identity/
  integrity mező onnantól monoton/immutable. Ezzel a kétlépcsős rebind út is
  fail-closed lesz.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-sonnet25-qa -e
  POSTGRES_DB=arch01qa -e POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p
  55437:5432 -v /srv/projects/webarchivum:/workspace:ro
  pgvector/pgvector:pg16`, majd `psql -q -v ON_ERROR_STOP=1` sorrendben
  `spec/schema.sql`, seed, `001..005` -> **FRESH_PASS CHECKSUM_MATCH
  774b00ca5b81c06cfe3904ef75d08f595319fe1dbbf9c00fd34c7f5d7aa7fb86**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55437/arch01qa
  pytest -q fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` a kért
  15 esettel -> **15 passed in 0.97s**; az új unverify/rebind regresszióval ->
  **15 passed, 1 failed in 1.08s**.
- `cd fewa-v3-backend && pytest -q tests/test_arch01_migration.py
  tests/test_arch01_contract.py` -> **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.69s**.
- Külön `arch01upgrade` DB, schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, `005`, majd `005` retry ->
  **UPGRADE_RETRY_CHECKSUM_MATCH
  774b00ca5b81c06cfe3904ef75d08f595319fe1dbbf9c00fd34c7f5d7aa7fb86**;
  számláló `8|1|3|2|1|774b00ca...`.
- `docker exec -e PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'
  ... psql -v ON_ERROR_STOP=1 -f
  /workspace/spec/migrations/005_arch_01_pipeline.sql` -> **EXPECTED REJECT**:
  `ARCH-01 migration 005 checksum mismatch`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 16 skipped
  in 0.28s**.
- `PYTHONPATH=.. python3` Pydantic/OpenAPI alignment script ->
  **OPENAPI_PARSE_PASS schemas=45 paths=25**,
  **PYDANTIC_EXPLICIT_ORIGIN_REJECT_PASS**,
  **PYDANTIC_SERVER_DEFAULT_MANUAL_PASS**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**, kizárólag a verified-at monotonic
immutability javítására, majd GPT QA teljes 16 DB + 9 S1 + 13 pipeline és
fresh/upgrade/retry/checksum re-QA. Teljes zöld esetén Sonnet 5 célzott
re-review csomag készül **csak a Sonnet #2–5 S1 javításokra**. Architect #1 /
R1 / 006 ettől függetlenül pending marad; semmilyen premature all-clear nincs.

## [2026-08-13 13:24 UTC] GPT QA — ARCH-01 S1 FINAL acceptance + SG-S1 packet

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **ELFOGADVA**. Ez a GPT QA S1 candidate verdictje, nem
Sonnet-verdict és nem production deploy-engedély. Production/spec fájlt ebben
a QA-körben nem módosítottam; csak a korábban létrehozott QA regressziós
tesztfájl marad a candidate része.

ELFOGADÁSI BIZONYÍTÉK:

- Izolált PostgreSQL 16-on a teljes adversarial DB suite: **10 passed in
  0.67s**.
- S1 migration + machine contract: **9 passed in 0.23s**.
- Releváns pipeline regresszió: **13 passed in 0.70s**.
- Fresh schema + seed + `001..005`: **PASS**; host source SHA és immutable DB
  ledger checksum pontosan egyezik:
  `e690edff753c84db636303e7ac56dd406e89c9261a68113ddb4996a66c67af06`.
- Pre-005 nyolc lifecycle + depth 2/3/5 fixture, `005`, majd teljes `005`
  retry: **PASS**. Végső számláló:
  `8|1|3|2|1|e690edff...` = legacy mapping | grandfathered release |
  legacy reapproval candidate | policy hold | ledger | checksum. Lifecycle
  mapping: candidate/approved/crawling/archived/indexed/deprecated ->
  `migration_hold/held`, published -> `published/released`, withdrawn ->
  `withdrawn/withdrawn`; policy mapping: `2>active,3>on_hold,5>on_hold`.
- Eltérő runtime source path/hash retry: **EXPECTED REJECT**,
  `ARCH-01 migration 005 checksum mismatch`.
- OpenAPI teljes YAML parse: **45 schemas, 25 paths**.
- QA test diff-check: **PASS**.

ADVERSARIAL INVARIÁNSOK — MIND ZÖLD:

1. Direct snapshot INSERT nem hozhat létre `published/released` állapotot.
2. Null-actor/legacy-grandfather record nem runtime publish credential.
3. Publish csak ugyanazon tranzakció teljes, aktív actorhoz kötött release
   decisionjével megy; `release_state='released'`, lifecycle audit és pontosan
   egy deduplikált `snapshot.released` outbox együtt jön létre.
4. Release az aktuális, ugyanahhoz a snapshothoz kötött, verified artifact
   UUID/version/SHA/readback/validator adataihoz kötött; puszta kliens hash vagy
   más artifact nem elég.
5. Új domain első snapshotjánál külön, aktív curator és admin kötelező;
   one-person/null/azonos principal tiltott.
6. Released decision után az artifact identity/integrity mezői immutábilisak;
   snapshot `artifact_id` relink tiltott, withdrawal után is. Pre-release
   artifact binding továbbra szerkeszthető, ezért a normál előkészítési út él.
7. Manual candidate immutable eredete/evidence/state nem írható át direct
   SQL-lel approval bypassra.
8. Depth 3--5 hold hitelesített curator reapproval/clearance nélkül nem
   aktiválható és crawl job nem hivatkozhat rá.
9. `published -> withdrawn` atomikusan `release_state='withdrawn'` értéket ad,
   a historical released artifact és snapshot binding megmarad immutábilisnak.
10. Lifecycle-only/null-actor withdrawal fail-closed. Valid withdrawal csak
    ugyanazon tranzakcióban írt aktív actor + nem üres reason + idempotency és
    request/response hash decisionnel megy; audit actor és pontosan egy
    deduplikált `snapshot.withdrawn` outbox ugyanabban a commitban keletkezik.

KÉZI POZITÍV WITHDRAWAL BIZONYÍTÉK:

- Egy teljes release, majd külön same-transaction withdrawal decision +
  lifecycle UPDATE után a DB eredménye:
  `withdrawn | withdrawn | 550e8400-e29b-41d4-a716-446655440000 | 1 | 1`
  = lifecycle | release_state | withdrawal audit actor | withdrawal outbox |
  withdrawal decision.
- Ezután artifact `object_version_id` mutation és snapshot artifact relink:
  mindkettő **EXPECTED_REJECT**. Egy ismételt `withdrawn -> withdrawn` no-op
  UPDATE nem duplikált eseményt, és elfogadott idempotens no-op maradt.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-atomic-final -e
  POSTGRES_DB=arch01qa -e POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p
  55436:5432 -v /srv/projects/webarchivum:/workspace:ro
  pgvector/pgvector:pg16`; readiness után `psql -q -v ON_ERROR_STOP=1`
  sorrendben `spec/schema.sql`, seed, `001..005` -> **FRESH_PASS
  CHECKSUM_MATCH e690edff753c84db636303e7ac56dd406e89c9261a68113ddb4996a66c67af06**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55436/arch01qa
  pytest -q fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` ->
  **10 passed in 0.67s**.
- `cd fewa-v3-backend && pytest -q tests/test_arch01_migration.py
  tests/test_arch01_contract.py` -> **9 passed in 0.23s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.70s**.
- Külön `arch01upgrade` DB: schema + seed + `001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, `005`, majd `005` retry -> **UPGRADE_RETRY_CHECKSUM_MATCH
  e690edff753c84db636303e7ac56dd406e89c9261a68113ddb4996a66c67af06**;
  számláló és mapping a fentiek szerint.
- `docker exec -e PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'
  ... psql -v ON_ERROR_STOP=1 -f
  /workspace/spec/migrations/005_arch_01_pipeline.sql` -> **EXPECTED REJECT**:
  `ARCH-01 migration 005 checksum mismatch`.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 10 skipped
  in 0.26s**.
- `python3` + `yaml.safe_load(spec/openapi.yaml)` -> **OPENAPI_PARSE_PASS:
  schemas=45 paths=25**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

SG-S1 FINAL SONNET REVIEW CSOMAG:

- **Review target / exact files:**
  `docs/adr/0002-arch-01-release-state-machine.md` (normative reference),
  `spec/migrations/005_arch_01_pipeline.sql`, `spec/pipeline_schemas.py`,
  `spec/openapi.yaml`,
  `fewa-v3-backend/tests/test_arch01_migration.py`,
  `fewa-v3-backend/tests/test_arch01_contract.py`,
  `fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`, valamint e fájl
  Builder/QA append-only evidence blokkjai.
- **Candidate diff shape:** új, versioned `005` migration és három új S1/QA
  tesztfájl; módosított Pydantic machine contract és OpenAPI. `git status`
  szerint ezek: `M spec/openapi.yaml`, `M spec/pipeline_schemas.py`, új
  `spec/migrations/005_arch_01_pipeline.sql`, új
  `test_arch01_migration.py`, `test_arch01_contract.py`,
  `test_arch01_s1_qa_regressions.py`. Más dirty worktree fájlok nem tartoznak
  az SG-S1 candidate-hez.
- **Sonnet kötelező visszaellenőrzése:** az ADR-0002 és korábbi SG checklist
  mind a 14 pontja, plusz a fenti 10 adversarial invariáns; különösen legacy
  publish/INSERT és null actor bypass, same-transaction release/withdrawal +
  audit/outbox, verified immutable artifact/version binding, first-domain dual
  gate, manual anti-bypass, depth hold, lossless 004 upgrade, enum-phased retry
  és runtime source checksum drift fail-closed.
- **Sonnet futtatandó bizonyíték minimum:** a fenti exact 10 DB, 9 S1 és 13
  pipeline parancs eredményeinek/diffjének független review-ja; szükség szerint
  ugyanazon izolált PG16 fixture reprodukciója. A production deploy, Compose,
  Nginx, secret és S2/S3 implementáció nincs e review scope-ban.

KÖVETKEZŐ CÍMZETT: **Sonnet 5 / SG-S1 FINAL REVIEW**. Adjon kizárólag
`ELFOGADVA` vagy tételes `JAVÍTÁS KÉRVE` verdictet a konkrét diff és a fenti
evidence alapján. GPT QA verdict: **ELFOGADVA**.

## [2026-08-13 13:39 UTC] SONNET 5 — SG-S1 FINAL REVIEW: JAVÍTÁS KÉRVE

MODEL=Sonnet 5; REASONING=high (teljes ADR-0002, a teljes 806 soros `005_arch_01_pipeline.sql`, mindkét kontraktus-fájl és mindhárom tesztfájl közvetlen elolvasása, plusz saját, önálló adversarial SQL friss, izolált PostgreSQL 16 konténeren — nem az öt korábbi QA-kör tesztjeinek megismétlése, hanem új támadási szögek keresése)

ÁLLAPOT: **JAVÍTÁS KÉRVE** (2 KRITIKUS, 1 MAGAS, 2 KÖZEPES — nem továbbítható a GPT release gate-nek ebben a formában)

**A korábbi 10 invariáns mind szilárd marad** — saját, a meglévő teszteknél szélesebb próbákkal is (multi-row INSERT, `COPY`, `ON CONFLICT DO UPDATE`, cross-transaction reuse, két admin curator nélkül, `legacy_grandfathered` `operation='release'`-lel) egyiket sem sikerült megkerülnöm. Fresh DB és 004→005 upgrade saját futtatásban is tiszta; a ledger checksum saját `sha256sum spec/migrations/005_arch_01_pipeline.sql` számítással bitre egyezik (`e690edff753c84db636303e7ac56dd406e89c9261a68113ddb4996a66c67af06`).

**De öt kört vizsgáló GPT QA egyike sem tesztelte a rendszer tényleges telepítési modelljét vagy a candidate/discovery állapotgépet — ezt saját magam vizsgáltam, és mindkét terület valódi, súlyos rést mutat.**

---

**1. KRITIKUS — az alkalmazás DB-szerepköre teljes PostgreSQL superuser; minden trigger egyetlen utasítással megkerülhető.**

`docker-compose.yml:9-11,67-69` — közvetlenül ellenőriztem: `POSTGRES_USER: fewa_user`, és ugyanaz a szerepkör csatlakozik az API/worker oldalról is. A hivatalos Postgres Docker image dokumentációja szerint a bootstrap `POSTGRES_USER` mindig **superuserként** jön létre — ez nem feltételezés, hanem a hivatalos image dokumentált viselkedése, saját magam is megerősítettem `pg_roles` lekérdezéssel egy azonos image/env-konfigurációjú konténeren: `rolsuper=t, rolbypassrls=t`.

A migrationban minden guard sima `BEFORE` row trigger, egyik sem `ENABLE ALWAYS TRIGGER`. Ordinary triggerek kikapcsolódnak, ha `session_replication_role = replica` — ezt a GUC-ot kizárólag superuser állíthatja, és `fewa_user` az. Ez azt jelenti, hogy **egyetlen** `SET session_replication_role = replica;` az adott tranzakción belül mind a 10 invariánst egyszerre hatástalanítja — nincs release_decision, nincs outbox, nincs audit, semmilyen kapu. Ez elérhető bármilyen jövőbeli "emergency fix" scripttel, admin tooling hibával, vagy SQL-injectionnel bárhol a stackben. Az ADR §1 alapkövetelménye ("PostgreSQL is the final authority") a ténylegesen telepített rendszerre nem igaz, mert az a fél, akit a triggereknek korlátozniuk kellene (az app), superuser jogot birtokol.

**Kért javítás:** dedikált, nem-superuser, nem-`BYPASSRLS` alkalmazási DB-szerepkör létrehozása, csak a szükséges DML jogokkal; `fewa_user` marad kizárólag migrációhoz/admin eszközökhöz fenntartva.

**2. KRITIKUS — a `discovery_candidates.state` átmeneteknek nincs semmilyen DB-szintű triggere; az ADR §8 kulcsmechanizmusa nincs megépítve, és mellékhatásként a manual candidate-ek örökre approve-olhatatlanok.**

Közvetlenül elolvastam `spec/migrations/005_arch_01_pipeline.sql:699-721` — ez az EGYETLEN trigger a `discovery_candidates` táblán. Két, egymással ellentétes hibát találtam, mindkettőt magam is megerősítettem a triggerfüggvény szövegéből:

- A `discovery`-eredetű (és `legacy_migration`-eredetű) candidate-ekre a trigger feltétele (`OLD.candidate_origin = 'manual'`) sosem teljesül — tehát **semmilyen** ellenőrzés nincs egy `UPDATE discovery_candidates SET state='curator_approved'` hívásra, hitelesítés, actor vagy policy-revision nélkül sem. Ez pontosan az az útvonal, amit az ADR §8 utolsó bekezdése explicit véd ("Only the DB-authorised curator transition... may atomically create a new snapshot").
- A `manual`-eredetű candidate-ekre viszont a trigger `OLD.state <> NEW.state`-et is az immutability-feltételek közé veszi (703. sor), kivétel nélkül — tehát a `uncertain → curator_approved` legitim átmenet is `ARCH-01 manual candidate provenance is immutable` hibával bukik. A dokumentált kurátori workflow emiatt **soha nem hajtható végre** manual candidate-re.

Nettó hatás: pontosan az a candidate-típus, amit az ADR §8 kifejezetten gátolni akart (manual beadás) sosem approve-olható, míg a magasabb kockázatú, automatizált/LLM-alapú típusok (discovery/legacy_migration) **nulla** DB-szintű jóváhagyási kapuval rendelkeznek.

**Kért javítás:** új trigger a `discovery_candidates.state` átmenetekre, `trg_lifecycle_guard` mintájára — `uncertain → curator_approved` csak hitelesített curator/admin actor és aktív approved policy revision mellett, atomikusan snapshot-létrehozással; plusz kivétel a `trg_arch01_manual_candidate` immutability-ellenőrzésébe erre az egy átmenetre.

**3. MAGAS — egy már verifikált, de még nem release-elt artifact átköthető más snapshothoz, és ott release-elhető: egyik site tényleges crawl-tartalma "mosható" egy másik site publikálásaként.**

Közvetlenül ellenőriztem `spec/migrations/005_arch_01_pipeline.sql:404-420` — az immutability guard kizárólag `WHERE rd.outcome = 'released'` esetén tiltja az `artifacts.snapshot_id` módosítását. Egy verifikált, de MÉG release-hez nem kötött artifact `snapshot_id`-je szabadon átírható. Az SG-S1 review saját reprodukciója: A site verifikált artifactját B site-hoz kötötte, B-re teljes, valid kétszemélyes release decisiont hozott létre, majd publikálta B-t — a végeredmény B `published/released` állapotban, de A tényleges WACZ objektumával. A korábbi QA jelentés (COLLAB_GEMINI.md 1949-1951. sor) ezt explicit "pre-release artifact binding remains editable" néven a normál előkészítési útnak minősítette, sosem tesztelte cross-snapshot swap ellen.

**Kért javítás:** `artifacts.snapshot_id` (és a readback/verified mezők) tegye immutábilissá már `verified_at IS NOT NULL` esetén, ne csak released után — vagy a publish-gate ellenőrizze, hogy az artifact ugyanahhoz a snapshot saját crawl jobjához lett verifikálva.

**4. KÖZEPES — manual candidate `landing_url`/`canonical_url` release/approval után is szabadon módosítható, az ADR "immutable" állítása ellenére.**

Közvetlenül ellenőriztem: a védett-oszlop lista (`005_arch_01_pipeline.sql:702-707`) nem tartalmazza a `landing_url`/`canonical_url` mezőket. Egy kurátor, aki "mit nyújtottak be" alapján dönt, egy utólag csendben kicserélt URL-t láthat.

**Kért javítás:** `landing_url`/`canonical_url` (ideálisan `host`/`etld_plus_one`/`content_sha256` is) felvétele az immutable-oszlop listába.

**5. KÖZEPES (kontraktus-réteg, ma nem elérhető, de a következő route-hoz hibás handoff) — `DiscoveryCandidateSubmission.candidate_origin` nincs `manual`-ra zárva.**

`spec/pipeline_schemas.py:232` — sima enum default, nem `Literal["manual"]`, ellentétben a testvér-mezőkkel. Ma nem kihasználható (`openapi.yaml` ManualCandidateSubmission sémája helyesen `additionalProperties: false`, 3 mezővel, `candidate_origin` nélkül, és nincs route ami ezt a Pydantic osztályt kötné), de az osztály saját docstringje "the only client-submittable manual intake shape"-nek nevezi magát — a következő route-építőnek hibás handoffot ad.

**Kért javítás:** `candidate_origin` (és a többi mező) `Literal`-zárása, az OpenAPI séma szigorúbb alakjához igazítva.

---

**Folyamat-megjegyzés, nem blokkoló:** a `005` fejléce a runner felelősségére hárítja az advisory lock/Phase A-B szétválasztást (ADR §5/§9), de a teljes repóban nincs runner-implementáció — minden eddigi QA-kör, és a saját reprodukcióm is, kézi `psql -f` hívásokkal szimulálta. Az ADR §9 "acceptance must prove... enum-phased retry behaviour" állítása emiatt ma nem bizonyítható valódi konkurens futással. Javaslat: vagy épüljön meg most a runner, vagy a handoff explicit mondja ki, hogy S1 csak az SQL felet szállítja, a runner S2/S3 felelősség.

**Tesztkészlet-minőség:** `test_arch01_s1_qa_regressions.py` valódi, DB-állapotot visszaolvasó teszt, nem theater. `test_arch01_migration.py`/`test_arch01_contract.py` túlnyomórészt szöveg-jelenlét/shape-ellenőrzés — legitim smoke-teszt, de semmit nem bizonyít DB-viselkedésről, és egyik sem fedezte volna fel a fenti 5 találat egyikét sem (ami nem meglepő: az 1. pont infrastruktúra/deploy kérdés, a 2-4. pont candidate-state és artifact-relink területen egyáltalán nincs teszt).

**Saját futtatás:**
```
pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py          -> 9 passed
pytest -q tests/test_arch01_s1_qa_regressions.py (izolált PG16, saját konténer) -> 10 passed
fresh schema+seed+001..005 saját konténeren                                      -> PASS
004->005 upgrade saját konténeren                                                -> PASS
sha256sum 005_arch_01_pipeline.sql vs. saját friss DB ledger                     -> EGYEZIK
```
Mind egyezik a GPT QA jelentett számaival — a 10 korábbi invariáns tényleg zöld. A fenti 5 találat egyike sem szerepel egyik korábbi kör evidence-ében sem.

**Összesített verdikt: JAVÍTÁS KÉRVE.** A korábbi 10, öt körön át finomított invariáns valódi és szilárd alap — ez nem visszalépés. De az 1. és 2. pont önmagában is elég súlyos ahhoz, hogy ezt ne engedjem tovább a GPT release gate-nek: az 1. pont hatástalanítja a teljes trigger-alapú védelmi modellt a ténylegesen telepített rendszeren, a 2. pont pedig azt jelenti, hogy az ADR §8 központi jóváhagyási mechanizmusa valójában sosem épült meg (és emellett a manual workflow működésképtelen). A 3-5. pont valódi, de kevésbé súlyos rés.

**Következő címzett: S1 Builder** (1-5. pont javítása), utána **GPT QA** teljes 10+5=15-tételes reprodukció, majd **Sonnet 5 SG-S1 re-review** — nem elég a prózai összefoglaló, ugyanolyan konkrét diff+futtatás+bizonyíték kell, mint az eddigi köröknél. Production deploy, Compose, Nginx vagy titok módosítás továbbra sincs autorizálva.

## [2026-08-13 13:45 UTC] ARCHITECT/DEVOPS — SG-S1 DB-authority role and runner correction

MODEL=gpt-5.6-terra; REASONING=high

ÁLLAPOT: JAVÍTÁS KÉRVE — a 13:39 Sonnet #1 kritikus finding normatív
korrekciója elkészült; production kód, teszt, Compose és secret nem módosult.

ÉRINTETT FÁJLOK: `COLLAB_GEMINI.md` (append-only),
`docs/adr/0002-arch-01-release-state-machine.md` (új 10--12. fejezet).

**Döntés.** A jelenlegi `POSTGRES_USER=fewa_user` valóban bootstrap-superuser,
ezért a backend/worker nem használhatja többé. Kötelező, külön jelszavas
topológia: `fewa_bootstrap` csak one-shot cluster provisioner; `fewa_migrator`
nem-superuser schema/object owner, kizárólag migration-runner; `fewa_app`
nem-superuser, `NOBYPASSRLS`, `NOREPLICATION`, owner-membership nélküli API és
worker principal. App csak explicit runtime `SELECT/INSERT/UPDATE` és szükséges
sequence jogokat kap; nincs schema CREATE/DDL, trigger, role-admin vagy
migrator/bootstrap secret. Minden ARCH-01 business guard `ENABLE ALWAYS
TRIGGER`; RLS tenant-segmentationként FORCE + fail-closed contexttel egészül ki,
nem szerep-határ helyettesítőjeként.

**Kompatibilis rollout.** A checksumolt `005` érintetlen marad. Új
`006_arch_01_db_roles.sql` jön; egy auditálható bootstrap-only provisioner
hozza létre a szerepeket, adja át a tulajdont, revoke-olja a legacy/public
jogokat és állítja a default privileges-et. API/worker drain + backup után a
runner `fewa_migrator`-ral fut; csak bizonyított `fewa_app` runtime kapcsolat
után lesz a régi `fewa_user` `NOLOGIN`. Nincs adat-, object-ID- vagy ledger
vesztés.

**Owner/sorrend.** S1 corrective builder: új `006` + DB-role regresszió;
R1 DevOps: új `infra/postgres/bootstrap_roles.sql`,
`infra/migrations/runner.py`, `infra/migrations/Dockerfile` és runner tesztek.
R1 blokkoló, nem S2/S3-re halasztható: a runnernek valóban kell futtatnia
`005/006`-ot advisory lockkal és enum-phased móddal. Csak a jelenlegi owner
checkpointja után S3 köti be a meglévő Compose/config/Dockerfile fájlokat és a
`migration-runner` completion gate-et. A `jobs.py` és `arq_worker.py` jelenlegi
in-flight tulajdonban marad; nem kapnak migrator credentielt és nem változnak e
javításban.

**Kötelező QA/Sonnet evidence.** Compose-wired `fewa_app` alatt `rolsuper`,
`rolbypassrls`, `rolreplication` mind false; `SET
session_replication_role=replica`, `ALTER ... DISABLE TRIGGER`, `ALTER TABLE`
és `CREATE TABLE` mind permission/ownership hiba. Izolált migrator/QA futásban
a replication-role hipotézis sem kapcsolhatja ki az `ENABLE ALWAYS` guardokat.
Csak az executable runner adhat fresh és `004->006` upgrade evidence-et,
advisory-lock konkurencia-, checksum/order-drift- és enum Phase-A/B retry
teszttel; API/worker runner előtt nem ready, utána `fewa_app`-pal ready.

FUTTATÁS: read-only ellenőrzés: `docker-compose*.yml` runtime `POSTGRES_USER`
összekötése és a Sonnet 13:39 exact finding; ADR §5/§9 és `005` immutábilis
checksum/runner szerződés. Production teszt nem futott, mert ez kizárólag
Architect/DevOps scope-korrekció.

VERDICT / KÖVETKEZŐ CÍMZETT: S1 corrective Builder + R1 DevOps; utána GPT QA
teljes DB/runner reprodukció; csak ezután Sonnet SG-S1 célzott re-review.

## [2026-08-13 14:25 UTC] S1 BUILDER — ARCH-01 / Sonnet findings 2–5

MODEL=gpt-5.6-terra; REASONING=high
ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)
ÉRINTETT FÁJLOK: `spec/migrations/005_arch_01_pipeline.sql`,
`spec/pipeline_schemas.py`, `fewa-v3-backend/tests/test_arch01_migration.py`,
`fewa-v3-backend/tests/test_arch01_contract.py`,
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`. Compose, Docker,
Nginx, production route és S3 in-flight fájlok érintetlenek. Sonnet #1
superuser/runner finding külön Architect/R1/006 scope, szándékosan nem változott.

JAVÍTÁSOK: új DB candidate-transition trigger csak `uncertain` →
`curator_approved` transitiont enged hitelesített curator/admin actorral és a
candidate site-jához kötött active approved policy revisionnel; atomikusan
approved snapshotot és `candidate.approved` outboxot ír. Direct approval,
actor/policy nélküli legacy approval tiltott; manual legitim út kivétel, de a
submission identity immutable. Verified artifact már release előtt sem
köthető más snapshothoz. Manual landing/canonical URL, host/eTLD+1/content hash
immutable. `DiscoveryCandidateSubmission.candidate_origin` `Literal['manual']`;
explicit kliens origin tiltott, az OpenAPI manual schema továbbra zárt.

FUTTATÁS:

- Isolated PG16/pgvector fresh DB teljes adversarial suite → **`15 passed in
  1.03s`** (10 korábbi + 5 új candidate/artifact/contract eset).
- S1 kör DSN nélkül → **`9 passed, 15 skipped in 0.29s`**; pipeline regresszió
  → **`13 passed in 0.70s`**; `git diff --check` → PASS.
- Isolated pre-005 nyolc lifecycle fixture + 005 + retry → PASS: `8` mapping,
  `1` grandfathered release, `3` reapproval candidate, ledger checksum egyezik.
  Aktuális 005 SHA-256:
  `774b00ca5b81c06cfe3904ef75d08f595319fe1dbbf9c00fd34c7f5d7aa7fb86`.

KÖVETKEZŐ CÍMZETT: **GPT QA.** Futtasd a teljes 15 DB regressziót, S1+pipeline
regressziót, fresh és 004->005/retry/checksum kört. Sonnet re-review csak GPT
QA `ELFOGADVA` után; R1/006 runner/deploy finding külön workstream.

## [2026-08-13 14:32 UTC] S1 BUILDER — ARCH-01 / verified artifact monotonicity

MODEL=gpt-5.6-terra; REASONING=high
ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)
ÉRINTETT FÁJLOK: kizárólag `spec/migrations/005_arch_01_pipeline.sql` és
`fewa-v3-backend/tests/test_arch01_migration.py`; R1/006 infra, Compose és S3
in-flight fájlok érintetlenek.

JAVÍTÁS: a verified artifact trigger most monotonic. Ha `OLD.verified_at` nem
NULL, a `verified_at` maga, snapshot binding, object/version, SHA, readback SHA
és validator report sem nullázható, sem lecserélhető. A még nem verified
artifact szerkeszthető marad; a `NULL → verified` átmenet csak matching
readback SHA és validator report mellett megengedett. Így `verified_at=NULL`
nem nyithatja vissza a cross-snapshot relink bypassot.

FUTTATÁS:

- Isolated PG16/pgvector fresh DB adversarial suite → **`16 passed in 1.06s`**
  (új verified→unverified→rebind regresszió zöld).
- S1 kör DSN nélkül → **`9 passed, 16 skipped in 0.28s`**; pipeline →
  **`13 passed in 0.71s`**; diff check PASS.
- Fresh DB 005 retry + source checksum → PASS (`true`). Aktuális 005 SHA-256:
  `5357fac45aa52b4b989c1ee24392993e32deff2dcaf0bfcfcce035d417143701`.

KÖVETKEZŐ CÍMZETT: **GPT QA.** Kérlek futtasd a teljes 16 DB regressziót,
S1+pipeline köröket és fresh/004->005/retry/checksum acceptance-t. Sonnet
re-review csak QA `ELFOGADVA` után; R1/006 változatlanul külön scope.

## [2026-08-13 14:37 UTC] S1 BUILDER — ARCH-01 / null-safe verification evidence

MODEL=gpt-5.6-terra; REASONING=high
ÁLLAPOT: GPT QA-RA KÉSZ (nem Sonnet verdict, nem deploy-jóváhagyás)
ÉRINTETT FÁJLOK: csak `spec/migrations/005_arch_01_pipeline.sql`,
`fewa-v3-backend/tests/test_arch01_migration.py`,
`fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`. R1/006, Compose és
S3 in-flight fájlok érintetlenek.

JAVÍTÁS: a `NULL <> value` háromértékű SQL-hibát null-safe gate váltotta fel.
`NULL → verified_at` csak nem-null `sha256`, nem-null `readback_sha256`,
`readback_sha256 IS NOT DISTINCT FROM sha256`, valamint nem-null validator
report mellett engedett. Hiányos readback vagy validator evidence DB-hiba;
verified utáni monotonic immutability változatlan.

FUTTATÁS:

- Isolated PG16/pgvector fresh adversarial suite → **`18 passed in 1.19s`**
  (a QA által hozzáadott null-readback verification bypass is tiltott).
- S1 kör DSN nélkül → **`9 passed, 18 skipped in 0.29s`**; pipeline →
  **`13 passed in 0.69s`**.
- Fresh 005 retry + source checksum → **PASS** (`true`); diff check PASS.
  Aktuális 005 SHA-256:
  `47d7a7571e07111898e54267c14dcf95e570822ed2fa6a5863e10eecd76577d2`.

KÖVETKEZŐ CÍMZETT: **GPT QA.** Futtasd a teljes kibővített DB regressziót,
S1+pipeline és fresh/004->005/retry/checksum acceptance-t. Sonnet re-review
csak QA `ELFOGADVA` után; R1/006 továbbra külön scope.

## [2026-08-13 14:30 UTC] GPT QA — latest canonical Sonnet #2–5 verdict

MODEL=gpt-5.6-sol; REASONING=high

VERDICT: **JAVÍTÁS KÉRVE**; NEXT OWNER: **S1 Builder**. A részletes exact
evidence a fenti `14:29 UTC` GPT QA blokkban van. A kért 15 DB, 9 S1, 13
pipeline, fresh/upgrade/retry/checksum kapu zöld, továbbá Sonnet #2, #4 és #5
lezárható. Sonnet #3 azonban kétlépcsősen továbbra megkerülhető: verified
artifact `verified_at` értéke nullázható, majd más snapshothoz rebindelhető.
Az új QA teszttel a teljes suite **15 passed, 1 failed in 1.08s**. Fix:
`OLD.verified_at IS NOT NULL` után maga a verification state is legyen
monoton/immutable. A következő zöld kör Sonnet re-review csomagja kizárólag
#2–5-re vonatkozhat; Architect #1 / R1 / 006 külön pending és blokkoló marad.

## [2026-08-13 14:34 UTC] GPT QA — Sonnet #3 monotonic verification re-QA

MODEL=gpt-5.6-sol; REASONING=high

ÁLLAPOT / VERDICT: **JAVÍTÁS KÉRVE** a szűk Sonnet #2–5 S1 candidate-re. Ez
nem Sonnet-verdict és nem all-project all-clear. **Architect/Sonnet kritikus
#1, R1 és a külön 006 DB-role/runner workstream változatlanul NYITOTT,
PENDING és RELEASE-BLOKKOLÓ**; e QA-kör nem vizsgálta vagy fogadta el.

ELŐÍRT EREDMÉNYEK:

- Izolált PostgreSQL 16-on a handoff szerinti 16 DB adversarial teszt:
  **16 passed in 1.02s**.
- S1 migration + contract: **9 passed in 0.22s**.
- Pipeline regresszió: **13 passed in 0.72s**.
- Fresh schema + seed + `001..005`: **PASS**; host source SHA és DB ledger
  checksum egyezik:
  `5357fac45aa52b4b989c1ee24392993e32deff2dcaf0bfcfcce035d417143701`.
- Pre-005 lifecycle/depth fixture, `005`, majd teljes `005` retry: **PASS**;
  számláló `8|1|3|2|1|5357fac4...` = mapping | grandfathered release |
  legacy candidate | policy hold | ledger | checksum.
- Eltérő runtime source path/hash: **EXPECTED REJECT**,
  `ARCH-01 migration 005 checksum mismatch`.
- DSN nélküli S1 kör: **9 passed, 17 skipped in 0.28s**.

KÓDAUDIT:

- A korábbi kétlépcsős `verified_at=NULL -> snapshot rebind` út lezárult:
  `OLD.verified_at IS NOT NULL` után verification state, snapshot binding,
  object/version és integrity mezők változtatása tiltott. Az előző
  `test_verified_artifact_cannot_be_unverified_then_rebound` most zöld.
- Legitimate positive út zöld: pre-verification `object_key`/
  `object_version_id` szerkesztés sikeres; matching `readback_sha256=sha256`,
  nem-null validator report és `verified_at=now()` verification sikeres.

FENNMARADÓ SONNET #3 BLOKKOLÓ — NULL READBACK VERIFICATION BYPASS:

- A verification guard feltétele:
  `NEW.readback_sha256 <> NEW.sha256 OR NEW.validator_report_sha256 IS NULL`.
  PostgreSQL háromértékű logikában null readback esetén az első tag `NULL`, a
  második `FALSE`, így az egész IF nem TRUE és nem dob hibát.
- A table CHECK ugyanezt nem fogja meg, mert a CHECK `NULL` eredményt
  elfogadja. Valódi PG16 reprodukcióban artifact `readback_sha256=NULL`,
  validator report nem-null, majd `verified_at=now()` sikeres lett:
  `has_readback=false | verified=true`.
- Új QA regresszió:
  `test_verification_rejects_missing_readback_hash` -> **DID NOT RAISE**.
  Kibővített teljes DB suite: **16 passed, 1 failed in 1.11s**.
- Kötelező fix: null-safe ellenőrzés, például
  `NEW.readback_sha256 IS DISTINCT FROM NEW.sha256`, és explicit non-null
  readback/validator követelmény a `NULL -> verified` átmeneten. A valid
  positive út maradjon zöld.

FUTTATÁS (exact command/result):

- `docker run -d --rm --name arch01-s1-monotonic-qa -e
  POSTGRES_DB=arch01qa -e POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p
  55438:5432 -v /srv/projects/webarchivum:/workspace:ro
  pgvector/pgvector:pg16`, majd `psql -q -v ON_ERROR_STOP=1` sorrendben
  `spec/schema.sql`, seed, `001..005` -> **FRESH_PASS CHECKSUM_MATCH
  5357fac45aa52b4b989c1ee24392993e32deff2dcaf0bfcfcce035d417143701**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55438/arch01qa
  pytest -q fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` a kért
  16 esettel -> **16 passed in 1.02s**; az új null-readback regresszióval ->
  **16 passed, 1 failed in 1.11s**.
- `cd fewa-v3-backend && pytest -q tests/test_arch01_migration.py
  tests/test_arch01_contract.py` -> **9 passed in 0.22s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.72s**.
- Külön `arch01upgrade` DB, schema + seed + `001..004`, lifecycle/depth
  fixture, `005`, majd `005` retry -> **UPGRADE_RETRY_CHECKSUM_MATCH
  5357fac45aa52b4b989c1ee24392993e32deff2dcaf0bfcfcce035d417143701**;
  számláló `8|1|3|2|1|5357fac4...`.
- Runtime source path eltérítés `004_seed_default_users.sql` fájlra ->
  **EXPECTED CHECKSUM DRIFT REJECT**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 17 skipped
  in 0.28s**.
- `git diff --check -- tests/test_arch01_s1_qa_regressions.py` -> **PASS**.

KÖVETKEZŐ CÍMZETT: **S1 Builder**, csak a null-safe verification hard gate
javítására. Utána GPT QA teljes 17 DB + 9 S1 + 13 pipeline és fresh/upgrade/
retry/checksum kört futtat. Teljes zöld esetben célzott Sonnet #2–5 re-review
packet készül; kritikus #1/R1/006 akkor is külön release-blokkoló marad.

## [2026-08-13 14:41 UTC] GPT QA — SG-S1 FINAL, szűk Sonnet #2–5 re-review packet

MODEL=gpt-5.6-sol; REASONING=high

VERDICT: **ELFOGADVA kizárólag a Sonnet #2–5 S1 javításokra**. Ez nem Sonnet
verdict, nem deploy-jóváhagyás és nem teljes ARCH-01 all-clear.
**A kritikus Sonnet #1 / Architect R1 / külön 006 DB-role és migráció-runner
workstream továbbra is NYITOTT, PENDING és RELEASE-BLOKKOLÓ.**

FÜGGETLEN EREDMÉNYEK, izolált PostgreSQL 16-on:

- Fresh schema + base seed + `001..005`: **PASS**. Host source SHA és a DB
  `schema_migrations` ledger checksum egyezik:
  `47d7a7571e07111898e54267c14dcf95e570822ed2fa6a5863e10eecd76577d2`.
- Kibővített DB adversarial suite: **18 passed in 1.10s**.
- S1 migration + contract: **9 passed in 0.23s**.
- Pipeline regresszió: **13 passed in 0.73s**.
- DSN nélküli S1 kör: **9 passed, 18 skipped in 0.29s**.
- Valódi `004 -> 005 -> teljes 005 retry` fixture: **PASS**; számláló
  `8|1|3|2|1|47d7a757...` = legacy snapshot mapping | grandfathered release
  decision | reapproval candidate | depth 3/5 hold | 005 ledger | checksum.
- Runtime source path eltérítés a 004 fájlra: **EXPECTED REJECT**, rc=3,
  `ARCH-01 migration 005 checksum mismatch`; a rögzített 005 checksum nem
  változott.
- Külön SQL verification matrix: `sha256=NULL` **REJECT**, NULL readback
  **REJECT**, NULL validator report **REJECT**, matching SHA+readback és
  nem-null validator melletti szabályos `NULL -> verified_at` **PASS**.
- `git diff --check` az auditált S1 fájlokra és a QA tesztre: **PASS**.

ADVERSARIAL ACCEPTANCE / SONNET #2–5:

1. **#2 candidate state és atomicitás — PASS.** Direct state bypass, null actor,
   inaktív/idegen policy revision tiltott; a szabályos manual approval ugyanabban
   a tranzakcióban hozza létre a policyhoz kötött snapshotot és az egyedi outbox
   rekordot. Rollback esetén egyik mellékhatás sem marad.
2. **#3 artifact binding és verification — PASS.** Verified artifact nem
   cserélhető más snapshotra, nem downgrade-elhető/unverify-olható, identity és
   integrity mezői monoton immutable-ek. A verification explicit nem-null SHA,
   matching readback SHA és nem-null validator evidence nélkül fail-closed; a
   legitimate pre-verification identity edit és valid verification engedett.
3. **#4 manual provenance — PASS.** Origin/state közvetlen átírása, valamint
   landing/canonical URL, host/eTLD+1 és content identity mutációja tiltott; az
   egyetlen hitelesített `uncertain -> curator_approved` pozitív út megmaradt.
4. **#5 contract alignment — PASS.** A Pydantic manual submission mezők
   `Literal["manual"]`, `Literal["uncertain"]` és
   `Literal["manual_review"]`; a kliens nem kontrollálhatja az origint, az
   OpenAPI manual request csak evidence-only mezőket enged és
   `additionalProperties: false`.
5. A korábbi lifecycle/release invariánsok is zöldek: first-domain distinct
   non-null curator+admin, current verified artifact/version/hash, release és
   withdrawal decision+snapshot+outbox atomikusság, historical artifact/snapshot
   immutability, depth 3–5 hold, legacy/manual anti-bypass.

EXACT COMMANDS:

- `docker run -d --rm --name arch01-s1-final-qa -e POSTGRES_DB=arch01qa -e
  POSTGRES_USER=qa -e POSTGRES_PASSWORD=qa -p 55439:5432 -v
  /srv/projects/webarchivum:/workspace:ro pgvector/pgvector:pg16`, majd
  `psql -q -v ON_ERROR_STOP=1` sorrendben `spec/schema.sql`, base seed,
  `001..005` -> **FRESH_PASS / checksum match=true**.
- `ARCH01_QA_DATABASE_URL=postgresql://qa:qa@127.0.0.1:55439/arch01qa
  pytest -q fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py` ->
  **18 passed in 1.10s**.
- `cd fewa-v3-backend && pytest -q tests/test_arch01_migration.py
  tests/test_arch01_contract.py` -> **9 passed in 0.23s**.
- `pytest -q tests/test_pipeline_extraction.py tests/test_pipeline_ner.py
  tests/test_pipeline_summary.py tests/test_pipeline_embedding.py
  tests/test_pipeline_qc_dedup.py tests/test_main.py` -> **13 passed in
  0.73s**.
- `pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py
  tests/test_arch01_s1_qa_regressions.py` DSN nélkül -> **9 passed, 18 skipped
  in 0.29s**.
- Külön `arch01upgrade` DB-ben schema+seed+`001..004`, nyolc lifecycle és
  depth 2/3/5 fixture, majd `005` kétszer ->
  **`8|1|3|2|1|47d7a757...` PASS**.
- `PGOPTIONS='-c
  arch01.migration_source_path=/workspace/spec/migrations/004_seed_default_users.sql'`
  mellett 005 futtatás -> **EXPECTED CHECKSUM DRIFT REJECT, rc=3**.
- PSQL `DO` verification matrix -> **NULL_SHA_REJECT=PASS;
  NULL_READBACK_REJECT=PASS; NULL_VALIDATOR_REJECT=PASS;
  VALID_VERIFICATION_POSITIVE=PASS**.

SONNET SZŰK REVIEW DIFF-CSOMAG:

- `spec/migrations/005_arch_01_pipeline.sql`
- `fewa-v3-backend/tests/test_arch01_migration.py`
- `fewa-v3-backend/tests/test_arch01_s1_qa_regressions.py`
- `spec/pipeline_schemas.py`
- `spec/openapi.yaml`

KÖVETKEZŐ CÍMZETT: **SG-S1 Sonnet reviewer**, kizárólag a #2–5 javítások és
a fenti 18 DB + residual verification acceptance végső felülvizsgálatára.
Sonnet #1 / R1 / 006 külön workstreamje e packetből explicit kizárt és a release
kaput továbbra is blokkolja.

## [2026-08-13 14:44 UTC] SONNET 5 — SG-S1 szűk re-review (#2–5): ELFOGADVA

MODEL=Sonnet 5; REASONING=high — a diff-csomag mind az 5 fájljának (`005_arch_01_pipeline.sql`, `test_arch01_migration.py`, `test_arch01_s1_qa_regressions.py`, `pipeline_schemas.py`, `openapi.yaml`) közvetlen elolvasása, saját friss izolált PostgreSQL 16 konténer (nem a QA-é), saját `sha256sum` és saját, a korábbi két saját eredeti findingemet (#2 candidate bypass, #3 null-readback bypass) újra közvetlenül reprodukáló SQL, nem csak a meglévő tesztek újrafuttatása.

**Erre a szűk körre vonatkozik kizárólag ez a verdikt: #2–5.** A kritikus #1 (superuser DB-szerepkör) és a hozzá tartozó R1/006 workstream **továbbra is nyitott és release-blokkoló** — ez a verdikt nem érinti és nem oldja fel azt.

**#2 candidate state/atomicitás — ELFOGADVA.** `005_arch_01_pipeline.sql:775-826` — új `trg_arch01_candidate_transition_guard` minden `discovery_candidates` sorra fut (nincs `candidate_origin` szűrés), csak `uncertain→curator_approved`-ot enged, hitelesített curator/admin `arch01.actor_id` GUC-ot és aktív, a candidate site-jához kötött `arch01.policy_revision_id` GUC-ot követel, majd atomikusan approved snapshotot + dedupelt `candidate.approved` outboxot ír. Saját reprodukció: pontosan az eredeti kihasználásomat (`UPDATE discovery_candidates SET state='curator_approved'` semmilyen GUC nélkül, `discovery`-eredetű candidate-en) újra megpróbáltam saját friss konténeren — helyesen elutasítva: `ARCH-01 curator approval requires active actor, candidate site and active approved policy revision`. A manual-candidate immutability trigger (`734-764. sor`) is kapott explicit kivételt erre az egy átmenetre (745-754. sor) — a korábbi "manual candidate örökre approve-olhatatlan" hiba is zárva.

**#3 artifact binding/verification — ELFOGADVA.** `005_arch_01_pipeline.sql:429-462` — az új `trg_arch01_verified_artifact_binding_immutable` `OLD.verified_at IS NOT NULL` esetén zárolja a snapshot/identity/integrity mezőket (nem csak released állapotban), és a `NULL→verified` átmenetnél explicit `IS NULL`+`IS DISTINCT FROM` (nem `<>`) ellenőrzést használ — ez helyesen null-safe, szemben az eredeti hárompólusú-logika hibával. Saját reprodukció: az eredeti null-readback bypass-t (`readback_sha256=NULL`, nem-null validator report, `verified_at=now()`) újra megpróbáltam saját friss konténeren — helyesen elutasítva: `ARCH-01 verification requires non-null matching readback SHA-256 and validator report`. A QA által talált kétlépcsős (verified→unverify→rebind) bypass is zárva, mert a trigger `OLD.verified_at IS NOT NULL`-t nézi, nem a jelenlegi release-állapotot.

**#4 manual candidate provenance — ELFOGADVA.** `734-744. sor` — az immutable-oszlop lista kibővült `landing_url`/`canonical_url`/`host`/`etld_plus_one`/`content_sha256`-tal, `IS DISTINCT FROM` null-safe formában a nullable mezőkre.

**#5 kontraktus-egyezés — ELFOGADVA.** `spec/pipeline_schemas.py:232-241` — `DiscoveryCandidateSubmission.candidate_origin` most `Literal["manual"] = "manual"`, a testvérmezőkkel (`state`, `decision_source`, `reason_code`) egyező szigorral, plusz egy explicit validator, ami a nested-dict-injection útvonalat is elutasítja. Az OpenAPI `ManualCandidateSubmission` séma változatlanul `additionalProperties: false`, 3 mezővel.

**Saját futtatás:**
```
pytest -q tests/test_arch01_migration.py tests/test_arch01_contract.py     -> 9 passed
pytest -q pipeline regresszió (6 fájl)                                     -> 13 passed
saját friss PG16 konténer: schema+seed+001..005                            -> PASS
saját sha256sum 005_arch_01_pipeline.sql vs. saját DB ledger checksum      -> EGYEZIK (47d7a757...)
saját friss konténeren: test_arch01_s1_qa_regressions.py                   -> 18 passed
saját SQL: eredeti #2 exploit (bare UPDATE, GUC nélkül)                    -> helyesen ELUTASÍTVA
saját SQL: eredeti #3 exploit (NULL readback, nem-null validator)          -> helyesen ELUTASÍTVA
```
Mind egyezik a GPT QA jelentett számaival — de ez saját, önálló futtatás és két saját eredeti kihasználási kísérlet közvetlen újra-reprodukciója, nem a QA jelentésének elfogadása.

**Verdikt: ELFOGADVA — kizárólag #2–5-re.** Mind a négy korábban talált hiba (candidate-state total bypass, manual candidate örök-approve-olhatatlanság, artifact cross-snapshot laundering + null-readback three-valued-logic bypass, URL-mutálhatóság, Pydantic contract-lock hiány) valódi, teljes javítást kapott, saját közvetlen reprodukcióval megerősítve.

**A release kapu továbbra is zárva marad**, amíg a kritikus #1 (superuser DB-szerepkör) és a hozzá tartozó Architect R1/006 DB-role + migration-runner workstream nem kap saját, teljes Sonnet SG-S1 verdiktet — ez a mai verdikt kifejezetten nem terjed ki rá, ahogy a QA handoff is explicit kizárta. Amikor az R1/006 candidate elkészül és GPT QA lezárja, ugyanide kérek konkrét diffet+futtatást a végső, teljes ARCH-01/S1 release-gate review-hoz. Production deploy, Compose, Nginx vagy titok módosítás továbbra sincs autorizálva.

## [2026-08-13 14:45 UTC] WORKFLOW — kötelező folyamatos végrehajtás

**Cél:** nincs indokolatlan üresjárat a Builder, GPT QA és Sonnet kapui között.

1. Minden Builder-handoff után a GPT QA automatikusan indul; nem vár emberi utasításra.
2. Minden QA `ELFOGADVA` után a Sonnet review-csomag automatikusan a COLLAB-ba kerül. Sonnet válasza közben a koordinátor azonnal elindítja a következő, fájl-tulajdon szerint nem ütköző build-szeletet vagy a szükséges izolált előkészítést.
3. Minden QA/Sonnet `JAVÍTÁS KÉRVE` verdict közvetlenül és konkrét acceptance teszttel visszamegy a Builderhez; nem kér felhasználói köztes döntést.
4. Külső verdictre csak akkor várunk tétlenül, ha nincs biztonságosan párhuzamos, már specifikált szelet. Ilyenkor a következő megengedett szeletet kell elindítani, nem státuszüzeneteket ismételni.
5. Release/deploy továbbra külön felhasználói jogosultság; a fejlesztési és tesztelési ciklus azonban autonóm.

AKTUÁLIS VÉGREHAJTÁS: Sonnet SG-S1 #2–5 **ELFOGADVA**. Az egyetlen maradék release-blokkoló a #1/R1–006: least-privilege DB-szerepkörök + executable migration runner. R1 Builder aktív; befejezése után GPT QA, majd teljes Sonnet release-gate automatikusan következik.

## [2026-08-13 15:18 UTC] R1 BUILDER — 006 role/runner executable evidence, architect decision required

MODEL=gpt-5.6-terra; REASONING=high

ÉRINTETT ÚJ FÁJLOK: `spec/migrations/006_arch_01_db_roles.sql`,
`infra/postgres/bootstrap_roles.sql`, `infra/migrations/runner.py`,
`infra/migrations/Dockerfile`, `infra/migrations/tests/test_runner_contract.py`,
`infra/migrations/tests/run_pg_acceptance.sh`. S1/005, Compose, API/worker,
Nginx és secret fájlok érintetlenek.

MEGVALÓSÍTVA:

- `fewa_bootstrap`, `fewa_migrator`, `fewa_app` külön szereptopológia;
  migrator/app `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
  NOBYPASSRLS NOINHERIT`, külön psql változókon át adott jelszavakkal.
- Bootstrap tulajdon-átruházás, PUBLIC revoke, explicit app DML/view/sequence
  allow-list, default-privilege revoke; runtime szerep nem kap bootstrap vagy
  migrator credentielt.
- `006` explicit `ENABLE ALWAYS` állapotba tesz minden ARCH-01 lifecycle,
  candidate, artifact, release, policy, outbox/ledger guardot.
- Az executable runner session advisory lockot, lexikális sorrendet,
  fail-closed checksum-ledgert, `enum_phased` autocommit Phase-A + egyetlen
  Phase-B tranzakciót, retry-t és drift-refusalt implementál.

VALÓDI IZOLÁLT PG16 EVIDENCE:

- fresh schema + bootstrap + runner `001..006` → **PASS**, ledgerben mind a
  hat verzió; `005=enum_phased`, `006=transactional`.
- runner-al épített `004 -> 006` upgrade → **PASS**; ledger `001..006`.
- ismételt runner → **PASS**; módosított 006 source → **EXPECTED REJECT**,
  `migration 006 checksum drift`, rc=3; élő advisory lock → **EXPECTED
  REJECT**, rc=3.
- `fewa_app`: `rolsuper=false`, `rolbypassrls=false`,
  `rolreplication=false`; `SET session_replication_role=replica`, trigger
  disable, ALTER TABLE és CREATE TABLE mind **EXPECTED REJECT**.
- ellenőrzött guardok `tgenabled='A'`: lifecycle, candidate-transition,
  verified-artifact. Statikus runner-contract pytest: **3 passed**; diff check
  **PASS**.

KRITIKUS, REPRODUKÁLT ARCHITECT-DÖNTÉSI BLOKKOLÓ — NEM QA-RA KÉSZ:

Az immutable `005` Phase-B a PostgreSQL szerver-oldali
`pg_read_binary_file(source_path)` hívással saját source-checksumot számol.
Ezt egy `NOINHERIT`/nonsuperuser migrator csak a `pg_read_server_files`
predefined role átmeneti effektív tagságával tudja végrehajtani. PostgreSQLben
ennek a tagságnak a visszavonása a bootstrap grantor joga; egy kizárólag
`fewa_migrator`-ral futó `006` transaction (SECURITY DEFINER bridge sem)
nem tudja fizikailag eltávolítani a bootstrap által adott tagságot. A runner és
app jogtesztek zöldek, de a `005` után maradó server-file role ezért **nem
felel meg** a §10 végső least-privilege követelménynek.

KÖVETKEZŐ CÍMZETT: **Architect/DevOps**. Kérlek rögzítsd az egyetlen
kompatibilis megoldást: (A) explicit, auditált bootstrap-only post-005 cleanup
lépés a runner után és 006 ledger előtt/után, vagy (B) új, jóváhagyott
checksum-mechanizmus (005 checksum immutabilitása miatt ez csak külön
kompatibilitási döntéssel). Addig R1 **JAVÍTÁS KÉRVE / release-blokkoló**;
nem állítok be félkész Compose wiringot vagy secretet.
