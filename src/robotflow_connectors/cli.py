"""CLI for robotflow-connectors — provider management and smoke testing.

Usage:
    robotflow-connectors login <provider>   # OAuth login (claude, codex)
    robotflow-connectors logout <provider>  # Remove stored credentials
    robotflow-connectors test               # Smoke test all providers
    robotflow-connectors list               # Show configured providers
    robotflow-connectors status             # Show auth status for all providers
"""

from __future__ import annotations

import asyncio
import sys
import time


def main():
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "test":
        asyncio.run(_test_providers())
    elif cmd == "list":
        _list_providers()
    elif cmd == "login":
        if len(sys.argv) < 3:
            print("Usage: robotflow-connectors login <provider>")
            print("Providers: claude, codex")
            sys.exit(1)
        asyncio.run(_login(sys.argv[2]))
    elif cmd == "logout":
        if len(sys.argv) < 3:
            print("Usage: robotflow-connectors logout <provider>")
            sys.exit(1)
        _logout(sys.argv[2])
    elif cmd == "status":
        _show_status()
    else:
        print(f"Unknown command: {cmd}")
        _print_usage()
        sys.exit(1)


def _print_usage():
    print("Usage: robotflow-connectors <command>")
    print()
    print("Commands:")
    print("  login <provider>   OAuth login (claude, codex)")
    print("  logout <provider>  Remove stored credentials")
    print("  test               Smoke test all configured providers")
    print("  list               Show configured providers")
    print("  status             Show auth status for all providers")


# ── Login / Logout ───────────────────────────────────────────────


async def _login(provider: str):
    """OAuth login — auto-detect, then browser flow, then paste."""
    from .auth.store import AuthStore

    provider = provider.lower().strip()
    if provider not in ("claude", "codex"):
        print(f"OAuth login not supported for '{provider}'.")
        print("Use API keys in .env for: minimax, glm5, kimi")
        return

    store = AuthStore()

    # Try auto-detection first
    from .auth.token_extractor import (
        find_claude_token,
        find_codex_token,
    )

    found = (
        find_claude_token()
        if provider == "claude"
        else find_codex_token()
    )

    if found:
        await _login_with_found_token(store, provider, found)
        return

    # Launch browser-based login
    from .auth.browser_auth import run_browser_login

    run_browser_login(provider)


async def _login_with_found_token(store, provider, found):
    """Verify and store an auto-detected token."""
    import httpx

    token = found["token"]
    token_type = found["type"]
    print(
        f"Found {provider} {token_type} token "
        f"(auto-detected, ...{token[-4:]})"
    )
    print("Verifying...", end=" ", flush=True)

    async with httpx.AsyncClient(timeout=15.0) as http:
        if provider == "claude":
            from .auth.claude_oauth import verify_claude_auth

            auth_mode = (
                "api_key" if token_type == "api_key" else "oauth"
            )
            if auth_mode == "api_key":
                result = await verify_claude_auth(
                    http, api_key=token, auth_mode="api_key"
                )
            else:
                result = await verify_claude_auth(
                    http, oauth_token=token, auth_mode="oauth"
                )
        else:
            from .auth.codex_oauth import verify_codex_auth

            auth_mode = (
                "api_key" if token_type == "api_key" else "oauth"
            )
            account_id = found.get("account_id", "")
            if auth_mode == "api_key":
                result = await verify_codex_auth(
                    http, api_key=token, auth_mode="api_key"
                )
            else:
                result = await verify_codex_auth(
                    http,
                    oauth_token=token,
                    auth_mode="oauth",
                    account_id=account_id,
                )

    if result["ok"]:
        if token_type == "api_key":
            store.set_api_key(provider, token)
        else:
            store.set_oauth(
                provider,
                access_token=token,
                account_id=found.get("account_id", ""),
            )
        print("OK")
        print(f"{provider} credentials saved to {store._path}")
    else:
        err = result.get("error", "unknown")
        print(f"FAILED: {err}")
        print("Falling back to manual login...")
        if provider == "claude":
            await _login_claude(store)
        else:
            await _login_codex(store)


async def _login_claude(store):
    """Claude OAuth login — paste token from Claude Code CLI."""
    import httpx

    print("=" * 55)
    print("  Claude OAuth Login")
    print("=" * 55)
    print()
    print("To get your OAuth token:")
    print("  1. Open Claude Code CLI (claude)")
    print("  2. Run: /login")
    print("  3. Copy the OAuth token displayed")
    print()
    print("Or get a session key from claude.ai:")
    print("  1. Open claude.ai in your browser")
    print("  2. Open DevTools → Application → Cookies")
    print("  3. Copy the 'sessionKey' value")
    print()

    token = input("Paste your Claude token: ").strip()
    if not token:
        print("No token provided. Aborting.")
        return

    print("\nVerifying token...", end=" ", flush=True)

    async with httpx.AsyncClient(timeout=15.0) as http:
        from .auth.claude_oauth import verify_claude_auth

        result = await verify_claude_auth(
            http, oauth_token=token, auth_mode="oauth"
        )

    if result["ok"]:
        store.set_oauth("claude", access_token=token)
        print("OK")
        print(f"\nClaude credentials saved to {store._path}")
        print("You can now use: robotflow-connectors test")
    else:
        print(f"FAILED: {result.get('error', 'unknown')}")
        print("\nToken was NOT saved. Please check and try again.")


