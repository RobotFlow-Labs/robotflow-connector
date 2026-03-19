"""Claude OAuth — Bearer token auth for Anthropic API.

Supports:
  1. OAuth access token (Bearer header + anthropic-beta: oauth-2025-04-20)
  2. Claude Web session key fallback (Cookie: sessionKey=sk-ant-...)
  3. Standard API key (x-api-key header)

Extracted from openclaw patterns (provider-usage.fetch.claude.ts).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_OAUTH_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_WEB_ORGS_URL = "https://claude.ai/api/organizations"
CLAUDE_WEB_USAGE_URL = "https://claude.ai/api/organizations/{org_id}/usage"


def build_auth_headers(
    api_key: str = "",
    oauth_token: str = "",
    auth_mode: str = "api_key",
) -> dict[str, str]:
    """Build provider-appropriate auth headers for Anthropic API.

    Returns headers dict ready for httpx requests.
    """
    headers: dict[str, str] = {
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    if auth_mode == "oauth" and oauth_token:
        # OAuth bearer token mode (Claude Code subscription)
        headers["Authorization"] = f"Bearer {oauth_token}"
        headers["anthropic-beta"] = "oauth-2025-04-20"
    elif api_key:
        # Standard API key mode
        headers["x-api-key"] = api_key
    else:
        logger.warning("No Claude auth credentials configured")

    return headers


async def verify_claude_auth(
    http: httpx.AsyncClient,
    api_key: str = "",
    oauth_token: str = "",
    auth_mode: str = "api_key",
) -> dict[str, Any]:
    """Verify Claude authentication and return account info.

    Returns dict with 'ok', 'auth_mode', and optional usage data.
    """
    if auth_mode == "oauth" and oauth_token:
        return await _verify_oauth(http, oauth_token)
    elif api_key:
        return await _verify_api_key(http, api_key)
    return {"ok": False, "error": "No credentials configured"}


async def _verify_oauth(http: httpx.AsyncClient, token: str) -> dict[str, Any]:
    """Verify OAuth token via usage endpoint."""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "robotflow-connectors",
        "Accept": "application/json",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
    }
    try:
        resp = await http.get(ANTHROPIC_OAUTH_USAGE_URL, headers=headers)
        if resp.status_code == 200:
            return {"ok": True, "auth_mode": "oauth", "usage": resp.json()}
        elif resp.status_code in (401, 403):
            return {"ok": False, "auth_mode": "oauth", "error": "Token expired or invalid"}
        return {"ok": False, "auth_mode": "oauth", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "auth_mode": "oauth", "error": str(e)}


async def _verify_api_key(http: httpx.AsyncClient, api_key: str) -> dict[str, Any]:
    """Verify API key without burning tokens — uses a dry-run with max_tokens=1.

    Anthropic doesn't have a /v1/models endpoint, so we send a minimal
    request. The cost is negligible (~1 token).
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        resp = await http.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "."}],
            },
        )
        if resp.status_code == 200:
            return {"ok": True, "auth_mode": "api_key"}
        elif resp.status_code in (401, 403):
            return {"ok": False, "auth_mode": "api_key", "error": "Invalid API key"}
        return {"ok": False, "auth_mode": "api_key", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "auth_mode": "api_key", "error": str(e)}
