"""
Asynchronous database engine and session factory for PostgreSQL 16 / SQLite.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings
from src.db.dns_patch import apply_dns_patch

settings = get_settings()

# Fallback DNS cho Supabase pooler (mạng trường học/công ty chặn phân giải CNAME AWS). Bật có điều kiện:
# `DB_DNS_FALLBACK=false` để tắt hẳn, và patch cũng tự bỏ qua nếu DATABASE_URL không trỏ tới Supabase —
# vì nó đổi `socket.getaddrinfo` của toàn tiến trình.
if settings.db_dns_fallback:
    apply_dns_patch(settings.database_url)

# Hỗ trợ PostgreSQL (asyncpg) hoặc SQLite (aiosqlite)
db_url = settings.database_url
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite+aiosqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
elif db_url.startswith("postgres://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://")

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_recycle=300,
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


# Alias for backward compatibility
get_db = get_db_session


async def init_db() -> None:
    """Khởi tạo toàn bộ schema cơ sở dữ liệu (drop & create all)."""
    from src.db.models import Base as ModelsBase

    async with engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all)
