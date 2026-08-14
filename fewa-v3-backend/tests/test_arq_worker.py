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

import asyncio
import os
import time
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
async def test_run_crawl_job_seed_http_error_skips_qa_and_forces_review(db_pool, approved_snapshot, monkeypatch, tmp_path):
    """Regression test for the 2026-08-02 incident: szgyf.gov.hu's seed URL
    returned a genuine, consistent HTTP 404 (confirmed on 4 separate real
    crawls, recorded by Browsertrix itself in pages.jsonl). The crawl still
    "succeeded" — a complete, valid WACZ of the 404 page — and Browsertrix's
    QA re-crawled the SAME dead URL live, found it still 404s, and reported
    96% similarity: both sides are the same "not found" page. That
    auto-published a 404 screen as real archived content.

    A seed page with an error HTTP status must never reach the normal
    QA-comparison path at all — no comparison score can distinguish "we
    faithfully archived a working page" from "we faithfully archived the
    same broken page the live site still serves." It must go straight to
    qc_score=0 with a reason a curator can act on, skipping run_enrich_job
    entirely so no misleading comparison ever runs."""
    fake_wacz = tmp_path / "fake_404.wacz"
    fake_wacz.write_bytes(b"fake wacz bytes for a 404 page")

    monkeypatch.setattr(
        arq_worker, "automation_run_crawl",
        lambda **kwargs: _FakeCrawlResult(True, fake_wacz, 0, "", seed_http_status=404),
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

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT lifecycle_status, qc_score, qc_detail, wacz_sha256 FROM archived_snapshots WHERE id = $1",
            approved_snapshot["snapshot_id"],
        )
    # The WACZ itself is still kept — it's real evidence of what happened —
    # but the snapshot must be gated for human review, never auto-published.
    assert row["wacz_sha256"] == "a" * 64
    assert row["lifecycle_status"] == "archived"
    assert row["qc_score"] == 0
    assert "404" in row["qc_detail"]

    # No QA job — a similarity comparison against the same dead URL would
    # have been the exact mechanism that caused the original incident.
    ctx["redis"].enqueue_job.assert_not_called()


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


@pytest.mark.asyncio
async def test_crawl_concurrency_is_capped(db_pool, monkeypatch, tmp_path):
    """More crawl jobs than CRAWL_CONCURRENCY_LIMIT must not run their
    blocking crawl step at the same time — see arq_worker._crawl_semaphore.
    Regression test for 2026-08-02: 5 concurrent Browsertrix crawls on an
    8-core box pushed load average to 5.84 and one crawl failed twice."""
    n = arq_worker.CRAWL_CONCURRENCY_LIMIT + 2
    snapshots = []
    async with db_pool.acquire() as conn:
        for _ in range(n):
            domain = f"conc-test-{uuid.uuid4().hex[:8]}.hu"
            site_row = await conn.fetchrow(
                "INSERT INTO sites (tenant_id, domain, base_url, display_name) VALUES ($1, $2, $3, $4) RETURNING id",
                TENANT_ID, domain, f"https://{domain}/", domain,
            )
            created = await archive.create_candidate_snapshot(
                conn, site_id=str(site_row["id"]), seed_url=f"https://{domain}/",
                dc_title="T", discovery_reason="test", discovery_metadata={},
            )
            await archive.approve_candidate(conn, created["id"], user_id=None)
            snapshots.append({
                "site_id": str(site_row["id"]),
                "snapshot_id": str(created["id"]),
                "seed_url": f"https://{domain}/",
            })

    fake_wacz = tmp_path / "fake.wacz"
    fake_wacz.write_bytes(b"fake wacz bytes for test")

    current = 0
    peak = 0

    def slow_crawl(**kwargs):
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        time.sleep(0.15)
        current -= 1
        return _FakeCrawlResult(True, fake_wacz, 0, "")

    monkeypatch.setattr(arq_worker, "automation_run_crawl", slow_crawl)

    try:
        await asyncio.gather(*[
            arq_worker.run_crawl_job(_mock_ctx(db_pool), {
                "job_id": str(uuid.uuid4()),
                "site_id": s["site_id"],
                "snapshot_id": s["snapshot_id"],
                "seed_url": s["seed_url"],
                "depth": 1,
                "max_pages": 5,
            })
            for s in snapshots
        ])

        assert peak <= arq_worker.CRAWL_CONCURRENCY_LIMIT
        assert peak == arq_worker.CRAWL_CONCURRENCY_LIMIT  # actually exercised the cap, not trivially under it
    finally:
        async with db_pool.acquire() as conn:
            for s in snapshots:
                await conn.execute("DELETE FROM lifecycle_events WHERE snapshot_id = $1", s["snapshot_id"])
                await conn.execute("DELETE FROM archived_snapshots WHERE id = $1", s["snapshot_id"])
                await conn.execute("DELETE FROM sites WHERE id = $1", s["site_id"])


