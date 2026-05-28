# lashbot

Telegram group companion bot with a swappable LLM adapter. Default: **one OpenRouter model** for text chat and voice notes.

## Prerequisites

1. [@BotFather](https://t.me/BotFather) bot token; **disable privacy mode** (`/setprivacy` → Disable).
2. [OpenRouter](https://openrouter.ai) API key with credit.

## Quick start

```bash
cp .env.example .env
# TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY

docker compose up --build
```

## One model for everything

Set a single `OPENROUTER_MODEL` that supports **text + audio**:

| Model | Chat | Voice | Notes |
|-------|------|-------|-------|
| `google/gemini-2.5-flash` | **Default** — production Gemini | Yes | Best balance for a friends bot |
| `google/gemini-2.0-flash-001` | Fast Gemini 2.0 | Yes | Slightly cheaper |
| `meta-llama/llama-3.3-70b-instruct` | Strong 70B text | No | Text-only, very cheap on Groq |

Voice uses the **same model** in **one API call** (transcript + your question + audio).

## Configuration

| Variable | Description |
|----------|-------------|
| `OPENROUTER_MODEL` | Used for all LLM requests |
| `LLM_PROVIDER` | `openrouter` (default) or `gemini` (direct Google API) |

## Local development

```bash
pip install -r requirements.txt
python -m app.main
```
