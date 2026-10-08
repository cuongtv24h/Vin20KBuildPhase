"""Thiết lập đọc câu trả lời Copilot (TTS) — API cho UI Sale và Admin.

Ba việc endpoint này làm:

1. `GET /settings/tts` — trả danh mục nhà cung cấp (kèm đơn giá + đã có khoá chưa), thiết lập hiện
   hành và **thiết lập hiệu lực** của người đang đăng nhập (hồ sơ riêng → mặc định hệ thống).
2. `PUT /settings/tts` — lưu thiết lập. Phạm vi `user` ai cũng đổi được cho chính mình; phạm vi
   `default` (toàn hệ thống) chỉ ADMIN/MANAGER, để một Sale không đổi giọng cho cả 20k người.
3. `POST /settings/tts/feedback` — ghi nhận "nghe ổn / chưa ổn" kèm giọng đã dùng, làm dữ liệu chọn
   giọng thay vì quyết định bằng cảm tính.

Mọi endpoint đều yêu cầu phiên đăng nhập (`require_staff_principal`) và trả về cùng một shape
`TtsSettingsResponse` để UI không phải suy diễn.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal
from src.api.endpoints.copilot import require_staff_principal
from src.db.models import TTSFeedbackModel, TTSSettingsModel
from src.db.session import get_db_session
from src.services.tts_providers import (
    DEFAULT_MAX_CHARS_PER_TURN,
    default_tts_settings,
    estimate_tts_cost,
    get_tts_provider,
    refresh_tts_providers,
    tts_catalog,
    validate_tts_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_SCOPE = "default"
#: Vai trò được đổi thiết lập dùng chung (ảnh hưởng mọi nhân viên).
DEFAULT_SCOPE_ROLES = ("ADMIN", "MANAGER")
MAX_FEEDBACK_REASON = 300


def user_scope(user_id: str) -> str:
    """Khoá thiết lập riêng của một nhân viên."""
    return f"user:{user_id}"


class TtsSettingsPayload(BaseModel):
    """Payload cập nhật; trường bỏ trống giữ nguyên giá trị đang có."""

    scope: Literal["user", "default"] = Field("user", description="'user' = riêng tôi, 'default' = toàn hệ thống")
    enabled: bool | None = None
    auto_speak: bool | None = Field(None, description="Tự đọc mỗi câu trả lời mới")
    provider: str | None = None
    model: str | None = None
    voice: str | None = None
    speed: float | None = Field(None, ge=0.5, le=2.0)
    max_chars_per_turn: int | None = Field(None, ge=50, le=5000)


class TtsFeedbackPayload(BaseModel):
    rating: int = Field(..., description="1 = nghe ổn, -1 = nghe chưa ổn")
    provider: str | None = None
    voice: str | None = None
    conversation_id: str | None = None
    reason: str | None = Field(None, max_length=MAX_FEEDBACK_REASON)


class TtsSettingsResponse(BaseModel):
    catalog: list[dict[str, Any]]
    #: Mặc định toàn hệ thống (do ADMIN/MANAGER đặt).
    default: dict[str, Any]
    #: Hồ sơ riêng của người đang hỏi (None nếu chưa đặt).
    user_override: dict[str, Any] | None
    #: Thiết lập thực sự sẽ dùng để đọc.
    effective: dict[str, Any]
    #: Ước tính chi phí đọc trọn 1 câu trả lời dài tối đa.
    cost_hint: dict[str, Any]
    #: Tóm tắt phản hồi giọng đọc để UI hiện "giọng này được khen/chê bao nhiêu".
    feedback_summary: dict[str, Any]


class TtsFeedbackResponse(BaseModel):
    feedback_id: str
    total: int
    up: int
    down: int


def _row_to_dict(row: TTSSettingsModel) -> dict[str, Any]:
    return {
        "enabled": row.enabled,
        "auto_speak": row.auto_speak,
        "provider": row.provider,
        "model": row.model,
        "voice": row.voice,
        "speed": row.speed,
        "max_chars_per_turn": row.max_chars_per_turn,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def _load_scope(session: AsyncSession, scope: str) -> dict[str, Any] | None:
    row = (
        await session.execute(select(TTSSettingsModel).where(TTSSettingsModel.scope == scope))
    ).scalar_one_or_none()
    return _row_to_dict(row) if row else None


async def _feedback_summary(session: AsyncSession, provider: str, voice: str) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(TTSFeedbackModel.rating).where(
                TTSFeedbackModel.provider == provider, TTSFeedbackModel.voice == voice
            )
        )
    ).scalars().all()
    up = sum(1 for r in rows if r == 1)
    down = sum(1 for r in rows if r == -1)
    total = len(rows)
    return {
        "total": total,
        "up": up,
        "down": down,
        "satisfaction": round(up / total, 4) if total else None,
    }


def _without_missing_provider(settings: dict[str, Any]) -> dict[str, Any]:
    """Rơi về nhà cung cấp mặc định khi nhà cung cấp đã lưu không còn trong danh mục.

    Tình huống thật: quản trị viên xoá một nhà cung cấp tự thêm trong khi vẫn có người đang chọn nó.
    Nếu cứ đem mã cũ đi kiểm tra thì trang giọng đọc trả lỗi 500 cho mọi nhân viên — không chấp nhận được.
    Ở đây thay bằng nhà cung cấp mặc định (trình duyệt) và ghi log để quản trị viên biết.
    """
    provider = str(settings.get("provider") or "").strip().lower()
    if not provider or get_tts_provider(provider) is not None:
        return settings
    fallback = default_tts_settings()["provider"]
    logger.warning("tts_provider_missing provider=%s → fallback=%s", provider, fallback)
    return {**settings, "provider": fallback}


@router.get("/tts", response_model=TtsSettingsResponse)
async def get_tts_settings(
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> TtsSettingsResponse:
    """Thiết lập hiện hành + thiết lập hiệu lực cho người đang đăng nhập."""
    # Nhà cung cấp TTS có thể do Admin thêm/sửa trong màn hình quản trị (DB) ⇒ nạp trước khi dựng danh mục,
    # nếu không người dùng sẽ không thấy nhà cung cấp mới cho tới khi khởi động lại backend.
    await refresh_tts_providers(session)
    base = default_tts_settings()
    default_override = await _load_scope(session, DEFAULT_SCOPE)
    user_override = await _load_scope(session, user_scope(principal.user_id))

    effective = dict(base)
    if default_override:
        effective.update({k: v for k, v in default_override.items() if k not in ("updated_by", "updated_at")})
    if user_override:
        effective.update({k: v for k, v in user_override.items() if k not in ("updated_by", "updated_at")})
    effective = validate_tts_settings({}, base=_without_missing_provider(effective))
    effective.pop("warning", None)

    return TtsSettingsResponse(
        catalog=tts_catalog(),
        default=validate_tts_settings({}, base=_without_missing_provider(default_override or base))
        | {"is_explicit": default_override is not None},
        user_override=user_override,
        effective=effective,
        cost_hint=estimate_tts_cost(
            "x" * effective["max_chars_per_turn"],
            provider=effective["provider"],
            max_chars=effective["max_chars_per_turn"],
        ),
        feedback_summary=await _feedback_summary(session, effective["provider"], effective["voice"]),
    )


@router.put("/tts", response_model=TtsSettingsResponse)
async def update_tts_settings(
    payload: TtsSettingsPayload,
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> TtsSettingsResponse:
    """Lưu thiết lập TTS (riêng tôi hoặc toàn hệ thống — có phân quyền)."""
    # Cùng lý do như GET: nạp bản ghi DB để nhà cung cấp do Admin thêm không bị coi là "không hợp lệ"
    # khi người dùng lưu lựa chọn ngay sau khi thêm (backend chưa khởi động lại).
    await refresh_tts_providers(session)
    scope = DEFAULT_SCOPE if payload.scope == "default" else user_scope(principal.user_id)
    if scope == DEFAULT_SCOPE and not principal.has_role(*DEFAULT_SCOPE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ ADMIN/MANAGER được đổi giọng đọc dùng chung. Anh/chị có thể lưu lựa chọn riêng cho mình.",
        )

    base = default_tts_settings()
    if scope == DEFAULT_SCOPE:
        existing_scope = await _load_scope(session, DEFAULT_SCOPE)
    else:
        existing_scope = await _load_scope(session, scope)
    if existing_scope:
        base.update({k: v for k, v in existing_scope.items() if k not in ("updated_by", "updated_at")})

    changes = payload.model_dump(exclude_none=True, exclude={"scope"})
    try:
        merged = validate_tts_settings(changes, base=_without_missing_provider(base))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    merged.pop("warning", None)
    merged.pop("estimated_cost_full_turn", None)

    row = (
        await session.execute(select(TTSSettingsModel).where(TTSSettingsModel.scope == scope))
    ).scalar_one_or_none()
    if row is None:
        row = TTSSettingsModel(scope=scope, updated_by=principal.user_id)
        session.add(row)
    for field_name in ("enabled", "auto_speak", "provider", "model", "voice", "speed", "max_chars_per_turn"):
        setattr(row, field_name, merged[field_name])
    row.updated_by = principal.user_id
    await session.commit()
    await session.refresh(row)
    logger.info(
        "tts_settings_updated scope=%s by=%s provider=%s voice=%s",
        scope,
        principal.user_id,
        row.provider,
        row.voice,
    )
    return await get_tts_settings(principal=principal, session=session)


@router.post("/tts/feedback", response_model=TtsFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_tts_feedback(
    payload: TtsFeedbackPayload,
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> TtsFeedbackResponse:
    """Ghi nhận phản hồi giọng đọc — dữ liệu để chọn giọng theo thực tế sử dụng."""
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=422, detail="rating chỉ nhận 1 hoặc -1.")

    base = default_tts_settings()
    default_override = await _load_scope(session, DEFAULT_SCOPE)
    user_override = await _load_scope(session, user_scope(principal.user_id))
    for override in (default_override, user_override):
        if override:
            base.update({k: v for k, v in override.items() if k not in ("updated_by", "updated_at")})
    effective = validate_tts_settings({}, base=base)

    provider = (payload.provider or effective["provider"]).strip().lower()
    voice = (payload.voice or effective["voice"]).strip()
    reason = (payload.reason or "").replace("\x00", "").strip()[:MAX_FEEDBACK_REASON] or None

    record = TTSFeedbackModel(
        user_id=principal.user_id,
        conversation_id=payload.conversation_id,
        provider=provider,
        voice=voice,
        rating=payload.rating,
        reason=reason,
    )
    session.add(record)
    await session.commit()

    summary = await _feedback_summary(session, provider, voice)
    return TtsFeedbackResponse(feedback_id=record.feedback_id, **{k: summary[k] for k in ("total", "up", "down")})


__all__ = ["router", "DEFAULT_MAX_CHARS_PER_TURN", "user_scope"]
