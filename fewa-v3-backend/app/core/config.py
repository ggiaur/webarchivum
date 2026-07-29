import os
from typing import Literal, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = Field(
        default="development-secret-key-change-this-in-production-32-chars-min",
        min_length=32,
        description="JWT HMAC/RSA fallback secret key. Must be at least 32 characters.",
    )
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    # PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "fewa_admin"
    POSTGRES_PASSWORD: str = "fewa_password"
    POSTGRES_DB: str = "fewa_v3"
    POSTGRES_POOL_MIN_SIZE: int = Field(default=5, ge=1)
    POSTGRES_POOL_MAX_SIZE: int = Field(default=20, ge=5)

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_QUEUE_DB: int = 0
    REDIS_CACHE_DB: int = 1

    # MinIO S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_WACZ: str = "fewa-wacz"
    MINIO_SECURE: bool = False

    # Ollama LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen2.5:7b"

    @property
    def postgres_dsn(self) -> str:
        """Constructs postgresql DSN string for asyncpg."""
        user_pass = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        return f"postgresql://{user_pass}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key_in_production(cls, v: str, info) -> str:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production" and "change-this" in v.lower():
            raise ValueError("SECRET_KEY must be properly configured in production environment.")
        return v


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
