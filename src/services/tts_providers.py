"""Danh mục nhà cung cấp Text-to-Speech (TTS) + quy đổi chi phí đọc câu trả lời.

Vì sao có module này: Sale cần **nghe** câu trả lời của Copilot (đang lái xe / đang đứng cạnh khách),
nhưng nếu để trình duyệt tự đọc thì giọng tuỳ máy, không đo được chi phí, không đồng bộ giữa 20k
nhân viên. Module này là **một nguồn sự thật** cho: chọn nhà cung cấp, mã giọng tiếng Việt, đơn giá
và công thức quy chi phí — chạy ở cả chế độ "đọc tại trình duyệt" (0 đồng) và "gọi API TTS" (có phí).

Nguyên tắc kế thừa từ phần LLM (`llm_providers.py` / `llm_usage.py`):

- Khoá API **không** lưu ở đây; chúng đọc từ ENV (thiết kế hiện tại) — DB/UI chỉ ghi *chọn* provider
  và giọng. Khi nối vào `llm_providers`-style CRUD thì phần khoá dùng lại nguyên cơ chế Fernet.
- Đơn giá là **giá niêm yết tham khảo** do nhà cung cấp công bố, có `verified_at` để biết số liệu cũ
  tới đâu. Không dùng con số này để quyết toán nếu chưa đối chiếu hoá đơn thật.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import Settings, get_settings
from src.services.llm_secrets import is_usable_api_key

#: Giọng đọc mặc định khi Admin chưa chọn gì — 0 đồng, chạy ngay trong trình duyệt.
BROWSER_PROVIDER = "browser"


@dataclass(frozen=True)
class TtsVoice:
    """Một mã giọng gợi ý kèm mô tả để người dùng không phải đoán."""

    code: str
    label: str
    gender: str = "neutral"


@dataclass(frozen=True)
class TtsProviderConfig:
    """Nhà cung cấp TTS — thông tin để UI hiển thị và để tính chi phí."""

    provider: str
    label: str
    mode: str  # browser | api
    env_key: str
    base_url: str = ""
    default_model: str = ""
    #: Đơn giá theo 1 triệu ký tự; 0 nghĩa là không phát sinh chi phí.
    price_per_1m_chars: float = 0.0
    currency: str = "USD"
    #: Mốc kiểm chứng giá — giá niêm yết đổi theo thời gian, UI phải hiện để không gây hiểu nhầm.
    verified_at: str = ""
    price_note: str = ""
    voices: tuple[TtsVoice, ...] = field(default_factory=tuple)
    supports_streaming: bool = False
    voice_cloning: bool = False
    note: str = ""


#: Danh mục tham khảo (giá niêm yết công bố trên trang giá của nhà cung cấp).
#: VNĐ/triệu ký tự tính theo gói bán lẻ phổ biến — bắt buộc đối chiếu lại khi ký hợp đồng.
TTS_PROVIDER_CATALOG: tuple[TtsProviderConfig, ...] = (
    TtsProviderConfig(
        provider=BROWSER_PROVIDER,
        label="Trình duyệt (Web Speech API)",
        mode="browser",
        env_key="",
        verified_at="2026-10-02",
        voices=(
            TtsVoice("vi-VN", "Giọng tiếng Việt của hệ điều hành", "neutral"),
        ),
        note="Miễn phí, không cần khoá, có ngay trong demo. Đổi máy/đổi trình duyệt là đổi giọng, "
        "và không chạy khi máy không có giọng tiếng Việt.",
    ),
    TtsProviderConfig(
        provider="openai",
        label="OpenAI TTS",
        mode="api",
        env_key="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        default_model="tts-1",
        price_per_1m_chars=15.0,
        currency="USD",
        verified_at="2026-10-02",
        price_note="tts-1: 15 USD/1M ký tự; tts-1-hd: 30 USD/1M; gpt-4o-mini-tts tính theo token audio.",
        voices=(
            TtsVoice("alloy", "Alloy — trung tính, dùng chung"),
            TtsVoice("nova", "Nova — nữ, rõ chữ"),
            TtsVoice("onyx", "Onyx — nam, trầm"),
            TtsVoice("shimmer", "Shimmer — nữ, mềm"),
        ),
        supports_streaming=True,
        note="Dùng chung khoá với LLM đang cấu hình; hỗ trợ streaming nên đọc được khi câu trả lời còn dài.",
    ),
    TtsProviderConfig(
        provider="google_cloud",
        label="Google Cloud TTS",
        mode="api",
        env_key="GOOGLE_APPLICATION_CREDENTIALS",
        base_url="https://texttospeech.googleapis.com/v1",
        default_model="vi-VN-Wavenet-A",
        price_per_1m_chars=4.0,
        currency="USD",
        verified_at="2026-10-02",
        price_note="Standard/WaveNet 4 USD/1M ký tự (miễn phí 4M/tháng); Neural2 16 USD/1M (miễn phí 1M/tháng).",
        voices=(
            TtsVoice("vi-VN-Wavenet-A", "vi-VN WaveNet A — nữ", "female"),
            TtsVoice("vi-VN-Wavenet-B", "vi-VN WaveNet B — nam", "male"),
            TtsVoice("vi-VN-Neural2-A", "vi-VN Neural2 A — nữ (nét hơn)", "female"),
        ),
        supports_streaming=True,
        note="Có giọng tiếng Việt chính thức + hạn mức miễn phí hằng tháng, hợp cho bản triển khai đầu.",
    ),
    TtsProviderConfig(
        provider="azure",
        label="Azure AI Speech",
        mode="api",
        env_key="AZURE_SPEECH_KEY",
        base_url="https://{region}.tts.speech.microsoft.com",
        default_model="vi-VN-HoaiMyNeural",
        price_per_1m_chars=16.0,
        currency="USD",
        verified_at="2026-10-02",
        price_note="Neural 16 USD/1M ký tự (bậc thấp nhất); có giảm giá theo cam kết khối lượng.",
        voices=(
            TtsVoice("vi-VN-HoaiMyNeural", "HoaiMy — nữ miền Nam", "female"),
            TtsVoice("vi-VN-NamMinhNeural", "NamMinh — nam miền Bắc", "male"),
        ),
        supports_streaming=True,
        voice_cloning=True,
        note="Hai giọng tiếng Việt ổn định; có SSML để ngắt nghỉ theo câu.",
    ),
    TtsProviderConfig(
        provider="viettel",
        label="Viettel AI TTS",
        mode="api",
        env_key="VIETTEL_TTS_TOKEN",
        base_url="https://viettelai.vn/tts",
        default_model="viettel-tts",
        price_per_1m_chars=320_000.0,
        currency="VND",
        verified_at="2022-12-26",
        price_note="Bảng giá công bố: 320.000 VNĐ/1M ký tự (không thuê bao); có gói thuê bao rẻ hơn.",
        voices=(
            TtsVoice("hn_female_ngochuyen", "Nữ Hà Nội", "female"),
            TtsVoice("hn_male_manhdung", "Nam Hà Nội", "male"),
            TtsVoice("sg_female_thaotrinh", "Nữ Sài Gòn", "female"),
        ),
        note="Nhà cung cấp trong nước: dữ liệu không ra ngoài, bảng giá bằng VNĐ, hỗ trợ tiếng Việt tốt. "
        "Giá niêm yết trong tài liệu cũ — cần xác nhận lại trước khi quyết toán.",
    ),
    TtsProviderConfig(
        provider="vbee",
        label="Vbee AIVoice",
        mode="api",
        env_key="VBEE_TOKEN",
        base_url="https://api.vbee.vn",
        default_model="vbee-aivoice",
        price_per_1m_chars=598_000.0,
        currency="VND",
        verified_at="2026-02-23",
        price_note="Tính theo gói ký tự (tham khảo 149.000đ/125k ký tự ≈ 1.192.000đ/1M; gói VIP 299.000đ/500k ≈ 598.000đ/1M).",
        voices=(
            TtsVoice("hn-quynhanh", "Quỳnh Anh — nữ Bắc", "female"),
            TtsVoice("hue-baoquoc", "Bảo Quốc — nam miền Trung", "male"),
            TtsVoice("sg-thuydung", "Thuỳ Dung — nữ Nam", "female"),
        ),
        voice_cloning=True,
        note="Mạnh về giọng tiếng Việt 3 miền và có nhân bản giọng; giá theo gói nên phải quy đổi theo ký tự thực dùng.",
    ),
    TtsProviderConfig(
        provider="fpt",
        label="FPT.AI Voice",
        mode="api",
        env_key="FPT_TTS_API_KEY",
        base_url="https://api.fpt.ai/hmi/tts/v5",
        default_model="fpt-tts",
        price_per_1m_chars=333_333.0,
        currency="VND",
        verified_at="2026-02-23",
        price_note="Tham khảo từ 500.000đ cho 1,5 triệu ký tự ≈ 333.333đ/1M (tuỳ gói).",
        voices=(
            TtsVoice("banmai", "Ban Mai — nữ", "female"),
            TtsVoice("lannhi", "Lan Nhi — nữ", "female"),
            TtsVoice("leminh", "Lê Minh — nam", "male"),
        ),
        note="Phổ biến ở Việt Nam, dễ ký hợp đồng nội địa; chất lượng tuỳ giọng.",
    ),
)

_BY_PROVIDER = {cfg.provider: cfg for cfg in TTS_PROVIDER_CATALOG}

#: Chặn trên số ký tự đọc mỗi lượt — câu trả lời dài mà đọc hết vừa lâu vừa tốn tiền.
DEFAULT_MAX_CHARS_PER_TURN = 600


def get_tts_provider(provider: str | None) -> TtsProviderConfig | None:
    """Tra cứu nhà cung cấp TTS theo mã (không phân biệt hoa/thường)."""
    if not provider:
        return None
    return _BY_PROVIDER.get(provider.strip().lower())


def tts_catalog(*, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Danh mục cho UI: giá, giọng gợi ý, và **đã có khoá để gọi chưa** (không lộ khoá)."""
    resolved = settings or get_settings()
    items: list[dict[str, Any]] = []
    for cfg in TTS_PROVIDER_CATALOG:
        items.append(
            {
                "provider": cfg.provider,
                "label": cfg.label,
                "mode": cfg.mode,
                "default_model": cfg.default_model,
                "price_per_1m_chars": cfg.price_per_1m_chars,
                "currency": cfg.currency,
                "price_note": cfg.price_note,
                "verified_at": cfg.verified_at,
                "supports_streaming": cfg.supports_streaming,
                "voice_cloning": cfg.voice_cloning,
                "note": cfg.note,
                # Chỉ trả về CÓ/KHÔNG, không bao giờ trả chính khoá.
                "api_key_configured": is_provider_configured(cfg, settings=resolved),
                "voices": [{"code": v.code, "label": v.label, "gender": v.gender} for v in cfg.voices],
            }
        )
    return items


