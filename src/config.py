from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Primary LLM
    openai_api_key: str = ""
    openai_base_url: str | None = None
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=1, ge=0, le=10)

    # Fallback LLM 1
    fallback_openai_api_key: str | None = None
    fallback_openai_base_url: str | None = None
    fallback_model_name: str | None = None

    # Fallback LLM 2
    fallback2_openai_api_key: str | None = None
    fallback2_openai_base_url: str | None = None
    fallback2_model_name: str | None = None

    # Database — Supabase PostgreSQL 16 (TD-4.2)
    # Dev có thể để mặc định sqlite; production bắt buộc postgresql+asyncpg://
    database_url: str = "sqlite:///./data/app.db"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_anon_key: str | None = None

    # pgvector / Embeddings (C-02: time-travel semantic search)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)

    # Outbox Worker — Redis/ARQ (PDF + SSE dispatch, src/worker/)
    redis_url: str | None = None

    # Pricing Sidecar (C-06: Math Engine qua Unix Domain Socket)
    pricing_sidecar_socket: str = "./data/pricing.sock"

    # Ký số & HITL (C-05: KMS Ed25519 — private key chỉ nằm ở KMS)
    signing_kms_url: str | None = None
    signing_key_id: str | None = None

    # Object storage — PDF báo giá & snapshots (Supabase Storage hoặc S3)
    supabase_storage_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # Pre-Sales (C-09: TTL phiên chat công khai — Spike 5)
    pre_sales_session_ttl_minutes: int = Field(default=60, ge=1, le=1440)


@lru_cache
def get_settings() -> Settings:
    return Settings()
