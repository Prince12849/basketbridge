"""
comment_fetcher.py
===================
Pulls comments for a single video using `youtube-comment-downloader`
(egbertbouman). This talks to YouTube's own internal endpoints — the same
ones youtube.com's web frontend uses to render the comment section — so no
API key or quota is involved. It's purpose-built for this (continuation-
token pagination handled internally), which is why it's preferred over
yt-dlp for the comment-extraction step even though yt-dlp *can* also do it.

Each raw comment dict has these documented fields:
    cid, text, time, time_parsed, author, channel, votes, replies, photo,
    heart, reply
"""

from __future__ import annotations

import logging
from typing import Optional

from youtube_comment_downloader import YoutubeCommentDownloader

import config
from utils import retry

logger = logging.getLogger(__name__)

# One downloader instance is reused across videos (it holds no per-video
# state, just an HTTP session).
_downloader = YoutubeCommentDownloader()


@retry(exceptions=(Exception,))
def fetch_comments_for_video(
    video_id: str, limit: Optional[int], sort_by: int = config.DEFAULT_SORT
) -> list[dict]:
    """
    Fetch up to `limit` comments (None = unlimited) for a video. Retried as
    a whole on transient failure (network blips, momentary blocks) — safe to
    retry from scratch because downstream dedup is keyed on comment id, so a
    retried fetch never produces duplicate rows even if the first attempt
    had partially succeeded before failing.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    comments = []
    generator = _downloader.get_comments_from_url(url, sort_by=sort_by)
    for comment in generator:
        comments.append(comment)
        if limit and len(comments) >= limit:
            break
    return comments
