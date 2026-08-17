import asyncio
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from arq import cron
from arq.connections import RedisSettings

from spec.pipeline_schemas import CrawlJobPayload, EnrichJobPayload, ReembedJobPayload
from app.crud import archive
from app.core.config import settings
from app.core.minio_client import MinIOClient

# fewa-automation is a sibling project directory, not a pip-installed
# package — see fewa-automation/README.md. Import it explicitly rather than
# duplicating its (already real, tested) crawl/QA logic here.
_FEWA_AUTOMATION_DIR = Path(__file__).resolve().parents[3] / "fewa-automation"
if not _FEWA_AUTOMATION_DIR.exists():
    _FEWA_AUTOMATION_DIR = Path(__file__).resolve().parents[2] / "fewa-automation"
if str(_FEWA_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_FEWA_AUTOMATION_DIR))

from crawler import run_crawl as automation_run_crawl, run_qa as automation_run_qa  # noqa: E402

logger = logging.getLogger(__name__)

CRAWL_STAGING_DIR = Path("/tmp/fewa_crawl_staging")

# Reconciler thresholds — see reconcile_stalled_snapshots below.
RECONCILE_STALE_APPROVED_MINUTES = 10
RECONCILE_STALE_CRAWLING_MINUTES = 60
RECONCILE_LOCK_TTL_SECONDS = 1800

# Each crawl/QA run is a real headless-Chromium Browsertrix container — running
# too many at once starves them all of CPU. First cut was limit=2 (down from
# an unbounded 5, which had pushed load average to 5.84 and failed a crawl
# outright). But at limit=2, both concurrent crawls still hit their
# --timeLimit at nearly the same instant and BOTH died (returncode 15)
# during the graceful WACZ-finalize step instead of exiting cleanly — CPU
# contention during that step is worse than during the crawl itself.
# Dropped to 1 (fully serial) until finalize-step contention is understood
# better; revisit raising this once that's root-caused.
CRAWL_CONCURRENCY_LIMIT = 1
_crawl_semaphore = asyncio.Semaphore(CRAWL_CONCURRENCY_LIMIT)


