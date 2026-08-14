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
    # wacz_url is now a same-origin API path keyed by snapshot id, not a
    # presigned MinIO URL containing the object key — see
    # test_wacz_url_is_same_origin_not_internal_minio_host for why.
    assert data["wacz_url"] == f"/api/wacz/{published_snapshot['id']}"


@pytest.mark.asyncio
async def test_get_document_unknown_id_returns_real_404_not_fabricated_placeholder():
    response = client.get(f"/api/documents/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_document_malformed_id_returns_404_not_500():
    response = client.get("/api/documents/not-a-valid-uuid")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_public_stats_reflects_real_counts(published_snapshot, conn):
    response = client.get("/api/stats")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data["active_sites"], int)
    assert isinstance(data["published_documents"], int)

    # The published_snapshot fixture created one real published document —
    # the count must reflect it, not a hardcoded number.
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS c FROM archived_snapshots WHERE lifecycle_status = 'published'"
    )
    assert data["published_documents"] == row["c"]


@pytest.mark.asyncio
async def test_collections_reflects_real_per_category_counts(published_snapshot, conn):
    """Regression: fewa-v3-frontend's /collections page had a hardcoded
    array of 3 categories with fabricated counts (42/18/27) - the exact
    same public-facing-fake-data bug class as the old search_service.py
    (see that module's docstring, "the highest-severity finding of this
    session"). There was no backend endpoint for it at all. published_snapshot
    creates a site with the default category ('egyéb') - the response must
    show a real count for it, not an invented number."""
    response = client.get("/api/collections")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "collections" in data

    row = await conn.fetchrow(
        "SELECT COUNT(*) AS c FROM v_published_snapshots WHERE site_category = 'egyéb'"
    )
    egyeb = next((c for c in data["collections"] if c["id"] == "egyéb"), None)
    assert egyeb is not None, f"expected an 'egyéb' category entry, got: {data['collections']}"
    assert egyeb["count"] == row["c"]


@pytest.mark.asyncio
async def test_search_filtered_by_category_returns_results(published_snapshot):
    """Regression test for the 2026-08-02 incident: /collections' "browse"
    button links to /?category=<enum id>, which calls this endpoint with
    that filter — and it returned HTTP 500 for EVERY category, making the
    entire public archive unreachable through the collections UI (the only
    navigation path to it, since the homepage is just a search form).

    Root cause: site_category is a real Postgres enum (site_category_enum),
    and ILIKE has no operator defined against an enum — Postgres raised
    "operator does not exist: site_category_enum ~~* unknown". Filtering
    must cast to text first. Uses the real 'egyéb' enum value that
    published_snapshot's site actually has."""
    response = client.get("/api/search", params={"category": "egyéb"})
    assert response.status_code == status.HTTP_200_OK, response.text

    results = response.json()["results"]
    assert published_snapshot["id"] in [r["id"] for r in results]
    assert all(r["category"] == "egyéb" for r in results)


@pytest.mark.asyncio
async def test_wacz_url_is_same_origin_not_internal_minio_host(published_snapshot):
    """Regression test for the 2026-08-02 incident: wacz_url was a presigned
    MinIO URL like http://localhost:9002/... — the exact deployment concern
    generate_presigned_wacz_url's own docstring warned about. From a user's
    browser 'localhost' is THEIR machine, so ReplayWeb.page failed with
    "TypeError: Failed to fetch"; and an http:// URL on an https:// page is
    blocked as mixed content anyway. It must be a same-origin relative path
    the API itself serves instead."""
    response = client.get(f"/api/documents/{published_snapshot['id']}")
    assert response.status_code == status.HTTP_200_OK
    wacz_url = response.json()["wacz_url"]
    assert wacz_url is not None
    assert wacz_url.startswith("/api/wacz/"), wacz_url
    assert "localhost" not in wacz_url
    assert not wacz_url.startswith("http://")


@pytest.mark.asyncio
async def test_wacz_endpoint_streams_published_object_and_supports_range(published_snapshot, conn):
    """ReplayWeb.page reads a WACZ as a remote zip: it issues HTTP Range
    requests for individual entries rather than downloading the whole
    archive. A proxy that ignores Range would make replay fail or force a
    full multi-hundred-MB download, so 206 + Content-Range is required, not
    a nice-to-have."""
    from app.core.minio_client import minio_client
    key = f"wacz/test/{published_snapshot['id']}.wacz"
    payload = b"PK\x03\x04fake-wacz-bytes-for-range-test" * 10
    import io
    minio_client.upload_wacz_stream(key, io.BytesIO(payload))
    await conn.execute(
        "UPDATE archived_snapshots SET wacz_minio_path = $2 WHERE id = $1",
        published_snapshot["id"], key,
    )

    full = client.get(f"/api/wacz/{published_snapshot['id']}")
    assert full.status_code == status.HTTP_200_OK
    assert full.content == payload

    ranged = client.get(
        f"/api/wacz/{published_snapshot['id']}", headers={"Range": "bytes=0-9"}
    )
    assert ranged.status_code == status.HTTP_206_PARTIAL_CONTENT
    assert ranged.content == payload[:10]
    assert "Content-Range" in ranged.headers


@pytest.mark.asyncio
async def test_wacz_endpoint_refuses_unpublished_snapshot_without_token(conn):
    """The public WACZ route must not become a way to read content that is
    still awaiting a publish decision."""
    domain = f"waczgate-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        TENANT_ID, domain, f"https://{domain}/", domain,
    )
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    try:
        await archive.approve_candidate(conn, created["id"], user_id=None)
        await archive.mark_crawling(conn, created["id"])
        await archive.record_crawl_result(conn, created["id"], "wacz/nope.wacz", "b" * 64, 10)

        res = client.get(f"/api/wacz/{created['id']}")
        assert res.status_code == status.HTTP_404_NOT_FOUND
    finally:
        await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
        await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
        await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])
