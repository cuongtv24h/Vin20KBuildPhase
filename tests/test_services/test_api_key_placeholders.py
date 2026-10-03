"""Khoá API "chỗ giữ chỗ" không được tính là khoá thật (đợt 21).

Người dùng mở màn hình quản trị → tab “Giọng đọc” và thấy cột **Khoá API** của OpenAI ghi **“Đã có”**,
rồi hỏi: *“Khoá api của OpenAI ở đâu vậy, tôi đã cung cấp đâu?”* — và đúng là chưa ai cung cấp.

Nguyên nhân: `.env.example` bán sẵn `OPENAI_API_KEY=sk-your-openai-or-groq-key`; hướng dẫn triển khai là
`cp .env.example .env`; hàm kiểm tra chỉ hỏi “khác rỗng?”. Bộ test này khoá lại luật đúng:

- giá trị rỗng / giá trị **mẫu** ⇒ **chưa có khoá** (UI hiện “Chưa có”, không mang khoá giả đi gọi API);
- khoá thật ⇒ vẫn hoạt động như cũ (không được siết quá tay);
- khoá thật **không bao giờ** lộ ra qua API (chỉ trả `api_key_configured`).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.api.deps import create_access_token
from src.config import Settings
from src.services.llm_providers import _env_configs
from src.services.llm_secrets import is_usable_api_key, looks_like_placeholder_key
from src.services.tts_providers import get_tts_provider, is_provider_configured, tts_catalog

#: Đúng giá trị từng nằm trong `.env.example` — thủ phạm của badge “Đã có”.
ENV_EXAMPLE_PLACEHOLDER = "sk-your-openai-or-groq-key"


class TestPlaceholderDetection:
    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            ENV_EXAMPLE_PLACEHOLDER,
            "your-key-here",
            "CHANGEME",
            "change-me",
            "placeholder",
            "dummy-key",
            "sk-example-1234",
            "<your-api-key>",
        ],
    )
    def test_gia_tri_mau_bi_coi_la_chua_co(self, value):
        assert looks_like_placeholder_key(value) is True
        assert is_usable_api_key(value) is False

    @pytest.mark.parametrize(
        "value",
        [
            "sk-proj-9f3aK2mQ7xLp1",
            "gsk_live_abc123def456",
            "sk-env-key",
            "sk-test-1234567890abcd",
            "primary-key",
        ],
    )
    def test_khoa_that_khong_bi_chan(self, value):
        """Không được siết quá tay: các khoá đang dùng trong test/hệ thống phải vẫn hợp lệ."""
        assert is_usable_api_key(value) is True
        assert looks_like_placeholder_key(value) is False


class TestTtsCatalog:
    def test_gia_tri_mau_trong_env_khong_hien_da_co(self, monkeypatch):
        """Đúng ca người dùng gặp: `.env` có giá trị mẫu ⇒ OpenAI phải hiện “Chưa có”."""
        monkeypatch.setenv("OPENAI_API_KEY", ENV_EXAMPLE_PLACEHOLDER)
        settings = Settings()
        openai = get_tts_provider("openai")
        assert openai is not None
        assert is_provider_configured(openai, settings=settings) is False
        catalog = {item["provider"]: item for item in tts_catalog(settings=settings)}
        assert catalog["openai"]["api_key_configured"] is False

    def test_khoa_that_thi_bao_da_co(self):
        settings = Settings(openai_api_key="sk-proj-9f3aK2mQ7xLp1")
        openai = get_tts_provider("openai")
        assert openai is not None
        assert is_provider_configured(openai, settings=settings) is True

    def test_browser_luon_san_sang_vi_khong_can_khoa(self):
        settings = Settings()
        browser = get_tts_provider("browser")
        assert browser is not None
        assert is_provider_configured(browser, settings=settings) is True


class TestLlmEnvConfigs:
    def test_bo_qua_khoa_mau_tu_env(self):
        """Khoá mẫu không được dựng thành nhà cung cấp, nếu không hệ thống gọi bằng khoá giả (401 khó hiểu)."""
        assert _env_configs(Settings(openai_api_key=ENV_EXAMPLE_PLACEHOLDER)) == []
        assert _env_configs(Settings(openai_api_key="")) == []

    def test_khoa_that_van_dung_binh_thuong(self):
        configs = _env_configs(Settings(openai_api_key="sk-proj-9f3aK2mQ7xLp1"))
        assert [c.provider_id for c in configs] == ["ENV-PRIMARY"]
        assert configs[0].api_key == "sk-proj-9f3aK2mQ7xLp1"

    def test_fallback_mau_bi_bo_qua_nhung_fallback_that_thi_khong(self):
        settings = Settings(
            openai_api_key="sk-proj-primary-9f3a",
            fallback_openai_api_key=ENV_EXAMPLE_PLACEHOLDER,
            fallback_model_name="gpt-4o-mini",
            fallback2_openai_api_key="sk-proj-fb2-7c1d",
            fallback2_model_name="gpt-4o-mini",
        )
        assert [c.provider_id for c in _env_configs(settings)] == ["ENV-PRIMARY", "ENV-FALLBACK-2"]


class TestApiNeverLeaksKey:
    @pytest.mark.asyncio
    async def test_settings_tts_khong_lo_khoa_va_bao_dung_trang_thai(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", ENV_EXAMPLE_PLACEHOLDER)
        headers = {"Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}"}
        res = await client.get("/api/v1/settings/tts", headers=headers)
        assert res.status_code == 200
        assert ENV_EXAMPLE_PLACEHOLDER not in res.text
        assert '"api_key"' not in res.text
        catalog = {item["provider"]: item for item in res.json()["catalog"]}
        assert catalog["openai"]["api_key_configured"] is False, "giá trị mẫu không được tính là khoá"
        assert catalog["browser"]["api_key_configured"] is True
