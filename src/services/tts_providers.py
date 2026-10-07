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

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import Settings, get_settings
from src.services.llm_secrets import is_usable_api_key

logger = logging.getLogger(__name__)

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
    #: `provider_id` của bản ghi DB ("" nếu chỉ có trong danh mục dựng sẵn).
    provider_id: str = ""
    #: True khi bản ghi do Admin tự thêm (không nằm trong danh mục dựng sẵn).
    custom: bool = False
    #: Đang bật hay đang tắt (bản ghi DB có thể tạm ẩn một nhà cung cấp).
    is_active: bool = True
    #: Khoá đã giải mã từ DB — chỉ nằm trong bộ nhớ, KHÔNG bao giờ trả ra API.
    db_api_key: str = ""


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

#: Bản ghi DB đã nạp: `None` = chưa nạp (dùng danh mục dựng sẵn), `[]` = đã nạp và DB trống.
_DB_ROWS: list[dict[str, Any]] | None = None

#: Chặn trên số ký tự đọc mỗi lượt — câu trả lời dài mà đọc hết vừa lâu vừa tốn tiền.
DEFAULT_MAX_CHARS_PER_TURN = 600


def set_tts_provider_rows(rows: list[dict[str, Any]] | None) -> None:
    """Nạp bản ghi DB vào bộ nhớ (gọi từ endpoint sau mỗi lần đọc/ghi, hoặc từ test).

    `None` = chưa nạp; `[]` = đã nạp và DB trống (hai trạng thái này khác nhau: DB trống nghĩa là
    "không có bản ghi nào", còn chưa nạp nghĩa là "chưa hỏi DB").
    """
    global _DB_ROWS
    _DB_ROWS = rows


def tts_provider_rows() -> list[dict[str, Any]] | None:
    """Bản ghi DB đang có trong bộ nhớ (dùng cho test và endpoint)."""
    return _DB_ROWS


async def refresh_tts_providers(session: Any | None = None) -> list[dict[str, Any]]:
    """Đọc bảng `tts_providers` từ DB, giải mã khoá, nạp vào bộ nhớ; trả danh sách bản ghi.

    Khoá được giải mã ngay tại đây để mọi tầng sau (kiểm tra "đã có khoá", chọn khoá khi gọi API) dùng
    cùng một nguồn — nhưng khoá **không** bao giờ được trả ra API (endpoint chỉ trả dạng che).
    """
    from sqlalchemy import select

    from src.db.models import TTSProviderModel
    from src.db.session import get_db_session
    from src.services.llm_secrets import decrypt_api_key

    async def _load(db_session: Any) -> list[TTSProviderModel]:
        result = await db_session.execute(select(TTSProviderModel).order_by(TTSProviderModel.priority.asc()))
        return list(result.scalars().all())

    try:
        if session is not None:
            rows = await _load(session)
        else:
            async for db_session in get_db_session():
                rows = await _load(db_session)
                break
            else:  # pragma: no cover — không mở được session (DB chưa cấu hình)
                set_tts_provider_rows([])
                return []
    except Exception as exc:  # noqa: BLE001
        # Bảng chưa kịp tạo trên một triển khai cũ KHÔNG được làm sập trang giọng đọc của Sale:
        # giữ nguyên danh mục dựng sẵn và ghi cảnh báo để quản trị viên biết chạy lại khởi động backend
        # (`Base.metadata.create_all` sẽ tạo bảng còn thiếu).
        logger.warning("tts_providers_load_failed err=%s — dùng danh mục dựng sẵn", exc)
        set_tts_provider_rows([])
        return []

    models = list(rows)
    set_tts_provider_rows([tts_row_to_dict(row, decrypt_api_key=decrypt_api_key) for row in models])
    return _DB_ROWS or []


def tts_row_to_dict(row: Any, *, decrypt_api_key: Any | None = None) -> dict[str, Any]:
    """Bản ghi DB → dict thuần (khoá ở dạng giải mã nếu truyền `decrypt_api_key`)."""
    try:
        voices = json.loads(row.voices_json or "[]")
    except (TypeError, ValueError):  # JSON hỏng thì coi như chưa khai giọng, không làm sập trang
        voices = []
    return {
        "provider_id": row.provider_id,
        "provider": row.provider,
        "label": row.label,
        "mode": row.mode,
        "base_url": row.base_url or "",
        "default_model": row.default_model or "",
        "env_key": row.env_key or "",
        "price_per_1m_chars": float(row.price_per_1m_chars or 0.0),
        "currency": row.currency or "USD",
        "price_note": row.price_note or "",
        "verified_at": row.verified_at or "",
        "note": row.note or "",
        "voices": [v for v in voices if isinstance(v, dict) and v.get("code")],
        "supports_streaming": bool(row.supports_streaming),
        "voice_cloning": bool(row.voice_cloning),
        "api_key": decrypt_api_key(row.api_key_encrypted) if decrypt_api_key else "",
        "priority": int(row.priority or 50),
        "is_active": bool(row.is_active),
        "last_test_status": row.last_test_status,
        "last_test_latency_ms": row.last_test_latency_ms,
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
        "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
    }


