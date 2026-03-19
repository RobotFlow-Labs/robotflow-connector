"""Tests for claude_oauth and codex_oauth auth modules."""

from robotflow_connectors.auth.claude_oauth import build_auth_headers as claude_headers
from robotflow_connectors.auth.codex_oauth import build_auth_headers as codex_headers


class TestClaudeAuthHeaders:
    def test_api_key_mode(self):
        h = claude_headers(api_key="sk-ant-test", auth_mode="api_key")
        assert h["x-api-key"] == "sk-ant-test"
        assert "Authorization" not in h
        assert h["anthropic-version"] == "2023-06-01"

    def test_oauth_mode(self):
        h = claude_headers(oauth_token="bearer-xyz", auth_mode="oauth")
        assert h["Authorization"] == "Bearer bearer-xyz"
        assert "oauth" in h["anthropic-beta"]
        assert "x-api-key" not in h

    def test_no_credentials(self):
        h = claude_headers()
        assert "x-api-key" not in h
        assert "Authorization" not in h


class TestCodexAuthHeaders:
    def test_api_key_mode(self):
        h = codex_headers(api_key="sk-test", auth_mode="api_key")
        assert h["Authorization"] == "Bearer sk-test"
        assert "ChatGPT-Account-Id" not in h

    def test_oauth_mode_with_account_id(self):
        h = codex_headers(
            oauth_token="codex-token", auth_mode="oauth", account_id="acct-1"
        )
        assert h["Authorization"] == "Bearer codex-token"
        assert h["ChatGPT-Account-Id"] == "acct-1"

    def test_oauth_mode_without_account_id(self):
        h = codex_headers(oauth_token="token", auth_mode="oauth")
        assert h["Authorization"] == "Bearer token"
        assert "ChatGPT-Account-Id" not in h

    def test_no_credentials(self):
        h = codex_headers()
        assert "Authorization" not in h
