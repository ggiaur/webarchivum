"""Real integration tests for the admin sites CRUD API — against the same
isolated test Postgres as the other DB-backed test modules. Replaces the
previous version, which asserted against a pure in-memory dict (a single
hardcoded "alba.hu" fixture reset on every process restart)."""

import os
import uuid

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.sites import router as sites_router
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
app.include_router(sites_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)

ARCHIVIST_TOKEN = create_access_token(
    subject="archivist-user",
    role="archivist",
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
async def real_site(conn):
    domain = f"sitesapi-{uuid.uuid4().hex[:8]}.hu"
    row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    yield {"id": str(row["id"]), "domain": domain}
    await conn.execute("DELETE FROM crawl_policies WHERE site_id = $1", row["id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", row["id"])


def test_list_sites_requires_curator_role():
    # Sites CRUD requires curator+ — the admin dashboard's own login form
    # defaults to a curator account, and "Kurátori Portál" (curator portal)
    # is this whole admin area's own framing, so curator must be able to
    # actually use it. (Previously required archivist, which silently
    # locked out the default account — a real RBAC bug caught via live use.)
    res_curator = client.get(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
    )
    assert res_curator.status_code == status.HTTP_200_OK
    assert "items" in res_curator.json()

    # A viewer (below curator) still must not have access.
    viewer_token = create_access_token(
        subject="viewer-user", role="viewer", tenant_id="00000000-0000-0000-0000-000000000001",
    )
    res_viewer = client.get(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_viewer.status_code == status.HTTP_403_FORBIDDEN

    # Archivist (higher than curator) should also succeed.
    res_archivist = client.get(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert res_archivist.status_code == status.HTTP_200_OK
    assert "items" in res_archivist.json()


@pytest.mark.asyncio
async def test_create_and_get_site_success(conn):
    domain = f"fejer-{uuid.uuid4().hex[:8]}.hu"
    payload = {
        "domain": domain,
        "base_url": f"https://{domain}",
        "display_name": "Fejér Vármegyei Önkormányzat",
        "priority": "critical",
        "category": "kozintézmény",
        "crawl_frequency": "daily",
        "curator_notes": "Napi mentés kiemelten fontos",
        "oszk_status": "yes",
    }
    response = client.post(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json=payload,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    site_id = data["id"]
    assert data["domain"] == domain
    assert data["priority"] == "critical"
    assert len(data["crawl_policies"]) == 1
    assert data["crawl_policies"][0]["is_default"] is True

    # Get site detail
    get_res = client.get(
        f"/api/admin/sites/{site_id}",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["domain"] == domain

    await conn.execute("DELETE FROM crawl_policies WHERE site_id = $1", site_id)
    await conn.execute("DELETE FROM sites WHERE id = $1", site_id)


@pytest.mark.asyncio
async def test_create_duplicate_domain_returns_409(real_site):
    payload = {
        "domain": real_site["domain"],
        "base_url": f"https://{real_site['domain']}",
    }
    response = client.post(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json=payload,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_update_site_success(real_site):
    patch_res = client.patch(
        f"/api/admin/sites/{real_site['id']}",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"priority": "critical", "curator_notes": "Módosított megjegyzés"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    updated = patch_res.json()
    assert updated["priority"] == "critical"
    assert updated["curator_notes"] == "Módosított megjegyzés"


def test_get_unknown_site_returns_404():
    response = client.get(
        f"/api/admin/sites/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_malformed_site_id_returns_404_not_500():
    response = client.get(
        "/api/admin/sites/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
