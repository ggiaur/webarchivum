# Fejér Vármegyei Webarchívum (FEWA)
# Digitális Örökség Platform — Mesterdokumentum
# V3.1 → V4 Átfogó Rendszerterv

> **Verzió:** 4.0-draft | **Dátum:** 2026-07-27
> **Szervezet:** Vörösmarty Mihály Könyvtár (VMK), Székesfehérvár
> **Infrastruktúra:** Debian, Docker, UniFi, nyílt forráskód, 0 Ft/hó OPEX

---

## A Dokumentum Három Rétege

```
┌─────────────────────────────────────────────────────────────────┐
│  I. RÉSZ  Vezetői Összefoglaló (10-15 oldal)                    │
│           Célok · Eredmények · Költségek · Ütemezés             │
├─────────────────────────────────────────────────────────────────┤
│  II. RÉSZ  Rendszerterv (80-120 oldal)                          │
│            Architektúra · Adatmodell · API · Biztonság          │
├─────────────────────────────────────────────────────────────────┤
│  III. RÉSZ  Fejlesztői Specifikáció (150+ oldal)                │
│             Schema · Docker · OpenAPI · CI/CD · Tesztek         │
└─────────────────────────────────────────────────────────────────┘
```

Ez a felosztás alkalmas fejlesztési projektdokumentációhoz, közbeszerzési kiíráshoz és pályázati dokumentációhoz egyaránt.

---

# I. RÉSZ — VEZETŐI ÖSSZEFOGLALÓ

## 1. Projekt Célja és Kontextusa

A **Fejér Vármegyei Webarchívum (FEWA)** a Vörösmarty Mihály Könyvtár kezdeményezése, amelynek célja Fejér vármegye digitális kulturális örökségének szisztematikus begyűjtése, megőrzése és közgyűjteményi szintű hozzáférhetővé tétele.

A rendszer **két fázisban** valósul meg:

| Fázis | Neve | Tartalma | Időkeret |
|---|---|---|---|
| **V3.1** | FEWA Enterprise Webarchívum | Webarchívum + RAG + Admin | 2026 Q3–Q4 |
| **V4** | FEWA Digitális Örökség Platform | Eseményalapú + Knowledge Graph + Multi-tenant | 2027+ |

## 2. Kulcsmutató-célok (KPI)

| Mutató | V3.1 Cél | V4 Cél |
|---|---|---|
| Archivált domainek száma | 500+ | 2 000+ |
| WACZ állományok mérete | ~500 GB | ~2 TB |
| RAG válaszidő | < 3 másodperc | < 1 másodperc |
| WCAG 2.1 AA megfelelés | 100% | 100% |
| Havi üzemeltetési költség | 0 Ft | 0 Ft |
| OAI-PMH partner intézmények | OSZK + 3 | 10+ |

## 3. Ütemezési Áttekintés

```
2026 Q3    2026 Q4    2027 Q1    2027 Q2    2027 Q3+
   │           │           │           │           │
   ▼           ▼           ▼           ▼           ▼
[Infra &    [Frontend  [V3.1 Éles  [V4 Design  [V4 Build:
 Backend]    & Admin]   Launch]     & PoC]      Graph, MT]
```

---

# II. RÉSZ — RENDSZERTERV

## 4. Verzió-Stratégia és Komponens Rétegek

### Mi valósul meg V3.1-ben (most)?

| Komponens | Státusz |
|---|---|
| PostgreSQL + pgvector + tsvector hibrid keresés | ✅ Teljes |
| Redis Queue + Redis Cache (szétválasztva, SPOF nélkül) | ✅ Teljes |
| MinIO S3 objektumtároló (Versioning + Lock + SSE) | ✅ Teljes |
| Arq aszinkron worker queue | ✅ Teljes |
| 7-lépcsős AI Pipeline (huSpaCy + Ollama) | ✅ Teljes |
| AI Cache réteg (text_hash → embedding/summary) | ✅ Teljes |
| AI Observability (ai_traces tábla) | ✅ Teljes |
| RBAC (6 szerepkör, JWT RS256) | ✅ Teljes |
| SKOS Tezaurusz (DB tábla + REST API) | ✅ Teljes |
| OAI-PMH 2.0 (mind a 6 ige: DC/METS/MODS) | ✅ Teljes |
| Perzisztens Azonosító: fewa:YYYY:NNNNNN | ✅ Teljes |
| Archiválási életciklus (8 állapot) | ✅ Teljes |
| PREMIS + User Audit Log | ✅ Teljes |
| Monitoring: Prometheus + Grafana + Loki + Alertmanager | ✅ Teljes |
| Biztonsági hardening: Fail2ban, CrowdSec, HSTS, CSP | ✅ Teljes |
| Backup & DR (RPO ≤24h, RTO ≤4h) | ✅ Teljes |
| Next.js SSR nyilvános frontend (WCAG 2.1 AA) | ✅ Teljes |
| React + Vite Admin SPA | ✅ Teljes |
| Digitális Objektum Modell (object_type + extra_metadata) | 🔵 Előkészítve |
| Multi-tenant (tenant_id mezők) | 🔵 Előkészítve |

