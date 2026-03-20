"""OAuth PKCE flows for Claude (Anthropic) and Codex (OpenAI).

Implements the exact same OAuth flow as Claude Code CLI and Codex CLI:
  1. Generate PKCE verifier + challenge
  2. Open browser to authorize URL
  3. Local HTTP server catches the callback with auth code
  4. Exchange code for access + refresh tokens
  5. Store tokens in AuthStore

Based on @mariozechner/pi-ai OAuth implementation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger(__name__)

# ── Claude (Anthropic) OAuth config ─────────────────────────────

CLAUDE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
CLAUDE_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLAUDE_CALLBACK_PORT = 53692
CLAUDE_CALLBACK_PATH = "/callback"
CLAUDE_REDIRECT_URI = f"http://localhost:{CLAUDE_CALLBACK_PORT}{CLAUDE_CALLBACK_PATH}"
CLAUDE_SCOPES = (
    "org:create_api_key user:profile user:inference "
    "user:sessions:claude_code user:mcp_servers user:file_upload"
)

# ── OpenAI Codex OAuth config ───────────────────────────────────

CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_CALLBACK_PORT = 1455
CODEX_CALLBACK_PATH = "/auth/callback"
CODEX_REDIRECT_URI = f"http://localhost:{CODEX_CALLBACK_PORT}{CODEX_CALLBACK_PATH}"
CODEX_SCOPES = "openid profile email offline_access"

# Token expiry buffer (5 minutes before actual expiry)
EXPIRY_BUFFER_MS = 5 * 60 * 1000


# ── PKCE ────────────────────────────────────────────────────────


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE verifier and S256 challenge."""
    verifier_bytes = secrets.token_bytes(32)
    verifier = _base64url_encode(verifier_bytes)
    challenge_hash = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _base64url_encode(challenge_hash)
    return verifier, challenge


# ── Callback server ─────────────────────────────────────────────

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><title>Authentication Successful</title>
<style>body{font-family:system-ui;background:#0a0a0a;color:#e5e5e5;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#1a1a1a;border:1px solid #333;border-radius:16px;padding:40px;
text-align:center;max-width:400px}
h1{color:#4ade80;margin-bottom:8px}
</style></head>
<body><div class="card">
<h1>Authenticated!</h1>
<p>You can close this tab and return to the terminal.</p>
</div></body></html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html><head><title>Authentication Failed</title>
<style>body{font-family:system-ui;background:#0a0a0a;color:#e5e5e5;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#1a1a1a;border:1px solid #7f1d1d;border-radius:16px;padding:40px;
text-align:center;max-width:400px}
h1{color:#f87171;margin-bottom:8px}
</style></head>
<body><div class="card">
<h1>Authentication Failed</h1>
<p>%s</p>
</div></body></html>"""


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Catches the OAuth redirect with the authorization code."""

    def do_GET(self):
        parsed = urlparse(self.path)
        expected_path = self.server._expected_path

        if parsed.path != expected_path:
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_ERROR_HTML.replace("%s", "Wrong path.").encode())
            return

        params = parse_qs(parsed.query)
        error = params.get("error", [None])[0]

        if error:
            import html as html_mod

            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            safe_err = html_mod.escape(error)
            self.wfile.write(
                _ERROR_HTML.replace("%s", safe_err).encode()
            )
            self.server._result = {"error": error}
            self.server._done_event.set()
            return

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not code:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                _ERROR_HTML.replace("%s", "Missing authorization code.").encode()
            )
            return

        # Validate state
        if state != self.server._expected_state:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                _ERROR_HTML.replace("%s", "State mismatch — possible CSRF.").encode()
            )
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(_SUCCESS_HTML.encode())
        self.server._result = {"code": code, "state": state}
        self.server._done_event.set()

    def log_message(self, format, *args):
        pass


