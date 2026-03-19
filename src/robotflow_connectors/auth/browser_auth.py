"""Browser-based token acquisition — serves a local helper page.

Opens a local webpage at http://localhost:18490 that:
1. Guides the user to get their token from Claude/Codex
2. Provides a paste field
3. Sends the token back to the server
4. Server stores it in AuthStore

No external OAuth app registration required.
"""

from __future__ import annotations

import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

PORT = 18490

_CLAUDE_HTML = """<!DOCTYPE html>
<html><head><title>RobotFlow — Claude Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0a;
color:#e5e5e5;min-height:100vh;display:flex;align-items:center;
justify-content:center}
.card{background:#1a1a1a;border:1px solid #333;border-radius:16px;
padding:40px;max-width:560px;width:100%}
h1{font-size:24px;margin-bottom:8px;color:#fff}
.sub{color:#888;margin-bottom:24px}
.steps{background:#111;border-radius:8px;padding:16px 20px;margin:16px 0}
.steps li{margin:8px 0;color:#ccc}
.steps code{background:#222;padding:2px 8px;border-radius:4px;color:#f0c040}
textarea{width:100%;height:80px;background:#111;border:1px solid #444;
border-radius:8px;padding:12px;color:#fff;font-family:monospace;
font-size:13px;resize:vertical;margin:12px 0}
textarea:focus{outline:none;border-color:#7c3aed}
button{background:#7c3aed;color:#fff;border:none;border-radius:8px;
padding:12px 32px;font-size:16px;cursor:pointer;width:100%;
font-weight:600;transition:background 0.2s}
button:hover{background:#6d28d9}
button:disabled{background:#333;cursor:not-allowed}
.status{margin-top:16px;padding:12px;border-radius:8px;display:none}
.success{background:#052e16;color:#4ade80;border:1px solid #166534;display:block}
.error{background:#2a0a0a;color:#f87171;border:1px solid #7f1d1d;display:block}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:24px}
.logo span{font-size:28px}
</style></head>
<body>
<div class="card">
  <div class="logo"><span>&#129302;</span><h1>RobotFlow — Claude Login</h1></div>
  <p class="sub">Connect your Claude Code or Claude Pro subscription</p>

  <div class="steps">
    <p><strong>Option A — Claude Code CLI:</strong></p>
    <ol>
      <li>Open terminal, run <code>claude</code></li>
      <li>Type <code>/login</code></li>
      <li>Copy the displayed OAuth token</li>
    </ol>
  </div>

  <div class="steps">
    <p><strong>Option B — claude.ai session:</strong></p>
    <ol>
      <li>Open <a href="https://claude.ai" target="_blank" style="color:#7c3aed">claude.ai</a></li>
      <li>DevTools (F12) → Application → Cookies</li>
      <li>Copy the <code>sessionKey</code> value</li>
    </ol>
  </div>

  <div class="steps">
    <p><strong>Option C — API Key:</strong></p>
    <ol>
      <li>Go to <a href="https://console.anthropic.com/settings/keys" target="_blank"
          style="color:#7c3aed">console.anthropic.com/settings/keys</a></li>
      <li>Create or copy an API key</li>
    </ol>
  </div>

  <textarea id="token" placeholder="Paste your token here..."></textarea>
  <button onclick="submit()" id="btn">Save & Verify</button>
  <div id="status" class="status"></div>
</div>
<script>
async function submit() {
  const token = document.getElementById('token').value.trim();
  if (!token) return;
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  btn.disabled = true; btn.textContent = 'Verifying...';
  try {
    const res = await fetch('/api/save-token', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider: 'claude', token: token})
    });
    const data = await res.json();
    if (data.ok) {
      status.className = 'status success';
      status.innerHTML = '&#10003; Claude connected! You can close this tab.';
      status.style.display = 'block';
      btn.textContent = 'Connected!';
    } else {
      status.className = 'status error';
      status.textContent = 'Failed: ' + (data.error || 'Unknown error');
      status.style.display = 'block';
      btn.disabled = false; btn.textContent = 'Save & Verify';
    }
  } catch(e) {
    status.className = 'status error';
    status.textContent = 'Error: ' + e.message;
    status.style.display = 'block';
    btn.disabled = false; btn.textContent = 'Save & Verify';
  }
}
</script></body></html>"""

