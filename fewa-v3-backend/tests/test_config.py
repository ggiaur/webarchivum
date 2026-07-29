import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings


def test_settings_default_values(monkeypatch):
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("MINIO_BUCKET_WACZ", raising=False)
    settings = get_settings()
    assert settings.ENVIRONMENT in ["development", "staging", "production", "testing"]
    assert settings.POSTGRES_PORT == 5432
    assert settings.REDIS_QUEUE_DB == 0
    assert settings.REDIS_CACHE_DB == 1
    assert settings.MINIO_BUCKET_WACZ == "fewa-wacz"


def test_postgres_dsn_property():
    settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_SERVER="db.example.com",
        POSTGRES_PORT=5432,
        POSTGRES_DB="test_db",
    )
    assert settings.postgres_dsn == "postgresql://test_user:test_password@db.example.com:5432/test_db"


def test_short_secret_key_fails():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="short")


def test_production_secret_key_validation():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="change-this-in-production-super-secret-key-32-chars-min",
        )
