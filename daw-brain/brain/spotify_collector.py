"""
Spotify data collection — pulls listening history, top artists/tracks,
recent plays, saved tracks, and audio features.
"""

import time
import logging
from spotipy.exceptions import SpotifyException

from brain.spotify_auth import get_spotify_client
from brain.database import (
    save_top_artists, save_top_tracks, save_recent_plays,
    save_saved_tracks, clear_spotify_data,
)

log = logging.getLogger("daw-brain")

TIME_RANGES = ["short_term", "medium_term", "long_term"]


def _retry_on_rate_limit(fn, max_retries=3):
    """Wrap a Spotify API call with retry-on-429 logic."""
    for attempt in range(max_retries):
        try:
            return fn()
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 2)) if e.headers else 2
                log.warning(f"Spotify 429 — retrying in {retry_after}s (attempt {attempt + 1})")
                time.sleep(retry_after)
            else:
                raise
    # Final attempt without catching
    return fn()


def _batch_audio_features(sp, track_ids):
    """Fetch audio features in batches of 50. Returns {track_id: features_dict}."""
    features_map = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i:i + 50]
        try:
            results = _retry_on_rate_limit(lambda b=batch: sp.audio_features(b))
            if results:
                for feat in results:
                    if feat and feat.get("id"):
                        features_map[feat["id"]] = feat
        except Exception as e:
            log.warning(f"Audio features batch failed: {e}")
    return features_map


def collect_top_artists(sp, user_id):
    """Fetch top 50 artists for each time range."""
    for time_range in TIME_RANGES:
        try:
            results = _retry_on_rate_limit(
                lambda tr=time_range: sp.current_user_top_artists(limit=50, time_range=tr)
            )
            artists = []
            for item in results.get("items", []):
                artists.append({
                    "id": item["id"],
                    "name": item["name"],
                    "genres": item.get("genres", []),
                    "popularity": item.get("popularity"),
                    "follower_count": item.get("followers", {}).get("total"),
                    "image_url": item["images"][0]["url"] if item.get("images") else None,
                })
            save_top_artists(user_id, artists, time_range)
            log.info(f"Collected {len(artists)} top artists ({time_range})")
        except Exception as e:
            log.error(f"Failed to collect top artists ({time_range}): {e}")


def collect_top_tracks(sp, user_id):
    """Fetch top 50 tracks for each time range, then batch-fetch audio features."""
    all_track_ids = set()
    tracks_by_range = {}

    for time_range in TIME_RANGES:
        try:
            results = _retry_on_rate_limit(
                lambda tr=time_range: sp.current_user_top_tracks(limit=50, time_range=tr)
            )
            tracks = []
            for item in results.get("items", []):
                track_id = item["id"]
                all_track_ids.add(track_id)
                artists = item.get("artists", [])
                tracks.append({
                    "id": track_id,
                    "name": item["name"],
                    "artist_name": artists[0]["name"] if artists else "Unknown",
                    "artist_id": artists[0]["id"] if artists else None,
                    "album_name": item.get("album", {}).get("name"),
                    "duration_ms": item.get("duration_ms"),
                    "popularity": item.get("popularity"),
                    "explicit": item.get("explicit", False),
                })
            tracks_by_range[time_range] = tracks
            log.info(f"Collected {len(tracks)} top tracks ({time_range})")
        except Exception as e:
            log.error(f"Failed to collect top tracks ({time_range}): {e}")

    # Batch-fetch audio features for all unique tracks
    features = _batch_audio_features(sp, list(all_track_ids))

    # Merge features and save
    for time_range, tracks in tracks_by_range.items():
        for track in tracks:
            track["audio_features"] = features.get(track["id"])
        save_top_tracks(user_id, tracks, time_range)


def collect_recent_plays(sp, user_id):
    """Fetch 50 most recently played tracks."""
    try:
        results = _retry_on_rate_limit(
            lambda: sp.current_user_recently_played(limit=50)
        )
        plays = []
        for item in results.get("items", []):
            track = item.get("track", {})
            artists = track.get("artists", [])
            context = item.get("context") or {}
            plays.append({
                "track_id": track.get("id"),
                "track_name": track.get("name"),
                "artist_name": artists[0]["name"] if artists else "Unknown",
                "played_at": item.get("played_at"),
                "context_type": context.get("type"),
                "context_name": context.get("uri"),
            })
        save_recent_plays(user_id, plays)
        log.info(f"Collected {len(plays)} recent plays")
    except Exception as e:
        log.error(f"Failed to collect recent plays: {e}")


def collect_saved_tracks(sp, user_id):
    """Fetch ALL of user's saved/liked tracks with audio features."""
    try:
        tracks = []
        track_ids = []
        offset = 0

        while True:
            results = _retry_on_rate_limit(
                lambda o=offset: sp.current_user_saved_tracks(limit=50, offset=o)
            )
            items = results.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track", {})
                if not track.get("id"):
                    continue  # Skip local files
                artists = track.get("artists", [])
                track_ids.append(track["id"])
                tracks.append({
                    "id": track["id"],
                    "name": track["name"],
                    "artist_name": artists[0]["name"] if artists else "Unknown",
                    "artist_id": artists[0]["id"] if artists else None,
                    "album_name": track.get("album", {}).get("name"),
                    "added_at": item.get("added_at"),
                })

            offset += len(items)
            if not results.get("next"):
                break

        # Batch audio features
        features = _batch_audio_features(sp, track_ids)
        for track in tracks:
            track["audio_features"] = features.get(track["id"])

        save_saved_tracks(user_id, tracks)
        log.info(f"Collected {len(tracks)} saved tracks")
    except Exception as e:
        log.error(f"Failed to collect saved tracks: {e}")


def collect_all_spotify_data(user_id):
    """Main collection function — pulls everything from Spotify.

    Clears existing data first for freshness, then runs all sub-collectors.
    Returns True on success, False on failure.
    """
    sp = get_spotify_client(user_id)
    if not sp:
        log.error(f"No Spotify client for user {user_id}")
        return False

    log.info(f"Starting full Spotify data collection for user {user_id}")

    # Clear existing listening data (not artist_research_cache or taste profile)
    clear_spotify_data(user_id)

    collect_top_artists(sp, user_id)
    collect_top_tracks(sp, user_id)
    collect_recent_plays(sp, user_id)
    collect_saved_tracks(sp, user_id)

    log.info(f"Spotify data collection complete for user {user_id}")
    return True
