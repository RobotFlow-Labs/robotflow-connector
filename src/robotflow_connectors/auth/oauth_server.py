"""Local OAuth callback server — opens browser, catches token redirect.

Spins up a temporary HTTP server on localhost:18490, opens the auth URL
in the user's browser, and waits for the provider to redirect back with
the token. Works for both Claude and Codex OAuth flows.
"""

from __future__ import annotations

import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

CALLBACK_PORT = 18490
CALLBACK_PATH = "/oauth/callback"


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    token: str | None = None
    state: str | None = None
    error: str | None = None
    received = False

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        # Check for error
        if "error" in params:
            import html

            _OAuthCallbackHandler.error = params["error"][0]
            _OAuthCallbackHandler.received = True
            safe_err = html.escape(params["error"][0])
            self._send_html(
                "Authentication Failed",
                f"<p>Error: {safe_err}</p>"
                "<p>You can close this tab.</p>",
            )
            return

        # Extract token — only accept code (not access_token in URL)
        token = (
            params.get("token", [None])[0]
            or params.get("code", [None])[0]
        )
        state = params.get("state", [None])[0]

        _OAuthCallbackHandler.token = token
        _OAuthCallbackHandler.state = state
        _OAuthCallbackHandler.received = True

        self._send_html(
            "Authentication Successful",
            "<p>You can close this tab and return to the terminal.</p>",
        )

    def _send_html(self, title: str, body: str):
        html = f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>body{{font-family:system-ui;max-width:500px;margin:80px auto;
text-align:center}}h1{{color:#333}}</style></head>
<body><h1>{title}</h1>{body}</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress request logs


def run_oauth_flow(
    auth_url: str,
    timeout: float = 120.0,
) -> dict[str, str | None]:
    """Run a full OAuth flow: open browser → wait for callback.

    Args:
        auth_url: The authorization URL to open in the browser.
        timeout: Max seconds to wait for the callback.

    Returns:
        dict with 'token', 'state', 'error' keys.
    """
    # Reset handler state
    _OAuthCallbackHandler.token = None
    _OAuthCallbackHandler.state = None
    _OAuthCallbackHandler.error = None
    _OAuthCallbackHandler.received = False

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _OAuthCallbackHandler)
    server.timeout = 1.0

    # Run server in background thread
    def serve():
        while not _OAuthCallbackHandler.received:
            server.handle_request()

    thread = Thread(target=serve, daemon=True)
    thread.start()

    callback_url = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
    print("\nOpening browser for authentication...")
    print("If the browser doesn't open, visit this URL:\n")
    print(f"  {auth_url}\n")
    print(f"Waiting for callback on {callback_url}...")

    # Open browser
    import contextlib

    with contextlib.suppress(Exception):
        webbrowser.open(auth_url)

    # Wait for callback
    thread.join(timeout=timeout)
    server.server_close()

    if not _OAuthCallbackHandler.received:
        return {"token": None, "state": None, "error": "Timeout waiting for callback"}

    return {
        "token": _OAuthCallbackHandler.token,
        "state": _OAuthCallbackHandler.state,
        "error": _OAuthCallbackHandler.error,
    }


def get_callback_url() -> str:
    """Return the OAuth callback URL for registration with providers."""
    return f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
