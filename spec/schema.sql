-- =============================================================================
-- FEWA V3.1 — Teljes PostgreSQL DDL séma
-- Vörösmarty Mihály Könyvtár, Székesfehérvár
-- Verzió: 3.1.0 | Dátum: 2026-07-28
-- Phase 2 — spec-first megközelítés
-- =============================================================================
-- Futtatás: psql -U fewa_admin -d fewa_v3 -f schema.sql
-- Előfeltétel: PostgreSQL 16+, pgvector extension
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";         -- pgvector
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- trigram index (fuzzy search)
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- ékezet-független keresés

-- ---------------------------------------------------------------------------
-- Custom ENUM típusok
-- ---------------------------------------------------------------------------

CREATE TYPE lifecycle_status_enum AS ENUM (
    'candidate',    -- felfedező jelöli, nincs jóváhagyva
    'approved',     -- kurátor jóváhagyta, crawl indítható
    'crawling',     -- aktív crawl folyamatban
    'archived',     -- WACZ feltöltve MinIO-ba, AI pipeline várja
    'indexed',      -- AI pipeline lefutott, chunk-ok megvannak
    'published',    -- publikusan kereshető
    'deprecated',   -- elavult, de megőrzött
    'withdrawn'     -- tartalom eltávolítva (opt-out / jogi)
);

CREATE TYPE crawl_priority_enum AS ENUM (
    'critical',     -- pl. önkormányzati portálok, napi mentés
    'high',         -- médiaoldalak, hetente
    'medium',       -- civil szervezetek, havonta
    'low',          -- alkalmi, eseményvezérelt
    'on_hold'       -- ideiglenesen szüneteltetett
);

CREATE TYPE site_category_enum AS ENUM (
    'kozintézmény',     -- önkormányzat, hivatal, iskola, kórház
    'civil',            -- egyesület, alapítvány, nonprofit
    'média',            -- hírportál, rádió, újság
    'vállalkozás',      -- helyi cég, kereskedelmi
    'kulturális',       -- múzeum, könyvtár, színház
    'egyéb'
);

CREATE TYPE crawl_frequency_enum AS ENUM (
    'daily',
    'weekly',
    'monthly',
    'quarterly',
    'event_driven',     -- kurátor manuálisan triggereli
    'once'              -- egyszeri archívum
);

CREATE TYPE oszk_status_enum AS ENUM (
    'yes',              -- OSZK aktívan gyűjti
    'no',               -- OSZK nem gyűjti (FEWA egyedüli forrás)
    'unknown',          -- nem ellenőrzött
    'partial'           -- OSZK részben gyűjti (pl. más scope)
);

CREATE TYPE job_type_enum AS ENUM (
    'crawl',
    'enrich',
    'reindex',
    'export_oaipmh',
    'reembed'           -- embedding modell-váltás utáni újrafuttatás
);

CREATE TYPE job_status_enum AS ENUM (
    'queued',
    'running',
    'completed',
    'failed',
    'dead_lettered'
);

CREATE TYPE llm_profile_enum AS ENUM (
    'fast',             -- qwen2.5:3b, 4096 ctx
    'balanced',         -- qwen2.5:7b, 8192 ctx
    'high_quality'      -- gemma3:12b, 12288 ctx
);

CREATE TYPE user_role_enum AS ENUM (
    'admin',
    'archivist',
    'curator',
    'indexer',
    'viewer',
    'guest'
);

-- ---------------------------------------------------------------------------
-- 1. TENANTS — V4 előkészítve (V3.1-ben egyetlen tenant: VMK)
-- ---------------------------------------------------------------------------

CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(50) UNIQUE NOT NULL,    -- pl. 'vmk', 'eszterhazy'
    name        TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE tenants IS 'V4 multi-tenant előkészítés. V3.1-ben egyetlen rekord: VMK.';

-- Alap tenant seed (migration-ban futtatandó, nem idempotens — lásd: seed_data.sql)
-- INSERT INTO tenants (id, slug, name) VALUES ('00000000-0000-0000-0000-000000000001', 'vmk', 'Vörösmarty Mihály Könyvtár');

