"""Real integration tests for GET /api/search and GET /api/documents/{id} —
against the same isolated test Postgres as the other DB-backed test
modules. Replaces the previous version, which asserted against a hardcoded
array of 7 fabricated snapshot records served regardless of the database
(see task #40 — this was the public-facing fake-data finding)."""

import os
import uuid

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.search import router as search_router
from app.core.db import get_db_connection
from app.crud import archive

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)
TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def _override_get_db_connection():
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


app = FastAPI()
app.include_router(search_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)


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
async def published_snapshot(conn):
    """A real snapshot pushed all the way to 'published' via the actual
    lifecycle helpers — this is what makes it visible to public search."""
    domain = f"search-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        TENANT_ID, domain, f"https://{domain}/", domain,
    )
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/hirek/varoshaza-felujitas",
        dc_title="Székesfehérvár Városháza felújítási hírei", discovery_reason="test", discovery_metadata={},
    )
    await conn.execute(
        "UPDATE archived_snapshots SET dc_description = $2 WHERE id = $1",
        created["id"], "A Városháza műemléki épületének felújítási munkálatai folynak.",
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/search-test.wacz", "e" * 64, 500)
    result = await archive.record_qc_result(
        conn, created["id"], qc_score=99, qc_detail={}, auto_accept_threshold=96,
    )
    assert result["lifecycle_status"] == "published"

    yield {"id": str(created["id"]), "site_id": str(site_row["id"]), "domain": domain}

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])


@pytest.mark.asyncio
async def test_search_finds_real_published_snapshot_by_title_keyword(published_snapshot):
    response = client.get("/api/search?q=Városháza")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["search_type"] == "fulltext"
    ids = [r["id"] for r in data["results"]]
    assert published_snapshot["id"] in ids


@pytest.mark.asyncio
async def test_search_does_not_return_unpublished_or_unrelated_snapshots(conn):
    response = client.get(f"/api/search?q=zzz-nonexistent-{uuid.uuid4().hex}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_empty_query_returns_200_with_results(published_snapshot):
    response = client.get("/api/search")
    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.json()


@pytest.mark.asyncio
async def test_get_document_returns_real_data_including_wacz_url(published_snapshot):
    response = client.get(f"/api/documents/{published_snapshot['id']}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["dc_title"] == "Székesfehérvár Városháza felújítási hírei"
    assert data["qc_score"] == 99
    assert data["site"]["domain"] == published_snapshot["domain"]
    assert data["wacz_url"] is not None
    assert "search-test.wacz" in data["wacz_url"]


@pytest.mark.asyncio
async def test_get_document_unknown_id_returns_real_404_not_fabricated_placeholder():
    response = client.get(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_document_malformed_id_returns_404_not_500():
    response = client.get("/api/documents/not-a-valid-uuid")
    assert response.status_code == status.HTTP_404_NOT_FOUND
