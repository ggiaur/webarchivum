# FEWA — Domain Model & Bounded Contexts

> **Verzió:** 1.0 | **Dátum:** 2026-07-28
> **Szerző:** @architect (AI agent)
> **Kapcsolódó ADR:** [ADR-0001](adr/0001-domain-boundaries.md)

---

## Kontextus térkép

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         FEWA Rendszer                                    │
│                                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────────────┐ │
│  │   CRAWLER   │───▶│   ARCHIVE    │◀───│         COLLECTIONS         │ │
│  │             │    │              │    │                             │ │
│  │ discovery   │    │ snapshots    │    │ gyűjtemény-kurátori réteg   │ │
│  │ scheduling  │    │ lifecycle    │    │                             │ │
│  │ robots.txt  │    │ WACZ/MinIO   │    └─────────────────────────────┘ │
│  └─────────────┘    │ municipality │                   ▲                │
│                     └──────┬───────┘                   │                │
│                            │                      ┌────┴──────┐         │
│                            │ CrawlCompleted        │   USERS   │         │
│                            ▼                      │           │         │
│                     ┌──────────────┐              │ auth      │         │
│                     │     AI       │              │ RBAC      │         │
│                     │              │              │ JWT RS256 │         │
│                     │ NER          │              └───────────┘         │
│                     │ embedding    │                                     │
│                     │ summary      │                                     │
│                     │ QC score     │                                     │
│                     └──────┬───────┘                                     │
│                            │ ChunksIndexed                               │
│                            ▼                                             │
│                     ┌──────────────┐    ┌──────────────────────────────┐│
│                     │    SEARCH    │    │            JOBS              ││
│                     │              │    │                              ││
│                     │ fulltext     │    │ async munkák állapotgépe     ││
│                     │ vector       │    │ monitoring, retry, DLQ       ││
│                     │ hybrid rerank│    │                              ││
│                     └──────────────┘    └──────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 1. ARCHIVE Bounded Context

### Felelősség
Az archivált weboldalak teljes életciklusának kezelése: jelöléstől (`candidate`) a publikálásig (`published`). Ő a rendszer egyetlen igazságforrása (source of truth) az archívum-rekordokra.

### Határok (mit NEM tud)
- Nem tud a keresési indexelés részleteiről — csak egy `ChunksIndexed` eseményt vár vissza
- Nem tud a felhasználók jogosultságairól — a Users contexttől csak tokent fogad el
- Nem tud az AI pipeline belső implementációjáról — csak `AIEnrichmentCompleted` eseményre reagál
- Nem tud a Crawler belső logikájáról — csak `CrawlCompleted` eseményt fogad

### Aggregátumok
| Aggregátum | Gyökér entitás | Invariánsok |
|---|---|---|
| **Snapshot** | `ArchivedSnapshot` | PID egyedi; lifecycle sorrend kötelező; content_hash duplikátum-védett |
| **Site** | `Site` | Domain + tenant_id egyedi; crawl_policy nem null ha aktív |
| **Collection** | `Collection` (delegált az Archive-hoz) | Legalább 1 snapshot; kurátor RBAC |

### Értékobjektumok
- `PersistentIdentifier` — `fewa:YYYY:NNNNNN` formátum, immutable
- `ContentHash` — SHA-256 normalizált URL+tartalom, immutable
- `Municipality` — Fejér vm. önkormányzati egység neve (kontrollált lista, nem szabad szöveg)
- `LifecycleStatus` — enum: `candidate | approved | crawling | archived | indexed | published | deprecated | withdrawn`
- `WaczReference` — MinIO path + SHA-256 + filesize, immutable a tárolás után

### Kibocsátott események
- `SnapshotCreated` — új jelölt belép a rendszerbe
- `SnapshotApproved` — kurátor jóváhagyta, crawler indítható
- `SnapshotArchived` — WACZ feltöltve MinIO-ba, AI pipeline meghívható
- `SnapshotPublished` — teljes pipeline lefutott, publikus
- `SnapshotDeprecated` / `SnapshotWithdrawn` — életciklus vége

