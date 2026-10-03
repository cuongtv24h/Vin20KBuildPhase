"""Đọc câu trả lời thành tiếng **qua nhà cung cấp TTS** (bước kế tiếp của `tts_integration_plan.md` §7).

- `POST /tts/speak` — nhân viên gửi văn bản cần đọc, nhận audio (base64) + số ký tự + chi phí.
- `GET /tts/quota` — hạn mức ký tự còn lại trong ngày (UI nói trước khi đọc để không “cháy” ngân sách).

Nguyên tắc:

- Nhà cung cấp trình duyệt (`mode = "browser"`) **không** đi đường này — trả về thông báo rõ để giao diện
  dùng giọng máy (0 đồng), không im lặng đọc sai đường.
- Nhà cung cấp chưa nối adapter ⇒ **501 kèm hướng dẫn**, không giả vờ đọc được.
- Nhà cung cấp lỗi ⇒ **502/503**; giao diện tự lùi về giọng trình duyệt (đúng hành vi đã chốt trong kế hoạch).
- Văn bản được **che PII** và **cắt theo hạn mức ký tự** trước khi rời khỏi hệ thống.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal
from src.api.endpoints.copilot import require_staff_principal
from src.api.endpoints.settings import DEFAULT_SCOPE, _load_scope, user_scope
from src.db.session import get_db_session
from src.services.tts_providers import default_tts_settings, get_tts_provider, refresh_tts_providers
from src.services.tts_speak import (
    TtsSpeakError,
    audio_base64,
    chars_spoken_today,
    daily_char_budget,
    synthesize_speech,
    trim_for_speech,
)

router = APIRouter(prefix="/tts", tags=["tts"])

#: Chế độ “chỉ đọc bản tóm tắt” (rảnh tay): đọc phần đầu, đủ để Sale nắm ý mà không đọc cả câu trả lời dài.
SUMMARY_ONLY_CHARS = 240


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    provider: str | None = Field(None, description="Bỏ trống = lấy thiết lập hiệu lực của người gọi")
    voice: str | None = None
    model: str | None = None
    speed: float | None = Field(None, ge=0.5, le=2.0)
    conversation_id: str | None = None
    summary_only: bool = Field(False, description="True = chỉ đọc phần đầu (chế độ rảnh tay)")


class QuotaInfo(BaseModel):
    daily_budget: int
    chars_today: int
    remaining: int


class SpeakResponse(BaseModel):
    provider: str
    voice: str
    model: str
    mime: str
    audio_base64: str
    chars: int
    cached: bool
    cost: float
    currency: str
    latency_ms: float
    quota: QuotaInfo


async def _effective_settings(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Thiết lập giọng đọc hiệu lực cho người gọi (hồ sơ riêng thắng mặc định — như `GET /settings/tts`)."""
    await refresh_tts_providers(session)
    effective = dict(default_tts_settings())
    for scope in (await _load_scope(session, DEFAULT_SCOPE), await _load_scope(session, user_scope(user_id))):
        if scope:
            effective.update({k: v for k, v in scope.items() if k not in ("updated_by", "updated_at")})
    return effective


def _quota(settings: Any = None) -> QuotaInfo:
    budget = daily_char_budget(settings=settings)
    used = chars_spoken_today()
    return QuotaInfo(daily_budget=budget, chars_today=used, remaining=max(0, budget - used) if budget > 0 else -1)


@router.get("/quota", response_model=QuotaInfo)
async def get_quota(_: Principal = Depends(require_staff_principal)) -> QuotaInfo:
    """Hạn mức ký tự đọc thành tiếng còn lại trong ngày (`daily_budget = 0` nghĩa là không giới hạn)."""
    return _quota()


@router.post("/speak", response_model=SpeakResponse)
async def speak(
    payload: SpeakRequest,
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> SpeakResponse:
    """Tổng hợp audio cho một đoạn văn bản (cache theo nội dung ⇒ đọc lại không tốn thêm tiền)."""
    effective = await _effective_settings(session, principal.user_id)
    provider_code = (payload.provider or effective.get("provider") or "").strip().lower()
    cfg = get_tts_provider(provider_code)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nhà cung cấp TTS '{provider_code}' không có trong danh mục. Chọn lại trong thiết lập giọng đọc.",
        )
    if cfg.mode == "browser":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Nhà cung cấp đang chọn là giọng trình duyệt — giao diện đọc trực tiếp tại máy, "
                "không gửi qua backend."
            ),
        )

    voice = (payload.voice or effective.get("voice") or (cfg.voices[0].code if cfg.voices else "")).strip()
    model = (payload.model or effective.get("model") or cfg.default_model).strip()
    speed = float(payload.speed if payload.speed is not None else effective.get("speed", 1.0) or 1.0)
    max_chars = int(effective.get("max_chars_per_turn") or 600)
    text = trim_for_speech(payload.text, SUMMARY_ONLY_CHARS) if payload.summary_only else payload.text
    if not text.strip():
        raise HTTPException(status_code=422, detail="Không có nội dung để đọc.")

    try:
        result = await synthesize_speech(
            cfg,
            text=text,
            voice=voice,
            model=model,
            speed=speed,
            max_chars=max_chars,
        )
    except TtsSpeakError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    return SpeakResponse(
        provider=cfg.provider,
        voice=voice,
        model=model,
        mime=result.mime,
        audio_base64=audio_base64(result.audio),
        chars=result.chars,
        cached=result.cached,
        cost=result.cost,
        currency=result.currency,
        latency_ms=result.latency_ms,
        quota=_quota(),
    )
