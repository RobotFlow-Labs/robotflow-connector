# NEXT_STEPS — robotflow_connectors

## Last Updated: 2026-03-20

## What Was Accomplished
- Package published at https://github.com/RobotFlow-Labs/robotflow-connector
- 5 LLM providers configured with correct model names
- OAuth PKCE login working for Claude and Codex (same flow as Claude Code CLI)
- 4/5 providers tested and working with real API calls
- 63 tests, lint clean, CI/CD on GitHub Actions

## Provider Status (Real Tests)

| Provider | Auth | Model | Status |
|----------|------|-------|--------|
| claude | OAuth (Max subscription) | claude-haiku-4-5-20251001 | WORKING |
| codex | OAuth (Pro subscription) | gpt-5.4 | needs gateway proxy |
| minimax | API key | MiniMax-M2.5 | WORKING |
| glm5 | API key | glm-5 | WORKING |
| kimi | API key | kimi-for-coding | WORKING |

## Known Limitations
- Claude OAuth (Max plan) only allows Haiku via API, not Sonnet/Opus
- Codex OAuth token doesn't work on api.openai.com (needs chatgpt.com gateway)
- Both are Anthropic/OpenAI subscription restrictions, not our code bug
- openclaw works around this by running its own gateway proxy server

## TODO
- [ ] Wire robotflow_connectors into reachy-claw (replace anthropic_llm.py)
- [ ] Add gateway proxy for Codex OAuth (like openclaw does)
- [ ] Investigate Claude Sonnet/Opus via API key (console.anthropic.com)
- [ ] Add mlx-audio TTS backend
- [ ] Publish to PyPI

## MVP Readiness: 80%
- Core package: 100%
- Auth flows: 95% (OAuth PKCE working for both)
- Provider testing: 80% (4/5 working)
- Integration with reachy-claw: 0% (next step)
