"""Thiết lập đọc câu trả lời Copilot (TTS): danh mục nhà cung cấp, ưu tiên hồ sơ người dùng, phản hồi giọng.

Kiểm chứng đúng ba điều dễ sai:
- quy đổi chi phí theo đơn giá công bố (không bịa con số);
- thiết lập riêng của từng nhân viên thắng mặc định hệ thống, và chỉ ADMIN/MANAGER đổi được mặc định;
- phản hồi giọng đọc lưu được và tổng hợp lại thành tỉ lệ hài lòng.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.api.deps import create_access_token
from src.services.tts_providers import (
    TTS_PROVIDER_CATALOG,
    estimate_tts_cost,
    get_tts_provider,
    validate_tts_settings,
)

SALE_HEADERS = {"Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}"}
OTHER_SALE_HEADERS = {"Authorization": f"Bearer {create_access_token('trang.le@vlandfuture.vn', 'SALE')}"}
MANAGER_HEADERS = {"Authorization": f"Bearer {create_access_token('ha.nguyen@vlandfuture.vn', 'MANAGER')}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {create_access_token('admin@vlandfuture.vn', 'ADMIN')}"}


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    """DB test dùng chung một engine in-memory → phải tự dọn hai bảng TTS giữa các test."""
    from sqlalchemy import delete

    from src.db.models import TTSFeedbackModel, TTSSettingsModel
    from tests.conftest import async_test_session_factory

    async with async_test_session_factory() as session:
        await session.execute(delete(TTSFeedbackModel))
        await session.execute(delete(TTSSettingsModel))
        await session.commit()
    yield


class TestCatalog:
    def test_catalog_co_tieng_viet_va_gia_niem_yet(self):
        providers = {cfg.provider for cfg in TTS_PROVIDER_CATALOG}
        assert {"browser", "openai", "google_cloud", "azure", "viettel", "vbee", "fpt"} <= providers
        # Mọi nhà cung cấp API phải khai báo ENV cho khoá và đơn giá kèm mốc kiểm chứng.
        for cfg in TTS_PROVIDER_CATALOG:
            if cfg.mode == "api":
                assert cfg.env_key, cfg.provider
                assert cfg.price_per_1m_chars > 0, cfg.provider
                assert cfg.verified_at, cfg.provider
        # Trình duyệt là lựa chọn 0 đồng luôn sẵn có (demo không cần khoá).
        browser = get_tts_provider("browser")
        assert browser is not None and browser.price_per_1m_chars == 0

    def test_uoc_tinh_chi_phi_theo_don_gia(self):
        # 600 ký tự × 15 USD/1M = 0.009 USD
        assert estimate_tts_cost("x" * 600, provider="openai")["cost"] == 0.009
        # 600 ký tự × 4 USD/1M = 0.0024 USD
        assert estimate_tts_cost("x" * 600, provider="google_cloud")["cost"] == 0.0024
        # Nhà cung cấp tính bằng VNĐ: đúng đơn giá trên mỗi triệu ký tự.
        assert estimate_tts_cost("x" * 1_000_000, provider="viettel", max_chars=1_000_000)["cost"] == 320_000
        # Cắt theo trần ký tự mỗi lượt — câu dài 5.000 ký tự nhưng chỉ tính 600.
        capped = estimate_tts_cost("x" * 5_000, provider="openai", max_chars=600)
        assert capped["chars"] == 5_000 and capped["billable_chars"] == 600 and capped["cost"] == 0.009
        # Không có khoá vẫn ước tính được (dùng cho màn hình cấu hình).
        assert estimate_tts_cost("x" * 100, provider="browser")["cost"] == 0

    def test_validate_tu_choi_cau_hinh_sai(self):
        with pytest.raises(ValueError, match="Nhà cung cấp"):
            validate_tts_settings({"provider": "khong-ton-tai"})
        with pytest.raises(ValueError, match="Tốc độ"):
            validate_tts_settings({"speed": 3.5})
        with pytest.raises(ValueError, match="Giới hạn ký tự"):
            validate_tts_settings({"max_chars_per_turn": 10})


@pytest.mark.asyncio
class TestSettingsApi:
    async def test_mac_dinh_la_giong_trinh_duyet_mien_phi(self, client: AsyncClient):
        res = await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert body["effective"]["provider"] == "browser"
        assert body["cost_hint"]["cost"] == 0
        assert body["user_override"] is None
        assert body["default"]["is_explicit"] is False
        assert body["feedback_summary"]["total"] == 0
        # Danh mục có giọng tiếng Việt để chọn, và không lộ khoá API.
        google = next(c for c in body["catalog"] if c["provider"] == "google_cloud")
        assert any(v["code"].startswith("vi-VN") for v in google["voices"])
        # Chỉ trả về cờ "đã có khoá", tuyệt đối không trả giá trị khoá.
        assert '"api_key"' not in res.text and "sk-" not in res.text
        assert '"api_key_configured"' in res.text

    async def test_ho_so_rieng_thang_mac_dinh_va_pham_vi_default_chan_sale(self, client: AsyncClient):
        ok = await client.put(
            "/api/v1/settings/tts",
            json={"scope": "user", "provider": "google_cloud", "voice": "vi-VN-Wavenet-A", "speed": 1.2},
            headers=SALE_HEADERS,
        )
        assert ok.status_code == 200
        assert ok.json()["effective"]["voice"] == "vi-VN-Wavenet-A"
        assert ok.json()["effective"]["speed"] == 1.2
        assert ok.json()["cost_hint"]["provider"] == "google_cloud"
        assert ok.json()["cost_hint"]["cost"] > 0  # nói trước chi phí khi chọn giọng trả phí

        forbidden = await client.put(
            "/api/v1/settings/tts", json={"scope": "default", "provider": "azure"}, headers=SALE_HEADERS
        )
        assert forbidden.status_code == 403
        assert "ADMIN/MANAGER" in forbidden.json()["detail"]

        # Nhân viên khác không bị ảnh hưởng bởi lựa chọn của đồng nghiệp.
        other = (await client.get("/api/v1/settings/tts", headers=OTHER_SALE_HEADERS)).json()
        assert other["effective"]["provider"] == "browser"
        assert other["user_override"] is None

        # MANAGER đặt mặc định → người chưa có hồ sơ riêng nhận mặc định mới.
        res = await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "provider": "azure", "voice": "vi-VN-HoaiMyNeural", "auto_speak": True},
            headers=MANAGER_HEADERS,
        )
        assert res.status_code == 200
        assert res.json()["default"]["is_explicit"] is True

        after = (await client.get("/api/v1/settings/tts", headers=OTHER_SALE_HEADERS)).json()
        assert after["effective"]["provider"] == "azure"
        assert after["effective"]["auto_speak"] is True
        assert after["effective"]["voice"] == "vi-VN-HoaiMyNeural"

        # Sale 1 vẫn giữ lựa chọn riêng (hồ sơ người dùng thắng mặc định).
        mine = (await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)).json()
        assert mine["effective"]["provider"] == "google_cloud"
        assert mine["effective"]["auto_speak"] is False

    async def test_cau_hinh_sai_tra_422_va_luu_lai_duoc_qua_lan_sau(self, client: AsyncClient):
        bad = await client.put("/api/v1/settings/tts", json={"provider": "khong-co-that"}, headers=SALE_HEADERS)
        assert bad.status_code == 422
        assert "Nhà cung cấp" in bad.json()["detail"]

        await client.put(
            "/api/v1/settings/tts", json={"provider": "browser", "voice": "vi-VN", "speed": 0.9}, headers=SALE_HEADERS
        )
        again = (await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)).json()
        assert again["effective"]["speed"] == 0.9
        assert again["user_override"]["voice"] == "vi-VN"

    async def test_bat_buoc_dang_nhap(self, client: AsyncClient):
        assert (await client.get("/api/v1/settings/tts")).status_code == 401
        assert (await client.put("/api/v1/settings/tts", json={"provider": "browser"})).status_code == 401

    async def test_phan_hoi_giong_doc_tong_hop_duoc(self, client: AsyncClient):
        first = await client.post(
            "/api/v1/settings/tts/feedback",
            json={"rating": 1, "provider": "browser", "voice": "vi-VN", "reason": "Nghe rõ"},
            headers=SALE_HEADERS,
        )
        assert first.status_code == 201
        assert first.json()["up"] == 1

        await client.post("/api/v1/settings/tts/feedback", json={"rating": -1, "reason": "Hơi nhanh"}, headers=SALE_HEADERS)
        summary = (await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)).json()["feedback_summary"]
        assert summary == {"total": 2, "up": 1, "down": 1, "satisfaction": 0.5}

        invalid = await client.post("/api/v1/settings/tts/feedback", json={"rating": 5}, headers=SALE_HEADERS)
        assert invalid.status_code == 422

        # Phản hồi không đăng nhập bị chặn (không ghi được vào hồ sơ ai).
        assert (await client.post("/api/v1/settings/tts/feedback", json={"rating": 1})).status_code == 401

    async def test_admin_doi_mac_dinh_cho_toan_he_thong(self, client: AsyncClient):
        res = await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "provider": "viettel", "voice": "hn_female_ngochuyen", "speed": 1.1},
            headers=ADMIN_HEADERS,
        )
        assert res.status_code == 200
        effective = (await client.get("/api/v1/settings/tts", headers=ADMIN_HEADERS)).json()["effective"]
        assert effective["provider"] == "viettel"
        assert effective["speed"] == 1.1
