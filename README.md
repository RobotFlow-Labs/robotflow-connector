# robotflow-connectors

Secure, async multi-provider LLM connectors for robotics and AI agents.

One interface, five providers. API key and OAuth support. Built for [RobotFlow Labs](https://github.com/RobotFlow-Labs).

## Install

```bash
# With uv (recommended)
uv add robotflow-connectors

# With pip
pip install robotflow-connectors
```

## Quick Start

```python
from robotflow_connectors import create_client

# Create a client (reads config from .env)
client = create_client("minimax")

# Connect and stream
await client.connect()
await client.send_message_streaming("Hello!")
```

## Providers

| Provider | API | Auth | Default Model |
|----------|-----|------|---------------|
| `claude` | Anthropic Messages | API key or OAuth | `claude-opus-4-6` |
| `codex` | OpenAI Chat Completions | API key or OAuth | `chatgpt-5.4` |
| `minimax` | Anthropic-compatible | API key | `MiniMax-M2.7` |
| `glm5` | Anthropic-compatible | API key | `glm-5` |
| `kimi` | Anthropic-compatible | API key | `kimi-for-coding` |

## Configuration

Create a `.env` file:

```env
# Default provider
ROBOTFLOW_LLM_PROVIDER=minimax

# API Key providers
MINIMAX_API_KEY=your-key
GLM5_API_KEY=your-key
KIMI_API_KEY=your-key

# Claude (API key mode)
ANTHROPIC_API_KEY=sk-ant-...

# Claude (OAuth mode — Claude Code subscription)
ANTHROPIC_OAUTH_TOKEN=your-oauth-token

# Codex (API key mode)
OPENAI_API_KEY=sk-...

# Codex (OAuth mode — ChatGPT subscription)
OPENAI_OAUTH_TOKEN=your-oauth-token
OPENAI_ACCOUNT_ID=acct-...  # optional
```

## Usage

### Streaming with callbacks

```python
import asyncio
from robotflow_connectors import create_client

async def main():
    client = create_client("claude")

    # Wire up callbacks
    client.callbacks.on_stream_start = lambda rid: print(f"[start {rid}]")
    client.callbacks.on_stream_delta = lambda text, rid: print(text, end="", flush=True)
    client.callbacks.on_stream_end = lambda text, rid: print(f"\n[done]")
    client.callbacks.on_emotion = lambda e: print(f"[emotion: {e}]")

    await client.connect()
    await client.send_message_streaming("Tell me a joke")

    # Wait for completion
    await asyncio.sleep(10)
    await client.disconnect()

asyncio.run(main())
```

### Custom config

```python
from robotflow_connectors import create_client

client = create_client(
    "minimax",
    system_prompt="You are a helpful robot assistant.",
    temperature=0.5,
    max_tokens=2048,
    max_history=5,
)
```

### CLI commands

```bash
# OAuth login (Claude Code or ChatGPT subscription)
robotflow-connectors login claude
robotflow-connectors login codex

# Remove stored credentials
robotflow-connectors logout claude

# Show auth status for all providers
robotflow-connectors status

# List configured providers
robotflow-connectors list

# Smoke test all configured providers
robotflow-connectors test
```

## Security

- **API keys** are never logged or displayed (only last 4 chars shown in CLI)
- **OAuth tokens** stored in `~/.robotflow/auth.json` with `chmod 600` (owner-only)
- **Atomic file writes** prevent TOCTOU race conditions on credential storage
- **Auth verification** uses free endpoints (`/v1/models`) — no tokens burned
- **No secrets in code** — all credentials via `.env` or environment variables

## Architecture

```
robotflow_connectors/
├── base.py                 # BaseLLMClient + StreamCallbacks + emotion extraction
├── config.py               # .env loading, provider presets
├── registry.py             # create_client() factory
├── cli.py                  # CLI smoke test tool
├── auth/
│   ├── store.py            # ~/.robotflow/auth.json (chmod 600)
│   ├── claude_oauth.py     # Claude Bearer + OAuth beta headers
│   └── codex_oauth.py      # Codex Bearer + ChatGPT-Account-Id
└── providers/
    ├── anthropic_compat.py # Claude, MiniMax, GLM-5, Kimi (Anthropic Messages SSE)
    └── openai_compat.py    # Codex/GPT (OpenAI Chat Completions SSE)
```

All providers implement the same `BaseLLMClient` interface:

```python
await client.connect()
await client.send_message_streaming(text)
await client.send_interrupt()
await client.warmup_session()
await client.disconnect()
client.is_connected  # bool
client.callbacks     # StreamCallbacks
```

## Development

```bash
# Clone
git clone https://github.com/RobotFlow-Labs/robotflow-connector.git
cd robotflow-connector

# Install with dev deps
uv sync --dev

# Run tests
uv run pytest -v

# Lint
uv run ruff check src/
```

## License

MIT — see [LICENSE](LICENSE).

## Built by

[AIFLOW LABS LIMITED](https://aiflowlabs.io) / [RobotFlow Labs](https://github.com/RobotFlow-Labs)
