"""Tầng nhà cung cấp Speech-to-Text (`src/services/stt_providers.py`).

Chốt bốn điều người dùng đã quyết cho luồng Sale nói → Copilot:

1. Khoá khai báo được ở **CẢ HAI nơi**: DB (ADMIN dán trong app, lưu mã hoá) được ƯU TIÊN, `.env` dự phòng.
2. Chuỗi fallback theo `priority`, mắt xích hỏng thì đi tiếp; cuối cùng còn `browser` (Web Speech API)
   nên hết quota Groq giữa demo thì Sale vẫn nói được.
3. **Hạn mức phút audio/ngày** chặn được — không âm thầm đốt tiền khi chạm trần gói free.
4. Transcript đi qua lớp chuẩn hoá tất định: mã căn sai một ký tự là Copilot tra sai căn, nên "ZEN A 1205"
   phải thành "ZEN-A-1205" — nhưng KHÔNG được sửa nhầm câu chữ bình thường.

Không gọi mạng thật trong bộ test này: `_post_openai_compatible` bị thay bằng hàm giả.
"""

from __future__ import annotations

import io
import wave

import pytest

from src.config import Settings
from src.services import stt_providers as sp
from src.services.stt_providers import (
    BROWSER_PROVIDER,
    SttError,
    estimate_audio_seconds,
    get_stt_provider,
    is_provider_configured,
    normalize_transcript,
    resolve_provider_api_key,
    resolve_stt_providers,
    set_stt_provider_rows,
    silent_wav,
    stt_health_report,
    transcribe_chain,
    transcribe_with_fallback,
)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    """Sổ chi phí riêng cho từng ca + xoá cache cấu hình DB để ca này không dính ca kia."""
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "usage.jsonl"))
    set_stt_provider_rows(None)
    sp._PLAIN_KEYS.clear()
    yield
    set_stt_provider_rows(None)
    sp._PLAIN_KEYS.clear()


