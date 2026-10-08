"""Endpoint nghe-nói `POST /api/v1/stt/transcribe` + cổng quản trị cấu hình nhà cung cấp.

Chốt bằng test những luật đã hứa với người dùng (2026-10-08):

1. Bắt buộc phiên nhân viên — không ai gửi audio lên máy chủ mà không đăng nhập (401).
2. Chưa cấu hình nhà cung cấp nào → **503 kèm chỉ dẫn dán khoá Groq**, và báo luôn còn lưới an toàn
   Web Speech API phía trình duyệt không, để UI biết đường mà dùng (không im lặng, không "hệ thống lỗi").
3. Chặn đúng loại lỗi đầu vào: sai kiểu file 415 · file rỗng 422 · quá dung lượng 413 · hết hạn mức 429.
4. Cấu hình nhà cung cấp là việc ADMIN: Sale gọi → 403; khoá dán vào DB được **mã hoá** và API chỉ trả dạng che.
5. Không gọi mạng thật trong test: tầng gọi nhà cung cấp bị thay bằng hàm giả.
"""

from __future__ import annotations

import pytest

from src.api.endpoints import stt as stt_endpoints
from src.config import Settings
from src.db.models import STTProviderModel
from src.services import stt_providers as sp
from src.services.stt_providers import SttResult
from tests.conftest import async_test_session_factory

SALE = ("SALES-001", "SALE")
ADMIN = ("ADMIN-001", "ADMIN")


def _headers(actor: tuple[str, str] | None) -> dict[str, str]:
    if actor is None:
        return {}
    user_id, role = actor
    return {"Authorization": f"Bearer {user_id}", "X-User-Id": user_id, "X-User-Role": role}


