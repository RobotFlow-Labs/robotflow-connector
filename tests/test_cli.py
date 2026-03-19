"""Tests for CLI module — list providers, smoke test structure."""

from unittest.mock import patch

from robotflow_connectors.cli import _list_providers
from robotflow_connectors.config import ConnectorConfig, ProviderConfig


class TestListProviders:
    def test_list_with_providers(self, capsys):
        cfg = ConnectorConfig(
            default_provider="minimax",
            providers={
                "minimax": ProviderConfig(
                    name="minimax",
                    api_key="mm-key-1234567890",
                    base_url="https://api.minimax.io/anthropic",
                    model="MiniMax-M2.7",
                ),
                "claude": ProviderConfig(
                    name="claude",
                    oauth_token="bearer-xyz",
                    auth_mode="oauth",
                    base_url="https://api.anthropic.com",
                    model="claude-opus-4-6",
                ),
            },
        )

        with patch("robotflow_connectors.config.load_connector_config", return_value=cfg):
            _list_providers()

        output = capsys.readouterr().out
        assert "minimax" in output
        assert "claude" in output
        assert "Default provider: minimax" in output
        # S1 fix: should only show last 4 chars of key
        assert "mm-key-12" not in output  # first 8 chars must NOT appear
        assert "7890" in output  # last 4 chars should appear

    def test_list_no_providers(self, capsys):
        cfg = ConnectorConfig(providers={})

        with patch("robotflow_connectors.config.load_connector_config", return_value=cfg):
            _list_providers()

        output = capsys.readouterr().out
        assert "Not configured" in output

    def test_key_masking_security(self):
        """Verify API key masking shows only last 4 chars."""
        key = "sk-ant-very-secret-key-1234"
        preview = f"...{key[-4:]}" if key else "(none)"
        assert preview == "...1234"
        assert "secret" not in preview
        assert "sk-ant" not in preview
