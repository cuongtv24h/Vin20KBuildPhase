"""Nhà cung cấp Speech-to-Text (Whisper) — Sale NÓI, hệ thống trả về CHỮ cho Copilot.

Vì sao nhân bản khuôn `tts_providers.py` thay vì viết mới:

- Cùng một bài toán "nhiều nhà cung cấp, khoá bí mật, cần fallback": **DB ưu tiên → `.env` dự phòng**,
  khoá lưu mã hoá Fernet (`src/services/llm_secrets.py`), API chỉ trả dạng che. ADMIN đổi khoá không cần deploy.
- Chuỗi fallback: nhà cung cấp đầu lỗi/hết hạn mức thì tự rơi xuống mắt xích kế, cuối cùng là
  `browser` (Web Speech API phía frontend) — nên hết quota Groq giữa demo thì Sale vẫn nói được.
- Ghi chi phí vào cùng sổ `llm_usage.jsonl` (`kind = "stt"`) nên tab "Chi phí & hiệu năng" thấy được.

Ranh giới kiến trúc (đã chốt với người dùng 2026-10-08): **ASR chỉ là "bàn phím bằng giọng nói"**.
Module này trả về CHỮ; chữ đó đi vào đúng `POST /api/v1/copilot/chat` như Sale gõ. Không đưa audio
vào graph, không đụng grounding/verifier/compliance — nên không có rủi ro hồi quy cho luồng Copilot.

Về dữ liệu audio: hệ thống **không lưu audio** ở bất kỳ đâu (không ghi đĩa, không nhét vào DB) — chỉ
giữ transcript + tên nhà cung cấp + độ trễ để đo chất lượng và chi phí. Với Groq, Zero Data Retention
là **cờ cấp tài khoản bật trong Groq Console → Data Controls**, KHÔNG có tham số theo từng request;
vì vậy ở đây nó là một cam kết vận hành (`zero_data_retention`) và `/stt/health` sẽ cảnh báo nếu chưa bật.
"""

from __future__ import annotations

import io
import logging
import math
import struct
import time
import wave
from dataclasses import dataclass, field, replace
from typing import Any

import httpx

from src.config import Settings, get_settings
from src.services import llm_usage
from src.services.llm_secrets import decrypt_api_key, mask_api_key

logger = logging.getLogger(__name__)

#: Nhà cung cấp "trình duyệt": Web Speech API chạy ngay trên máy Sale, 0 đồng, không qua backend.
BROWSER_PROVIDER = "browser"

#: Định dạng audio chấp nhận (Whisper phía Groq/OpenAI nhận các loại này; `MediaRecorder` sinh webm/opus).
ACCEPTED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/flac",
        # Safari/iOS đôi khi không khai báo đúng kiểu; chấp nhận kèm cảnh báo thay vì chặn oan.
        "application/octet-stream",
    }
)


@dataclass(slots=True)
class SttProviderConfig:
    """Cấu hình một nhà cung cấp STT (dựng sẵn trong danh mục hoặc ADMIN khai báo trong DB)."""

    provider: str
    label: str
    #: `api` = backend gọi lên nhà cung cấp; `browser` = frontend tự nhận dạng (Web Speech API).
    mode: str = "api"
    base_url: str = ""
    default_model: str = ""
    #: Tên biến môi trường giữ khoá (dùng khi DB chưa có khoá cho nhà cung cấp này).
    env_key: str = ""
    language: str = "vi"
    #: Giá theo MỘT GIỜ audio (đơn vị ở `currency`) — để ước lượng chi phí trong báo cáo.
    price_per_hour_audio: float = 0.0
    currency: str = "USD"
    note: str = ""
    priority: int = 50
    is_active: bool = True
    #: Cam kết vận hành: đã bật Zero Data Retention ở phía nhà cung cấp (Groq: Console → Data Controls).
    zero_data_retention: bool = False
    #: Từ vựng mồi riêng của nhà cung cấp (rỗng thì dùng `settings.stt_prompt`).
    prompt_bias: str = ""
    #: Bản ghi DB mà cấu hình này được dựng từ (None = nhà cung cấp dựng sẵn chưa bị đè).
    provider_id: str | None = None
    api_key_masked: str = ""


