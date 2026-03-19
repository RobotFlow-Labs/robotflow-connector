"""Tests for error paths in streaming — 401, malformed SSE, cancellation, API errors."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from robotflow_connectors.base import LLMConfig
from robotflow_connectors.providers.anthropic_compat import AnthropicCompatClient
from robotflow_connectors.providers.openai_compat import OpenAICompatClient


# ── Helpers ───────────────────────────────────────────────────────


class _FakeSSEResponse:
    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


class _FakeAuthFailResponse(_FakeSSEResponse):
    """Simulates 401 response."""

    def __init__(self):
        super().__init__([], status_code=401)

    def raise_for_status(self):
        pass  # We check status_code manually before raise_for_status


# ── Anthropic error paths ────────────────────────────────────────


class TestAnthropicErrors:
    @pytest.mark.asyncio
    async def test_auth_expired_oauth(self):
        """401 with OAuth should produce clear error message."""
        cfg = LLMConfig(base_url="http://x", model="m")
        client = AnthropicCompatClient(
            cfg, auth_mode="oauth", oauth_token="expired", provider_name="claude"
        )
        await client.connect()

        aborts = []
        client.callbacks.on_stream_abort = lambda reason, rid: aborts.append(reason)
        client._http.stream = MagicMock(return_value=_FakeAuthFailResponse())

        await client._stream_chat_template("Hi", "claude")

        assert len(aborts) == 1
        assert "Auth failed" in aborts[0]
        assert "OAuth" in aborts[0]
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_auth_expired_api_key(self):
        """401 with API key should suggest checking key."""
        cfg = LLMConfig(api_key="bad-key", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg, provider_name="minimax")
        await client.connect()

        aborts = []
        client.callbacks.on_stream_abort = lambda reason, rid: aborts.append(reason)
        client._http.stream = MagicMock(return_value=_FakeAuthFailResponse())

        await client._stream_chat_template("Hi", "minimax")

        assert len(aborts) == 1
        assert "API key" in aborts[0]
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_malformed_sse_skipped(self):
        """Malformed JSON in SSE should be skipped, not crash."""
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg, provider_name="test")
        await client.connect()

        lines = [
            "data: {bad json}",  # malformed
            "data: " + json.dumps({
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "OK "},
            }),
            "data: " + json.dumps({"type": "message_stop"}),
        ]

        ends = []
        client.callbacks.on_stream_end = lambda t, r: ends.append(t)
        client._http.stream = MagicMock(return_value=_FakeSSEResponse(lines))

        await client._stream_chat_template("Hi", "test")

        assert len(ends) == 1
        assert "OK" in ends[0]
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_api_error_chunk(self):
        """API error in SSE stream should fire abort."""
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg, provider_name="test")
        await client.connect()

        lines = [
            "data: " + json.dumps({
                "type": "error",
                "error": {"message": "rate limited"},
            }),
        ]

        aborts = []
        client.callbacks.on_stream_abort = lambda reason, rid: aborts.append(reason)
        client._http.stream = MagicMock(return_value=_FakeSSEResponse(lines))

        await client._stream_chat_template("Hi", "test")

        assert len(aborts) == 1
        assert "rate limited" in aborts[0]
        await client.disconnect()


# ── OpenAI error paths ───────────────────────────────────────────


class TestOpenAIErrors:
    @pytest.mark.asyncio
    async def test_auth_expired(self):
        cfg = LLMConfig(base_url="http://x", model="m")
        client = OpenAICompatClient(
            cfg, auth_mode="oauth", oauth_token="expired", provider_name="codex"
        )
        await client.connect()

        aborts = []
        client.callbacks.on_stream_abort = lambda reason, rid: aborts.append(reason)
        client._http.stream = MagicMock(return_value=_FakeAuthFailResponse())

        await client._stream_chat_template("Hi", "codex")

        assert len(aborts) == 1
        assert "Auth failed" in aborts[0]
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_malformed_sse_skipped(self):
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m")
        client = OpenAICompatClient(cfg, provider_name="test")
        await client.connect()

        lines = [
            "data: not json",
            "data: " + json.dumps({
                "choices": [{"delta": {"content": "OK "}, "finish_reason": None}],
            }),
            "data: [DONE]",
        ]

        ends = []
        client.callbacks.on_stream_end = lambda t, r: ends.append(t)
        client._http.stream = MagicMock(return_value=_FakeSSEResponse(lines))

        await client._stream_chat_template("Hi", "test")

        assert len(ends) == 1
        assert "OK" in ends[0]
        await client.disconnect()


# ── Base template error paths ────────────────────────────────────


class TestBaseTemplateErrors:
    @pytest.mark.asyncio
    async def test_repr(self):
        cfg = LLMConfig(api_key="k", base_url="http://x", model="test-model")
        client = AnthropicCompatClient(cfg, provider_name="minimax")
        assert "test-model" in repr(client)
        assert "disconnected" in repr(client)

        await client.connect()
        assert "connected" in repr(client)
        await client.disconnect()
