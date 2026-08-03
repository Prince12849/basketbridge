"""Orchestrates the full scrape: iterates queries x subreddits, tries the
JSON method first, falls back to HTML, then to Playwright if all else
fails. Continues on individual failures and writes results incrementally."""

from __future__ import annotations

import logging
from typing import List, Optional

from tqdm import tqdm

from .config import ScraperConfig
from .dedupe import SeenTracker
from .html_scraper import RedditHTMLScraper
from .http_utils import RateLimiter, build_session
from .json_scraper import RedditJSONScraper
from .models import PostRecord
from .playwright_scraper import PlaywrightUnavailableError, RedditPlaywrightScraper
from .writer import CSVWriter

logger = logging.getLogger("blinkit_scraper")


class RedditScraper:
    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.session = build_session(config.user_agent)
        self.rate_limiter = RateLimiter(config.request_delay, config.jitter)

        self.json_scraper = RedditJSONScraper(self.session, config, self.rate_limiter)
        self.html_scraper = RedditHTMLScraper(self.session, config, self.rate_limiter)
        self._pw_scraper: Optional[RedditPlaywrightScraper] = None

        self.seen = SeenTracker()
        self.stats = {
            "posts_json": 0, "posts_html": 0, "posts_playwright": 0, "posts_failed": 0,
            "comments_json": 0, "comments_html": 0, "comments_playwright": 0, "comments_failed": 0,
        }

    # ------------------------------------------------------------------
    def _get_playwright(self) -> Optional[RedditPlaywrightScraper]:
        if not self.config.enable_playwright_fallback:
            return None
        if self._pw_scraper is None:
            self._pw_scraper = RedditPlaywrightScraper(self.config)
        return self._pw_scraper

    def close(self) -> None:
        if self._pw_scraper is not None:
            self._pw_scraper.close()
        self.session.close()

    # ------------------------------------------------------------------
    # search with automatic fallback chain: JSON -> HTML -> Playwright
    # ------------------------------------------------------------------
    def _search_with_fallback(self, subreddit: Optional[str], query: str,
                               limit: int) -> List[PostRecord]:
        # Method 1: JSON
        try:
            if subreddit:
                return self.json_scraper.search_subreddit(subreddit, query, limit)
            return self.json_scraper.search_global(query, limit)
        except Exception as exc:  # noqa: BLE001
            logger.info("JSON search failed (%s), falling back to HTML.", exc)

        # Method 2: old.reddit.com HTML
        try:
            if subreddit:
                return self.html_scraper.search_subreddit(subreddit, query, limit)
            return self.html_scraper.search_global(query, limit)
        except Exception as exc:  # noqa: BLE001
            logger.info("HTML search failed (%s), falling back to Playwright.", exc)

        # Method 3: Playwright (last resort)
        pw = self._get_playwright()
        if pw is None:
            logger.error("All search methods failed for query=%r subreddit=%r "
                         "and Playwright fallback is disabled.", query, subreddit)
            return []
        try:
            if subreddit:
                return pw.search_subreddit(subreddit, query, limit)
            return pw.search_global(query, limit)
        except PlaywrightUnavailableError as exc:
            logger.error("Playwright fallback unavailable: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Playwright search also failed for query=%r subreddit=%r: %s",
                        query, subreddit, exc)
            return []

    def _fetch_comments_with_fallback(self, subreddit: str, post_id: str,
                                       max_comments: int) -> list:
        try:
            comments = self.json_scraper.fetch_comments(subreddit, post_id, max_comments)
            self.stats["comments_json"] += len(comments)
            return comments
        except Exception as exc:  # noqa: BLE001
            logger.info("JSON comment fetch failed for %s (%s), trying HTML.", post_id, exc)

        try:
            comments = self.html_scraper.fetch_comments(subreddit, post_id, max_comments)
            self.stats["comments_html"] += len(comments)
            return comments
        except Exception as exc:  # noqa: BLE001
            logger.info("HTML comment fetch failed for %s (%s), trying Playwright.", post_id, exc)

        pw = self._get_playwright()
        if pw is None:
            self.stats["comments_failed"] += 1
            return []
        try:
            comments = pw.fetch_comments(subreddit, post_id, max_comments)
            self.stats["comments_playwright"] += len(comments)
            return comments
        except Exception as exc:  # noqa: BLE001
            logger.warning("All comment-fetch methods failed for post %s: %s", post_id, exc)
            self.stats["comments_failed"] += 1
            return []

    # ------------------------------------------------------------------
    def run(self) -> dict:
        cfg = self.config
        collected_posts: List[PostRecord] = []

        search_targets: List[Optional[str]] = list(cfg.subreddits)
        if cfg.include_global_search:
            search_targets.append(None)  # None => global search

        logger.info("Starting search phase: %d queries x %d targets",
                   len(cfg.queries), len(search_targets))

        with CSVWriter(cfg.output_path) as writer:
            search_pbar = tqdm(total=len(cfg.queries) * len(search_targets),
                              desc="Searching", unit="query")
            for query in cfg.queries:
                for target in search_targets:
                    label = target or "ALL"
                    search_pbar.set_postfix_str(f"r/{label} :: {query[:25]}")
                    if self.seen.post_count >= cfg.max_posts:
                        search_pbar.update(1)
                        continue
                    try:
                        posts = self._search_with_fallback(target, query, limit=100)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Unexpected error searching r/%s for %r: %s",
                                    label, query, exc)
                        posts = []

                    for post in posts:
                        if self.seen.post_count >= cfg.max_posts:
                            break
                        if not self.seen.is_new_post(post.post_id):
                            continue
                        writer.write_row(post.to_row())
                        collected_posts.append(post)
                        self.stats[f"posts_{post.source_method}"] += 1

                    search_pbar.update(1)
            search_pbar.close()

            logger.info("Search phase complete. %d unique posts collected.",
                       len(collected_posts))
            logger.info("Starting comment collection phase (max %d/post).",
                       cfg.max_comments_per_post)

            comment_pbar = tqdm(collected_posts, desc="Fetching comments", unit="post")
            for post in comment_pbar:
                comment_pbar.set_postfix_str(f"post={post.post_id}")
                try:
                    comments = self._fetch_comments_with_fallback(
                        post.subreddit or "india", post.post_id, cfg.max_comments_per_post
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Unexpected error fetching comments for post %s: %s",
                                post.post_id, exc)
                    comments = []
                    self.stats["comments_failed"] += 1

                for comment in comments:
                    if not self.seen.is_new_comment(comment.comment_id):
                        continue
                    writer.write_row(comment.to_row())
            comment_pbar.close()

            total_rows = writer.rows_written

        logger.info("Scrape complete. Rows written: %d | Posts: %d | Comments: %d",
                   total_rows, self.seen.post_count, self.seen.comment_count)
        logger.info("Method breakdown: %s", self.stats)
        self.close()

        return {
            "total_rows": total_rows,
            "unique_posts": self.seen.post_count,
            "unique_comments": self.seen.comment_count,
            "stats": self.stats,
            "output_path": str(cfg.output_path),
        }
