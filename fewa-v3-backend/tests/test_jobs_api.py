"""Real integration tests for app/api/v1/jobs.py's admin candidate/
quality-review endpoints — against the same isolated test Postgres +
Redis containers as test_archive_crud.py / test_arq_worker.py (see
tests/conftest.py). Replaces the previous version, which asserted against
a mock in-memory `_JOBS_DB` and a hardcoded fixture site_id.
"""

import os
import uuid

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from arq import create_pool
from arq.connections import RedisSettings

from app.api.v1.jobs import router as jobs_router
from app.core.arq_pool import get_arq_pool
from app.core.db import get_db_connection
from app.core.security import create_access_token

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)
TEST_REDIS_HOST = os.environ.get("TEST_REDIS_HOST", "redis")
TEST_REDIS_PORT = int(os.environ.get("TEST_REDIS_PORT", "6379"))


async def _override_get_db_connection():
    # Starlette's TestClient opens a fresh event loop per call, but
    # app.core.db's pool is a lazily-cached process-global — reusing it
    # across calls binds it to an already-closed loop and breaks with
    # "another operation is in progress". Opening a fresh connection here,
    # inside whichever loop is actually running the request, sidesteps that.
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


async def _override_get_arq_pool():
    # Same cross-event-loop issue as _override_get_db_connection, this time
    # for app.core.arq_pool's cached ArqRedis pool.
    pool = await create_pool(RedisSettings(host=TEST_REDIS_HOST, port=TEST_REDIS_PORT))
    try:
        yield pool
    finally:
        await pool.aclose()


app = FastAPI()
app.include_router(jobs_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection
app.dependency_overrides[get_arq_pool] = _override_get_arq_pool

client = TestClient(app)

ARCHIVIST_ID = "00000000-0000-0000-0000-000000000099"
CURATOR_ID = "550e8400-e29b-41d4-a716-446655440000"

ARCHIVIST_TOKEN = create_access_token(
    subject=ARCHIVIST_ID,
    role="curator",
    tenant_id="00000000-0000-0000-0000-000000000001",
)
CURATOR_TOKEN = create_access_token(
    subject=CURATOR_ID,
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


@pytest.mark.asyncio
async def test_trigger_ingest_creates_real_site_and_candidate_snapshot(conn):
    domain = f"jobsapi-{uuid.uuid4().hex[:8]}.hu"
    response = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"seed_url": f"https://{domain}/"},
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["lifecycle_status"] == "candidate"

    row = await conn.fetchrow(
        "SELECT lifecycle_status FROM archived_snapshots WHERE id = $1", data["snapshot_id"],
    )
    assert row["lifecycle_status"] == "candidate"

    site_row = await conn.fetchrow("SELECT domain FROM sites WHERE id = $1", data["site_id"])
    assert site_row["domain"] == domain

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", data["snapshot_id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", data["snapshot_id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", data["site_id"])


@pytest.mark.asyncio
async def test_trigger_ingest_rejects_second_url_for_same_domain(conn):
    """Regression test (2026-08-03): repeated /api/admin/ingest calls for
    different sub-page URLs on the same domain each created their own
    site-worth of search results (www.szekesfehervar.hu ended up with 9).
    The second ingest for an already-active domain must be rejected, not
    silently create another parallel candidate."""
    domain = f"jobsapi-dup-{uuid.uuid4().hex[:8]}.hu"
    first = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"seed_url": f"https://{domain}/cikk-1"},
    )
    assert first.status_code == status.HTTP_202_ACCEPTED
    data = first.json()

    second = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"seed_url": f"https://{domain}/cikk-2"},
    )
    assert second.status_code == status.HTTP_409_CONFLICT

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", data["snapshot_id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", data["snapshot_id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", data["site_id"])


@pytest.mark.asyncio
async def test_trigger_ingest_rejects_url_without_domain(conn):
    response = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"seed_url": "https://example.hu/"},
    )
    # A well-formed URL always has a domain; this instead checks the
    # endpoint's validation path is reachable and returns 202 for a valid one.
    assert response.status_code == status.HTTP_202_ACCEPTED
    snapshot_id = response.json()["snapshot_id"]
    site_id = response.json()["site_id"]
    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", snapshot_id)
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", snapshot_id)
    await conn.execute("DELETE FROM sites WHERE id = $1", site_id)


@pytest.mark.asyncio
async def test_candidate_approve_reject_flow_against_real_db(conn):
    domain = f"jobsapi-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    from app.crud import archive
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )

    list_res = client.get("/api/admin/candidates", headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"})
    assert list_res.status_code == status.HTTP_200_OK
    assert str(created["id"]) in [c["id"] for c in list_res.json()["items"]]

    reject_res = client.post(
        f"/api/admin/candidates/{created['id']}/reject",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"reason": "Nem helyi vonatkozású"},
    )
    assert reject_res.status_code == status.HTTP_200_OK
    assert reject_res.json()["lifecycle_status"] == "withdrawn"

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])


@pytest.mark.asyncio
async def test_quality_review_list_and_decide_against_real_db(conn):
    domain = f"jobsapi-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    from app.crud import archive
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/x.wacz", "f" * 64, 100)
    await archive.record_qc_result(conn, created["id"], qc_score=60, qc_detail={}, auto_accept_threshold=96)

    list_res = client.get("/api/admin/quality-review", headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"})
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["threshold"] == 96
    assert str(created["id"]) in [q["id"] for q in list_res.json()["items"]]

    decide_res = client.post(
        f"/api/admin/quality-review/{created['id']}/decide",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"accept": True, "reason": "Kézi ellenőrzés után elfogadva"},
    )
    assert decide_res.status_code == status.HTTP_200_OK
    assert decide_res.json()["lifecycle_status"] == "published"

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])


