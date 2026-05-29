from __future__ import annotations

import base64
import logging
from typing import Any

from app.llm.openrouter_common import (
    parse_completion_text,
    post_chat_completion,
    response_model_id,
)
from app.llm.types import AudioPart, ImagePart, LLMError, LLMRequest, LLMResponse, TextPart

logger = logging.getLogger(__name__)

_MIME_TO_FORMAT: dict[str, str] = {
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "audio/webm": "webm",
}


class OpenRouterProvider:
    """OpenRouter chat completions — text and voice (multimodal) in one model."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        default_max_output_tokens: int = 1024,
        max_retries: int = 3,
        retry_base_delay_seconds: float = 1.0,
        retry_max_delay_seconds: float = 8.0,
        timeout_seconds: float = 120.0,
        temperature: float = 0.8,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._default_max_output_tokens = default_max_output_tokens
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
        self._retry_max_delay_seconds = retry_max_delay_seconds
        self._timeout = timeout_seconds
        self._temperature = temperature

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def supports_audio_input(self) -> bool:
        return True

    @property
    def supports_image_input(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        user_content = _build_user_content(request.user_parts)
        if user_content is None:
            raise LLMError("No content for the model")

        max_tokens = request.max_output_tokens or self._default_max_output_tokens
        temperature = (
            request.temperature if request.temperature is not None else self._temperature
        )

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            body = await post_chat_completion(
                api_key=self._api_key,
                base_url=self._base_url,
                payload=payload,
                max_retries=self._max_retries,
                retry_base_delay_seconds=self._retry_base_delay_seconds,
                retry_max_delay_seconds=self._retry_max_delay_seconds,
                timeout_seconds=self._timeout,
                log_label="OpenRouter",
            )
        except Exception as exc:
            logger.exception("OpenRouter call failed")
            raise LLMError("OpenRouter request failed") from exc

        text = parse_completion_text(body)
        if not text:
            raise LLMError("OpenRouter returned no text")

        return LLMResponse(
            text=text.strip(),
            model=response_model_id(body, self._model),
            raw=body,
        )


def _build_user_content(
    parts: list[TextPart | AudioPart | ImagePart],
) -> str | list[dict[str, Any]] | None:
    text_blocks: list[str] = []
    media_blocks: list[dict[str, Any]] = []

    for part in parts:
        if isinstance(part, TextPart):
            if part.text.strip():
                text_blocks.append(part.text)
        elif isinstance(part, AudioPart):
            media_blocks.append(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(part.data).decode("ascii"),
                        "format": _mime_to_format(part.mime_type),
                    },
                }
            )
        else:
            media_blocks.append(_image_part_to_openrouter(part))

    if not text_blocks and not media_blocks:
        return None

    if not media_blocks:
        return "\n\n".join(text_blocks)

    content: list[dict[str, Any]] = []
    if text_blocks:
        content.append({"type": "text", "text": "\n\n".join(text_blocks)})
    content.extend(media_blocks)
    return content


def _image_part_to_openrouter(part: ImagePart) -> dict[str, Any]:
    mime = part.mime_type.lower().split(";")[0].strip()
    encoded = base64.b64encode(part.data).decode("ascii")
    if mime.startswith("video/"):
        return {
            "type": "video_url",
            "video_url": {"url": f"data:{mime};base64,{encoded}"},
        }
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{encoded}"},
    }


def _mime_to_format(mime_type: str) -> str:
    normalized = mime_type.lower().split(";")[0].strip()
    return _MIME_TO_FORMAT.get(normalized, "ogg")
