# Skill: Acceptance Testing

## Alapelv
Minden fázis csak akkor zárható le, ha az acceptance tesztek PASS-t adnak.
Az AI agent futtatja a teszteket — és addig nem lép tovább, amíg nem PASS.

---

## Tesztstruktúra

```
backend/tests/
├── unit/           ← izolált egységek, mock-ok
├── contract/       ← API contract tesztek az openapi.yaml alapján
├── integration/    ← komponensek együtt, test DB
└── acceptance/     ← fázis-szintű kapuk
```

---

## Fázis acceptance tesztek példák

### Fázis 1 — Schema integritás

```python
# tests/acceptance/test_phase1_schema.py
import pytest
from sqlalchemy import inspect, text

def test_page_chunks_embedding_column(db_engine):
    inspector = inspect(db_engine)
    columns = {c["name"]: c for c in inspector.get_columns("page_chunks")}
    assert "embedding" in columns
    assert "vector" in str(columns["embedding"]["type"]).lower()

def test_hnsw_index_exists(db_engine):
    with db_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'page_chunks'
            AND indexdef LIKE '%hnsw%'
        """)).fetchone()
    assert result is not None, "HNSW index hiányzik a page_chunks táblán"

def test_redis_queue_cache_isolation(redis_queue, redis_cache):
    redis_queue.set("isolation_test_key", "value")
    assert redis_cache.get("isolation_test_key") is None, \
        "Redis queue és cache nem izolált (db=0 vs db=1)"
```

### Fázis 2 — Auth acceptance

```python
# tests/acceptance/test_phase2_auth.py
def test_viewer_cannot_access_admin_queue(client, viewer_token):
    response = client.get(
        "/api/admin/queue",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert response.status_code == 403

def test_admin_can_access_admin_queue(client, admin_token):
    response = client.get(
        "/api/admin/queue",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

def test_public_search_no_auth_required(client):
    response = client.get("/api/search?q=teszt")
    assert response.status_code == 200
```

---

## Futtatási szabályok

```bash
# Egy fázis lezárása előtt MINDIG ezt futtatod:
pytest tests/acceptance/test_phase[N]_*.py -v --tb=short

# Ha bármi FAIL → nem lépsz tovább
# Ha mind PASS → frissíted a STATUS.md-t és lezárod a fázist
```

---

## Tiltott megoldások

- ❌ `pytest.mark.skip` — nem skippolsz tesztet hogy átmenjen
- ❌ `assert True` — nem mock-olsz el éles acceptance kritériumot
- ❌ Hardcoded user ID a tesztekben
- ❌ Éles adatbázis a tesztekben (mindig test DB, `pytest-asyncio` + fixtures)
