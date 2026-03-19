"""Tests for BaseLLMClient and shared utilities."""

from robotflow_connectors.base import (
    LLMConfig,
    StreamCallbacks,
    extract_emotion,
    _KNOWN_EMOTIONS,
)


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.api_key == ""
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 1024
        assert cfg.max_history == 3

    def test_custom(self):
        cfg = LLMConfig(api_key="k", model="m", temperature=0.5)
        assert cfg.api_key == "k"
        assert cfg.model == "m"
        assert cfg.temperature == 0.5


class TestStreamCallbacks:
    def test_defaults_none(self):
        cb = StreamCallbacks()
        assert cb.on_stream_start is None
        assert cb.on_stream_delta is None
        assert cb.on_stream_end is None
        assert cb.on_emotion is None


class TestExtractEmotion:
    def test_happy(self):
        text, emotion = extract_emotion("Hello! [happy]")
        assert text == "Hello!"
        assert emotion == "happy"

    def test_no_emotion(self):
        text, emotion = extract_emotion("Hello world")
        assert text == "Hello world"
        assert emotion is None

    def test_multiple_tags_last_wins(self):
        text, emotion = extract_emotion("[thinking] Let me see [happy]")
        assert "thinking" not in text
        assert "happy" not in text
        assert emotion == "happy"

    def test_unknown_tag_ignored(self):
        text, emotion = extract_emotion("Test [foobar]")
        assert text == "Test"
        assert emotion is None

    def test_all_known_emotions(self):
        for e in _KNOWN_EMOTIONS:
            _, extracted = extract_emotion(f"test [{e}]")
            assert extracted == e