def _config_from_row(row: dict[str, Any], *, custom: bool) -> TtsProviderConfig:
    """Bản ghi DB → `TtsProviderConfig` (để danh mục và mọi tầng dùng chung một hình dạng)."""
    return TtsProviderConfig(
        provider=str(row["provider"]).strip().lower(),
        label=str(row["label"]).strip() or str(row["provider"]),
        mode=str(row.get("mode") or "api").strip().lower(),
        env_key=str(row.get("env_key") or "").strip().upper(),
        base_url=str(row.get("base_url") or "").strip(),
        default_model=str(row.get("default_model") or "").strip(),
        price_per_1m_chars=float(row.get("price_per_1m_chars") or 0.0),
        currency=str(row.get("currency") or "USD").strip().upper(),
        verified_at=str(row.get("verified_at") or "").strip(),
        price_note=str(row.get("price_note") or "").strip(),
        voices=tuple(
            TtsVoice(
                code=str(v.get("code", "")).strip(),
                label=str(v.get("label") or v.get("code") or "").strip(),
                gender=str(v.get("gender") or "neutral").strip(),
            )
            for v in (row.get("voices") or [])
            if str(v.get("code", "")).strip()
        ),
        supports_streaming=bool(row.get("supports_streaming")),
        voice_cloning=bool(row.get("voice_cloning")),
        note=str(row.get("note") or "").strip(),
        provider_id=str(row.get("provider_id") or ""),
        custom=custom,
        is_active=bool(row.get("is_active", True)),
        db_api_key=str(row.get("api_key") or ""),
    )


def resolve_tts_providers(*, include_inactive: bool = False) -> list[TtsProviderConfig]:
    """Danh mục HIỆU LỰC: danh mục dựng sẵn + bản ghi DB (đè theo mã, rồi tới nhà cung cấp mới).

    Đây là điểm duy nhất quyết định "có những nhà cung cấp nào" — nhờ vậy thêm một nhà cung cấp mới
    trong giao diện là nó xuất hiện ở mọi nơi (chọn giọng đọc, tính chi phí, kiểm tra khoá).
    """
    rows = _DB_ROWS if _DB_ROWS is not None else []
    overrides = {str(r["provider"]).strip().lower(): r for r in rows}
    merged: list[TtsProviderConfig] = []
    for base in TTS_PROVIDER_CATALOG:
        row = overrides.get(base.provider)
        if row is None:
            merged.append(base)
            continue
        merged.append(
            TtsProviderConfig(
                provider=base.provider,
                label=str(row.get("label") or base.label),
                mode=str(row.get("mode") or base.mode),
                env_key=str(row.get("env_key") or base.env_key),
                base_url=str(row.get("base_url") or base.base_url),
                default_model=str(row.get("default_model") or base.default_model),
                price_per_1m_chars=float(row.get("price_per_1m_chars") or 0.0),
                currency=str(row.get("currency") or base.currency),
                verified_at=str(row.get("verified_at") or base.verified_at),
                price_note=str(row.get("price_note") or base.price_note),
                voices=tuple(
                    TtsVoice(code=str(v.get("code", "")), label=str(v.get("label") or v.get("code", "")), gender=str(v.get("gender") or "neutral"))
                    for v in (row.get("voices") or [])
                )
                or base.voices,
                supports_streaming=bool(row.get("supports_streaming", base.supports_streaming)),
                voice_cloning=bool(row.get("voice_cloning", base.voice_cloning)),
                note=str(row.get("note") or base.note),
                provider_id=str(row.get("provider_id") or ""),
                custom=False,
                is_active=bool(row.get("is_active", True)),
                db_api_key=str(row.get("api_key") or ""),
            )
        )
    builtin_codes = {cfg.provider for cfg in TTS_PROVIDER_CATALOG}
    custom_rows = sorted(
        (r for r in rows if str(r["provider"]).strip().lower() not in builtin_codes),
        key=lambda r: (int(r.get("priority") or 50), str(r["provider"])),
    )
    merged.extend(_config_from_row(row, custom=True) for row in custom_rows)
    if include_inactive:
        return merged
    return [cfg for cfg in merged if cfg.is_active]