#: Danh mục dựng sẵn. `groq` đứng đầu vì có gói FREE không cần thẻ (2.000 request/ngày, 8 giờ audio/ngày)
#: và Whisper chạy trên LPU rất nhanh; `openai` là phương án trả phí quen thuộc; `browser` là lưới an toàn.
STT_PROVIDER_CATALOG: tuple[SttProviderConfig, ...] = (
    SttProviderConfig(
        provider="groq",
        label="Groq Whisper (LPU)",
        mode="api",
        base_url="https://api.groq.com/openai/v1",
        default_model="whisper-large-v3-turbo",
        env_key="STT_GROQ_API_KEY",
        price_per_hour_audio=0.04,
        note=(
            "Gói free không cần thẻ: 20 request/phút, 2.000 request/ngày, 8 giờ audio/ngày, file ≤ 25 MB. "
            "Trả phí 0,04 USD/giờ (turbo) hoặc 0,111 USD/giờ (large-v3 — tiếng Việt chính xác hơn). "
            "Zero Data Retention bật ở Console → Data Controls (cờ cấp tài khoản, không phải theo request)."
        ),
        priority=10,
    ),
    SttProviderConfig(
        provider="openai",
        label="OpenAI Whisper",
        mode="api",
        base_url="https://api.openai.com/v1",
        default_model="whisper-1",
        # Dùng lại khoá LLM sẵn có: không bắt ADMIN khai thêm secret nếu đã chạy Copilot bằng OpenAI.
        env_key="OPENAI_API_KEY",
        price_per_hour_audio=0.36,
        note="Cần trả phí trước (không có gói free). Dùng lại OPENAI_API_KEY/OPENAI_BASE_URL của LLM.",
        priority=20,
    ),
    SttProviderConfig(
        provider=BROWSER_PROVIDER,
        label="Trình duyệt (Web Speech API)",
        mode="browser",
        base_url="",
        default_model="",
        env_key="",
        price_per_hour_audio=0.0,
        note=(
            "0 đồng, chạy sẵn trong Chrome/Edge/Cốc Cốc, không qua backend. Hạn chế: chỉ vài trình duyệt, "
            "audio đi qua máy chủ của hãng trình duyệt, không bias được từ vựng dự án. Lưới an toàn cuối chuỗi."
        ),
        priority=90,
    ),
)

_BY_PROVIDER: dict[str, SttProviderConfig] = {cfg.provider: cfg for cfg in STT_PROVIDER_CATALOG}


# --------------------------------------------------------------------------- #
# Lớp DB (ưu tiên) — cùng cơ chế cache tiến trình như tts_providers
# --------------------------------------------------------------------------- #

_ROWS_CACHE: list[dict[str, Any]] | None = None

#: Khoá đã giải mã theo mã nhà cung cấp (chỉ sống trong bộ nhớ tiến trình; không log, không trả ra API).
_PLAIN_KEYS: dict[str, str] = {}


def set_stt_provider_rows(rows: list[dict[str, Any]] | None) -> None:
    """Nạp cache cấu hình DB (gọi lúc khởi động và sau khi ADMIN sửa; `None` = xoá cache)."""
    global _ROWS_CACHE
    _ROWS_CACHE = [dict(row) for row in rows] if rows is not None else None


def stt_provider_rows() -> list[dict[str, Any]] | None:
    return _ROWS_CACHE


async def refresh_stt_providers(session: Any | None = None) -> list[dict[str, Any]]:
    """Đọc bảng `stt_providers` vào cache tiến trình.

    KHÔNG được làm hỏng ứng dụng khi bảng chưa tồn tại (VM chưa chạy `init_db` lại sau khi thêm bảng):
    mọi lỗi DB đều bị nuốt kèm cảnh báo, và hệ thống tiếp tục chạy bằng `.env`.
    """
    rows: list[dict[str, Any]] = []
    try:
        if session is not None:
            rows = await _load_rows(session)
        else:
            from src.db.session import get_db_session

            async for db in get_db_session():
                rows = await _load_rows(db)
                break
    except Exception as exc:  # noqa: BLE001 - bảng chưa có/kết nối lỗi thì dùng ENV, không chặn khởi động
        logger.warning("Không đọc được bảng stt_providers (%s) — dùng cấu hình .env cho STT.", exc)
        set_stt_provider_rows([])
        return []
    set_stt_provider_rows(rows)
    return rows


