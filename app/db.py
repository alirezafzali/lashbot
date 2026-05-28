from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL,
    chat_id         BIGINT NOT NULL,
    user_id         BIGINT,
    username        TEXT,
    display_name    TEXT,
    message_type    TEXT NOT NULL,
    text_body       TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chat_id, telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created
    ON messages (chat_id, created_at DESC);
"""

INSERT_SQL = """
INSERT INTO messages (
    telegram_id, chat_id, user_id, username, display_name,
    message_type, text_body, metadata
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
ON CONFLICT (chat_id, telegram_id) DO NOTHING
"""

FETCH_LAST_N_SQL = """
SELECT telegram_id, chat_id, user_id, username, display_name,
       message_type, text_body, metadata, created_at
FROM messages
WHERE chat_id = $1
ORDER BY created_at DESC
LIMIT $2
"""


@dataclass(frozen=True)
class StoredMessage:
    telegram_id: int
    chat_id: int
    user_id: int | None
    username: str | None
    display_name: str | None
    message_type: str
    text_body: str | None
    metadata: dict[str, Any]
    created_at: datetime


class Database:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, database_url: str) -> Database:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def init_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        logger.info("Database schema ready")

    async def insert_message(
        self,
        *,
        telegram_id: int,
        chat_id: int,
        user_id: int | None,
        username: str | None,
        display_name: str | None,
        message_type: str,
        text_body: str | None,
        metadata: dict[str, Any],
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                INSERT_SQL,
                telegram_id,
                chat_id,
                user_id,
                username,
                display_name,
                message_type,
                text_body,
                json.dumps(metadata),
            )

    async def fetch_last_n(self, chat_id: int, limit: int) -> list[StoredMessage]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(FETCH_LAST_N_SQL, chat_id, limit)

        messages = [_row_to_message(row) for row in rows]
        messages.reverse()
        return messages


def _row_to_message(row: asyncpg.Record) -> StoredMessage:
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return StoredMessage(
        telegram_id=row["telegram_id"],
        chat_id=row["chat_id"],
        user_id=row["user_id"],
        username=row["username"],
        display_name=row["display_name"],
        message_type=row["message_type"],
        text_body=row["text_body"],
        metadata=metadata or {},
        created_at=row["created_at"],
    )
