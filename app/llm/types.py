from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class AudioPart:
    data: bytes
    mime_type: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    mime_type: str


ContentPart = Union[TextPart, AudioPart, ImagePart]


@dataclass(frozen=True)
class LLMRequest:
    system_instruction: str
    user_parts: list[ContentPart]
    max_output_tokens: int | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str | None = None
    raw: object | None = None


class LLMError(Exception):
    """Raised when the LLM provider fails or returns no usable content."""
