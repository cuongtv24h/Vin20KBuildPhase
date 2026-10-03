"""Quản trị nhà cung cấp TTS & khoá API (chỉ ADMIN) — **dùng lại cơ chế của nhà cung cấp LLM**.

Yêu cầu người dùng (đợt 22): *“Dùng sẵn cơ chế cũ đã có, cho phép thêm mới nhà cung cấp ngoài các nhà
cung cấp sẵn.”* Nghĩa là:

- Khoá API nhập trên giao diện, lưu DB **đã mã hoá Fernet**, API chỉ trả dạng che (`sk-…abcd`) — y hệt
  `llm_admin.py` (dùng chung `llm_secrets`).
- Thứ tự ưu tiên **DB → ENV** (ENV chỉ dùng khi DB chưa có khoá cho nhà cung cấp đó).
- Có nút **Test kết nối** như tab “Nhà cung cấp LLM”.
- Cho phép **thêm nhà cung cấp mới** (self-host, gateway nội bộ, nhà cung cấp ngoài danh mục), không chỉ
  nhập khoá cho các nhà cung cấp dựng sẵn.

Khác một điểm so với LLM: một bản ghi có thể là **bản ghi đè** của nhà cung cấp dựng sẵn (sửa nhãn, đơn
giá, giọng, nhập khoá) — nhận biết bằng `provider` (slug) trùng mã trong danh mục.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, get_current_principal
from src.db.models import TTSProviderModel, TTSSettingsModel
from src.db.session import get_db_session
from src.services import tts_providers
from src.services.llm_secrets import encrypt_api_key, mask_api_key
from src.services.tts_probe import probe_tts_provider

router = APIRouter(prefix="/admin/tts", tags=["admin-tts"])

#: Nhãn cho nguồn khoá — UI hiển thị để Admin biết khoá đang lấy từ đâu.
KEY_SOURCE_LABELS = {
    "db": "DB (nhập trên giao diện)",
    "env": "ENV máy chủ",
    "llm": "dùng chung khoá nhà cung cấp LLM",
    "browser": "không cần khoá (đọc tại trình duyệt)",
    "none": "chưa có khoá",
}


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    """Khoá API là tài sản hạ tầng → chỉ Quản trị viên hệ thống."""
    if not principal.has_role("ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên hệ thống được cấu hình nhà cung cấp TTS.",
        )
    return principal


class TtsProviderPayload(BaseModel):
    """Dữ liệu tạo/sửa nhà cung cấp TTS. `api_key` để trống khi sửa = giữ khoá cũ."""

    provider: str = Field(..., min_length=1, max_length=48, description="Mã nhà cung cấp (slug), ví dụ vieneu")
    label: str = Field(..., min_length=1, max_length=128)
    mode: str = Field("api", description="api | browser")
    base_url: str | None = None
    default_model: str = Field("", max_length=128)
    env_key: str = Field("", max_length=64, description="Tên biến ENV chứa khoá (đường lui khi DB trống)")
    price_per_1m_chars: float = Field(0.0, ge=0)
    currency: str = Field("USD", max_length=8)
    price_note: str = ""
    verified_at: str = Field("", max_length=16)
    note: str = ""
    #: Mỗi dòng một giọng: `mã | nhãn | giới tính` (giới tính có thể bỏ trống).
    voices_text: str = Field("", description="Danh sách giọng, mỗi dòng 'mã | nhãn | giới tính'")
    supports_streaming: bool = False
    voice_cloning: bool = False
    api_key: str | None = Field(None, description="Bỏ trống khi sửa để giữ nguyên khoá cũ")
    priority: int = Field(50, ge=0, le=999, description="Số nhỏ hiện trước")
    is_active: bool = True


class TtsProviderView(BaseModel):
    provider: str
    provider_id: str = ""
    label: str
    mode: str
    base_url: str = ""
    default_model: str = ""
    env_key: str = ""
    price_per_1m_chars: float = 0.0
    currency: str = "USD"
    price_note: str = ""
    verified_at: str = ""
    note: str = ""
    voices: list[dict[str, str]] = Field(default_factory=list)
    supports_streaming: bool = False
    voice_cloning: bool = False
    priority: int = 50
    is_active: bool = True
    #: True khi KHÔNG nằm trong danh mục dựng sẵn (do Admin tự thêm).
    custom: bool = False
    #: True khi đã có bản ghi DB (bản ghi đè hoặc nhà cung cấp mới).
    has_db_row: bool = False
    api_key_configured: bool = False
    api_key_masked: str = ""
    key_source: str = "none"
    key_source_label: str = ""
    last_test_status: str | None = None
    last_test_latency_ms: float | None = None
    last_tested_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TtsProviderListResponse(BaseModel):
    source: str = Field(..., description="'db' nếu có bản ghi trong DB, 'env'/'builtin' nếu chỉ có danh mục")
    total: int
    items: list[TtsProviderView]


class TtsProviderTestResult(BaseModel):
    provider: str
    ok: bool
    latency_ms: float
    status: str
    detail: str
    method: str | None = None
    url: str | None = None


def _parse_voices(voices_text: str, fallback: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    """`mã | nhãn | giới tính` mỗi dòng → danh sách giọng. Để trống = giữ danh sách hiện có."""
    text = (voices_text or "").strip()
    if not text:
        return list(fallback or [])
    voices: list[dict[str, str]] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if not parts or not parts[0]:
            continue
        voices.append(
            {
                "code": parts[0],
                "label": parts[1] if len(parts) > 1 and parts[1] else parts[0],
                "gender": (parts[2] if len(parts) > 2 and parts[2] else "neutral"),
            }
        )
    return voices


def _to_view(cfg: tts_providers.TtsProviderConfig, *, settings: Any | None = None) -> TtsProviderView:
    """`TtsProviderConfig` → view cho UI: chỉ trả khoá dạng CHE, kèm nguồn khoá."""
    source = tts_providers.provider_key_source(cfg, settings=settings)
    masked = mask_api_key(cfg.db_api_key) if cfg.db_api_key else ""
    return TtsProviderView(
        provider=cfg.provider,
        provider_id=cfg.provider_id,
        label=cfg.label,
        mode=cfg.mode,
        base_url=cfg.base_url,
        default_model=cfg.default_model,
        env_key=cfg.env_key,
        price_per_1m_chars=cfg.price_per_1m_chars,
        currency=cfg.currency,
        price_note=cfg.price_note,
        verified_at=cfg.verified_at,
        note=cfg.note,
        voices=[{"code": v.code, "label": v.label, "gender": v.gender} for v in cfg.voices],
        supports_streaming=cfg.supports_streaming,
        voice_cloning=cfg.voice_cloning,
        is_active=cfg.is_active,
        custom=cfg.custom,
        has_db_row=bool(cfg.provider_id),
        api_key_configured=source != "none",
        api_key_masked=masked,
        key_source=source,
        key_source_label=KEY_SOURCE_LABELS.get(source, source),
    )


async def _rows(session: AsyncSession) -> list[TTSProviderModel]:
    result = await session.execute(select(TTSProviderModel).order_by(TTSProviderModel.priority.asc()))
    return list(result.scalars().all())


async def _load_and_refresh(session: AsyncSession) -> list[tts_providers.TtsProviderConfig]:
    """Nạp bản ghi DB vào bộ nhớ danh mục rồi trả danh mục hiệu lực (gồm cả nhà cung cấp đang tắt)."""
    await tts_providers.refresh_tts_providers(session)
    return tts_providers.resolve_tts_providers(include_inactive=True)


def _row_or_404(rows: list[TTSProviderModel], provider_id: str) -> TTSProviderModel:
    for row in rows:
        if row.provider_id == provider_id:
            return row
    raise HTTPException(status_code=404, detail=f"Không có bản ghi nhà cung cấp TTS '{provider_id}'.")


@router.get("/providers", response_model=TtsProviderListResponse)
async def list_tts_providers(
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> TtsProviderListResponse:
    """Danh mục nhà cung cấp TTS hiệu lực: dựng sẵn + bản ghi Admin thêm/đè. Khoá chỉ hiển thị dạng che."""
    rows = await _rows(session)
    catalog = await _load_and_refresh(session)
    by_provider = {str(row.provider).strip().lower(): row for row in rows}
    items: list[TtsProviderView] = []
    for cfg in catalog:
        view = _to_view(cfg)
        row = by_provider.get(cfg.provider)
        if row is not None:
            view.last_test_status = row.last_test_status
            view.last_test_latency_ms = row.last_test_latency_ms
            view.last_tested_at = row.last_tested_at.isoformat() if row.last_tested_at else None
            view.priority = int(row.priority or 50)
            view.created_at = row.created_at.isoformat() if row.created_at else None
            view.updated_at = row.updated_at.isoformat() if row.updated_at else None
        items.append(view)
    return TtsProviderListResponse(
        source="db" if rows else "builtin",
        total=len(items),
        items=items,
    )


@router.post("/providers", response_model=TtsProviderView, status_code=status.HTTP_201_CREATED)
async def create_tts_provider(
    payload: TtsProviderPayload,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> TtsProviderView:
    """Thêm nhà cung cấp mới **hoặc** tạo bản ghi đè cho nhà cung cấp dựng sẵn (theo mã `provider`)."""
    slug = payload.provider.strip().lower()
    rows = await _rows(session)
    existing = next((r for r in rows if str(r.provider).strip().lower() == slug), None)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Nhà cung cấp '{slug}' đã có bản ghi — dùng nút Sửa để cập nhật thay vì thêm mới. "
                f"(provider_id: {existing.provider_id})"
            ),
        )
    if payload.mode == "api" and not (payload.api_key or "").strip():
        raise HTTPException(status_code=422, detail="Cần nhập API key cho nhà cung cấp mới.")

    builtin = next((cfg for cfg in tts_providers.TTS_PROVIDER_CATALOG if cfg.provider == slug), None)
    row = TTSProviderModel(
        provider=slug,
        label=payload.label.strip(),
        mode=payload.mode.strip().lower(),
        base_url=(payload.base_url or "").strip() or (builtin.base_url if builtin else None),
        default_model=payload.default_model.strip() or (builtin.default_model if builtin else ""),
        env_key=(payload.env_key or "").strip().upper() or (builtin.env_key if builtin else ""),
        price_per_1m_chars=payload.price_per_1m_chars,
        currency=payload.currency.upper(),
        price_note=payload.price_note.strip(),
        verified_at=payload.verified_at.strip(),
        note=payload.note.strip(),
        voices_json=json.dumps(
            _parse_voices(
                payload.voices_text,
                fallback=[{"code": v.code, "label": v.label, "gender": v.gender} for v in (builtin.voices if builtin else ())],
            ),
            ensure_ascii=False,
        ),
        supports_streaming=payload.supports_streaming,
        voice_cloning=payload.voice_cloning,
        api_key_encrypted=encrypt_api_key((payload.api_key or "").strip()),
        priority=payload.priority,
        is_active=payload.is_active,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    catalog = await _load_and_refresh(session)
    cfg = next((c for c in catalog if c.provider == slug), None)
    assert cfg is not None  # vừa ghi DB thì danh mục phải có
    view = _to_view(cfg)
    view.last_test_status = row.last_test_status
    view.created_at = row.created_at.isoformat() if row.created_at else None
    return view


@router.put("/providers/{provider_id}", response_model=TtsProviderView)
async def update_tts_provider(
    provider_id: str,
    payload: TtsProviderPayload,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> TtsProviderView:
    """Cập nhật bản ghi nhà cung cấp; để trống `api_key` nghĩa là **giữ khoá cũ**."""
    row = _row_or_404(await _rows(session), provider_id)
    new_slug = payload.provider.strip().lower()
    if new_slug != str(row.provider).strip().lower():
        clash = next(
            (r for r in await _rows(session) if str(r.provider).strip().lower() == new_slug and r.provider_id != provider_id),
            None,
        )
        if clash is not None:
            raise HTTPException(status_code=409, detail=f"Nhà cung cấp '{new_slug}' đã có bản ghi khác.")
        row.provider = new_slug
    row.label = payload.label.strip()
    row.mode = payload.mode.strip().lower()
    row.base_url = (payload.base_url or "").strip() or None
    row.default_model = payload.default_model.strip()
    row.env_key = (payload.env_key or "").strip().upper()
    row.price_per_1m_chars = payload.price_per_1m_chars
    row.currency = payload.currency.upper()
    row.price_note = payload.price_note.strip()
    row.verified_at = payload.verified_at.strip()
    row.note = payload.note.strip()
    if payload.voices_text.strip():
        row.voices_json = json.dumps(_parse_voices(payload.voices_text), ensure_ascii=False)
    row.supports_streaming = payload.supports_streaming
    row.voice_cloning = payload.voice_cloning
    if (payload.api_key or "").strip():
        row.api_key_encrypted = encrypt_api_key(payload.api_key.strip())
    row.priority = payload.priority
    row.is_active = payload.is_active
    await session.commit()
    await session.refresh(row)
    catalog = await _load_and_refresh(session)
    cfg = next((c for c in catalog if c.provider_id == provider_id), None)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Bản ghi vừa cập nhật không còn trong danh mục.")
    view = _to_view(cfg)
    view.last_test_status = row.last_test_status
    view.last_test_latency_ms = row.last_test_latency_ms
    view.updated_at = row.updated_at.isoformat() if row.updated_at else None
    return view


@router.delete("/providers/{provider_id}", status_code=status.HTTP_200_OK)
async def delete_tts_provider(
    provider_id: str,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Xoá bản ghi (nhà cung cấp dựng sẵn chỉ mất phần đè, vẫn còn trong danh mục; nhà cung cấp tự thêm thì biến mất)."""
    row = _row_or_404(await _rows(session), provider_id)
    provider = str(row.provider).strip().lower()
    builtin = any(cfg.provider == provider for cfg in tts_providers.TTS_PROVIDER_CATALOG)
    # Đang có người chọn nhà cung cấp này để đọc? Nói ra để giao diện cảnh báo, thay vì để họ tự phát hiện
    # giọng đọc đã đổi (backend sẽ tự rơi về giọng trình duyệt khi nhà cung cấp không còn).
    used_by_scopes = (
        await session.execute(
            select(func.count()).select_from(TTSSettingsModel).where(func.lower(TTSSettingsModel.provider) == provider)
        )
    ).scalar_one()
    await session.delete(row)
    await session.commit()
    await _load_and_refresh(session)
    return {
        "ok": True,
        "provider_id": provider_id,
        "provider": provider,
        "still_available": builtin,
        "used_by_scopes": int(used_by_scopes or 0),
    }


