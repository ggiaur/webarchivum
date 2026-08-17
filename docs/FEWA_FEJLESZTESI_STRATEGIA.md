# FEWA — Fejlesztési stratégia és úttörő megoldás terve

> Készült: 2026-08-17 · Claude Code elemzés
> Státusz: **JAVASLAT — döntésre vár**, nem jóváhagyott terv
> Kiegészíti (nem váltja ki) a `docs/FEWA_V3.1_V4_Mesterterv.md`-t

---

## 0. Helyzetkép — ellenőrzött tények

Ezek nem a dokumentációból, hanem az **élő rendszerből és a kódból** származnak (2026-08-17):

| Tény | Forrás | Következmény |
|---|---|---|
| A legacy `fewa.vmk.hu` **324 publikus rekordot** szolgáltat, WordPress + kézzel írt PHP endpointokon (`/tmp/search_form_data.php`) | élő API lekérdezés | Ez a valóság, amit ki kell váltani |
| A munkafolyamat szerint a **következő kiadandó azonosító `fewa0000739`** | folyamatleírás | ~415 azonosító nem publikus (elhalt, jogilag tiltott, feldolgozás alatt) — ezt tisztázni kell |
| A legacy rekord minden metaadata **lapos szöveg** (`"Kapcsolódó testület": "Alba Sansz Kulturális Alapítvány"`) | detail endpoint | Nincs valódi authority-kapcsolat, csak névegyezés |
| Az 1. rekord `Jogi státusz = 0`, mégis szerepel a publikus listavégponton | élő API | **Ellenőrizendő**: kiszivárog-e olyan rekord, aminek nem szabadna |
| A `spec/schema.sql` **15 táblát** tartalmaz, közte **egyetlen authority-tábla sincs** — se személy, se testület, se rendezvény; csak `skos_concepts` (tárgyszó) és egy minimál `municipalities` | kódolvasás | A napi katalogizálási munka modellje hiányzik a célrendszerből |
| A `pid` egy globális Postgres `SEQUENCE`-ből jön (`fewa:YYYY:NNNNNN`, UNIQUE) | `spec/schema.sql:289,373` | **Strukturálisan összeegyeztethetetlen** a legacy `fewa0000739` formátummal és az ID-újrafelhasználási gyakorlattal |
| Három párhuzamos, egymással **nem integrált** rendszer fut: legacy WordPress/PHP/pywb · `fewa-v3-*` ("half-finished rewrite") · `fewa-automation` (csak olvas a legacyből, sehova nem ír) | `fewa-automation/README.md` | Ez a legnagyobb projektkockázat |
| A `README.md` "87 webhely, 96,5 átlagos QC, 100% siker" állítása **nem egyeztethető** a 324 élő rekorddal | összevetés | A belső dokumentáció és a valóság szétcsúszott — ezt tisztázni kell, mielőtt bárki tervezési döntést hoz rá |

### A központi stratégiai ellentmondás

A Mesterterv az **Authority Control-t és a Knowledge Graph-ot V4-re (2027+) halasztja**.
De a napi katalogizálási munkafolyamat — az öt authority-entitás (tárgyszó, földrajzi név, testület, személy, rendezvény), a VIAF/ISNI/Wikidata/Nemzeti Névtér permalinkekkel — **ma is, minden egyes rekordnál ez zajlik**.

Vagyis: a roadmap pont azt tolja el két évvel, ami a szakmai munka lényege. Amíg ez így van, minden Excelben felhalmozott authority-adatnak nincs célrendszere, ami megőrizze. Ezt javaslom megfordítani.

---

## 1. Öt döntés, amit a kódolás folytatása előtt meg kell hozni

**D1 — Egy rendszer marad, nem három.**
Vagy a `fewa-v3` lesz a cél és a `fewa-automation` betáplál bele, vagy fordítva. A jelenlegi "három sávban építünk párhuzamosan" állapot minden további munkaórát megsokszoroz. *Javaslat: `fewa-v3` a mag, `fewa-automation` a beszállító pipeline-ja, a legacy csak migrációs forrás.*