### Mi kerül V4 ütemtervre?

| Komponens | Státusz |
|---|---|
| Eseményalapú architektúra (NATS / CloudEvents) | ❌ V4 |
| Knowledge Graph (Neo4j / Apache AGE) | ❌ V4 |
| Authority Control (entitás-összevonás) | ❌ V4 |
| Tezaurusz mint önálló mikroszolgáltatás | ❌ V4 |
| Multi-tenant teljes RLS izoláció | ❌ V4 |

---

## 5. Rendszerarchitektúra

```
FELFEDEZŐ PC (Izolált)
┌─────────────────────────┐
│ SearXNG                 │
│ → Domain Scraper        │
│ → Hard Filter + huSpaCy │
│ → candidates.jsonl      │
└──────────┬──────────────┘
           │ SSH Pull (egyirányú)
           ▼
ARCHÍVUM VM — Docker Stack
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  Kurátori Várólista (Admin SPA / RBAC)                        │
│         │                                                      │
│  Crawl Policy Manager                                          │
│         │                                                      │
│  Redis Queue (Arq Workers)                                     │
│    │                                                           │
│    ├─→ Browsertrix Worker → WACZ → MinIO S3                   │
│    │                          │                               │
│    └─→ Extractor Worker ──────┘                               │
│              │                                                 │
│         Dedup Check (URL + SHA256 + SimHash)                  │
│              │                                                 │
│         AI Cache (Redis) ──→ HIT: 0ms CPU                    │
│              │ MISS                                            │
│         AI Pipeline (7 lépcsős):                              │
│           1. Text Extraction (warcio + trafilatura)           │
│           2. Metadata Extraction (Dublin Core)                │
│           3. NER (huSpaCy hu_core_news_lg)                   │
│           4. Summary (Ollama LLM profil)                      │
│           5. Keywords (SKOS tezauruszhoz illesztve)           │
│           6. Embedding (nomic-embed-text 768d)                │
│           7. QC Score (0-100)                                 │
│              │                                                 │
│         PostgreSQL 16 + pgvector + tsvector                   │
│           ├─→ Next.js SSR (Nyilvános frontend)                │
│           ├─→ React Admin SPA                                  │
│           └─→ OAI-PMH 2.0 Provider                            │
│                                                                │
└────────────────────────────────────────────────────────────────┘

MONITORING STACK
┌─────────────────────────────────────────────┐
│ Prometheus + Alertmanager → Grafana         │
│ Loki (logok) + Node Exporter + cAdvisor    │
│ Postgres Exporter                           │
└─────────────────────────────────────────────┘
```

---

## 6. Adatmodell (PostgreSQL V3.1 — Főbb Táblák)

### Gyűjteményhierarchia
```
tenants (V4 előkészítve)
  └── collections (pl. "Fejér Megye 2026")
        └── sites (pl. "alba.hu")
              └── crawl_policies (mélység, ütemezés, robots)
                    └── archived_snapshots (WACZ ref. + Dublin Core + PREMIS)
                          └── page_chunks (szövegdarabok + pgvector embedding)
```

### Kulcs Schema elemek

```sql
-- Minden snapshot kap PID-et
archived_snapshots.pid              VARCHAR(30) UNIQUE  -- pl. fewa:2026:000001

-- 8-állapotú életciklus
archived_snapshots.lifecycle_status VARCHAR(20)
  -- candidate → approved → crawling → archived → indexed → published → deprecated → withdrawn

-- Hibrid keresés
archived_snapshots.search_vector    TSVECTOR  -- automatikus trigger frissíti
page_chunks.embedding               vector(768)  -- HNSW index

-- Embedding verziókövetés
page_chunks.embedding_model         VARCHAR(100)  -- pl. 'nomic-embed-text'
page_chunks.embedding_version       VARCHAR(20)   -- pl. '1.5'

-- AI Observability
ai_traces.prompt_text               TEXT
ai_traces.retrieved_chunks          JSONB
ai_traces.confidence_score          NUMERIC(4,3)
ai_traces.user_feedback             VARCHAR(10)  -- 'helpful'/'unhelpful'/'wrong'

-- Duplikátum szűrés
archived_snapshots.content_hash     CHAR(64) UNIQUE  -- SHA-256 normalizált
archived_snapshots.simhash          CHAR(64)         -- közel-duplikátumokhoz
```

