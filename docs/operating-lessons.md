# Webarchivum — kötelező tanulságok és működési szabályok

Ez a fájl nem munkanapló. A lezárt hibákból levont, minden további fejlesztési
szeletre kötelező szabályokat őrzi. Az élő átadások a `COLLAB_GEMINI.md`-ben,
a korábbi részletek a `COLLAB_GEMINI.old.md`-ben maradnak.

## OPR-01 — Az átadás nem várhat emberi noszogatásra

**Hiba:** Builder-, QA- és külső reviewer-átadások között indokolatlan holtidő
keletkezett, mert a következő szerepkör indítása chat-figyelemhez kötődött.

**Kötelező szabály:** minden handoffnak tartalmaznia kell a verdictet, a
következő tulajdonost, pontos parancsokat/eredményeket és tiltott lépéseket.
Builder→QA, QA-finding→Builder és QA-elfogadás→Sonnet automatikus állapotváltás.

**Mérés:** 15 perc új mérhető checkpoint nélkül eszkaláció; 30 perc után nincs
néma „dolgozik” státusz. A vezérlő konkrétan feladatot indít vagy rögzített,
reprodukálható blokkert állít elő.

## OPR-02 — A külső reviewer nem képzelhető el aktívnak

**Hiba:** a Sonnet-figyelés és a tényleges Sonnet-verdict összemosható volt.

**Kötelező szabály:** Sonnet csak a `COLLAB_GEMINI.md` valódi, időbélyeges EOF
bejegyzésével tekinthető aktívnak vagy késznek. „Waiting/watching” nem review,
és nem engedélyez deployt vagy új függő slice indítását.

### OPR-02a — Saját naplóírási visszajelzés zaj, nem workflow-esemény

**Ismétlődő hiba:** a „That's my own edit from writing the verdict. Routine,
no action needed.” típusú visszajelzés egy már elkészült naplóírás technikai
visszaigazolása. Nem új verdict, nem új feladat és nem státuszkérdés.

**Kötelező szabály:** a vezérlő ezt és funkcionális megfelelőit `NOOP`-ként
rögzíti: nem ír új handoffot, nem küld rá followupot, és nem módosít gate
állapotot. Kizárólag a strukturált verdict (`ELFOGADVA` vagy `JAVÍTÁS KÉRVE`),
next owner és evidence számít valódi eseménynek.

## DATA-01 — A forrásrendszer szerződését közvetlenül kell ellenőrizni

**Hiba:** a FEWA keresési lista rövid válaszából tévesen arra következtettünk,
hogy nincs eredeti URL.

**Helyes tény:** a lista jelenleg 324 rekordot ad; minden rekordhoz a detail
endpoint adja az `Eredeti webcím (URL)` mezőt. A FEWA portál katalogizáló
forrás, nem crawl-candidate.

**Kötelező szabály:** külső rendszer adatmodelljéről csak dokumentált vagy
közvetlenül lefuttatott list→detail mintával lehet állítást tenni. A forrás
nyers kérés/válaszának hash-elt provenance-e a jelöltfeltételek része.

## SEC-01 — A „zöld teszt” nem egyenlő a negatív bizonyítékkal

**Hiba:** több egymást követő S2 QA-kör új URL-, DNS-, provenance-, manifest- és
WARC-kijátszási esetet talált annak ellenére, hogy a Builder saját teljes suite-ja
zöld volt.

**Kötelező szabály:** minden új biztonsági vagy integritási findingból állandó,
committelt adversarial regresszió lesz. A pozitív út mellett kötelező az
azonos-hatású aliasok, hibás bemenetek, bizonyíték-átkötés és közvetlen
állapotmegkerülés vizsgálata.

## SEC-02 — A határértékeket a normalizálás után, fail-closed kell dönteni

**Hiba:** terminális/Unicode DNS-pont, IDNA, numeric host, hibás URL és scope
adatok sorrendfüggő megkerüléseket okozhattak.

**Kötelező szabály:** a hostot önálló komponensként kell canonicalizálni;
érvénytelen URL/host nem „külső”, hanem `invalid` és `crawl_incomplete`.
A hívó által közölt scope/final URL nem írhatja felül a canonical számítást.

## QA-01 — A mentés minőségét az objektumhoz kötött bizonyíték igazolja

**Hiba:** a WACZ/replay pozitív bool, hiányos manifest vagy laza WARC-framing
önmagában sikeres minősítést kaphatott.

**Kötelező szabály:** release-hez a versioned WACZ objektum hash-e, a replay
evidence hash-e, a teljes manifest és a WARC rekordframing egymáshoz kötött,
ellenőrzött evidence. Hiány vagy eltérés kizárólag `review_required` vagy
`crawl_incomplete`, soha nem siker.

## Alkalmazási kapu új slice előtt

Minden Builder a munka megkezdése előtt átnézi e fájl releváns pontjait és a
handoffban felsorolja, melyikeket érinti. A független QA ezt ellenőrzi; hiányzó
tanulság-kapu esetén a jelölt nem adható Sonnet review-ra.
