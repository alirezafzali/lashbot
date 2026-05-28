# lashbot

A Dockerized Telegram group companion bot. It logs group messages to Postgres, chats like a friend when @mentioned or replied to, and can recap recent messages or summarize voice notes via Gemini (behind a swappable LLM adapter).

## Prerequisites

1. Create a bot with [@BotFather](https://t.me/BotFather) and note the token and username (e.g. `@lashbot`).
2. **Disable privacy mode** so the bot receives all group messages: `/setprivacy` → **Disable**.
3. Get a [Google AI Studio](https://aistudio.google.com/apikey) API key (`GOOGLE_API_KEY`).

## Quick start

```bash
cp .env.example .env
# Edit .env: TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY

docker compose up --build
```

Add the bot to your friends group. Talk to it by **@mentioning** it or **replying** to one of its messages.

## Examples

- `@lashbot catch me up`
- `@lashbot summarize the last messages`
- Reply to a voice note, mention the bot: `@lashbot what did they say?`

## Configuration

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `GOOGLE_API_KEY` | Gemini API key |
| `LLM_PROVIDER` | `gemini` (default); extend under `app/llm/` |
| `GEMINI_MODEL` | e.g. `gemini-2.5-flash` |
| `RECAP_MESSAGE_COUNT` | Messages loaded for context (default 50) |
| `MAX_TRANSCRIPT_CHARS` | Cap on transcript size sent to the LLM |
| `ALLOWED_CHAT_IDS` | Optional comma-separated allowlist |

## Limitations

- Recap/history only includes messages **since the bot was added** to the group.
- The bot only replies when @mentioned or when you reply to its message.

## Swapping the LLM later

1. Implement `LLMProvider` in a new file under `app/llm/`.
2. Register it in `create_llm_provider()` in `app/llm/__init__.py`.
3. Set `LLM_PROVIDER` in `.env`.

Handlers do not import Gemini directly.

## Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Run Postgres and set DATABASE_URL in .env
python -m app.main
```