-- ---------------------------------------------------------------------------
-- 2. USERS — Felhasználói fiókok
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    email           VARCHAR(254) NOT NULL,
    password_hash   TEXT NOT NULL,              -- bcrypt, sosem plain text
    role            user_role_enum NOT NULL DEFAULT 'viewer',
    full_name       TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,                -- soft delete, GDPR

    CONSTRAINT users_email_tenant_unique UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant ON users (tenant_id);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_active ON users (tenant_id, is_active) WHERE deleted_at IS NULL;

COMMENT ON COLUMN users.deleted_at IS 'Soft delete: GDPR törlési kérésre töltjük ki, a rekord megmarad az audit logban.';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash. Min cost=12. Soha nem tároljuk a plain text jelszót.';

-- ---------------------------------------------------------------------------
-- 3. COLLECTIONS — Kurátori gyűjtemények (Archive domain)
-- ---------------------------------------------------------------------------

CREATE TABLE collections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    created_by      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL,
    description     TEXT,
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT collections_name_tenant_unique UNIQUE (tenant_id, name)
);

CREATE INDEX idx_collections_tenant ON collections (tenant_id);

-- ---------------------------------------------------------------------------
-- 4. MUNICIPALITIES — Fejér vm. önkormányzati egységek lookup táblája
-- ---------------------------------------------------------------------------
-- Kurátori felületen lenyíló listaként jelenik meg.
-- Bővíthető: új önkormányzat hozzáadása nem igényel séma-változtatást.

CREATE TABLE municipalities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150) NOT NULL UNIQUE,   -- pl. 'Székesfehérvár'
    slug        VARCHAR(100) NOT NULL UNIQUE,   -- pl. 'szekesfehervar' (URL-safe)
    county      VARCHAR(100) NOT NULL DEFAULT 'Fejér',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,  -- inaktív: nem jelenik meg a lenyílóban
    sort_order  SMALLINT NOT NULL DEFAULT 100,  -- sorrend a lenyílóban (kisebb = előbb)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_municipalities_active ON municipalities (is_active, sort_order)
    WHERE is_active = TRUE;

COMMENT ON TABLE municipalities IS 'Fejér vm. önkormányzati egységek kontrolált listája. Kurátori felületen lenyílóként jelenik meg.';
COMMENT ON COLUMN municipalities.slug IS 'URL-safe, ékezet nélküli azonosító. API szűrőparaméterként is használható.';
COMMENT ON COLUMN municipalities.is_active IS 'FALSE: megőrizzük a régi rekordokat, de az UI nem mutatja új bejegyzésnél.';

-- ---------------------------------------------------------------------------
-- 5. SITES — Domain-szintű bejegyzések + kurátori prioritizálás
-- ---------------------------------------------------------------------------
-- Ez a tábla lett kibővítve a Phase 2 kontextus alapján:
-- priority, category, frequency, curator_notes, oszk_status, is_active_collection

CREATE TABLE sites (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    collection_id           UUID REFERENCES collections(id) ON DELETE SET NULL,

    -- Domain azonosítás
    domain                  VARCHAR(253) NOT NULL,              -- pl. 'alba.hu'
    base_url                TEXT NOT NULL,                      -- pl. 'https://alba.hu'
    display_name            TEXT,                               -- emberi olvasásra

    -- Kurátori prioritizálás (Phase 2 kontextus)
    priority                crawl_priority_enum NOT NULL DEFAULT 'medium',
    category                site_category_enum NOT NULL DEFAULT 'egyéb',
    crawl_frequency         crawl_frequency_enum NOT NULL DEFAULT 'monthly',
    curator_notes           TEXT,                               -- szabad szöveges megjegyzés
    oszk_status             oszk_status_enum NOT NULL DEFAULT 'unknown',
    is_active_collection    BOOLEAN NOT NULL DEFAULT TRUE,      -- be/ki kapcsolható gyűjtés

    -- Technikai adatok
    robots_txt_respect      BOOLEAN NOT NULL DEFAULT TRUE,
    requires_js             BOOLEAN NOT NULL DEFAULT FALSE,     -- Browsertrix JS-rendered
    scope_restriction       TEXT,                               -- ha csak aldomain archiválandó

    -- Metaadatok
    municipality_id         UUID REFERENCES municipalities(id) ON DELETE SET NULL,  -- FK lookup táblára
    added_by                UUID REFERENCES users(id) ON DELETE SET NULL,
    last_crawled_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT sites_domain_tenant_unique UNIQUE (tenant_id, domain)
);

