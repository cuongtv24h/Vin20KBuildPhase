"""Endpoint nghe-nói (Speech-to-Text): Sale NÓI → chữ → dán vào ô hỏi Copilot.

Ranh giới đã chốt: endpoint này **chỉ trả về chữ**. Chữ đó đi vào đúng `POST /api/v1/copilot/chat`
như khi Sale gõ, nên grounding/verifier/compliance/lịch sử hội thoại không đổi một dòng nào.

Bảo mật & chi phí (theo khuôn `tts_speak.py`):

- Bắt buộc phiên nhân viên (`require_staff_principal`) — không có chuyện khách lạ gửi audio lên đây.
- Trần dung lượng `STT_MAX_BYTES` (mặc định 10 MB) đọc **từng khúc** để không nạp vào RAM quá tay.
- Hạn mức **phút audio/ngày** (`STT_DAILY_MINUTES_BUDGET`) → vượt thì 429, không âm thầm đốt tiền.
- **Không lưu audio**: chỉ ghi sổ `llm_usage.jsonl` (transcript không ghi vào sổ, chỉ số giây + độ trễ + nhà cung cấp).
- Khoá nhà cung cấp: **DB trước → `.env` sau**, lưu mã hoá Fernet, API chỉ trả dạng che.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal
from src.api.endpoints.copilot import require_staff_principal
from src.config import get_settings
from src.db.models import STTProviderModel
from src.db.session import get_db_session
from src.services.llm_secrets import encrypt_api_key, mask_api_key
from src.services.stt_providers import (
    ACCEPTED_CONTENT_TYPES,
    SttError,
    estimate_audio_seconds,
    get_stt_provider,
    probe_provider,
    provider_catalog_view,
    quota_exceeded,
    quota_report,
    refresh_stt_providers,
    stt_health_report,
    transcribe_with_fallback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt", tags=["stt"])

#: Đọc theo khúc 64 KB để chặn file quá khổ mà không nạp cả vào RAM.
_CHUNK_BYTES = 64 * 1024


class TranscribeResponse(BaseModel):
    """Kết quả một lượt nghe."""

    text: str = Field(description="Transcript thô từ nhà cung cấp.")
    normalized_text: str = Field(description="Transcript sau chuẩn hoá thuật ngữ (mã căn, KPBT, số thập phân…).")
    language: str
    provider: str
    model: str
    latency_ms: float
    audio_bytes: int
    estimated_seconds: float
    quota: dict[str, Any]
    fallback_used: bool
    warnings: list[str] = Field(default_factory=list)


class SttQuotaResponse(BaseModel):
    daily_budget_minutes: int
    minutes_today: int
    seconds_today: int
    remaining_minutes: int


class SttProviderUpsert(BaseModel):
    """ADMIN khai báo/đè cấu hình một nhà cung cấp STT trong DB (khoá lưu mã hoá)."""

    label: str | None = None
    api_key: str | None = Field(default=None, description="Để trống = giữ khoá đang có; `''` = xoá khoá.")
    base_url: str | None = None
    model: str | None = None
    language: str | None = None
    priority: int | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None
    zero_data_retention: bool | None = None
    prompt_bias: str | None = None
    env_key: str | None = None
    price_per_hour_audio: float | None = Field(default=None, ge=0)
    currency: str | None = None
    note: str | None = None


class SttProviderView(BaseModel):
    provider_id: str
    provider: str
    label: str
    mode: str
    base_url: str
    default_model: str
    language: str
    priority: int
    is_active: bool
    zero_data_retention: bool
    api_key_masked: str
    has_api_key: bool
    source: str = Field(description="`db` = bản ghi này; `env` = khoá đang lấy từ biến môi trường.")


def _require_admin(principal: Principal, authorization: str | None) -> None:
    """Cổng ADMIN cho cấu hình nhà cung cấp: dán khoá là thao tác quản trị, không mở cho nhân viên."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Cần đăng nhập để cấu hình nhà cung cấp nghe-nói.")
    if not principal.has_role("ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Chỉ quản trị viên mới được cấu hình nhà cung cấp nghe-nói (STT).",
        )


def _view(row: STTProviderModel, *, key_source: str = "db") -> SttProviderView:
    from src.services.llm_secrets import decrypt_api_key

    stored = str(row.api_key_encrypted or "")
    return SttProviderView(
        provider_id=row.provider_id,
        provider=row.provider,
        label=row.label,
        mode=row.mode,
        base_url=str(row.base_url or ""),
        default_model=row.default_model,
        language=row.language,
        priority=row.priority,
        is_active=row.is_active,
        zero_data_retention=row.zero_data_retention,
        api_key_masked=mask_api_key(decrypt_api_key(stored)) if stored else "",
        has_api_key=bool(stored),
        source=key_source,
    )


