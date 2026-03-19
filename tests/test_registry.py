"""Tests for provider registry and create_client factory."""

import pytest

from robotflow_connectors.config import ConnectorConfig, ProviderConfig
from robotflow_connectors.registry import create_client, PROVIDERS
from robotflow_connectors.providers.anthropic_compat import AnthropicCompatClient
from robotflow_connectors.providers.openai_compat import OpenAICompatClient


class TestProviderList:
    def test_all_providers_listed(self):
        assert "claude" in PROVIDERS
        assert "codex" in PROVIDERS
        assert "minimax" in PROVIDERS
        assert "glm5" in PROVIDERS
        assert "kimi" in PROVIDERS
        assert len(PROVIDERS) == 5


class TestCreateClient:
    def _make_config(self, **providers) -> ConnectorConfig:
        pconfigs = {}
        for name, key in providers.items():
            pconfigs[name] = ProviderConfig(
                name=name,
                api_key=key,
                base_url=f"https://api.{name}.test",
                model=f"{name}-model",
            )
        return ConnectorConfig(providers=pconfigs)

    def test_anthropic_compat_providers(self):
        for name in ("claude", "minimax", "glm5", "kimi"):
            cfg = self._make_config(**{name: "test-key"})
            client = create_client(name, config=cfg)
            assert isinstance(client, AnthropicCompatClient)
            assert client._provider_name == name
            assert client._config.api_key == "test-key"

    def test_openai_compat_provider(self):
        cfg = self._make_config(codex="openai-key")
        client = create_client("codex", config=cfg)
        assert isinstance(client, OpenAICompatClient)
        assert client._provider_name == "codex"

    def test_unknown_provider_raises(self):
        cfg = ConnectorConfig()
        with pytest.raises(ValueError, match="Unknown provider"):
            create_client("foobar", config=cfg)

    def test_default_provider(self):
        cfg = self._make_config(minimax="mm-key")
        cfg.default_provider = "minimax"
        client = create_client(config=cfg)
        assert isinstance(client, AnthropicCompatClient)
        assert client._provider_name == "minimax"

    def test_system_prompt_override(self):
        cfg = self._make_config(minimax="key")
        client = create_client("minimax", config=cfg, system_prompt="Custom prompt")
        assert client._config.system_prompt == "Custom prompt"

    def test_config_overrides(self):
        cfg = self._make_config(minimax="key")
        client = create_client("minimax", config=cfg, temperature=0.3, max_tokens=512)
        assert client._config.temperature == 0.3
        assert client._config.max_tokens == 512
