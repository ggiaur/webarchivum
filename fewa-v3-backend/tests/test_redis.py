import pytest
from unittest.mock import AsyncMock, patch
from app.core.redis import get_queue_redis, get_cache_redis, check_redis_health, settings


def test_redis_clients_db_isolation():
    q_client = get_queue_redis()
    c_client = get_cache_redis()

    assert q_client.connection_pool.connection_kwargs["db"] == 0
    assert c_client.connection_pool.connection_kwargs["db"] == 1
    assert q_client.connection_pool.connection_kwargs["db"] != c_client.connection_pool.connection_kwargs["db"]


@pytest.mark.asyncio
async def test_check_redis_health_mock():
    with patch("app.core.redis.get_queue_redis") as mock_q, patch("app.core.redis.get_cache_redis") as mock_c:
        mock_q_client = AsyncMock()
        mock_q_client.ping.return_value = True
        mock_q.return_value = mock_q_client

        mock_c_client = AsyncMock()
        mock_c_client.ping.return_value = True
        mock_c.return_value = mock_c_client

        health = await check_redis_health()
        assert health["queue"] is True
        assert health["cache"] is True
