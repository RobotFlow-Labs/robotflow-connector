"""Tests for config edge cases — bad env values, missing providers, defaults."""

from robotflow_connectors.config import (
    _safe_float,
    _safe_int,
    _resolve_provider_from_env,
    load_connector_config,
)


class TestSafeConverters:
    def test_safe_float_valid(self):
        assert _safe_float("0.5", 0.7) == 0.5

    def test_safe_float_invalid(self):
        assert _safe_float("hot", 0.7) == 0.7

    def test_safe_float_empty(self):
        assert _safe_float("", 0.7) == 0.7

    def test_safe_int_valid(self):
        assert _safe_int("512", 1024) == 512

    def test_safe_int_invalid(self):
        assert _safe_int("lots", 1024) == 1024

    def test_safe_int_float_string(self):
        assert _safe_int("1.5", 1024) == 1024


class TestProviderDefaults:
    def test_claude_defaults(self):
        pcfg = _resolve_provider_from_env("claude")
        assert pcfg.base_url == "https://api.anthropic.com"
        assert pcfg.model == "claude-haiku-4-5-20251001"

    def test_codex_defaults(self):
        pcfg = _resolve_provider_from_env("codex")
        assert pcfg.base_url == "https://api.openai.com"
        assert pcfg.model == "gpt-5.4"

    def test_minimax_defaults(self):
        pcfg = _resolve_provider_from_env("minimax")
        assert pcfg.model == "MiniMax-M2.7"

    def test_unknown_provider(self):
        pcfg = _resolve_provider_from_env("unknown_provider")
        assert pcfg.name == "unknown_provider"
        assert pcfg.api_key == ""
        assert pcfg.base_url == ""


class TestLoadConnectorConfig:
    def test_default_provider_env(self, monkeypatch):
        monkeypatch.setenv("ROBOTFLOW_LLM_PROVIDER", "claude")
        cfg = load_connector_config()
        assert cfg.default_provider == "claude"

    def test_bad_temperature_env(self, monkeypatch):
        monkeypatch.setenv("ROBOTFLOW_TEMPERATURE", "very_hot")
        cfg = load_connector_config()
        assert cfg.temperature == 0.7  # falls back to default

    def test_bad_max_tokens_env(self, monkeypatch):
        monkeypatch.setenv("ROBOTFLOW_MAX_TOKENS", "unlimited")
        cfg = load_connector_config()
        assert cfg.max_tokens == 1024  # falls back to default

    def test_only_configured_providers_included(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("CLAUDE_WEB_SESSION_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_AI_SESSION_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("GLM5_API_KEY", raising=False)
        monkeypatch.delenv("KIMI_API_KEY", raising=False)

        # Isolate from real auth store
        from unittest.mock import patch
        from robotflow_connectors.auth.store import AuthStore

        empty_store = AuthStore(path=tmp_path / "empty_auth.json")
        with patch(
            "robotflow_connectors.auth.store._DEFAULT_STORE_PATH",
            tmp_path / "empty_auth.json",
        ):
            cfg = load_connector_config()
        assert "minimax" in cfg.providers
        assert "claude" not in cfg.providers
        assert "codex" not in cfg.providers
