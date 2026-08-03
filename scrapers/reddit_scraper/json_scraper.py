"""Primary scraping method: Reddit's public, unauthenticated .json
endpoints (e.g. https://www.reddit.com/r/india/search.json?q=Blinkit).

These endpoints serve the same read-only data shown on the website and do
not require API credentials, OAuth, or PRAW.
"""

from __future__ import annotations

import logging
from typing import List

import requests

from .config import ScraperConfig
from .http_utils import RateLimiter, retry
from .models import CommentRecord, PostRecord

logger = logging.getLogger("blinkit_scraper")

BASE = "https://www.reddit.com"


class RedditJSONScraper:
    def __init__(self, session: requests.Session, config: ScraperConfig,
                 rate_limiter: RateLimiter) -> None:
        self.session = session
        self.config = config
        self.rate_limiter = rate_limiter

    # ------------------------------------------------------------------
    # low level fetch
    # ------------------------------------------------------------------
    @retry(max_retries=4, backoff_base=2.0)
    def _get_json(self, url: str, params: dict) -> dict:
        self.rate_limiter.wait()
        resp = self.session.get(url, params=params, timeout=self.config.timeout)
        if resp.status_code == 429:
            raise requests.HTTPError(f"429 Too Many Requests for {url}")
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise requests.RequestException(f"Invalid JSON from {url}: {exc}") from exc

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search_subreddit(self, subreddit: str, query: str, limit: int = 100) -> List[PostRecord]:
        """Search within a specific subreddit."""
        url = f"{BASE}/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "on",
            "sort": self.config.sort,
            "t": self.config.time_filter,
            "limit": min(limit, 100),
        }
        try:
            data = self._get_json(url, params)
        except requests.RequestException as exc:
            logger.warning("JSON search failed for r/%s q=%r: %s", subreddit, query, exc)
            raise
        return self._parse_listing(data)

    def search_global(self, query: str, limit: int = 100) -> List[PostRecord]:
        """Search across all of reddit (not restricted to a subreddit list),
        covering the requirement to catch 'any subreddit where Blinkit appears'."""
        url = f"{BASE}/search.json"
        params = {
            "q": query,
            "sort": self.config.sort,
            "t": self.config.time_filter,
            "limit": min(limit, 100),
        }
        try:
            data = self._get_json(url, params)
        except requests.RequestException as exc:
            logger.warning("JSON global search failed for q=%r: %s", query, exc)
            raise
        return self._parse_listing(data)

    @staticmethod
    def _parse_listing(data: dict) -> List[PostRecord]:
        posts: List[PostRecord] = []
        children = data.get("data", {}).get("children", [])
        for child in children:
            d = child.get("data", {})
            if not d.get("id"):
                continue
            posts.append(
                PostRecord(
                    post_id=d.get("id", ""),
                    subreddit=d.get("subreddit", ""),
                    title=d.get("title", ""),
                    selftext=d.get("selftext", ""),
                    author=d.get("author", "[unknown]"),
                    score=d.get("score", 0),
                    upvote_ratio=d.get("upvote_ratio"),
                    num_comments=d.get("num_comments", 0),
                    created_utc=d.get("created_utc"),
                    permalink=d.get("permalink", ""),
                    url=d.get("url", ""),
                    source_method="json",
                )
            )
        return posts

    # ------------------------------------------------------------------
    # comments
    # ------------------------------------------------------------------
    def fetch_comments(self, subreddit: str, post_id: str,
                        max_comments: int) -> List[CommentRecord]:
        url = f"{BASE}/r/{subreddit}/comments/{post_id}.json"
        params = {"limit": max_comments, "depth": 5, "sort": "top"}
        try:
            data = self._get_json(url, params)
        except requests.RequestException as exc:
            logger.warning("JSON comment fetch failed for post %s: %s", post_id, exc)
            raise

        if not isinstance(data, list) or len(data) < 2:
            return []

        comment_listing = data[1].get("data", {}).get("children", [])
        comments: List[CommentRecord] = []
        self._flatten_comments(comment_listing, post_id, subreddit, comments, max_comments)
        return comments[:max_comments]

    def _flatten_comments(self, children: list, post_id: str, subreddit: str,
                           out: List[CommentRecord], max_comments: int) -> None:
        for child in children:
            if len(out) >= max_comments:
                return
            if child.get("kind") != "t1":
                continue  # skip "more" stubs etc.
            d = child.get("data", {})
            if not d.get("id"):
                continue
            out.append(
                CommentRecord(
                    comment_id=d.get("id", ""),
                    parent_post_id=post_id,
                    subreddit=subreddit,
                    author=d.get("author", "[unknown]"),
                    body=d.get("body", ""),
                    score=d.get("score", 0),
                    created_utc=d.get("created_utc"),
                    permalink=d.get("permalink", ""),
                    source_method="json",
                )
            )
            replies = d.get("replies")
            if isinstance(replies, dict):
                reply_children = replies.get("data", {}).get("children", [])
                if reply_children:
                    self._flatten_comments(reply_children, post_id, subreddit, out, max_comments)