@router.post("/providers/{provider_ref}/test", response_model=TtsProviderTestResult)
async def test_tts_provider_endpoint(
    provider_ref: str,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> TtsProviderTestResult:
    """Kiểm tra kết nối thật tới nhà cung cấp (không tính phí tổng hợp — chỉ gọi endpoint danh mục/model).

    `provider_ref` nhận **cả hai** dạng: `provider_id` của bản ghi DB, hoặc **mã nhà cung cấp** dựng sẵn
    (ví dụ `openai`) để kiểm tra ngay khoá đang có trong ENV/kho LLM mà không cần tạo bản ghi trước.
    """
    rows = await _rows(session)
    row = next((r for r in rows if r.provider_id == provider_ref), None)
    catalog = await _load_and_refresh(session)
    slug = provider_ref.strip().lower()
    cfg = next(
        (c for c in catalog if c.provider_id == provider_ref or c.provider == slug),
        None,
    )
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy nhà cung cấp TTS '{provider_ref}' để kiểm tra.")
    api_key = tts_providers.resolve_provider_api_key(cfg)
    result = await probe_tts_provider(
        provider=cfg.provider,
        base_url=cfg.base_url,
        api_key=api_key,
        mode=cfg.mode,
        env_key=cfg.env_key,
    )
    if row is not None:  # nhà cung cấp dựng sẵn chưa có bản ghi thì chỉ kiểm tra, không ghi lịch sử
        row.last_test_status = result.status
        row.last_test_latency_ms = result.latency_ms
        row.last_tested_at = datetime.now(UTC)
        await session.commit()
    return TtsProviderTestResult(
        provider=cfg.provider,
        ok=result.ok,
        latency_ms=result.latency_ms,
        status=result.status,
        detail=result.detail,
        method=result.method,
        url=result.url,
    )