### Fogadott események
- `CrawlCompleted` (Crawler-től) → Snapshot `crawling → archived` átmenet
- `AIEnrichmentCompleted` (AI-tól) → Snapshot `archived → indexed` átmenet
- `ChunksIndexed` (Search-től) → Snapshot `indexed → published` átmenet

### Külső contractok
- → **Crawler**: REST `POST /api/internal/crawl-job` — site URL + policy paraméterek
- → **AI**: Arq job `enrich_snapshot` — `snapshot_id` + `wacz_minio_path`
- → **MinIO**: S3 API — WACZ fájl letöltése/feltöltése
- → **Users**: JWT token validálása (read-only, nem hív, csak verifikál)

---

## 2. CRAWLER Bounded Context

### Felelősség
URL discovery, crawl ütemezés, robots.txt kezelés és a Browsertrix integrációja. Az egyetlen komponens, amely az internetre nyúl.

### Határok (mit NEM tud)
- Nem tud a snapshot metaadatairól — csak URL-t és policy-t kap
- Nem tud az AI pipeline-ról — a WACZ-ot egyenesen MinIO-ba rakja
- Nem dönt a jelöltek jóváhagyásáról — ez az Archive + Users feladata

### Aggregátumok
| Aggregátum | Gyökér entitás | Invariánsok |
|---|---|---|
| **CrawlJob** | `CrawlJob` | Egy time-slot-on belül egy domain csak egyszer futhat; WACZ sha256 kötelező |
| **CrawlPolicy** | `CrawlPolicy` | Depth ≥ 1; schedule valid cron expr; robots_respect boolean |

### Értékobjektumok
- `CrawlSchedule` — cron expression + timezone, validált
- `SeedURL` — normalizált, schema-kötelező URL
- `CrawlDepth` — 1–5 közötti integer (max limit architektúrális döntés)

### Kibocsátott események
- `CrawlCompleted` — `{ snapshot_id, wacz_minio_path, wacz_sha256, page_count, crawl_duration_s }`
- `CrawlFailed` — `{ snapshot_id, error_code, retry_count }`

### Fogadott események
- `SnapshotApproved` (Archive-tól) → CrawlJob létrehozása

### Külső contractok
- → **MinIO**: WACZ feltöltés S3 API-n
- → **Browsertrix**: lokális Docker API
- ← **Felfedező PC**: SSH pull egyirányú csatornán (candidates.jsonl)

### candidates.jsonl séma (Discovery interface contract)
```json
{
  "url": "https://example.hu",
  "domain": "example.hu",
  "municipality": "Székesfehérvár",
  "source": "searxng",
  "discovered_at": "2026-07-28T10:00:00Z",
  "confidence_score": 0.85
}
```

---

## 3. AI Bounded Context

### Felelősség
A 7-lépcsős feldolgozó pipeline futtatása minden archivált snapshot-on: szövegkinyerés → NER → összegzés → embedding → QC. Önálló cache réteggel és observability-vel rendelkezik.

### Határok (mit NEM tud)
- Nem tud a snapshot életciklusáról — csak `snapshot_id`-t kap és `AIEnrichmentCompleted`-et küld vissza
- Nem tud a Search indexelési stratégiájáról — csak chunk objektumokat ír a DB-be
- Nem dönt a snapshot publikálásáról

### Aggregátumok
| Aggregátum | Gyökér entitás | Invariánsok |
|---|---|---|
| **EnrichmentJob** | `EnrichmentJob` | Idempotens: ugyanaz a `content_hash` nem fut újra (cache hit) |
| **AITrace** | `AITrace` | Minden LLM hívást naplóz; `confidence_score` 0–1 között |

### Értékobjektumok
- `TextHash` — `SHA-256(normalized_text)` — az AI cache kulcsa
- `EmbeddingVector` — `float[768]`, modell + verzió metaadatával
- `QCScore` — 0–100 integer; `< 40` → auto-reject trigger
- `PromptTemplateVersion` — pl. `"summary-v2.1"` — az összes trace-hez rögzítve

