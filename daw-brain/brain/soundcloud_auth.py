"""
SoundCloud OAuth 2.1 with PKCE authentication for DAW Brain.
Tokens stored in SQLite, same pattern as Spotify integration.
"""

import os
import base64
import hashlib
import secrets
import time
import logging
from urllib.parse import urlencode
import requests

from brain.database import (
    get_user_by_soundcloud_id, create_user, update_user, update_last_login,
    save_soundcloud_tokens, get_soundcloud_tokens,
)

log = logging.getLogger("daw-brain")

# ─── Env Loading ──────────────────────────────────────────────

def _load_env_from_shell():
    """Load SOUNDCLOUD_CLIENT_ID/SECRET from the user's shell if missing."""
    import subprocess
    needed = ["SOUNDCLOUD_CLIENT_ID", "SOUNDCLOUD_CLIENT_SECRET"]
    missing = [k for k in needed if not os.environ.get(k)]
    if not missing:
        return
    try:
        cmd = 'source ~/.zshrc 2>/dev/null; echo "___DELIM___"; env'
        result = subprocess.run(
            ["zsh", "-c", cmd], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            env_section = result.stdout.split("___DELIM___")[-1]
            for line in env_section.strip().splitlines():
                if "=" in line:
                    key, _, val = line.partition("=")
                    if key in missing:
                        os.environ[key] = val
                        log.info(f"Loaded {key} from ~/.zshrc")
    except Exception as e:
        log.warning(f"Could not load SoundCloud env from shell: {e}")


_load_env_from_shell()

REDIRECT_URI = "http://127.0.0.1:5050/callback/soundcloud"
AUTH_URL = "https://secure.soundcloud.com/authorize"
TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
API_BASE = "https://api.soundcloud.com"


# ─── PKCE Helpers ─────────────────────────────────────────────

def generate_pkce():
    """Generate PKCE code_verifier and code_challenge (S256).

    Returns (code_verifier, code_challenge).
    """
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _basic_auth_header():
    """Build HTTP Basic auth header from client_id:client_secret."""
    client_id = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
    client_secret = os.environ.get("SOUNDCLOUD_CLIENT_SECRET", "")
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return f"Basic {creds}"


# ─── OAuth Flow ───────────────────────────────────────────────

def get_auth_url(flask_session):
    """Build the SoundCloud authorization URL with PKCE.

    Stores code_verifier and state in Flask session for the callback.
    Returns the authorization URL string.
    """
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    flask_session["sc_code_verifier"] = code_verifier
    flask_session["sc_oauth_state"] = state

    client_id = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    url = f"{AUTH_URL}?{params}"
    log.info(f"SoundCloud auth URL: {AUTH_URL}?client_id={client_id[:8]}...&redirect_uri={REDIRECT_URI}")
    return url


def handle_callback(code, code_verifier):
    """Exchange auth code for tokens, create/update user, return user dict.

    Returns: dict with keys id, display_name, soundcloud_id, avatar_url.
    """
    client_id = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
    client_secret = os.environ.get("SOUNDCLOUD_CLIENT_SECRET", "")

    # Exchange code for tokens — SoundCloud requires Basic auth header
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json; charset=utf-8",
            "Authorization": _basic_auth_header(),
        },
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "code": code,
        },
        timeout=15,
    )
    if not resp.ok:
        log.error(f"SoundCloud token exchange failed: {resp.status_code} {resp.text[:200]}")
    resp.raise_for_status()
    token_data = resp.json()

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    token_expiry = int(time.time()) + expires_in

    # Fetch user profile
    me_resp = requests.get(
        f"{API_BASE}/me",
        headers={"Authorization": f"OAuth {access_token}"},
        timeout=10,
    )
    me_resp.raise_for_status()
    me = me_resp.json()

    soundcloud_id = str(me["id"])
    display_name = me.get("username") or me.get("permalink") or soundcloud_id
    avatar_url = me.get("avatar_url")
    city = me.get("city")
    country = me.get("country_code")

    # Find or create user
    user = get_user_by_soundcloud_id(soundcloud_id)
    if user:
        user_id = user["id"]
        update_user(user_id,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    soundcloud_id=soundcloud_id)
        update_last_login(user_id)
    else:
        user_id = create_user(
            soundcloud_id=soundcloud_id,
            display_name=display_name,
            avatar_url=avatar_url,
        )

    # Save tokens
    save_soundcloud_tokens(user_id, access_token, refresh_token, token_expiry)

    log.info(f"SoundCloud OAuth complete for {display_name} (user_id={user_id})")

    return {
        "id": user_id,
        "soundcloud_id": soundcloud_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }


# ─── Authenticated Client ────────────────────────────────────

class SoundCloudClient:
    """Simple authenticated SoundCloud API client."""

    def __init__(self, access_token):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"OAuth {access_token}",
            "Accept": "application/json",
        })

    def get(self, path, params=None, timeout=15):
        """Make an authenticated GET request to the SoundCloud API."""
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


def get_soundcloud_client(user_id):
    """Return an authenticated SoundCloudClient for this user.

    Automatically refreshes expired tokens.
    Returns None if no tokens found.
    """
    tokens = get_soundcloud_tokens(user_id)
    if not tokens:
        return None

    # Check if token is expired (with 60s buffer)
    expiry = tokens.get("token_expiry")
    if expiry and float(expiry) < time.time() + 60:
        new_token = refresh_access_token(user_id)
        if not new_token:
            return None
        return SoundCloudClient(new_token)

    return SoundCloudClient(tokens["access_token"])


def refresh_access_token(user_id):
    """Refresh the access token using the stored refresh token.

    Returns the new access token string, or None on failure.
    """
    tokens = get_soundcloud_tokens(user_id)
    if not tokens or not tokens.get("refresh_token"):
        log.warning(f"No SoundCloud refresh token for user {user_id}")
        return None

    try:
        client_id = os.environ.get("SOUNDCLOUD_CLIENT_ID", "")
        client_secret = os.environ.get("SOUNDCLOUD_CLIENT_SECRET", "")
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json; charset=utf-8",
                "Authorization": _basic_auth_header(),
            },
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": tokens["refresh_token"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", tokens["refresh_token"])
        new_expiry = int(time.time()) + data.get("expires_in", 3600)

        save_soundcloud_tokens(user_id, new_access, new_refresh, new_expiry)
        log.info(f"Refreshed SoundCloud token for user {user_id}")
        return new_access
    except Exception as e:
        log.error(f"SoundCloud token refresh failed for user {user_id}: {e}")
        return None
