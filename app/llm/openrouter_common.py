from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

DEFAULT_HEADERS_EXTRA = {
    "HTTP-Referer": "https://github.com/lashbot",
    "X-Title": "lashbot",
}


def openrouter_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **DEFAULT_HEADERS_EXTRA,
    }


def chat_completions_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def parse_completion_text(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts) if parts else None
    return None


def response_model_id(body: object, fallback: str) -> str:
    if isinstance(body, dict):
        model = body.get("model")
        if isinstance(model, str):
            return model
    return fallback


async def post_chat_completion(
    *,
    api_key: str,
    base_url: str,
    payload: dict[str, Any],
    max_retries: int,
    retry_base_delay_seconds: float,
    retry_max_delay_seconds: float,
    timeout_seconds: float,
    log_label: str,
) -> dict[str, Any]:
    url = chat_completions_url(base_url)
    headers = openrouter_headers(api_key)
    max_attempts = max(0, max_retries) + 1
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= max_attempts:
                    logger.exception(
                        "%s request failed (attempt %s/%s)",
                        log_label,
                        attempt,
                        max_attempts,
                    )
                    raise
                delay = retry_delay_seconds(
                    attempt, retry_base_delay_seconds, retry_max_delay_seconds
                )
                logger.warning(
                    "%s network error (attempt %s/%s), retrying in %.1fs: %s",
                    log_label,
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES:
                last_error = RuntimeError(
                    f"{log_label} HTTP {response.status_code}: {response.text[:200]}"
                )
                if attempt >= max_attempts:
                    logger.error(
                        "%s failed after %s attempts: %s",
                        log_label,
                        max_attempts,
                        response.text[:500],
                    )
                    raise last_error
                delay = retry_delay_seconds(
                    attempt, retry_base_delay_seconds, retry_max_delay_seconds
                )
                logger.warning(
                    "%s HTTP %s (attempt %s/%s), retrying in %.1fs",
                    log_label,
                    response.status_code,
                    attempt,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 400:
                logger.error(
                    "%s client error %s: %s",
                    log_label,
                    response.status_code,
                    response.text[:500],
                )
                raise RuntimeError(
                    f"{log_label} HTTP {response.status_code}: {response.text[:200]}"
                )

            if attempt > 1:
                logger.info(
                    "%s succeeded on attempt %s/%s",
                    log_label,
                    attempt,
                    max_attempts,
                )
            return response.json()

    raise RuntimeError(f"{log_label} request failed") from last_error


def retry_delay_seconds(attempt: int, base_delay: float, max_delay: float) -> float:
    delay = base_delay * (2 ** (attempt - 1))
    return min(delay, max_delay)
