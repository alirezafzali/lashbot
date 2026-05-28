from __future__ import annotations

import asyncio
import logging
import sys

from telegram.ext import Application, MessageHandler, filters

from app.config import Settings
from app.db import Database
from app.handlers import BotContext, create_group_message_handler
from app.llm import create_llm_provider

logger = logging.getLogger(__name__)

POSTGRES_RETRY_SECONDS = 2
POSTGRES_MAX_ATTEMPTS = 30


async def _wait_for_database(database_url: str) -> Database:
    last_error: Exception | None = None
    for attempt in range(1, POSTGRES_MAX_ATTEMPTS + 1):
        try:
            db = await Database.connect(database_url)
            await db.init_schema()
            logger.info("Connected to Postgres (attempt %s)", attempt)
            return db
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Postgres not ready (attempt %s/%s): %s",
                attempt,
                POSTGRES_MAX_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(POSTGRES_RETRY_SECONDS)

    raise RuntimeError("Could not connect to Postgres") from last_error


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    llm = create_llm_provider(settings)
    db_holder: dict[str, Database | None] = {"db": None}

    async def post_init(app: Application) -> None:
        db_holder["db"] = await _wait_for_database(settings.database_url)
        me = await app.bot.get_me()
        bot_ctx = BotContext(
            settings=settings,
            db=db_holder["db"],
            llm=llm,
            bot_id=me.id,
            bot_username=me.username or "",
        )
        app.add_handler(
            MessageHandler(
                filters.ChatType.GROUPS & ~filters.COMMAND,
                create_group_message_handler(bot_ctx),
            )
        )
        model_label = (
            settings.openrouter_model
            if settings.llm_provider.lower() == "openrouter"
            else settings.gemini_model
        )
        logger.info(
            "lashbot ready as @%s (provider=%s, model=%s)",
            bot_ctx.bot_username,
            settings.llm_provider,
            model_label,
        )

    async def post_shutdown(app: Application) -> None:
        db = db_holder.get("db")
        if db is not None:
            await db.close()
            logger.info("Postgres connection closed")

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    try:
        application.run_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
