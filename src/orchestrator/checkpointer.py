"""
LangGraph Checkpoint Manager (Spike 2)
Owner: TechLead (cuongtv_02560)
Supports:
- AsyncPostgresSaver for persistent production checkpointing in PostgreSQL 16
- MemorySaver for lightweight in-memory testing/mocking
- Namespace and Thread Isolation (PRE_SALES vs DEFAULT)
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

try:
    from psycopg_pool import AsyncConnectionPool
except ImportError:
    AsyncConnectionPool = None  # type: ignore[assignment, misc]

# Registry chia sẻ: mọi CheckpointManager trỏ cùng db_uri dùng chung một pool.
# Tránh việc mỗi graph/runner tự mở pool riêng làm cạn connection Supabase.
_shared_managers: dict[str, CheckpointManager] = {}

# Checkpointer ứng dụng (persistent) được lifespan cấu hình một lần khi start.
# Các runner/graph mức module lấy qua get_app_checkpointer() để dùng chung pool.
_app_checkpointer: BaseCheckpointSaver | None = None


def configure_app_checkpointer(saver: BaseCheckpointSaver) -> None:
    """Lifespan gọi một lần khi start để publish checkpointer persistent cho toàn app."""
    global _app_checkpointer
    _app_checkpointer = saver


def get_app_checkpointer() -> BaseCheckpointSaver | None:
    """Trả checkpointer persistent nếu đã bật, ngược lại None (runner tự fallback MemorySaver)."""
    return _app_checkpointer


class CheckpointManager:
    """
    Manages LangGraph checkpointers, connection pools, and thread configuration isolation.
    """

    def __init__(self, db_uri: str | None = None, max_pool_size: int = 20) -> None:
        self.db_uri = db_uri
        self.max_pool_size = max_pool_size
        self._pool: AsyncConnectionPool | None = None
        self._saver: BaseCheckpointSaver | None = None
        self._memory_saver: MemorySaver = MemorySaver()
        # Các saver Postgres được sinh ra từ pool này — phải đóng trước pool
        # để AsyncPostgresSaver không văng lỗi khi pool đã đóng.
        self._savers: list[BaseCheckpointSaver] = []
        self._owns_shared_pool: bool = False

    async def initialize(self) -> None:
        """Initialize PostgreSQL connection pool if db_uri is configured."""
        if self.db_uri and self.db_uri.startswith("postgres"):
            # psycopg async KHÔNG chạy được trên ProactorEventLoop (mặc định Windows).
            # Launcher run.py đặt WindowsSelectorEventLoopPolicy trước khi tạo loop.
            if sys.platform == "win32" and type(asyncio.get_running_loop()).__name__ == "ProactorEventLoop":
                raise RuntimeError(
                    "psycopg async can SelectorEventLoop tren Windows. "
                    "Chay app bang 'py -3 run.py' (tu dat event loop policy), "
                    "hoac asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)."
                )
            shared = _shared_managers.get(self.db_uri)
            if shared is not None and shared is not self:
                # Đã có manager khác giữ pool cho cùng URI: dùng lại pool + saver của nó.
                self._pool = shared._pool
                self._saver = shared._saver
                return
            self._owns_shared_pool = True
            if self._pool is not None:
                return  # idempotent
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            self._pool = AsyncConnectionPool(
                conninfo=self.db_uri,
                max_size=self.max_pool_size,
                open=False,
                # autocommit=True BẮT BUỘC: setup() của AsyncPostgresSaver chạy
                # CREATE INDEX CONCURRENTLY — không được phép trong transaction block.
                kwargs={"autocommit": True},
            )
            await self._pool.open()
            # Pattern chính thức LangGraph: truyền POOL (không phải connection đã checkout)
            # — saver tự checkout connection cho từng thao tác.
            saver = AsyncPostgresSaver(self._pool)
            await saver.setup()
            self._saver = saver
            _shared_managers[self.db_uri] = self

    async def close(self) -> None:
        """Close connection pool gracefully.

        Borrower (manager mượn pool/saver của manager khác) CHỈ gỡ tham chiếu —
        tuyệt đối không đóng pool dùng chung của owner.
        """
        if self._pool is not None:
            for saver in self._savers:
                close = getattr(saver, "close", None)
                if close is not None:
                    try:
                        result = close()
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:  # noqa: S110 - best-effort cleanup
                        pass
            self._savers.clear()
            if self._owns_shared_pool:
                await self._pool.close()
                if self.db_uri in _shared_managers and _shared_managers[self.db_uri] is self:
                    del _shared_managers[self.db_uri]
                self._owns_shared_pool = False
            self._pool = None
            self._saver = None

    def get_memory_checkpointer(self) -> MemorySaver:
        """Get an in-memory checkpointer for testing or fallback."""
        return self._memory_saver

    def get_postgres_checkpointer(self, conn: Any) -> BaseCheckpointSaver:
        """Instantiate an AsyncPostgresSaver for a given connection."""
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver(conn)
        self._savers.append(saver)
        return saver

    def get_async_postgres_checkpointer(self) -> BaseCheckpointSaver:
        """
        Trả AsyncPostgresSaver dùng chung pool nội bộ (yêu cầu đã initialize() thành công).
        Saver dùng chung cho mọi graph — tự checkout connection từ pool cho từng thao tác.
        """
        if self._pool is None or self._saver is None:
            raise RuntimeError(
                "CheckpointManager chưa initialize() với CHECKPOINT_DB_URI cấu hình Postgres."
            )
        return self._saver

    @staticmethod
    def build_thread_config(
        namespace: str,
        tenant_id: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """
        Build thread configuration adhering to strict namespace isolation:
        - Pre-Sales: namespace='PRE_SALES', thread_id='presales:{tenant_id}:{entity_id}'
        - Official Quote: namespace='DEFAULT', thread_id='quote:{tenant_id}:{entity_id}'
        """
        if namespace == "PRE_SALES":
            thread_id = f"presales:{tenant_id}:{entity_id}"
        else:
            thread_id = f"quote:{tenant_id}:{entity_id}"

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            },
            "metadata": {
                "namespace": namespace,
            },
        }
