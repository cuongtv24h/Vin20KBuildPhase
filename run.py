"""
Launcher chạy dev server local (đặc biệt quan trọng trên Windows).

Lý do tồn tại: psycopg async (AsyncConnectionPool của LangGraph checkpointer)
KHÔNG tương thích ProactorEventLoop — event loop mặc định của Python trên
Windows. Phải đặt WindowsSelectorEventLoopPolicy TRƯỚC khi uvicorn tạo event
loop (tức trước asyncio.run bên trong uvicorn.run), nên policy được đặt ở đây
chứ không phải trong src/main.py (module app được import SAU khi loop đã chạy).

Cách chạy:
    py -3 run.py                 # server + checkpointer Postgres (nếu .env bật)
    USE_POSTGRES_CHECKPOINTER=false py -3 run.py   # ép chạy MemorySaver offline

Cấu hình uvicorn đọc từ settings: APP_HOST/APP_PORT (mặc định 0.0.0.0:8000),
LOG_LEVEL cho --log-level.
"""

from __future__ import annotations

import sys

# BẮT BUỘC chạy trước mọi thứ tạo event loop (kể cả import uvicorn trên Windows).
if sys.platform == "win32":
    import asyncio
    from asyncio import WindowsSelectorEventLoopPolicy

    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

import src.db.dns_patch  # noqa: F401, E402 — Resilient DNS cho Supabase DB Pooler
from src.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    config = uvicorn.Config(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        import asyncio

        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()


if __name__ == "__main__":
    main()
