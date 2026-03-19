# Contributing to robotflow-connectors

We welcome contributions! Here's how to get started.

## Setup

```bash
git clone https://github.com/RobotFlow-Labs/robotflow-connector.git
cd robotflow-connector
uv sync --dev
```

## Running Tests

```bash
uv run pytest -v
```

## Adding a New Provider

1. Determine if your provider uses Anthropic Messages API or OpenAI Chat Completions API
2. If Anthropic-compatible: just add config to `_PROVIDER_ENV_PREFIX` and `_PROVIDER_DEFAULTS` in `config.py`
3. If different API: create a new client class inheriting `BaseLLMClient`, implement `_do_stream()`
4. Add tests mirroring `test_anthropic_compat.py` or `test_openai_compat.py`
5. Update README with the new provider

## Code Style

- Python 3.10+
- Async/await everywhere
- Ruff for linting (`uv run ruff check src/`)
- All tests must pass before PR

## Security

- NEVER commit API keys or OAuth tokens
- All credential handling must use `AuthStore` (atomic writes, chmod 600)
- API key display must show only last 4 characters
