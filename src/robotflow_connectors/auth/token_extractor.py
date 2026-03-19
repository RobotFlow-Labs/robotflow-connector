"""Extract OAuth tokens from existing CLI tool installations.

Finds tokens from:
  - Claude Code CLI (~/.claude/ credentials)
  - Codex CLI (~/.codex/ or environment)

This avoids requiring users to register OAuth apps — we reuse
tokens from tools they've already authenticated with.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def find_claude_token() -> dict[str, str] | None:
    """Try to find a Claude OAuth token from Claude Code CLI.

    Checks:
      1. ANTHROPIC_API_KEY env var
      2. Claude Code's stored credentials
      3. claude.ai session key from env
    """
    # 1. Check env var
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return {"type": "api_key", "token": api_key}

    # 2. Try Claude Code's credential store
    # Claude Code stores auth in the system keychain or config
    claude_dir = Path.home() / ".claude"
    for cred_file in [
        claude_dir / ".credentials.json",
        claude_dir / "credentials.json",
    ]:
        if cred_file.is_file():
            try:
                data = json.loads(cred_file.read_text())
                token = data.get("oauthToken") or data.get(
                    "accessToken"
                )
                if token:
                    return {"type": "oauth", "token": token}
            except Exception:
                continue

    # 3. Try running `claude auth status` to check if logged in
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "authenticated" in result.stdout.lower():
            logger.info("Claude Code is authenticated (use `claude` CLI)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 4. Session key fallback
    session_key = os.environ.get(
        "CLAUDE_WEB_SESSION_KEY", ""
    ) or os.environ.get("CLAUDE_AI_SESSION_KEY", "")
    if session_key:
        return {"type": "session_key", "token": session_key}

    return None


def find_codex_token() -> dict[str, str] | None:
    """Try to find an OpenAI/Codex token from existing tools.

    Checks:
      1. OPENAI_API_KEY env var
      2. Codex CLI stored credentials
      3. ~/.config/openai/ credentials
    """
    # 1. Check env var
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        return {"type": "api_key", "token": api_key}

    # 2. Try Codex CLI credential store
    for cred_path in [
        Path.home() / ".codex" / "credentials.json",
        Path.home() / ".codex" / ".credentials",
        Path.home() / ".config" / "openai" / "credentials.json",
    ]:
        if cred_path.is_file():
            try:
                data = json.loads(cred_path.read_text())
                token = (
                    data.get("access_token")
                    or data.get("api_key")
                    or data.get("token")
                )
                if token:
                    return {
                        "type": "oauth",
                        "token": token,
                        "account_id": data.get("account_id", ""),
                    }
            except Exception:
                continue

    return None