def get_tts_provider(provider: str | None, *, include_inactive: bool = False) -> TtsProviderConfig | None:
    """Tra cứu nhà cung cấp TTS theo mã (không phân biệt hoa/thường) — có tính bản ghi DB."""
    if not provider:
        return None
    wanted = provider.strip().lower()
    for cfg in resolve_tts_providers(include_inactive=include_inactive):
        if cfg.provider == wanted:
            return cfg
    return None


def tts_catalog(*, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Danh mục hiệu lực cho UI: giá, giọng gợi ý, và **đã có khoá để gọi chưa** (không lộ khoá).

    Danh mục gồm nhà cung cấp dựng sẵn **và** nhà cung cấp Admin tự thêm trong giao diện; nhà cung cấp
    tự thêm có cờ `custom = true` để UI gắn nhãn "Tuỳ chỉnh".
    """
    resolved = settings or get_settings()
    items: list[dict[str, Any]] = []
    for cfg in resolve_tts_providers():
        items.append(
            {
                "provider": cfg.provider,
                "label": cfg.label,
                "mode": cfg.mode,
                "default_model": cfg.default_model,
                "base_url": cfg.base_url,
                "env_key": cfg.env_key,
                "price_per_1m_chars": cfg.price_per_1m_chars,
                "currency": cfg.currency,
                "price_note": cfg.price_note,
                "verified_at": cfg.verified_at,
                "supports_streaming": cfg.supports_streaming,
                "voice_cloning": cfg.voice_cloning,
                "note": cfg.note,
                # Nhà cung cấp do Admin thêm (ngoài danh mục dựng sẵn) — UI gắn nhãn "Tuỳ chỉnh".
                "custom": cfg.custom,
                "provider_id": cfg.provider_id,
                # Chỉ trả về CÓ/KHÔNG, không bao giờ trả chính khoá.
                "api_key_configured": is_provider_configured(cfg, settings=resolved),
                "key_source": provider_key_source(cfg, settings=resolved),
                "voices": [{"code": v.code, "label": v.label, "gender": v.gender} for v in cfg.voices],
            }
        )
    return items


def is_provider_configured(cfg: TtsProviderConfig, *, settings: Settings | None = None) -> bool:
    """Nhà cung cấp đã có khoá chưa — kiểm tra cả trường Settings lẫn biến môi trường thô.

    Vì sao hai đường: `OPENAI_API_KEY` được Settings map thành `openai_api_key`, còn
    `GOOGLE_APPLICATION_CREDENTIALS` là đường dẫn file, Settings không khai báo → phải đọc ENV trực tiếp.
    """
    return provider_key_source(cfg, settings=settings) != "none"


def provider_key_source(cfg: TtsProviderConfig, *, settings: Settings | None = None) -> str:
    """Khoá của nhà cung cấp đang lấy từ đâu: `db` | `env` | `llm` | `browser` | `none`.

    Thứ tự ưu tiên đúng như kho nhà cung cấp LLM (**DB → ENV**), cộng thêm một đường đặc biệt: nhà cung
    cấp TTS trùng vendor với LLM đang cấu hình thì dùng chung khoá đó (OpenAI).
    """
    if cfg.mode == "browser" or not cfg.env_key:
        return "browser"
    if is_usable_api_key(cfg.db_api_key):
        return "db"
    resolved = settings or get_settings()
    # "Khác rỗng" KHÔNG đủ: giá trị mẫu trong `.env.example` (ví dụ `sk-your-openai-or-groq-key`) từng bị
    # tính là khoá thật ⇒ giao diện báo "Đã có" dù chưa ai cung cấp khoá (đợt 21).
    if is_usable_api_key(_env_lookup(cfg.env_key)) or is_usable_api_key(
        getattr(resolved, cfg.env_key.lower(), "")
    ):
        return "env"
    # Đường thứ ba: khoá đã khai trong **màn hình quản trị → Nhà cung cấp LLM** (lưu DB, đã mã hoá).
    # Nhà cung cấp TTS trùng vendor với LLM (OpenAI hiện tại) dùng CHUNG khoá đó — catalog cũng ghi rõ
    # "dùng chung khoá với LLM đang cấu hình". Trước đây badge TTS chỉ nhìn ENV nên hiện "Chưa có" oan
    # sau khi quản trị viên đã nhập khoá trên giao diện.
    if _configured_in_llm_store(cfg.provider):
        return "llm"
    return "none"


def resolve_provider_api_key(cfg: TtsProviderConfig, *, settings: Settings | None = None) -> str:
    """Khoá dùng thật khi gọi nhà cung cấp (DB → ENV → kho LLM). Không bao giờ trả ra API."""
    resolved = settings or get_settings()
    if is_usable_api_key(cfg.db_api_key):
        return cfg.db_api_key
    for candidate in (_env_lookup(cfg.env_key), str(getattr(resolved, cfg.env_key.lower(), "") or "")):
        if is_usable_api_key(candidate):
            return candidate
    try:
        from src.services import llm_providers

        for provider in llm_providers.resolve_provider_configs():
            if str(provider.provider).lower() == cfg.provider.lower() and is_usable_api_key(provider.api_key):
                return str(provider.api_key)
    except Exception:  # noqa: BLE001 — thiếu module không được làm sập luồng đọc
        pass
    return ""


def speak_capable(cfg: TtsProviderConfig, *, settings: Settings | None = None) -> tuple[bool, str]:
    """Nhà cung cấp này có **gọi đọc thật** được không — kèm lý do nếu chưa.

    Luật **không phụ thuộc tên nhà cung cấp** (đúng yêu cầu “sao chép cơ chế sẵn có, cho phép thêm nhà cung
    cấp mới”): cứ `mode = "api"` + có **Base URL** + có **khoá dùng được** là gọi được theo giao thức
    OpenAI-compatible (`POST {base}/audio/speech`). Không có danh sách cứng trong đường đọc — nhà cung cấp
    mới thêm trong giao diện tham gia chuỗi đọc y như nhà cung cấp dựng sẵn.
    """
    if cfg.mode == "browser":
        return False, "đọc tại trình duyệt (không gọi qua backend)"
    if not cfg.is_active:
        return False, "đang tắt"
    if not cfg.base_url:
        return False, "chưa khai Base URL"
    if provider_key_source(cfg, settings=settings) == "none":
        return False, "chưa có khoá"
    return True, ""


def speak_chain(*, preferred: str | None = None, settings: Settings | None = None) -> list[TtsProviderConfig]:
    """Chuỗi nhà cung cấp sẽ thử khi đọc — **sao chép đúng cơ chế nhà cung cấp LLM**:

    1. nhà cung cấp đang được chọn (thiết lập giọng đọc) chạy trước;
    2. rồi tới các nhà cung cấp còn lại theo `priority` (số nhỏ trước);
    3. chỉ gồm nhà cung cấp **gọi được thật** (Base URL + khoá) và đang bật;
    4. lỗi ở nhà cung cấp trước thì tự chuyển sang nhà cung cấp kế tiếp (ghi log + nói cho người dùng).
    """
    wanted = (preferred or "").strip().lower()
    head: list[TtsProviderConfig] = []
    tail: list[TtsProviderConfig] = []
    for cfg in resolve_tts_providers():
        ok, _reason = speak_capable(cfg, settings=settings)
        if not ok:
            continue
        (head if wanted and cfg.provider == wanted else tail).append(cfg)
    return head + tail


def speak_chain_report(*, preferred: str | None = None, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Danh mục kèm lý do **vì sao (không) gọi được** — để giao diện nói rõ thứ tự đọc và chỗ tắc.

    Nhà cung cấp đọc được xếp trước theo đúng thứ tự chuỗi (nhà cung cấp đang chọn lên đầu); nhà cung cấp
    chưa gọi được xếp sau, mỗi dòng kèm lý do để quản trị viên biết cần bổ sung gì.
    """
    resolved = settings or get_settings()
    wanted = (preferred or "").strip().lower()
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for cfg in speak_chain(preferred=preferred, settings=resolved) + [
        cfg
        for cfg in resolve_tts_providers(include_inactive=True)
        if not speak_capable(cfg, settings=resolved)[0]
    ]:
        if cfg.mode == "browser":
            # Giọng trình duyệt không đi qua backend (đọc tại máy, 0 đồng) ⇒ không thuộc chuỗi này.
            continue
        ok, reason = speak_capable(cfg, settings=resolved)
        item = {
            "provider": cfg.provider,
            "label": cfg.label,
            "mode": cfg.mode,
            "base_url": cfg.base_url,
            "price_per_1m_chars": cfg.price_per_1m_chars,
            "currency": cfg.currency,
            "ready": ok,
            "reason": reason,
            "is_preferred": bool(wanted) and cfg.provider == wanted,
        }
        (ready if ok else blocked).append(item)
    return ready + blocked


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
            + ", ".join(cfg.provider for cfg in resolve_tts_providers())
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