### Pipeline I/O sémák (minden lépés explicit)

```python
class ExtractionInput(BaseModel):
    snapshot_id: UUID
    wacz_minio_path: str
    language: Literal["hu", "en"] = "hu"

class ExtractionOutput(BaseModel):
    raw_text: str
    page_count: int
    extraction_method: str  # "trafilatura" | "fallback_bs4"
    char_count: int

class NEROutput(BaseModel):
    persons: list[str]
    organizations: list[str]
    locations: list[str]
    model_version: str  # "hu_core_news_lg-3.7.0"
    processing_time_ms: int

class SummaryOutput(BaseModel):
    summary: str
    ollama_model: str       # "qwen2.5:7b"
    prompt_template_version: str
    llm_latency_ms: int

class EmbeddingOutput(BaseModel):
    chunks: list[ChunkEmbedding]
    embedding_model: str    # "nomic-embed-text"
    embedding_version: str  # "1.5"
    embedding_latency_ms: int

class ChunkEmbedding(BaseModel):
    chunk_index: int
    text: str
    token_count: int
    embedding: list[float]  # dim=768

class QCOutput(BaseModel):
    score: int              # 0-100
    auto_reject: bool       # score < 40
    reasons: list[str]      # miért alacsony a score
```

### Kibocsátott események
- `AIEnrichmentCompleted` — `{ snapshot_id, qc_score, chunk_count, cache_hit: bool }`
- `AIEnrichmentFailed` — `{ snapshot_id, step_failed, error }`

### Fogadott események
- `SnapshotArchived` (Archive-tól) → EnrichmentJob indítása

### Külső contractok
- → **MinIO**: WACZ letöltés (szövegkinyeréshez)
- → **Ollama**: lokális HTTP API (`/api/generate`, `/api/embeddings`)
- → **PostgreSQL**: chunk-ok és ai_traces írása
- → **Redis db=1**: AI cache olvasás/írás

---

## 4. SEARCH Bounded Context

### Felelősség
Hibrid keresési index kezelése (BM25 tsvector + pgvector HNSW) és a lekérdezések kiszolgálása. Ő a read-optimalizált olvasási oldal.

### Határok (mit NEM tud)
- Nem tud a snapshot életciklusáról — csak publikált tartalmakat lát
- Nem tud a crawl folyamatról
- Nem ír az `archived_snapshots` táblába — csak olvas

### Aggregátumok
- *(Search kontextusban nincs saját aggregátum — a `page_chunks` tábla az AI context tulajdona, a Search csak olvassa)*

### Értékobjektumok
- `SearchQuery` — `q: str`, szűrők, pagination paraméterek
- `SearchResult` — snapshot ID + relevancia score + snippet
- `RRFScore` — Reciprocal Rank Fusion score a hibrid rankinghez

### Kibocsátott események
- `ChunksIndexed` — `{ snapshot_id }` — visszajelzés az Archive-nak a publikáláshoz

### Fogadott események
- `AIEnrichmentCompleted` (AI-tól) → HNSW index refresh trigger (ha szükséges)

### Külső contractok
- → **PostgreSQL**: `SELECT` a `page_chunks`, `archived_snapshots` táblákból
- ← **Next.js frontend**: `GET /api/search`, `POST /api/rag`

### RAG Guardrail szabályok (kőbe vésve)
1. Csak a top-3 legmagasabb cosine-similarity chunk alapján válaszol
2. `confidence_score < 0.6` → "Nincs elegendő bizonyíték az archívumban."
3. Minden válasz mellé forrás URL + `crawl_timestamp` kötelező
4. Pydantic v2 JSON Schema validáció a LLM output-ra
5. UI figyelmeztetés: "Kísérleti AI-válasz — ellenőrizze az eredeti forrást"

---

## 5. USERS Bounded Context

### Felelősség
Autentikáció (JWT RS256), 6-szintű RBAC, és a felhasználói identitás kezelése. A rendszer egyetlen auth igazságforrása.