async def _login_codex(store):
    """Codex/ChatGPT OAuth login — paste token from browser."""
    import httpx

    print("=" * 55)
    print("  Codex / ChatGPT OAuth Login")
    print("=" * 55)
    print()
    print("To get your OAuth token:")
    print("  1. Open chatgpt.com in your browser")
    print("  2. Open DevTools → Network tab")
    print("  3. Make any request, find Authorization header")
    print("  4. Copy the Bearer token value")
    print()

    token = input("Paste your Codex/ChatGPT token: ").strip()
    if not token:
        print("No token provided. Aborting.")
        return

    # Remove "Bearer " prefix if pasted with it
    if token.lower().startswith("bearer "):
        token = token[7:]

    account_id = input(
        "Account ID (optional, press Enter to skip): "
    ).strip()

    print("\nVerifying token...", end=" ", flush=True)

    async with httpx.AsyncClient(timeout=15.0) as http:
        from .auth.codex_oauth import verify_codex_auth

        result = await verify_codex_auth(
            http,
            oauth_token=token,
            auth_mode="oauth",
            account_id=account_id,
        )

    if result["ok"]:
        store.set_oauth(
            "codex",
            access_token=token,
            account_id=account_id,
        )
        plan = result.get("plan", "")
        print("OK")
        if plan:
            print(f"Plan: {plan}")
        print(f"\nCodex credentials saved to {store._path}")
        print("You can now use: robotflow-connectors test")
    else:
        print(f"FAILED: {result.get('error', 'unknown')}")
        print("\nToken was NOT saved. Please check and try again.")


def _logout(provider: str):
    """Remove stored credentials for a provider."""
    from .auth.store import AuthStore

    provider = provider.lower().strip()
    store = AuthStore()

    if store.get(provider):
        store.remove(provider)
        print(f"Credentials removed for '{provider}'.")
    else:
        print(f"No stored credentials for '{provider}'.")


# ── Status ───────────────────────────────────────────────────────


def _show_status():
    """Show auth status for all providers."""
    from .auth.store import AuthStore
    from .config import load_connector_config

    config = load_connector_config()
    store = AuthStore()

    print("Provider Status:")
    print(f"{'Provider':12s} {'Auth':10s} {'Source':12s} {'Status'}")
    print("-" * 55)

    for name in sorted(
        set(config.providers.keys()) | set(store.providers)
    ):
        pcfg = config.providers.get(name)
        stored = store.get(name)

        if stored:
            auth = stored.get("type", "?")
            source = "auth.json"
            status = (
                "EXPIRED"
                if auth == "oauth" and store.is_expired(name)
                else "ready"
            )
        elif pcfg and (pcfg.api_key or pcfg.oauth_token):
            auth = pcfg.auth_mode
            source = ".env"
            status = "ready"
        else:
            auth = "-"
            source = "-"
            status = "not configured"

        print(f"  {name:10s} {auth:10s} {source:12s} {status}")


# ── List ─────────────────────────────────────────────────────────


def _list_providers():
    from .config import load_connector_config

    config = load_connector_config()
    print(f"Default provider: {config.default_provider}")
    print("Configured providers:")
    for name, pcfg in config.providers.items():
        auth = pcfg.auth_mode
        model = pcfg.model or "(default)"
        key_hint = (
            f"...{pcfg.api_key[-4:]}" if pcfg.api_key else "(none)"
        )
        oauth = "yes" if pcfg.oauth_token else "no"
        print(
            f"  {name:10s}  model={model:20s}  "
            f"auth={auth:8s}  key={key_hint}  oauth={oauth}"
        )

    from .registry import PROVIDERS

    missing = set(PROVIDERS) - set(config.providers.keys())
    if missing:
        print(f"\nNot configured: {', '.join(sorted(missing))}")


# ── Test ─────────────────────────────────────────────────────────


async def _test_providers():
    from .config import load_connector_config
    from .registry import create_client

    config = load_connector_config()
    if not config.providers:
        print("No providers configured.")
        print("Set API keys in .env or run: robotflow-connectors login")
        return

    print(
        f"Testing {len(config.providers)} configured provider(s)...\n"
    )
    results: list[tuple[str, bool, str, float]] = []

    for name in sorted(config.providers.keys()):
        print(f"  Testing {name}...", end=" ", flush=True)
        t0 = time.monotonic()
        try:
            client = create_client(
                provider=name,
                config=config,
                system_prompt="Reply with exactly: OK",
            )
            await client.connect()

            result = {"text": ""}
            done = asyncio.Event()

            client.callbacks.on_stream_delta = (
                lambda text, rid, r=result: r.update(
                    text=r["text"] + text
                )
            )
            client.callbacks.on_stream_end = (
                lambda text, rid, r=result, d=done: (
                    r.update(text=text), d.set()
                )
            )
            client.callbacks.on_stream_abort = (
                lambda reason, rid, r=result, d=done: (
                    r.update(text=f"ABORT: {reason}"), d.set()
                )
            )

            await client.send_message_streaming("Say OK")
            await asyncio.wait_for(done.wait(), timeout=30.0)
            await client.disconnect()

            elapsed = time.monotonic() - t0
            resp = result["text"]
            ok = bool(resp) and "ABORT" not in resp
            preview = resp[:50].replace("\n", " ")
            results.append((name, ok, preview, elapsed))
            status = "OK" if ok else "FAIL"
            print(f"{status} ({elapsed:.1f}s) — {preview}")

        except Exception as e:
            elapsed = time.monotonic() - t0
            results.append((name, False, str(e)[:50], elapsed))
            print(f"FAIL ({elapsed:.1f}s) — {e}")

    passed = sum(1 for _, ok, _, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} providers working")


if __name__ == "__main__":
    main()
