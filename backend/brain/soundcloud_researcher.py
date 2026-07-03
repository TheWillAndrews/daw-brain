"""
SoundCloud artist research — extracts top artists from SoundCloud data
and feeds them into the shared artist research pipeline.

Uses the same structured JSON research from artist_researcher.py.
"""

import json
import logging
import threading
from collections import Counter

from brain.database import (
    get_soundcloud_likes, get_soundcloud_followings,
    get_artist_research, save_artist_research,
    get_unresearched_artists, get_stale_artist_research,
    save_soundcloud_production_dna, update_soundcloud_research_status,
    get_soundcloud_taste_profile,
)
from brain.artist_researcher import (
    _research_single_artist, _format_profile_summary,
    SYNTHESIS_PROMPT, MODEL,
)

log = logging.getLogger("daw-brain")


def _get_top_soundcloud_artists(user_id, limit=15):
    """Merge artists from follows, likes, and reposts. Return top N names with genres."""
    artist_scores = Counter()
    artist_genres = {}

    # Followings: by order (earlier = more intentional)
    followings = get_soundcloud_followings(user_id)
    for i, f in enumerate(followings):
        name = f.get("artist_name", "").strip()
        if not name or name == "Unknown":
            continue
        artist_scores[name] += max(1, 5 - i // 20)
        if name not in artist_genres:
            genre = f.get("genre", "")
            artist_genres[name] = [genre] if genre else []

    # Most-liked artists: count how many likes per artist
    likes = get_soundcloud_likes(user_id)
    like_artist_counts = Counter()
    for l in likes:
        name = l.get("artist_name", "").strip()
        if name and name != "Unknown":
            like_artist_counts[name] += 1
            if name not in artist_genres:
                genre = l.get("genre", "")
                artist_genres[name] = [genre] if genre else []

    for name, count in like_artist_counts.items():
        artist_scores[name] += count * 2

    # Repost artists
    from brain.database import get_connection, _rows_to_dicts
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM soundcloud_reposts WHERE user_id = ?", (user_id,)
        ).fetchall()
        reposts = _rows_to_dicts(rows)

    for r in reposts:
        name = r.get("artist_name", "").strip()
        if name and name != "Unknown":
            artist_scores[name] += 3
            if name not in artist_genres:
                genre = r.get("genre", "")
                artist_genres[name] = [genre] if genre else []

    top = artist_scores.most_common(limit)
    return [(name, artist_genres.get(name, [])) for name, _ in top]


def research_soundcloud_artists(user_id):
    """Research the user's top SoundCloud artists' production styles.

    Uses the shared artist_research_cache — skips already-researched artists.
    Now returns structured JSON profiles via the shared research pipeline.
    """
    update_soundcloud_research_status(user_id, "in_progress")

    try:
        top_artists = _get_top_soundcloud_artists(user_id, limit=15)
        if not top_artists:
            log.warning(f"No top SoundCloud artists found for user {user_id}")
            update_soundcloud_research_status(user_id, "complete")
            return

        artist_names = [name for name, _ in top_artists]

        # Check shared cache — skip already researched
        unresearched = get_unresearched_artists(artist_names)
        stale = get_stale_artist_research(artist_names, max_age_days=90)
        needs_research = list(set(unresearched + stale))

        log.info(f"SoundCloud artist research: {len(top_artists)} total, "
                 f"{len(needs_research)} need research")

        if needs_research:
            import anthropic
            import time
            client = anthropic.Anthropic()

            for i in range(0, len(needs_research), 3):
                batch = needs_research[i:i + 3]
                for artist_name in batch:
                    # Find genres for this artist
                    genres = []
                    for name, g in top_artists:
                        if name == artist_name:
                            genres = g
                            break

                    profile = _research_single_artist(client, artist_name, genres)
                    if not profile:
                        continue

                    save_artist_research(artist_name, profile)
                    log.info(
                        f"Researched (SoundCloud): {artist_name} "
                        f"(confidence: {profile.get('research_metadata', {}).get('confidence_score', '?')})"
                    )

                if i + 3 < len(needs_research):
                    time.sleep(1)

        # Synthesis: build Production DNA from all researched structured profiles
        profile_summaries = []
        for artist_name, _ in top_artists:
            cached = get_artist_research(artist_name)
            if cached and cached.get("profile"):
                summary = _format_profile_summary(cached["profile"])
                profile_summaries.append(summary)

        if profile_summaries:
            try:
                import anthropic
                client = anthropic.Anthropic()
                synthesis_prompt = SYNTHESIS_PROMPT.format(
                    profiles="\n\n".join(profile_summaries)
                )
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=600,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                )
                dna = response.content[0].text
                save_soundcloud_production_dna(user_id, dna)
                log.info(f"SoundCloud Production DNA synthesized for user {user_id}")
            except Exception as e:
                log.error(f"SoundCloud Production DNA synthesis failed: {e}")
                update_soundcloud_research_status(user_id, "complete")
        else:
            update_soundcloud_research_status(user_id, "complete")

    except Exception as e:
        log.error(f"SoundCloud artist research failed for user {user_id}: {e}")
        update_soundcloud_research_status(user_id, "complete")


def start_soundcloud_background_research(user_id):
    """Launch SoundCloud artist research in a background thread."""
    thread = threading.Thread(
        target=research_soundcloud_artists,
        args=(user_id,),
        daemon=True,
        name=f"sc-artist-research-{user_id}",
    )
    thread.start()
    log.info(f"Background SoundCloud artist research started for user {user_id}")
    return thread