_CODEX_HTML = """<!DOCTYPE html>
<html><head><title>RobotFlow — Codex Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0a;
color:#e5e5e5;min-height:100vh;display:flex;align-items:center;
justify-content:center}
.card{background:#1a1a1a;border:1px solid #333;border-radius:16px;
padding:40px;max-width:560px;width:100%}
h1{font-size:24px;margin-bottom:8px;color:#fff}
.sub{color:#888;margin-bottom:24px}
.steps{background:#111;border-radius:8px;padding:16px 20px;margin:16px 0}
.steps li{margin:8px 0;color:#ccc}
.steps code{background:#222;padding:2px 8px;border-radius:4px;color:#22d3ee}
textarea{width:100%;height:80px;background:#111;border:1px solid #444;
border-radius:8px;padding:12px;color:#fff;font-family:monospace;
font-size:13px;resize:vertical;margin:12px 0}
textarea:focus{outline:none;border-color:#10b981}
input{width:100%;background:#111;border:1px solid #444;
border-radius:8px;padding:12px;color:#fff;font-family:monospace;
font-size:13px;margin:8px 0}
input:focus{outline:none;border-color:#10b981}
button{background:#10b981;color:#fff;border:none;border-radius:8px;
padding:12px 32px;font-size:16px;cursor:pointer;width:100%;
font-weight:600;transition:background 0.2s}
button:hover{background:#059669}
button:disabled{background:#333;cursor:not-allowed}
.status{margin-top:16px;padding:12px;border-radius:8px;display:none}
.success{background:#052e16;color:#4ade80;border:1px solid #166534;display:block}
.error{background:#2a0a0a;color:#f87171;border:1px solid #7f1d1d;display:block}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:24px}
.logo span{font-size:28px}
label{color:#999;font-size:13px;display:block;margin-top:8px}
</style></head>
<body>
<div class="card">
  <div class="logo"><span>&#129302;</span><h1>RobotFlow — Codex Login</h1></div>
  <p class="sub">Connect your ChatGPT / Codex subscription</p>

  <div class="steps">
    <p><strong>Option A — API Key:</strong></p>
    <ol>
      <li>Go to <a href="https://platform.openai.com/api-keys" target="_blank"
          style="color:#10b981">platform.openai.com/api-keys</a></li>
      <li>Create or copy an API key</li>
    </ol>
  </div>

  <div class="steps">
    <p><strong>Option B — ChatGPT Bearer Token:</strong></p>
    <ol>
      <li>Open <a href="https://chatgpt.com" target="_blank"
          style="color:#10b981">chatgpt.com</a></li>
      <li>DevTools (F12) → Network tab</li>
      <li>Click any request, find <code>Authorization: Bearer ...</code></li>
      <li>Copy the token (without "Bearer " prefix)</li>
    </ol>
  </div>

  <textarea id="token" placeholder="Paste your API key or Bearer token here..."></textarea>
  <label>Account ID (optional — for ChatGPT subscription routing)</label>
  <input id="account" placeholder="acct-... (optional)" />
  <button onclick="submit()" id="btn">Save & Verify</button>
  <div id="status" class="status"></div>
</div>
<script>
async function submit() {
  let token = document.getElementById('token').value.trim();
  const account = document.getElementById('account').value.trim();
  if (!token) return;
  if (token.toLowerCase().startsWith('bearer ')) token = token.substring(7);
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  btn.disabled = true; btn.textContent = 'Verifying...';
  try {
    const res = await fetch('/api/save-token', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider: 'codex', token, account_id: account})
    });
    const data = await res.json();
    if (data.ok) {
      status.className = 'status success';
      let msg = '&#10003; Codex connected!';
      if (data.plan) msg += ' Plan: ' + data.plan;
      msg += ' You can close this tab.';
      status.innerHTML = msg;
      status.style.display = 'block';
      btn.textContent = 'Connected!';
    } else {
      status.className = 'status error';
      status.textContent = 'Failed: ' + (data.error || 'Unknown error');
      status.style.display = 'block';
      btn.disabled = false; btn.textContent = 'Save & Verify';
    }
  } catch(e) {
    status.className = 'status error';
    status.textContent = 'Error: ' + e.message;
    status.style.display = 'block';
    btn.disabled = false; btn.textContent = 'Save & Verify';
  }
}
</script></body></html>"""


class _BrowserAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for the browser auth flow."""

    store = None  # Set externally
    provider = "claude"
    done = False

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            html = (
                _CLAUDE_HTML
                if self.server._provider == "claude"
                else _CODEX_HTML
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/save-token":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            result = self._save_token(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            if result.get("ok"):
                self.server._done = True
        else:
            self.send_response(404)
            self.end_headers()

    def _save_token(self, body: dict) -> dict:
        """Verify and save the token."""
        import asyncio

        provider = body.get("provider", "claude")
        token = body.get("token", "").strip()
        account_id = body.get("account_id", "").strip()

        if not token:
            return {"ok": False, "error": "No token provided"}

        # Run async verification
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _verify_and_store(
                    self.server._store, provider, token, account_id
                )
            )
            return result
        finally:
            loop.close()

    def log_message(self, format, *args):
        pass


async def _verify_and_store(
    store, provider: str, token: str, account_id: str = ""
) -> dict:
    """Verify token with provider API, store if valid."""
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as http:
        if provider == "claude":
            from .claude_oauth import verify_claude_auth

            # Detect token type
            if token.startswith("sk-ant-api"):
                result = await verify_claude_auth(
                    http, api_key=token, auth_mode="api_key"
                )
                if result["ok"]:
                    store.set_api_key("claude", token)
            else:
                result = await verify_claude_auth(
                    http, oauth_token=token, auth_mode="oauth"
                )
                if result["ok"]:
                    store.set_oauth("claude", access_token=token)
        else:
            from .codex_oauth import verify_codex_auth

            if token.startswith("sk-"):
                result = await verify_codex_auth(
                    http, api_key=token, auth_mode="api_key"
                )
                if result["ok"]:
                    store.set_api_key("codex", token)
            else:
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

    return {
        "ok": result["ok"],
        "error": result.get("error"),
        "plan": result.get("plan"),
    }


def run_browser_login(provider: str) -> bool:
    """Launch browser auth flow for a provider.

    Opens http://localhost:18490 in the default browser with a
    styled login page. Returns True if auth was successful.
    """
    from .store import AuthStore

    store = AuthStore()

    server = HTTPServer(("127.0.0.1", PORT), _BrowserAuthHandler)
    server._store = store
    server._provider = provider
    server._done = False

    url = f"http://localhost:{PORT}/"

    print(f"\nOpening browser for {provider} login...")
    print("If the browser doesn't open, visit:\n")
    print(f"  {url}\n")

    import contextlib

    with contextlib.suppress(Exception):
        webbrowser.open(url)

    print("Waiting for authentication...")
    print("(Press Ctrl+C to cancel)\n")

    try:
        while not server._done:
            server.handle_request()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return False
    finally:
        server.server_close()

    return server._done
