"""E2E integration test: Auth -> Ingest (real site+snapshot in Postgres) ->
Candidate queue -> Search -> RAG -> OAI-PMH. The ingest step now creates a
real site row and an approved archived_snapshots row (see
app/api/v1/jobs.py::trigger_ingest) instead of referencing an in-memory
fixture site — this test was previously asserting against that mock and a
`/api/admin/jobs` list endpoint that no longer exists (replaced by the real
candidate/quality-review admin API, see app/crud/archive.py).
"""

import os
import uuid

import asyncpg
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from arq import create_pool
from arq.connections import RedisSettings

from app.main import app
from app.core.arq_pool import get_arq_pool
from app.core.db import get_db_connection
from app.core.security import create_access_token

client = TestClient(app)

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)
TEST_REDIS_PORT = int(os.environ.get("TEST_REDIS_PORT", "6380"))


async def _override_get_db_connection():
    # See tests/test_jobs_api.py for why: TestClient opens a fresh event
    # loop per call, which breaks app.core.db's lazily-cached global pool.
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


async def _override_get_arq_pool():
    pool = await create_pool(RedisSettings(host="localhost", port=TEST_REDIS_PORT))
    try:
        yield pool
    finally:
        await pool.aclose()


@pytest.mark.asyncio
async def test_full_e2e_archival_pipeline_flow():
    """
    E2E Integration Test: Auth -> Municipalities -> Ingest -> Candidate queue
    -> Search -> RAG -> OAI-PMH
    """
    try:
        conn = await asyncpg.connect(dsn=TEST_DSN)
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres not reachable at {TEST_DSN}: {e}")
        return

    snapshot_id = None
    site_id = None
    app.dependency_overrides[get_db_connection] = _override_get_db_connection
    app.dependency_overrides[get_arq_pool] = _override_get_arq_pool
    try:
        # Step 1: Login & Token
        auth_token = create_access_token(
            subject="archivist-e2e",
            role="archivist",
            tenant_id="00000000-0000-0000-0000-000000000001",
        )
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Step 2: Fetch Municipalities
        muni_res = client.get("/api/municipalities")
        assert muni_res.status_code == status.HTTP_200_OK
        municipalities = muni_res.json()
        assert len(municipalities) >= 1

        # Step 3: Trigger Ingest — creates a real site + approved snapshot
        domain = f"e2e-{uuid.uuid4().hex[:8]}.hu"
        ingest_res = client.post("/api/admin/ingest", headers=headers, json={"seed_url": f"https://{domain}/"})
        assert ingest_res.status_code == status.HTTP_202_ACCEPTED
        job_data = ingest_res.json()
        assert job_data["lifecycle_status"] == "approved"
        snapshot_id = job_data["snapshot_id"]
        site_id = job_data["site_id"]

        # Step 4: Verify real DB state — approved, not in the candidate queue
        # anymore (ingest auto-approves on submission).
        row = await conn.fetchrow(
            "SELECT lifecycle_status FROM archived_snapshots WHERE id = $1", snapshot_id,
        )
        assert row["lifecycle_status"] == "approved"

        candidates_res = client.get("/api/admin/candidates", headers=headers)
        assert candidates_res.status_code == status.HTTP_200_OK
        assert snapshot_id not in [c["id"] for c in candidates_res.json()["items"]]

        # Step 5: Hybrid Search — this e2e test only pushes its own snapshot
        # to 'approved' (no worker runs the crawl/QC queue here), so it
        # isn't publicly searchable yet; that specific search-relevance
        # behavior is covered for real in tests/test_search_api.py. Here we
        # only confirm the real, DB-backed endpoint responds correctly.
        search_res = client.get("/api/search?q=nincs-ilyen-teszt-kifejezes")
        assert search_res.status_code == status.HTTP_200_OK
        assert search_res.json()["total"] == 0

        # Step 6: RAG AI Assistant
        rag_res = client.post("/api/rag", json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"})
        assert rag_res.status_code == status.HTTP_200_OK
        rag_data = rag_res.json()
        assert rag_data["is_sufficient"] is True
        trace_id = rag_data["trace_id"]

        # Step 7: RAG Feedback
        fb_res = client.post("/api/rag/feedback", json={"trace_id": trace_id, "feedback": "helpful"})
        assert fb_res.status_code == status.HTTP_204_NO_CONTENT

        # Step 8: OAI-PMH Provider Export
        oai_res = client.get("/oai?verb=Identify")
        assert oai_res.status_code == status.HTTP_200_OK
        assert "<repositoryName>" in oai_res.text
    finally:
        if snapshot_id is not None:
            await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", snapshot_id)
            await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", snapshot_id)
        if site_id is not None:
            await conn.execute("DELETE FROM sites WHERE id = $1", site_id)
        await conn.close()
        app.dependency_overrides.pop(get_db_connection, None)
        app.dependency_overrides.pop(get_arq_pool, None)
