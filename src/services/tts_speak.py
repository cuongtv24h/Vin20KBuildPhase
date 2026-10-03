"""Tổng hợp audio qua nhà cung cấp TTS (bước kế tiếp của `tts_integration_plan.md` §7).

Trước đợt 22, tiếng đọc do **trình duyệt** tổng hợp (miễn phí nhưng giọng tuỳ máy, không đo được chi phí).
Sau khi có chỗ khai báo nhà cung cấp + khoá trên giao diện, module này là đường **gọi nhà cung cấp thật**
qua backend:

- Chỉ gọi khi thiết lập hiệu lực trỏ tới nhà cung cấp `mode = "api"`; nhà cung cấp trình duyệt vẫn để
  trình duyệt làm (0 đồng).
- **Che PII trước khi gửi ra ngoài** (SĐT/email của khách) — đúng việc còn thiếu đã ghi trong kế hoạch.
- **Cắt theo `max_chars_per_turn`** để không đọc cả câu trả lời dài (vừa tốn tiền vừa bắt khách chờ).
- **Cache trên đĩa** theo `sha256(text|provider|voice|model|speed)`: đọc lại cùng câu không tốn thêm tiền.
- **Ghi chi phí** vào `llm_usage.jsonl` với `kind = "tts"` (cột ký tự, không nhồi vào token).

Hiện mới nối **giao thức OpenAI-compatible** (`POST {base}/audio/speech`) — dùng được cho OpenAI, gateway
nội bộ và các máy chủ tự dựng kiểu OpenAI. Các nhà cung cấp khác (Google/Azure/Viettel/Vbee/FPT) trả về
thông báo **chưa nối adapter** kèm cách xử lý, thay vì giả vờ thành công.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.services import llm_usage
from src.services.llm_http import APP_USER_AGENT
from src.services.tts_providers import TtsProviderConfig, resolve_provider_api_key

logger = logging.getLogger(__name__)

#: Nhà cung cấp nói giao thức OpenAI-compatible cho `/audio/speech`.
OPENAI_SPEECH_STYLE = {"openai", "openai_compatible", "groq", "openrouter", "deepseek", "vieneu"}
#: Nhà cung cấp đã biết nhưng CHƯA nối adapter (nói thẳng ra, không giả vờ chạy được).
KNOWN_UNWIRED = {"google_cloud", "azure", "viettel", "vbee", "fpt"}

#: Che PII y như `copilot/feedback.mask_pii` (cùng luật: SĐT Việt Nam + email).
_PHONE_RE = re.compile(r"\b0\d{8,10}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")

DEFAULT_CACHE_DIR = Path("data/tts_cache")
DEFAULT_CACHE_TTL_DAYS = 7
DEFAULT_CACHE_MAX_MB = 200


class TtsSpeakError(Exception):
    """Lỗi khi tổng hợp audio — `status` để endpoint trả đúng mã HTTP, `detail` là câu đọc được."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SpeechResult:
    audio: bytes
    mime: str
    chars: int
    billable_chars: int
    cached: bool
    cost: float
    currency: str
    latency_ms: float


def mask_pii_for_speech(text: str) -> str:
    """Che SĐT/email trước khi gửi văn bản ra nhà cung cấp ngoài.

    Giọng đọc không cần số điện thoại/email dạng đầy đủ; đọc `091***78` vẫn đủ để câu nói tự nhiên.
    """
    masked = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "***" + m.group(0)[-2:], str(text or ""))
    return _EMAIL_RE.sub("***@***", masked)


def trim_for_speech(text: str, max_chars: int) -> str:
    """Cắt bớt theo `max_chars`, cố gắng dừng ở ranh giới câu để nghe tự nhiên."""
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    head = clean[:max_chars]
    cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "), head.rfind("; "))
    if cut >= max_chars // 2:
        return head[: cut + 1].strip()
    return head.rstrip() + "…"


def speak_style_for(cfg: TtsProviderConfig) -> str:
    """`openai` nếu gọi được qua `/audio/speech`; `none` nếu chưa nối adapter cho nhà cung cấp này."""
    if cfg.provider in OPENAI_SPEECH_STYLE:
        return "openai"
    # Nhà cung cấp tự thêm: có Base URL ⇒ coi là OpenAI-compatible (kiểu máy chủ TTS tự dựng phổ biến),
    # trừ khi trùng tên một nhà cung cấp đã biết là dùng giao thức riêng.
    if cfg.custom and cfg.base_url and cfg.provider not in KNOWN_UNWIRED:
        return "openai"
    return "none"


