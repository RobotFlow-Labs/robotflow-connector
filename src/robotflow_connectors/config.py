"""Provider configuration — .env loading, preset resolution."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Provider name → env var prefix
_PROVIDER_ENV_PREFIX = {
    "claude": "ANTHROPIC",
    "codex": "OPENAI",
    "minimax": "MINIMAX",
    "glm5": "GLM5",
    "kimi": "KIMI",
}

# Default base URLs and models per provider
_PROVIDER_DEFAULTS = {
    "claude": {
        "base_url": "https://api.anthropic.com",
        "model": "claude-opus-4-6",
    },
    "codex": {
        "base_url": "https://api.openai.com",
        "model": "chatgpt-5.4",
    },
    "minimax": {
        "base_url": "https://api.minimax.io/anthropic",
        "model": "MiniMax-M2.7",
    },
    "glm5": {
        "base_url": "https://api.z.ai/api/anthropic",
        "model": "glm-5",
    },
    "kimi": {
        "base_url": "https://api.kimi.com/coding",
        "model": "kimi-for-coding",
    },
}


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    auth_mode: str = "api_key"  # "api_key" or "oauth"
    oauth_token: str = ""
    oauth_refresh: str = ""
    oauth_expires: int = 0
    account_id: str = ""  # OpenAI account routing


@dataclass
class ConnectorConfig:
    """Configuration for all providers."""

    default_provider: str = "minimax"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    max_history: int = 3


def _resolve_provider_from_env(name: str) -> ProviderConfig:
    """Load a provider's config from environment variables."""
    prefix = _PROVIDER_ENV_PREFIX.get(name, name.upper())
    defaults = _PROVIDER_DEFAULTS.get(name, {})

    api_key = os.environ.get(f"{prefix}_API_KEY", "")
    base_url = os.environ.get(f"{prefix}_BASE_URL", defaults.get("base_url", ""))
    model = os.environ.get(f"{prefix}_MODEL", defaults.get("model", ""))

    # OAuth tokens (for Claude and Codex)
    oauth_token = os.environ.get(f"{prefix}_OAUTH_TOKEN", "")
    oauth_refresh = os.environ.get(f"{prefix}_OAUTH_REFRESH", "")
    account_id = os.environ.get(f"{prefix}_ACCOUNT_ID", "")

    # Determine auth mode
    auth_mode = "oauth" if oauth_token else "api_key"

    # Claude-specific: check CLAUDE_WEB_SESSION_KEY fallback
    if name == "claude" and not api_key and not oauth_token:
        session_key = os.environ.get("CLAUDE_WEB_SESSION_KEY", "") or os.environ.get("CLAUDE_AI_SESSION_KEY", "")
        if session_key:
            oauth_token = session_key
            auth_mode = "oauth"

    return ProviderConfig(
        name=name,
        api_key=api_key,
        base_url=base_url,
        model=model,
        auth_mode=auth_mode,
        oauth_token=oauth_token,
        oauth_refresh=oauth_refresh,
        account_id=account_id,
    )


def _safe_float(val: str, default: float) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: str, default: int) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def load_connector_config() -> ConnectorConfig:
    """Load configuration from .env and environment variables."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    default_provider = os.environ.get("ROBOTFLOW_LLM_PROVIDER", "minimax")
    system_prompt = os.environ.get("ROBOTFLOW_SYSTEM_PROMPT", "")
    temperature = _safe_float(os.environ.get("ROBOTFLOW_TEMPERATURE", "0.7"), 0.7)
    max_tokens = _safe_int(os.environ.get("ROBOTFLOW_MAX_TOKENS", "1024"), 1024)
    max_history = _safe_int(os.environ.get("ROBOTFLOW_MAX_HISTORY", "3"), 3)

    providers: dict[str, ProviderConfig] = {}
    for name in _PROVIDER_ENV_PREFIX:
        pcfg = _resolve_provider_from_env(name)
        if pcfg.api_key or pcfg.oauth_token:
            providers[name] = pcfg
            logger.debug("Provider '%s' configured (auth: %s)", name, pcfg.auth_mode)

    return ConnectorConfig(
        default_provider=default_provider,
        providers=providers,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        max_history=max_history,
    )