async def _load_rows(db_session: Any) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from src.db.models import STTProviderModel

    result = await db_session.execute(select(STTProviderModel))
    return [stt_row_to_dict(row) for row in result.scalars().all()]


def stt_row_to_dict(row: Any, *, decrypt: bool = True) -> dict[str, Any]:
    """Đổi bản ghi DB thành dict; khoá chỉ ở dạng CHE khi `decrypt=False` (để trả ra API)."""
    stored = str(getattr(row, "api_key_encrypted", "") or "")
    return {
        "provider_id": getattr(row, "provider_id", None),
        "provider": str(getattr(row, "provider", "") or ""),
        "label": str(getattr(row, "label", "") or ""),
        "mode": str(getattr(row, "mode", "api") or "api"),
        "base_url": getattr(row, "base_url", None) or "",
        "default_model": str(getattr(row, "default_model", "") or ""),
        "env_key": str(getattr(row, "env_key", "") or ""),
        "language": str(getattr(row, "language", "vi") or "vi"),
        "price_per_hour_audio": float(getattr(row, "price_per_hour_audio", 0.0) or 0.0),
        "currency": str(getattr(row, "currency", "USD") or "USD"),
        "note": str(getattr(row, "note", "") or ""),
        "priority": int(getattr(row, "priority", 50) or 50),
        "is_active": bool(getattr(row, "is_active", True)),
        "zero_data_retention": bool(getattr(row, "zero_data_retention", False)),
        "prompt_bias": str(getattr(row, "prompt_bias", "") or ""),
        "api_key_masked": mask_api_key(decrypt_api_key(stored)) if stored else "",
        "has_api_key": bool(stored),
        "api_key_plain": decrypt_api_key(stored) if (decrypt and stored) else "",
    }


def _config_from_row(row: dict[str, Any]) -> SttProviderConfig:
    base = _BY_PROVIDER.get(row["provider"])
    return SttProviderConfig(
        provider=row["provider"],
        label=row["label"] or (base.label if base else row["provider"]),
        mode=row["mode"] or (base.mode if base else "api"),
        base_url=row["base_url"] or (base.base_url if base else ""),
        default_model=row["default_model"] or (base.default_model if base else ""),
        env_key=row["env_key"] or (base.env_key if base else ""),
        language=row["language"] or (base.language if base else "vi"),
        price_per_hour_audio=row["price_per_hour_audio"] if row["price_per_hour_audio"] else (base.price_per_hour_audio if base else 0.0),
        currency=row["currency"] or (base.currency if base else "USD"),
        note=row["note"] or (base.note if base else ""),
        priority=int(row["priority"]),
        is_active=bool(row["is_active"]),
        zero_data_retention=bool(row["zero_data_retention"]),
        prompt_bias=row["prompt_bias"] or "",
        provider_id=row.get("provider_id"),
        api_key_masked=row.get("api_key_masked", ""),
    )


def resolve_stt_providers(*, include_inactive: bool = False) -> list[SttProviderConfig]:
    """Danh mục sau khi ghép bản ghi DB: DB đè nhà cung cấp cùng mã, mã lạ thành nhà cung cấp MỚI."""
    rows = _ROWS_CACHE or []
    configs: dict[str, SttProviderConfig] = {}
    for base in STT_PROVIDER_CATALOG:
        configs[base.provider] = replace(base)
    for row in rows:
        cfg = _config_from_row(row)
        configs[cfg.provider] = cfg
        # `_row_keys` giữ khoá đã giải mã theo provider để `resolve_provider_api_key` dùng (không đưa vào dataclass).
        _PLAIN_KEYS[cfg.provider] = str(row.get("api_key_plain") or "")
    ordered = sorted(configs.values(), key=lambda c: (c.priority, c.provider))
    return ordered if include_inactive else [c for c in ordered if c.is_active]



def get_stt_provider(provider: str | None, *, include_inactive: bool = False) -> SttProviderConfig | None:
    if not provider:
        return None
    for cfg in resolve_stt_providers(include_inactive=include_inactive):
        if cfg.provider == provider:
            return cfg
    return None