**D2 — Az authority control előre kerül, V3.1-be.**
Nem V4-es luxus, hanem a jelenlegi napi munka adatmodellje. Enélkül a migráció adatvesztéssel jár.

**D3 — Az azonosító-újrafelhasználás megszűnik.**
Elhalt webhely azonosítója **tombstone** lesz (HTTP 410 + magyarázó oldal), soha nem kap új tartalmat. Ez nemzetközi alapelv (VIAF, ISNI, DOI, ARK mind így működik), és a v3 sequence-alapú `pid`-je egyébként sem tudná megvalósítani az újraosztást.

**D4 — Kettős azonosító, nem azonosítócsere.**
A `fewa0000739` formátum marad **örökre, változatlanul** (erre hivatkoznak kívülről). Mellé kap minden rekord egy globálisan feloldható PID-et (**ARK** ajánlott — ingyenes NAAN, könyvtári sztenderd). A `fewa:YYYY:NNNNNN` séma a jelenlegi formájában eldobandó vagy belső technikai kulccsá minősítendő.

**D5 — Az Excel kivezetése ütemezett, nem azonnali.**
A gyakorlat Excel-központú, a v3-ban nincs xlsx-híd (`grep openpyxl` → 0 találat). Két út: (a) importáló híd épül, az Excel marad átmenetileg; (b) a v3 admin felület átveszi a szerepét. *Javaslat: (a) először, mert az Excel-ben már benne van 739 rekordnyi munka — azt be kell tudni tölteni.*

---

## 2. Fázisterv

### F0 — Konszolidáció és leltár (2–4 hét)
- A 324 élő rekord + a teljes Excel-munkafelület kimentése verziókövetett, gépi formátumba (JSON/CSV, egyszeri export)
- Adatminőségi audit: hány duplikált testület/személy/geo névalak van ténylegesen? (ez adja meg, mekkora az AI-dedup megtérülése)
- A `README.md`/`STATUS.md` állításainak visszaellenőrzése a valósághoz
- **Kimenet:** egy hiteles "mi van most" dokumentum, számokkal

### F1 — Authority-mag (4–8 hét) ← *ez a projekt szíve*
- 5 authority-tábla a `fewa-v3` sémába: `subjects`, `places`, `corporate_bodies`, `persons`, `events`
- Mindegyiken: belső ID + megőrzött legacy FEWA-ID + külső azonosítók (Wikidata QID, VIAF, ISNI, Nemzeti Névtér, GeoNames, Köztaurusz, Fejér Megyei Életrajzi Lexikon) + egyéb névalakok + kapcsolódó dátum/hely
- **Kötelező dedup-keresés** a felviteli felületen (ez ma hiányzik a folyamatból, és garantáltan duplikátumokat termel)
- Reconciliation API végpont (W3C/OpenRefine sztenderd) — így a katalogizálók **OpenRefine-ból** tömegesen tudják a meglévő 739 rekord neveit Wikidatához kötni
- **Kimenet:** az authority-adat végre strukturált, kereshető, és exportálható linked data-ként

### F2 — Migráció + Excel-híd (4–6 hét)
- Importáló: `új tartalom (EDIT).xlsx` és a munkafelület → API (validációval, hibalistával)
- A 324 publikus rekord + a nem publikus többi átemelése, provenienciával (melyik mező honnan jött)
- Tombstone-kezelés az elhalt azonosítókra
- **Kimenet:** egyetlen adatbázis, az Excel ettől kezdve csak beviteli eszköz, nem az igazság forrása

### F3 — Aratás modernizálása (párhuzamosan futhat F1-gyel)
- `fewa-automation` → Browsertrix Crawler váltás (böngésző-alapú, JS-nehéz oldalakat is hitelesen ment)
- **WACZ aláírás** (Webrecorder signing spec) — hitelesség-bizonyíték, ezt Magyarországon tudomásom szerint senki nem csinálja
- Fixity (SHA-256) + PREMIS események minden objektumra, 3-2-1 mentési szabály
- Replay: pywb marad vagy ReplayWeb.page — mindkettő WACZ-natív

