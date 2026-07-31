"""Real integration tests for GET /api/municipalities — against the same
isolated test Postgres as the other DB-backed test modules, seeded via
spec/migrations/003_seed_fejer_municipalities.sql. Replaces the previous
version, which asserted against a hardcoded in-memory list with fabricated
non-UUID ids that was never backed by the DB at all."""

import os

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.municipalities import router as municipalities_router
from app.core.db import get_db_connection

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)


async def _override_get_db_connection():
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


app = FastAPI()
app.include_router(municipalities_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)


def test_list_active_municipalities():
    response = client.get("/api/municipalities")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) > 0
    # Ensure inactive ones are omitted by default
    slugs = [m["slug"] for m in data]
    assert "szekesfehervar" in slugs
    assert "szabadbattyan" not in slugs

    # Ensure correct sort order
    sort_orders = [m["sort_order"] for m in data]
    assert sort_orders == sorted(sort_orders)


def test_list_all_municipalities_include_inactive():
    response = client.get("/api/municipalities?include_inactive=true")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    slugs = [m["slug"] for m in data]
    assert "szabadbattyan" in slugs