COMMENT ON COLUMN sites.priority IS 'Gyűjtési prioritás — kurátori felületen módosítható bármikor.';
COMMENT ON COLUMN sites.category IS 'Webhely kategória: közintézmény, civil, média, vállalkozás, kulturális, egyéb.';
COMMENT ON COLUMN sites.crawl_frequency IS 'Tervezett gyűjtési frekvencia. Az actual crawl ütemező ezt veszi alapul.';
COMMENT ON COLUMN sites.curator_notes IS 'Szabad szöveges kurátori megjegyzés — pl. "csak a /hirek aloldalt archivájuk".';
COMMENT ON COLUMN sites.oszk_status IS 'Az OSZK webarchívuma gyűjti-e ezt az oldalt? Duplikáció-elkerülés.';
COMMENT ON COLUMN sites.is_active_collection IS 'FALSE: a site bejegyezve, de gyűjtés szünetel (pl. oldal megszűnt).';
COMMENT ON COLUMN sites.municipality_id IS 'FK a municipalities táblára. Kurátori felületen lenyílóból választható.';

CREATE INDEX idx_sites_tenant ON sites (tenant_id);
CREATE INDEX idx_sites_collection ON sites (collection_id);
CREATE INDEX idx_sites_priority ON sites (tenant_id, priority) WHERE is_active_collection = TRUE;
CREATE INDEX idx_sites_municipality ON sites (municipality_id);
CREATE INDEX idx_sites_category ON sites (category);
CREATE INDEX idx_sites_active ON sites (tenant_id, is_active_collection);

-- ---------------------------------------------------------------------------
-- 5. CRAWL_POLICIES — Technikai crawl paraméterek (Sites 1:N)
-- ---------------------------------------------------------------------------

CREATE TABLE crawl_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name            TEXT NOT NULL DEFAULT 'default',

    -- Crawl paraméterek
    depth           SMALLINT NOT NULL DEFAULT 3 CHECK (depth BETWEEN 1 AND 5),
    max_pages       INTEGER NOT NULL DEFAULT 5000 CHECK (max_pages > 0),
    page_limit      INTEGER NOT NULL DEFAULT 500,           -- per-crawl limit
    cron_schedule   TEXT NOT NULL DEFAULT '0 2 * * 0',     -- minden vasárnap 02:00
    llm_profile     llm_profile_enum NOT NULL DEFAULT 'balanced',

    -- Szűrők
    include_patterns    TEXT[],             -- pl. ARRAY['/hirek/*', '/archivum/*']
    exclude_patterns    TEXT[],             -- pl. ARRAY['/admin/*', '/login']
    allowed_mime_types  TEXT[] NOT NULL DEFAULT ARRAY['text/html', 'application/pdf'],

    is_default      BOOLEAN NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT crawl_policies_site_name_unique UNIQUE (site_id, name)
);

COMMENT ON COLUMN crawl_policies.depth IS 'Maximális crawl mélység. Architektúrális korlát: 1-5.';
COMMENT ON COLUMN crawl_policies.cron_schedule IS 'Standard cron expression. TZ: Europe/Budapest.';
COMMENT ON COLUMN crawl_policies.include_patterns IS 'Ha megadva, csak ezeket az útvonalakat archivájuk.';

CREATE INDEX idx_crawl_policies_site ON crawl_policies (site_id);
CREATE INDEX idx_crawl_policies_active ON crawl_policies (is_active) WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- 6. ARCHIVED_SNAPSHOTS — A core archívum tábla
-- ---------------------------------------------------------------------------

