"""Kiểm tra kết nối nhà cung cấp LLM: phải chịu được Cloudflare và báo lỗi đọc được.

Bối cảnh thật: Admin bấm "Test kết nối" và nhận `HTTP 403` kèm trang `"Just a moment..."` của Cloudflare,
dù API vẫn dùng tốt từ ứng dụng khác. Nguyên nhân: bản cũ gọi `GET /models` bằng httpx mặc định
(`User-Agent: python-httpx/...`) — Cloudflare chặn client không khai báo/bị coi là bot. Test này dựng một
server giả **đóng đúng hành vi đó** để khoá lại cách xử lý:

1. `/models` bị Cloudflare chặn nhưng `/chat/completions` chạy → phải kết luận **OK** qua đường chat.
2. Cloudflare chặn cả hai → phải trả câu chẩn đoán nói rõ Cloudflare, **không** đổ HTML thô.
3. Server bình thường → OK qua `/models` như trước.
4. Sai base URL (trả HTML trang chủ) → nhắc nghi thiếu `/v1`.
5. Khoá sai (401 JSON) → nói rõ khoá bị từ chối.
"""

from __future__ import annotations

import pytest

from src.services.llm_probe import USER_AGENT, probe_llm_provider


@pytest.mark.asyncio
async def test_cloudflare_chan_models_nhung_chat_chay_thi_van_ket_luan_ok(provider_server) -> None:
    """Đúng ca người dùng gặp: /models bị Cloudflare chặn, nhưng API thật vẫn dùng được."""
    base, _ = provider_server("cloudflare-models-only")
    result = await probe_llm_provider(base, "sk-test", "gpt-4o-mini")
    assert result.ok is True, result.detail
    assert result.status == "OK"
    assert result.method == "POST /chat/completions"
    assert "chat/completions" in result.detail
    # Phải nói rõ vì sao /models không dùng được để Admin biết chuyện gì đang xảy ra.
    assert "Cloudflare" in result.detail


@pytest.mark.asyncio
async def test_cloudflare_chan_ca_hai_thi_bao_loi_doc_duoc_khong_do_html(provider_server) -> None:
    base, _ = provider_server("cloudflare-both")
    result = await probe_llm_provider(base, "sk-test", "gpt-4o-mini")
    assert result.ok is False
    assert result.status == "ERROR"
    assert "Cloudflare" in result.detail
    assert "Just a moment" in result.detail
    # Không được đổ HTML thô vào màn hình Admin.
    assert "<!DOCTYPE" not in result.detail
    assert "<html" not in result.detail
    # Có gợi ý việc cần kiểm tra: URL API (/v1) và chính sách chặn bot của nhà cung cấp.
    assert "/v1" in result.detail
    assert "allowlist" in result.detail


@pytest.mark.asyncio
async def test_server_binh_thuong_thi_van_dung_models(provider_server) -> None:
    base, _ = provider_server("ok")
    result = await probe_llm_provider(base, "sk-test", "gpt-4o-mini")
    assert result.ok is True
    assert result.method == "GET /models"
    assert "2 model" in result.detail


@pytest.mark.asyncio
async def test_gui_user_agent_ro_rang_khong_phai_mac_dinh_cua_httpx(provider_server) -> None:
    """Nguyên nhân gốc của lỗi 403: UA mặc định của httpx bị Cloudflare chặn."""
    base, user_agents = provider_server("ok")
    await probe_llm_provider(base, "sk-test", "gpt-4o-mini")
    assert user_agents, "server giả không nhận được request nào"
    assert all(ua == USER_AGENT for ua in user_agents), user_agents
    assert "python-httpx" not in user_agents[0]


@pytest.mark.asyncio
async def test_base_url_tro_vao_trang_chu_thi_nhac_thieu_v1(provider_server) -> None:
    base, _ = provider_server("homepage")
    result = await probe_llm_provider(base, "sk-test", "gpt-4o-mini")
    assert result.ok is False
    assert "HTML" in result.detail
    assert "/v1" in result.detail
    assert "<html" not in result.detail


@pytest.mark.asyncio
async def test_base_url_thieu_v1_thi_chi_duoc_cach_sua(provider_server) -> None:
    """Ca rất hay gặp: app khác dùng đúng `/v1` nên chạy, còn Base URL đã lưu thì thiếu `/v1`."""
    base_with_v1, _ = provider_server("missing-v1")
    base_without_v1 = base_with_v1.rsplit("/v1", 1)[0]
    result = await probe_llm_provider(base_without_v1, "sk-test", "gpt-4o-mini")
    assert result.ok is False  # cấu hình ĐANG SAI → không được báo xanh
    assert f"{base_without_v1}/v1" in result.detail
    assert "Sửa Base URL" in result.detail


@pytest.mark.asyncio
async def test_khoa_sai_thi_noi_ro_bi_tu_choi(provider_server) -> None:
    base, _ = provider_server("bad-key")
    result = await probe_llm_provider(base, "sk-sai", "gpt-4o-mini")
    assert result.ok is False
    assert "401" in result.detail


@pytest.mark.asyncio
async def test_chua_co_khoa_thi_bao_not_configured() -> None:
    result = await probe_llm_provider("https://api.openai.com/v1", None)
    assert result.ok is False
    assert result.status == "NOT_CONFIGURED"
    assert "API key" in result.detail
