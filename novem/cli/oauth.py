"""
OAuth 2.0 Authorization Code flow with PKCE for CLI authentication.

Opens the user's browser to the Novem login page. A lightweight local
HTTP server captures the authorization code callback, then exchanges
it for a Novem API token.

Falls back to out-of-band (OOB) manual code entry when the browser
can't be opened (headless servers, SSH sessions, etc.).
"""

import hashlib
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import requests

CLIENT_ID = "novem-cli"


def _generate_pkce() -> Tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    # base64url-encode without padding
    challenge = digest.hex()  # not what we want — need proper base64url
    # proper base64url encoding
    import base64

    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback and serves a success page."""

    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        _CallbackHandler.code = params.get("code", [None])[0]
        _CallbackHandler.state = params.get("state", [None])[0]
        _CallbackHandler.error = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        if _CallbackHandler.code:
            body = (
                "<html><body style='font-family:system-ui;text-align:center;padding:60px'>"
                "<h2>Authentication successful</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
                "</body></html>"
            )
        else:
            error_desc = params.get("error_description", ["Unknown error"])[0]
            body = (
                "<html><body style='font-family:system-ui;text-align:center;padding:60px'>"
                f"<h2>Authentication failed</h2><p>{error_desc}</p>"
                "</body></html>"
            )
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default request logging."""
        pass


def oauth_authenticate(
    api_root: str,
    ignore_ssl: bool = False,
) -> str:
    """
    Run the OAuth flow and return the API token.

    1. Start local callback server
    2. Open browser to authorize endpoint
    3. Wait for callback with auth code
    4. Exchange code for token

    Falls back to OOB if browser can't be opened.

    Returns:
        token string

    Raises:
        SystemExit on failure
    """
    # Derive OAuth base URL from api_root (e.g. https://api.novem.io/v1/ → https://api.novem.io)
    parsed = urlparse(api_root)
    oauth_base = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in (80, 443):
        oauth_base = f"{oauth_base}:{parsed.port}"

    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    # Try browser-based flow with local callback server
    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"

    code = _try_browser_flow(oauth_base, redirect_uri, state, code_challenge, port)

    if code is None:
        # Fallback to OOB
        code = _try_oob_flow(oauth_base, state, code_challenge)

    if not code:
        print("Authentication cancelled.")
        sys.exit(1)

    # Exchange code for token
    return _exchange_code(oauth_base, code, code_verifier, redirect_uri, ignore_ssl)


def _try_browser_flow(
    oauth_base: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    port: int,
) -> Optional[str]:
    """Open browser and wait for callback. Returns auth code or None."""
    params = urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorize_url = f"{oauth_base}/oauth/authorize?{params}"

    # Reset handler state
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    _CallbackHandler.error = None

    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    # Try opening browser
    print("\n  Opening browser to sign in...\n")
    print(f"  If the browser doesn't open, visit:\n  {authorize_url}\n")

    try:
        opened = webbrowser.open(authorize_url)
    except Exception:
        opened = False

    if not opened:
        return None

    # Wait for the callback (blocks until request or timeout)
    # Run in a thread so we can handle keyboard interrupt
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    try:
        server_thread.join(timeout=120)
    except KeyboardInterrupt:
        server.server_close()
        return None

    server.server_close()

    if _CallbackHandler.error:
        print(f"  Authentication error: {_CallbackHandler.error}")
        return None

    if _CallbackHandler.state != state:
        print("  State mismatch — possible CSRF attack.")
        return None

    return _CallbackHandler.code


def _try_oob_flow(
    oauth_base: str,
    state: str,
    code_challenge: str,
) -> Optional[str]:
    """Fallback: print URL, user pastes auth code manually."""
    params = urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorize_url = f"{oauth_base}/oauth/authorize?{params}"

    print("\n  Open this URL in your browser to sign in:\n")
    print(f"  {authorize_url}\n")

    try:
        code = input("  Paste the authorization code here: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    return code or None


def _exchange_code(
    oauth_base: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    ignore_ssl: bool,
) -> str:
    """Exchange authorization code for a Novem API token."""
    resp = requests.post(
        f"{oauth_base}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        verify=not ignore_ssl,
    )

    if resp.status_code != 200:
        try:
            error = resp.json().get("error_description", resp.text)
        except Exception:
            error = resp.text[:200]
        print(f"  Token exchange failed: {error}")
        sys.exit(1)

    data = resp.json()
    return data["access_token"]