### F4 — Kereső és hozzáférés
- Teljes szöveges keresés a WARC tartalmán (SolrWayback vagy a saját pgvector-hibrid megoldás)
- Facettált keresés az authority-adatokra épülve (személy → mely webhelyek; hely → mely webhelyek)
- OAI-PMH az OSZK felé (már tervben)
- WCAG 2.1 AA

### F5 — AI-réteg (lásd 4. fejezet) — F1 után, nem előtte
Az AI csak akkor ér valamit, ha van mihez kötnie az entitásokat. Fordított sorrendben csak látványos demó lesz belőle, használható rendszer nem.

---

## 3. Technológiai ajánlás — eszközönként kifejtve

### 3.1 Aratás: Browsertrix Crawler

A jelenlegi `fewa-automation/crawler.py` feltehetően klasszikus HTTP-letöltő logikával dolgozik (kérés → HTML → linkek kinyerése → következő kérés). Ez a mai JS-vezérelt oldalakon (React/Vue SPA-k, lusta betöltés, cookie-fal mögötti tartalom) rendszeresen üres vagy csonka mentést eredményez — a WARC technikailag létrejön, de nem azt tartalmazza, amit a látogató ténylegesen lát.

A **Browsertrix Crawler** (Webrecorder projekt) ezt úgy oldja meg, hogy minden oldalt **valódi, headless Chromium-példányban tölt be** (Playwright-alapú vezérléssel), és a böngésző teljes hálózati forgalmát rögzíti WARC-ba — tehát amit egy ember látna, azt menti, nem amit egy egyszerű HTTP-kliens kapna vissza. Van beépített **"behaviors" rendszere** is: előre megírt JS-viselkedések, amik automatikusan legörgetnek egy végtelen listát, elfogadnak egy cookie-bannert, vagy kinyitnak egy "továbbiak" gombot — ez pontosan azokra a mai magyar önkormányzati/sajtó-oldalakra kell, amikre a leltár is hivatkozik (szekesfehervar.hu, feol.hu stb.).

**Konkrét integráció**: a meglévő `crawl_policies` tábla (séma szerint már létezik) természetes módon feleltethető meg egy Browsertrix "workflow" konfigurációnak (scope, mélység, kizárási minták, viselkedés-lista). A crawler Docker konténerként fut, a kimenete közvetlenül WACZ — ez rövidíti is a jelenlegi pipeline-t, mert nem kell külön lépésben WARC-ból WACZ-ot csomagolni.

### 3.2 Csomagformátum és hitelesség: WARC 1.1 + WACZ + aláírás + fixity

A WARC/WACZ választás már helyes a tervben, ezt nem kell változtatni. Amit hozzáadnék: a **Webrecorder `authsign` szolgáltatás**. Ez azt csinálja, hogy a WACZ-fájl tartalmának hash-éből (a `datapackage.json`-ban felsorolt fájlok SHA-256 összegzéséből) egy **Ed25519 kulcspárral aláírt, időbélyeggel ellátott tanúsítványt** állít elő, amit a WACZ mellé tárolunk. Ez azt bizonyítja **utólag is, harmadik fél által ellenőrizhetően**, hogy az adott archívum-csomag azóta nem módosult, hogy létrehozták — ez a különbség egy "megbízunk a szerverben" és egy "bizonyítottan sértetlen" archívum között.

Emellett minden objektumhoz **PREMIS eseményláncot** vezetünk (mikor, ki/mi, milyen műveletet — capture, fixity check, migration), és **rendszeres időközönként (pl. negyedévente) újraszámoljuk a SHA-256-ot**, összevetve a felvételkori értékkel — ez a "fixity checking", ami időben veszi észre, ha a MinIO-tárolóban bármi korrumpálódott (lemezhiba, emberi hiba), mielőtt a mentés maga válna használhatatlanná.

