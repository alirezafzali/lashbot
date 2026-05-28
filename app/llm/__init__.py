from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.types import LLMError

__all__ = ["LLMProvider", "LLMError", "create_llm_provider"]


def create_llm_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "gemini":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
            return GeminiProvider(
                api_key=settings.google_api_key,
                model=settings.gemini_model,
                default_max_output_tokens=settings.gemini_max_output_tokens,
            )
        case provider:
            raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
