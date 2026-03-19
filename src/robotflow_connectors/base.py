"""Base LLM client interface — all providers implement this contract."""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Emotion tag pattern: [happy], [sad], etc. (public — used by providers)
EMOTION_RE = re.compile(r"\[(\w+)\]")

_KNOWN_EMOTIONS = frozenset({
    "happy", "laugh", "excited", "thinking", "confused", "curious",
    "sad", "angry", "surprised", "fear", "neutral", "listening",
    "agreeing", "disagreeing",
})


@dataclass
class StreamCallbacks:
    """Callbacks for streaming events — shared across all providers."""

    on_stream_start: Callable[[str], Any] | None = None
    on_stream_delta: Callable[[str, str], Any] | None = None
    on_stream_end: Callable[[str, str], Any] | None = None
    on_stream_abort: Callable[[str, str], Any] | None = None
    on_emotion: Callable[[str], Any] | None = None
    on_error: Callable[[str], Any] | None = None


@dataclass
class LLMConfig:
    """Base configuration for any LLM provider."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    max_history: int = 3
    skip_emotion_extraction: bool = False


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider clients.

    All providers must implement:
      connect(), disconnect(), warmup_session(),
      send_message_streaming(), send_interrupt()

    And expose:
      is_connected, callbacks, _history
    """

    def __init__(self, config: LLMConfig):
        self._config = config
        self._history: list[dict[str, str]] = []
        self._connected = False
        self._current_task: asyncio.Task | None = None
        self._run_counter = 0
        self.callbacks = StreamCallbacks()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def warmup_session(self) -> None: ...

    @abstractmethod
    async def send_message_streaming(self, text: str) -> None: ...

    async def send_interrupt(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            logger.info("%s generation interrupted", self.__class__.__name__)

    async def send_state_change(self, state: str) -> None:  # noqa: B027
        """No-op — override if provider needs state notifications."""

    async def send_robot_result(self, command_id: str, result: dict) -> None:  # noqa: B027
        """No-op — override if provider supports tool results."""

    # ── Shared utilities ─────────────────────────────────────────

    def _next_run_id(self, prefix: str) -> str:
        self._run_counter += 1
        return f"{prefix}-{self._run_counter}"

    def _build_system_prompt(self) -> str:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"Current time: {now}\n{self._config.system_prompt}"

    def _update_history(self, user_text: str, assistant_text: str) -> None:
        if self._config.max_history <= 0:
            return
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        max_msgs = self._config.max_history * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

    def _get_history_messages(self) -> list[dict[str, str]]:
        if self._config.max_history <= 0:
            return []
        return list(self._history[-(self._config.max_history * 2):])

    # ── Streaming template (DRY) ─────────────────────────────────
    #
    #  _stream_chat_template() handles the shared lifecycle:
    #    1. Generate run_id
    #    2. Build system prompt + history + user message
    #    3. Fire on_stream_start
    #    4. Call subclass _do_stream() for provider-specific SSE parsing
    #    5. Handle CancelledError → on_stream_abort
    #    6. Handle Exception → on_stream_abort
    #    7. Extract emotion from full text
    #    8. Update history
    #    9. Fire on_stream_end
    #
    #  Subclasses only implement _do_stream() with the SSE parsing logic.

    async def _stream_chat_template(
        self, user_text: str, provider_prefix: str
    ) -> None:
        """Shared streaming lifecycle — subclasses implement _do_stream()."""
        run_id = self._next_run_id(provider_prefix)
        system = self._build_system_prompt()

        if self.callbacks.on_stream_start:
            await maybe_await(self.callbacks.on_stream_start(run_id))

        full_text = ""
        try:
            full_text = await self._do_stream(user_text, system, run_id)
        except asyncio.CancelledError:
            if self.callbacks.on_stream_abort:
                await maybe_await(
                    self.callbacks.on_stream_abort("interrupted", run_id)
                )
            return
        except Exception as e:
            logger.error("Streaming error (%s): %s", provider_prefix, e)
            if self.callbacks.on_stream_abort:
                await maybe_await(self.callbacks.on_stream_abort(str(e), run_id))
            return

        # Extract emotion
        if self._config.skip_emotion_extraction:
            clean_full = full_text.strip()
        else:
            clean_full, emotion = extract_emotion(full_text)
            clean_full = clean_full.strip()
            if emotion and self.callbacks.on_emotion:
                await maybe_await(self.callbacks.on_emotion(emotion))

        # Update history
        self._update_history(user_text, clean_full)

        # Fire stream_end
        if self.callbacks.on_stream_end:
            await maybe_await(self.callbacks.on_stream_end(clean_full, run_id))

    async def _do_stream(
        self, user_text: str, system: str, run_id: str
    ) -> str:
        """Provider-specific SSE streaming. Returns full response text.

        Subclasses must override this. Fire on_stream_delta for each token.
        Raise on errors (template handles CancelledError + Exception).
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        state = "connected" if self._connected else "disconnected"
        return f"<{self.__class__.__name__} model={self._config.model!r} {state}>"


def extract_emotion(text: str) -> tuple[str, str | None]:
    """Extract emotion from text, strip all bracket tags."""
    emotion = None
    for m in EMOTION_RE.finditer(text):
        tag = m.group(1).lower()
        if tag in _KNOWN_EMOTIONS:
            emotion = tag
    cleaned = EMOTION_RE.sub("", text).strip()
    return cleaned, emotion


async def maybe_await(result: Any) -> None:
    import inspect
    if inspect.isawaitable(result):
        await result
