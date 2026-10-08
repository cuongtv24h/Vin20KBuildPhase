import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.agents.copilot import grounding
from src.db.models import Base
from src.db.session import get_db_session
from src.main import app
from src.services import data_source

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


@pytest.fixture(autouse=True)
def isolate_copilot_grounding_from_local_db(monkeypatch):
    """Chặn Copilot grounding đọc DB thật của máy dev trong test + bật fixture canonical.

    `grounding._fetch_db_units` / `policy_source.fetch_policies_sync` dùng psycopg trỏ thẳng DB cấu
    hình (machine-dependent); đặt cache = [] để mọi test chỉ chạy với fixture canonical, kết quả không
    phụ thuộc máy. (DB endpoint FastAPI vẫn chạy qua in-memory SQLite ở fixture bên dưới.)

    **Sản phẩm chạy thật thì ngược lại**: mặc định `ALLOW_FIXTURE_DATA` không bật ⇒ chỉ đọc CSDL.
    Cờ này chỉ dùng cho test/demo offline — xem `src/services/data_source.py`.
    """
    monkeypatch.setattr(grounding, "_cached_db_units", [], raising=False)
    monkeypatch.setattr(grounding, "_cached_db_policies", [], raising=False)
    monkeypatch.setenv(data_source.FIXTURE_ENV, "1")


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
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
    monkeypatch.setattr("src.db.session.async_session_factory", async_test_session_factory)
    monkeypatch.setattr("src.db.async_session_factory", async_test_session_factory, raising=False)
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

    def version_string(self) -> str:
        """Tên server trong header `Server` — giống nhà cung cấp thật đứng sau Cloudflare."""
        return "cloudflare"

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self) -> None:  # noqa: N802 — tên do BaseHTTPRequestHandler quy định
        type(self).seen_user_agents.append(self.headers.get("User-Agent", ""))
        if self.path.endswith("/models"):
            if self.scenario == "cloudflare-ua-only":
                # Chỉ client gửi header kiểu trình duyệt mới qua — mô phỏng Cloudflare "chặn theo kiểu client".
                if self.headers.get("User-Agent", "").startswith("Mozilla/5.0"):
                    self._json(404, {"error": {"message": "not found"}})
                else:
                    self._send(
                    403,
                    CLOUDFLARE_HTML.encode(),
                    "text/html; charset=UTF-8",
                    # Header thật Cloudflare gửi kèm — Admin cần để gửi cho nhà cung cấp.
                    {"cf-mitigated": "challenge", "cf-ray": "8f3c1a2b9d6e4f11-SIN"},
                )
            elif self.scenario == "ok":
                self._json(200, {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]})
            elif self.scenario in {"cloudflare-models-only", "cloudflare-both"}:
                self._send(
                    403,
                    CLOUDFLARE_HTML.encode(),
                    "text/html; charset=UTF-8",
                    # Header thật Cloudflare gửi kèm — Admin cần để gửi cho nhà cung cấp.
                    {"cf-mitigated": "challenge", "cf-ray": "8f3c1a2b9d6e4f11-SIN"},
                )
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
            payload = {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "created": 0,
                "model": "fake-model",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            }
            if self.scenario == "cloudflare-ua-only":
                if self.headers.get("User-Agent", "").startswith("Mozilla/5.0"):
                    self._json(200, payload)
                else:
                    self._send(
                    403,
                    CLOUDFLARE_HTML.encode(),
                    "text/html; charset=UTF-8",
                    # Header thật Cloudflare gửi kèm — Admin cần để gửi cho nhà cung cấp.
                    {"cf-mitigated": "challenge", "cf-ray": "8f3c1a2b9d6e4f11-SIN"},
                )
            elif self.scenario in {"ok", "cloudflare-models-only"}:
                self._json(200, payload)
            elif self.scenario == "homepage":
                # Base URL trỏ vào trang web: mọi đường dẫn đều trả trang chủ (HTML), kèm 200.
                self._send(200, b"<!DOCTYPE html><html><body>Trang chu</body></html>", "text/html")
            elif self.scenario == "bad-key":
                self._json(401, {"error": {"message": "Invalid API key"}})
            elif self.scenario == "missing-v1" and self.path.startswith("/v1/"):
                self._json(200, payload)
            else:
                self._send(
                    403,
                    CLOUDFLARE_HTML.encode(),
                    "text/html; charset=UTF-8",
                    # Header thật Cloudflare gửi kèm — Admin cần để gửi cho nhà cung cấp.
                    {"cf-mitigated": "challenge", "cf-ray": "8f3c1a2b9d6e4f11-SIN"},
                )
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