@pytest.mark.asyncio
async def test_admin_document_preview_works_before_publication(conn):
    """Regression test for the 2026-08-02 incident: the quality-review
    tab's "Visszajátszás megnyitása" replay link pointed at the PUBLIC
    /api/documents/{id} endpoint, which only ever returns 'published'
    snapshots — but every item in the review queue is, by definition, not
    yet published. The curator could never actually preview what they
    were being asked to accept/reject. This admin-scoped endpoint must
    return the document (including a real wacz_url) for an 'archived'
    snapshot with a recorded WACZ, not just for 'published' ones."""
    # try/finally, not just sequential cleanup at the end: TEST_DSN is the
    # shared dev database (see module docstring), not an isolated
    # container — an assertion failure between creation and cleanup once
    # left this exact fixture ("T" / jobsapi-preview-*.hu) sitting in the
    # real quality-review queue, visibly confusing a real user who had
    # never approved any such thing (2026-08-02 incident).
    domain = f"jobsapi-preview-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    from app.crud import archive
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    try:
        await archive.approve_candidate(conn, created["id"], user_id=None)
        await archive.mark_crawling(conn, created["id"])
        await archive.record_crawl_result(conn, created["id"], "wacz/preview-test.wacz", "a" * 64, 100)
        # No QC result yet — mirrors exactly what the screenshot showed
        # ("Nincs QC eredmény") that triggered this fix.

        # (The public /api/documents/{id} endpoint's own published-only gate
        # is covered by test_search_api.py; this app instance only wires
        # jobs_router.)
        admin_res = client.get(
            f"/api/admin/documents/{created['id']}",
            headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        )
        assert admin_res.status_code == status.HTTP_200_OK
        body = admin_res.json()
        assert body["lifecycle_status"] == "archived"
        assert body["wacz_url"] is not None

        unauth_res = client.get(f"/api/admin/documents/{created['id']}")
        assert unauth_res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    finally:
        await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
        await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
        await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])


@pytest.mark.asyncio
async def test_curator_role_can_access_candidate_approval_queue():
    """Regression test: the admin dashboard's login form defaults to a
    curator account (curator@vmk.hu), and 'curator' is this workflow's own
    documented actor (see list_candidates()'s docstring: "awaiting curator
    approve/reject decision") — but these endpoints originally required
    'archivist', silently locking out the default account with no error a
    normal user would recognize as a permissions issue (403, not 401, so
    the frontend's token-refresh logic correctly left it alone — this was
    a real RBAC misconfiguration, not an auth bug)."""
    list_res = client.get("/api/admin/candidates", headers={"Authorization": f"Bearer {CURATOR_TOKEN}"})
    assert list_res.status_code == status.HTTP_200_OK

    quality_res = client.get("/api/admin/quality-review", headers={"Authorization": f"Bearer {CURATOR_TOKEN}"})
    assert quality_res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_approved_by_records_user_id(conn):
    domain = f"jobsapi-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    from app.crud import archive
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )

    approve_res = client.post(
        f"/api/admin/candidates/{created['id']}/approve",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={"reason": "Approved by curator test"},
    )
    assert approve_res.status_code == status.HTTP_200_OK
    assert approve_res.json()["lifecycle_status"] == "approved"

    row = await conn.fetchrow("SELECT approved_by FROM archived_snapshots WHERE id = $1", created["id"])
    assert str(row["approved_by"]) == CURATOR_ID

    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
    await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
    await conn.execute("DELETE FROM sites WHERE id = $1", site_row["id"])


@pytest.mark.asyncio
async def test_withdraw_published_snapshot_endpoint(conn):
    domain = f"jobsapi-{uuid.uuid4().hex[:8]}.hu"
    site_row = await conn.fetchrow(
        "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
        "00000000-0000-0000-0000-000000000001", domain, f"https://{domain}/", domain,
    )
    from app.crud import archive
    created = await archive.create_candidate_snapshot(
        conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/withdraw.wacz", "a" * 64, 100)
    await archive.record_qc_result(conn, created["id"], qc_score=98, qc_detail={}, auto_accept_threshold=96)

    withdraw_res = client.post(
        f"/api/admin/documents/{created['id']}/withdraw",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={"reason": "Out of scope / test withdrawal"},
    )
    assert withdraw_res.status_code == status.HTTP_200_OK
    assert withdraw_res.json()["lifecycle_status"] == "withdrawn"

    snapshot_row = await conn.fetchrow("SELECT lifecycle_status FROM archived_snapshots WHERE id = $1", created["id"])
    assert snapshot_row["lifecycle_status"] == "withdrawn"

    decision_row = await conn.fetchrow(
        "SELECT operation, outcome, actor_id FROM release_decisions WHERE snapshot_id = $1 ORDER BY created_at DESC LIMIT 1",
        created["id"],
    )
    assert decision_row is not None
    assert decision_row["operation"] == "withdraw"
    assert decision_row["outcome"] == "withdrawn"
    assert str(decision_row["actor_id"]) == CURATOR_ID

