"""Codex OAuth — Bearer token auth for OpenAI / ChatGPT API.

Supports:
  1. OAuth access token (Bearer header + optional ChatGPT-Account-Id)
  2. Standard API key (Authorization: Bearer sk-...)

Extracted from openclaw patterns (provider-usage.fetch.codex.ts).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
OPENAI_API_BASE = "https://api.openai.com"


def build_auth_headers(
    api_key: str = "",
    oauth_token: str = "",
    auth_mode: str = "api_key",
    account_id: str = "",
) -> dict[str, str]:
    """Build provider-appropriate auth headers for OpenAI API.

    Returns headers dict ready for httpx requests.
    """
    headers: dict[str, str] = {
        "content-type": "application/json",
    }

    token = oauth_token if auth_mode == "oauth" else api_key
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("No OpenAI/Codex auth credentials configured")

    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    return headers


async def verify_codex_auth(
    http: httpx.AsyncClient,
    api_key: str = "",
    oauth_token: str = "",
    auth_mode: str = "api_key",
    account_id: str = "",
) -> dict[str, Any]:
    """Verify OpenAI/Codex authentication."""
    if auth_mode == "oauth" and oauth_token:
        return await _verify_codex_oauth(http, oauth_token, account_id)
    elif api_key:
        return await _verify_openai_api_key(http, api_key)
    return {"ok": False, "error": "No credentials configured"}


async def _verify_codex_oauth(
    http: httpx.AsyncClient, token: str, account_id: str = ""
) -> dict[str, Any]:
    """Verify Codex OAuth token via usage endpoint."""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "robotflow-connectors",
        "Accept": "application/json",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    try:
        resp = await http.get(CODEX_USAGE_URL, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "ok": True,
                "auth_mode": "oauth",
                "plan": data.get("plan_type"),
                "usage": data.get("rate_limit"),
            }
        elif resp.status_code in (401, 403):
            return {"ok": False, "auth_mode": "oauth", "error": "Token expired or invalid"}
        return {"ok": False, "auth_mode": "oauth", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "auth_mode": "oauth", "error": str(e)}


async def _verify_openai_api_key(
    http: httpx.AsyncClient, api_key: str
) -> dict[str, Any]:
    """Verify OpenAI API key using /v1/models (free, no tokens burned)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = await http.get(f"{OPENAI_API_BASE}/v1/models", headers=headers)
        if resp.status_code == 200:
            return {"ok": True, "auth_mode": "api_key"}
        elif resp.status_code in (401, 403):
            return {"ok": False, "auth_mode": "api_key", "error": "Invalid API key"}
        return {"ok": False, "auth_mode": "api_key", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "auth_mode": "api_key", "error": str(e)}