def _start_callback_server(
    port: int, path: str, expected_state: str
) -> tuple[HTTPServer, Event]:
    """Start a local HTTP server to catch the OAuth callback."""
    done = Event()
    server = HTTPServer(("127.0.0.1", port), _OAuthCallbackHandler)
    server.allow_reuse_address = True
    server._expected_path = path
    server._expected_state = expected_state
    server._result = None
    server._done_event = done
    return server, done


# ── Token exchange ──────────────────────────────────────────────


async def _exchange_code_anthropic(
    code: str, state: str, verifier: str
) -> dict[str, Any]:
    """Exchange auth code for tokens with Anthropic."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            CLAUDE_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "client_id": CLAUDE_CLIENT_ID,
                "code": code,
                "state": state,
                "redirect_uri": CLAUDE_REDIRECT_URI,
                "code_verifier": verifier,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if not resp.is_success:
            return {"error": f"Token exchange failed: HTTP {resp.status_code}"}
        data = resp.json()
        import time

        return {
            "access": data["access_token"],
            "refresh": data.get("refresh_token", ""),
            "expires": int(time.time() * 1000)
            + data.get("expires_in", 3600) * 1000
            - EXPIRY_BUFFER_MS,
        }


async def _exchange_code_openai(
    code: str, verifier: str
) -> dict[str, Any]:
    """Exchange auth code for tokens with OpenAI."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            CODEX_TOKEN_URL,
            content=(
                f"grant_type=authorization_code"
                f"&client_id={CODEX_CLIENT_ID}"
                f"&code={code}"
                f"&code_verifier={verifier}"
                f"&redirect_uri={CODEX_REDIRECT_URI}"
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if not resp.is_success:
            return {"error": f"Token exchange failed: HTTP {resp.status_code}"}
        data = resp.json()
        access = data.get("access_token", "")
        import time

        # Extract account_id from JWT
        account_id = _extract_openai_account_id(access)

        return {
            "access": access,
            "refresh": data.get("refresh_token", ""),
            "expires": int(time.time() * 1000)
            + data.get("expires_in", 3600) * 1000,
            "account_id": account_id or "",
        }


def _extract_openai_account_id(token: str) -> str | None:
    """Extract chatgpt_account_id from OpenAI JWT."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        # Add padding
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        auth = decoded.get("https://api.openai.com/auth", {})
        return auth.get("chatgpt_account_id")
    except Exception:
        return None


# ── Public API ──────────────────────────────────────────────────


async def login_claude() -> dict[str, Any]:
    """Run Claude OAuth PKCE flow — opens browser, returns tokens.

    Flow:
      1. Generate PKCE verifier + challenge
      2. Start local server on port 53692
      3. Open browser to claude.ai/oauth/authorize
      4. User logs in → redirect back with code
      5. Exchange code for access + refresh tokens

    Returns dict with 'access', 'refresh', 'expires' or 'error'.
    """
    verifier, challenge = generate_pkce()

    # Build authorize URL
    from urllib.parse import urlencode

    params = urlencode({
        "code": "true",
        "client_id": CLAUDE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": CLAUDE_REDIRECT_URI,
        "scope": CLAUDE_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": verifier,
    })
    auth_url = f"{CLAUDE_AUTHORIZE_URL}?{params}"

    # Start callback server
    try:
        server, done = _start_callback_server(
            CLAUDE_CALLBACK_PORT, CLAUDE_CALLBACK_PATH, verifier
        )
    except OSError as e:
        return {"error": f"Cannot start callback server: {e}"}

    # Serve in background thread
    def serve():
        while not done.is_set():
            server.handle_request()

    thread = Thread(target=serve, daemon=True)
    thread.start()

    print("\nOpening browser for Claude login...")
    print("If browser doesn't open, visit:\n")
    print(f"  {auth_url}\n")
    print("Waiting for authentication...")

    import contextlib

    with contextlib.suppress(Exception):
        webbrowser.open(auth_url)

    # Wait for callback (120s timeout)
    done.wait(timeout=120.0)
    server.server_close()

    if not done.is_set():
        return {"error": "Timeout — no callback received in 120s"}

    result = server._result
    if not result or "error" in result:
        return {"error": result.get("error", "Unknown error")}

    # Exchange code for tokens
    print("Exchanging code for tokens...", end=" ", flush=True)
    tokens = await _exchange_code_anthropic(
        result["code"], result["state"], verifier
    )

    if "error" in tokens:
        print("FAILED")
        return tokens

    print("OK")
    return tokens


async def login_codex() -> dict[str, Any]:
    """Run OpenAI Codex OAuth PKCE flow — opens browser, returns tokens.

    Flow:
      1. Generate PKCE verifier + challenge
      2. Start local server on port 1455
      3. Open browser to auth.openai.com/oauth/authorize
      4. User logs in → redirect back with code
      5. Exchange code for access + refresh tokens
      6. Extract account_id from JWT

    Returns dict with 'access', 'refresh', 'expires', 'account_id' or 'error'.
    """
    verifier, challenge = generate_pkce()
    state = secrets.token_hex(16)

    # Build authorize URL
    from urllib.parse import urlencode

    params = urlencode({
        "response_type": "code",
        "client_id": CODEX_CLIENT_ID,
        "redirect_uri": CODEX_REDIRECT_URI,
        "scope": CODEX_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "robotflow",
    })
    auth_url = f"{CODEX_AUTHORIZE_URL}?{params}"

    # Start callback server
    try:
        server, done = _start_callback_server(
            CODEX_CALLBACK_PORT, CODEX_CALLBACK_PATH, state
        )
    except OSError as e:
        return {"error": f"Cannot start callback server: {e}"}

    def serve():
        while not done.is_set():
            server.handle_request()

    thread = Thread(target=serve, daemon=True)
    thread.start()

    print("\nOpening browser for Codex/ChatGPT login...")
    print("If browser doesn't open, visit:\n")
    print(f"  {auth_url}\n")
    print("Waiting for authentication...")

    import contextlib

    with contextlib.suppress(Exception):
        webbrowser.open(auth_url)

    done.wait(timeout=120.0)
    server.server_close()

    if not done.is_set():
        return {"error": "Timeout — no callback received in 120s"}

    result = server._result
    if not result or "error" in result:
        return {"error": result.get("error", "Unknown error")}

    print("Exchanging code for tokens...", end=" ", flush=True)
    tokens = await _exchange_code_openai(result["code"], verifier)

    if "error" in tokens:
        print("FAILED")
        return tokens

    print("OK")
    return tokens


async def refresh_claude_token(refresh_token: str) -> dict[str, Any]:
    """Refresh a Claude OAuth token."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            CLAUDE_TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "client_id": CLAUDE_CLIENT_ID,
                "refresh_token": refresh_token,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if not resp.is_success:
            return {"error": f"Refresh failed: HTTP {resp.status_code}"}
        data = resp.json()
        import time

        return {
            "access": data["access_token"],
            "refresh": data.get("refresh_token", refresh_token),
            "expires": int(time.time() * 1000)
            + data.get("expires_in", 3600) * 1000
            - EXPIRY_BUFFER_MS,
        }


async def refresh_codex_token(refresh_token: str) -> dict[str, Any]:
    """Refresh an OpenAI Codex OAuth token."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            CODEX_TOKEN_URL,
            content=(
                f"grant_type=refresh_token"
                f"&client_id={CODEX_CLIENT_ID}"
                f"&refresh_token={refresh_token}"
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if not resp.is_success:
            return {"error": f"Refresh failed: HTTP {resp.status_code}"}
        data = resp.json()
        access = data.get("access_token", "")
        import time

        return {
            "access": access,
            "refresh": data.get("refresh_token", refresh_token),
            "expires": int(time.time() * 1000)
            + data.get("expires_in", 3600) * 1000,
            "account_id": _extract_openai_account_id(access) or "",
        }
