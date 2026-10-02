"""Dựng client LLM theo cấu hình **DB trước, ENV sau** và gắn đo độ tiêu tốn.

- Admin khai báo nhà cung cấp + API key + đơn giá ngay trên giao diện → lưu DB (mã hoá).
- `get_llm()` lấy danh sách provider đang bật (theo `priority`) làm primary + fallback;
  chỉ khi DB chưa có khai báo nào mới rơi về ENV (`OPENAI_API_KEY`, `FALLBACK1_*`, `FALLBACK2_*`).
- Mỗi lượt gọi được ghi lại (token vào/ra, độ trễ, chi phí theo đơn giá) cho tab
  "Chi phí & hiệu năng" của trang quản trị.
"""

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.services.llm_providers import ProviderConfig, resolve_provider_configs
from src.services.llm_usage_callback import UsageTrackingHandler


def _create_chat_model(config: ProviderConfig, *, max_retries: int = 1) -> ChatOpenAI:
    kwargs = {
        "model": config.model_name,
        "api_key": config.api_key,
        "temperature": config.temperature,
        # Gắn handler đo usage cho đúng provider này (đơn giá nằm trong config).
        "callbacks": [UsageTrackingHandler(config)],
        "max_retries": max_retries,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    return ChatOpenAI(**kwargs)


def get_llm() -> Runnable:
    """Runnable chính: provider đầu tiên theo priority, các provider còn lại là fallback."""
    settings = get_settings()
    configs = resolve_provider_configs(settings)
    if not configs:
        # Không có DB lẫn ENV: vẫn dựng client "rỗng" như hành vi cũ để tầng gọi tự xử lý offline.
        configs = [
            ProviderConfig(
                provider_id="ENV-PRIMARY",
                name="ENV · primary (chưa cấu hình)",
                provider="openai",
                model_name=settings.model_name,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=settings.llm_temperature,
                source="env",
            )
        ]

    models = [_create_chat_model(cfg, max_retries=settings.llm_max_retries) for cfg in configs]
    primary, fallbacks = models[0], models[1:]
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


def describe_active_llm() -> dict[str, object]:
    """Thông tin ngắn về cấu hình đang có hiệu lực (cho trang quản trị hiển thị nguồn)."""
    from src.services.llm_providers import cache_source

    settings = get_settings()
    configs = resolve_provider_configs(settings)
    return {
        "source": cache_source(settings),
        "total": len(configs),
        "primary": f"{configs[0].provider}/{configs[0].model_name}" if configs else None,
    }
