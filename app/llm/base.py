from __future__ import annotations

from typing import Protocol

from app.llm.types import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def generate(self, request: LLMRequest) -> LLMResponse: ...
