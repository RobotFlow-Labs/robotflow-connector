# NEXT_STEPS — robotflow_connectors

## Last Updated: 2026-03-19

## What Was Accomplished
- Package created at `packages/robotflow_connectors/` with full pyproject.toml
- 5 LLM providers: Claude (Opus 4.6), Codex (ChatGPT 5.4), MiniMax (M2.7), GLM-5, Kimi
- 2 streaming parsers: AnthropicCompatClient (Anthropic Messages SSE) + OpenAICompatClient (OpenAI Chat Completions SSE)
- DRY streaming template in BaseLLMClient — providers only implement `_do_stream()`
- Full auth system: API key + OAuth for Claude and Codex
- Auth store: ~/.robotflow/auth.json with atomic chmod 600 writes
- Claude OAuth: Bearer token + anthropic-beta header + web session fallback
- Codex OAuth: Bearer token + ChatGPT-Account-Id header
- CLI smoke test: `robotflow-connectors test` and `robotflow-connectors list`
- Code review fixes: key masking (last 4 chars), TOCTOU race fix, free API verification (/v1/models), safe config parsing
- 59 tests across 11 test files, all passing

## TODO
- [ ] Wire robotflow_connectors into reachy-claw (replace anthropic_llm.py)
- [ ] Add real provider smoke test (requires API keys in .env)
- [ ] Create standalone repo when ready (github.com/RobotFlow-Labs/robotflow-connectors)
- [ ] Add VCR cassettes for OAuth verification tests
- [ ] Integrate into claude-in-the-shell architecture
- [ ] Add mlx-audio TTS backend as separate module

## Blocking Issues
- None — package is functional and tested

## MVP Readiness: 75%
- Core package: 100%
- Auth flows: 90% (token paste works, no browser OAuth yet)
- Integration with reachy-claw: 0% (next step)
- Real provider testing: 0% (needs API keys)
