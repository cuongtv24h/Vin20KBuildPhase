"""Callback LangChain ghi nhận token/độ trễ/chi phí của **mỗi lượt gọi LLM**.

Không đụng vào logic nghiệp vụ: gắn handler vào model lúc dựng client, handler tự đo
`on_llm_start` → `on_llm_end`/`on_llm_error` rồi gọi `llm_usage.record_usage` với đơn giá của
đúng nhà cung cấp đang phục vụ lượt đó.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from src.services import llm_usage
from src.services.llm_providers import ProviderConfig


def _extract_tokens(response: Any) -> tuple[int, int]:
    """Lấy (input_tokens, output_tokens) từ nhiều kiểu payload khác nhau của LangChain/OpenAI."""
    llm_output = getattr(response, "llm_output", None) or {}
    usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if usage:
        return int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0), int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
    generations = getattr(response, "generations", None) or []
    for generation in generations:
        for item in generation or []:
            message = getattr(item, "message", None)
            meta = getattr(message, "usage_metadata", None) or {}
            if meta:
                return int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)
    return 0, 0


class UsageTrackingHandler(BaseCallbackHandler):
    """Ghi usage cho mọi lượt gọi của một nhà cung cấp cụ thể."""

    def __init__(self, config: ProviderConfig, *, conversation_id: str | None = None, user_id: str | None = None):
        self.config = config
        self.conversation_id = conversation_id
        self.user_id = user_id
        self._started: dict[str, float] = {}

    # ─── Đo độ trễ ────────────────────────────────────────────────────────────
    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        run_id = kwargs.get("run_id")
        self._started[str(run_id or uuid.uuid4())] = time.perf_counter()

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        self.on_llm_start(serialized, [], **kwargs)

    def _latency_ms(self, kwargs: dict[str, Any]) -> float:
        run_id = str(kwargs.get("run_id") or "")
        started = self._started.pop(run_id, None)
        return (time.perf_counter() - started) * 1000.0 if started else 0.0

    # ─── Ghi nhận kết quả ────────────────────────────────────────────────────
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        input_tokens, output_tokens = _extract_tokens(response)
        llm_usage.record_usage(
            provider=self.config.provider,
            model_name=self.config.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=self._latency_ms(kwargs),
            ok=True,
            is_fallback=self.config.is_fallback,
            input_price_per_1m=self.config.input_price_per_1m,
            output_price_per_1m=self.config.output_price_per_1m,
            currency=self.config.currency,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        llm_usage.record_usage(
            provider=self.config.provider,
            model_name=self.config.model_name,
            latency_ms=self._latency_ms(kwargs),
            ok=False,
            error=str(error)[:300],
            is_fallback=self.config.is_fallback,
            input_price_per_1m=self.config.input_price_per_1m,
            output_price_per_1m=self.config.output_price_per_1m,
            currency=self.config.currency,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
        )