def _cache_dir() -> Path:
    raw = os.environ.get("TTS_CACHE_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_CACHE_DIR


def _cache_key(*, text: str, provider: str, voice: str, model: str, speed: float) -> str:
    payload = json.dumps(
        {"t": text, "p": provider, "v": voice, "m": model, "s": round(float(speed), 2)},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_read(key: str) -> bytes | None:
    path = _cache_dir() / key
    if not path.exists():
        return None
    ttl_days = int(getattr(get_settings(), "tts_cache_ttl_days", DEFAULT_CACHE_TTL_DAYS) or DEFAULT_CACHE_TTL_DAYS)
    if ttl_days > 0 and time.time() - path.stat().st_mtime > ttl_days * 86_400:
        path.unlink(missing_ok=True)
        return None
    try:
        return path.read_bytes()
    except OSError:  # pragma: no cover — đĩa lỗi thì coi như không có cache
        return None


def _cache_write(key: str, audio: bytes) -> None:
    """Ghi cache + dọn bớt file cũ nếu vượt trần dung lượng (trần để cache không ăn hết đĩa)."""
    directory = _cache_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / key).write_bytes(audio)
        max_mb = int(getattr(get_settings(), "tts_cache_max_mb", DEFAULT_CACHE_MAX_MB) or DEFAULT_CACHE_MAX_MB)
        if max_mb <= 0:
            return
        files = sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        limit = max_mb * 1024 * 1024
        while total > limit and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)
    except OSError:  # pragma: no cover — không ghi được cache thì vẫn phải trả audio cho người dùng
        logger.warning("tts_cache_write_failed key=%s", key)


def _audio_mime(headers_content_type: str) -> str:
    ctype = (headers_content_type or "").split(";")[0].strip().lower()
    return ctype if ctype.startswith("audio/") else "audio/mpeg"


async def _call_openai_style(
    *,
    base_url: str,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    speed: float,
    timeout: float,
) -> tuple[bytes, str]:
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": APP_USER_AGENT,
        "Accept": "audio/*",
    }
    payload = {"model": model or "tts-1", "voice": voice, "input": text, "speed": round(float(speed), 2)}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code == 200 and resp.content:
        return resp.content, _audio_mime(resp.headers.get("content-type", ""))
    if resp.status_code in (401, 403):
        raise TtsSpeakError(
            502,
            "PROVIDER_AUTH",
            f"Nhà cung cấp từ chối khoá (mã {resp.status_code}). Kiểm tra lại khoá trong Quản trị CP → Giọng đọc.",
        )
    ctype = resp.headers.get("content-type", "")
    body = resp.text[:300] if not ctype.startswith("audio/") else ""
    logger.warning("tts_provider_error status=%s url=%s body=%s", resp.status_code, url, body[:120])
    if "<html" in body.lower():
        body = "(nhà cung cấp trả trang HTML — thường là bị chặn/Cloudflare, không phải lỗi khoá)"
    raise TtsSpeakError(
        502,
        "PROVIDER_ERROR",
        f"Nhà cung cấp trả mã {resp.status_code} cho {url}." + (f" Phản hồi: {body}" if body else ""),
    )