CREATE TABLE archived_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
    collection_id   UUID REFERENCES collections(id) ON DELETE SET NULL,

    -- Perzisztens azonosító (PID)
    pid             VARCHAR(30) UNIQUE,         -- pl. 'fewa:2026:000001' — trigger tölti ki

    -- Életciklus
    lifecycle_status    lifecycle_status_enum NOT NULL DEFAULT 'candidate',
    lifecycle_reason    TEXT,                   -- utolsó státuszváltás oka

    -- WACZ tárolás (MinIO referencia)
    wacz_minio_path     TEXT,                   -- pl. 'wacz/2026/07/abc123.wacz'
    wacz_sha256         CHAR(64),               -- integritás-ellenőrzés
    wacz_filesize_bytes BIGINT,
    wacz_page_count     INTEGER,

    -- Duplikátum-szűrés
    content_hash        CHAR(64) UNIQUE,        -- SHA-256 normalizált tartalom
    simhash             CHAR(16),               -- 64-bit SimHash hex — közel-duplikátumokhoz
    simhash_threshold   SMALLINT DEFAULT 3,     -- Hamming-távolság küszöb (0-64)

    -- Dublin Core metaadatok
    dc_title            TEXT,
    dc_description      TEXT,
    dc_creator          TEXT,
    dc_publisher        TEXT,
    dc_subject          TEXT[],                 -- SKOS tezaurusz fogalmak
    dc_language         VARCHAR(10) DEFAULT 'hu',
    dc_coverage         TEXT,                   -- földrajzi lefedettség
    dc_rights           TEXT,
    dc_type             TEXT DEFAULT 'Website',

    -- Keresési metaadatok
    municipality_id     UUID REFERENCES municipalities(id) ON DELETE SET NULL,  -- FK lookup
    crawl_timestamp     TIMESTAMPTZ,            -- mikor archivált
    crawl_duration_s    INTEGER,
    seed_url            TEXT NOT NULL,          -- archívum kiindulópontja

    -- Full-text keresés (automatikus trigger frissíti)
    search_vector       TSVECTOR,

    -- AI metaadatok (AI context tölti ki)
    ai_summary          TEXT,
    ai_keywords         TEXT[],
    qc_score            SMALLINT CHECK (qc_score BETWEEN 0 AND 100),
    embedding_model     VARCHAR(100),           -- pl. 'nomic-embed-text'
    embedding_version   VARCHAR(20),            -- pl. '1.5'

    -- PREMIS (digitális megőrzés)
    premis_object_id    TEXT,
    premis_event_log    JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Audit
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN archived_snapshots.pid IS 'Perzisztens azonosító: fewa:YYYY:NNNNNN. Trigger generálja automatikusan published státusznál.';
COMMENT ON COLUMN archived_snapshots.content_hash IS 'SHA-256 a normalizált (whitespace-stripped) oldalszövegre. Egzakt duplikátum-szűrés.';
COMMENT ON COLUMN archived_snapshots.simhash IS '64-bit SimHash hex. Hamming-távolság < simhash_threshold → közel-duplikátum.';
COMMENT ON COLUMN archived_snapshots.dc_subject IS 'SKOS tezaurusz preferred label-ek tömbje. GIN index a hatékony szűréshez.';
COMMENT ON COLUMN archived_snapshots.search_vector IS 'tsvector a hibrid kereséshez. Trigger automatikusan frissíti dc_title + dc_description + ai_summary változáskor.';
COMMENT ON COLUMN archived_snapshots.premis_event_log IS 'JSONB tömb: minden életciklus-esemény PREMIS formátumban.';

-- Teljesítmény indexek
CREATE INDEX idx_snapshots_tenant ON archived_snapshots (tenant_id);
CREATE INDEX idx_snapshots_site ON archived_snapshots (site_id);
CREATE INDEX idx_snapshots_lifecycle ON archived_snapshots (lifecycle_status);
CREATE INDEX idx_snapshots_municipality ON archived_snapshots (municipality_id);
CREATE INDEX idx_snapshots_crawl_ts ON archived_snapshots (crawl_timestamp DESC);
CREATE INDEX idx_snapshots_collection ON archived_snapshots (collection_id);
CREATE INDEX idx_snapshots_qc ON archived_snapshots (qc_score) WHERE qc_score IS NOT NULL;

-- GIN indexek
CREATE INDEX idx_snapshots_search_vector ON archived_snapshots USING GIN (search_vector);
CREATE INDEX idx_snapshots_dc_subject ON archived_snapshots USING GIN (dc_subject);
CREATE INDEX idx_snapshots_ai_keywords ON archived_snapshots USING GIN (ai_keywords);

