from __future__ import annotations

import asyncio
import logging

from google import genai
from google.genai import types
from google.genai.errors import APIError, ServerError

from app.llm.types import AudioPart, LLMError, LLMRequest, LLMResponse, TextPart

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class GeminiProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        default_max_output_tokens: int = 1024,
        max_retries: int = 3,
        retry_base_delay_seconds: float = 1.0,
        retry_max_delay_seconds: float = 8.0,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._default_max_output_tokens = default_max_output_tokens
        self._max_retries = max(0, max_retries)
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supports_audio_input(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        parts = [_content_part_to_gemini(part) for part in request.user_parts]
        max_tokens = request.max_output_tokens or self._default_max_output_tokens

        config_kwargs: dict = {
            "system_instruction": request.system_instruction,
            "max_output_tokens": max_tokens,
        }
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature

        config = types.GenerateContentConfig(**config_kwargs)
        contents = [types.Content(role="user", parts=parts)]

        max_attempts = self._max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt >= max_attempts:
                    logger.exception(
                        "Gemini API call failed (attempt %s/%s)",
                        attempt,
                        max_attempts,
                    )
                    raise LLMError("Gemini request failed") from exc

                delay = _retry_delay_seconds(
                    attempt,
                    self._retry_base_delay_seconds,
                    self._retry_max_delay_seconds,
                )
                logger.warning(
                    "Gemini retryable error (attempt %s/%s, code=%s), "
                    "retrying in %.1fs: %s",
                    attempt,
                    max_attempts,
                    _error_code(exc),
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
                continue

            text = _extract_text(response)
            if not text:
                raise LLMError("Gemini returned no text (safety block or empty response)")

            if attempt > 1:
                logger.info("Gemini succeeded on attempt %s/%s", attempt, max_attempts)

            return LLMResponse(text=text.strip(), model=self._model, raw=response)

        raise LLMError("Gemini request failed") from last_error


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ServerError):
        return True
    if isinstance(exc, APIError):
        return exc.code in _RETRYABLE_STATUS_CODES
    return False


def _error_code(exc: Exception) -> int | str:
    if isinstance(exc, APIError):
        return exc.code
    return "unknown"


def _retry_delay_seconds(
    attempt: int,
    base_delay: float,
    max_delay: float,
) -> float:
    delay = base_delay * (2 ** (attempt - 1))
    return min(delay, max_delay)


def _content_part_to_gemini(part: TextPart | AudioPart) -> types.Part:
    if isinstance(part, TextPart):
        return types.Part.from_text(text=part.text)
    return types.Part.from_bytes(data=part.data, mime_type=part.mime_type)


def _extract_text(response: object) -> str | None:
    text = getattr(response, "text", None)
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                return part_text
    return None