### Teljesítmény indexek
```sql
-- pgvector HNSW (100 000+ chunk felett <100ms)
CREATE INDEX ON page_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Full-Text Search
CREATE INDEX ON archived_snapshots USING GIN (search_vector);

-- dc_subject tömb keresés
CREATE INDEX ON archived_snapshots USING GIN (dc_subject);

-- Szűrők
CREATE INDEX ON archived_snapshots (crawl_timestamp DESC);
CREATE INDEX ON archived_snapshots (municipality);
CREATE INDEX ON archived_snapshots (lifecycle_status);
```

---

## 7. AI Pipeline Részletek

### Chunking paraméterek
| Paraméter | Érték |
|---|---|
| chunk_size | 600 token |
| chunk_overlap | 100 token |
| min_chunk_len | 50 token |
| splitter | mondathatár-alapú |

### Ollama LLM Profilok (admin felületen váltható)
| Profil | Modell | Kontextus | Mikor |
|---|---|---|---|
| Fast | qwen2.5:3b | 4 096 token | Nagy tömegű napi crawl |
| Balanced | qwen2.5:7b | 8 192 token | Normál archiválás |
| HighQuality | gemma3:12b | 12 288 token | Éves összesítők |

### RAG Guardrails
1. **Strict Context-Only** — csak a top-3 chunk alapján válaszolhat
2. **JSON Schema Validation** — Pydantic v2 struktúra-ellenőrzés
3. **Citation Check** — minden állítás mellett forrás URL + crawl_timestamp kötelező
4. **Confidence Threshold** — ha `confidence_score < 0.6` → *"Nincs elegendő bizonyíték az archívumban."*
5. **UI figyelmeztetés** — *"Kísérleti AI-válasz — ellenőrizze az eredeti forrást"*

---

## 8. Objektumtároló (MinIO)

```
Browsertrix → WACZ fájl → MinIO S3 bucket
                               │
PostgreSQL csak ezt tárolja:   │
  wacz_minio_path ─────────────┘
  wacz_sha256
  wacz_filesize
  mime_type
  crawl_timestamp

MinIO bekapcsolt funkciók:
  ✅ Bucket Versioning
  ✅ Object Lock (GOVERNANCE mód)
  ✅ Server-Side Encryption (SSE-S3)
  ✅ Lifecycle Policy (1 év után GLACIER)
```

---

## 9. RBAC Jogosultságok

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

---

## 10. OAI-PMH 2.0 Végpont

Mind a 6 kötelező ige implementálva:

| Ige | Leírás |
|---|---|
| `Identify` | Gyűjtemény metaadatok, adminEmail |
| `ListSets` | Collection hierarchia |
| `ListMetadataFormats` | oai_dc, mets, mods |
| `ListIdentifiers` | Rekord ID-k lapozva |
| `ListRecords` | Teljes rekordok |
| `GetRecord` | Egyedi rekord PID alapján |

Kompatibilis: **DSpace, Omeka, Koha, AtoM, OSZK**

---

## 11. Biztonsági Hardening

```
Nginx:
  ✅ HSTS (max-age=31536000; includeSubDomains; preload)
  ✅ CSP (Content-Security-Policy)
  ✅ X-Frame-Options: SAMEORIGIN
  ✅ Rate limiting: API 30r/m, RAG 10r/m

Intrusion Detection:
  ✅ Fail2ban (5 hiba → 1 óra ban)
  ✅ CrowdSec (közösségi IP reputáció)

FastAPI:
  ✅ JWT RS256 hitelesítés
  ✅ CORS whitelist
  ✅ Pydantic input validáció
  ✅ Paraméteres asyncpg lekérdezések (SQL injection védelem)
```

---

## 12. Monitoring Stack

| Konténer | Szerepe |
|---|---|
| Prometheus + Alertmanager | Metrikák + email/Telegram riasztások |
| Grafana | Dashboardok |
| Loki | Log aggregátor |
| Node Exporter | Host OS metrikák |
| cAdvisor | Docker konténer metrikák |
| Postgres Exporter | pgvector lekérdezési idők, táblaméret |