def is_provider_configured(cfg: TtsProviderConfig, *, settings: Settings | None = None) -> bool:
    """Nhà cung cấp đã có khoá chưa — kiểm tra cả trường Settings lẫn biến môi trường thô.

    Vì sao hai đường: `OPENAI_API_KEY` được Settings map thành `openai_api_key`, còn
    `GOOGLE_APPLICATION_CREDENTIALS` là đường dẫn file, Settings không khai báo → phải đọc ENV trực tiếp.
    """
    if not cfg.env_key:
        return True  # chế độ trình duyệt: không cần khoá
    resolved = settings or get_settings()
    # "Khác rỗng" KHÔNG đủ: giá trị mẫu trong `.env.example` (ví dụ `sk-your-openai-or-groq-key`) từng bị
    # tính là khoá thật ⇒ giao diện báo "Đã có" dù chưa ai cung cấp khoá (đợt 21).
    if is_usable_api_key(_env_lookup(cfg.env_key)) or is_usable_api_key(
        getattr(resolved, cfg.env_key.lower(), "")
    ):
        return True
    # Đường thứ ba: khoá đã khai trong **màn hình quản trị → Nhà cung cấp LLM** (lưu DB, đã mã hoá).
    # Nhà cung cấp TTS trùng vendor với LLM (OpenAI hiện tại) dùng CHUNG khoá đó — catalog cũng ghi rõ
    # "dùng chung khoá với LLM đang cấu hình". Trước đây badge TTS chỉ nhìn ENV nên hiện "Chưa có" oan
    # sau khi quản trị viên đã nhập khoá trên giao diện.
    return _configured_in_llm_store(cfg.provider)