def resolve_provider_api_key(cfg: SttProviderConfig, *, settings: Settings | None = None) -> str:
    """Khoá theo thứ tự **DB → ENV** (đúng yêu cầu "khai báo trong env và trong db đều được")."""
    from_db = (_PLAIN_KEYS.get(cfg.provider) or "").strip()
    if from_db:
        return from_db
    resolved = settings or get_settings()
    if cfg.provider == "groq":
        return (resolved.stt_groq_api_key or "").strip()
    if cfg.provider == "openai":
        return (resolved.openai_api_key or "").strip()
    if cfg.env_key:
        import os

        return (os.environ.get(cfg.env_key) or "").strip()
    return ""


def zero_data_retention_effective(cfg: SttProviderConfig, *, settings: Settings | None = None) -> bool:
    """Zero Data Retention của một mắt xích — **cam kết vận hành**, không phải tham số gửi đi.

    Groq bật ZDR ở CẤP TÀI KHOẢN trong Console → Data Controls; không có cờ theo request. Vì vậy giá trị
    ở đây chỉ để hệ thống biết mà cảnh báo: bản ghi DB (ADMIN tick) đè lên, chưa có bản ghi DB thì lấy
    theo `STT_ZERO_DATA_RETENTION` trong `.env`.
    """
    resolved = settings or get_settings()
    if cfg.provider_id:
        return bool(cfg.zero_data_retention)
    return bool(cfg.zero_data_retention or resolved.stt_zero_data_retention)


def is_provider_configured(cfg: SttProviderConfig, *, settings: Settings | None = None) -> bool:
    """`browser` luôn "sẵn sàng" (không cần khoá); nhà cung cấp API phải có khoá THẬT."""
    if cfg.mode == "browser":
        return True
    key = resolve_provider_api_key(cfg, settings=settings)
    # "Khác rỗng" chưa đủ: giá trị mẫu trong `.env.example` từng khiến hệ thống tưởng đã có khoá.
    if not key or key.startswith("sk-your-") or "your-" in key or key.lower() in {"changeme", "todo", "test"}:
        return False
    return True


def transcribe_chain(*, preferred: str | None = None, settings: Settings | None = None) -> list[SttProviderConfig]:
    """Chuỗi nhà cung cấp BACKEND sẽ thử, theo `priority`; chỉ gồm mắt xích đang bật VÀ đã cấu hình.

    `browser` (Web Speech API) KHÔNG nằm trong chuỗi này vì backend không gọi được trình duyệt — nó là
    lưới an toàn phía frontend, hỏi riêng bằng `browser_fallback_available()`.
    """
    resolved = settings or get_settings()
    usable = [c for c in resolve_stt_providers() if c.mode == "api" and is_provider_configured(c, settings=resolved)]
    if preferred:
        usable.sort(key=lambda c: (c.provider != preferred, c.priority, c.provider))
    return usable


def browser_fallback_available() -> bool:
    """Frontend còn lưới an toàn Web Speech API không (để báo cho UI biết mà hiện nút)."""
    cfg = get_stt_provider(BROWSER_PROVIDER)
    return bool(cfg and cfg.is_active)


# --------------------------------------------------------------------------- #
# Gọi nhà cung cấp
# --------------------------------------------------------------------------- #


class SttError(Exception):
    """Lỗi STT có mã + trạng thái HTTP để endpoint dịch thẳng thành phản hồi."""

    def __init__(self, http_status: int, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(slots=True)
class SttResult:
    """Kết quả một lượt nghe: chữ thô + chữ đã chuẩn hoá thuật ngữ + số đo để ghi sổ."""

    text: str
    normalized_text: str
    language: str
    provider: str
    model: str
    latency_ms: float
    audio_bytes: int
    attempts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def _post_openai_compatible(
    cfg: SttProviderConfig,
    api_key: str,
    audio: bytes,
    *,
    filename: str,
    language: str,
    prompt: str,
    model: str,
    timeout: float,
) -> tuple[str, str]:
    """Gọi `POST {base_url}/audio/transcriptions` (Groq và OpenAI dùng chung hình dạng API này)."""
    url = f"{cfg.base_url.rstrip('/')}/audio/transcriptions"
    data: dict[str, Any] = {"model": model, "language": language}
    # `prompt` chỉ là từ vựng MỒI (Whisper dùng làm ngữ cảnh) — không phải lệnh hệ thống, và không được
    # chứa dữ liệu khách hàng: chỉ tên dự án/mã căn/thuật ngữ.
    if prompt:
        data["prompt"] = prompt[:1_000]
    files = {"file": (filename, audio, "application/octet-stream")}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, data=data, files=files, headers={"Authorization": f"Bearer {api_key}"})
    if response.status_code >= 400:
        detail = response.text[:300]
        raise SttError(
            502 if response.status_code >= 500 else 400,
            "STT_PROVIDER_ERROR",
            f"{cfg.label} từ chối yêu cầu ({response.status_code}): {detail}",
            details={"provider": cfg.provider, "status_code": response.status_code},
        )
    payload = response.json()
    text = str(payload.get("text") or "").strip()
    detected = str(payload.get("language") or language).strip()
    return text, detected


