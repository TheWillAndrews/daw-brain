"""
SoundCloud data collection — pulls likes, followings, reposts, playlists,
and user's own tracks from the SoundCloud API.
"""

import time
import logging

from brain.soundcloud_auth import get_soundcloud_client
from brain.database import (
    save_soundcloud_likes, save_soundcloud_followings,
    save_soundcloud_reposts, save_soundcloud_playlists,
    save_soundcloud_user_tracks, clear_soundcloud_data,
)

log = logging.getLogger("daw-brain")


def _paginated_collect(client, path, limit=200, max_items=1000):
    """Collect paginated results from SoundCloud API.

    SoundCloud uses linked_partitioning with next_href for pagination.
    Returns list of items.
    """
    items = []
    params = {"limit": min(limit, 200), "linked_partitioning": "true"}

    url = path
    retries = 0

    while url and len(items) < max_items:
        try:
            data = client.get(url, params=params if not url.startswith("http") else None)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429 and retries < 3:
                retries += 1
                wait = 2 ** retries
                log.warning(f"SoundCloud 429 — retrying in {wait}s (attempt {retries})")
                time.sleep(wait)
                continue
            else:
                log.error(f"SoundCloud API error on {path}: {e}")
                break

        retries = 0

        # SoundCloud returns collection for most endpoints
        collection = data.get("collection", data) if isinstance(data, dict) else data
        if isinstance(collection, list):
            items.extend(collection)
        elif isinstance(data, dict) and "collection" not in data:
            # Some endpoints return items directly in a list
            break

        # Follow next_href for pagination
        next_href = data.get("next_href") if isinstance(data, dict) else None
        if next_href:
            url = next_href
            params = None  # next_href includes all params
        else:
            break

    return items[:max_items]


def collect_likes(client, user_id):
    """Fetch user's liked tracks — strongest taste signal on SoundCloud."""
    try:
        raw_items = _paginated_collect(client, "/me/likes", limit=200, max_items=500)
        likes = []
        for item in raw_items:
            # Likes can contain tracks or playlists; we want tracks
            track = item.get("track") or item
            if not track.get("id"):
                continue
            user_obj = track.get("user", {})
            likes.append({
                "track_id": str(track["id"]),
                "track_title": track.get("title", ""),
                "artist_name": user_obj.get("username", "Unknown"),
                "artist_id": str(user_obj.get("id", "")),
                "genre": track.get("genre", ""),
                "tag_list": track.get("tag_list", ""),
                "duration_ms": track.get("duration"),
                "playback_count": track.get("playback_count"),
                "likes_count": track.get("likes_count") or track.get("favoritings_count"),
                "reposts_count": track.get("reposts_count"),
                "created_at_sc": track.get("created_at", ""),
                "liked_at": item.get("created_at", ""),
            })
        save_soundcloud_likes(user_id, likes)
        log.info(f"Collected {len(likes)} SoundCloud likes")
    except Exception as e:
        log.error(f"Failed to collect SoundCloud likes: {e}")


def collect_followings(client, user_id):
    """Fetch artists the user follows."""
    try:
        raw_items = _paginated_collect(client, "/me/followings", limit=200, max_items=500)
        followings = []
        for item in raw_items:
            followings.append({
                "artist_id": str(item.get("id", "")),
                "artist_name": item.get("username", "Unknown"),
                "artist_permalink": item.get("permalink", ""),
                "followers_count": item.get("followers_count", 0),
                "track_count": item.get("track_count", 0),
                "genre": item.get("genre", ""),
                "city": item.get("city", ""),
                "country": item.get("country_code", ""),
            })
        save_soundcloud_followings(user_id, followings)
        log.info(f"Collected {len(followings)} SoundCloud followings")
    except Exception as e:
        log.error(f"Failed to collect SoundCloud followings: {e}")


def collect_reposts(client, user_id):
    """Fetch user's reposts — public endorsement, stronger than likes."""
    try:
        raw_items = _paginated_collect(client, "/me/reposts", limit=100, max_items=200)
        reposts = []
        for item in raw_items:
            track = item.get("track") or item
            if not track.get("id"):
                continue
            user_obj = track.get("user", {})
            reposts.append({
                "track_id": str(track["id"]),
                "track_title": track.get("title", ""),
                "artist_name": user_obj.get("username", "Unknown"),
                "artist_id": str(user_obj.get("id", "")),
                "genre": track.get("genre", ""),
                "tag_list": track.get("tag_list", ""),
                "reposted_at": item.get("created_at", ""),
            })
        save_soundcloud_reposts(user_id, reposts)
        log.info(f"Collected {len(reposts)} SoundCloud reposts")
    except Exception as e:
        log.error(f"Failed to collect SoundCloud reposts: {e}")


def collect_playlists(client, user_id):
    """Fetch user's playlists — names and tags are rich taste signals."""
    try:
        raw_items = _paginated_collect(client, "/me/playlists", limit=50, max_items=100)
        playlists = []
        for item in raw_items:
            playlists.append({
                "playlist_id": str(item.get("id", "")),
                "playlist_title": item.get("title", ""),
                "description": item.get("description", ""),
                "genre": item.get("genre", ""),
                "tag_list": item.get("tag_list", ""),
                "track_count": item.get("track_count", 0),
                "is_public": item.get("sharing") == "public",
                "created_at_sc": item.get("created_at", ""),
            })
        save_soundcloud_playlists(user_id, playlists)
        log.info(f"Collected {len(playlists)} SoundCloud playlists")
    except Exception as e:
        log.error(f"Failed to collect SoundCloud playlists: {e}")


def collect_user_tracks(client, user_id):
    """Fetch user's own uploaded tracks — direct production insight."""
    try:
        raw_items = _paginated_collect(client, "/me/tracks", limit=50, max_items=100)
        tracks = []
        for item in raw_items:
            tracks.append({
                "track_id": str(item.get("id", "")),
                "track_title": item.get("title", ""),
                "genre": item.get("genre", ""),
                "tag_list": item.get("tag_list", ""),
                "bpm": item.get("bpm"),
                "key_signature": item.get("key_signature", ""),
                "duration_ms": item.get("duration"),
                "playback_count": item.get("playback_count"),
                "likes_count": item.get("likes_count") or item.get("favoritings_count"),
                "created_at_sc": item.get("created_at", ""),
            })
        save_soundcloud_user_tracks(user_id, tracks)
        log.info(f"Collected {len(tracks)} SoundCloud user tracks")
    except Exception as e:
        log.error(f"Failed to collect SoundCloud user tracks: {e}")


def collect_all_soundcloud_data(user_id):
    """Main collection function — pulls everything from SoundCloud.

    Clears existing data first for freshness, then runs all sub-collectors
    sequentially (to respect rate limits).
    Returns True on success, False on failure.
    """
    client = get_soundcloud_client(user_id)
    if not client:
        log.error(f"No SoundCloud client for user {user_id}")
        return False

    log.info(f"Starting full SoundCloud data collection for user {user_id}")

    # Clear existing SoundCloud data (not artist_research_cache)
    clear_soundcloud_data(user_id)

    # Collect sequentially to respect rate limits
    collect_likes(client, user_id)
    time.sleep(0.5)
    collect_followings(client, user_id)
    time.sleep(0.5)
    collect_reposts(client, user_id)
    time.sleep(0.5)
    collect_playlists(client, user_id)
    time.sleep(0.5)
    collect_user_tracks(client, user_id)

    log.info(f"SoundCloud data collection complete for user {user_id}")
    return True
