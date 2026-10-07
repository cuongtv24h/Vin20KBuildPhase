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


# ─── Test kết nối: đúng ca Cloudflare chặn /models nhưng chat vẫn chạy ────────
# Bối cảnh: Admin bấm "Test kết nối" và nhận HTTP 403 kèm trang "Just a moment..." của Cloudflare,
# dù API dùng tốt từ ứng dụng khác. Endpoint phải: gửi User-Agent rõ ràng, thử tiếp /chat/completions,
# và trả về câu chẩn đoán đọc được (không đổ HTML thô).


@pytest.mark.asyncio
async def test_test_ket_noi_qua_duoc_cloudflare_va_bao_ro_duong_da_dung(
    client: AsyncClient, provider_server
) -> None:
    """Provider trỏ vào server giả: /models bị Cloudflare chặn, /chat/completions OK → kết luận OK."""
    base, _ = provider_server("cloudflare-models-only")
    created = (
        await client.post(
            "/api/v1/admin/llm/providers",
            json={**PAYLOAD, "base_url": base},
            headers=ADMIN_HEADERS,
        )
    ).json()

    resp = await client.post(f"/api/v1/admin/llm/providers/{created['provider_id']}/test", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True, body["detail"]
    assert body["status"] == "OK"
    assert "chat/completions" in body["detail"]
    assert "Cloudflare" in body["detail"]
    assert body["latency_ms"] > 0

    # Kết quả phải đọng lại trong danh sách để bảng không còn hiện "Chưa kiểm tra".
    listed = (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).json()
    row = next(p for p in listed["items"] if p["provider_id"] == created["provider_id"])
    assert row["last_test_status"] == "OK"
    assert row["last_test_latency_ms"] is not None
    assert row["last_tested_at"]


@pytest.mark.asyncio
async def test_test_ket_noi_bi_cloudflare_chan_ca_hai_thi_bao_loi_doc_duoc(
    client: AsyncClient, provider_server
) -> None:
    base, _ = provider_server("cloudflare-both")
    created = (
        await client.post(
            "/api/v1/admin/llm/providers",
            json={**PAYLOAD, "base_url": base},
            headers=ADMIN_HEADERS,
        )
    ).json()

    resp = await client.post(f"/api/v1/admin/llm/providers/{created['provider_id']}/test", headers=ADMIN_HEADERS)
    body = resp.json()
    assert body["ok"] is False
    assert body["status"] == "ERROR"
    assert "Cloudflare" in body["detail"]
    assert "<!DOCTYPE" not in body["detail"] and "<html" not in body["detail"]


def _provider_payload(
    name: str, priority: int, model: str, *, base_url: str, active: bool = True, api_key: str | None = None
) -> dict:
    """Payload khai báo một nhà cung cấp — dùng để dựng chuỗi dự phòng trong các test dưới.

    `api_key` mặc định suy từ `model` (ASCII) — không suy từ `name` vì tên có thể là tiếng Việt và
    khoá API nằm trong HTTP header (chỉ ASCII).
    """
    return {
        **PAYLOAD,
        "name": name,
        "priority": priority,
        "model_name": model,
        "base_url": base_url,
        "is_active": active,
        "api_key": api_key or f"sk-{model}-1234",
    }


@pytest.mark.asyncio
async def test_nhieu_khai_bao_db_thi_noi_thanh_chuoi_chinh_du_phong_theo_uu_tien(
    client: AsyncClient, provider_server
) -> None:
    """Khai báo nhiều nhà cung cấp: nhà cung cấp ưu tiên nhỏ nhất là chính, còn lại là dự phòng theo thứ tự.

    Khai báo **lộn xộn** (không theo thứ tự ưu tiên) để chắc chắn chuỗi xếp theo `priority`, không phải
    theo lúc tạo; nhà cung cấp đang TẮT phải bị loại khỏi chuỗi.
    """
    from src.services.llm import get_llm
    from src.services.llm_providers import resolve_provider_configs

    fake_base, _ = provider_server("ok")
    # Tạo theo thứ tự: 20 → 10 → 30 → (tắt, 5)
    for payload in (
        _provider_payload("Dự phòng 1", 20, "fb1-model", base_url=fake_base),
        _provider_payload("Chính", 10, "primary-model", base_url=fake_base),
        _provider_payload("Dự phòng 2", 30, "fb2-model", base_url=fake_base),
        _provider_payload("Đang tắt", 5, "tat-model", base_url=fake_base, active=False),
    ):
        resp = await client.post("/api/v1/admin/llm/providers", json=payload, headers=ADMIN_HEADERS)
        assert resp.status_code == 201, resp.text

    configs = resolve_provider_configs()
    assert [c.model_name for c in configs] == ["primary-model", "fb1-model", "fb2-model"]
    assert configs[0].is_fallback is False
    assert [c.is_fallback for c in configs[1:]] == [True, True]

    # Và chuỗi đó phải được truyền thật vào LLM mà ứng dụng dùng.
    llm = get_llm()
    assert llm.runnable.model_name == "primary-model"
    assert [m.model_name for m in llm.fallbacks] == ["fb1-model", "fb2-model"]


@pytest.mark.asyncio
async def test_nha_cung_cap_chinh_chet_thi_tu_dong_chay_sang_nha_cung_cap_ke_tiep(
    client: AsyncClient, provider_server
) -> None:
    """Chứng minh bằng lượt gọi thật: primary không gọi được → câu trả lời đến từ nhà cung cấp dự phòng.

    Đây là thứ Admin quan tâm khi khai báo nhiều nhà cung cấp: một cái chết (hoặc bị rate limit) thì
    dịch vụ vẫn trả lời, không sập Copilot.
    """
    from src.services.llm import get_llm

    fake_base, _ = provider_server("ok")
    # "Chính" trỏ vào cổng không có gì lắng nghe → chắc chắn lỗi kết nối.
    dead_base = "http://127.0.0.1:9/v1"
    for payload in (
        _provider_payload("Chính (chết)", 10, "primary-model", base_url=dead_base, api_key="sk-primary-1234"),
        _provider_payload("Dự phòng", 20, "fb1-model", base_url=fake_base, api_key="sk-fallback-1234"),
    ):
        resp = await client.post("/api/v1/admin/llm/providers", json=payload, headers=ADMIN_HEADERS)
        assert resp.status_code == 201, resp.text

    llm = get_llm()
    assert llm.runnable.model_name == "primary-model"
    answer = await llm.ainvoke("ping")
    assert answer.content == "pong"  # câu trả lời của nhà cung cấp dự phòng


@pytest.mark.asyncio
async def test_doi_khoa_ma_hoa_khong_lam_mat_nha_cung_cap_nhung_phai_nhap_lai_key(
    client: AsyncClient, monkeypatch, caplog
) -> None:
    """Đặt `LLM_SECRET_KEY` sau khi đã khai báo khoá: vẫn dùng được, nhưng cảnh báo phải nhập lại key.

    Nếu đổi khoá mã hoá mà coi khoá cũ là "hỏng", Admin sẽ mất sạch nhà cung cấp và Copilot ngừng trả
    lời ngay khi deploy — đường lùi (giải mã bằng khoá mặc định của mã nguồn) tránh đúng chuyện đó,
    nhưng phải ghi cảnh báo để khoá được mã hoá lại theo khoá riêng.
    """
    import logging

    from src.services.llm_providers import refresh_provider_cache, reset_provider_cache
    from tests.conftest import async_test_session_factory

    created = (await client.post("/api/v1/admin/llm/providers", json=PAYLOAD, headers=ADMIN_HEADERS)).json()
    assert created["has_api_key"] is True

    monkeypatch.setenv("LLM_SECRET_KEY", "khoa-rieng-cua-vm-2026")
    reset_provider_cache()
    caplog.set_level(logging.WARNING, logger="src.services.llm_secrets")
    async with async_test_session_factory() as session:
        configs = await refresh_provider_cache(session)

    # Không mất nhà cung cấp (dịch vụ không sập) …
    assert [c.model_name for c in configs] == [PAYLOAD["model_name"]]
    assert configs[0].api_key == PAYLOAD["api_key"]
    # … nhưng phải có cảnh báo yêu cầu nhập lại khoá để mã hoá theo khoá mới.
    assert any("nhập lại" in record.message.lower() for record in caplog.records)

    # Nhập lại khoá (đúng việc Admin sẽ làm trên giao diện) → mã hoá theo khoá mới.
    resp = await client.put(
        f"/api/v1/admin/llm/providers/{created['provider_id']}",
        json={**PAYLOAD, "api_key": "sk-moi-sau-khi-doi-khoa-9999"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from src.db.models import LLMProviderModel

    async with async_test_session_factory() as session:
        row = (await session.execute(select(LLMProviderModel))).scalars().first()
    assert decrypt_api_key(row.api_key_encrypted) == "sk-moi-sau-khi-doi-khoa-9999"

    # Và khi khoá ENV bị đổi sang giá trị khác hẳn (không còn giải mã được bằng khoá cũ) thì phải
    # bỏ nhà cung cấp đó kèm cảnh báo, không im lặng.
    monkeypatch.setenv("LLM_SECRET_KEY", "khoa-khac-hoan-toan")
    reset_provider_cache()
    caplog.clear()
    async with async_test_session_factory() as session:
        configs = await refresh_provider_cache(session)
    assert configs == []
    assert any("không giải mã được" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_test_ket_noi_xanh_thi_chat_that_cung_chay_duoc(client: AsyncClient, provider_server, monkeypatch) -> None:
    """Nút Test kết nối không được nói dối: khi nó báo OK thì Copilot gọi thật cũng phải qua.

    Kịch bản: nhà cung cấp chỉ cho client giống trình duyệt. Bật `LLM_HTTP_HEADERS=browser` rồi:
    1) bấm Test kết nối → OK; 2) gọi thật qua `get_llm()` → trả lời được. Cả hai dùng chung bộ header.
    """
    from src.services.llm import get_llm

    base, seen = provider_server("cloudflare-ua-only")
    monkeypatch.setenv("LLM_HTTP_HEADERS", "browser")
    payload = _provider_payload("Sau Cloudflare", 10, "cloudflare-model", base_url=base)
    created = await client.post("/api/v1/admin/llm/providers", json=payload, headers=ADMIN_HEADERS)
    assert created.status_code == 201, created.text

    tested = await client.post(
        f"/api/v1/admin/llm/providers/{created.json()['provider_id']}/test", headers=ADMIN_HEADERS
    )
    assert tested.status_code == 200
    body = tested.json()
    assert body["ok"] is True, body["detail"]
    assert body["status"] == "OK"

    seen.clear()
    answer = await get_llm().ainvoke("ping")
    assert answer.content == "pong"
    assert seen and seen[0].startswith("Mozilla/5.0"), seen[0]



# ── Đợt 22 (bổ sung): “2 nhà cung cấp sẵn” phải NHÌN THẤY được, và thêm mới được ngoài chúng ──────────
# Người dùng: “Dùng sẵn cơ chế cũ đã có, cho phép thêm mới nhà cung cấp ngoài 2 nhà cung cấp sẵn.”
# Trước đây bảng quản trị chỉ liệt kê bản ghi DB nên khi hệ thống đang chạy bằng ENV (thường 2 nhà cung
# cấp: primary + fallback 1) màn hình vẫn ghi “Chưa khai báo nhà cung cấp nào” ⇒ không thấy mình đang có gì.


@pytest.mark.asyncio
async def test_hien_thi_nha_cung_cap_doc_tu_env(client: AsyncClient, monkeypatch) -> None:
    """ENV có 2 khoá ⇒ `env_items` liệt kê đủ 2 dòng, khoá chỉ dạng che, và nói rõ chưa bị DB đè."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-primary-0001")
    monkeypatch.delenv("FALLBACK1_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FALLBACK1_OPENAI_API_KEY", "sk-env-fallback-0002")
    monkeypatch.setenv("FALLBACK1_MODEL_NAME", "gpt-4o-mini")
    # Settings được cache trong tiến trình ⇒ xoá cache để đọc lại ENV vừa đặt.
    from src.config import get_settings

    get_settings.cache_clear()

    resp = await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "env" and body["total"] == 0, "DB trống thì vẫn ưu tiên báo đang chạy bằng ENV"
    names = [item["name"] for item in body["env_items"]]
    assert names == ["ENV · primary", "ENV · fallback 1"]
    primary = body["env_items"][0]
    assert primary["provider_id"] == "ENV-PRIMARY"
    assert primary["provider"] == "openai" and primary["has_api_key"] is True
    assert primary["api_key_masked"].endswith("0001")
    assert "sk-env-primary-0001" not in resp.text, "khoá ENV cũng không được trả nguyên văn"
    assert body["env_items"][1]["is_fallback"] is True
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_them_nha_cung_cap_moi_ngoai_hai_cai_san(client: AsyncClient, monkeypatch) -> None:
    """Thêm nhà cung cấp thứ ba (vendor khác) trong khi ENV vẫn còn 2 nhà cung cấp sẵn."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-primary-0001")
    from src.config import get_settings

    get_settings.cache_clear()

    payload = dict(
        PAYLOAD,
        name="DeepSeek (nhà cung cấp mới)",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model_name="deepseek-chat",
        api_key="sk-deepseek-9999",
        priority=0,
    )
    created = await client.post("/api/v1/admin/llm/providers", json=payload, headers=ADMIN_HEADERS)
    assert created.status_code == 201, created.text
    assert created.json()["provider"] == "deepseek"

    body = (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).json()
    assert body["source"] == "db", "có bản ghi DB ⇒ DB chạy trước ENV"
    assert [item["provider"] for item in body["items"]] == ["deepseek"]
    # 2 nhà cung cấp ENV vẫn hiển thị (chỉ-đọc) để quản trị viên biết chúng là đường lui.
    assert [item["provider_id"] for item in body["env_items"]] == ["ENV-PRIMARY"]
    assert body["env_items"][0]["overridden_by_db"] is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_kiem_tra_ket_noi_nha_cung_cap_env(client: AsyncClient, monkeypatch, provider_server) -> None:
    """“Test kết nối” phải chạy được cho cả nhà cung cấp ENV, không chỉ bản ghi DB."""
    base_url, _seen = provider_server("ok")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-primary-0001")
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)
    from src.config import get_settings

    get_settings.cache_clear()

    resp = await client.post("/api/v1/admin/llm/providers/ENV-PRIMARY/test", headers=ADMIN_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_id"] == "ENV-PRIMARY"
    assert body["ok"] is True and body["status"] == "OK"
    # Không ghi lịch sử kiểm tra vào DB (không có bản ghi nào cho nhà cung cấp ENV).
    listing = (await client.get("/api/v1/admin/llm/providers", headers=ADMIN_HEADERS)).json()
    assert listing["total"] == 0
    get_settings.cache_clear()