### 3.3 Visszajátszás: pywb + ReplayWeb.page kombinálva

A meglévő pywb (szerveroldali Python) marad az admin/kurátori visszajátszásra. A publikus oldalon viszont érdemes a **ReplayWeb.page** (kliensoldali, Service Worker alapú) beágyazást erősíteni — ez a README szerint már részben megvan. Az előnye: a WACZ fájl közvetlenül a MinIO S3-ból (aláírt, időkorlátos URL-lel) streamelhető a böngészőbe, nincs szükség hozzá szerveroldali visszajátszó-folyamatra minden egyes lekérésnél — ez költséget és terhelést spórol a szerveren, mert a "lejátszás" munkája a látogató böngészőjében történik.

### 3.4 Azonosító: ARK + a fewaID megőrzése

A jelenlegi `fewa0000739` formátum humán-olvasható, jól bevált, erre már hivatkoznak — ezt nem cseréljük le. Amit hozzáadnék: egy **ARK (Archival Resource Key)** azonosítót minden rekordhoz, ami a `ark:/NAAN/name` formátumú, globálisan feloldható, és — ellentétben egy DOI-val — **nincs hozzá regisztrációs díj**, csak egy intézményi NAAN-számot kell igényelni (pl. a California Digital Library / az ARK Alliance regisztrátorán keresztül). Az ARK explicit támogatja a "tombstone" állapotot: egy megszűnt objektum ARK-ja feloldva egy szabványos "ez az objektum megszűnt, ezért" oldalra mutat, nem 404-et ad és nem kerül újra kiosztásra — ez pontosan a D3 döntést valósítja meg szabványos módon, nem házi megoldással.

### 3.5 Authority-adat: saját táblák + Reconciliation API + OpenRefine

Ez a rész technikailag a legfontosabb, ezért itt a **teljes munkamódszer**, nem csak az eszköznév:

