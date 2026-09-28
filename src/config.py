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
    checkpoint_db_uri: str | None = None
    use_postgres_checkpointer: bool = False

    # Vector Store & Local Embeddings
    chroma_persist_dir: str = "./data/chroma"
    pg_table_name: str = "policy_atoms"
    embedding_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    reranker_model_id: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_enabled: bool = True
    reranker_top_k: int = 5
    hybrid_search_enabled: bool = True
    coarse_top_k: int = 30

    # Pricing Sidecar (Component C-06)
    pricing_sidecar_socket: str = "./data/pricing.sock"
    pricing_sidecar_host: str = "127.0.0.1"
    pricing_sidecar_port: int = 8001
    pricing_use_mock: bool = False
    pricing_fallback_to_direct: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
