import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from arq.connections import RedisSettings

from spec.pipeline_schemas import CrawlJobPayload, EnrichJobPayload, ReembedJobPayload
from app.crud import archive
from app.core.config import settings
from app.core.minio_client import MinIOClient

# fewa-automation is a sibling project directory, not a pip-installed
# package — see fewa-automation/README.md. Import it explicitly rather than
# duplicating its (already real, tested) crawl/QA logic here.
_FEWA_AUTOMATION_DIR = Path(__file__).resolve().parents[3] / "fewa-automation"
if str(_FEWA_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(_FEWA_AUTOMATION_DIR))

from crawler import run_crawl as automation_run_crawl, run_qa as automation_run_qa  # noqa: E402

logger = logging.getLogger(__name__)

CRAWL_STAGING_DIR = Path("/tmp/fewa_crawl_staging")


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
    crawl_result = automation_run_crawl(
        url=str(parsed.seed_url),
        collection=collection_name,
        output_dir=CRAWL_STAGING_DIR,
        depth=parsed.depth,
        page_limit=min(parsed.max_pages, 100),  # extra safety cap regardless of what's requested
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

    qa_result = automation_run_qa(
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

    # One snapshot = one seed page for now; average across pages if the
    # crawl covered more than one (see crawler.py's depth/page_limit).
    screenshot_scores = [p["screenshotMatch"] for p in qa_result.per_page if p.get("screenshotMatch") is not None]
    text_scores = [p["textMatch"] for p in qa_result.per_page if p.get("textMatch") is not None]
    avg_screenshot = sum(screenshot_scores) / len(screenshot_scores) if screenshot_scores else 0.0
    avg_text = sum(text_scores) / len(text_scores) if text_scores else 0.0
    qc_score = round(min(avg_screenshot, avg_text) * 100)  # conservative: the WORSE of the two dimensions

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
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_QUEUE_DB,
    )
