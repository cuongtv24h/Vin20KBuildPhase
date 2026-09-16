from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage

from src.config import Settings
from src.services.llm import get_llm


def test_get_llm_default():
    mock_settings = Settings(
        openai_api_key="sk-test",
        model_name="gpt-4o-mini",
        openai_base_url=None,
    )
    with patch("src.services.llm.get_settings", return_value=mock_settings):
        llm = get_llm()
        assert llm.model_name == "gpt-4o-mini"
        assert str(llm.openai_api_key.get_secret_value()) == "sk-test"


def test_get_llm_openai_compatible():
    mock_settings = Settings(
        openai_api_key="gsk-test",
        openai_base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.3-70b-versatile",
    )
    with patch("src.services.llm.get_settings", return_value=mock_settings):
        llm = get_llm()
        assert llm.model_name == "llama-3.3-70b-versatile"
        assert str(llm.openai_api_base) == "https://api.groq.com/openai/v1"


def test_get_llm_with_fallbacks_configuration():
    mock_settings = Settings(
        openai_api_key="primary-key",
        openai_base_url="https://api.groq.com/openai/v1",
        model_name="primary-model",
        fallback_openai_api_key="fb1-key",
        fallback_openai_base_url="https://api.deepseek.com/v1",
        fallback_model_name="fb1-model",
        fallback2_openai_api_key="fb2-key",
        fallback2_model_name="fb2-model",
    )
    with patch("src.services.llm.get_settings", return_value=mock_settings):
        llm = get_llm()
        # Should be wrapped in RunnableWithFallbacks
        assert hasattr(llm, "fallbacks")
        assert len(llm.fallbacks) == 2
        # Check primary runnable
        assert llm.runnable.model_name == "primary-model"
        # Check fallbacks
        assert llm.fallbacks[0].model_name == "fb1-model"
        assert str(llm.fallbacks[0].openai_api_base) == "https://api.deepseek.com/v1"
        assert llm.fallbacks[1].model_name == "fb2-model"


@pytest.mark.asyncio
async def test_fallback_execution_on_error():
    mock_settings = Settings(
        openai_api_key="primary-key",
        model_name="primary-model",
        fallback_openai_api_key="fb-key",
        fallback_model_name="fb-model",
    )
    with patch("src.services.llm.get_settings", return_value=mock_settings):
        llm = get_llm()

        call_count = 0

        async def fake_ainvoke(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if self.model_name == "primary-model":
                raise RuntimeError("Primary 429 Rate Limit Exceeded")
            return AIMessage(content="Fallback answer")

        with patch("langchain_openai.ChatOpenAI.ainvoke", new=fake_ainvoke):
            response = await llm.ainvoke("Hi")
            assert response.content == "Fallback answer"
            assert call_count == 2
