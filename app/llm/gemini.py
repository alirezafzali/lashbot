from __future__ import annotations

import logging

from google import genai
from google.genai import types

from app.llm.types import AudioPart, LLMError, LLMRequest, LLMResponse, TextPart

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        default_max_output_tokens: int = 1024,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._default_max_output_tokens = default_max_output_tokens

    @property
    def name(self) -> str:
        return "gemini"

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

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
        except Exception as exc:
            logger.exception("Gemini API call failed")
            raise LLMError("Gemini request failed") from exc

        text = _extract_text(response)
        if not text:
            raise LLMError("Gemini returned no text (safety block or empty response)")

        return LLMResponse(text=text.strip(), model=self._model, raw=response)


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
