import logging
from typing import Optional
from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

queue_redis_client: Optional[Redis] = None
cache_redis_client: Optional[Redis] = None


def get_queue_redis() -> Redis:
    """Returns async Redis client for queue (db=0)."""
    global queue_redis_client
    if queue_redis_client is None:
        queue_redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_QUEUE_DB,
            decode_responses=True,
        )
    return queue_redis_client


def get_cache_redis() -> Redis:
    """Returns async Redis client for AI cache (db=1)."""
    global cache_redis_client
    if cache_redis_client is None:
        cache_redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_CACHE_DB,
            decode_responses=True,
        )
    return cache_redis_client


async def close_redis_clients() -> None:
    global queue_redis_client, cache_redis_client
    if queue_redis_client is not None:
        await queue_redis_client.close()
        queue_redis_client = None
    if cache_redis_client is not None:
        await cache_redis_client.close()
        cache_redis_client = None


async def check_redis_health() -> dict[str, bool]:
    """Checks connection health for both Queue (db=0) and Cache (db=1)."""
    res = {"queue": False, "cache": False}
    try:
        q_client = get_queue_redis()
        res["queue"] = await q_client.ping()
    except Exception as e:
        logger.warning(f"Redis Queue health check failed: {e}")

    try:
        c_client = get_cache_redis()
        res["cache"] = await c_client.ping()
    except Exception as e:
        logger.warning(f"Redis Cache health check failed: {e}")

    return res
