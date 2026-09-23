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

    # Database & Vector Store (pgvector)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pricepolicy_db"
    pg_table_name: str = "policy_clauses"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    hybrid_search_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
