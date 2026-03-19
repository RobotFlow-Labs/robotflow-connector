"""Tests for CLI module — list, status, login, logout."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from robotflow_connectors.auth.store import AuthStore
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

        with patch(
            "robotflow_connectors.config.load_connector_config",
            return_value=cfg,
        ):
            _list_providers()

        output = capsys.readouterr().out
        assert "minimax" in output
        assert "claude" in output
        assert "Default provider: minimax" in output
        assert "mm-key-12" not in output
        assert "7890" in output

    def test_list_no_providers(self, capsys):
        cfg = ConnectorConfig(providers={})

        with patch(
            "robotflow_connectors.config.load_connector_config",
            return_value=cfg,
        ):
            _list_providers()

        output = capsys.readouterr().out
        assert "Not configured" in output

    def test_key_masking_security(self):
        key = "sk-ant-very-secret-key-1234"
        preview = f"...{key[-4:]}" if key else "(none)"
        assert preview == "...1234"
        assert "secret" not in preview
        assert "sk-ant" not in preview


class TestLogout:
    def test_logout_existing(self, tmp_path, capsys):
        store = AuthStore(path=tmp_path / "auth.json")
        store.set_api_key("minimax", "test-key")
        assert store.get("minimax") is not None

        # Patch at the module level where it gets imported
        with patch(
            "robotflow_connectors.auth.store._DEFAULT_STORE_PATH",
            tmp_path / "auth.json",
        ):
            from robotflow_connectors.cli import _logout
            _logout("minimax")

        output = capsys.readouterr().out
        assert "removed" in output.lower() or "Credentials" in output

    def test_logout_nonexistent(self, tmp_path, capsys):
        with patch(
            "robotflow_connectors.auth.store._DEFAULT_STORE_PATH",
            tmp_path / "auth.json",
        ):
            from robotflow_connectors.cli import _logout
            _logout("foobar")

        output = capsys.readouterr().out
        assert "No stored" in output


class TestAuthStoreConfigIntegration:
    def test_stored_oauth_appears_in_config(self, tmp_path, monkeypatch):
        """Stored OAuth tokens should be picked up by config loader."""
        # Clear all provider env vars
        for var in [
            "ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN",
            "OPENAI_API_KEY", "OPENAI_OAUTH_TOKEN",
            "MINIMAX_API_KEY", "GLM5_API_KEY", "KIMI_API_KEY",
            "CLAUDE_WEB_SESSION_KEY", "CLAUDE_AI_SESSION_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)

        store = AuthStore(path=tmp_path / "auth.json")
        store.set_oauth(
            "claude",
            access_token="stored-token-xyz",
            expires_at=int(time.time() * 1000) + 999_999,
        )

        with patch(
            "robotflow_connectors.auth.store._DEFAULT_STORE_PATH",
            tmp_path / "auth.json",
        ):
            from robotflow_connectors.config import load_connector_config
            cfg = load_connector_config()

        assert "claude" in cfg.providers
        assert cfg.providers["claude"].oauth_token == "stored-token-xyz"
        assert cfg.providers["claude"].auth_mode == "oauth"

    def test_expired_token_not_loaded(self, tmp_path, monkeypatch):
        """Expired OAuth tokens should NOT be loaded into config."""
        for var in [
            "ANTHROPIC_API_KEY", "ANTHROPIC_OAUTH_TOKEN",
            "OPENAI_API_KEY", "OPENAI_OAUTH_TOKEN",
            "MINIMAX_API_KEY", "GLM5_API_KEY", "KIMI_API_KEY",
            "CLAUDE_WEB_SESSION_KEY", "CLAUDE_AI_SESSION_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)

        store = AuthStore(path=tmp_path / "auth.json")
        store.set_oauth(
            "claude",
            access_token="expired-token",
            expires_at=1000,  # long expired
        )

        with patch(
            "robotflow_connectors.auth.store._DEFAULT_STORE_PATH",
            tmp_path / "auth.json",
        ):
            from robotflow_connectors.config import load_connector_config
            cfg = load_connector_config()

        # Expired token should not create a provider entry
        assert "claude" not in cfg.providers
