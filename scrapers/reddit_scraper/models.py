"""Dataclasses representing scraped Reddit posts and comments, and their
mapping onto the unified output schema used for the CSV file."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# Unified CSV column order, as required by the spec.
OUTPUT_COLUMNS = [
    "source",
    "type",
    "subreddit",
    "post_id",
    "parent_post_id",
    "comment_id",
    "title",
    "text",
    "author",
    "score",
    "num_comments",
    "created_at",
    "url",
]


def _iso(ts: Optional[float]) -> str:
    """Convert a unix timestamp (created_utc) to an ISO-8601 string."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


@dataclass
class PostRecord:
    post_id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    score: int
    upvote_ratio: Optional[float]
    num_comments: int
    created_utc: Optional[float]
    permalink: str
    url: str
    source_method: str = "json"  # json | html | playwright

    def to_row(self) -> dict:
        return {
            "source": "reddit",
            "type": "post",
            "subreddit": self.subreddit,
            "post_id": self.post_id,
            "parent_post_id": "",
            "comment_id": "",
            "title": self.title or "",
            "text": self.selftext or "",
            "author": self.author or "[unknown]",
            "score": self.score if self.score is not None else "",
            "num_comments": self.num_comments if self.num_comments is not None else "",
            "created_at": _iso(self.created_utc),
            "url": self.url or f"https://www.reddit.com{self.permalink}",
        }


@dataclass
class CommentRecord:
    comment_id: str
    parent_post_id: str
    subreddit: str
    author: str
    body: str
    score: int
    created_utc: Optional[float]
    permalink: str = ""
    source_method: str = "json"

    def to_row(self) -> dict:
        return {
            "source": "reddit",
            "type": "comment",
            "subreddit": self.subreddit,
            "post_id": "",
            "parent_post_id": self.parent_post_id,
            "comment_id": self.comment_id,
            "title": "",
            "text": self.body or "",
            "author": self.author or "[unknown]",
            "score": self.score if self.score is not None else "",
            "num_comments": "",
            "created_at": _iso(self.created_utc),
            "url": (
                f"https://www.reddit.com{self.permalink}"
                if self.permalink
                else ""
            ),
        }