### Riasztások (példák)
| Riasztás | Küszöb |
|---|---|
| Arq queue feltöltöttség | > 100 feladat |
| Disk usage (MinIO) | > 85% |
| Ollama nem elérhető | > 60 másodperc |
| Crawl hibaarány | > 20% / 1 óra |

---

## 13. Backup & Disaster Recovery

| Ütemezés | Rendszer | Módszer | Megőrzés |
|---|---|---|---|
| Naponta | PostgreSQL | pg_dump → lokális + SFTP offsite | 30 nap |
| Naponta | Audit Log | pg_dump (audit_logs tábla) | 5 év |
| Hetente | MinIO WACZ | mc mirror → backup NAS | 52 hét |
| Havonta | MinIO teljes bucket | mc admin snapshot | 12 hónap |
| Évente | Archív snapshot | Offline HDD + digitális aláírás | Végleges |
| Folyamatos | MinIO Object Versioning | Bucket szintű | Korlátlan |
| Verziókövetett | SKOS Tezaurusz | Git repository (tezaurusz.ttl) | Teljes history |

**RPO:** ≤ 24 óra | **RTO:** ≤ 4 óra

---

## 14. Jogi Megfelelőség

- **OSZK egyeztetés:** Együttműködési megállapodás a regionális gyűjtőkör jogi tisztázásához
- **robots.txt:** Alapértelmezésben tiszteletben tartva; felülírás csak könyvtárvezetői engedéllyel
- **Opt-out:** E-mail / webes űrlap → 30 napon belül törlés (soft delete + Object Lock delete marker)
- **GDPR:** Audit log IP-k anonimizálása 1 év után; belső fiókok törlési kérésre soft delete
- **Megőrzési idők:** WACZ korlátlan (kulturális örökség); audit log 5 év; AI cache 90 nap

---

## 15. Üzemeltetési Környezetek

| Jellemző | Development | Staging | Production |
|---|---|---|---|
| Ollama modell | qwen2.5:3b (Fast) | qwen2.5:7b (Balanced) | Admin által konfigurált |
| MinIO | localhost:9000 | Teszt bucket | Prod bucket |
| Monitoring | Kikapcsolva | Prometheus local | Teljes stack |
| HTTPS | Kikapcsolva | Self-signed | Let's Encrypt |

### Frissítési folyamat
```bash
# 1. Mentés
docker exec fewa-postgres pg_dump -U fewa_admin fewa_v3 > backup_pre_update.pgdump

# 2. Frissítés (zero downtime)
docker compose pull
docker compose up -d --no-deps fewa-backend fewa-worker
docker compose up -d --no-deps fewa-frontend fewa-admin

# 3. Rollback ha szükséges
docker compose down fewa-backend
docker compose up -d fewa-backend  # előző stabil kép
```

---

# III. RÉSZ — FEJLESZTŐI SPECIFIKÁCIÓ

## 16. Implementációs Sorrend (7 Fázis, 14 hét)

| Fázis | Tartalom | Időkeret |
|---|---|---|
| **1** | PostgreSQL V3.1 schema + HNSW index + Redis szétválasztás + MinIO | 1-2. hét |
| **2** | FastAPI core (db, security, models) + Arq worker engine | 3-4. hét |
| **3** | AI Pipeline (7 lépcsős) + AI Cache + AI Traces + Dedup | 5-6. hét |
| **4** | REST API végpontok + OAI-PMH 6 ige + OpenAPI docs | 7-8. hét |
| **5** | Next.js SSR frontend (főoldal, keresés, replay, RAG UI) | 9-10. hét |
| **6** | React Admin SPA (queue, policies, thesaurus, lifecycle, traces) | 11-12. hét |
| **7** | Monitoring + Nginx hardening + Fail2ban + Discovery Sync | 13-14. hét |

## 17. Könyvtárszerkezet

```
webachivum/
├── docs/
│   └── FEWA_V3.1_V4_Mesterterv.md     ← Ez a dokumentum
├── fewa-v3-backend/
│   ├── app/
│   │   ├── api/          (search, rag, collections, oaipmh, admin/*)
│   │   ├── core/         (config, security, db, minio_client)
│   │   ├── pipeline/     (hard_filter, nlp_ner, llm_enrich, qc_engine, dedup, chunker)
│   │   ├── workers/      (arq_worker, scheduler)
│   │   └── main.py
│   ├── db/schema_v3_1.sql
│   ├── tests/
│   └── requirements.txt
├── fewa-v3-frontend/     (Next.js 15 SSR)
├── fewa-v3-admin/        (Vite + React SPA)
├── monitoring/           (prometheus.yml, alertmanager.yml, grafana/)
├── nginx/fewa.conf
└── docker-compose.yml
```

