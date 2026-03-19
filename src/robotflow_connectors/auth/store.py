"""Auth profile storage — persists OAuth tokens and API keys to disk.

Stores credentials in ~/.robotflow/auth.json with chmod 600.
Writes with atomic file permissions (no TOCTOU race).
"""

from __future__ import annotations

import json
import logging
import os
import stat
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_STORE_PATH = Path.home() / ".robotflow" / "auth.json"


class AuthStore:
    """Persistent credential store for LLM providers."""

    def __init__(self, path: Path | None = None):
        self._path = path or _DEFAULT_STORE_PATH
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text())
            self._profiles = data.get("profiles", {})
        except Exception as e:
            logger.warning("Failed to load auth store: %s", e)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps({"profiles": self._profiles}, indent=2)
        # Atomic write with correct permissions from the start (no TOCTOU race)
        try:
            fd = os.open(
                str(self._path),
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                stat.S_IRUSR | stat.S_IWUSR,  # 0o600
            )
            with os.fdopen(fd, "w") as f:
                f.write(content)
        except OSError:
            # Fallback for platforms without proper os.open support (Windows)
            self._path.write_text(content)

    def get(self, provider: str) -> dict[str, Any] | None:
        """Get stored credentials for a provider."""
        return self._profiles.get(provider)

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Store an API key credential."""
        self._profiles[provider] = {
            "type": "api_key",
            "provider": provider,
            "key": api_key,
        }
        self._save()

    def set_oauth(
        self,
        provider: str,
        access_token: str,
        refresh_token: str = "",
        expires_at: int = 0,
        account_id: str = "",
    ) -> None:
        """Store an OAuth credential."""
        self._profiles[provider] = {
            "type": "oauth",
            "provider": provider,
            "access": access_token,
            "refresh": refresh_token,
            "expires": expires_at or int(time.time() * 1000) + 3600_000,
            "account_id": account_id,
        }
        self._save()

    def is_expired(self, provider: str) -> bool:
        """Check if an OAuth token is expired."""
        cred = self._profiles.get(provider)
        if not cred or cred.get("type") != "oauth":
            return False
        expires = cred.get("expires", 0)
        return int(time.time() * 1000) >= expires

    def remove(self, provider: str) -> None:
        """Remove stored credentials for a provider."""
        self._profiles.pop(provider, None)
        self._save()

    @property
    def providers(self) -> list[str]:
        """List all stored providers."""
        return list(self._profiles.keys())
