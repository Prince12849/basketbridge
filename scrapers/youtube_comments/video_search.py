"""
video_search.py
================
Discovers candidate videos for a search query using yt-dlp's `ytsearchN:`
pseudo-extractor. This talks to the same search results YouTube.com itself
returns (relevance-sorted by default), with no API key and no quota.

yt-dlp is one of the most actively maintained scraping tools in existence —
it ships frequent releases specifically to keep up with YouTube's changes.
Keep it current: `pip install -U yt-dlp` periodically, especially if search
suddenly starts returning nothing.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)

# A real YouTube video ID is exactly 11 URL-safe base64-ish characters.
# Flat search results have occasionally been reported to leak a channel or
# playlist entry instead of a video (see yt-dlp issue #13847) — this filter
# guards against silently treating one of those as a video.
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def search_videos(query: str, limit: int) -> list[dict]:
    """
    Return up to `limit` candidate videos for `query` as dicts with keys:
    video_id, video_title, channel_name, video_url. Returns an empty list
    (logged, not raised) on failure — the caller treats that as "this query
    contributed nothing" and moves on, per the "continue on failure"
    requirement.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # metadata only, no per-video page hits
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
    }
    search_target = f"ytsearch{limit}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
    except Exception as exc:
        logger.error("yt-dlp search failed for query %r: %s", query, exc)
        return []

    entries = (info or {}).get("entries") or []
    results = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id or not _VIDEO_ID_PATTERN.match(video_id):
            continue
        results.append(
            {
                "video_id": video_id,
                "video_title": entry.get("title") or "",
                "channel_name": entry.get("channel") or entry.get("uploader") or "",
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return results
