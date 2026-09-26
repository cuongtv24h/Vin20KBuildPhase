"""Quản lý kết nối / session factory (lazy import để giữ CI nhẹ)."""


def get_engine():
    """Async engine cho `settings.database_url`.

    TODO(TechLead): bật khi implement — cần `sqlalchemy[asyncio]`, `asyncpg`;
    checkpoint LangGraph (AsyncPostgresSaver, Spike 2) dùng chung pool này.
    """
    raise NotImplementedError("C-02: bật sqlalchemy async engine theo TD-4.1")