def normalize_transcript(text: str, *, extra_terms: dict[str, str] | None = None) -> str:
    """Chuẩn hoá tất định sau ASR — vì mã căn sai MỘT ký tự là Copilot tra sai căn.

    Chỉ sửa những thứ chắc chắn (danh từ riêng của dự án, viết tắt, số thập phân đọc theo kiểu Việt);
    không "đoán" nội dung, không thêm bớt ý của Sale.
    """
    import re

    if not text:
        return ""
    out = text.strip()

    # 1) Mã căn: "ZEN A 1205" / "zen a-1205" → "ZEN-A-1205" (mẫu <tên toà>-<MỘT chữ cái tháp>-<số>).
    # Chỉ nhận MỘT chữ cái ở giữa: nới thành 1-3 chữ cái sẽ sửa nhầm "anh Ba 1234" thành "ANH-BA-1234".
    def _unit(match: re.Match[str]) -> str:
        return f"{match.group(1).upper()}-{match.group(2).upper()}-{match.group(3)}"

    out = re.sub(r"\b([A-Za-z]{3,})[\s\-]+([A-Za-z])[\s\-]+(\d{3,5})\b", _unit, out)

    # 2) Viết tắt nghiệp vụ hay bị Whisper đánh vần rời.
    glossary: dict[str, str] = {
        r"\bk(?:ê|e)?\s*p(?:hẩy)?\s*b(?:ê)?\s*t(?:ê)?\b": "KPBT",
        r"\bv\s*a\s+t\b": "VAT",
        r"\bg\s*p\b": "GPMB",
    }
    for pattern, replacement in glossary.items():
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    for pattern, replacement in (extra_terms or {}).items():
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # 3) Số thập phân đọc kiểu Việt: "3 phẩy 864 tỷ" → "3,864 tỷ"; "1 chấm 5 tỷ" → "1,5 tỷ".
    out = re.sub(r"(\d+)\s*(?:phẩy|chấm|comma)\s*(\d+)", r"\1,\2", out, flags=re.IGNORECASE)

    return re.sub(r"\s{2,}", " ", out).strip()