async def run_crawl_job(ctx: Dict[str, Any], payload: dict) -> dict:
    """
    Real crawl execution: fewa-automation's Browsertrix wrapper (scope-
    limited, cookie-autoclick, screenshot-capturing — see
    fewa-automation/crawler.py) produces a real WACZ, which is uploaded to
    MinIO and recorded in Postgres via app/crud/archive.py. No simulation.
    """
    parsed = CrawlJobPayload(**payload)
    start_time = time.time()
    snapshot_id = str(parsed.snapshot_id)
    logger.info(f"Starting CrawlJob {parsed.job_id} for snapshot {snapshot_id} ({parsed.seed_url})")

    db_pool = ctx["db_pool"]
    minio_client: MinIOClient = ctx["minio_client"]

    async with db_pool.acquire() as conn:
        await archive.mark_crawling(conn, snapshot_id)

    collection_name = f"snapshot_{snapshot_id.replace('-', '')}"
    # automation_run_crawl calls subprocess.run(), which blocks — running it
    # directly here would freeze the ENTIRE worker event loop (all other
    # jobs, including the reconcile_stalled_snapshots cron) for the whole
    # crawl duration, serializing every job onto one at a time regardless
    # of arq's configured concurrency. to_thread moves the block off the
    # loop so other jobs keep running while this one crawls.
    loop = asyncio.get_running_loop()

    def progress_cb(pages: int, depth: int):
        async def _update():
            async with db_pool.acquire() as conn:
                await archive.update_crawl_progress(conn, snapshot_id, pages, depth)
        asyncio.run_coroutine_threadsafe(_update(), loop)

    async with _crawl_semaphore:
        crawl_result = await asyncio.to_thread(
            automation_run_crawl,
            url=str(parsed.seed_url),
            collection=collection_name,
            output_dir=CRAWL_STAGING_DIR,
            depth=parsed.depth,
            page_limit=min(parsed.max_pages, 100),  # extra safety cap regardless of what's requested
            progress_callback=progress_cb,
        )

    if not crawl_result.success or crawl_result.wacz_path is None:
        error_msg = f"Crawl failed (returncode={crawl_result.returncode}): {crawl_result.stderr_tail}"
        logger.error(f"CrawlJob {parsed.job_id} failed: {error_msg}")
        return {
            "job_id": str(parsed.job_id),
            "status": "failed",
            "snapshot_id": snapshot_id,
            "error": error_msg,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    minio_key = f"wacz/{time.strftime('%Y/%m')}/{snapshot_id}.wacz"
    with open(crawl_result.wacz_path, "rb") as f:
        upload_info = minio_client.upload_wacz_stream(minio_key, f)

    async with db_pool.acquire() as conn:
        await archive.record_crawl_result(
            conn, snapshot_id,
            wacz_minio_path=minio_key,
            wacz_sha256=upload_info.get("sha256"),
            wacz_filesize_bytes=upload_info.get("size"),
        )

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"CrawlJob {parsed.job_id} completed in {duration_ms}ms -> {minio_key}")

    # A seed page that itself returned an HTTP error must never reach the
    # normal QA-comparison path. Incident 2026-08-02: szgyf.gov.hu's seed
    # URL returned a real, consistent 404 (confirmed across 4 separate
    # crawls, recorded by Browsertrix itself in pages.jsonl). The crawl
    # still produced a complete, valid WACZ — of the 404 page — and
    # Browsertrix's QA then re-crawled the SAME dead URL live, found it
    # still 404s, and reported 96% similarity: both sides are the same
    # "not found" page. That auto-published a 404 screen as real content.
    # No similarity score can tell "faithfully archived a working page"
    # apart from "faithfully archived the same broken page live still
    # serves" — only the underlying HTTP status can. Going straight to
    # qc_score=0 (skipping run_enrich_job) means no comparison ever runs
    # that could paper over the real problem.
    if crawl_result.seed_http_status is not None and crawl_result.seed_http_status >= 400:
        reason = (
            f"A kiinduló URL HTTP {crawl_result.seed_http_status} választ adott a bejáráskor "
            "— az archívum valószínűleg egy hibaoldalt tartalmaz, nem a valódi tartalmat."
        )
        logger.warning(f"CrawlJob {parsed.job_id}: seed URL returned HTTP {crawl_result.seed_http_status}, forcing human review")
        async with db_pool.acquire() as conn:
            await archive.record_qc_result(
                conn, snapshot_id,
                qc_score=0,
                qc_detail={"reason": "seed_http_error", "http_status": crawl_result.seed_http_status, "note": reason},
                auto_accept_threshold=settings.QUALITY_AUTO_ACCEPT_THRESHOLD,
            )
        return {
            "job_id": str(parsed.job_id),
            "status": "completed",
            "snapshot_id": snapshot_id,
            "wacz_minio_path": minio_key,
            "local_wacz_path": str(crawl_result.wacz_path),
            "duration_ms": duration_ms,
            "seed_http_status": crawl_result.seed_http_status,
        }

    # Chain straight into QC — a fresh crawl always needs quality assessment
    # before it can leave 'archived'. ctx["redis"] is the same ArqRedis pool
    # the worker itself is connected through (arq sets this automatically).
    enrich_job_id = str(uuid.uuid4())
    await ctx["redis"].enqueue_job(
        "run_enrich_job",
        {
            "job_id": enrich_job_id,
            "snapshot_id": snapshot_id,
            "wacz_minio_path": minio_key,
        },
        _job_id=enrich_job_id,
    )

    return {
        "job_id": str(parsed.job_id),
        "status": "completed",
        "snapshot_id": snapshot_id,
        "wacz_minio_path": minio_key,
        "local_wacz_path": str(crawl_result.wacz_path),
        "duration_ms": duration_ms,
    }