def _settings(**overrides) -> Settings:
    base = {
        "stt_enabled": True,
        "stt_provider": "groq",
        "stt_groq_api_key": "",
        "stt_model": "whisper-large-v3-turbo",
        "stt_language": "vi",
        "stt_daily_minutes_budget": 60,
        "stt_max_bytes": 10_000_000,
        "stt_max_duration_seconds": 120,
        "stt_request_timeout_seconds": 5.0,
        "stt_zero_data_retention": False,
        "openai_api_key": "",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Không để test chạm mạng/ghi sổ thật, và cấu hình DB ca này không lẫn sang ca khác."""
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "usage.jsonl"))
    sp.set_stt_provider_rows(None)
    sp._PLAIN_KEYS.clear()
    monkeypatch.setattr(stt_endpoints, "get_settings", lambda: _settings())
    yield
    sp.set_stt_provider_rows(None)
    sp._PLAIN_KEYS.clear()


def _audio(size: int = 32_000, content_type: str = "audio/webm") -> dict:
    return {"files": {"file": ("clip.webm", b"a" * size, content_type)}}


async def _post(client, *, headers=None, size: int = 32_000, content_type: str = "audio/webm"):
    return await client.post("/api/v1/stt/transcribe", headers=_headers(headers), **_audio(size, content_type))


# --------------------------------------------------------------------------- #
# Quyền + cấu hình
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chua_dang_nhap_thi_khong_gui_duoc_audio(client) -> None:
    response = await _post(client, headers=None)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chua_cau_hinh_nha_cung_cap_thi_bao_503_kem_chi_dan(client) -> None:
    response = await _post(client, headers=SALE)
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "Groq" in detail and "STT_GROQ_API_KEY" in detail, "phải chỉ rõ ADMIN cần làm gì"


@pytest.mark.asyncio
async def test_health_mo_cho_nhan_vien_va_bao_trang_thai_chuoi(client) -> None:
    assert (await client.get("/api/v1/stt/health")).status_code == 401

    response = await client.get("/api/v1/stt/health", headers=_headers(SALE))
    assert response.status_code == 200
    body = response.json()
    assert body["preferred"] == "groq"
    assert {item["provider"] for item in body["chain"]} >= {"groq", "openai", "browser"}
    assert body["browser_fallback"] is True, "UI cần biết còn lưới an toàn Web Speech API"
    assert body["limits"]["max_duration_seconds"] == 120
    assert body["quota"]["daily_budget_minutes"] == 60


# --------------------------------------------------------------------------- #
# Chặn lỗi đầu vào
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tu_choi_kieu_file_khong_phai_audio(client) -> None:
    response = await _post(client, headers=SALE, content_type="text/plain")
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_file_rong_thi_bao_422(client) -> None:
    response = await _post(client, headers=SALE, size=0)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_vuot_tran_dung_luong_thi_bao_413(client, monkeypatch) -> None:
    """Đọc theo khúc và dừng ngay khi vượt trần — không nạp cả file vào RAM."""
    monkeypatch.setattr(stt_endpoints, "get_settings", lambda: _settings(stt_max_bytes=1_000))
    response = await _post(client, headers=SALE, size=5_000)
    assert response.status_code == 413
    assert "MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_het_han_muc_phut_trong_ngay_thi_bao_429(client, monkeypatch) -> None:
    monkeypatch.setattr(stt_endpoints, "quota_exceeded", lambda **_: True)
    response = await _post(client, headers=SALE)
    assert response.status_code == 429
    assert "hạn mức" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stt_bi_tat_thi_bao_503(client, monkeypatch) -> None:
    monkeypatch.setattr(stt_endpoints, "get_settings", lambda: _settings(stt_enabled=False))
    response = await _post(client, headers=SALE)
    assert response.status_code == 503
    assert "STT_ENABLED" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Đường hạnh phúc (nhà cung cấp bị giả lập)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_transcribe_tra_ve_chu_da_chuan_hoa_thuat_ngu(client, monkeypatch) -> None:
    """ASR chỉ là "bàn phím bằng giọng nói": endpoint trả CHỮ, không đụng luồng Copilot."""
    captured: dict = {}

    async def fake_transcribe(audio, **kwargs):
        captured.update(kwargs)
        return SttResult(
            text="Khách hỏi căn zen a 1205, kpbt bao nhiêu",
            normalized_text="Khách hỏi căn ZEN-A-1205, KPBT bao nhiêu",
            language="vi",
            provider="groq",
            model="whisper-large-v3-turbo",
            latency_ms=412.7,
            audio_bytes=len(audio),
            attempts=[{"provider": "groq", "label": "Groq Whisper (LPU)", "ok": True, "latency_ms": 412.7}],
            warnings=[],
        )

    monkeypatch.setattr(stt_endpoints, "transcribe_with_fallback", fake_transcribe)
    response = await _post(client, headers=SALE)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "Khách hỏi căn zen a 1205, kpbt bao nhiêu"
    assert body["normalized_text"] == "Khách hỏi căn ZEN-A-1205, KPBT bao nhiêu"
    assert body["provider"] == "groq" and body["language"] == "vi"
    assert body["audio_bytes"] > 0 and body["estimated_seconds"] > 0
    assert body["quota"]["daily_budget_minutes"] == 60
    assert body["fallback_used"] is False
    # Từ vựng mồi phải được gửi kèm để Whisper không đoán sai mã căn.
    assert "ZEN-A-1205" in captured["prompt"]
    assert captured["user_id"] == SALE[0]


@pytest.mark.asyncio
async def test_transcript_rong_thi_nhac_sale_noi_lai(client, monkeypatch) -> None:
    async def fake_transcribe(audio, **kwargs):
        return SttResult(
            text="", normalized_text="", language="vi", provider="groq", model="m",
            latency_ms=10.0, audio_bytes=len(audio), attempts=[{"provider": "groq", "ok": True}], warnings=[],
        )

    monkeypatch.setattr(stt_endpoints, "transcribe_with_fallback", fake_transcribe)
    body = (await _post(client, headers=SALE)).json()
    assert body["text"] == ""
    assert any("nói lại" in w for w in body["warnings"]), "không được im lặng khi máy không nghe thấy gì"


# --------------------------------------------------------------------------- #
# Cổng quản trị: khai báo nhà cung cấp trong DB (DB đè .env)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_sale_khong_duoc_cau_hinh_nha_cung_cap(client) -> None:
    response = await client.put(
        "/api/v1/stt/providers/groq",
        json={"api_key": "gsk_lay_duoc_dau"},
        headers=_headers(SALE),
    )
    assert response.status_code == 403
    assert (await client.get("/api/v1/stt/providers", headers=_headers(SALE))).status_code == 403


@pytest.mark.asyncio
async def test_admin_dan_khoa_thi_luu_ma_hoa_va_de_env(client, monkeypatch) -> None:
    """Người dùng chốt: "khai báo riêng 1 key Groq, trong env và trong db luôn cũng được" → DB phải đè ENV."""
    monkeypatch.setattr(stt_endpoints, "get_settings", lambda: _settings(stt_groq_api_key="khoa-tu-env"))

    response = await client.put(
        "/api/v1/stt/providers/groq",
        json={"api_key": "gsk_khoa_dan_trong_app", "model": "whisper-large-v3", "zero_data_retention": True},
        headers=_headers(ADMIN),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "groq" and body["has_api_key"] is True
    assert "gsk_khoa_dan_trong_app" not in response.text, "không bao giờ trả khoá thật ra API"
    assert body["api_key_masked"] and body["api_key_masked"] != "gsk_khoa_dan_trong_app"
    assert body["zero_data_retention"] is True

    async with async_test_session_factory() as session:
        from sqlalchemy import select

        row = (await session.execute(select(STTProviderModel))).scalars().first()
        assert row is not None and row.provider == "groq"
        assert row.api_key_encrypted.startswith("enc::"), "khoá phải lưu mã hoá Fernet"
        assert row.default_model == "whisper-large-v3"

    # Khoá DB thắng khoá ENV.
    cfg = sp.get_stt_provider("groq")
    assert sp.resolve_provider_api_key(cfg, settings=_settings(stt_groq_api_key="khoa-tu-env")) == "gsk_khoa_dan_trong_app"

    listing = await client.get("/api/v1/stt/providers", headers=_headers(ADMIN))
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["db_overrides"] == ["groq"]
    assert "groq" in payload["effective_chain"]


@pytest.mark.asyncio
async def test_xoa_ban_ghi_db_thi_tro_ve_cau_hinh_env(client, monkeypatch) -> None:
    monkeypatch.setattr(stt_endpoints, "get_settings", lambda: _settings(stt_groq_api_key="khoa-tu-env"))
    await client.put("/api/v1/stt/providers/groq", json={"api_key": "gsk_db"}, headers=_headers(ADMIN))

    deleted = await client.delete("/api/v1/stt/providers/groq", headers=_headers(ADMIN))
    assert deleted.status_code == 200
    again = await client.delete("/api/v1/stt/providers/groq", headers=_headers(ADMIN))
    assert again.status_code == 404

    cfg = sp.get_stt_provider("groq")
    assert sp.resolve_provider_api_key(cfg, settings=_settings(stt_groq_api_key="khoa-tu-env")) == "khoa-tu-env"


@pytest.mark.asyncio
async def test_nut_test_cua_admin_khong_can_thu_am(client, monkeypatch) -> None:
    """Gửi 1 giây im lặng để kiểm tra khoá/URL/model; kết quả được ghi lại trên bản ghi DB."""
    await client.put("/api/v1/stt/providers/groq", json={"api_key": "gsk_db"}, headers=_headers(ADMIN))

    async def fake_probe(provider, **kwargs):
        return {"provider": provider, "ok": True, "latency_ms": 321.0, "detail": "Khoá và model hợp lệ."}

    monkeypatch.setattr(stt_endpoints, "probe_provider", fake_probe)
    response = await client.post("/api/v1/stt/providers/groq/test", headers=_headers(ADMIN))
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["tested_by"] == ADMIN[0]

    async with async_test_session_factory() as session:
        from sqlalchemy import select

        row = (await session.execute(select(STTProviderModel).where(STTProviderModel.provider == "groq"))).scalars().first()
        assert row.last_test_status == "ok"
        assert row.last_test_latency_ms == 321.0
