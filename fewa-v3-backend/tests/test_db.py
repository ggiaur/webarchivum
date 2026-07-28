import pytest
from unittest.mock import AsyncMock, patch
from app.core.db import check_db_health, settings


@pytest.mark.asyncio
async def test_db_health_check_mock_success():
    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1
        mock_connect.return_value = mock_conn

        is_healthy = await check_db_health()
        assert is_healthy is True
        mock_conn.fetchval.assert_called_once_with("SELECT 1")


@pytest.mark.asyncio
async def test_db_health_check_mock_failure():
    with patch("asyncpg.connect", side_effect=Exception("Connection refused")):
        is_healthy = await check_db_health()
        assert is_healthy is False
