"""Real integration tests for app/crud/archive.py — against an actual
Postgres instance (isolated container, real schema.sql loaded), not mocks.
This module's entire point is "the DB-enforced lifecycle state machine
actually works as designed" — that can only be proven against a real DB.

Requires: an isolated Postgres with spec/schema.sql + migrations loaded.
Set TEST_DATABASE_URL to override the default local test container DSN.
"""

import json
import os
import uuid

import asyncpg
import pytest

from app.crud import archive

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)

TENANT_ID = "00000000-0000-0000-0000-000000000001"


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
async def site_id(conn):
    """A real site row — archived_snapshots.site_id is NOT NULL FK."""
    domain = f"test-{uuid.uuid4().hex[:8]}.hu"
    row = await conn.fetchrow(
        """
        INSERT INTO sites (tenant_id, domain, base_url, display_name)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        TENANT_ID, domain, f"https://{domain}/", domain,
    )
    site_id_value = str(row["id"])
    yield site_id_value
    # Cleanup: cascades to archived_snapshots (site_id ON DELETE RESTRICT —
    # actually RESTRICT, so we must delete snapshots first).
    await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id IN (SELECT id FROM archived_snapshots WHERE site_id = $1)", site_id_value)
    await conn.execute("DELETE FROM archived_snapshots WHERE site_id = $1", site_id_value)
    await conn.execute("DELETE FROM sites WHERE id = $1", site_id_value)


@pytest.mark.asyncio
async def test_create_candidate_snapshot_starts_in_candidate_status(conn, site_id):
    result = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="Test Candidate", discovery_reason="matched: Székesfehérvár",
        discovery_metadata={"matched_terms": ["Székesfehérvár"]},
    )
    assert result["lifecycle_status"] == "candidate"

    events = await conn.fetch(
        "SELECT * FROM lifecycle_events WHERE snapshot_id = $1", result["id"]
    )
    assert len(events) == 1
    assert events[0]["to_status"] == "candidate"
    assert json.loads(events[0]["metadata"])["matched_terms"] == ["Székesfehérvár"]


@pytest.mark.asyncio
async def test_approve_candidate_transitions_to_approved(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    result = await archive.approve_candidate(conn, created["id"], user_id=None)
    assert result["lifecycle_status"] == "approved"


@pytest.mark.asyncio
async def test_approve_candidate_fails_if_not_in_candidate_status(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)

    with pytest.raises(ValueError):
        await archive.approve_candidate(conn, created["id"], user_id=None)


@pytest.mark.asyncio
async def test_reject_candidate_transitions_to_withdrawn(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    result = await archive.reject_candidate(conn, created["id"], reason="Not locally relevant")
    assert result["lifecycle_status"] == "withdrawn"


@pytest.mark.asyncio
async def test_full_lifecycle_happy_path_to_crawling_and_archived(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    crawling = await archive.mark_crawling(conn, created["id"])
    assert crawling["lifecycle_status"] == "crawling"

    archived = await archive.record_crawl_result(
        conn, created["id"], wacz_minio_path="wacz/2026/07/test.wacz",
        wacz_sha256="a" * 64, wacz_filesize_bytes=1000,
    )
    assert archived["lifecycle_status"] == "archived"


@pytest.mark.asyncio
async def test_qc_result_above_threshold_auto_accepts(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(
        conn, created["id"], "wacz/x.wacz", "b" * 64, 500,
    )

    result = await archive.record_qc_result(
        conn, created["id"], qc_score=98,
        qc_detail={"screenshotMatch": 0.99, "textMatch": 0.97},
        auto_accept_threshold=96,
    )
    assert result["lifecycle_status"] == "published"


@pytest.mark.asyncio
async def test_qc_result_below_threshold_stays_archived_for_human_review(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/x.wacz", "c" * 64, 500)

    result = await archive.record_qc_result(
        conn, created["id"], qc_score=70,
        qc_detail={"screenshotMatch": 0.70, "textMatch": 0.65},
        auto_accept_threshold=96,
    )
    assert result["lifecycle_status"] == "archived"  # NOT auto-indexed

    queue = await archive.list_quality_review_queue(conn, threshold=96)
    queue_ids = [str(q["id"]) for q in queue]
    assert str(created["id"]) in queue_ids


@pytest.mark.asyncio
async def test_decide_quality_review_accept_moves_to_published(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/x.wacz", "d" * 64, 500)
    await archive.record_qc_result(
        conn, created["id"], qc_score=80, qc_detail={}, auto_accept_threshold=96,
    )

    result = await archive.decide_quality_review(
        conn, created["id"], accept=True, user_id=None, reason="Manually reviewed, acceptable",
    )
    assert result["lifecycle_status"] == "published"


@pytest.mark.asyncio
async def test_decide_quality_review_reject_sends_back_to_candidate(conn, site_id):
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    await archive.approve_candidate(conn, created["id"], user_id=None)
    await archive.mark_crawling(conn, created["id"])
    await archive.record_crawl_result(conn, created["id"], "wacz/x.wacz", "e" * 64, 500)
    await archive.record_qc_result(
        conn, created["id"], qc_score=40, qc_detail={}, auto_accept_threshold=96,
    )

    result = await archive.decide_quality_review(
        conn, created["id"], accept=False, user_id=None, reason="Too degraded, retry later",
    )
    assert result["lifecycle_status"] == "candidate"


@pytest.mark.asyncio
async def test_db_rejects_invalid_lifecycle_transition_directly(conn, site_id):
    """The DB's own trg_lifecycle_guard must reject illegal transitions even
    if application code tried to bypass the crud helpers entirely."""
    created = await archive.create_candidate_snapshot(
        conn, site_id=site_id, seed_url="https://example.hu/",
        dc_title="T", discovery_reason="r", discovery_metadata={},
    )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "UPDATE archived_snapshots SET lifecycle_status = 'published' WHERE id = $1",
            created["id"],
        )  # candidate -> published is not a valid direct transition
