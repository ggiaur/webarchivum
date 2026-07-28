# ADR-0001: Domain határok és bounded contextek

**Dátum**: 2026-07-28
**Státusz**: Accepted

---

## Kontextus

A FEWA rendszer tervezésekor el kellett dönteni, hogyan határozzuk meg az egyes alrendszerek felelősségét és határait. Három vitás kérdés merült fel:
1. A `Municipality` entitás melyik domain tulajdona?
2. Az AI Pipeline önálló bounded context, vagy az Archive aldomainje?
3. A Collections feature a Users vagy az Archive alá tartozik?

Ezek a döntések befolyásolják az adatmodellt, az eseményfolyamot és a jövőbeni V4 micro-service határokat.

## Döntés

**1. Municipality → Archive domain**
A `municipality` az archivált snapshot kurátori metaadataává (szűrési dimenzió). A Search context csak olvassa — nem tulajdonosa. Kontrollált lista (nem szabad szöveg), az Archive repository tartja karban.

**2. AI Pipeline → önálló AI bounded context**
Az AI pipeline saját életciklussal rendelkezik (cache réteg, ai_traces, modell-verzió-követés), kívülről triggerelhető, és V4-ben eseményalapú micro-service-szé alakítható. Az Archive-tól való szétválasztás lehetővé teszi, hogy az AI pipeline cserélhető legyen az archívum üzleti logikájának érintése nélkül.

**3. Collections → Archive domain (nem önálló context)**
A Collections kurátori objektum (snapshot-csoportosítás), nem autentikációs/authorizációs objektum. Az Archive repository-n keresztül ér el snapshot-okat; saját repository-ja nincs. A Users context csak az engedélyeket kezeli a collections-ökhöz.

## Következmények

**Pozitív**:
- Az Archive egyetlen igazságforrás (source of truth) marad az összes archívum-rekordra
- Az AI context önállóan cserélhető/frissíthető (pl. más embedding modell)
- V4 eseményalapú architektúrában a contexthatárok egybeesnek a service-határokkal
- A Municipality mint kontrollált lista biztosítja az adatminőséget

**Negatív / trade-off**:
- A Collections önállósága korlátozott — ha V4-ben önálló service lesz, migrációt igényel
- A Municipality lista karbantartása manuális admin feladat

**Semleges**:
- Az AI context szétválasztása extra Arq job definíciót igényel (CrawlJobPayload vs EnrichJobPayload)

## Elvetett alternatívák

| Alternatíva | Miért vetettük el |
|---|---|
| Municipality a Search domainben | A Search read-only — nem kezel master adatot |
| AI Pipeline az Archive aldomainje | Szoros csatolást okozna; V4-ben nehezebb szétválasztani |
| Collections önálló context | Nincs elegendő önálló felelőssége V3.1-ben — over-engineering |
| Municipality szabad szöveg | Adatminőségi kockázat: "Fehérvár" vs "Székesfehérvár" vs "Szfvár" |
