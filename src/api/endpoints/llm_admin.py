"""Quản trị nhà cung cấp LLM & đo độ tiêu tốn (chỉ ADMIN).

Bối cảnh: trước đây muốn đổi API key/model phải sửa `.env` rồi deploy lại. Bộ endpoint này cho
Admin tự khai báo **nhà cung cấp API + API key + đơn giá** ngay trên giao diện:

- `GET/POST/PUT/DELETE /admin/llm/providers` — CRUD; API key lưu DB dạng mã hoá, trả về dạng che.
- `POST /admin/llm/providers/{id}/test` — kiểm tra kết nối thật (gọi `/models` của nhà cung cấp).
- `GET /admin/llm/usage/summary` + `/admin/llm/usage/records` — tab "Chi phí & hiệu năng":
  token, chi phí theo đơn giá, p50/p95 độ trễ, tỉ lệ lỗi.

Thứ tự ưu tiên khi chạy: DB (theo `priority`) → ENV (chỉ khi DB trống) — xem `llm_providers`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, get_current_principal
from src.db.models import LLMProviderModel
from src.db.session import get_db_session
from src.services import llm_usage
from src.services.llm_probe import probe_llm_provider
from src.services.llm_providers import _env_configs, cache_source, refresh_provider_cache
from src.services.llm_secrets import decrypt_api_key, encrypt_api_key, mask_api_key

router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    """Khoá API là tài sản hạ tầng → chỉ Quản trị viên hệ thống."""
    if not principal.has_role("ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên hệ thống được cấu hình nhà cung cấp LLM.",
        )
    return principal


class LLMProviderPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field("openai", description="openai | azure | openrouter | groq | custom")
    base_url: str | None = None
    model_name: str = Field(..., min_length=1, max_length=128)
    api_key: str | None = Field(None, description="Bỏ trống khi sửa để giữ nguyên khoá cũ")
    input_price_per_1m: float = Field(0.0, ge=0, description="Đơn giá token vào / 1 triệu token")
    output_price_per_1m: float = Field(0.0, ge=0, description="Đơn giá token ra / 1 triệu token")
    currency: str = Field("USD", max_length=8)
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    priority: int = Field(10, ge=0, le=999, description="Số nhỏ chạy trước (primary là 0-10)")
    is_active: bool = True


class LLMProviderView(BaseModel):
    provider_id: str
    name: str
    provider: str
    base_url: str | None = None
    model_name: str
    api_key_masked: str = ""
    has_api_key: bool = False
    input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    currency: str = "USD"
    temperature: float = 0.2
    priority: int = 10
    is_active: bool = True
    last_test_status: str | None = None
    last_test_latency_ms: float | None = None
    last_tested_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LlmEnvProviderView(BaseModel):
    """Nhà cung cấp **đọc từ biến môi trường máy chủ** — chỉ để hiển thị, không sửa/xoá được từ giao diện.

    Vì sao cần: khi DB trống, hệ thống chạy bằng cấu hình ENV (thường là 2: `ENV · primary` +
    `ENV · fallback 1`), nhưng bảng quản trị chỉ liệt kê bản ghi DB nên hiện “Chưa khai báo nhà cung cấp
    nào” — quản trị viên không thấy mình đang có những nhà cung cấp nào, cũng không biết thêm mới từ đâu.
    Khoá ở đây **chỉ trả dạng che**, đúng nguyên tắc của tab này.
    """

    provider_id: str
    name: str
    provider: str
    base_url: str | None = None
    model_name: str
    api_key_masked: str
    has_api_key: bool = True
    priority: int
    is_fallback: bool = False
    #: Khai báo `provider` này đã có bản ghi trong DB chưa (nếu có thì bản ghi DB đang thắng ENV).
    overridden_by_db: bool = False
    source: str = "env"


class LLMProviderListResponse(BaseModel):
    source: str = Field(..., description="'db' nếu đang dùng khai báo trong DB, 'env' nếu rơi về ENV")
    total: int
    items: list[LLMProviderView]
    #: Nhà cung cấp đang có trong ENV của máy chủ (chỉ-đọc) — để màn hình nói đủ sự thật.
    env_items: list[LlmEnvProviderView] = Field(default_factory=list)


class ProviderTestResult(BaseModel):
    provider_id: str
    ok: bool
    latency_ms: float
    status: str
    detail: str


def _env_provider_views(*, db_provider_codes: set[str] | None = None) -> list[LlmEnvProviderView]:
    """Nhà cung cấp dựng từ ENV (`ENV · primary`, `ENV · fallback 1`…) ở dạng chỉ-đọc, khoá đã che."""
    try:
        configs = _env_configs()
    except Exception:  # noqa: BLE001 — thiếu cấu hình không được làm hỏng màn hình quản trị
        return []
    overridden = db_provider_codes or set()
    views: list[LlmEnvProviderView] = []
    for cfg in configs:
        key = str(getattr(cfg, "api_key", "") or "")
        views.append(
            LlmEnvProviderView(
                provider_id=str(getattr(cfg, "provider_id", "")),
                name=str(getattr(cfg, "name", "")),
                provider=str(getattr(cfg, "provider", "")),
                base_url=getattr(cfg, "base_url", None),
                model_name=str(getattr(cfg, "model_name", "")),
                api_key_masked=mask_api_key(key),
                has_api_key=bool(key),
                priority=int(getattr(cfg, "priority", 0) or 0),
                is_fallback=bool(getattr(cfg, "is_fallback", False)),
                overridden_by_db=str(getattr(cfg, "provider", "")).strip().lower() in overridden,
            )
        )
    return views


def _to_view(row: LLMProviderModel) -> LLMProviderView:
    return LLMProviderView(
        provider_id=row.provider_id,
        name=row.name,
        provider=row.provider,
        base_url=row.base_url,
        model_name=row.model_name,
        api_key_masked=mask_api_key(row.api_key_encrypted),
        has_api_key=bool(row.api_key_encrypted),
        input_price_per_1m=float(row.input_price_per_1m or 0.0),
        output_price_per_1m=float(row.output_price_per_1m or 0.0),
        currency=row.currency or "USD",
        temperature=float(row.temperature or 0.2),
        priority=int(row.priority or 10),
        is_active=bool(row.is_active),
        last_test_status=row.last_test_status,
        last_test_latency_ms=row.last_test_latency_ms,
        last_tested_at=row.last_tested_at.isoformat() if row.last_tested_at else None,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


async def _get_or_404(session: AsyncSession, provider_id: str) -> LLMProviderModel:
    row = (
        await session.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy nhà cung cấp '{provider_id}'.")
    return row


@router.get("/providers", response_model=LLMProviderListResponse)
async def list_providers(
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> LLMProviderListResponse:
    """Danh sách nhà cung cấp Admin đã khai báo (API key chỉ hiển thị dạng che)."""
    rows = (
        (await session.execute(select(LLMProviderModel).order_by(LLMProviderModel.priority.asc())))
        .scalars()
        .all()
    )
    await refresh_provider_cache(session)
    return LLMProviderListResponse(
        source=cache_source(),
        total=len(rows),
        items=[_to_view(r) for r in rows],
        env_items=_env_provider_views(db_provider_codes={str(r.provider).strip().lower() for r in rows}),
    )


@router.post("/providers", response_model=LLMProviderView, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: LLMProviderPayload,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> LLMProviderView:
    """Thêm nhà cung cấp mới. API key được mã hoá trước khi lưu."""
    if not (payload.api_key or "").strip():
        raise HTTPException(status_code=422, detail="Cần nhập API key cho nhà cung cấp mới.")
    row = LLMProviderModel(
        name=payload.name.strip(),
        provider=payload.provider.strip().lower(),
        base_url=(payload.base_url or "").strip() or None,
        model_name=payload.model_name.strip(),
        api_key_encrypted=encrypt_api_key(payload.api_key.strip()),
        input_price_per_1m=payload.input_price_per_1m,
        output_price_per_1m=payload.output_price_per_1m,
        currency=payload.currency.upper(),
        temperature=payload.temperature,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await refresh_provider_cache(session)
    return _to_view(row)


@router.put("/providers/{provider_id}", response_model=LLMProviderView)
async def update_provider(
    provider_id: str,
    payload: LLMProviderPayload,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> LLMProviderView:
    """Cập nhật cấu hình; để trống `api_key` nghĩa là giữ nguyên khoá cũ."""
    row = await _get_or_404(session, provider_id)
    row.name = payload.name.strip()
    row.provider = payload.provider.strip().lower()
    row.base_url = (payload.base_url or "").strip() or None
    row.model_name = payload.model_name.strip()
    if (payload.api_key or "").strip():
        row.api_key_encrypted = encrypt_api_key(payload.api_key.strip())
    row.input_price_per_1m = payload.input_price_per_1m
    row.output_price_per_1m = payload.output_price_per_1m
    row.currency = payload.currency.upper()
    row.temperature = payload.temperature
    row.priority = payload.priority
    row.is_active = payload.is_active
    await session.commit()
    await session.refresh(row)
    await refresh_provider_cache(session)
    return _to_view(row)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_200_OK)
async def delete_provider(
    provider_id: str,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await _get_or_404(session, provider_id)
    await session.delete(row)
    await session.commit()
    await refresh_provider_cache(session)
    return {"ok": True, "provider_id": provider_id}


@router.post("/providers/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: str,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ProviderTestResult:
    """Kiểm tra kết nối thật tới nhà cung cấp và ghi lại kết quả.

    Việc gọi mạng nằm ở `src/services/llm_probe.py` (test được, không cần DB): ưu tiên `GET /models`,
    tự thử tiếp `POST /chat/completions` — endpoint ứng dụng thật dùng, cũng là đường đi qua được
    Cloudflare khi nhà cung cấp chặn client lạ. Lỗi trả về luôn là câu đọc được, không đổ HTML thô.
    """
    # Nhận cả bản ghi DB **lẫn** nhà cung cấp đọc từ ENV (`ENV-PRIMARY`, `ENV-FALLBACK-1`…): quản trị viên
    # phải kiểm tra được 2 nhà cung cấp đang chạy thật trước khi quyết định thêm nhà cung cấp mới.
    env_cfg = next((c for c in _env_configs() if str(c.provider_id) == provider_id), None)
    if env_cfg is not None:
        probe = await probe_llm_provider(
            env_cfg.base_url,
            str(env_cfg.api_key or ""),
            env_cfg.model_name,
        )
        return ProviderTestResult(
            provider_id=provider_id,
            ok=probe.ok,
            latency_ms=probe.latency_ms,
            status=probe.status,
            detail=probe.detail,
        )

    row = await _get_or_404(session, provider_id)
    probe = await probe_llm_provider(
        row.base_url,
        decrypt_api_key(row.api_key_encrypted),
        row.model_name,
    )

    row.last_test_status = probe.status
    row.last_test_latency_ms = probe.latency_ms
    row.last_tested_at = datetime.now(UTC)
    await session.commit()
    return ProviderTestResult(
        provider_id=provider_id,
        ok=probe.ok,
        latency_ms=probe.latency_ms,
        status=probe.status,
        detail=probe.detail,
    )


class UsageSummaryResponse(BaseModel):
    window_days: int
    total_calls: int
    failed_calls: int
    error_rate: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    currency: str
    p50_latency_ms: float
    p95_latency_ms: float
    avg_cost_per_call: float
    by_provider: list[dict[str, Any]]
    by_day: list[dict[str, Any]]


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def usage_summary(
    days: int = Query(14, ge=1, le=365),
    _: Principal = Depends(require_admin),
) -> UsageSummaryResponse:
    """Tổng hợp token/chi phí/độ trễ theo đơn giá Admin đã khai báo."""
    return UsageSummaryResponse(**llm_usage.summarize_usage(days))


class UsageRecordsResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


@router.get("/usage/records", response_model=UsageRecordsResponse)
async def usage_records(
    limit: int = Query(50, ge=1, le=500),
    _: Principal = Depends(require_admin),
) -> UsageRecordsResponse:
    """Log các lượt gọi gần nhất để đối chiếu chi phí thực tế."""
    items = llm_usage.recent_usage(limit)
    return UsageRecordsResponse(total=len(items), items=items)
