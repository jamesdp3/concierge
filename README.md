# concierge

iMessage-style front desk for AI task management via [spacecadet](https://github.com/jamesdp3/spacecadet) MCP.

Send natural-language messages from a browser. Concierge classifies your intent, creates/updates tasks in org-mode through spacecadet, and sends back a short acknowledgement — all without blocking your input.

## Architecture

```
Browser (WebSocket)
    ↕
FastAPI server
    ↕
WebSocket Handler → Inbox (filesystem, append-only)
    ↓
Burst Detector (groups rapid messages)
    ↓
Classifier (LLM: Anthropic or Ollama)
    ↓
Reconciler → SpacecadetClient (MCP) → org files
    ↓
Acknowledger → response back over WebSocket
```

## Prerequisites

- Python 3.10+
- spacecadet set up and working (with Emacs)
- An LLM provider: Anthropic API key **or** Ollama running locally

## Setup

```bash
git clone <repo-url>
cd concierge
pip install -e .
```

Copy `.env.example` to `.env` and fill in your settings:

```bash
cp .env.example .env
```

At minimum, set:
- `CONCIERGE_SPACECADET_PATH` — path to your spacecadet `server.py`
- `ANTHROPIC_API_KEY` — if using Anthropic (default provider)

## Running

```bash
uvicorn concierge.main:app
```

Open `http://localhost:8000` in your browser.

## LLM providers

Set `CONCIERGE_LLM_PROVIDER` to choose:

| Provider | Value | Requirements |
|----------|-------|-------------|
| Anthropic | `anthropic` (default) | `ANTHROPIC_API_KEY` set |
| Ollama | `ollama` | Ollama running at `CONCIERGE_OLLAMA_BASE_URL` |

## How it works

1. You type messages in the browser. Each is persisted to the inbox immediately.
2. The **burst detector** groups rapid messages (waits for a 2s quiet window).
3. The **classifier** sends the burst to an LLM, extracting structured intents.
4. The **reconciler** maps each intent to spacecadet tool calls (add_task, update_task, etc.).
5. The **acknowledger** generates a short confirmation and sends it back.

Input is never blocked — you can keep typing while processing happens.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
