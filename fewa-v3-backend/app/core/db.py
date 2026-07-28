import logging
from typing import AsyncGenerator, Optional
import asyncpg
from app.core.config import settings

logger = logging.getLogger(__name__)

pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        logger.info(f"Initializing asyncpg pool to {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
        pool = await asyncpg.create_pool(
            dsn=settings.postgres_dsn,
            min_size=settings.POSTGRES_POOL_MIN_SIZE,
            max_size=settings.POSTGRES_POOL_MAX_SIZE,
        )
    return pool


async def close_db_pool() -> None:
    global pool
    if pool is not None:
        logger.info("Closing asyncpg pool")
        await pool.close()
        pool = None


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    if pool is None:
        await init_db_pool()
    assert pool is not None
    async with pool.acquire() as connection:
        yield connection


async def check_db_health() -> bool:
    """Returns True if database ping SELECT 1 succeeds."""
    try:
        if pool is None:
            conn = await asyncpg.connect(dsn=settings.postgres_dsn)
            val = await conn.fetchval("SELECT 1")
            await conn.close()
            return val == 1
        else:
            async with pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1")
                return val == 1
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
