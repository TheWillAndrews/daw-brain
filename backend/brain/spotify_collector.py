"""
Spotify data collection — pulls listening history, top artists/tracks,
recent plays, saved tracks, and followed artists.

NOTE: audio_features, popularity, followers, and batch endpoints were
removed by Spotify (Nov 2024 / Feb 2026). Genre-based taste profiling
replaces audio features.
"""

import time
import logging
from spotipy.exceptions import SpotifyException

from brain.spotify_auth import get_spotify_client
from brain.database import (
    save_top_artists, save_top_tracks, save_recent_plays,
    save_saved_tracks, save_followed_artists, clear_spotify_data,
    save_artist_edge, artist_in_research_cache, queue_for_research,
    get_user_top_artists,
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
                    "image_url": item["images"][0]["url"] if item.get("images") else None,
                })
            save_top_artists(user_id, artists, time_range)
            log.info(f"Collected {len(artists)} top artists ({time_range})")
            time.sleep(0.2)
        except Exception as e:
            log.error(f"Failed to collect top artists ({time_range}): {e}")


def collect_top_tracks(sp, user_id):
    """Fetch top 50 tracks for each time range."""
    for time_range in TIME_RANGES:
        try:
            results = _retry_on_rate_limit(
                lambda tr=time_range: sp.current_user_top_tracks(limit=50, time_range=tr)
            )
            tracks = []
            for item in results.get("items", []):
                artists = item.get("artists", [])
                tracks.append({
                    "id": item["id"],
                    "name": item["name"],
                    "artist_name": artists[0]["name"] if artists else "Unknown",
                    "artist_id": artists[0]["id"] if artists else None,
                    "album_name": item.get("album", {}).get("name"),
                    "album_release_date": item.get("album", {}).get("release_date", ""),
                    "duration_ms": item.get("duration_ms"),
                    "explicit": item.get("explicit", False),
                    "external_ids": item.get("external_ids", {}),
                })
            save_top_tracks(user_id, tracks, time_range)
            log.info(f"Collected {len(tracks)} top tracks ({time_range})")
            time.sleep(0.2)
        except Exception as e:
            log.error(f"Failed to collect top tracks ({time_range}): {e}")


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
            plays.append({
                "track_id": track.get("id"),
                "track_name": track.get("name"),
                "artist_name": artists[0]["name"] if artists else "Unknown",
                "artist_id": artists[0]["id"] if artists else None,
                "played_at": item.get("played_at"),
                "duration_ms": track.get("duration_ms"),
            })
        save_recent_plays(user_id, plays)
        log.info(f"Collected {len(plays)} recent plays")
    except Exception as e:
        log.error(f"Failed to collect recent plays: {e}")


def collect_saved_tracks(sp, user_id):
    """Fetch user's saved/liked tracks (up to 200)."""
    try:
        tracks = []
        offset = 0

        while offset < 200:
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
            time.sleep(0.2)

        save_saved_tracks(user_id, tracks)
        log.info(f"Collected {len(tracks)} saved tracks")
    except Exception as e:
        log.error(f"Failed to collect saved tracks: {e}")


def collect_followed_artists(sp, user_id):
    """Fetch all followed artists (paginated with cursor)."""
    try:
        all_artists = []
        after = None

        while True:
            if after:
                results = _retry_on_rate_limit(
                    lambda a=after: sp.current_user_followed_artists(limit=50, after=a)
                )
            else:
                results = _retry_on_rate_limit(
                    lambda: sp.current_user_followed_artists(limit=50)
                )

            items = results.get("artists", {}).get("items", [])
            if not items:
                break

            for artist in items:
                all_artists.append({
                    "id": artist["id"],
                    "name": artist["name"],
                    "genres": artist.get("genres", []),
                    "image_url": artist["images"][0]["url"] if artist.get("images") else None,
                })

            # Cursor-based pagination
            cursors = results.get("artists", {}).get("cursors", {})
            after = cursors.get("after")
            if not after:
                break
            time.sleep(0.2)

        save_followed_artists(user_id, all_artists)
        log.info(f"Collected {len(all_artists)} followed artists")
    except Exception as e:
        log.error(f"Failed to collect followed artists: {e}")


def crawl_related_artists(sp, user_id, depth=1):
    """Crawl the Spotify Related Artists graph from user's top artists.

    Stores connections in artist_graph table.
    Queues newly discovered artists for research.
    Returns number of artists crawled.
    """
    # Get seed artist IDs from top artists
    top_artists = get_user_top_artists(user_id)
    if not top_artists:
        return 0

    # Deduplicate artist IDs
    seen_ids = set()
    seed_ids = []
    for a in top_artists:
        aid = a.get("artist_id")
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            seed_ids.append(aid)

    # Limit to top 15 seeds to avoid excessive API calls
    seed_ids = seed_ids[:15]
    crawled = 0

    for artist_id in seed_ids:
        try:
            related = _retry_on_rate_limit(
                lambda aid=artist_id: sp.artist_related_artists(aid)
            )
            # Get source artist name from our data
            source_name = next(
                (a["artist_name"] for a in top_artists if a.get("artist_id") == artist_id),
                "Unknown"
            )

            for rel in related.get("artists", []):
                # Store the graph edge
                save_artist_edge({
                    "source_artist_id": artist_id,
                    "related_artist_id": rel["id"],
                    "source_name": source_name,
                    "related_name": rel["name"],
                })

                # Queue for research if not already cached
                if not artist_in_research_cache(rel["name"]):
                    queue_for_research(
                        rel["id"], rel["name"],
                        user_id=user_id, priority=0
                    )

            crawled += 1
            time.sleep(0.3)  # respect rate limits

        except Exception as e:
            log.warning(f"Error crawling related artists for {artist_id}: {e}")
            continue

    log.info(f"Crawled related artists for {crawled}/{len(seed_ids)} seed artists")
    return crawled


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
    collect_followed_artists(sp, user_id)

    # Crawl related artists graph (non-blocking — failures logged but not fatal)
    try:
        crawl_related_artists(sp, user_id)
    except Exception as e:
        log.warning(f"Related artist crawl failed: {e}")

    log.info(f"Spotify data collection complete for user {user_id}")
    return True