-- Partial index: csak publikus snapshot-ok
CREATE INDEX idx_snapshots_published ON archived_snapshots (crawl_timestamp DESC, municipality_id)
    WHERE lifecycle_status = 'published';

-- ---------------------------------------------------------------------------
-- 7. PID SZEKVENCIA + TRIGGER
-- ---------------------------------------------------------------------------

CREATE SEQUENCE pid_sequence START 1 INCREMENT 1;

CREATE OR REPLACE FUNCTION generate_pid()
RETURNS TRIGGER AS $$
BEGIN
    -- PID-et csak published státusznál és ha még nincs
    IF NEW.lifecycle_status = 'published' AND NEW.pid IS NULL THEN
        NEW.pid := 'fewa:' || EXTRACT(YEAR FROM now())::TEXT || ':' ||
                   LPAD(nextval('pid_sequence')::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generate_pid
    BEFORE INSERT OR UPDATE ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION generate_pid();

-- ---------------------------------------------------------------------------
-- 8. SEARCH_VECTOR TRIGGER
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('hungarian', COALESCE(NEW.dc_title, '')), 'A') ||
        setweight(to_tsvector('hungarian', COALESCE(NEW.dc_description, '')), 'B') ||
        setweight(to_tsvector('hungarian', COALESCE(NEW.ai_summary, '')), 'C') ||
        setweight(to_tsvector('hungarian', COALESCE(array_to_string(NEW.dc_subject, ' '), '')), 'B');
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_search_vector
    BEFORE INSERT OR UPDATE OF dc_title, dc_description, ai_summary, dc_subject
    ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- ---------------------------------------------------------------------------
-- 9. LIFECYCLE_EVENTS — Életciklus-átmenetek naplója
-- ---------------------------------------------------------------------------

CREATE TABLE lifecycle_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id     UUID NOT NULL REFERENCES archived_snapshots(id) ON DELETE CASCADE,
    from_status     lifecycle_status_enum,
    to_status       lifecycle_status_enum NOT NULL,
    triggered_by    UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL = rendszer
    reason          TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,             -- extra kontextus
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lifecycle_events_snapshot ON lifecycle_events (snapshot_id);
CREATE INDEX idx_lifecycle_events_ts ON lifecycle_events (occurred_at DESC);

COMMENT ON TABLE lifecycle_events IS 'Immutable napló: minden lifecycle átmenet rögzített. Törlés tilos.';
COMMENT ON COLUMN lifecycle_events.triggered_by IS 'NULL = automatikus rendszer-átmenet (pl. crawl befejezése).';

-- ---------------------------------------------------------------------------
-- 10. PAGE_CHUNKS — Szövegdarabok + pgvector embedding
-- ---------------------------------------------------------------------------

CREATE TABLE page_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id         UUID NOT NULL REFERENCES archived_snapshots(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL CHECK (chunk_index >= 0),
    content             TEXT NOT NULL,
    token_count         INTEGER NOT NULL CHECK (token_count > 0),

    -- Embedding
    embedding           vector(768),            -- nomic-embed-text-v1.5 dimenziója
    embedding_model     VARCHAR(100),           -- pl. 'nomic-embed-text'
    embedding_version   VARCHAR(20),            -- pl. '1.5'
    embedded_at         TIMESTAMPTZ,            -- mikor készült az embedding

    -- Chunk metaadatok
    page_url            TEXT,                   -- melyik oldalról jött a chunk
    char_offset         INTEGER,                -- karakterpozíció a raw text-ben

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT page_chunks_unique UNIQUE (snapshot_id, chunk_index)
);

COMMENT ON COLUMN page_chunks.embedding IS 'nomic-embed-text 768-dimenziós vektor. Ha NULL: embedding még nem készült.';
COMMENT ON COLUMN page_chunks.embedding_version IS 'Embedding modell verziója. Verzióváltáskor a chunk újra kell embeddelni.';
COMMENT ON COLUMN page_chunks.embedded_at IS 'Mikor készült az embedding. NULL = pending re-embedding.';

-- HNSW index pgvector-hoz (100k+ chunk felett <100ms)
CREATE INDEX idx_page_chunks_hnsw ON page_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Partial index: csak kész embedding-ek az HNSW-ben
CREATE INDEX idx_page_chunks_embedded ON page_chunks (snapshot_id)
    WHERE embedding IS NOT NULL;