## 18. REST API Végpontok

| Metódus | Végpont | RBAC |
|---|---|---|
| GET | `/api/health` | Public |
| GET | `/api/search?q=&municipality=&from_date=` | Public |
| GET | `/api/documents/{id}` | Public |
| GET | `/api/collections` | Public |
| POST | `/api/rag` | Public |
| GET | `/api/statistics` | Public |
| GET | `/oai?verb=ListRecords&metadataPrefix=oai_dc` | Public |
| GET | `/api/admin/queue` | Curator+ |
| POST | `/api/admin/queue/{id}/approve` | Curator+ |
| POST | `/api/admin/queue/{id}/reject` | Curator+ |
| GET | `/api/admin/policies` | Archivist+ |
| POST | `/api/admin/ingest` | Archivist+ |
| GET | `/api/admin/jobs` | Archivist+ |
| GET | `/api/admin/audit` | Archivist+ |
| GET | `/api/thesaurus` | Viewer+ |
| POST | `/api/thesaurus` | Curator+ |

*(OpenAPI dokumentáció automatikusan: `/docs` és `/redoc`)*

## 19. Python Függőségek

```
fastapi>=0.115.0          # Web framework
uvicorn[standard]>=0.30.0 # ASGI szerver
asyncpg>=0.29.0           # PostgreSQL async driver
pgvector>=0.3.0           # pgvector Python kliens
pydantic>=2.7.0           # Adatvalidáció
pydantic-settings>=2.3.0  # Konfiguráció
python-jose[cryptography]>=3.3.0  # JWT RS256
boto3>=1.34.0             # MinIO S3 kliens
arq>=0.26.0               # Async task queue
redis>=5.0.0              # Redis kliens
ollama>=0.2.0             # Ollama API kliens
spacy>=3.7.0              # NLP (+ hu_core_news_lg)
trafilatura>=1.12.0       # Szövegkinyerés WARC-ból
warcio>=1.7.4             # WACZ/WARC olvasó
simhash>=2.1.2            # Közel-duplikátum szűrés
paramiko>=3.4.0           # SSH Pull (discovery sync)
apscheduler>=3.10.0       # Cron ütemező
httpx>=0.27.0             # Async HTTP kliens
lxml>=5.2.0               # OAI-PMH XML generálás
python-multipart>=0.0.9   # Fájlfeltöltés
```

## 20. Ellenőrzési Lista (Go-Live előtt)

- [ ] pgvector HNSW index létrehozva, `\d page_chunks` mutatja
- [ ] MinIO: bucket versioning + object lock aktív (`mc ls --versions`)
- [ ] AI Cache: 2. futtatásnál Ollama log 0 hívást mutat
- [ ] PID: minden snapshot kap `fewa:2026:NNNNNN` azonosítót
- [ ] Életciklus: `candidate → published` átmenet `lifecycle_events`-ben naplózva
- [ ] OAI-PMH: `ListRecords?metadataPrefix=oai_dc` W3C valid XML-t ad
- [ ] RAG guardrail: `confidence < 0.6` → *"Nincs elegendő bizonyíték"*
- [ ] RBAC: Viewer HTTP 403-at kap `/api/admin/queue`-ra
- [ ] Alertmanager: teszt riasztás → email megérkezett
- [ ] WCAG 2.1 AA: axe-core 0 kritikus hibával fut le
- [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95

---

## V4 Ütemterv (2027+)

| Komponens | Leírás |
|---|---|
| **Eseményalapú architektúra** | NATS JetStream + CloudEvents séma; minden pipeline lépés önállóan újraindítható |
| **Digitális Objektum Modell** | PDF, kép, videó, hanganyag, oral history, dataset támogatás |
| **Knowledge Graph** | Apache AGE (PostgreSQL-en belül) vagy Neo4j; személy–intézmény–esemény–dokumentum gráf |
| **Authority Control** | Entitás-összevonás (VMK = Vörösmarty Könyvtár = Vörösmarty Mihály Könyvtár) |
| **Tezaurusz mikroszolgáltatás** | Önálló FastAPI service, SKOS TTL/RDF export/import, Git-alapú verziózás |
| **Multi-tenant** | PostgreSQL RLS; más könyvtárak csatlakoztatása (pl. Esterházy Archívum) |
| **Handle.net / DOI** | PID (`fewa:2026:000001`) → Handle vagy DOI prefix integrációja |

---

*Dokumentum vége — FEWA V3.1 → V4 Mesterdokumentum*
*Vörösmarty Mihály Könyvtár, Székesfehérvár · 2026*
