"""Configuration for the Blinkit Reddit scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Default target subreddits. "Any subreddit where Blinkit appears" is covered
# by the global search queries (include_global_search=True), which is not
# restricted to this list.
# ---------------------------------------------------------------------------
DEFAULT_SUBREDDITS: List[str] = [
    "india",
    "bangalore",
    "delhi",
    "mumbai",
    "hyderabad",
    "gurgaon",
    "startups",
    "developersIndia",
    "IndiaTech",
    "indianstartups",
    "IndianStreetBets",
    "chennai",
    "pune",
]

DEFAULT_QUERIES: List[str] = [
    "Blinkit",
    "Blinkit delivery",
    "Blinkit refund",
    "Blinkit customer service",
    "Blinkit app",
    "Blinkit grocery",
    "Blinkit dark store",
    "Blinkit order",
    "Blinkit support",
    "Blinkit issue",
    "Blinkit bug",
    "Blinkit experience",
    "Blinkit vs Zepto",
    "Blinkit vs Instamart",
    "Quick commerce India",
    "Grocery delivery India",
]


@dataclass
class ScraperConfig:
    """Holds all tunable parameters for a scrape run."""

    subreddits: List[str] = field(default_factory=lambda: DEFAULT_SUBREDDITS.copy())
    queries: List[str] = field(default_factory=lambda: DEFAULT_QUERIES.copy())

    # Volume controls
    max_posts: int = 300
    max_comments_per_post: int = 50

    # Networking / politeness
    request_delay: float = 2.0          # base seconds between requests
    jitter: float = 0.75                # random extra seconds added to delay
    max_retries: int = 4
    backoff_base: float = 2.0           # exponential backoff base (seconds)
    timeout: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        "ProductDiscoveryEngine/1.0 (contact: research@example.com)"
    )

    # Search behaviour
    include_global_search: bool = True  # also search all of reddit, not just the subreddit list
    sort: str = "new"
    time_filter: str = "all"

    # Output
    output_path: Path = Path("data/raw/blinkit_reddit.csv")

    # Logging
    log_level: str = "INFO"
    log_file: Path = Path("logs/blinkit_reddit_scraper.log")

    # Fallback control
    enable_playwright_fallback: bool = True
