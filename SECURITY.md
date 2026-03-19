# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** open a public GitHub issue
2. Email: **ilessio@aiflowlabs.io**
3. Include: description, reproduction steps, impact assessment
4. We will respond within 48 hours

## Security Design

### Credential Storage
- Tokens stored in `~/.robotflow/auth.json`
- File created with `chmod 600` (owner read/write only)
- Atomic writes via `os.open()` with explicit mode flags — no TOCTOU race
- Never logged, never displayed in full (last 4 chars only in CLI)

### API Key Handling
- Keys loaded from `.env` files or environment variables only
- Never hardcoded, never committed to version control
- `.env` is gitignored by default
- Auth verification uses free endpoints (`/v1/models`) — no tokens burned

### OAuth Token Flow
- Bearer tokens passed via `Authorization` header (HTTPS only)
- Claude: `anthropic-beta: oauth-2025-04-20` header for scope
- Codex: `ChatGPT-Account-Id` header for account routing
- Tokens can be revoked by the user at any time via provider dashboard

### What We Don't Do
- No telemetry or analytics
- No data sent to third parties (beyond the LLM provider you configure)
- No automatic credential sharing between providers
- No browser-based OAuth flows (token paste mode only — no localhost listeners)
