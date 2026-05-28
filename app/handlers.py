from __future__ import annotations

import logging
import time
from typing import Any

from telegram import Message, Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import ContextTypes

from app.config import Settings
from app.db import Database
from app.llm.base import LLMProvider
from app.llm.types import AudioPart, LLMError, LLMRequest, TextPart
from app.media import download_voice_or_audio
from app.prompts import SYSTEM_PROMPT
from app.transcript import build_transcript
from app.trigger import is_triggered

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
_SERVICE_MESSAGE_ATTRS = (
    "new_chat_members",
    "left_chat_member",
    "new_chat_title",
    "new_chat_photo",
    "delete_chat_photo",
    "group_chat_created",
    "supergroup_chat_created",
    "channel_chat_created",
    "migrate_to_chat_id",
    "migrate_from_chat_id",
    "pinned_message",
    "proximity_alert_triggered",
    "video_chat_scheduled",
    "video_chat_started",
    "video_chat_ended",
    "video_chat_participants_invited",
    "message_auto_delete_timer_changed",
    "forum_topic_created",
    "forum_topic_closed",
    "forum_topic_reopened",
    "forum_topic_edited",
    "general_forum_topic_hidden",
    "general_forum_topic_unhidden",
    "write_access_allowed",
    "user_shared",
    "chat_shared",
)


class BotContext:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        llm: LLMProvider,
        bot_id: int,
        bot_username: str,
    ) -> None:
        self.settings = settings
        self.db = db
        self.llm = llm
        self.bot_id = bot_id
        self.bot_username = bot_username
        self._last_reply_at: dict[int, float] = {}


def create_group_message_handler(bot_ctx: BotContext):
    async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message or not message.chat:
            return

        chat = message.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        if not _is_chat_allowed(chat.id, bot_ctx.settings):
            return

        parsed = _parse_message(message)
        if parsed is None:
            return

        message_type, text_body, metadata = parsed
        user = message.from_user

        await bot_ctx.db.insert_message(
            telegram_id=message.message_id,
            chat_id=chat.id,
            user_id=user.id if user else None,
            username=user.username if user else None,
            display_name=_display_name(user),
            message_type=message_type,
            text_body=text_body,
            metadata=metadata,
        )

        if not is_triggered(update, bot_ctx.bot_id, bot_ctx.bot_username):
            return

        if _is_on_cooldown(bot_ctx, chat.id):
            logger.info("Skipping reply due to cooldown chat_id=%s", chat.id)
            return

        await _handle_triggered_reply(update, context, bot_ctx, message)

    return on_group_message


def _is_chat_allowed(chat_id: int, settings: Settings) -> bool:
    allowed = settings.allowed_chat_ids
    if allowed is None:
        return True
    return chat_id in allowed


def _is_on_cooldown(bot_ctx: BotContext, chat_id: int) -> bool:
    now = time.monotonic()
    last = bot_ctx._last_reply_at.get(chat_id, 0.0)
    if now - last < bot_ctx.settings.chat_cooldown_seconds:
        return True
    bot_ctx._last_reply_at[chat_id] = now
    return False


async def _handle_triggered_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    bot_ctx: BotContext,
    message: Message,
) -> None:
    chat_id = message.chat_id

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    stored = await bot_ctx.db.fetch_last_n(
        chat_id,
        bot_ctx.settings.recap_message_count,
    )
    transcript = build_transcript(stored, bot_ctx.settings.max_transcript_chars)

    user_text = _strip_bot_mention(
        message.text or message.caption or "",
        bot_ctx.bot_username,
    ).strip()

    user_parts: list[TextPart | AudioPart] = []

    if transcript:
        user_parts.append(
            TextPart(
                text=(
                    "Recent group chat transcript (oldest to newest):\n"
                    f"{transcript}"
                )
            )
        )
    else:
        user_parts.append(
            TextPart(
                text=(
                    "Recent group chat transcript: (empty — bot has little "
                    "or no history for this chat yet)"
                )
            )
        )

    if user_text:
        user_parts.append(TextPart(text=f"User message:\n{user_text}"))
    else:
        user_parts.append(TextPart(text="User message: (no text, see attachment if any)"))

    replied = message.reply_to_message
    if replied and (replied.voice or replied.audio):
        audio = await download_voice_or_audio(replied, context)
        if audio:
            data, mime_type = audio
            await _add_voice_context(user_parts, bot_ctx, data, mime_type, chat_id)

    request = LLMRequest(
        system_instruction=SYSTEM_PROMPT,
        user_parts=user_parts,
        max_output_tokens=bot_ctx.settings.llm_max_output_tokens,
    )

    try:
        start = time.monotonic()
        response = await bot_ctx.llm.generate(request)
        elapsed = time.monotonic() - start
        logger.info(
            "LLM reply chat_id=%s provider=%s model=%s elapsed=%.2fs",
            chat_id,
            bot_ctx.llm.name,
            response.model,
            elapsed,
        )
        reply_text = response.text
    except LLMError:
        logger.exception("LLM failed chat_id=%s", chat_id)
        reply_text = "Brain freeze — try again in a moment."
    except Exception:
        logger.exception("Unexpected error during LLM call chat_id=%s", chat_id)
        reply_text = "Something went wrong on my end. Try again?"

    for chunk in _split_message(reply_text):
        await message.reply_text(chunk)


