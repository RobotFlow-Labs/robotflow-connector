"""Tests for AnthropicCompatClient — streaming, auth, history."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from robotflow_connectors.base import LLMConfig
from robotflow_connectors.providers.anthropic_compat import AnthropicCompatClient


def _make_sse_lines(text: str, emotion: str | None = None) -> list[str]:
    """Build SSE lines simulating an Anthropic streaming response."""
    lines = []
    lines.append("event: message_start")
    lines.append('data: {"type":"message_start","message":{"role":"assistant"}}')
    lines.append("")

    full = f"{text} [{emotion}]" if emotion else text
    for word in full.split(" "):
        delta = {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": word + " "},
        }
        lines.append("event: content_block_delta")
        lines.append(f"data: {json.dumps(delta)}")
        lines.append("")

    lines.append("event: message_stop")
    lines.append('data: {"type":"message_stop"}')
    lines.append("")
    return lines


class _FakeSSEResponse:
    def __init__(self, lines: list[str]):
        self._lines = lines
        self.status_code = 200

    def raise_for_status(self): pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass


class TestAnthropicStreaming:
    @pytest.mark.asyncio
    async def test_basic_streaming(self):
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg, provider_name="minimax")
        await client.connect()

        starts, deltas, ends, emotions = [], [], [], []
        client.callbacks.on_stream_start = lambda r: starts.append(r)
        client.callbacks.on_stream_delta = lambda t, r: deltas.append(t)
        client.callbacks.on_stream_end = lambda t, r: ends.append(t)
        client.callbacks.on_emotion = lambda e: emotions.append(e)

        client._http.stream = MagicMock(
            return_value=_FakeSSEResponse(_make_sse_lines("Hello world", "happy"))
        )
        await client._stream_chat_template("Hi", "test")

        assert len(starts) == 1
        assert starts[0].startswith("test-")
        assert len(deltas) > 0
        assert len(ends) == 1
        assert "Hello" in ends[0]
        assert emotions == ["happy"]

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_history_trimming(self):
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m", max_history=2)
        client = AnthropicCompatClient(cfg, provider_name="glm5")
        await client.connect()

        for i in range(5):
            client._http.stream = MagicMock(
                return_value=_FakeSSEResponse(_make_sse_lines(f"R{i}"))
            )
            await client._stream_chat_template(f"Q{i}", "glm5")

        assert len(client._history) == 4  # max_history=2 → 4 messages

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_no_emotion_when_skipped(self):
        cfg = LLMConfig(
            api_key="k", base_url="http://x", model="m",
            skip_emotion_extraction=True,
        )
        client = AnthropicCompatClient(cfg, provider_name="kimi")
        await client.connect()

        emotions = []
        client.callbacks.on_emotion = lambda e: emotions.append(e)
        client._http.stream = MagicMock(
            return_value=_FakeSSEResponse(_make_sse_lines("Hi", "happy"))
        )
        await client._stream_chat_template("Hey", "test")

        assert emotions == []
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        cfg = LLMConfig(api_key="k", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg)
        assert not client.is_connected
        await client.connect()
        assert client.is_connected
        await client.disconnect()
        assert not client.is_connected


class TestAnthropicAuth:
    @pytest.mark.asyncio
    async def test_api_key_headers(self):
        cfg = LLMConfig(api_key="test-key", base_url="http://x", model="m")
        client = AnthropicCompatClient(cfg, provider_name="minimax")
        await client.connect()

        assert client._http.headers["x-api-key"] == "test-key"
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_claude_oauth_headers(self):
        cfg = LLMConfig(base_url="https://api.anthropic.com", model="claude-opus-4")
        client = AnthropicCompatClient(
            cfg, auth_mode="oauth", oauth_token="bearer-123", provider_name="claude"
        )
        await client.connect()

        assert "Bearer bearer-123" in client._http.headers.get("Authorization", "")
        assert "oauth" in client._http.headers.get("anthropic-beta", "")
        await client.disconnect()