-- Re-embedding queue index
CREATE INDEX idx_page_chunks_reembed_queue ON page_chunks (embedding_version, embedded_at)
    WHERE embedded_at IS NULL OR embedding IS NULL;

-- ---------------------------------------------------------------------------
-- 11. AI_TRACES — AI Observability
-- ---------------------------------------------------------------------------

CREATE TABLE ai_traces (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id             UUID REFERENCES archived_snapshots(id) ON DELETE SET NULL,
    trace_type              VARCHAR(30) NOT NULL,       -- 'rag_query' | 'enrichment' | 'ner'

    -- Input
    prompt_text             TEXT,
    prompt_template_version VARCHAR(20),                -- pl. 'summary-v2.1'
    ollama_model            VARCHAR(50),                -- konkrét modell (nem profil)
    retrieved_chunks        JSONB,                      -- top-k chunk UUID + score

    -- Output
    response_text           TEXT,
    confidence_score        NUMERIC(4, 3) CHECK (confidence_score BETWEEN 0 AND 1),

    -- Teljesítmény
    embedding_latency_ms    INTEGER,
    llm_latency_ms          INTEGER,
    total_latency_ms        INTEGER,
    cache_hit               BOOLEAN NOT NULL DEFAULT FALSE,

    -- Felhasználói visszajelzés
    user_feedback           VARCHAR(15) CHECK (user_feedback IN ('helpful', 'unhelpful', 'wrong')),
    feedback_note           TEXT,

    -- Audit
    user_id                 UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN ai_traces.prompt_template_version IS 'A prompt template verziója. Kritikus: különböző verziók összehasonlíthatatlanok.';
COMMENT ON COLUMN ai_traces.confidence_score IS 'RAG guardrail: ha < 0.6, a rendszer "Nincs elegendő bizonyíték" választ ad.';
COMMENT ON COLUMN ai_traces.cache_hit IS 'TRUE: az AI cache-ből szolgálta ki, Ollama nem lett meghívva.';
COMMENT ON COLUMN ai_traces.user_feedback IS 'RLHF-light: unhelpful/wrong rekordok felülvizsgálati queue-ba kerülnek.';

CREATE INDEX idx_ai_traces_snapshot ON ai_traces (snapshot_id);
CREATE INDEX idx_ai_traces_type ON ai_traces (trace_type);
CREATE INDEX idx_ai_traces_ts ON ai_traces (created_at DESC);
CREATE INDEX idx_ai_traces_feedback ON ai_traces (user_feedback) WHERE user_feedback IS NOT NULL;
CREATE INDEX idx_ai_traces_confidence ON ai_traces (confidence_score) WHERE confidence_score < 0.6;

-- ---------------------------------------------------------------------------
-- 12. SKOS_CONCEPTS — Tezaurusz
-- ---------------------------------------------------------------------------

CREATE TABLE skos_concepts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,

    -- SKOS alapmezők
    uri                 TEXT UNIQUE NOT NULL,           -- pl. 'http://fewa.vmk.hu/thesaurus/helyi-politika'
    pref_label_hu       TEXT NOT NULL,                  -- elsődleges magyar label
    pref_label_en       TEXT,                           -- opcionális angol
    alt_labels          TEXT[],                         -- szinonimák
    definition          TEXT,
    scope_note          TEXT,
    notation            TEXT,                           -- pl. 'HE-123'

    -- Hierarchia
    broader_id          UUID REFERENCES skos_concepts(id) ON DELETE SET NULL,
    related_ids         UUID[],                         -- asszociatív kapcsolatok

    -- Verziókövetés
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deprecated       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_skos_pref_label ON skos_concepts USING GIN (to_tsvector('hungarian', pref_label_hu));
CREATE INDEX idx_skos_alt_labels ON skos_concepts USING GIN (alt_labels);
CREATE INDEX idx_skos_broader ON skos_concepts (broader_id);
CREATE INDEX idx_skos_tenant ON skos_concepts (tenant_id);

-- ---------------------------------------------------------------------------
-- 13. JOBS — Aszinkron feladatok (Arq workers)
-- ---------------------------------------------------------------------------

CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    job_type        job_type_enum NOT NULL,
    status          job_status_enum NOT NULL DEFAULT 'queued',

    -- Referencia (melyik entitáshoz tartozik)
    snapshot_id     UUID REFERENCES archived_snapshots(id) ON DELETE SET NULL,
    site_id         UUID REFERENCES sites(id) ON DELETE SET NULL,

    -- Arq job azonosítás
    arq_job_id      TEXT,                       -- Arq belső job ID

    -- Payload (Pydantic séma alapján)
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Futtatás
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    max_retries     SMALLINT NOT NULL DEFAULT 3,
    error_message   TEXT,
    error_detail    JSONB,

    -- Teljesítmény
    queued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER GENERATED ALWAYS AS (
                        CASE WHEN started_at IS NOT NULL AND completed_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER * 1000
                        ELSE NULL END
                    ) STORED,

    created_by      UUID REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON COLUMN jobs.duration_ms IS 'Automatikusan számított: completed_at - started_at (ms). NULL ha még fut.';
COMMENT ON COLUMN jobs.payload IS 'JSON payload — CrawlJobPayload vagy EnrichJobPayload Pydantic séma szerint.';

CREATE INDEX idx_jobs_status ON jobs (status, job_type);
CREATE INDEX idx_jobs_snapshot ON jobs (snapshot_id);
CREATE INDEX idx_jobs_site ON jobs (site_id);
CREATE INDEX idx_jobs_queued ON jobs (queued_at DESC);
CREATE INDEX idx_jobs_tenant ON jobs (tenant_id, status);

-- Dead letter queue index
CREATE INDEX idx_jobs_dlq ON jobs (job_type, queued_at)
    WHERE status = 'dead_lettered';

-- ---------------------------------------------------------------------------
-- 14. AUDIT_LOGS — PREMIS audit napló
-- ---------------------------------------------------------------------------

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Esemény
    action          VARCHAR(100) NOT NULL,      -- pl. 'snapshot.approved', 'user.login'
    resource_type   VARCHAR(50) NOT NULL,       -- pl. 'snapshot', 'site', 'user'
    resource_id     UUID,

    -- Kontextus
    old_value       JSONB,
    new_value       JSONB,
    ip_address      INET,                       -- 1 év után anonimizálva
    user_agent      TEXT,

    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE audit_logs IS 'Immutable: sem UPDATE, sem DELETE nem megengedett. Megőrzés: 5 év.';
COMMENT ON COLUMN audit_logs.ip_address IS 'GDPR: 1 év után automatikusan NULL-ra állítandó (cron job).';

CREATE INDEX idx_audit_logs_tenant ON audit_logs (tenant_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_user ON audit_logs (user_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_logs_ts ON audit_logs (occurred_at DESC);

-- ---------------------------------------------------------------------------
-- 15. UPDATED_AT TRIGGEREK — automatikus frissítés
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Minden táblára, ahol van updated_at
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_sites_updated_at BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_crawl_policies_updated_at BEFORE UPDATE ON crawl_policies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_snapshots_updated_at BEFORE UPDATE ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_skos_updated_at BEFORE UPDATE ON skos_concepts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 16. LIFECYCLE GUARD — tiltja az érvénytelen átmeneteket
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION validate_lifecycle_transition()
RETURNS TRIGGER AS $$
DECLARE
    valid_transitions JSONB := '{
        "candidate":   ["approved", "withdrawn"],
        "approved":    ["crawling", "withdrawn"],
        "crawling":    ["archived", "candidate"],
        "archived":    ["indexed", "candidate"],
        "indexed":     ["published", "archived"],
        "published":   ["deprecated", "withdrawn"],
        "deprecated":  ["published", "withdrawn"],
        "withdrawn":   []
    }'::jsonb;
    allowed TEXT[];
BEGIN
    IF OLD.lifecycle_status = NEW.lifecycle_status THEN
        RETURN NEW;  -- nincs változás, engedjük
    END IF;

    SELECT ARRAY(SELECT jsonb_array_elements_text(valid_transitions->OLD.lifecycle_status::text))
    INTO allowed;

    IF NOT (NEW.lifecycle_status::text = ANY(allowed)) THEN
        RAISE EXCEPTION 'Érvénytelen életciklus-átmenet: % → %',
            OLD.lifecycle_status, NEW.lifecycle_status;
    END IF;

    -- Naplózzuk az átmenetet
    INSERT INTO lifecycle_events (snapshot_id, from_status, to_status, reason)
    VALUES (NEW.id, OLD.lifecycle_status, NEW.lifecycle_status, NEW.lifecycle_reason);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_lifecycle_guard
    BEFORE UPDATE OF lifecycle_status ON archived_snapshots
    FOR EACH ROW EXECUTE FUNCTION validate_lifecycle_transition();

-- ---------------------------------------------------------------------------
-- 17. NÉZETEK (VIEWS) — gyakori lekérdezések egyszerűsítése
-- ---------------------------------------------------------------------------

-- Publikus kereséshez optimalizált nézet
CREATE VIEW v_published_snapshots AS
SELECT
    s.id,
    s.pid,
    s.dc_title,
    s.dc_description,
    s.ai_summary,
    s.dc_subject,
    s.municipality_id,
    m.name AS municipality_name,
    m.slug AS municipality_slug,
    s.crawl_timestamp,
    s.qc_score,
    s.search_vector,
    si.domain,
    si.display_name AS site_name,
    si.category AS site_category,
    si.priority AS site_priority,
    si.oszk_status
FROM archived_snapshots s
JOIN sites si ON si.id = s.site_id
LEFT JOIN municipalities m ON m.id = s.municipality_id
WHERE s.lifecycle_status = 'published';

COMMENT ON VIEW v_published_snapshots IS 'Csak published snapshot-ok — Next.js SSR és API /search végpont használja.';

-- Admin queue nézet
CREATE VIEW v_admin_queue AS
SELECT
    s.id,
    s.lifecycle_status,
    s.dc_title,
    s.seed_url,
    s.qc_score,
    s.created_at,
    si.domain,
    si.priority,
    si.category,
    m.name AS municipality_name,
    u.full_name AS created_by_name
FROM archived_snapshots s
JOIN sites si ON si.id = s.site_id
LEFT JOIN municipalities m ON m.id = s.municipality_id
LEFT JOIN users u ON u.id = s.created_by
WHERE s.lifecycle_status IN ('candidate', 'approved')
ORDER BY si.priority DESC, s.created_at ASC;

-- Gyűjtési státusz áttekintő
CREATE VIEW v_site_collection_status AS
SELECT
    si.id,
    si.domain,
    si.display_name,
    si.priority,
    si.category,
    si.crawl_frequency,
    si.oszk_status,
    si.is_active_collection,
    m.name AS municipality_name,
    m.slug AS municipality_slug,
    COUNT(sn.id) AS total_snapshots,
    COUNT(sn.id) FILTER (WHERE sn.lifecycle_status = 'published') AS published_count,
    MAX(sn.crawl_timestamp) AS last_crawled_at,
    si.curator_notes
FROM sites si
LEFT JOIN municipalities m ON m.id = si.municipality_id
LEFT JOIN archived_snapshots sn ON sn.site_id = si.id
GROUP BY si.id, si.domain, si.display_name, si.priority, si.category,
         si.crawl_frequency, si.oszk_status, si.is_active_collection,
         m.name, m.slug, si.curator_notes;

COMMENT ON VIEW v_site_collection_status IS 'Admin dashboard: minden site gyűjtési állapota egy helyen.';

-- ---------------------------------------------------------------------------
-- 18. ROW LEVEL SECURITY — V4 előkészítés (V3.1-ben kikapcsolva)
-- ---------------------------------------------------------------------------

-- ALTER TABLE archived_snapshots ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON archived_snapshots
--     USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
-- (V4-ben aktiválandó minden táblán)

-- ---------------------------------------------------------------------------
-- COMMIT
-- ---------------------------------------------------------------------------

COMMIT;

-- =============================================================================
-- Ellenőrzési lekérdezések (futtatás után manuálisan)
-- =============================================================================
-- \dt                                              → táblák listája
-- \d archived_snapshots                            → snapshot tábla struktúrája
-- \d page_chunks                                   → chunks + HNSW index látszik
-- SELECT * FROM pg_indexes WHERE tablename='page_chunks';
-- SELECT * FROM pg_trigger WHERE tgrelid='archived_snapshots'::regclass;
