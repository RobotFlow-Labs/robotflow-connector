"""Provider registry — create_client() factory for all providers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import BaseLLMClient, LLMConfig
from .config import ConnectorConfig, ProviderConfig, load_connector_config

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Providers that use Anthropic Messages API
_ANTHROPIC_COMPAT_PROVIDERS = {"claude", "minimax", "glm5", "kimi"}

# Providers that use OpenAI Chat Completions API
_OPENAI_COMPAT_PROVIDERS = {"codex"}

PROVIDERS = sorted(_ANTHROPIC_COMPAT_PROVIDERS | _OPENAI_COMPAT_PROVIDERS)


def create_client(
    provider: str | None = None,
    config: ConnectorConfig | None = None,
    system_prompt: str = "",
    **overrides,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Args:
        provider: Provider name (claude, codex, minimax, glm5, kimi).
                  If None, uses config.default_provider.
        config: ConnectorConfig. If None, loads from env.
        system_prompt: Override system prompt.
        **overrides: Override any LLMConfig field.

    Returns:
        BaseLLMClient instance (not yet connected — call await client.connect()).
    """
    if config is None:
        config = load_connector_config()

    provider = provider or config.default_provider
    provider = provider.lower().strip()

    if provider not in _ANTHROPIC_COMPAT_PROVIDERS | _OPENAI_COMPAT_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Available: {', '.join(PROVIDERS)}"
        )

    # Get provider-specific config
    pcfg = config.providers.get(provider)
    if pcfg is None:
        pcfg = ProviderConfig(name=provider)
        logger.warning("Provider '%s' not configured — using defaults", provider)

    # Build LLMConfig
    llm_cfg = LLMConfig(
        api_key=overrides.get("api_key", pcfg.api_key),
        base_url=overrides.get("base_url", pcfg.base_url),
        model=overrides.get("model", pcfg.model),
        system_prompt=system_prompt or config.system_prompt,
        temperature=overrides.get("temperature", config.temperature),
        max_tokens=overrides.get("max_tokens", config.max_tokens),
        max_history=overrides.get("max_history", config.max_history),
    )

    if provider in _ANTHROPIC_COMPAT_PROVIDERS:
        from .providers.anthropic_compat import AnthropicCompatClient

        return AnthropicCompatClient(
            config=llm_cfg,
            auth_mode=pcfg.auth_mode,
            oauth_token=pcfg.oauth_token,
            provider_name=provider,
        )
    else:
        # OpenAI-compatible
        from .providers.openai_compat import OpenAICompatClient

        return OpenAICompatClient(
            config=llm_cfg,
            auth_mode=pcfg.auth_mode,
            oauth_token=pcfg.oauth_token,
            account_id=pcfg.account_id,
            provider_name=provider,
        )
