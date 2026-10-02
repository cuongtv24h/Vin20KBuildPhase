import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base
from src.db.session import get_db_session
from src.main import app

# Shared in-memory SQLite engine for tests
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
async_test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create all tables in in-memory SQLite before test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db_session():
        async with async_test_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db_session] = _override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests."""
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock


# ── Server nhà cung cấp LLM giả (dùng cho test "Test kết nối") ──────────────────
# Dựng đúng hành vi thật đã gặp: Cloudflare trả 403 kèm trang "Just a moment...", gateway chỉ mở
# /chat/completions, hoặc Base URL thiếu /v1. Xem tests/test_services/test_llm_probe.py.
CLOUDFLARE_HTML = (
    "<!DOCTYPE html><html lang=\"en-US\"><head><title>Just a moment...</title>"
    "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=UTF-8\">"
    "</head><body><div id=\"cf-chl-wrapper\">Checking your browser before accessing.</div></body></html>"
)


class _ProviderHandler(BaseHTTPRequestHandler):
    """Server giả: hành vi điều khiển qua `scenario` của lớp (mỗi test một server riêng)."""

    scenario = "ok"
    seen_user_agents: list[str] = []

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802 — tên do BaseHTTPRequestHandler quy định
        type(self).seen_user_agents.append(self.headers.get("User-Agent", ""))
        if self.path.endswith("/models"):
            if self.scenario == "ok":
                self._json(200, {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]})
            elif self.scenario in {"cloudflare-models-only", "cloudflare-both"}:
                self._send(403, CLOUDFLARE_HTML.encode(), "text/html; charset=UTF-8")
            elif self.scenario == "homepage":
                self._send(200, b"<!DOCTYPE html><html><body>Trang chu</body></html>", "text/html")
            elif self.scenario == "bad-key":
                self._json(401, {"error": {"message": "Invalid API key"}})
            else:
                self._json(404, {"error": {"message": "not found"}})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802 — tên do BaseHTTPRequestHandler quy định
        type(self).seen_user_agents.append(self.headers.get("User-Agent", ""))
        if self.path.endswith("/chat/completions"):
            if self.scenario in {"ok", "cloudflare-models-only"}:
                self._json(200, {"choices": [{"message": {"content": "pong"}}]})
            elif self.scenario == "missing-v1" and self.path.startswith("/v1/"):
                self._json(200, {"choices": [{"message": {"content": "pong"}}]})
            else:
                self._send(403, CLOUDFLARE_HTML.encode(), "text/html; charset=UTF-8")
        else:
            self._json(404, {"error": {"message": "not found"}})

    def log_message(self, *args: object) -> None:  # pragma: no cover — tắt log ồn ào
        return


@pytest.fixture()
def provider_server():
    """Khởi động server nhà cung cấp giả trên cổng trống.

    Trả về hàm `factory(scenario) -> (base_url, user_agents)`; mọi server được tắt khi test kết thúc.
    """
    servers: list = []

    def factory(scenario: str):
        handler = type("Handler", (_ProviderHandler,), {"scenario": scenario, "seen_user_agents": []})
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def shutdown() -> None:
            server.shutdown()
            server.server_close()

        servers.append(shutdown)
        return f"http://127.0.0.1:{server.server_port}/v1", handler.seen_user_agents

    yield factory
    for shutdown in servers:
        shutdown()
