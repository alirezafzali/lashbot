from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_allowed_chat_ids(value: str) -> set[int] | None:
    stripped = value.strip()
    if not stripped:
        return None
    return {int(part.strip()) for part in stripped.split(",") if part.strip()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str

    llm_provider: str = "openrouter"
    llm_max_output_tokens: int = 1024

    openrouter_api_key: str = ""
    # One multimodal model for chat + voice (production Gemini via OpenRouter)
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_max_retries: int = 3
    openrouter_retry_base_delay_seconds: float = 1.0
    openrouter_retry_max_delay_seconds: float = 8.0
    openrouter_timeout_seconds: float = 120.0

    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_max_retries: int = 3
    gemini_retry_base_delay_seconds: float = 1.0
    gemini_retry_max_delay_seconds: float = 8.0

    database_url: str = "postgresql://lashbot:lashbot@localhost:5432/lashbot"
    recap_message_count: int = 50
    max_transcript_chars: int = 80_000
    chat_cooldown_seconds: float = 3.0

    allowed_chat_ids_raw: str = Field(default="", validation_alias="ALLOWED_CHAT_IDS")
    log_level: str = "INFO"

    @property
    def allowed_chat_ids(self) -> set[int] | None:
        return _parse_allowed_chat_ids(self.allowed_chat_ids_raw)
