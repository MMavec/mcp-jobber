"""One-shot helper to complete the OAuth 2 authorization-code flow.

Run `mcp-jobber-auth` once after registering your app at
developer.getjobber.com. It opens the consent page, captures the redirect on a
throwaway localhost server, exchanges the code for tokens, and prints the
`refresh_token` you should put in `JOBBER_REFRESH_TOKEN`. The full token bundle
is also written to the token cache so the server can start immediately.
"""

from __future__ import annotations

import http.server
import secrets
import sys
import time
import urllib.parse
import webbrowser
from threading import Event

import httpx

from .auth import TokenBundle
from .config import load_settings


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code_holder: dict[str, str] = {}
    expected_state: str = ""
    done = Event()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if params.get("state", [""])[0] != self.expected_state:
            self.wfile.write(b"<h1>State mismatch. Close this tab and retry.</h1>")
            return
        if "code" not in params:
            err = params.get("error", ["unknown"])[0]
            self.wfile.write(f"<h1>Authorization failed: {err}</h1>".encode())
            return

        self.code_holder["code"] = params["code"][0]
        self.wfile.write(b"<h1>mcp-jobber: authorized. You can close this tab.</h1>")
        self.done.set()

    def log_message(self, *_args) -> None:  # silence the default stderr spam
        return


def main() -> int:
    settings = load_settings()
    if not (settings.client_id and settings.client_secret):
        print("Set JOBBER_CLIENT_ID and JOBBER_CLIENT_SECRET first.", file=sys.stderr)
        return 1

    redirect = urllib.parse.urlparse(settings.redirect_uri)
    host = redirect.hostname or "localhost"
    port = redirect.port or 8976

    state = secrets.token_urlsafe(16)
    authorize_url = (
        f"{settings.oauth_authorize_url}?"
        + urllib.parse.urlencode(
            {
                "client_id": settings.client_id,
                "redirect_uri": settings.redirect_uri,
                "response_type": "code",
                "state": state,
            }
        )
    )

    _CallbackHandler.expected_state = state
    server = http.server.HTTPServer((host, port), _CallbackHandler)

    print("Opening the Jobber consent page in your browser...")
    print(f"If it does not open, visit:\n  {authorize_url}\n")
    webbrowser.open(authorize_url)

    while not _CallbackHandler.done.is_set():
        server.handle_request()

    code = _CallbackHandler.code_holder.get("code")
    if not code:
        print("No authorization code received.", file=sys.stderr)
        return 1

    resp = httpx.post(
        settings.oauth_token_url,
        data={
            "grant_type": "authorization_code",
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "code": code,
            "redirect_uri": settings.redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=settings.request_timeout_seconds,
    )
    if resp.status_code >= 400:
        print(f"Token exchange failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        return 1

    payload = resp.json()
    refresh_token = payload.get("refresh_token", "")
    bundle = TokenBundle(
        access_token=payload["access_token"],
        refresh_token=refresh_token or None,
        expires_at=time.time() + float(payload.get("expires_in", 3600)),
    )
    cache_path = settings.resolved_token_cache()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(bundle.to_json())
    cache_path.chmod(0o600)

    print("\nAuthorized. Token cache written to:", cache_path)
    if refresh_token:
        print("\nAdd this to your environment / MCP config:")
        print(f"  JOBBER_REFRESH_TOKEN={refresh_token}")
    else:
        print("\nNo refresh_token returned; the token cache will be used until it expires.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