@pytest.mark.asyncio
async def test_reconcile_requeues_stale_approved_snapshot(db_pool, approved_snapshot, monkeypatch):
    """Regression test for the 2026-08-02 incident: an approved candidate
    whose crawl job silently expired in Redis (worker outage) must be
    picked back up by the reconciler, not stay stuck in 'approved' forever."""
    monkeypatch.setattr(arq_worker, "RECONCILE_STALE_APPROVED_MINUTES", 0)
    ctx = _mock_ctx(db_pool)
    ctx["redis"].set = AsyncMock(return_value=True)  # lock acquired

    await arq_worker.reconcile_stalled_snapshots(ctx)

    # TEST_DSN is the shared dev database (not an isolated container), so
    # other genuinely-stale 'approved' rows may legitimately match too —
    # assert membership, not exact call count.
    enqueued_snapshot_ids = {c.args[1]["snapshot_id"] for c in ctx["redis"].enqueue_job.call_args_list}
    assert approved_snapshot["snapshot_id"] in enqueued_snapshot_ids
    matching_call = next(
        c for c in ctx["redis"].enqueue_job.call_args_list
        if c.args[1]["snapshot_id"] == approved_snapshot["snapshot_id"]
    )
    assert matching_call.args[0] == "run_crawl_job"
    assert matching_call.args[1]["seed_url"] == approved_snapshot["seed_url"]


@pytest.mark.asyncio
async def test_reconcile_skips_snapshot_already_locked_by_another_run(db_pool, approved_snapshot, monkeypatch):
    """Two reconciler ticks (or a tick racing the original enqueue) must not
    double-enqueue a crawl for the same snapshot — the Redis NX lock is what
    prevents that."""
    monkeypatch.setattr(arq_worker, "RECONCILE_STALE_APPROVED_MINUTES", 0)
    ctx = _mock_ctx(db_pool)
    ctx["redis"].set = AsyncMock(return_value=False)  # lock already held

    await arq_worker.reconcile_stalled_snapshots(ctx)

    ctx["redis"].enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_reverts_stale_crawling_snapshot_to_candidate(db_pool, approved_snapshot, monkeypatch):
    """A crawl job that crashed mid-run (not a clean run_crawl_job failure
    return) leaves the snapshot in 'crawling' forever unless the reconciler
    notices and sends it back for re-approval.

    TEST_DSN is the shared dev database, not an isolated container (see
    module docstring) — a threshold=0 minutes query would match and REVERT
    every real 'crawling' snapshot currently in flight, not just this
    fixture's row (this happened for real once: see incident notes for
    2026-08-02 13:13, four real in-progress crawls were wiped by an earlier
    version of this test). list_stale_crawling itself is patched to return
    only this fixture's row so the reconciler's revert/lock logic is still
    exercised for real, without scanning/mutating unrelated live data.
    """
    async with db_pool.acquire() as conn:
        await archive.mark_crawling(conn, approved_snapshot["snapshot_id"])

    monkeypatch.setattr(arq_worker, "RECONCILE_STALE_APPROVED_MINUTES", 999_999)
    monkeypatch.setattr(
        archive, "list_stale_crawling",
        AsyncMock(return_value=[{
            "id": approved_snapshot["snapshot_id"],
            "site_id": approved_snapshot["site_id"],
            "seed_url": approved_snapshot["seed_url"],
        }]),
    )
    ctx = _mock_ctx(db_pool)
    ctx["redis"].set = AsyncMock(return_value=True)

    await arq_worker.reconcile_stalled_snapshots(ctx)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT lifecycle_status FROM archived_snapshots WHERE id = $1",
            approved_snapshot["snapshot_id"],
        )
    assert row["lifecycle_status"] == "candidate"
    ctx["redis"].enqueue_job.assert_not_called()


class _FakeCrawlResult:
    def __init__(self, success, wacz_path, returncode, stderr_tail, seed_http_status=None):
        self.success = success
        self.wacz_path = wacz_path
        self.returncode = returncode
        self.stderr_tail = stderr_tail
        self.seed_http_status = seed_http_status


class _FakeQAResult:
    def __init__(self, success, per_page, returncode=0, stderr_tail=""):
        self.success = success
        self.per_page = per_page
        self.returncode = returncode
        self.stderr_tail = stderr_tail
