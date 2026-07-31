"""Real arq (Redis-backed job queue) connection pool for enqueueing jobs
that app/workers/arq_worker.py's WorkerSettings actually picks up and runs
(run_crawl_job, run_enrich_job) — not a simulated/in-process call.
"""

from typing import Optional

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import settings

_arq_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(
            RedisSettings(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                database=settings.REDIS_QUEUE_DB,
            )
        )
    return _arq_pool


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None
