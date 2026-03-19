"""OpenAI-compatible LLM client — handles GPT, Codex, and compatible providers.

Uses OpenAI Chat Completions API:
  POST /v1/chat/completions with SSE streaming.

SSE format: data: {"choices":[{"delta":{"content":"token"}}]}
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import httpx

from ..auth.codex_oauth import build_auth_headers as build_openai_headers
from ..base import EMOTION_RE, BaseLLMClient, LLMConfig, maybe_await

logger = logging.getLogger(__name__)


class OpenAICompatClient(BaseLLMClient):
    """Client for OpenAI Chat Completions API and compatible providers.

    Handles: GPT-4o, ChatGPT 5.4, Codex.
    Uses _stream_chat_template() from BaseLLMClient for shared lifecycle.
    """

    def __init__(
        self,
        config: LLMConfig,
        auth_mode: str = "api_key",
        oauth_token: str = "",
        account_id: str = "",
        provider_name: str = "openai",
    ):
        super().__init__(config)
        self._auth_mode = auth_mode
        self._oauth_token = oauth_token
        self._account_id = account_id
        self._provider_name = provider_name
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        headers = build_openai_headers(
            api_key=self._config.api_key,
            oauth_token=self._oauth_token,
            auth_mode=self._auth_mode,
            account_id=self._account_id,
        )

        self._http = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        )
        self._connected = True
        logger.info(
            "OpenAICompatClient ready: %s (%s @ %s)",
            self._provider_name, self._config.model, self._config.base_url,
        )

    async def disconnect(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._current_task
        if self._http:
            await self._http.aclose()
            self._http = None
        self._connected = False
        logger.info("OpenAICompatClient disconnected (%s)", self._provider_name)

    async def warmup_session(self) -> None:
        if not self._http:
            return
        try:
            resp = await self._http.post(
                "/v1/chat/completions",
                json={
                    "model": self._config.model,
                    "max_tokens": 1,
                    "messages": [
                        {"role": "system", "content": self._build_system_prompt()},
                        {"role": "user", "content": "."},
                    ],
                },
            )
            resp.raise_for_status()
            logger.info("Warmup OK (%s/%s)", self._provider_name, self._config.model)
        except Exception as e:
            logger.warning("Warmup failed (%s): %s", self._provider_name, e)

    async def send_message_streaming(self, text: str) -> None:
        if not self._http:
            raise RuntimeError("Not connected")
        self._current_task = asyncio.create_task(
            self._stream_chat_template(text, self._provider_name)
        )

    # ── Provider-specific SSE parsing ────────────────────────────

    async def _do_stream(
        self, user_text: str, system: str, run_id: str
    ) -> str:
        """Parse OpenAI Chat Completions SSE stream.

        SSE events:
          data: {"choices":[{"delta":{"content":"token"},"finish_reason":null}]}
          data: [DONE]
        """
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.extend(self._get_history_messages())
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "stream": True,
        }

        full_text = ""

        async with self._http.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as resp:
            if resp.status_code in (401, 403):
                hint = ("Update your OAuth token." if self._auth_mode == "oauth"
                        else "Check your API key.")
                raise RuntimeError(
                    f"Auth failed for {self._provider_name} "
                    f"(HTTP {resp.status_code}). {hint}"
                )
            resp.raise_for_status()

            async for line in resp.aiter_lines():
                if not line.strip() or not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                if not data_str:
                    continue

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.debug("Malformed SSE chunk: %s", data_str[:100])
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                token = delta.get("content", "")
                finish = choices[0].get("finish_reason")

                if token:
                    full_text += token
                    clean_token = (
                        token
                        if self._config.skip_emotion_extraction
                        else EMOTION_RE.sub("", token)
                    )
                    if clean_token and self.callbacks.on_stream_delta:
                        await maybe_await(
                            self.callbacks.on_stream_delta(clean_token, run_id)
                        )

                if finish == "stop":
                    break

        return full_text