def _configured_in_llm_store(vendor: str) -> bool:
    """Khoá của `vendor` đã có trong kho nhà cung cấp LLM (DB hoặc ENV) hay chưa."""
    try:
        from src.services import llm_providers
    except Exception:  # noqa: BLE001 — thiếu module không được làm sập trang thiết lập giọng đọc
        return False
    return any(
        str(provider.provider).lower() == vendor.lower() and is_usable_api_key(provider.api_key)
        for provider in llm_providers.resolve_provider_configs()
    )


def _env_lookup(name: str) -> str:
    """Đọc biến môi trường theo tên thật (Settings chỉ map các trường nó khai báo)."""
    import os

    return os.environ.get(name, "")


def estimate_tts_cost(
    text: str,
    *,
    provider: str | None,
    settings: Settings | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Quy chi phí đọc một câu trả lời: số ký tự × đơn giá/1M (làm tròn 6 chữ số thập phân).

    Trả về cả `currency` và `price_verified_at` để UI không hiển thị con số như thể là giá hiện hành
    tuyệt đối khi bảng giá đã cũ.
    """
    cfg = get_tts_provider(provider) or get_tts_provider(BROWSER_PROVIDER)
    assert cfg is not None  # browser luôn tồn tại trong catalog
    resolved_max = max_chars if max_chars is not None else DEFAULT_MAX_CHARS_PER_TURN
    chars = len(text or "")
    billable = min(chars, max(0, resolved_max))
    cost = round(billable / 1_000_000 * cfg.price_per_1m_chars, 6)
    return {
        "provider": cfg.provider,
        "mode": cfg.mode,
        "chars": chars,
        "billable_chars": billable,
        "price_per_1m_chars": cfg.price_per_1m_chars,
        "currency": cfg.currency,
        "cost": cost,
        "price_verified_at": cfg.verified_at,
    }


def default_tts_settings(*, settings: Settings | None = None) -> dict[str, Any]:
    """Thiết lập mặc định của hệ thống khi Admin chưa khai báo gì."""
    resolved = settings or get_settings()
    configured_provider = (getattr(resolved, "tts_provider", "") or "").strip().lower()
    provider = get_tts_provider(configured_provider) or get_tts_provider(BROWSER_PROVIDER)
    assert provider is not None
    voice = (getattr(resolved, "tts_voice", "") or "").strip() or (provider.voices[0].code if provider.voices else "")
    max_chars = int(getattr(resolved, "tts_max_chars_per_turn", DEFAULT_MAX_CHARS_PER_TURN) or DEFAULT_MAX_CHARS_PER_TURN)
    return {
        "enabled": bool(getattr(resolved, "tts_enabled", True)),
        "auto_speak": bool(getattr(resolved, "tts_auto_speak", False)),
        "provider": provider.provider,
        "model": (getattr(resolved, "tts_model", "") or "").strip() or provider.default_model,
        "voice": voice,
        "speed": float(getattr(resolved, "tts_speed", 1.0) or 1.0),
        "max_chars_per_turn": max_chars,
    }


def validate_tts_settings(payload: dict[str, Any], *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Chuẩn hoá + kiểm tra một payload thiết lập TTS; ném `ValueError` khi không hợp lệ.

    Dùng chung cho cả endpoint (trả 422) và test, để luật chỉ nằm một chỗ.
    """
    merged = dict(base or default_tts_settings())
    for key in ("enabled", "auto_speak", "provider", "model", "voice", "speed", "max_chars_per_turn"):
        if key in payload and payload[key] is not None:
            merged[key] = payload[key]

    provider = get_tts_provider(str(merged.get("provider", "")))
    if provider is None:
        raise ValueError(
            "Nhà cung cấp TTS không hợp lệ. Chọn một trong: "
            + ", ".join(cfg.provider for cfg in TTS_PROVIDER_CATALOG)
        )
    merged["provider"] = provider.provider

    if provider.mode == "api" and provider.env_key and not _env_lookup(provider.env_key):
        # Vẫn cho phép lưu (để chuẩn bị trước), nhưng nói rõ vì sao bấm đọc sẽ lỗi.
        merged["warning"] = f"Chưa thấy biến môi trường {provider.env_key} cho {provider.label}."

    voice = str(merged.get("voice") or "").strip()
    if not voice:
        raise ValueError("Thiếu mã giọng đọc (voice).")
    merged["voice"] = voice
    merged["model"] = str(merged.get("model") or provider.default_model).strip()

    try:
        speed = float(merged.get("speed", 1.0))
    except (TypeError, ValueError) as exc:  # pragma: no cover - pydantic đã chặn kiểu
        raise ValueError("Tốc độ đọc phải là số.") from exc
    if not 0.5 <= speed <= 2.0:
        raise ValueError("Tốc độ đọc phải trong khoảng 0.5–2.0.")
    merged["speed"] = round(speed, 2)

    try:
        max_chars = int(merged.get("max_chars_per_turn", DEFAULT_MAX_CHARS_PER_TURN))
    except (TypeError, ValueError) as exc:  # pragma: no cover
        raise ValueError("Giới hạn ký tự mỗi lượt phải là số nguyên.") from exc
    if not 50 <= max_chars <= 5_000:
        raise ValueError("Giới hạn ký tự mỗi lượt phải trong khoảng 50–5000.")
    merged["max_chars_per_turn"] = max_chars

    merged["enabled"] = bool(merged.get("enabled", True))
    merged["auto_speak"] = bool(merged.get("auto_speak", False))

    # Chi phí ước tính cho một lượt đọc dài tối đa — để UI nói trước cái giá.
    merged["estimated_cost_full_turn"] = estimate_tts_cost(
        "x" * max_chars, provider=provider.provider, max_chars=max_chars
    )
    return merged
