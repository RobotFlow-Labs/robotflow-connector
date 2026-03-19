"""CLI smoke test — verify all configured providers work.

Usage:
    robotflow-connectors test
    robotflow-connectors list
"""

from __future__ import annotations

import asyncio
import sys
import time


def main():
    if len(sys.argv) < 2:
        print("Usage: robotflow-connectors <command>")
        print("Commands: test, list")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "test":
        asyncio.run(_test_providers())
    elif cmd == "list":
        _list_providers()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


def _list_providers():
    from .config import load_connector_config

    config = load_connector_config()
    print(f"Default provider: {config.default_provider}")
    print(f"Configured providers:")
    for name, pcfg in config.providers.items():
        auth = pcfg.auth_mode
        model = pcfg.model or "(default)"
        key_preview = f"...{pcfg.api_key[-4:]}" if pcfg.api_key else "(none)"
        oauth = "yes" if pcfg.oauth_token else "no"
        print(f"  {name:10s}  model={model:20s}  auth={auth:8s}  key={key_preview:12s}  oauth={oauth}")

    from .registry import PROVIDERS

    missing = set(PROVIDERS) - set(config.providers.keys())
    if missing:
        print(f"\nNot configured: {', '.join(sorted(missing))}")


async def _test_providers():
    from .config import load_connector_config
    from .registry import create_client

    config = load_connector_config()
    if not config.providers:
        print("No providers configured. Set API keys in .env")
        return

    print(f"Testing {len(config.providers)} configured provider(s)...\n")
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

            # Capture response
            response_text = ""
            done_event = asyncio.Event()

            def on_delta(text, rid):
                nonlocal response_text
                response_text += text

            def on_end(text, rid):
                nonlocal response_text
                response_text = text
                done_event.set()

            def on_abort(reason, rid):
                nonlocal response_text
                response_text = f"ABORT: {reason}"
                done_event.set()

            client.callbacks.on_stream_delta = on_delta
            client.callbacks.on_stream_end = on_end
            client.callbacks.on_stream_abort = on_abort

            await client.send_message_streaming("Say OK")
            await asyncio.wait_for(done_event.wait(), timeout=30.0)
            await client.disconnect()

            elapsed = time.monotonic() - t0
            ok = bool(response_text) and "ABORT" not in response_text
            preview = response_text[:50].replace("\n", " ")
            results.append((name, ok, preview, elapsed))
            status = "OK" if ok else "FAIL"
            print(f"{status} ({elapsed:.1f}s) — {preview}")

        except Exception as e:
            elapsed = time.monotonic() - t0
            results.append((name, False, str(e)[:50], elapsed))
            print(f"FAIL ({elapsed:.1f}s) — {e}")

    # Summary
    passed = sum(1 for _, ok, _, _ in results if ok)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} providers working")


if __name__ == "__main__":
    main()
