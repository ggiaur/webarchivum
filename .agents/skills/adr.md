# Skill: Architecture Decision Records (ADR)

## Mikor írasz ADR-t
Minden architektúrális döntésnél. Azonnal, nem utólag.

Ha döntötél valamiről és nincs hozzá ADR → a döntés nem létezik.

---

## Fájl elnevezés és helye

```
docs/adr/NNNN-tema-roviden.md
```

Ahol NNNN = négyjegyű sorszám: 0001, 0002, ...

---

## Kötelező formátum

```markdown
# ADR-NNNN: [Döntés rövid neve]

**Dátum**: YYYY-MM-DD
**Státusz**: Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

---

## Kontextus

[Miért merült fel ez a kérdés? Mi a probléma amit meg kell oldani?
Max 3-4 mondat, tényszerűen.]

## Döntés

[Mit választottunk? Konkrétan, egyértelműen.]

## Következmények

**Pozitív**:
- [mit nyerünk]

**Negatív / trade-off**:
- [mivel járunk, mit veszítünk]

**Semleges**:
- [ami változik, de nem jó/rossz]

## Elvetett alternatívák

| Alternatíva | Miért vetettük el |
|---|---|
| [opció A] | [ok] |
| [opció B] | [ok] |
```

---

## FEWA tervezett ADR-ek (sorrend ajánlott)

| Sorszám | Téma |
|---|---|
| 0001 | Domain határok és bounded contextek |
| 0002 | FastAPI választása (vs Django, Litestar) |
| 0003 | pgvector HNSW index paraméterek |
| 0004 | Redis db=0 queue / db=1 cache szétválasztás |
| 0005 | Arq worker választása (vs Celery, RQ) |
| 0006 | MinIO objektumtárolás stratégia |
| 0007 | Ollama lokális inference (vs API-alapú) |
| 0008 | RBAC 6-szintű szerepkör modell |
| 0009 | Hybrid search stratégia (BM25 + vector + rerank) |
| 0010 | Event-driven vs direct service call döntés |
