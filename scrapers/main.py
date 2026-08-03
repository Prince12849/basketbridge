#!/usr/bin/env python3
"""CLI entrypoint for the Blinkit Reddit scraper.

Usage examples
--------------
    python main.py
    python main.py --max-posts 500 --max-comments 80
    python main.py --output data/raw/blinkit_reddit.csv --no-playwright
    python main.py --subreddits india,bangalore,startups
    python main.py --queries "Blinkit refund,Blinkit vs Zepto"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reddit_scraper.config import DEFAULT_QUERIES, DEFAULT_SUBREDDITS, ScraperConfig
from reddit_scraper.logger import setup_logger
from reddit_scraper.scraper import RedditScraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape publicly available Reddit discussions about Blinkit "
                    "(and quick-commerce competitors) without using the Reddit API."
    )
    parser.add_argument("--max-posts", type=int, default=300,
                       help="Maximum number of unique posts to collect (default: 300)")
    parser.add_argument("--max-comments", type=int, default=50,
                       help="Maximum comments to collect per post (default: 50)")
    parser.add_argument("--output", type=str, default="data/raw/blinkit_reddit.csv",
                       help="Output CSV path (default: data/raw/blinkit_reddit.csv)")
    parser.add_argument("--delay", type=float, default=2.0,
                       help="Base delay in seconds between requests (default: 2.0)")
    parser.add_argument("--subreddits", type=str, default=None,
                       help="Comma-separated list of subreddits (overrides defaults)")
    parser.add_argument("--queries", type=str, default=None,
                       help="Comma-separated list of search queries (overrides defaults)")
    parser.add_argument("--no-global-search", action="store_true",
                       help="Disable searching all of reddit.com (subreddit list only)")
    parser.add_argument("--no-playwright", action="store_true",
                       help="Disable the Playwright fallback (JSON + HTML only)")
    parser.add_argument("--log-level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = ScraperConfig(
        subreddits=(args.subreddits.split(",") if args.subreddits else DEFAULT_SUBREDDITS.copy()),
        queries=(args.queries.split(",") if args.queries else DEFAULT_QUERIES.copy()),
        max_posts=args.max_posts,
        max_comments_per_post=args.max_comments,
        output_path=Path(args.output),
        request_delay=args.delay,
        include_global_search=not args.no_global_search,
        enable_playwright_fallback=not args.no_playwright,
        log_level=args.log_level,
    )

    logger = setup_logger(level=config.log_level, log_file=config.log_file)
    logger.info("=" * 70)
    logger.info("Blinkit Reddit Scraper starting")
    logger.info("Subreddits: %s", config.subreddits)
    logger.info("Queries: %s", config.queries)
    logger.info("max_posts=%d max_comments_per_post=%d output=%s",
               config.max_posts, config.max_comments_per_post, config.output_path)
    logger.info("=" * 70)

    scraper = RedditScraper(config)
    try:
        result = scraper.run()
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Partial results were saved to %s",
                       config.output_path)
        scraper.close()
        return

    logger.info("Done. Summary: %s", result)
    print(f"\nSaved {result['total_rows']} rows "
          f"({result['unique_posts']} posts, {result['unique_comments']} comments) "
          f"to {result['output_path']}")


if __name__ == "__main__":
    main()
