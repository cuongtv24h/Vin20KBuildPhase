"""Admin tự khai báo nhà cung cấp LLM (API key + đơn giá) và đo độ tiêu tốn.

Khoá các hành vi quan trọng:
- CRUD provider, API key **không bao giờ** trả về nguyên văn (chỉ dạng che) và lưu dạng mã hoá;
- ưu tiên DB trước, chỉ khi DB trống mới rơi về ENV;
- usage summary quy chi phí từ đơn giá Admin nhập.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.api.deps import create_access_token
from src.services import llm_usage
from src.services.llm_secrets import decrypt_api_key

ADMIN_HEADERS = {"Authorization": f"Bearer {create_access_token('admin@vlandfuture.vn', 'ADMIN')}"}
SALE_HEADERS = {"Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}"}

PAYLOAD = {
    "name": "OpenAI chính",
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-test-1234567890abcd",
    "input_price_per_1m": 0.15,
    "output_price_per_1m": 0.60,
    "currency": "USD",
    "temperature": 0.2,
    "priority": 1,
    "is_active": True,
}


@pytest_asyncio.fixture(autouse=True)
async def clean_state(tmp_path, monkeypatch):
    """Mỗi test dùng file usage riêng, cache provider sạch và bảng provider trống.

    DB test là SQLite in-memory dùng chung một engine (StaticPool) nên phải tự dọn bảng,
    nếu không dữ liệu test trước sẽ rơi sang test sau.
    """
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "llm_usage.jsonl"))
    from sqlalchemy import delete

    from src.db.models import LLMProviderModel
    from src.services.llm_providers import reset_provider_cache
    from tests.conftest import async_test_session_factory

    async with async_test_session_factory() as session:
        await session.execute(delete(LLMProviderModel))
        await session.commit()

    reset_provider_cache()
    yield
    reset_provider_cache()


@pytest.mark.asyncio
async def test_chi_admin_duoc_cau_hinh(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/llm/providers")).status_code == 403
    assert (await client.get("/api/v1/admin/llm/providers", headers=SALE_HEADERS)).status_code == 403
    assert (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).status_code == 200


@pytest.mark.asyncio
async def test_them_nha_cung_cap_khong_lo_api_key(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/admin/llm/providers", json=PAYLOAD, headers=ADMIN_HEADERS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider_id"].startswith("LLM-")
    assert body["has_api_key"] is True
    # Không trả khoá thật, chỉ dạng che
    assert "sk-test-1234567890abcd" not in resp.text
    assert body["api_key_masked"] == "sk-t…abcd"
    # Đơn giá được lưu để tính chi phí
    assert body["input_price_per_1m"] == 0.15
    assert body["output_price_per_1m"] == 0.60

    # Và trong DB khoá phải ở dạng mã hoá
    from sqlalchemy import select

    from src.db.models import LLMProviderModel
    from tests.conftest import async_test_session_factory

    async with async_test_session_factory() as session:
        row = (await session.execute(select(LLMProviderModel))).scalars().first()
    assert row is not None
    assert row.api_key_encrypted != PAYLOAD["api_key"]
    assert row.api_key_encrypted.startswith("enc::")
    assert decrypt_api_key(row.api_key_encrypted) == PAYLOAD["api_key"]

    # DB có dữ liệu → nguồn cấu hình phải là 'db'
    listing = (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).json()
    assert listing["source"] == "db"
    assert listing["total"] == 1


@pytest.mark.asyncio
async def test_sua_de_trong_api_key_thi_giu_khoa_cu(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/admin/llm/providers", json=PAYLOAD, headers=ADMIN_HEADERS)).json()
    updated = await client.put(
        f"/api/v1/admin/llm/providers/{created['provider_id']}",
        json={**PAYLOAD, "api_key": None, "name": "Đổi tên", "input_price_per_1m": 0.2},
        headers=ADMIN_HEADERS,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Đổi tên"
    assert body["input_price_per_1m"] == 0.2
    assert body["has_api_key"] is True  # khoá cũ còn nguyên
    assert body["api_key_masked"] == "sk-t…abcd"


@pytest.mark.asyncio
async def test_uu_tien_db_truoc_env_sau(client: AsyncClient, monkeypatch) -> None:
    """Chưa khai báo DB → dùng ENV; khai báo rồi → ENV không còn được dùng."""
    from src.config import get_settings
    from src.services.llm_providers import cache_source, refresh_provider_cache, resolve_provider_configs

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-env-key", raising=False)

    # 1. DB trống → rơi về ENV
    from src.services.llm_providers import reset_provider_cache

    reset_provider_cache()
    await refresh_provider_cache()
    configs = resolve_provider_configs()
    assert cache_source() == "env"
    assert configs and configs[0].provider_id == "ENV-PRIMARY"
    assert configs[0].api_key == "sk-env-key"

    # 2. Admin khai báo trong DB → DB thắng, ENV bị bỏ qua
    await client.post("/api/v1/admin/llm/providers", json=PAYLOAD, headers=ADMIN_HEADERS)
    configs = resolve_provider_configs()
    assert cache_source() == "db"
    assert [c.api_key for c in configs] == [PAYLOAD["api_key"]]


@pytest.mark.asyncio
async def test_xoa_nha_cung_cap(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/admin/llm/providers", json=PAYLOAD, headers=ADMIN_HEADERS)).json()
    resp = await client.delete(f"/api/v1/admin/llm/providers/{created['provider_id']}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).json()["total"] == 0


def test_usage_summary_quy_chi_phi_theo_don_gia(tmp_path, monkeypatch) -> None:
    """1M token vào + 500k token ra, đơn giá 0.15/0.60 USD → 0.45 USD."""
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "usage.jsonl"))
    llm_usage.record_usage(
        provider="openai",
        model_name="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=500_000,
        latency_ms=120.0,
        ok=True,
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
    )
    llm_usage.record_usage(
        provider="openai",
        model_name="gpt-4o-mini",
        input_tokens=0,
        output_tokens=0,
        latency_ms=900.0,
        ok=False,
        error="timeout",
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
    )

    summary = llm_usage.summarize_usage(days=1)
    assert summary["total_calls"] == 2
    assert summary["failed_calls"] == 1
    assert summary["error_rate"] == 0.5
    assert summary["total_input_tokens"] == 1_000_000
    assert summary["total_output_tokens"] == 500_000
    assert summary["total_cost"] == pytest.approx(0.15 + 0.30, abs=1e-6)
    assert summary["by_provider"][0]["provider"] == "openai"
    assert summary["avg_cost_per_call"] == pytest.approx(0.225, abs=1e-6)

    records = llm_usage.recent_usage(limit=10)
    assert records[0]["ok"] is False  # mới nhất trước


@pytest.mark.asyncio
async def test_usage_endpoints_chi_admin(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "usage.jsonl"))
    llm_usage.record_usage(
        provider="openai",
        model_name="gpt-4o-mini",
        input_tokens=2_000,
        output_tokens=1_000,
        latency_ms=200.0,
        ok=True,
        input_price_per_1m=1.0,
        output_price_per_1m=1.0,
    )
    assert (await client.get("/api/v1/admin/llm/usage/summary")).status_code == 403
    summary = await client.get("/api/v1/admin/llm/usage/summary?days=1", headers=ADMIN_HEADERS)
    assert summary.status_code == 200
    assert summary.json()["total_calls"] == 1
    assert summary.json()["total_cost"] == pytest.approx(0.003, abs=1e-6)

    records = await client.get("/api/v1/admin/llm/usage/records?limit=5", headers=ADMIN_HEADERS)
    assert records.status_code == 200
    assert records.json()["items"][0]["model_name"] == "gpt-4o-mini"
