from __future__ import annotations

from telegram import Message, MessageEntity, Update


def is_triggered(update: Update, bot_id: int, bot_username: str) -> bool:
    message = update.effective_message
    if not message:
        return False

    if _mentions_bot(message, bot_id, bot_username):
        return True

    return _is_reply_to_bot(message, bot_id)


def _mentions_bot(message: Message, bot_id: int, bot_username: str) -> bool:
    if not message.entities or not message.text:
        return False

    username_lower = bot_username.lower().lstrip("@")
    for entity in message.entities:
        if entity.type == MessageEntity.MENTION:
            mention = message.text[entity.offset : entity.offset + entity.length]
            if mention.lower().lstrip("@") == username_lower:
                return True
        if entity.type == MessageEntity.TEXT_MENTION:
            user = entity.user
            if user and user.id == bot_id:
                return True
    return False


def _is_reply_to_bot(message: Message, bot_id: int) -> bool:
    replied = message.reply_to_message
    if not replied or not replied.from_user:
        return False
    return replied.from_user.id == bot_id