def _settings(**overrides) -> Settings:
    base = {
        "stt_enabled": True,
        "stt_provider": "groq",
        "stt_groq_api_key": "",
        "stt_model": "whisper-large-v3-turbo",
        "stt_language": "vi",
        "stt_daily_minutes_budget": 60,
        "stt_max_bytes": 10_000_000,
        "stt_request_timeout_seconds": 5.0,
        "stt_zero_data_retention": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


# --------------------------------------------------------------------------- #
# Chuẩn hoá transcript
# --------------------------------------------------------------------------- #


def test_chuan_hoa_ma_can_va_thuat_ngu() -> None:
    assert normalize_transcript("xem căn ZEN A 1205 giá bao nhiêu") == "xem căn ZEN-A-1205 giá bao nhiêu"
    assert normalize_transcript("Khách hỏi kpbt") == "Khách hỏi KPBT"
    assert normalize_transcript("3 phẩy 864 tỷ") == "3,864 tỷ"
    assert normalize_transcript("vốn tự có 1 chấm 5 tỷ") == "vốn tự có 1,5 tỷ"
    assert normalize_transcript("") == ""


def test_chuan_hoa_khong_sua_nham_cau_binh_thuong() -> None:
    """Số điện thoại / câu chữ thường không bị biến thành mã căn."""
    for text in (
        "gọi cho anh Ba 1234 giúp chị",
        "khách muốn 2 phòng ngủ, hướng Đông Nam",
        "số điện thoại 0901234567",
        "The Zen Park còn căn nào không",
    ):
        assert normalize_transcript(text) == text


# --------------------------------------------------------------------------- #
# Danh mục + khoá (DB đè ENV)
# --------------------------------------------------------------------------- #


def test_danh_muc_mac_dinh_groq_dau_chuoi() -> None:
    providers = resolve_stt_providers(include_inactive=True)
    codes = [cfg.provider for cfg in providers]
    assert codes[0] == "groq", "Groq phải đứng đầu vì có gói free và Whisper chạy LPU rất nhanh"
    assert BROWSER_PROVIDER in codes
    assert get_stt_provider(BROWSER_PROVIDER).mode == "browser"


def test_khoa_env_dang_placeholder_khong_duoc_tinh_la_da_cau_hinh() -> None:
    """Giá trị mẫu trong `.env.example` từng khiến hệ thống tưởng "đã có khoá" — phải chặn."""
    for fake in ("", "sk-your-groq-key", "changeme", "todo"):
        settings = _settings(stt_groq_api_key=fake)
        assert is_provider_configured(get_stt_provider("groq"), settings=settings) is False
    real = _settings(stt_groq_api_key="gsk_that_123")
    assert is_provider_configured(get_stt_provider("groq"), settings=real) is True


def test_khoa_trong_db_duoc_uu_tien_hon_env() -> None:
    settings = _settings(stt_groq_api_key="khoa-tu-env")
    set_stt_provider_rows(
        [
            {
                "provider_id": "STT-1",
                "provider": "groq",
                "label": "Groq (DB)",
                "mode": "api",
                "base_url": "",
                "default_model": "whisper-large-v3",
                "env_key": "",
                "language": "vi",
                "price_per_hour_audio": 0.0,
                "currency": "USD",
                "note": "",
                "priority": 5,
                "is_active": True,
                "zero_data_retention": True,
                "prompt_bias": "",
                "api_key_masked": "gsk…_db",
                "has_api_key": True,
                "api_key_plain": "khoa-tu-db",
            }
        ]
    )
    cfg = get_stt_provider("groq")
    assert resolve_provider_api_key(cfg, settings=settings) == "khoa-tu-db"
    assert cfg.default_model == "whisper-large-v3", "Bản ghi DB phải đè model của danh mục"
    assert cfg.zero_data_retention is True
    health = stt_health_report(settings=settings)
    groq = next(item for item in health["chain"] if item["provider"] == "groq")
    assert groq["key_source"] == "db"


def test_chuoi_fallback_bo_mat_xich_chua_cau_hinh() -> None:
    """Chưa có khoá Groq nhưng có khoá OpenAI ⇒ chuỗi chỉ còn OpenAI; browser luôn là lưới an toàn."""
    settings = _settings(stt_groq_api_key="", openai_api_key="sk-openai-that")
    chain = [cfg.provider for cfg in transcribe_chain(settings=settings)]
    assert chain == ["openai"]
    assert sp.browser_fallback_available() is True


# --------------------------------------------------------------------------- #
# Gọi nhà cung cấp (giả lập, không ra mạng)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_transcribe_roi_sang_mat_xich_ke_khi_groq_loi(monkeypatch) -> None:
    settings = _settings(stt_groq_api_key="gsk_that", openai_api_key="sk-openai-that")
    calls: list[str] = []

    async def fake_post(cfg, api_key, audio, **kwargs):
        calls.append(cfg.provider)
        if cfg.provider == "groq":
            raise SttError(400, "STT_PROVIDER_ERROR", "Groq từ chối (429): hết hạn mức free")
        return "Khách hỏi căn zen a 1205", "vi"

    monkeypatch.setattr(sp, "_post_openai_compatible", fake_post)
    result = await transcribe_with_fallback(b"audio-gia", settings=settings, user_id="SALES-001")

    assert calls == ["groq", "openai"], "phải thử đúng thứ tự ưu tiên"
    assert result.provider == "openai"
    assert result.text == "Khách hỏi căn zen a 1205"
    assert result.normalized_text == "Khách hỏi căn ZEN-A-1205"
    assert [a["ok"] for a in result.attempts] == [False, True]


@pytest.mark.asyncio
async def test_chua_cau_hinh_thi_bao_503_va_chi_duong_fallback(monkeypatch) -> None:
    settings = _settings(stt_groq_api_key="", openai_api_key="")
    with pytest.raises(SttError) as exc:
        await transcribe_with_fallback(b"audio-gia", settings=settings)
    assert exc.value.code == "STT_NOT_CONFIGURED"
    assert exc.value.http_status == 503
    assert exc.value.details["browser_fallback"] is True
    assert "Groq" in exc.value.message, "thông báo phải chỉ rõ cách khắc phục cho ADMIN"


@pytest.mark.asyncio
async def test_moi_nha_cung_cap_deu_loi_thi_bao_502(monkeypatch) -> None:
    settings = _settings(stt_groq_api_key="gsk_that")

    async def fake_post(cfg, api_key, audio, **kwargs):
        raise SttError(502, "STT_PROVIDER_ERROR", "Groq sập")

    monkeypatch.setattr(sp, "_post_openai_compatible", fake_post)
    with pytest.raises(SttError) as exc:
        await transcribe_with_fallback(b"audio-gia", settings=settings)
    assert exc.value.code == "ALL_PROVIDERS_FAILED"


# --------------------------------------------------------------------------- #
# Hạn mức + công cụ kiểm tra
# --------------------------------------------------------------------------- #


def test_han_muc_phut_audio_chan_duoc() -> None:
    settings = _settings(stt_daily_minutes_budget=1)
    assert sp.quota_exceeded(settings=settings) is False
    # 60 giây audio ≈ 240 KB opus 32 kbps → ghi sổ đúng số giây ước tính.
    audio = b"x" * 240_000
    assert estimate_audio_seconds(len(audio)) == 60.0
    sp._record_usage(cfg=get_stt_provider("groq"), model="whisper-large-v3-turbo", audio_bytes=len(audio),
                     latency_ms=120.0, ok=True, user_id="SALES-001")
    assert sp.audio_seconds_today(settings=settings) == 60
    assert sp.quota_exceeded(settings=settings) is True
    assert sp.quota_report(settings=settings)["remaining_minutes"] == 0


def test_luot_loi_khong_tinh_vao_han_muc() -> None:
    settings = _settings(stt_daily_minutes_budget=5)
    sp._record_usage(cfg=get_stt_provider("groq"), model="m", audio_bytes=400_000, latency_ms=0.0, ok=False, error="boom")
    assert sp.audio_seconds_today(settings=settings) == 0


def test_silent_wav_doc_duoc_bang_thu_vien_chuan() -> None:
    """File 1 giây im lặng dùng cho nút "Test" của ADMIN và script kiểm tra trên VM — phải là WAV hợp lệ."""
    audio = silent_wav(1.0, rate=16_000)
    with wave.open(io.BytesIO(audio), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnframes() == 16_000


def test_health_bao_dong_khi_chua_bat_zdr_ben_groq() -> None:
    """Groq không có tham số ZDR theo request ⇒ hệ thống phải NHẮC bật ở Console, không được im lặng."""
    configured = _settings(stt_groq_api_key="gsk_that", stt_zero_data_retention=False)
    report = stt_health_report(settings=configured)
    assert any("Zero Data Retention" in w for w in report["warnings"])
    assert report["limits"]["max_bytes"] == configured.stt_max_bytes
    assert "audio/webm" in report["limits"]["accepted_content_types"]

    not_configured = _settings(stt_groq_api_key="")
    assert any("chưa cấu hình" in w.lower() or "Chưa có nhà cung cấp" in w for w in stt_health_report(settings=not_configured)["warnings"])