async def transcribe_with_fallback(
    audio: bytes,
    *,
    filename: str = "audio.webm",
    language: str | None = None,
    prompt: str | None = None,
    preferred: str | None = None,
    settings: Settings | None = None,
    user_id: str | None = None,
) -> SttResult:
    """Thử lần lượt theo chuỗi; mắt xích nào lỗi thì ghi nhận và đi tiếp (đúng hành vi `synthesize_with_fallback`)."""
    resolved = settings or get_settings()
    if not resolved.stt_enabled:
        raise SttError(503, "STT_DISABLED", "Chức năng nghe-nói đang tắt (STT_ENABLED=false).")

    chain = transcribe_chain(preferred=preferred, settings=resolved)
    if not chain:
        raise SttError(
            503,
            "STT_NOT_CONFIGURED",
            "Chưa cấu hình nhà cung cấp nghe-nói nào: ADMIN cần dán khoá Groq (STT_GROQ_API_KEY trong .env "
            "hoặc PUT /api/v1/stt/providers/groq). Trình duyệt vẫn có thể dùng Web Speech API làm phương án tạm.",
            details={"browser_fallback": browser_fallback_available()},
        )

    lang = (language or resolved.stt_language or "vi").strip() or "vi"
    bias = (prompt if prompt is not None else resolved.stt_prompt) or ""
    attempts: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, cfg in enumerate(chain):
        head = index == 0
        api_key = resolve_provider_api_key(cfg, settings=resolved)
        model = cfg.default_model or resolved.stt_model
        started = time.perf_counter()
        try:
            text, detected = await _post_openai_compatible(
                cfg,
                api_key,
                audio,
                filename=filename,
                language=lang,
                prompt=cfg.prompt_bias or bias,
                model=model,
                timeout=resolved.stt_request_timeout_seconds,
            )
        except SttError as exc:
            attempts.append({"provider": cfg.provider, "label": cfg.label, "ok": False, "detail": exc.message})
            logger.warning("STT %s thất bại: %s", cfg.label, exc.message)
            continue
        except httpx.HTTPError as exc:
            attempts.append({"provider": cfg.provider, "label": cfg.label, "ok": False, "detail": f"lỗi mạng: {exc}"})
            logger.warning("STT %s lỗi mạng: %s", cfg.label, exc)
            continue

        latency_ms = (time.perf_counter() - started) * 1000
        if not zero_data_retention_effective(cfg, settings=resolved) and cfg.provider == "groq":
            warnings.append(
                "Groq chưa được khai báo Zero Data Retention: bật ở Console → Data Controls để audio "
                "không bị giữ lại cho việc soát lỗi (mặc định Groq có thể log tối đa 30 ngày)."
            )
        normalized = normalize_transcript(text)
        _record_usage(
            cfg=cfg,
            model=model,
            audio_bytes=len(audio),
            latency_ms=latency_ms,
            ok=True,
            is_fallback=not head,
            user_id=user_id,
        )
        attempts.append({"provider": cfg.provider, "label": cfg.label, "ok": True, "latency_ms": round(latency_ms, 1)})
        return SttResult(
            text=text,
            normalized_text=normalized,
            language=detected or lang,
            provider=cfg.provider,
            model=model,
            latency_ms=round(latency_ms, 1),
            audio_bytes=len(audio),
            attempts=attempts,
            warnings=warnings,
        )

    for cfg in chain:
        _record_usage(cfg=cfg, model=cfg.default_model, audio_bytes=len(audio), latency_ms=0.0, ok=False, user_id=user_id)
    reasons = "; ".join(f"{a['label']}: {a.get('detail', 'lỗi')}" for a in attempts[:3])
    raise SttError(502, "ALL_PROVIDERS_FAILED", f"Không nhà cung cấp STT nào nghe được. {reasons}", details={"attempts": attempts})


def _record_usage(
    *,
    cfg: SttProviderConfig,
    model: str,
    audio_bytes: int,
    latency_ms: float,
    ok: bool,
    is_fallback: bool = False,
    user_id: str | None = None,
    error: str | None = None,
) -> None:
    """Ghi sổ `llm_usage.jsonl` với `kind = "stt"`; `chars` giữ SỐ GIÂY audio ước tính (hạn mức tính theo phút)."""
    seconds = estimate_audio_seconds(audio_bytes)
    llm_usage.record_usage(
        provider=cfg.provider,
        model_name=model,
        latency_ms=latency_ms,
        ok=ok,
        error=error,
        is_fallback=is_fallback,
        kind="stt",
        chars=int(round(seconds)),
        # Giá theo giờ audio → chi phí lượt này (ước lượng theo dung lượng, vì ASR không trả số giây).
        cost_override=round(cfg.price_per_hour_audio * seconds / 3600.0, 6) if ok else 0.0,
        currency=cfg.currency,
        user_id=user_id,
        note=None if ok else "failed",
    )


def estimate_audio_seconds(audio_bytes: int, *, bits_per_second: int = 32_000) -> float:
    """Ước lượng thời lượng từ dung lượng (opus/webm ~32 kbps cho giọng nói một kênh).

    Chỉ dùng cho hạn mức và ước tính chi phí — không phải số liệu chính xác; ASR không trả thời lượng.
    """
    if audio_bytes <= 0:
        return 0.0
    return max(1.0, round(audio_bytes * 8 / bits_per_second, 1))


# --------------------------------------------------------------------------- #
# Hạn mức (chặn cháy túi / chạm trần free tier giữa demo)
# --------------------------------------------------------------------------- #


