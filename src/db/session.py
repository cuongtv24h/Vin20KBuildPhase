"""Database Session and Connection Management."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def get_clean_database_url(url: str | None = None) -> str:
    """Ensure database URL has proper async driver and encoded credentials."""
    raw_url = url or settings.database_url
    if not raw_url.startswith("postgresql+asyncpg://"):
        if raw_url.startswith("postgresql://"):
            raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)

    # Parse and encode password if it contains unencoded special characters
    try:
        parsed = urlparse(raw_url)
        if parsed.password and "?" in parsed.password and "%3F" not in parsed.password:
            encoded_password = quote_plus(parsed.password)
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            raw_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception as e:
        logger.warning("Failed to normalize database URL: %s", e)

    return raw_url


DATABASE_URL = get_clean_database_url()

# Create SQLAlchemy Async Engine
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    echo=False,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
