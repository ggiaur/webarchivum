# Skill: Spec-First fejlesztés

## Alapelv
Soha nem implementálsz specifikálatlan interfészt.
A sorrend kötelező és nem felcserélhető.

---

## Kötelező sorrend

```
1. Domain Model (bounded contextek, események)
        ↓
2. Adatbázis séma — teljes DDL, minden constraint, minden trigger
        ↓
3. OpenAPI YAML — API contract előre megírva
        ↓
4. Pydantic sémák — pipeline I/O típusok minden lépésre
        ↓
5. Atomikus feladatok — acceptance tesztekkel
        ↓
6. Implementáció — a tesztek zöldjéig
        ↓
7. Acceptance tesztek futtatása — csak PASS esetén tovább
```

---

## Az adatbázis séma kötelező tartalma (`spec/schema.sql`)

```sql
-- Minden táblának:
-- 1. Teljes DDL (CREATE TABLE)
-- 2. Minden foreign key és constraint expliciten
-- 3. Minden index (beleértve partial és covering indexeket)
-- 4. Minden trigger definíciója (pl. search_vector frissítő)
-- 5. Komment minden nem-triviális mezőn

-- Példa:
CREATE TABLE page_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(768),  -- nomic-embed-text-v1.5
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT page_chunks_unique_chunk UNIQUE (snapshot_id, chunk_index)
);

CREATE INDEX ON page_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## Az OpenAPI YAML kötelező tartalma (`spec/openapi.yaml`)

Minden endpoint-nak:
- Pontos request paraméterek (type, format, minLength, maxLength, enum)
- Pontos response sémák ($ref-ekkel)
- Minden lehetséges HTTP status code
- Security requirements (melyik role kell)

```yaml
/api/search:
  get:
    parameters:
      - name: q
        in: query
        required: true
        schema:
          type: string
          minLength: 2
          maxLength: 500
      - name: search_type
        in: query
        schema:
          type: string
          enum: ["fulltext", "vector", "hybrid"]
          default: "hybrid"
    responses:
      200:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SearchResponse'
      422:
        $ref: '#/components/responses/ValidationError'
```

---

## Pydantic pipeline sémák (`spec/pipeline_schemas.py`)

Minden AI pipeline lépésnek explicit I/O típusa van:

```python
from pydantic import BaseModel
from typing import Literal
from uuid import UUID

class NERInput(BaseModel):
    text: str
    snapshot_id: UUID
    language: Literal["hu", "en"] = "hu"

class NEROutput(BaseModel):
    persons: list[str]
    organizations: list[str]
    locations: list[str]
    processing_time_ms: int
    model_version: str
```

---

## Atomikus feladatok formátuma

```markdown
## Feladat [fázis.lépés]: [Feladat neve]

**Előfeltétel**: [előző lépés] ✅ tesztekkel átment

**Input**: [konkrét fájl vagy interfész]

**Output**:
- [fájl] — [mit tartalmaz]
- [tesztfájl] — [mit fed le]

**Acceptance kritériumok**:
- `pytest [tesztfájl]` — 0 failure
- [konkrét HTTP státusz + payload elvárt eredmény]

**Tiltott megoldások**:
- [mit NEM szabad csinálni]
```
