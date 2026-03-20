"""CLI-based OAuth — delegates to Claude Code and Codex CLIs.

Both Claude Code and Codex CLI store OAuth tokens in macOS Keychain
via Electron's safeStorage. We can't read those directly, but we CAN:

1. Check if the user is already logged in (via `claude auth status`)
2. Trigger login (via `claude auth login` / `codex auth`)
3. Use the CLI as a proxy to make API calls with the stored token

For robotflow-connectors, the approach is:
  - If Claude/Codex CLI is authenticated → use it as an API proxy
  - The CLIs handle token refresh, keychain access, etc.
  - We just need to get one API key/token that we can use directly

Alternatively, users can extract their OAuth token from the CLI
and paste it into our auth store.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def check_claude_cli_auth() -> dict[str, Any]:
    """Check if Claude Code CLI is authenticated.

    Returns dict with 'authenticated', 'email', 'plan' keys.
    """
    try:
        result = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {
                    "authenticated": True,
                    "email": data.get("email", ""),
                    "plan": data.get("plan", ""),
                    "org": data.get("organization", ""),
                }
            except json.JSONDecodeError:
                # Non-JSON output — parse text
                if "authenticated" in result.stdout.lower():
                    return {"authenticated": True}
        return {"authenticated": False}
    except FileNotFoundError:
        return {"authenticated": False, "error": "claude CLI not found"}
    except subprocess.TimeoutExpired:
        return {"authenticated": False, "error": "timeout"}


def check_codex_cli_auth() -> dict[str, Any]:
    """Check if Codex CLI is authenticated.

    Returns dict with 'authenticated' key.
    """
    try:
        result = subprocess.run(
            ["codex", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"authenticated": True}
        return {"authenticated": False}
    except FileNotFoundError:
        return {"authenticated": False, "error": "codex CLI not found"}
    except subprocess.TimeoutExpired:
        return {"authenticated": False, "error": "timeout"}


def trigger_claude_login() -> bool:
    """Launch Claude Code CLI login flow (opens browser).

    Returns True if login was successful.
    """
    print("Launching Claude Code login...")
    print("This will open your browser for authentication.\n")
    try:
        result = subprocess.run(
            ["claude", "auth", "login"],
            timeout=120,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("Error: 'claude' CLI not found.")
        print("Install: npm install -g @anthropic-ai/claude-code")
        return False
    except subprocess.TimeoutExpired:
        print("Login timed out.")
        return False


def trigger_codex_login() -> bool:
    """Launch Codex CLI login flow (opens browser).

    Returns True if login was successful.
    """
    print("Launching Codex login...")
    print("This will open your browser for authentication.\n")
    try:
        result = subprocess.run(
            ["codex", "auth", "login"],
            timeout=120,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("Error: 'codex' CLI not found.")
        print("Install: npm install -g @openai/codex")
        return False
    except subprocess.TimeoutExpired:
        print("Login timed out.")
        return False


def get_claude_api_proxy_headers() -> dict[str, str] | None:
    """Try to get API headers by running claude CLI.

    Claude Code CLI manages its own OAuth tokens. We can ask it
    to make a test request and verify it works.
    """
    status = check_claude_cli_auth()
    if not status.get("authenticated"):
        return None
    # The CLI is authenticated — return headers indicating proxy mode
    return {"x-robotflow-proxy": "claude-cli", "x-authenticated": "true"}
