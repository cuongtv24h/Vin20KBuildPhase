"""Khai báo nhà cung cấp LLM trong DB — Admin tự nhập trên giao diện.

Quy tắc ưu tiên (theo yêu cầu):
1. **DB trước**: các bản ghi `llm_providers` đang bật, xếp theo `priority` tăng dần → dùng làm
   primary + fallback theo thứ tự đó.
2. **ENV sau**: chỉ khi DB **chưa có bản ghi nào đang bật** mới dùng cấu hình ENV
   (`OPENAI_API_KEY`, `FALLBACK1_*`, `FALLBACK2_*`) như trước đây.

Vì `get_llm()` chạy đồng bộ trong luồng async, danh sách provider được nạp vào cache qua đường
async (`refresh_provider_cache`), gọi ở lúc khởi động và sau mỗi thao tác CRUD của Admin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.config import get_settings
from src.services.llm_secrets import decrypt_api_key

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Cấu hình một nhà cung cấp đã sẵn sàng dựng client."""

    provider_id: str
    name: str
    provider: str
    model_name: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.2
    priority: int = 10
    input_price_per_1m: float = 0.0
    output_price_per_1m: float = 0.0
    currency: str = "USD"
    source: str = "db"  # 'db' | 'env'
    is_fallback: bool = False


#: None = chưa nạp từ DB; [] = đã nạp và DB trống → dùng ENV.
_CACHE: list[ProviderConfig] | None = None


def _env_configs(settings: Any | None = None) -> list[ProviderConfig]:
    """Cấu hình dựng từ ENV (đường lui khi DB chưa khai báo gì).

    `settings` truyền vào để tầng gọi dùng đúng object Settings của mình (test patch được).
    """
    settings = settings or get_settings()
    configs: list[ProviderConfig] = []
    if settings.openai_api_key:
        configs.append(
            ProviderConfig(
                provider_id="ENV-PRIMARY",
                name="ENV · primary",
                provider="openai",
                model_name=settings.model_name,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=settings.llm_temperature,
                priority=0,
                source="env",
            )
        )
    if settings.fallback_openai_api_key and settings.fallback_model_name:
        configs.append(
            ProviderConfig(
                provider_id="ENV-FALLBACK-1",
                name="ENV · fallback 1",
                provider="openai",
                model_name=settings.fallback_model_name,
                api_key=settings.fallback_openai_api_key,
                base_url=settings.fallback_openai_base_url,
                temperature=settings.llm_temperature,
                priority=1,
                source="env",
                is_fallback=True,
            )
        )
    if settings.fallback2_openai_api_key and settings.fallback2_model_name:
        configs.append(
            ProviderConfig(
                provider_id="ENV-FALLBACK-2",
                name="ENV · fallback 2",
                provider="openai",
                model_name=settings.fallback2_model_name,
                api_key=settings.fallback2_openai_api_key,
                base_url=settings.fallback2_openai_base_url,
                temperature=settings.llm_temperature,
                priority=2,
                source="env",
                is_fallback=True,
            )
        )
    return configs


def resolve_provider_configs(settings: Any | None = None) -> list[ProviderConfig]:
    """Danh sách provider đang dùng: DB (ưu tiên) → ENV (chỉ khi DB trống)."""
    if _CACHE:
        return list(_CACHE)
    env_configs = _env_configs(settings)
    if _CACHE is None and env_configs:
        logger.debug("Chưa nạp provider từ DB — tạm dùng cấu hình ENV.")
    return env_configs


def resolve_provider_for_model(model_name: str | None) -> ProviderConfig | None:
    """Tìm cấu hình khớp model (dùng để quy đơn giá khi ghi usage)."""
    for cfg in resolve_provider_configs():
        if model_name and cfg.model_name == model_name:
            return cfg
    return None


def cache_source(settings: Any | None = None) -> str:
    """Nguồn cấu hình đang có hiệu lực: 'db' | 'env' | 'none'."""
    if _CACHE:
        return "db"
    return "env" if _env_configs(settings) else "none"


def set_provider_cache(configs: list[ProviderConfig] | None) -> None:
    """Ghi đè cache (test dùng trực tiếp; app dùng `refresh_provider_cache`)."""
    global _CACHE
    _CACHE = list(configs) if configs is not None else None


async def refresh_provider_cache(session: Any | None = None) -> list[ProviderConfig]:
    """Nạp lại danh sách provider đang bật từ DB vào cache.

    Gọi ở lúc khởi động và sau mỗi thao tác thêm/sửa/xoá của Admin. Truyền `session` (endpoint
    đang có phiên DB) để dùng chung phiên — nhờ vậy test với SQLite in-memory cũng nạp đúng.
    Lỗi DB (chưa tạo bảng, DB xuống) không được làm sập luồng chat — chỉ log và rơi về ENV.
    """
    global _CACHE
    from contextlib import asynccontextmanager

    from sqlalchemy import select

    from src.db.models import LLMProviderModel

    @asynccontextmanager
    async def _session_scope():
        if session is not None:
            yield session
        else:
            from src.db.session import async_session_factory

            async with async_session_factory() as owned:
                yield owned

    try:
        async with _session_scope() as active:
            rows = (
                (
                    await active.execute(
                        select(LLMProviderModel)
                        .where(LLMProviderModel.is_active.is_(True))
                        .order_by(LLMProviderModel.priority.asc(), LLMProviderModel.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
    except Exception as exc:  # noqa: BLE001 — DB chưa sẵn sàng thì vẫn phải chat được bằng ENV
        logger.warning("Không nạp được nhà cung cấp LLM từ DB (%s) — dùng ENV nếu có.", exc)
        return resolve_provider_configs()

    configs = [
        ProviderConfig(
            provider_id=row.provider_id,
            name=row.name,
            provider=row.provider,
            model_name=row.model_name,
            api_key=decrypt_api_key(row.api_key_encrypted),
            base_url=row.base_url,
            temperature=float(row.temperature or 0.2),
            priority=int(row.priority or 10),
            input_price_per_1m=float(row.input_price_per_1m or 0.0),
            output_price_per_1m=float(row.output_price_per_1m or 0.0),
            currency=row.currency or "USD",
            source="db",
            is_fallback=index > 0,
        )
        for index, row in enumerate(rows)
        if decrypt_api_key(row.api_key_encrypted)
    ]
    _CACHE = configs
    logger.info("Đã nạp %d nhà cung cấp LLM từ DB.", len(configs))
    return list(configs)


def reset_provider_cache() -> None:
    """Xoá cache (test)."""
    global _CACHE
    _CACHE = None
