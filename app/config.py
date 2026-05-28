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
    google_api_key: str = ""
    llm_provider: str = "gemini"
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = 1024

    database_url: str = "postgresql://lashbot:lashbot@localhost:5432/lashbot"
    recap_message_count: int = 50
    max_transcript_chars: int = 80_000
    chat_cooldown_seconds: float = 3.0

    allowed_chat_ids_raw: str = Field(default="", validation_alias="ALLOWED_CHAT_IDS")
    log_level: str = "INFO"

    @property
    def allowed_chat_ids(self) -> set[int] | None:
        return _parse_allowed_chat_ids(self.allowed_chat_ids_raw)