### Határok (mit NEM tud)
- Nem tud az archívum tartalmáról
- Nem dönt arról, mi látható publikusan — az Archive és Search dönt
- Nem kezel üzleti objektumokat (snapshot, collection)

### RBAC mátrix (kőbe vésve)

| Jogosultság | Admin | Archivist | Curator | Indexer | Viewer | Guest |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Felhasználó kezelés | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| LLM profil / Crawl Policy | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Crawl indítás | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Célpont jóváhagyás | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Metaadat szerkesztés | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Tezaurusz szerkesztés | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Törlés | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Nyilvános keresés | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Kibocsátott események
- *(Users nem bocsát ki domain eseményt — csak tokent validál)*

### Külső contractok
- → Minden más context: JWT RS256 token verifikáció (nem közvetlen hívás, csak middleware)

---

## 6. COLLECTIONS Bounded Context

### Felelősség
Kurátori gyűjtemények kezelése: snapshot-ok csoportosítása tematikus, földrajzi vagy időbeli szempontok szerint. Az Archive aggregátumának kiterjesztése.

> **Architektúrális döntés (ADR-0001):** A Collections az Archive domain alá tartozik, nem önálló context. Saját repository-ja nincs, az Archive repository-n keresztül ér el snapshot-okat.

### Határok (mit NEM tud)
- Nem tud a crawl folyamatról
- Nem módosítja a snapshot életciklusát
- A publikus/privát láthatóságot nem kezeli — ez az Archive + Users feladata

### Értékobjektumok
- `CollectionMetadata` — cím, leírás, keletkezési dátum, kurátor user_id

---

## 7. JOBS Bounded Context

### Felelősség
Aszinkron feladatok (Arq workers) életciklusának kezelése: ütemezés, retry logika, dead-letter queue, monitorozás. Keresztmetszeti (cross-cutting) infrastruktúra.

### Határok (mit NEM tud)
- Nem tud az üzleti logikáról — csak job státuszokat kezel
- Nem dönt a retry-ról — a retry policy a job definíciójába van égetve

### Job típusok és payload sémák

```python
class CrawlJobPayload(BaseModel):
    snapshot_id: UUID
    site_url: HttpUrl
    depth: int = Field(ge=1, le=5)
    llm_profile: Literal["fast", "balanced", "high_quality"]
    retry_count: int = 0
    max_retries: int = 3

class EnrichJobPayload(BaseModel):
    snapshot_id: UUID
    wacz_minio_path: str
    language: Literal["hu", "en"] = "hu"
    force_reprocess: bool = False  # cache bypass
```

### Kibocsátott események
- `JobCompleted` — `{ job_id, job_type, duration_ms }`
- `JobFailed` — `{ job_id, job_type, error, retry_count }`
- `JobDeadLettered` — `{ job_id, job_type }` — max retry elért

### Monitoring küszöbök (Prometheus alertek)
| Metrika | Küszöb | Alert |
|---|---|---|
| Arq queue depth | > 100 feladat | Warning |
| Job failure rate | > 20% / 1 óra | Critical |
| Ollama unavailable | > 60 másodperc | Critical |
| Disk usage (MinIO) | > 85% | Warning |

---

## Elfogadási kritériumok — ellenőrzőlista

- [x] Mind a 7 bounded context definiálva van
- [x] Minden context tudja, miről NEM tud (határ explicit)
- [x] Az eseményfolyam végigkövethető (Crawler → Archive → AI → Search összefügg)
- [x] A Municipality entity kontextusa eldöntött: **Archive domain**, kontrollált lista
- [x] Az AI Pipeline önálló bounded context (nem Archive aldomain)
- [x] A Collections az Archive domain alá tartozik (ADR-0001)
- [x] Minden pipeline lépés I/O sémája Pydantic BaseModel-lel definiálva
- [x] RBAC mátrix kőbe vésve
- [x] RAG guardrail szabályok kőbe vésve
- [ ] ADR-0001 megírva és commitolva → *következő lépés*
- [ ] STATUS.md frissítve
