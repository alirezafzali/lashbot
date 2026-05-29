from __future__ import annotations

import logging

from telegram import InlineQueryResultGif, InlineQueryResultMpeg4Gif, Update
from telegram.ext import ContextTypes

from app.config import Settings
from app.giphy import search_giphy, trending_giphy

logger = logging.getLogger(__name__)

INLINE_CACHE_SECONDS = 300
INLINE_RESULT_LIMIT = 20


def create_inline_query_handler(settings: Settings):
    async def on_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        inline_query = update.inline_query
        if not inline_query:
            return

        if not settings.giphy_api_key.strip():
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

        query = (inline_query.query or "").strip()
        try:
            if query:
                gifs = await search_giphy(
                    query,
                    api_key=settings.giphy_api_key,
                    limit=INLINE_RESULT_LIMIT,
                    rating=settings.giphy_rating,
                )
            else:
                gifs = await trending_giphy(
                    api_key=settings.giphy_api_key,
                    limit=INLINE_RESULT_LIMIT,
                    rating=settings.giphy_rating,
                )
        except Exception:
            logger.exception("GIPHY inline search failed query=%r", query)
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

        results = []
        for index, gif in enumerate(gifs):
            result_id = f"{gif.id}:{index}"
            if gif.mp4_url:
                results.append(
                    InlineQueryResultMpeg4Gif(
                        id=result_id,
                        mpeg4_url=gif.mp4_url,
                        thumbnail_url=gif.thumbnail_url,
                        title=gif.title[:64] if gif.title else None,
                    )
                )
            else:
                results.append(
                    InlineQueryResultGif(
                        id=result_id,
                        gif_url=gif.gif_url,
                        thumbnail_url=gif.thumbnail_url,
                        title=gif.title[:64] if gif.title else None,
                    )
                )

        await inline_query.answer(
            results,
            cache_time=INLINE_CACHE_SECONDS,
            is_personal=False,
        )

    return on_inline_query
