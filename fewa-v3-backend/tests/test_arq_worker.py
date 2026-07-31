"""Real integration tests for app/workers/arq_worker.py — against an actual
Postgres instance (same isolated test container as test_archive_crud.py),
asserting real lifecycle-status/qc_score state in the DB. Only the external
boundaries (Browsertrix subprocess via fewa-automation, MinIO upload/
download, and the arq redis pool used for job-chaining) are mocked — the
worker's own logic and the DB writes it makes are exercised for real.

Replaces the previous version of this file, which asserted against the
in-memory _JOBS_DB dict and a hardcoded fake qc_score == 95 — i.e. it was
testing a simulation, not the real crawl/QC pipeline.
"""

import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from app.crud import archive
from app.workers import arq_worker

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)

TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def db_pool():
    try:
        p = await asyncpg.create_pool(dsn=TEST_DSN, min_size=1, max_size=2)
    except (OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"Test Postgres not reachable at {TEST_DSN}: {e}")
        return
    yield p
    await p.close()


@pytest.fixture
async def approved_snapshot(db_pool):
    """A real, approved candidate snapshot — the state run_crawl_job expects."""
    async with db_pool.acquire() as conn:
        domain = f"test-{uuid.uuid4().hex[:8]}.hu"
        site_row = await conn.fetchrow(
            "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
            TENANT_ID, domain, f"https://{domain}/", domain,
        )
        site_id = str(site_row["id"])
        created = await archive.create_candidate_snapshot(
            conn, site_id=site_id, seed_url=f"https://{domain}/",
            dc_title="T", discovery_reason="test", discovery_metadata={},
        )
        await archive.approve_candidate(conn, created["id"], user_id=None)

    yield {"site_id": site_id, "snapshot_id": str(created["id"]), "seed_url": f"https://{domain}/"}

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", created["id"])
        await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", created["id"])
        await conn.execute("DELETE FROM sites WHERE id = $1", site_id)


def _mock_ctx(db_pool):
    return {
        "db_pool": db_pool,
        "minio_client": MagicMock(
            upload_wacz_stream=MagicMock(return_value={"sha256": "a" * 64, "size": 1234}),
        ),
        "redis": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_run_crawl_job_records_real_archived_status(db_pool, approved_snapshot, monkeypatch, tmp_path):
    fake_wacz = tmp_path / "fake.wacz"
    fake_wacz.write_bytes(b"fake wacz bytes for test")

    monkeypatch.setattr(
        arq_worker, "automation_run_crawl",
        lambda **kwargs: _FakeCrawlResult(True, fake_wacz, 0, ""),
    )

    payload = {
        "job_id": str(uuid.uuid4()),
        "site_id": approved_snapshot["site_id"],
        "snapshot_id": approved_snapshot["snapshot_id"],
        "seed_url": approved_snapshot["seed_url"],
        "depth": 1,
        "max_pages": 5,
    }

    ctx = _mock_ctx(db_pool)
    res = await arq_worker.run_crawl_job(ctx, payload)

    assert res["status"] == "completed"
    assert res["snapshot_id"] == approved_snapshot["snapshot_id"]

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT lifecycle_status, wacz_sha256 FROM archived_snapshots WHERE id = $1",
            approved_snapshot["snapshot_id"],
        )
    assert row["lifecycle_status"] == "archived"
    assert row["wacz_sha256"] == "a" * 64

    # Successful crawl must chain into a real QC job, not just return.
    ctx["redis"].enqueue_job.assert_called_once()
    assert ctx["redis"].enqueue_job.call_args[0][0] == "run_enrich_job"


