# lashbot

Telegram **group** companion bot: logs chat history to Postgres, replies only when @mentioned or when someone replies to the bot. Uses a pluggable LLM adapter; default is **OpenRouter** with one multimodal model for text and voice.

## What it does

- **Ingests** messages in groups/supergroups (text, media labels, voice metadata) into Postgres for context.
- **Replies** on `@lashbot …` or a **reply to the bot** — not on every message.
- **Recaps** recent chat from stored history (`RECAP_MESSAGE_COUNT`).
- **Voice notes**: downloads audio and sends it to the same model in one API call (no separate STT step on OpenRouter).
- **Cooldown** per chat to avoid spam (`CHAT_COOLDOWN_SECONDS`).
- Optional **chat allowlist** via `ALLOWED_CHAT_IDS`.

Personality and tone live in `app/prompts.py` (short, in-group “one of the boys” vibe).

## Prerequisites

1. **[@BotFather](https://t.me/BotFather)** — create a bot, copy the token.
2. **Privacy mode off** — `/setprivacy` → **Disable** (bot must see group messages to build history).
3. **[OpenRouter](https://openrouter.ai)** API key with credit (default provider).
4. **Docker** (recommended) or Python 3.12+ and Postgres 16 for local dev.

## Quick start (Docker)

```bash
cp .env.example .env
# Set TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY

docker compose up --build
```

In `.env` for Compose, use:

```env
DATABASE_URL=postgresql://lashbot:lashbot@postgres:5432/lashbot
```

Add the bot to your group, then test with `@YourBot hey` or a reply to one of its messages.

Success in logs:

```text
Connected to Postgres
lashbot ready as @YourBot (provider=openrouter, model=google/gemini-2.5-flash)
```

## Deploy on a VPS

Long polling — no public URL or reverse proxy required.

1. **Stop** any other instance using the same bot token (only one poller per token).
2. Copy or clone the repo on the server; create `.env` there (`chmod 600 .env`).
3. Run:

```bash
docker compose up -d --build
docker compose logs -f bot
```

**Sizing:** 1 vCPU and **1 GB RAM** is enough for Postgres + the bot; LLM runs on OpenRouter, not on the VPS. Open **SSH (22)** only; the bot needs outbound HTTPS.

| Step | Detail |
|------|--------|
| `DATABASE_URL` on server | Host must be `postgres`, not `localhost` |
| Updates | `git pull` (or rsync) then `docker compose up -d --build` |
| Wipe history | `docker compose down -v` (deletes Postgres volume) |

## Local development

Postgres must be reachable (e.g. `docker compose up postgres -d` or a local instance).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# DATABASE_URL=postgresql://lashbot:lashbot@localhost:5432/lashbot if Postgres is on localhost

python -m app.main
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Required |
| `LLM_PROVIDER` | `openrouter` | `openrouter` or `gemini` |
| `OPENROUTER_API_KEY` | — | Required when provider is `openrouter` |
| `OPENROUTER_MODEL` | `google/gemini-2.5-flash` | Single model for chat + voice |
| `OPENROUTER_BASE_URL` | OpenRouter API v1 | Usually unchanged |
| `LLM_MAX_OUTPUT_TOKENS` | `1024` | Max tokens per reply |
| `GOOGLE_API_KEY` | — | Only if `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Direct Google API path |
| `DATABASE_URL` | localhost URL in code | Use `@postgres` in Docker Compose |
| `RECAP_MESSAGE_COUNT` | `50` | Messages loaded for recap context |
| `MAX_TRANSCRIPT_CHARS` | `80000` | Cap on transcript size sent to LLM |
| `CHAT_COOLDOWN_SECONDS` | `3` | Min seconds between bot replies per chat |
| `ALLOWED_CHAT_IDS` | empty | Comma-separated chat IDs; empty = all groups |
| `LOG_LEVEL` | `INFO` | Logging level |

OpenRouter retry/timeout knobs: `OPENROUTER_MAX_RETRIES`, `OPENROUTER_RETRY_*`, `OPENROUTER_TIMEOUT_SECONDS`. See `.env.example` for the full list.

## LLM providers and models

### OpenRouter (default)

One `OPENROUTER_MODEL` handles **text and voice** in a single completion (audio as base64 `input_audio`).

| Model | Chat | Voice | Notes |
|-------|------|-------|-------|
| `google/gemini-2.5-flash` | Yes | Yes | **Default** — strong balance for a friends bot |
| `google/gemini-2.0-flash-001` | Yes | Yes | Slightly cheaper Gemini 2.0 |
| `meta-llama/llama-3.3-70b-instruct` | Yes | No | Text-only; cheap on Groq |

Voice requires a **multimodal** model; text-only models will not handle voice replies.

### Gemini (direct)

Set `LLM_PROVIDER=gemini` and `GOOGLE_API_KEY`. Uses Google’s API directly (separate from OpenRouter billing/quota).

## How replies are triggered

```text
@bot_username in message  →  reply
reply_to_message.from_user.id == bot_id  →  reply
otherwise  →  log only (if ingested)
```

Groups and supergroups only; DMs are ignored.

## Architecture

```text
Telegram (long poll)  →  handlers.py
                              ├─ ingest → Postgres (messages)
                              └─ on trigger → transcript + LLM → reply

LLM: app/llm/  →  OpenRouterProvider | GeminiProvider (factory in __init__.py)
```

- **Stack:** Python 3.12, python-telegram-bot 21+, asyncpg, httpx, pydantic-settings.
- **Compose:** `postgres:16` + `bot` (`restart: unless-stopped`).

## Troubleshooting

| Problem | What to check |
|---------|----------------|
| Bot silent | Privacy disabled? In a **group**? @mention or reply to bot? |
| `OPENROUTER_API_KEY is required` | Key set in `.env` used by Compose |
| Crash loop / DB errors | Postgres healthy; `DATABASE_URL` host is `postgres` in Docker |
| Two instances fighting | Stop local Docker before running on VPS (one token = one poller) |
| Voice fails / 402 | OpenRouter balance; audio models bill per request |
| Thin recap | Bot joined recently — history only exists since it was added |

## Project layout

```text
app/
  main.py          # polling, DB connect, handler registration
  handlers.py      # ingest, triggers, LLM orchestration
  config.py        # settings from env
  db.py            # schema, insert, fetch history
  prompts.py       # system prompt
  trigger.py       # @mention / reply-to-bot
  transcript.py    # history → prompt text
  llm/             # OpenRouter, Gemini, shared HTTP retries
docker-compose.yml
Dockerfile
.env.example
```

## License

Private / friends-group use — add a license file if you open-source the repo.
