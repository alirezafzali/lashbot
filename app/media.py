from __future__ import annotations

from dataclasses import dataclass

from telegram import Audio, Message, Voice
from telegram.ext import ContextTypes

VOICE_MIME = "audio/ogg"
MAX_VISUAL_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class VisualAttachment:
    file_id: str
    mime_type: str
    kind: str


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


def find_visual_attachment(message: Message) -> VisualAttachment | None:
    if message.photo:
        photo = message.photo[-1]
        return VisualAttachment(
            file_id=photo.file_id,
            mime_type="image/jpeg",
            kind="photo",
        )

    if message.animation:
        animation = message.animation
        mime = getattr(animation, "mime_type", None) or "video/mp4"
        return VisualAttachment(
            file_id=animation.file_id,
            mime_type=mime,
            kind="animation",
        )

    if message.sticker and not message.sticker.is_video and not message.sticker.is_animated:
        return VisualAttachment(
            file_id=message.sticker.file_id,
            mime_type="image/webp",
            kind="sticker",
        )

    if message.document:
        doc = message.document
        mime = (doc.mime_type or "").lower()
        if mime.startswith("image/"):
            return VisualAttachment(
                file_id=doc.file_id,
                mime_type=mime,
                kind="document",
            )

    return None


async def download_visual(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    max_bytes: int = MAX_VISUAL_BYTES,
) -> tuple[bytes, str, str] | None:
    attachment = find_visual_attachment(message)
    if not attachment:
        return None

    telegram_file = await context.bot.get_file(attachment.file_id)
    data = bytes(await telegram_file.download_as_bytearray())
    if len(data) > max_bytes:
        data = data[:max_bytes]

    return data, attachment.mime_type, attachment.kind
