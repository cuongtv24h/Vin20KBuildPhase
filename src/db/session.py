"""
Asynchronous database engine and session factory for PostgreSQL 16 / SQLite.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

settings = get_settings()

# Hỗ trợ PostgreSQL (asyncpg) hoặc SQLite (aiosqlite)
db_url = settings.database_url
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite+aiosqlite:///"):
    # Chuyển đổi sang driver async nếu là sqlite
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg:///")

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Lớp cơ sở ORM DeclarativeBase cho tất cả các thực thể database."""
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cung cấp async database session trong FastAPI request lifecycle."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Khởi tạo toàn bộ schema cơ sở dữ liệu (drop & create all)."""
    from src.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