def audio_seconds_today(*, settings: Settings | None = None) -> int:
    """Số GIÂY audio đã gửi đi nghe trong hôm nay (lượt lỗi không tính)."""
    today = llm_usage.today_key()
    return sum(
        int(rec.get("chars") or 0)
        for rec in llm_usage.recent_usage(limit=llm_usage.MAX_RECORDS_SCANNED)
        if str(rec.get("kind") or "") == "stt"
        and str(rec.get("at") or "").startswith(today)
        and rec.get("ok") is not False
    )


def daily_minutes_budget(*, settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    return int(getattr(resolved, "stt_daily_minutes_budget", 0) or 0)


def quota_report(*, settings: Settings | None = None) -> dict[str, Any]:
    budget = daily_minutes_budget(settings=settings)
    used_seconds = audio_seconds_today(settings=settings)
    used_minutes = math.ceil(used_seconds / 60)
    return {
        "daily_budget_minutes": budget,
        "minutes_today": used_minutes,
        "seconds_today": used_seconds,
        "remaining_minutes": max(0, budget - used_minutes) if budget > 0 else -1,
    }


def quota_exceeded(*, settings: Settings | None = None) -> bool:
    budget = daily_minutes_budget(settings=settings)
    if budget <= 0:
        return False
    return math.ceil(audio_seconds_today(settings=settings) / 60) >= budget


# --------------------------------------------------------------------------- #
# Công cụ kiểm tra nhanh (ADMIN "Test" và scripts/check_stt_groq.py dùng chung)
# --------------------------------------------------------------------------- #


def silent_wav(seconds: float = 1.0, *, rate: int = 16_000) -> bytes:
    """Sinh file WAV im lặng bằng thư viện chuẩn — đủ để kiểm tra khoá/URL/model mà không cần thu âm."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(struct.pack("<h", 0) * int(rate * seconds))
    return buffer.getvalue()


async def probe_provider(provider: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Gửi 1 giây im lặng lên nhà cung cấp để kiểm tra cấu hình; trả trạng thái + độ trễ (không lưu audio)."""
    resolved = settings or get_settings()
    cfg = get_stt_provider(provider, include_inactive=True)
    if cfg is None:
        return {"provider": provider, "ok": False, "detail": "Không có nhà cung cấp này trong danh mục/DB."}
    if cfg.mode == "browser":
        return {"provider": provider, "ok": True, "detail": "Chạy trên trình duyệt, không cần kiểm tra phía máy chủ."}
    api_key = resolve_provider_api_key(cfg, settings=resolved)
    if not api_key:
        return {"provider": provider, "ok": False, "detail": "Chưa có khoá (DB và ENV đều trống)."}
    started = time.perf_counter()
    try:
        text, detected = await _post_openai_compatible(
            cfg,
            api_key,
            silent_wav(),
            filename="probe.wav",
            language=cfg.language or "vi",
            prompt="",
            model=cfg.default_model or resolved.stt_model,
            timeout=resolved.stt_request_timeout_seconds,
        )
    except SttError as exc:
        return {"provider": provider, "ok": False, "detail": exc.message, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    except httpx.HTTPError as exc:
        return {"provider": provider, "ok": False, "detail": f"Lỗi mạng khi gọi {cfg.base_url}: {exc}"}
    return {
        "provider": provider,
        "ok": True,
        "model": cfg.default_model or resolved.stt_model,
        "language": detected,
        "text": text,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "detail": "Khoá và model hợp lệ (file im lặng nên transcript rỗng là bình thường).",
    }


def stt_health_report(*, settings: Settings | None = None) -> dict[str, Any]:
    """Bức tranh cấu hình STT cho `/stt/health` và trang quản trị — cùng tinh thần `/copilot/health`."""
    resolved = settings or get_settings()
    providers = resolve_stt_providers(include_inactive=True)
    chain = transcribe_chain(settings=resolved)
    return {
        "enabled": bool(resolved.stt_enabled),
        "preferred": resolved.stt_provider,
        "language": resolved.stt_language,
        "chain": [
            {
                "provider": cfg.provider,
                "label": cfg.label,
                "model": cfg.default_model or resolved.stt_model,
                "configured": is_provider_configured(cfg, settings=resolved),
                "active": cfg.is_active,
                "key_source": "db" if (_PLAIN_KEYS.get(cfg.provider) or "").strip() else ("env" if is_provider_configured(cfg, settings=resolved) else "none"),
                "api_key_masked": cfg.api_key_masked,
                "zero_data_retention": zero_data_retention_effective(cfg, settings=resolved),
                "price_per_hour_audio": cfg.price_per_hour_audio,
                "currency": cfg.currency,
            }
            for cfg in providers
        ],
        "active_chain": [cfg.provider for cfg in chain],
        "browser_fallback": browser_fallback_available(),
        "quota": quota_report(settings=resolved),
        "limits": {
            "max_bytes": int(resolved.stt_max_bytes),
            "max_duration_seconds": int(resolved.stt_max_duration_seconds),
            "accepted_content_types": sorted(ACCEPTED_CONTENT_TYPES),
        },
        "warnings": _health_warnings(resolved, providers),
    }


def _health_warnings(resolved: Settings, providers: list[SttProviderConfig]) -> list[str]:
    warnings: list[str] = []
    if not any(c.mode == "api" and is_provider_configured(c, settings=resolved) for c in providers):
        warnings.append(
            "Chưa có nhà cung cấp API nào được cấu hình: Sale chỉ nhập giọng nói được bằng Web Speech API "
            "của trình duyệt (Chrome/Edge/Cốc Cốc)."
        )
    groq = next((c for c in providers if c.provider == "groq"), None)
    if groq and is_provider_configured(groq, settings=resolved) and not zero_data_retention_effective(groq, settings=resolved):
        warnings.append(
            "Groq chưa khai báo Zero Data Retention (STT_ZERO_DATA_RETENTION=true sau khi bật ở "
            "Console → Data Controls): mặc định Groq có thể lưu log audio tối đa 30 ngày để soát lỗi/lạm dụng."
        )
    if resolved.stt_daily_minutes_budget <= 0:
        warnings.append("Hạn mức phút/ngày đang TẮT (STT_DAILY_MINUTES_BUDGET=0) — không có chặn cháy túi.")
    return warnings


def provider_catalog_view(*, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Danh mục cho UI quản trị: che khoá, kèm trạng thái đã cấu hình."""
    resolved = settings or get_settings()
    return [
        {
            "provider": cfg.provider,
            "label": cfg.label,
            "mode": cfg.mode,
            "base_url": cfg.base_url,
            "default_model": cfg.default_model or (resolved.stt_model if cfg.mode == "api" else ""),
            "env_key": cfg.env_key,
            "language": cfg.language,
            "priority": cfg.priority,
            "is_active": cfg.is_active,
            "configured": is_provider_configured(cfg, settings=resolved),
            "key_source": "db" if (_PLAIN_KEYS.get(cfg.provider) or "").strip() else ("env" if is_provider_configured(cfg, settings=resolved) else "none"),
            "api_key_masked": cfg.api_key_masked,
            "zero_data_retention": zero_data_retention_effective(cfg, settings=resolved),
            "price_per_hour_audio": cfg.price_per_hour_audio,
            "currency": cfg.currency,
            "note": cfg.note,
            "prompt_bias": cfg.prompt_bias,
        }
        for cfg in resolve_stt_providers(include_inactive=True)
    ]


__all__ = [
    "ACCEPTED_CONTENT_TYPES",
    "BROWSER_PROVIDER",
    "STT_PROVIDER_CATALOG",
    "SttError",
    "SttProviderConfig",
    "SttResult",
    "audio_seconds_today",
    "browser_fallback_available",
    "daily_minutes_budget",
    "estimate_audio_seconds",
    "get_stt_provider",
    "is_provider_configured",
    "normalize_transcript",
    "probe_provider",
    "provider_catalog_view",
    "quota_exceeded",
    "quota_report",
    "refresh_stt_providers",
    "resolve_provider_api_key",
    "resolve_stt_providers",
    "set_stt_provider_rows",
    "silent_wav",
    "stt_health_report",
    "stt_provider_rows",
    "stt_row_to_dict",
    "transcribe_chain",
    "transcribe_with_fallback",
    "zero_data_retention_effective",
]
