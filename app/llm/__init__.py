from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.openrouter import OpenRouterProvider
from app.llm.types import LLMError

__all__ = ["LLMProvider", "LLMError", "create_llm_provider"]


def _openrouter_retry_kwargs(settings: Settings) -> dict:
    return {
        "max_retries": settings.openrouter_max_retries,
        "retry_base_delay_seconds": settings.openrouter_retry_base_delay_seconds,
        "retry_max_delay_seconds": settings.openrouter_retry_max_delay_seconds,
        "timeout_seconds": settings.openrouter_timeout_seconds,
    }


def create_llm_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider.lower():
        case "gemini":
            if not settings.google_api_key.strip():
                raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
            return GeminiProvider(
                api_key=settings.google_api_key,
                model=settings.gemini_model,
                default_max_output_tokens=settings.llm_max_output_tokens,
                max_retries=settings.gemini_max_retries,
                retry_base_delay_seconds=settings.gemini_retry_base_delay_seconds,
                retry_max_delay_seconds=settings.gemini_retry_max_delay_seconds,
            )
        case "openrouter":
            if not settings.openrouter_api_key.strip():
                raise ValueError(
                    "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter"
                )
            return OpenRouterProvider(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                base_url=settings.openrouter_base_url,
                default_max_output_tokens=settings.llm_max_output_tokens,
                **_openrouter_retry_kwargs(settings),
            )
        case provider:
            raise ValueError(
                f"Unknown LLM_PROVIDER: {provider}. Use 'openrouter' or 'gemini'."
            )
