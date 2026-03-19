"""RobotFlow Connectors — Multi-provider LLM client library.

Supports 5 providers:
  - claude:   Anthropic Messages API (API key or OAuth)
  - codex:    OpenAI Responses API (API key or OAuth)
  - minimax:  MiniMax via Anthropic-compatible API
  - glm5:     GLM-5 (ZhipuAI) via Anthropic-compatible API
  - kimi:     Kimi (Moonshot) via Anthropic-compatible API

Usage:
    from robotflow_connectors import create_client
    client = create_client("minimax")
    await client.connect()
    await client.send_message_streaming("Hello!")
"""

from .base import BaseLLMClient, StreamCallbacks
from .config import ConnectorConfig, load_connector_config
from .registry import create_client, PROVIDERS

__all__ = [
    "BaseLLMClient",
    "StreamCallbacks",
    "ConnectorConfig",
    "load_connector_config",
    "create_client",
    "PROVIDERS",
]
