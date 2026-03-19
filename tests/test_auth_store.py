"""Tests for AuthStore — credential persistence."""

import json
import time

import pytest

from robotflow_connectors.auth.store import AuthStore


@pytest.fixture
def store(tmp_path):
    return AuthStore(path=tmp_path / "auth.json")


class TestAuthStore:
    def test_set_get_api_key(self, store):
        store.set_api_key("minimax", "mm-key-123")
        cred = store.get("minimax")
        assert cred is not None
        assert cred["type"] == "api_key"
        assert cred["key"] == "mm-key-123"

    def test_set_get_oauth(self, store):
        store.set_oauth(
            "claude",
            access_token="bearer-abc",
            refresh_token="refresh-xyz",
            expires_at=int(time.time() * 1000) + 3600_000,
        )
        cred = store.get("claude")
        assert cred["type"] == "oauth"
        assert cred["access"] == "bearer-abc"
        assert cred["refresh"] == "refresh-xyz"

    def test_persistence(self, tmp_path):
        path = tmp_path / "auth.json"
        store1 = AuthStore(path=path)
        store1.set_api_key("test", "key-1")

        store2 = AuthStore(path=path)
        assert store2.get("test")["key"] == "key-1"

    def test_remove(self, store):
        store.set_api_key("test", "key")
        assert store.get("test") is not None
        store.remove("test")
        assert store.get("test") is None

    def test_is_expired(self, store):
        # Set expired token
        store.set_oauth("expired", "token", expires_at=1000)
        assert store.is_expired("expired") is True

        # Set future token
        store.set_oauth(
            "valid", "token",
            expires_at=int(time.time() * 1000) + 999_999_999,
        )
        assert store.is_expired("valid") is False

    def test_providers_list(self, store):
        store.set_api_key("a", "k1")
        store.set_api_key("b", "k2")
        assert sorted(store.providers) == ["a", "b"]

    def test_file_permissions(self, store):
        import os
        import stat

        store.set_api_key("test", "key")
        if hasattr(os, "chmod"):
            mode = os.stat(store._path).st_mode
            # Check owner-only read/write (0o600)
            assert mode & stat.S_IRWXG == 0  # no group
            assert mode & stat.S_IRWXO == 0  # no other