1. **Adatmodell**: 5 tábla (`persons`, `corporate_bodies`, `places`, `events`, `subjects`), mindegyik saját belső ID-vel, megőrzött legacy FEWA-prefixes ID-vel, és külső azonosító-mezőkkel (Wikidata QID, VIAF ID, ISNI, GeoNames ID, Nemzeti Névtér permalink).
2. **Reconciliation API**: építünk egy saját, kis REST-végpontot, ami a [W3C Reconciliation Service API](https://reconciliation-api.github.io/specs/latest/) specifikációját követi (ez egy szabványos szerződés: adott egy szabad szöveges név, a szolgáltatás visszaad egy rangsorolt jelöltlistát pontszámmal). A mi implementációnk két forrást kérdez le és fésül össze: a saját, már rögzített authority-táblákat, és a nyilvános Wikidata reconciliation API-t.
3. **OpenRefine munkafolyamat**: mivel a szolgáltatás szabványos, a katalogizálók a meglévő **739 rekordnyi** nevet be tudják tölteni OpenRefine-ba (ingyenes desktop eszköz), rákötik a mi reconciliation endpointunkra, és **egy kattintással, fasettázva, csoportosítva** látják, mely nevek egyeznek már meglévő rekorddal, melyek gyanúsan hasonlóak (potenciális duplikátum), és melyek biztosan újak. Ez az a lépés, ami a mai "gépeld be újra, és reménykedj, hogy nem duplikálod" folyamatot lecseréli egy tömeges, ellenőrizhető egyeztetésre.
4. **Opcionális továbblépés (nem most)**: ha az authority-állomány kinövi a saját táblás modellt, egy önálló **Wikibase-példány** (a Wikidata mögötti szoftver, önállóan telepíthető) hostolhatná az egészet mint saját linked-data gráfot — ezt csinálta a Görög Nemzeti Könyvtár és az OCLC Project Passage kísérlete is. Ez V2-es finomítás, nem F1 feltétele.

### 3.6 Magyar NLP: huSpaCy

A `hu_core_news_lg` modell (huSpaCy projekt, SZTAKI/PPKE együttműködés) ad névelem-felismerést (PER/ORG/LOC/MISC) magyar szövegen — ez a nyílt forráskódú opciók közül a legjobb hazai lefedettségű. Erre épül a 4. fejezet 3. pontja (entitás-felismerés). Érdemes hosszabb távon **finomhangolni** a modellt könyvtári/helyismereti névformákra (pl. történelmi helynevek, egyházi testületi nevek), mert az általános hírportál-szövegen tanított alapmodell ezeken gyengébb.

### 3.7 Keresés: pgvector hibrid keresés

A már meglévő PostgreSQL + pgvector kombináció (nincs szükség külön vektor-adatbázis-szolgáltatásra, ami extra üzemeltetési költség lenne) alkalmas **hibrid keresésre**: a magyar nyelvű `tsvector` teljes szöveges index (pontos szóalak-egyezés) és a szemantikus vektor-hasonlóság (embedding koszinusz-távolság) eredményét **Reciprocal Rank Fusion (RRF)** módszerrel összefésülve — ez ad jobb találati sorrendet, mint bármelyik módszer önmagában, és ez a technika ma a hibrid keresés de facto szabványa (Elastic, Weaviate, Postgres-natív megoldások mind ezt vagy ennek egy változatát használják).

### 3.8 Amit kerülnék

- **Heritrix önmagában** (a hagyományos, nem böngésző-alapú aratóeszköz) — modern JS-oldalakon rendszeresen hiányos mentést ad.
- **OpenWayback** visszajátszóként — a projekt lényegében leállt, a közösség a pywb/ReplayWeb.page felé mozdult.
- **Handle/DOI** azonosítóként — fizetős regisztráció, felesleges költség ott, ahol az ARK ingyenesen ugyanazt tudja.
- **Külön vektor-adatbázis** (Pinecone, Weaviate, stb.) ekkora korpuszra — a pgvector a meglévő Postgres-en belül elég, és nem hoz be új üzemeltetési felületet.

---

## 4. Hol és hogyan használjunk AI-t — pipeline szinten kifejtve

**Alapelv, amitől soha nem térünk el:** az AI **javasol**, ember **jóváhagy**. Minden AI által javasolt mező mellé eltároljuk, hogy *melyik modell, melyik verzió, mikor, milyen konfidenciával* javasolta, és *ki* hagyta jóvá. Ez a metaadat-proveniencia — és épp ez lenne az, amitől ez nemzetközi mércével is védhető, nem pedig "az AI beleírt valamit a katalógusba".

### 4.1 Gyűjtőköri szűrés (felfedezés)

Egy talált domain-ről az AI eldönti, Fejér-vonatkozású-e — a leírt két szabály (földrajzi: a mindenkori megye területéhez köthető; személyi: itt született vagy itt tevékenykedett) alapján. Módszertanilag ez egy **LLM-alapú osztályozó**, ami a domain tartalmából (kezdőlap + impresszum + kapcsolat oldal szövege) néhány mondatos indoklással "igen/nem/bizonytalan" választ ad. A "bizonytalan" eset kerül csak kurátori várólistára — a nyilvánvaló igen/nem eseteket nem kell emberi időt rájuk költeni. **Megtérülés: nagy**, mert ma ez tisztán kézi böngészés.

### 4.2 Metaadat-előtöltés

Az archivált oldal szövegéből az AI javaslatot tesz a **Műfaj** (11 elemű fix lista), **Típus** (6 elemű fix lista), **Témakör/Altémakör/Tárgyszó** mezőkre — kizárólag a zárt listákból választva, sosem kitalálva új kategóriát. Ez egy egyszerű, jól definiált **zárt osztályozási feladat**, amire kis, olcsó modell is elég (nem kell nagy LLM-et hívni minden rekordra). **Megtérülés: nagy**, mert ez a leggyakrabban ismétlődő katalogizálói lépés.

### 4.3 Entitás-felismerés + authority-kötés — a legnagyobb megtérülésű lépés

Ez a pipeline, ami a 3.5-ös reconciliation-módszertant automatizálja:
1. `huSpaCy` NER kiszedi a szövegből a személy/testület/hely/rendezvény jelölt-neveket.
2. Minden jelölt-név megy a saját reconciliation endpointra (3.5. pont) → visszakap egy rangsorolt egyezési listát a meglévő authority-táblából.
3. Magas konfidenciájú egyezésnél (pl. >0.9) az AI **automatikusan hozzáköti** a meglévő rekordhoz, alacsonyabbnál **jelölt-listát ad** a katalogizálónak választásra, egyik se-nél **"új entitás" javaslatot** tesz (Wikidata-jelölttel, ha talál).
4. A katalogizáló egy kattintással jóváhagy, módosít vagy elutasít — soha nem gépel be kézzel egy már létező nevet újra.

Ez az a pont, ahol a mai folyamat "előfeltétel: authority rekord előzetes rögzítése" lépése a duplikálás fő forrása — ez a pipeline szünteti meg strukturálisan, nem fegyelmi szabállyal.

### 4.4 Duplikátum-felderítés a meglévő állományban

Nem csak új rekordoknál — a **már rögzített ~739 authority-bejegyzésen** is lefuttatható egyszer, kötegelt módban: embedding-alapú hasonlósági klaszterezés jelzi ("ez a testület 87%-ban egyezik a `tes0000412`-vel"), ember dönt az összevonásról. **Megtérülés: nagy**, mert ma erre semmilyen védelem nincs, és minél tovább gyűlik az állomány, annál drágább utólag kibogozni.

### 4.5 Aratás-minőségellenőrzés — a legdrágább kézi lépés kiváltása

Ma a QC azt jelenti, hogy valaki emberileg megnézi, az archivált oldal úgy néz-e ki, mint az élő. Automatizálható: az élő és az archivált oldal **screenshotjának képi összehasonlítása** (perceptual hashing vagy SSIM-alapú különbségszámítás), és csak azok a rekordok kerülnek emberi szem elé, ahol a különbség egy küszöb fölött van. Ez a módszer publikált, működő gyakorlat (l. hivatkozások), nem kísérleti ötlet.

### 4.6 Egyéb pontok

- **Külső azonosító-javaslat**: Wikidata/VIAF/GeoNames jelölt-lista automatikus felajánlása authority-rekord rögzítésekor (ugyanaz a reconciliation-mechanizmus, mint 4.3-ban).
- **Változékonyság mérése**: a kézi "Rendszertelen / Havi / stb." becslés helyett a rendszer a **ténylegesen megfigyelt tartalmi változásokból** (korábbi aratások közti diff-mennyiség) számolja ki az ajánlott aratási gyakoriságot — ember felülbírálhatja, de kiindulásnak adatvezérelt, nem becslés.
- **Elhalt/eltérített webhely felismerése**: "soft 404" oldalak, domain-parkolás, gyanús tartalmi drift (a domain hirtelen teljesen más témáról szól — tipikusan lejárt domain felvásárlás jele) kiszűrése, kurátori riasztással.
- **Kutatói felület (RAG)**: természetes nyelvű kérdés-válasz az archívum tartalmára, **kötelező forrásmegjelöléssel** és konfidencia-korláttal (ez már a tervben szerepel, itt csak megerősítem: ez a helyes irány).
- **Aratás-konfigurálás**: a Browsertrix "behaviors" és kizárási szabályok kezdeti javaslata (naptár-widget, végtelen görgetés, keresőoldal-csapda felismerése) egy oldal első aratása előtt, hogy ne kelljen kézzel kitapasztalni.

### 4.7 Amire az AI-t NE használjuk

Végleges egységesített névalak automatikus előállítására, jogi státusz eldöntésére, és bármire, ami emberi jóváhagyás nélkül publikus rekordba kerül.

---

## 5. Mitől lenne ez országosan úttörő

Nem a "van benne AI"-tól — az ma már nem újdonság. Ezektől:

1. **Aláírt, bizonyíthatóan sértetlen archívum.** WACZ-aláírás + fixity + PREMIS eseménylánc. Magyar közgyűjteményi webarchívumban tudomásom szerint nincs precedense. Ez az, ami miatt egy archivált oldal *bizonyítékként* is használható lenne.
2. **Megyei szintű authority control linked data-ként publikálva.** Az öt entitástípus Wikidata/VIAF/ISNI/Nemzeti Névtér kötésekkel, gépileg lekérdezhetően. Ma ez nemzeti könyvtári szint; megyei szinten nincs rá példa.
3. **Metaadat-proveniencia AI-korban.** Minden mezőnél nyomon követhető, hogy ember vagy modell javasolta, melyik verzió, ki hagyta jóvá. Ez nemzetközileg is friss téma — a legtöbb intézmény most kezd rájönni, hogy szüksége lesz rá.
4. **Adatvezérelt aratási ütemezés** a kézi "változékonyság" becslés helyett.
5. **Tombstone-fegyelem** — a megszűnt tartalom azonosítója sem tűnik el és nem kerül újrahasznosításra. Apróságnak tűnik, valójában ez választja el az archívumot a weboldaltól.

---

## 6. Milyen felállás kell hozzá

| Szerep | Ki lehet | Heti ráfordítás |
|---|---|---|
| Szakmai vezető / gyűjtőkör | könyvtári oldal (jelenlegi katalogizálók) | meglévő |
| Adatmodell-gazda | 1 fő, aki a döntéseket (D1–D5) végigviszi | kritikus, nem delegálható AI-ra |
| Fejlesztés | AI-asszisztált (a jelenlegi felállás), **de emberi review-kapuval** | – |
| Üzemeltetés | Debian + Docker, meglévő | alacsony |

**A meglévő munkamódszer legnagyobb hiányossága**, amit a repóban látok: a fejlesztési státuszok (`STATUS.md`, `README.md`) tartalmaznak olyan állításokat, amiket az élő rendszer nem támaszt alá. A `CLAUDE.md` fegyelme (teszt előbb, független második ellenőrzés, csak ellenőrzött állítás kerül dokumentumba) helyes — de **be is kell tartatni**: minden "kész"-nek jelölt komponensnél a szám mögé oda kell tudni tenni, hol lett ténylegesen lemérve, élő adaton.

---

## 7. Amit a következő két hétben javaslok

1. **D1–D5 döntések meghozatala** (fél nap megbeszélés, nem fejlesztés)
2. **A jogi státusz szivárgás ellenőrzése** — `Jogi státusz = 0` rekord megjelenik a publikus végponton; ha ez valós, ez adatvédelmi/jogi kockázat, azonnal kezelendő
3. **Az ID-újrafelhasználás felfüggesztése** — még mielőtt újabb azonosító kerülne kiosztásra
4. **Kötelező "keress rá, mielőtt új authority rekordot rögzítesz" lépés** beépítése a jelenlegi Excel-folyamatba is, azonnal
5. **Adatminőségi leltár** (F0) — enélkül minden további becslés találgatás

---

## Hivatkozások

- Webrecorder — Browsertrix, WACZ, ReplayWeb.page: https://webrecorder.net/resources/
- IIPC (International Internet Preservation Consortium): https://netpreserve.org
- Archívum-minőségellenőrzés képi hasonlósággal (CEUR): https://ceur-ws.org/Vol-3937/short2.pdf
- OCLC — Library Linked Data with Wikibase (Project Passage): https://www.oclc.org/content/dam/research/publications/2019/oclcresearch-creating-library-linked-data-with-wikibase-project-passage.pdf
- Görög Nemzeti Könyvtár — entitáskezelés RDA + Wikibase: https://www.tandfonline.com/doi/abs/10.1080/19386389.2024.2307208
- OSZK Webarchívum (MIA): https://webarchivum.oszk.hu
- NCSU — ismétlődő aratások QA gyakorlata: https://ncsu-libraries.github.io/web-archiving-docs/recurring-crawl-qa/
