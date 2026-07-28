# Skill: Domain Model & Bounded Contexts

## Mikor használod
Fázis 1-ben. Kód írása előtt. Ez az alap, amire minden más épül.

---

## A FEWA core domainjai

Azonosítandó és definiálandó bounded contextek:

| Context | Felelősség |
|---|---|
| **Archive** | Weblapok mentése, snapshot-ok kezelése, verziókövetés |
| **Search** | Fulltext + vector keresés, ranking, reranking |
| **Crawler** | URL discovery, ütemezés, robots.txt kezelés |
| **AI** | OCR → Cleaning → NER → Embedding → Summarization pipeline |
| **Users** | Autentikáció, RBAC, 6 szerepkör kezelése |
| **Collections** | Kurátori gyűjtemények, metaadatok |
| **Jobs** | Aszinkron munkák állapotgépe, monitoring |

---

## Minden bounded contexthez definiálj

```markdown
## [Context neve]

### Felelősség
[Mit csinál — max 2 mondat]

### Határok (mit NEM tud)
[Milyen más context belső adatáról nincs tudomása]

### Kibocsátott események
- [EventNeve]: [mikor bocsátja ki]

### Fogadott események
- [EventNeve]: [mitől mit csinál]

### Külső contractok
- → [másik context]: [mit kér tőle, milyen interfészen]
```

---

## Output fájlok

- `docs/DOMAIN_MODEL.md` — a teljes domain modell
- `docs/adr/0001-domain-boundaries.md` — az ADR

---

## Acceptance kritériumok (ezt ellenőrzöd a lezárás előtt)

- [ ] Mind a 7 bounded context definiálva van
- [ ] Minden context tudja, miről NEM tud (határ explicit)
- [ ] Az eseményfolyam végigkövethető (Archive → Search → AI összefügg)
- [ ] A Municipality entity kontextusa eldöntött és dokumentált
- [ ] Az ADR megírva és commitolva
- [ ] STATUS.md frissítve: Phase 1 COMPLETED
