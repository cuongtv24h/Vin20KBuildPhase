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

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # LangGraph persistent checkpointing (INV-RT-04 — Spike 2)
    # CHECKPOINT_DB_URI: DSN psycopg (postgresql://) cho AsyncPostgresSaver.
    # Trống => CheckpointManager chỉ có MemorySaver (test/dev offline).
    checkpoint_db_uri: str | None = None
    # USE_POSTGRES_CHECKPOINTER: opt-in tường minh — khi false (mặc định)
    # app chạy MemorySaver ngay cả khi CHECKPOINT_DB_URI đã cấu hình.
    use_postgres_checkpointer: bool = False

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
