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

Đường đọc dùng **giao thức OpenAI-compatible** (`POST {base}/audio/speech`) cho **mọi** nhà cung cấp có Base
URL — cố ý **không** có danh sách cứng theo tên, để nhà cung cấp thêm mới trong Quản trị CP (đợt 22) đọc
được ngay mà không phải sửa mã. Nhà cung cấp chọn trước mà lỗi thì **tự chuyển sang nhà cung cấp kế tiếp**
theo `priority` (`synthesize_with_fallback`) — sao chép cơ chế dự phòng của nhà cung cấp LLM.
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
from typing import Any

import httpx

from src.config import Settings, get_settings
from src.services import llm_usage
from src.services.llm_http import APP_USER_AGENT
from src.services.tts_providers import TtsProviderConfig, resolve_provider_api_key

logger = logging.getLogger(__name__)


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
    """Giao thức dùng để gọi đọc: **OpenAI-compatible** cho mọi nhà cung cấp có Base URL.

    Cố ý **không** có danh sách cứng theo tên nhà cung cấp: yêu cầu là “sao chép cơ chế sẵn có, cho phép
    thêm nhà cung cấp mới”, nên nhà cung cấp thêm sau này (self-host, gateway nội bộ, đại lý) chạy đúng
    cùng một đường như nhà cung cấp dựng sẵn. Thiếu Base URL là lý do duy nhất để không gọi được.
    """
    return "openai" if cfg.base_url else "none"


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
    hint = ""
    if resp.status_code in (404, 405, 400) and "<html" not in body.lower():
        hint = (
            " Có thể nhà cung cấp này không dùng giao thức OpenAI-compatible: hãy khai Base URL trỏ tới endpoint "
            "tương thích (kết thúc bằng `/v1`) của họ, hoặc để hệ thống đọc bằng nhà cung cấp kế tiếp trong chuỗi."
        )
    if "<html" in body.lower():
        body = "(nhà cung cấp trả trang HTML — thường là bị chặn/Cloudflare, không phải lỗi khoá)"
    raise TtsSpeakError(
        502 if resp.status_code not in (404, 405) else 501,
        "PROVIDER_ERROR",
        f"Nhà cung cấp trả mã {resp.status_code} cho {url}." + (f" Phản hồi: {body}" if body else "") + hint,
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
    if speak_style_for(cfg) == "none" or not cfg.base_url:
        # Không có Base URL = không biết gọi vào đâu. *Không* kết luận hộ là "nhà cung cấp này chưa hỗ trợ":
        # điều kiện duy nhất là kỹ thuật, nên nhà cung cấp thêm mới chỉ cần khai Base URL là chạy.
        raise TtsSpeakError(
            503,
            "MISSING_BASE_URL",
            (
                f"{cfg.label} chưa có Base URL nên không gọi được. Khai báo trong Quản trị CP → Giọng đọc → "
                "Nhà cung cấp TTS (giao thức OpenAI-compatible, thường là địa chỉ kết thúc bằng /v1)."
            ),
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
        # Đọc lại từ cache: KHÔNG gọi nhà cung cấp ⇒ **không phát sinh chi phí** và không tính vào hạn mức
        # ngày (hạn mức để chặn tiền thật, không phải để chặn nghe lại). Vẫn trả số ký tự để hiển thị.
        return SpeechResult(
            audio=cached_audio,
            mime=_audio_mime(""),
            chars=billable,
            billable_chars=billable,
            cached=True,
            cost=0.0,
            currency=cfg.currency,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
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
    ok: bool = True,
    error: str | None = None,
    is_fallback: bool = False,
) -> None:
    llm_usage.record_usage(
        provider=cfg.provider,
        model_name=model or cfg.default_model or voice,
        latency_ms=latency_ms,
        ok=ok,
        error=error,
        is_fallback=is_fallback,
        input_price_per_1m=0.0,
        output_price_per_1m=0.0,
        currency=cfg.currency,
        kind="tts",
        chars=chars,
        cost_override=cost,
        note="cache" if cached else None,
    )


def voice_for(cfg: TtsProviderConfig, requested: str | None) -> str:
    """Giọng dùng cho một nhà cung cấp: giữ yêu cầu nếu họ có giọng đó, không thì lấy giọng đầu của họ.

    Quan trọng khi **chuyển tiếp**: giọng của nhà cung cấp này (ví dụ `alloy`) là mã lạ với nhà cung cấp
    khác và sẽ bị từ chối; dùng giọng hợp lệ của chính nhà cung cấp đó thì câu vẫn đọc được.
    """
    wanted = (requested or "").strip()
    if wanted and any(v.code == wanted for v in cfg.voices):
        return wanted
    if wanted and not cfg.voices:
        return wanted
    return cfg.voices[0].code if cfg.voices else wanted


async def synthesize_with_fallback(
    candidates: list[TtsProviderConfig],
    *,
    text: str,
    voice: str | None,
    model: str | None,
    speed: float,
    max_chars: int,
    settings: Settings | None = None,
    timeout: float = 30.0,
) -> tuple[SpeechResult, TtsProviderConfig, list[dict[str, Any]]]:
    """Thử lần lượt các nhà cung cấp trong chuỗi — **sao chép cơ chế dự phòng của nhà cung cấp LLM**.

    Trả về `(kết quả, nhà cung cấp đã đọc, danh sách lần thử)`. Mỗi lần thử (kể cả lần lỗi) được ghi vào
    `llm_usage.jsonl` với `kind = "tts"`, nên tab “Chi phí & hiệu năng” thấy được cả tỉ lệ lỗi và việc
    chuyển tiếp. Lỗi **402 (vượt hạn mức ngày)** dừng ngay cả chuỗi — đổi nhà cung cấp không giải quyết được
    ngân sách.
    """
    if not candidates:
        raise TtsSpeakError(
            503,
            "NO_PROVIDER",
            (
                "Chưa có nhà cung cấp TTS nào gọi được (cần Base URL + khoá, hoặc dùng giọng trình duyệt). "
                "Khai trong Quản trị CP → Giọng đọc → Nhà cung cấp TTS."
            ),
        )
    attempts: list[dict[str, Any]] = []
    for index, cfg in enumerate(candidates):
        head = index == 0
        # Giọng: giữ đúng giọng người dùng chọn nếu **nhà cung cấp này** có giọng đó, không thì lấy giọng
        # đầu của họ — gửi mã giọng của nhà cung cấp khác sẽ bị từ chối (400) và làm hỏng cả chuỗi.
        provider_voice = voice_for(cfg, voice)
        provider_model = ((model or "").strip() if head else "") or cfg.default_model
        try:
            result = await synthesize_speech(
                cfg,
                text=text,
                voice=provider_voice,
                model=provider_model,
                speed=speed,
                max_chars=max_chars,
                settings=settings,
                timeout=timeout,
            )
        except TtsSpeakError as exc:
            if exc.status == 402:
                raise
            attempts.append(
                {
                    "provider": cfg.provider,
                    "label": cfg.label,
                    "ok": False,
                    "status": exc.code,
                    "detail": exc.detail,
                    "voice": provider_voice,
                    "model": provider_model,
                }
            )
            _record(
                cfg,
                voice=provider_voice,
                model=provider_model,
                chars=0,
                cost=0.0,
                cached=False,
                latency_ms=0.0,
                ok=False,
                error=exc.code,
                is_fallback=not head,
            )
            logger.warning("tts_provider_failed provider=%s status=%s detail=%s", cfg.provider, exc.code, exc.detail[:160])
            continue
        attempts.append(
            {
                "provider": cfg.provider,
                "label": cfg.label,
                "ok": True,
                "status": "OK",
                "detail": "",
                "voice": provider_voice,
                "model": provider_model,
            }
        )
        _record(
            cfg,
            voice=provider_voice,
            model=provider_model,
            chars=result.chars,
            cost=result.cost,
            cached=result.cached,
            latency_ms=result.latency_ms,
            is_fallback=not head,
        )
        return result, cfg, attempts
    reasons = "; ".join(f"{a['label']}: {a['detail']}" for a in attempts[:3])
    raise TtsSpeakError(
        502,
        "ALL_PROVIDERS_FAILED",
        "Không nhà cung cấp TTS nào đọc được. " + reasons,
    )


def chars_spoken_today(*, settings: Settings | None = None) -> int:
    """Số ký tự đã gửi đi đọc trong hôm nay (để chặn vượt hạn mức)."""
    today = llm_usage.today_key()
    return sum(
        int(rec.get("chars") or 0)
        for rec in llm_usage.recent_usage(limit=llm_usage.MAX_RECORDS_SCANNED)
        if str(rec.get("kind") or "") == "tts"
        and str(rec.get("at") or "").startswith(today)
        # Lượt đọc lại từ cache không gửi gì ra nhà cung cấp ⇒ không tính vào hạn mức ngày.
        and rec.get("note") != "cache"
        and rec.get("ok") is not False
    )


def daily_char_budget(*, settings: Settings | None = None) -> int:
    """Hạn mức ký tự mỗi ngày cho đường đọc trả phí (0 = không giới hạn)."""
    resolved = settings or get_settings()
    return int(getattr(resolved, "tts_daily_char_budget", 0) or 0)


def audio_base64(audio: bytes) -> str:
    return base64.b64encode(audio).decode("ascii")
