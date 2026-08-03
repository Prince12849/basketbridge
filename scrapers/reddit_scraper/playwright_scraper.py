"""Fallback scraping method #3 (last resort): Playwright headless browser.

Only used when both the .json endpoints and the old.reddit.com HTML parser
fail (e.g. Reddit serves a different markup, blocks the request, or is
gated behind JS). Playwright is imported lazily so it is an optional
dependency - the rest of the scraper works fine without it installed.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from .config import ScraperConfig
from .models import CommentRecord, PostRecord

logger = logging.getLogger("blinkit_scraper")

OLD_BASE = "https://old.reddit.com"
_ID_FROM_PERMALINK = re.compile(r"/comments/([a-z0-9]+)/")


class PlaywrightUnavailableError(RuntimeError):
    """Raised when Playwright is not installed / browsers not provisioned."""


class RedditPlaywrightScraper:
    """Thin wrapper around a Playwright browser context. Reuses one browser
    instance across calls for efficiency; call close() when done."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self._playwright = None
        self._browser = None

    def _ensure_browser(self):
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightUnavailableError(
                "playwright is not installed. Run: pip install playwright "
                "&& playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            raise PlaywrightUnavailableError(
                f"Failed to launch Chromium via Playwright: {exc}. "
                "Try: playwright install chromium"
            ) from exc

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None

    def _get_html(self, url: str) -> str:
        self._ensure_browser()
        page = self._browser.new_page(user_agent=self.config.user_agent)
        try:
            page.goto(url, timeout=self.config.timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)  # let lazy content settle
            return page.content()
        finally:
            page.close()

    # ------------------------------------------------------------------
    def search_subreddit(self, subreddit: str, query: str, limit: int = 100) -> List[PostRecord]:
        url = f"{OLD_BASE}/r/{subreddit}/search?q={query}&restrict_sr=on&sort={self.config.sort}"
        html = self._get_html(url)
        return self._parse_search_html(html, limit)

    def search_global(self, query: str, limit: int = 100) -> List[PostRecord]:
        url = f"{OLD_BASE}/search?q={query}&sort={self.config.sort}"
        html = self._get_html(url)
        return self._parse_search_html(html, limit)

    @staticmethod
    def _parse_search_html(html: str, limit: int) -> List[PostRecord]:
        from bs4 import BeautifulSoup

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
            subreddit = subreddit_tag.text.replace("r/", "").strip() if subreddit_tag else ""
            author_tag = res.select_one("a.author")
            author = author_tag.text.strip() if author_tag else "[unknown]"

            posts.append(
                PostRecord(
                    post_id=post_id,
                    subreddit=subreddit,
                    title=title_tag.text.strip(),
                    selftext="",
                    author=author,
                    score=0,
                    upvote_ratio=None,
                    num_comments=0,
                    created_utc=None,
                    permalink=permalink if permalink.startswith("/") else f"/comments/{post_id}/",
                    url=permalink,
                    source_method="playwright",
                )
            )
        return posts

    # ------------------------------------------------------------------
    def fetch_comments(self, subreddit: str, post_id: str,
                        max_comments: int) -> List[CommentRecord]:
        from bs4 import BeautifulSoup

        url = f"{OLD_BASE}/r/{subreddit}/comments/{post_id}/?limit={max_comments}"
        html = self._get_html(url)
        soup = BeautifulSoup(html, "html.parser")

        comments: List[CommentRecord] = []
        for c in soup.select("div.comment")[:max_comments]:
            comment_id = c.get("data-fullname", "").split("_")[-1] or c.get("id", "")
            author_tag = c.select_one("a.author")
            author = author_tag.text.strip() if author_tag else "[deleted]"
            body_tag = c.select_one("div.md")
            body = body_tag.get_text("\n").strip() if body_tag else ""
            if not comment_id or not body:
                continue
            comments.append(
                CommentRecord(
                    comment_id=comment_id,
                    parent_post_id=post_id,
                    subreddit=subreddit,
                    author=author,
                    body=body,
                    score=0,
                    created_utc=None,
                    permalink=f"/r/{subreddit}/comments/{post_id}/",
                    source_method="playwright",
                )
            )
        return comments