async def run_enrich_job(ctx: Dict[str, Any], payload: dict) -> dict:
    """
    Real quality assessment: Browsertrix's OFFICIAL QA mode (re-crawls live,
    compares against the WACZ replay — see fewa-automation/crawler.py::run_qa(),
    live-verified 2026-07-31: real screenshotMatch/textMatch scores, not a
    fixed number). Records the result via app/crud/archive.py, which
    auto-accepts (archived -> indexed) at/above QUALITY_AUTO_ACCEPT_THRESHOLD
    or leaves it in the human quality-review queue below it.
    """
    parsed = EnrichJobPayload(**payload)
    start_time = time.time()
    snapshot_id = str(parsed.snapshot_id)
    logger.info(f"Starting EnrichJob {parsed.job_id} for snapshot {snapshot_id}")

    db_pool = ctx["db_pool"]

    # wacz_minio_path is a MinIO key, not a local path — QA needs a local
    # file. Download it fresh from MinIO rather than assuming the crawl
    # staging dir still has it (enrich can run independently/later).
    minio_client: MinIOClient = ctx["minio_client"]
    local_wacz_path = CRAWL_STAGING_DIR / f"{snapshot_id}_for_qa.wacz"
    local_wacz_path.parent.mkdir(parents=True, exist_ok=True)
    minio_client.client.download_file(
        Bucket=minio_client.bucket_wacz, Key=parsed.wacz_minio_path, Filename=str(local_wacz_path),
    )

    # Same blocking-subprocess and concurrency-cap concerns as run_crawl_job.
    async with _crawl_semaphore:
        qa_result = await asyncio.to_thread(
            automation_run_qa,
            wacz_path=local_wacz_path,
            collection=f"qa_{snapshot_id.replace('-', '')}",
            output_dir=CRAWL_STAGING_DIR / "qa_output",
        )

    if not qa_result.success or not qa_result.per_page:
        error_msg = f"QA run failed or produced no comparison data (returncode={qa_result.returncode})"
        logger.error(f"EnrichJob {parsed.job_id}: {error_msg}")
        return {
            "job_id": str(parsed.job_id),
            "status": "failed",
            "snapshot_id": snapshot_id,
            "error": error_msg,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    screenshot_scores = [p["screenshotMatch"] for p in qa_result.per_page if p.get("screenshotMatch") is not None]
    text_scores = [p["textMatch"] for p in qa_result.per_page if p.get("textMatch") is not None]
    avg_screenshot = sum(screenshot_scores) / len(screenshot_scores) if screenshot_scores else 0.0
    avg_text = sum(text_scores) / len(text_scores) if text_scores else 0.0
    qc_score = round(min(avg_screenshot, avg_text) * 100)  # conservative: the WORSE of the two dimensions

    # Task 8 — Hard lower threshold: if any single page's screenshotMatch or textMatch < 60%,
    # force mandatory human quality review regardless of high batch average score.
    min_single_page = 1.0
    for p in qa_result.per_page:
        if p.get("screenshotMatch") is not None:
            min_single_page = min(min_single_page, p["screenshotMatch"])
        if p.get("textMatch") is not None:
            min_single_page = min(min_single_page, p["textMatch"])

    if min_single_page < 0.60 and qc_score >= settings.QUALITY_AUTO_ACCEPT_THRESHOLD:
        logger.warning(
            f"EnrichJob {parsed.job_id}: Single page score ({round(min_single_page * 100)}%) < 60%. "
            "Forcing human quality review."
        )
        qc_score = min(qc_score, settings.QUALITY_AUTO_ACCEPT_THRESHOLD - 1)

    async with db_pool.acquire() as conn:
        db_result = await archive.record_qc_result(
            conn, snapshot_id,
            qc_score=qc_score,
            qc_detail={"pages": qa_result.per_page, "avg_screenshotMatch": avg_screenshot, "avg_textMatch": avg_text},
            auto_accept_threshold=settings.QUALITY_AUTO_ACCEPT_THRESHOLD,
        )

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"EnrichJob {parsed.job_id} completed: qc_score={qc_score} "
        f"-> lifecycle_status={db_result['lifecycle_status']} ({duration_ms}ms)"
    )

    return {
        "job_id": str(parsed.job_id),
        "status": "completed",
        "snapshot_id": snapshot_id,
        "qc_score": qc_score,
        "lifecycle_status": db_result["lifecycle_status"],
        "duration_ms": duration_ms,
    }