# --------------------------------------------------------------------------- #
# Đường dùng hằng ngày (nhân viên)
# --------------------------------------------------------------------------- #


@router.get("/health")
async def stt_health(
    _: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trạng thái chuỗi nhà cung cấp, hạn mức, trần dung lượng và cảnh báo (ví dụ chưa bật ZDR bên Groq)."""
    await refresh_stt_providers(session)
    return stt_health_report()


@router.get("/quota", response_model=SttQuotaResponse)
async def stt_quota(_: Principal = Depends(require_staff_principal)) -> SttQuotaResponse:
    # Không cần đọc DB: hạn mức đếm từ sổ `llm_usage.jsonl` theo ngày.
    """Số phút audio đã dùng hôm nay và phần còn lại (`daily_budget_minutes = 0` nghĩa là không giới hạn)."""
    return SttQuotaResponse(**quota_report())


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(description="Audio ghi từ micro (webm/opus, wav, m4a, mp3…)."),
    language: str | None = Form(default=None, description="Bỏ trống = dùng STT_LANGUAGE (mặc định `vi`)."),
    hint: str | None = Form(default=None, description="Từ vựng mồi bổ sung cho lượt này (không chứa dữ liệu khách)."),
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> TranscribeResponse:
    """Nghe audio và trả về CHỮ. Không lưu audio ở bất kỳ đâu.

    Lỗi: 401 chưa đăng nhập · 413 quá dung lượng · 415 kiểu file lạ · 422 file rỗng ·
    429 hết hạn mức phút/ngày · 503 chưa cấu hình nhà cung cấp · 502 mọi nhà cung cấp đều lỗi.
    """
    settings = get_settings()
    # Nạp cấu hình ADMIN khai báo trong DB (DB đè .env) — cùng cách `tts_speak` nạp nhà cung cấp TTS.
    await refresh_stt_providers(session)
    if not settings.stt_enabled:
        raise HTTPException(status_code=503, detail="Chức năng nghe-nói đang tắt (STT_ENABLED=false).")
    if quota_exceeded(settings=settings):
        raise HTTPException(
            status_code=429,
            detail=(
                "Đã hết hạn mức nghe-nói trong ngày. Anh/chị gõ câu hỏi giúp em, "
                "hoặc quản trị viên tăng STT_DAILY_MINUTES_BUDGET."
            ),
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Kiểu audio '{content_type}' không được hỗ trợ. Dùng webm/opus, wav, m4a, mp3, ogg hoặc flac.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.stt_max_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Bản ghi âm vượt quá {settings.stt_max_bytes // 1_000_000} MB. "
                    f"Anh/chị nói ngắn lại (tối đa {settings.stt_max_duration_seconds} giây) giúp em."
                ),
            )
        chunks.append(chunk)
    audio = b"".join(chunks)
    if not audio:
        raise HTTPException(status_code=422, detail="Không có dữ liệu audio trong yêu cầu.")

    filename = (file.filename or "audio.webm").rsplit("/", 1)[-1][:120] or "audio.webm"
    bias = settings.stt_prompt
    if hint and hint.strip():
        bias = f"{bias}, {hint.strip()}"[:1_000]

    try:
        result = await transcribe_with_fallback(
            audio,
            filename=filename,
            language=language,
            prompt=bias,
            preferred=(settings.stt_provider or None),
            settings=settings,
            user_id=principal.user_id,
        )
    except SttError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc

    if not result.text.strip():
        result.warnings.append(
            "Nhà cung cấp trả về transcript rỗng — có thể do im lặng, micro bị chặn, hoặc tiếng ồn. "
            "Anh/chị nói lại gần micro hơn giúp em."
        )

    return TranscribeResponse(
        text=result.text,
        normalized_text=result.normalized_text,
        language=result.language,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        audio_bytes=result.audio_bytes,
        estimated_seconds=estimate_audio_seconds(result.audio_bytes),
        quota=quota_report(settings=settings),
        fallback_used=len([a for a in result.attempts if not a.get("ok")]) > 0,
        warnings=result.warnings,
    )


# --------------------------------------------------------------------------- #
# Đường quản trị (ADMIN): khai báo nhà cung cấp trong DB — DB đè .env
# --------------------------------------------------------------------------- #


@router.get("/providers")
async def list_providers(
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Danh mục nhà cung cấp (dựng sẵn + bản ghi DB), kèm trạng thái đã cấu hình và nguồn khoá."""
    _require_admin(principal, authorization)
    await refresh_stt_providers(session)
    rows = (await session.execute(select(STTProviderModel))).scalars().all()
    db_providers = {row.provider for row in rows}
    return {
        "catalog": provider_catalog_view(),
        "db_rows": [_view(row).model_dump() for row in rows],
        "effective_chain": stt_health_report()["active_chain"],
        "db_overrides": sorted(db_providers),
    }


@router.put("/providers/{provider}", response_model=SttProviderView)
async def upsert_provider(
    provider: str,
    payload: SttProviderUpsert,
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> SttProviderView:
    """Tạo/đè cấu hình một nhà cung cấp STT trong DB (khoá mã hoá Fernet, không bao giờ trả lại khoá thật)."""
    _require_admin(principal, authorization)
    slug = provider.strip().lower()
    if not slug:
        raise HTTPException(status_code=422, detail="Mã nhà cung cấp không được để trống.")
    builtin = get_stt_provider(slug, include_inactive=True)

    row = (
        await session.execute(select(STTProviderModel).where(STTProviderModel.provider == slug))
    ).scalars().first()
    if row is None:
        row = STTProviderModel(
            provider=slug,
            label=payload.label or (builtin.label if builtin else slug),
            mode=(builtin.mode if builtin else "api"),
            base_url=(builtin.base_url if builtin else "") or "",
            default_model=(builtin.default_model if builtin else "") or "",
            env_key=(builtin.env_key if builtin else "") or "",
            language=(builtin.language if builtin else "vi"),
            price_per_hour_audio=(builtin.price_per_hour_audio if builtin else 0.0),
            currency=(builtin.currency if builtin else "USD"),
            note=(builtin.note if builtin else "") or "",
            priority=int(builtin.priority if builtin else 50),
            is_active=bool(builtin.is_active if builtin else True),
            zero_data_retention=bool(get_settings().stt_zero_data_retention),
        )
        session.add(row)

    if payload.label is not None:
        row.label = payload.label.strip() or row.label
    if payload.base_url is not None:
        row.base_url = payload.base_url.strip() or None
    if payload.model is not None:
        row.default_model = payload.model.strip()
    if payload.language is not None:
        row.language = payload.language.strip() or "vi"
    if payload.priority is not None:
        row.priority = int(payload.priority)
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)
    if payload.zero_data_retention is not None:
        row.zero_data_retention = bool(payload.zero_data_retention)
    if payload.prompt_bias is not None:
        row.prompt_bias = payload.prompt_bias.strip()
    if payload.env_key is not None:
        row.env_key = payload.env_key.strip()
    if payload.price_per_hour_audio is not None:
        row.price_per_hour_audio = float(payload.price_per_hour_audio)
    if payload.currency is not None:
        row.currency = payload.currency.strip() or row.currency
    if payload.note is not None:
        row.note = payload.note.strip()
    if payload.api_key is not None:
        # Chuỗi rỗng = XOÁ khoá trong DB (quay về dùng .env). Không log giá trị khoá ở bất kỳ đâu.
        row.api_key_encrypted = encrypt_api_key(payload.api_key.strip())

    await session.commit()
    await session.refresh(row)
    await refresh_stt_providers(session)
    logger.info("ADMIN %s cập nhật cấu hình STT cho '%s'.", principal.user_id, slug)
    return _view(row)


@router.post("/providers/{provider}/test")
async def test_provider(
    provider: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Gửi 1 GIÂY IM LẶNG lên nhà cung cấp để kiểm tra khoá/URL/model (không cần thu âm, không tốn quota)."""
    _require_admin(principal, authorization)
    await refresh_stt_providers(session)
    slug = provider.strip().lower()
    result = await probe_provider(slug)

    row = (
        await session.execute(select(STTProviderModel).where(STTProviderModel.provider == slug))
    ).scalars().first()
    if row is not None:
        row.last_test_status = "ok" if result.get("ok") else "failed"
        row.last_test_latency_ms = float(result.get("latency_ms") or 0.0) or None
        row.last_tested_at = datetime.now(UTC)
        await session.commit()
    return {"provider": slug, "tested_by": principal.user_id, **result}


@router.delete("/providers/{provider}", status_code=status.HTTP_200_OK)
async def delete_provider(
    provider: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_staff_principal),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Xoá bản ghi ĐÈ trong DB → nhà cung cấp quay về cấu hình dựng sẵn + khoá trong `.env`."""
    _require_admin(principal, authorization)
    slug = provider.strip().lower()
    row = (
        await session.execute(select(STTProviderModel).where(STTProviderModel.provider == slug))
    ).scalars().first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Không có bản ghi DB nào cho nhà cung cấp '{slug}' (cấu hình đang đến từ danh mục/.env).",
        )
    await session.delete(row)
    await session.commit()
    await refresh_stt_providers(session)
    logger.info("ADMIN %s xoá cấu hình STT '%s' trong DB.", principal.user_id, slug)
    return {"status": "deleted", "provider": slug}
