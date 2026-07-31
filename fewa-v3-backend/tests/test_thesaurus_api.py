"""Real integration tests for the SKOS thesaurus API — against the same
isolated test Postgres as the other DB-backed test modules. Replaces the
previous version, which asserted against a pure in-memory dict (two
hardcoded fixture concepts, reset on every process restart)."""

import os
import uuid

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.thesaurus import router as thesaurus_router
from app.core.db import get_db_connection
from app.core.security import create_access_token

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
app.include_router(thesaurus_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)

VIEWER_TOKEN = create_access_token(
    subject="viewer-user",
    role="viewer",
    tenant_id="00000000-0000-0000-0000-000000000001",
)
CURATOR_TOKEN = create_access_token(
    subject="curator-user",
    role="curator",
    tenant_id="00000000-0000-0000-0000-000000000001",
)


@pytest.fixture
async def conn():
    try:
        connection = await asyncpg.connect(dsn=TEST_DSN)
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres not reachable at {TEST_DSN}: {e}")
        return
    yield connection
    await connection.close()


@pytest.fixture
async def real_concept(conn):
    label = f"helyi politika {uuid.uuid4().hex[:8]}"
    row = await conn.fetchrow(
        "INSERT INTO skos_concepts (tenant_id, uri, pref_label_hu) VALUES ($1, $2, $3) RETURNING id",
        "00000000-0000-0000-0000-000000000001", f"http://fewa.vmk.hu/thesaurus/{uuid.uuid4().hex}", label,
    )
    yield {"id": str(row["id"]), "label": label}
    await conn.execute("DELETE FROM skos_concepts WHERE id = $1", row["id"])


def test_list_thesaurus_requires_viewer_role():
    # Unauthenticated request fails
    res_anon = client.get("/api/thesaurus")
    assert res_anon.status_code == status.HTTP_401_UNAUTHORIZED

    # Viewer succeeds
    res_viewer = client.get(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
    )
    assert res_viewer.status_code == status.HTTP_200_OK
    assert "items" in res_viewer.json()


@pytest.mark.asyncio
async def test_search_thesaurus_query(real_concept):
    response = client.get(
        f"/api/thesaurus?q={real_concept['label']}",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
    )
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) >= 1
    assert real_concept["label"].lower() in items[0]["pref_label_hu"].lower()


@pytest.mark.asyncio
async def test_create_and_patch_thesaurus_concept(conn):
    label = f"környezetvédelem-{uuid.uuid4().hex[:8]}"

    # Viewer cannot create concept (requires curator+)
    create_fail = client.post(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
        json={"pref_label_hu": label},
    )
    assert create_fail.status_code == status.HTTP_403_FORBIDDEN

    # Curator creates concept
    create_res = client.post(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={
            "pref_label_hu": label,
            "alt_labels": ["ökológia", "zöld ügyek"],
            "definition": "Fejér vármegyei környezetvédelmi témák",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    concept = create_res.json()
    concept_id = concept["id"]
    assert concept["pref_label_hu"] == label

    # Curator patches concept
    patch_res = client.patch(
        f"/api/thesaurus/{concept_id}",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={"notation": "KO-001"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["notation"] == "KO-001"

    await conn.execute("DELETE FROM skos_concepts WHERE id = $1", concept_id)


def test_patch_unknown_concept_returns_404():
    response = client.patch(
        f"/api/thesaurus/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={"notation": "X"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
