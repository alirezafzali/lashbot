from __future__ import annotations

from app.db import StoredMessage

_TYPE_LABELS = {
    "photo": "[photo]",
    "video": "[video]",
    "document": "[document]",
    "sticker": "[sticker]",
    "voice": "[voice]",
    "audio": "[audio]",
}


def build_transcript(messages: list[StoredMessage], max_chars: int) -> str:
    if not messages:
        return ""

    lines: list[str] = []
    for msg in messages:
        lines.append(_format_line(msg))

    full = "\n".join(lines)
    if len(full) <= max_chars:
        return full

    truncated_lines: list[str] = []
    total = 0
    for line in reversed(lines):
        extra = len(line) + (1 if truncated_lines else 0)
        if total + extra > max_chars:
            break
        truncated_lines.insert(0, line)
        total += extra

    if not truncated_lines:
        return full[-max_chars:]

    return "\n".join(truncated_lines)


def _format_line(msg: StoredMessage) -> str:
    ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
    speaker = _speaker_name(msg)
    body = _message_body(msg)
    return f"[{ts}] {speaker}: {body}"


def _speaker_name(msg: StoredMessage) -> str:
    if msg.display_name:
        return msg.display_name
    if msg.username:
        return f"@{msg.username}"
    if msg.user_id is not None:
        return f"user_{msg.user_id}"
    return "unknown"


def _message_body(msg: StoredMessage) -> str:
    if msg.text_body:
        if msg.message_type == "text":
            return msg.text_body
        return f"{_type_label(msg)} {msg.text_body}"

    label = _type_label(msg)
    duration = msg.metadata.get("duration")
    if duration is not None and msg.message_type in ("voice", "audio", "video"):
        return f"{label} ({_format_duration(duration)})"
    return label


def _type_label(msg: StoredMessage) -> str:
    return _TYPE_LABELS.get(msg.message_type, f"[{msg.message_type}]")


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"