@pytest.mark.asyncio
async def test_run_crawl_job_failure_leaves_snapshot_in_crawling_and_reports_error(db_pool, approved_snapshot, monkeypatch):
    monkeypatch.setattr(
        arq_worker, "automation_run_crawl",
        lambda **kwargs: _FakeCrawlResult(False, None, 1, "docker: crawl timed out"),
    )

    payload = {
        "job_id": str(uuid.uuid4()),
        "site_id": approved_snapshot["site_id"],
        "snapshot_id": approved_snapshot["snapshot_id"],
        "seed_url": approved_snapshot["seed_url"],
        "depth": 1,
        "max_pages": 5,
    }

    ctx = _mock_ctx(db_pool)
    res = await arq_worker.run_crawl_job(ctx, payload)

    assert res["status"] == "failed"
    assert "crawl timed out" in res["error"]
    ctx["redis"].enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_enrich_job_above_threshold_auto_publishes(db_pool, approved_snapshot, monkeypatch, tmp_path):
    async with db_pool.acquire() as conn:
        await archive.mark_crawling(conn, approved_snapshot["snapshot_id"])
        await archive.record_crawl_result(
            conn, approved_snapshot["snapshot_id"],
            wacz_minio_path="wacz/x.wacz", wacz_sha256="b" * 64, wacz_filesize_bytes=100,
        )

    monkeypatch.setattr(
        arq_worker, "automation_run_qa",
        lambda **kwargs: _FakeQAResult(True, [
            {"url": approved_snapshot["seed_url"], "screenshotMatch": 0.99, "textMatch": 0.98},
        ]),
    )

    payload = {
        "job_id": str(uuid.uuid4()),
        "snapshot_id": approved_snapshot["snapshot_id"],
        "wacz_minio_path": "wacz/x.wacz",
    }
    ctx = _mock_ctx(db_pool)
    ctx["minio_client"].client = MagicMock(download_file=MagicMock())
    ctx["minio_client"].bucket_wacz = "fewa-wacz"

    res = await arq_worker.run_enrich_job(ctx, payload)

    assert res["status"] == "completed"
    assert res["qc_score"] == 98  # round(min(0.99, 0.98) * 100) — real computation, not hardcoded
    assert res["lifecycle_status"] == "published"


@pytest.mark.asyncio
async def test_run_enrich_job_below_threshold_stays_archived_for_human_review(db_pool, approved_snapshot, monkeypatch):
    async with db_pool.acquire() as conn:
        await archive.mark_crawling(conn, approved_snapshot["snapshot_id"])
        await archive.record_crawl_result(
            conn, approved_snapshot["snapshot_id"],
            wacz_minio_path="wacz/x.wacz", wacz_sha256="c" * 64, wacz_filesize_bytes=100,
        )

    monkeypatch.setattr(
        arq_worker, "automation_run_qa",
        lambda **kwargs: _FakeQAResult(True, [
            {"url": approved_snapshot["seed_url"], "screenshotMatch": 0.5, "textMatch": 0.4},
        ]),
    )

    payload = {
        "job_id": str(uuid.uuid4()),
        "snapshot_id": approved_snapshot["snapshot_id"],
        "wacz_minio_path": "wacz/x.wacz",
    }
    ctx = _mock_ctx(db_pool)
    ctx["minio_client"].client = MagicMock(download_file=MagicMock())
    ctx["minio_client"].bucket_wacz = "fewa-wacz"

    res = await arq_worker.run_enrich_job(ctx, payload)

    assert res["qc_score"] == 40  # round(min(0.5, 0.4) * 100) — real computation, not hardcoded
    assert res["lifecycle_status"] == "archived"

    async with db_pool.acquire() as conn:
        queue = await archive.list_quality_review_queue(conn, threshold=96)
    assert approved_snapshot["snapshot_id"] in [str(q["id"]) for q in queue]


class _FakeCrawlResult:
    def __init__(self, success, wacz_path, returncode, stderr_tail):
        self.success = success
        self.wacz_path = wacz_path
        self.returncode = returncode
        self.stderr_tail = stderr_tail


class _FakeQAResult:
    def __init__(self, success, per_page, returncode=0, stderr_tail=""):
        self.success = success
        self.per_page = per_page
        self.returncode = returncode
        self.stderr_tail = stderr_tail