async def run_reembed_job(ctx: Dict[str, Any], payload: dict) -> dict:
    """
    Arq worker task executing batch re-embedding.

    NOT YET WIRED to real embeddings — app/pipeline/embedding.py's
    generate_mock_embedding() is still a hash-based fake (separate, tracked
    gap; out of scope for the crawl/QC approval workflow this session
    focused on). This function is left as-is rather than silently
    pretending it's real.
    """
    parsed = ReembedJobPayload(**payload)
    logger.info(f"Starting ReembedJob {parsed.job_id} to model {parsed.target_embedding_model}-{parsed.target_embedding_version}")

    result = {
        "job_id": str(parsed.job_id),
        "status": "completed",
        "processed_chunks": 100,
    }

    return result


async def reconcile_stalled_snapshots(ctx: Dict[str, Any]) -> None:
    """Self-healing sweep, run on a cron schedule (see WorkerSettings below).

    Incident 2026-08-02: 6 approved candidates had their run_crawl_job jobs
    enqueued correctly, but the arq worker wasn't running continuously —
    the jobs sat in Redis until they expired and were silently dropped.
    Nothing surfaced this; the snapshots just stayed 'approved' forever.
    This catches that case (and the mirror case of a crawl job crashing
    mid-run, stuck in 'crawling') without anyone having to notice.
    """
    db_pool = ctx["db_pool"]
    redis = ctx["redis"]

    async with db_pool.acquire() as conn:
        stale_approved = await archive.list_stale_approved(conn, RECONCILE_STALE_APPROVED_MINUTES)
        stale_crawling = await archive.list_stale_crawling(conn, RECONCILE_STALE_CRAWLING_MINUTES)

    for row in stale_crawling:
        snapshot_id = str(row["id"])
        try:
            async with db_pool.acquire() as conn:
                await archive.revert_stalled_crawl(
                    conn, snapshot_id,
                    reason=f"Reconciler: stuck in 'crawling' for over {RECONCILE_STALE_CRAWLING_MINUTES} "
                           "minutes — reverted to 'candidate' for re-approval rather than retried blindly.",
                )
            logger.warning(f"Reconciler: reverted stalled crawl {snapshot_id} back to 'candidate'")
        except ValueError:
            continue  # already moved on (e.g. its own job finished) between the query and here

    for row in stale_approved:
        snapshot_id = str(row["id"])
        lock_key = f"reconcile:crawl:{snapshot_id}"
        acquired = await redis.set(lock_key, "1", nx=True, ex=RECONCILE_LOCK_TTL_SECONDS)
        if not acquired:
            continue  # a previous tick already re-enqueued this one recently

        job_id = str(uuid.uuid4())
        await redis.enqueue_job(
            "run_crawl_job",
            {
                "job_id": job_id,
                "site_id": str(row["site_id"]),
                "snapshot_id": snapshot_id,
                "seed_url": row["seed_url"],
                "depth": 2,
                "max_pages": 20,
            },
            _job_id=job_id,
        )
        logger.warning(f"Reconciler: re-enqueued crawl job {job_id} for stalled approved snapshot {snapshot_id}")


async def startup(ctx: Dict[str, Any]) -> None:
    import asyncpg
    ctx["db_pool"] = await asyncpg.create_pool(
        dsn=settings.postgres_dsn,
        min_size=settings.POSTGRES_POOL_MIN_SIZE,
        max_size=settings.POSTGRES_POOL_MAX_SIZE,
    )
    ctx["minio_client"] = MinIOClient()


async def shutdown(ctx: Dict[str, Any]) -> None:
    db_pool = ctx.get("db_pool")
    if db_pool is not None:
        await db_pool.close()


class WorkerSettings:
    functions = [run_crawl_job, run_enrich_job, run_reembed_job]
    cron_jobs = [cron(reconcile_stalled_snapshots, minute=set(range(0, 60, 10)))]
    on_startup = startup
    on_shutdown = shutdown
    # arq's default (300s) is shorter than a job can legitimately wait for a
    # _crawl_semaphore slot once concurrency is capped (CRAWL_CONCURRENCY_LIMIT)
    # while more jobs than that are queued — arq was cancelling jobs via its
    # own wait_for timeout before they ever got a turn to run (observed
    # 2026-08-02, right after adding the concurrency cap). Generous enough for
    # a job to queue behind a full round of max-length crawls and still run.
    job_timeout = 3600
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_QUEUE_DB,
    )