async def synthesize_speech(
    cfg: TtsProviderConfig,
    *,
    text: str,
    voice: str,
    model: str,
    speed: float,
    max_chars: int,
    settings: Settings | None = None,
    timeout: float = 30.0,
) -> SpeechResult:
    """Tổng hợp `text` thành audio qua nhà cung cấp đã cấu hình (có cache + ghi chi phí)."""
    style = speak_style_for(cfg)
    if style == "none":
        raise TtsSpeakError(
            501,
            "ADAPTER_NOT_WIRED",
            (
                f"Chưa nối adapter tổng hợp audio cho {cfg.label} ({cfg.provider}). "
                "Hiện chạy được: OpenAI và mọi máy chủ/gateway theo giao thức OpenAI-compatible "
                "(thêm trong Quản trị CP → Giọng đọc với Base URL). "
                "Hoặc chọn giọng trình duyệt (miễn phí) cho tới khi adapter của nhà cung cấp này hoàn thành."
            ),
        )
    if not cfg.base_url:
        raise TtsSpeakError(
            503,
            "MISSING_BASE_URL",
            f"{cfg.label} chưa có Base URL nên không gọi được. Khai báo trong Quản trị CP → Giọng đọc.",
        )
    api_key = resolve_provider_api_key(cfg, settings=settings)
    if not api_key:
        raise TtsSpeakError(
            503,
            "MISSING_KEY",
            (
                f"Chưa có khoá cho {cfg.label}. Nhập khoá trong Quản trị CP → Giọng đọc → Nhà cung cấp TTS"
                + (f" (hoặc biến môi trường {cfg.env_key})" if cfg.env_key else "")
                + "."
            ),
        )

    spoken = trim_for_speech(mask_pii_for_speech(text), max_chars)
    billable = len(spoken)
    key = _cache_key(text=spoken, provider=cfg.provider, voice=voice, model=model, speed=speed)
    started = time.perf_counter()

    cached_audio = _cache_read(key)
    if cached_audio is not None:
        latency = round((time.perf_counter() - started) * 1000, 2)
        cost = round(billable / 1_000_000 * cfg.price_per_1m_chars, 6)
        _record(cfg, voice=voice, model=model, chars=billable, cost=cost, cached=True, latency_ms=latency)
        return SpeechResult(
            audio=cached_audio,
            mime=_audio_mime(""),
            chars=billable,
            billable_chars=billable,
            cached=True,
            cost=cost,
            currency=cfg.currency,
            latency_ms=latency,
        )

    budget = daily_char_budget(settings=settings)
    used = chars_spoken_today()
    if budget > 0 and used + billable > budget:
        raise TtsSpeakError(
            402,
            "DAILY_QUOTA_EXCEEDED",
            (
                f"Hạn mức đọc thành tiếng hôm nay không đủ: đã dùng {used:,} / {budget:,} ký tự, "
                f"lượt này cần {billable:,}. Tạm dùng giọng trình duyệt (miễn phí) hoặc nhờ quản trị viên "
                "nâng hạn mức (TTS_DAILY_CHAR_BUDGET)."
            ),
        )

    audio, mime = await _call_openai_style(
        base_url=cfg.base_url,
        api_key=api_key,
        model=model or cfg.default_model,
        voice=voice,
        text=spoken,
        speed=speed,
        timeout=timeout,
    )
    latency = round((time.perf_counter() - started) * 1000, 2)
    cost = round(billable / 1_000_000 * cfg.price_per_1m_chars, 6)
    _cache_write(key, audio)
    _record(cfg, voice=voice, model=model, chars=billable, cost=cost, cached=False, latency_ms=latency)
    return SpeechResult(
        audio=audio,
        mime=mime,
        chars=billable,
        billable_chars=billable,
        cached=False,
        cost=cost,
        currency=cfg.currency,
        latency_ms=latency,
    )


def _record(
    cfg: TtsProviderConfig,
    *,
    voice: str,
    model: str,
    chars: int,
    cost: float,
    cached: bool,
    latency_ms: float,
) -> None:
    llm_usage.record_usage(
        provider=cfg.provider,
        model_name=model or cfg.default_model or voice,
        latency_ms=latency_ms,
        ok=True,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        currency=cfg.currency,
        kind="tts",
        chars=chars,
        cost_override=cost,
        note="cache" if cached else None,
    )


def chars_spoken_today(*, settings: Settings | None = None) -> int:
    """Số ký tự đã gửi đi đọc trong hôm nay (để chặn vượt hạn mức)."""
    today = llm_usage.today_key()
    return sum(
        int(rec.get("chars") or 0)
        for rec in llm_usage.recent_usage(limit=llm_usage.MAX_RECORDS_SCANNED)
        if str(rec.get("kind") or "") == "tts" and str(rec.get("at") or "").startswith(today)
    )


def daily_char_budget(*, settings: Settings | None = None) -> int:
    """Hạn mức ký tự mỗi ngày cho đường đọc trả phí (0 = không giới hạn)."""
    resolved = settings or get_settings()
    return int(getattr(resolved, "tts_daily_char_budget", 0) or 0)


def audio_base64(audio: bytes) -> str:
    return base64.b64encode(audio).decode("ascii")
