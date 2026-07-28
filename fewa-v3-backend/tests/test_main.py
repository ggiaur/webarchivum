import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    with patch("app.main.check_db_health", new_callable=AsyncMock) as mock_db, \
         patch("app.main.check_redis_health", new_callable=AsyncMock) as mock_redis, \
         patch("app.main.minio_client") as mock_minio:

        mock_db.return_value = True
        mock_redis.return_value = {"queue": True, "cache": True}
        mock_minio.check_health.return_value = True

        response = client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "3.1.0"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["minio"] == "ok"


def test_openapi_json_schema():
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["info"]["title"] == "FEWA API — Fejér Vármegyei Webarchívum"
    assert "/api/auth/login" in data["paths"]
    assert "/api/search" in data["paths"]
    assert "/api/rag" in data["paths"]
    assert "/oai" in data["paths"]