async def _add_voice_context(
    user_parts: list[TextPart | AudioPart],
    bot_ctx: BotContext,
    data: bytes,
    mime_type: str,
    chat_id: int,
) -> None:
    if getattr(bot_ctx.llm, "supports_audio_input", False):
        user_parts.append(
            TextPart(
                text=(
                    "The user is replying to a voice/audio message. "
                    "Listen to the attached audio, then answer their question."
                )
            )
        )
        user_parts.append(AudioPart(data=data, mime_type=mime_type))
        return

    logger.warning("LLM does not support audio chat_id=%s", chat_id)
    user_parts.append(
        TextPart(
            text=(
                "The user replied to a voice message but this model cannot "
                "process audio. Ask them to type their question, or set "
                "OPENROUTER_MODEL to a multimodal model (e.g. google/gemini-2.5-flash)."
            )
        )
    )


def _parse_message(message: Message) -> tuple[str, str | None, dict[str, Any]] | None:
    if _is_service_message(message):
        return None

    user = message.from_user
    base_meta: dict[str, Any] = {}
    if message.entities:
        base_meta["entities"] = [
            {"type": entity.type, "offset": entity.offset, "length": entity.length}
            for entity in message.entities
        ]

    if message.text:
        return "text", message.text, base_meta

    if message.photo:
        photo = message.photo[-1]
        meta = {
            **base_meta,
            "file_id": photo.file_id,
            "width": photo.width,
            "height": photo.height,
        }
        return "photo", message.caption, meta

    if message.video:
        meta = {
            **base_meta,
            "file_id": message.video.file_id,
            "mime_type": message.video.mime_type,
            "duration": message.video.duration,
            "width": message.video.width,
            "height": message.video.height,
        }
        return "video", message.caption, meta

    if message.document:
        meta = {
            **base_meta,
            "file_id": message.document.file_id,
            "mime_type": message.document.mime_type,
            "file_name": message.document.file_name,
        }
        return "document", message.caption, meta

    if message.sticker:
        meta = {
            **base_meta,
            "file_id": message.sticker.file_id,
            "emoji": message.sticker.emoji,
            "set_name": message.sticker.set_name,
        }
        return "sticker", None, meta

    if message.voice:
        meta = {
            **base_meta,
            "file_id": message.voice.file_id,
            "mime_type": message.voice.mime_type,
            "duration": message.voice.duration,
        }
        return "voice", None, meta

    if message.audio:
        meta = {
            **base_meta,
            "file_id": message.audio.file_id,
            "mime_type": message.audio.mime_type,
            "duration": message.audio.duration,
            "title": message.audio.title,
        }
        return "audio", None, meta

    return None


def _is_service_message(message: Message) -> bool:
    return any(getattr(message, attr, None) for attr in _SERVICE_MESSAGE_ATTRS)


def _display_name(user: Any) -> str | None:
    if not user:
        return None
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or None


def _strip_bot_mention(text: str, bot_username: str) -> str:
    if not text:
        return text
    needle = f"@{bot_username.lstrip('@')}"
    return text.replace(needle, "").replace(needle.lower(), "").strip()


def _split_message(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks
