from __future__ import annotations

from telegram import Audio, Message, Voice
from telegram.ext import ContextTypes

VOICE_MIME = "audio/ogg"


async def download_voice_or_audio(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[bytes, str] | None:
    attachment: Voice | Audio | None = message.voice or message.audio
    if not attachment:
        return None

    telegram_file = await context.bot.get_file(attachment.file_id)
    data = bytes(await telegram_file.download_as_bytearray())
    mime_type = getattr(attachment, "mime_type", None) or VOICE_MIME
    return data, mime_type
