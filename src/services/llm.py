from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from src.config import get_settings


def _create_chat_model(
    api_key: str,
    base_url: str | None,
    model_name: str,
    temperature: float,
    max_retries: int = 1,
) -> ChatOpenAI:
    kwargs = {
        "model": model_name,
        "api_key": api_key,
        "temperature": temperature,
        "max_retries": max_retries,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def get_llm() -> Runnable:
    settings = get_settings()

    primary_llm = _create_chat_model(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model_name=settings.model_name,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
    )

    fallbacks = []

    # Fallback 1
    if settings.fallback_openai_api_key and settings.fallback_model_name:
        fallbacks.append(
            _create_chat_model(
                api_key=settings.fallback_openai_api_key,
                base_url=settings.fallback_openai_base_url,
                model_name=settings.fallback_model_name,
                temperature=settings.llm_temperature,
                max_retries=settings.llm_max_retries,
            )
        )

    # Fallback 2
    if settings.fallback2_openai_api_key and settings.fallback2_model_name:
        fallbacks.append(
            _create_chat_model(
                api_key=settings.fallback2_openai_api_key,
                base_url=settings.fallback2_openai_base_url,
                model_name=settings.fallback2_model_name,
                temperature=settings.llm_temperature,
                max_retries=settings.llm_max_retries,
            )
        )

    if fallbacks:
        return primary_llm.with_fallbacks(fallbacks)

    return primary_llm
