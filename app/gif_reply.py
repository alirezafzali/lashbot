from __future__ import annotations

import re

SEND_GIF_PATTERN = re.compile(r"^SEND_GIF:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def parse_send_gif_marker(text: str) -> tuple[str, str | None]:
    match = SEND_GIF_PATTERN.search(text)
    if not match:
        return text.strip(), None

    query = match.group(1).strip()
    clean = SEND_GIF_PATTERN.sub("", text).strip()
    return clean, query or None
