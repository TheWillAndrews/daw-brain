"""
Spotify OAuth authentication for DAW Brain.
Uses spotipy SpotifyOAuth — tokens stored in SQLite, not file cache.
"""

import os
import re
import subprocess
import time
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from brain.database import (
    get_user_by_spotify_id, create_user, update_user, update_last_login,
    save_spotify_tokens, get_spotify_tokens, update_access_token,
)

log = logging.getLogger("daw-brain")


def _load_env_from_shell():
    """Load SPOTIFY_CLIENT_ID/SECRET from the user's shell if not in os.environ.

    Non-interactive shells (scripts, IDEs, some terminal launchers) don't source
    ~/.zshrc, so the vars can be missing even though the user exported them.
    """
    needed = ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"]
    missing = [k for k in needed if not os.environ.get(k)]
    if not missing:
        return

    # Try sourcing the user's shell profile and extracting the vars
    try:
        cmd = 'source ~/.zshrc 2>/dev/null; echo "___DELIM___"; env'
        result = subprocess.run(
            ["zsh", "-c", cmd],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # Parse env output after delimiter
            env_section = result.stdout.split("___DELIM___")[-1]
            for line in env_section.strip().splitlines():
                if "=" in line:
                    key, _, val = line.partition("=")
                    if key in missing:
                        os.environ[key] = val
                        log.info(f"Loaded {key} from ~/.zshrc")
    except Exception as e:
        log.warning(f"Could not load env from shell: {e}")


_load_env_from_shell()

SCOPES = "user-top-read user-read-recently-played user-library-read user-read-private user-read-email"
REDIRECT_URI = "http://127.0.0.1:5050/callback/spotify"


def _get_oauth():
    """Build a SpotifyOAuth manager (no file cache)."""
    return SpotifyOAuth(
        client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
        client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_handler=spotipy.MemoryCacheHandler(),
    )


def get_auth_url():
    """Return the Spotify authorization URL to redirect the user to."""
    oauth = _get_oauth()
    return oauth.get_authorize_url()


def handle_callback(code):
    """Exchange auth code for tokens, create/update user, return user dict.

    Returns: dict with keys id, display_name, avatar_url, etc.
    """
    oauth = _get_oauth()
    token_info = oauth.get_access_token(code, as_dict=True)

    access_token = token_info["access_token"]
    refresh_token = token_info["refresh_token"]
    expires_at = token_info.get("expires_at", int(time.time()) + 3600)

    # Fetch Spotify user profile
    sp = spotipy.Spotify(auth=access_token)
    me = sp.current_user()

    spotify_id = me["id"]
    display_name = me.get("display_name") or spotify_id
    email = me.get("email")
    avatar_url = me["images"][0]["url"] if me.get("images") else None
    country = me.get("country")
    product = me.get("product")

    # Find or create user
    user = get_user_by_spotify_id(spotify_id)
    if user:
        user_id = user["id"]
        update_user(user_id,
                    display_name=display_name,
                    email=email,
                    avatar_url=avatar_url,
                    spotify_country=country,
                    spotify_product=product)
        update_last_login(user_id)
    else:
        user_id = create_user(
            spotify_id=spotify_id,
            display_name=display_name,
            email=email,
            avatar_url=avatar_url,
            spotify_country=country,
            spotify_product=product,
        )

    # Save tokens
    save_spotify_tokens(user_id, access_token, refresh_token, expires_at, SCOPES)

    log.info(f"Spotify OAuth complete for {display_name} (user_id={user_id})")

    return {
        "id": user_id,
        "spotify_id": spotify_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }


def get_spotify_client(user_id):
    """Return an authenticated spotipy.Spotify client for this user.

    Automatically refreshes expired tokens.
    Returns None if no tokens found.
    """
    tokens = get_spotify_tokens(user_id)
    if not tokens:
        return None

    # Check if token is expired (with 60s buffer)
    expires_at = tokens.get("token_expiry")
    if expires_at and float(expires_at) < time.time() + 60:
        new_token = refresh_access_token(user_id)
        if not new_token:
            return None
        return spotipy.Spotify(auth=new_token)

    return spotipy.Spotify(auth=tokens["access_token"])


def refresh_access_token(user_id):
    """Refresh the access token using the stored refresh token.

    Returns the new access token string, or None on failure.
    """
    tokens = get_spotify_tokens(user_id)
    if not tokens or not tokens.get("refresh_token"):
        log.warning(f"No refresh token for user {user_id}")
        return None

    try:
        oauth = _get_oauth()
        new_info = oauth.refresh_access_token(tokens["refresh_token"])
        new_access = new_info["access_token"]
        new_expiry = new_info.get("expires_at", int(time.time()) + 3600)

        # If Spotify rotated the refresh token, save the new one
        new_refresh = new_info.get("refresh_token", tokens["refresh_token"])
        if new_refresh != tokens["refresh_token"]:
            save_spotify_tokens(user_id, new_access, new_refresh, new_expiry, SCOPES)
        else:
            update_access_token(user_id, new_access, new_expiry)

        log.info(f"Refreshed Spotify token for user {user_id}")
        return new_access
    except Exception as e:
        log.error(f"Token refresh failed for user {user_id}: {e}")
        return None
