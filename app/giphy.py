from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GIPHY_BASE_URL = "https://api.giphy.com/v1/gifs"


@dataclass(frozen=True)
class GiphyGif:
    id: str
    title: str
    gif_url: str
    mp4_url: str | None
    thumbnail_url: str


async def search_giphy(
    query: str,
    *,
    api_key: str,
    limit: int = 20,
    rating: str = "pg",
) -> list[GiphyGif]:
    params = {
        "api_key": api_key,
        "q": query,
        "limit": str(limit),
        "rating": rating,
    }
    body = await _get("/search", params)
    return _parse_results(body)


async def trending_giphy(
    *,
    api_key: str,
    limit: int = 20,
    rating: str = "pg",
) -> list[GiphyGif]:
    params = {
        "api_key": api_key,
        "limit": str(limit),
        "rating": rating,
    }
    body = await _get("/trending", params)
    return _parse_results(body)


async def pick_animation_url(
    query: str,
    *,
    api_key: str,
    rating: str = "pg",
) -> str | None:
    results = await search_giphy(
        query,
        api_key=api_key,
        limit=5,
        rating=rating,
    )
    if not results:
        return None

    chosen = results[0]
    return chosen.mp4_url or chosen.gif_url


async def _get(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = GIPHY_BASE_URL + path
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        if response.status_code >= 400:
            raise RuntimeError(
                f"GIPHY HTTP {response.status_code}: {response.text[:200]}"
            )
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("GIPHY returned invalid JSON")
        return body


def _parse_results(body: dict[str, Any]) -> list[GiphyGif]:
    data = body.get("data")
    if not isinstance(data, list):
        return []

    parsed: list[GiphyGif] = []
    for item in data:
        gif = _parse_one(item)
        if gif is not None:
            parsed.append(gif)
    return parsed


def _parse_one(item: object) -> GiphyGif | None:
    if not isinstance(item, dict):
        return None

    gif_id = item.get("id")
    if not isinstance(gif_id, str):
        return None

    title = item.get("title")
    if not isinstance(title, str):
        title = ""

    images = item.get("images")
    if not isinstance(images, dict):
        return None

    gif_url = _image_url(images, "downsized", "fixed_height", "original")
    if not gif_url:
        return None

    thumbnail = _image_url(
        images,
        "fixed_height_small_still",
        "preview_gif",
        "downsized_still",
        "original_still",
    ) or gif_url
    mp4_url = _image_mp4(images)

    return GiphyGif(
        id=gif_id,
        title=title,
        gif_url=gif_url,
        mp4_url=mp4_url,
        thumbnail_url=thumbnail,
    )


def _image_url(images: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        block = images.get(key)
        if isinstance(block, dict):
            url = block.get("url")
            if isinstance(url, str) and url:
                return url
    return None


def _image_mp4(images: dict[str, Any]) -> str | None:
    for key in ("original", "fixed_height", "downsized"):
        block = images.get(key)
        if isinstance(block, dict):
            mp4 = block.get("mp4")
            if isinstance(mp4, str) and mp4:
                return mp4
    return None
