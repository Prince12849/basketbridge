"""Fallback scraping method #2: old.reddit.com HTML pages, parsed with
BeautifulSoup. Used automatically when the .json endpoints fail (e.g. if
Reddit rate-limits or changes the JSON API)."""

from __future__ import annotations

import logging
import re
from typing import List

import requests
from bs4 import BeautifulSoup

from .config import ScraperConfig
from .http_utils import RateLimiter, retry
from .models import CommentRecord, PostRecord

logger = logging.getLogger("blinkit_scraper")

OLD_BASE = "https://old.reddit.com"

_ID_FROM_PERMALINK = re.compile(r"/comments/([a-z0-9]+)/")


class RedditHTMLScraper:
    def __init__(self, session: requests.Session, config: ScraperConfig,
                 rate_limiter: RateLimiter) -> None:
        self.session = session
        self.config = config
        self.rate_limiter = rate_limiter

    @retry(max_retries=4, backoff_base=2.0)
    def _get_html(self, url: str, params: dict) -> str:
        self.rate_limiter.wait()
        resp = self.session.get(url, params=params, timeout=self.config.timeout)
        if resp.status_code == 429:
            raise requests.HTTPError(f"429 Too Many Requests for {url}")
        resp.raise_for_status()
        return resp.text

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search_subreddit(self, subreddit: str, query: str, limit: int = 100) -> List[PostRecord]:
        url = f"{OLD_BASE}/r/{subreddit}/search"
        params = {"q": query, "restrict_sr": "on", "sort": self.config.sort}
        try:
            html = self._get_html(url, params)
        except requests.RequestException as exc:
            logger.warning("HTML search failed for r/%s q=%r: %s", subreddit, query, exc)
            raise
        return self._parse_search_results(html, limit)

    def search_global(self, query: str, limit: int = 100) -> List[PostRecord]:
        url = f"{OLD_BASE}/search"
        params = {"q": query, "sort": self.config.sort}
        try:
            html = self._get_html(url, params)
        except requests.RequestException as exc:
            logger.warning("HTML global search failed for q=%r: %s", query, exc)
            raise
        return self._parse_search_results(html, limit)

    @staticmethod
    def _parse_search_results(html: str, limit: int) -> List[PostRecord]:
        soup = BeautifulSoup(html, "html.parser")
        posts: List[PostRecord] = []

        results = soup.select("div.search-result-link") or soup.select("div.search-result")
        for res in results[:limit]:
            title_tag = res.select_one("a.search-title")
            if not title_tag:
                continue
            permalink = title_tag.get("href", "")
            match = _ID_FROM_PERMALINK.search(permalink)
            post_id = match.group(1) if match else ""
            if not post_id:
                continue

            subreddit_tag = res.select_one("a.search-subreddit-link")
            subreddit = ""
            if subreddit_tag:
                subreddit = subreddit_tag.text.replace("r/", "").strip()

            author_tag = res.select_one("a.author")
            author = author_tag.text.strip() if author_tag else "[unknown]"

            score_tag = res.select_one("span.search-score")
            score = 0
            if score_tag:
                score_match = re.search(r"-?\d+", score_tag.text.replace(",", ""))
                score = int(score_match.group()) if score_match else 0

            comments_tag = res.select_one("a.search-comments")
            num_comments = 0
            if comments_tag:
                c_match = re.search(r"\d+", comments_tag.text.replace(",", ""))
                num_comments = int(c_match.group()) if c_match else 0

            posts.append(
                PostRecord(
                    post_id=post_id,
                    subreddit=subreddit,
                    title=title_tag.text.strip(),
                    selftext="",  # not shown on search results page
                    author=author,
                    score=score,
                    upvote_ratio=None,
                    num_comments=num_comments,
                    created_utc=None,
                    permalink=permalink if permalink.startswith("/") else f"/comments/{post_id}/",
                    url=title_tag.get("href", ""),
                    source_method="html",
                )
            )
        return posts

    # ------------------------------------------------------------------
    # comments
    # ------------------------------------------------------------------
    def fetch_comments(self, subreddit: str, post_id: str,
                        max_comments: int) -> List[CommentRecord]:
        url = f"{OLD_BASE}/r/{subreddit}/comments/{post_id}/"
        try:
            html = self._get_html(url, params={"limit": max_comments})
        except requests.RequestException as exc:
            logger.warning("HTML comment fetch failed for post %s: %s", post_id, exc)
            raise

        soup = BeautifulSoup(html, "html.parser")
        comments: List[CommentRecord] = []
        for c in soup.select("div.comment")[:max_comments]:
            comment_id = c.get("data-fullname", "").split("_")[-1] or c.get("id", "")
            author_tag = c.select_one("a.author")
            author = author_tag.text.strip() if author_tag else "[deleted]"
            body_tag = c.select_one("div.md")
            body = body_tag.get_text("\n").strip() if body_tag else ""
            score_tag = c.select_one("span.score.unvoted")
            score = 0
            if score_tag and score_tag.get("title"):
                try:
                    score = int(score_tag["title"])
                except ValueError:
                    score = 0

            if not comment_id or not body:
                continue

            comments.append(
                CommentRecord(
                    comment_id=comment_id,
                    parent_post_id=post_id,
                    subreddit=subreddit,
                    author=author,
                    body=body,
                    score=score,
                    created_utc=None,
                    permalink=f"/r/{subreddit}/comments/{post_id}/",
                    source_method="html",
                )
            )
        return comments
