"""
config.py
=========
Central configuration for the Blinkit YouTube comments scraper. Edit this
file to point the scraper at a different product/brand, or override most of
these at the CLI (see youtube_scraper.py --help).
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Search configuration
# --------------------------------------------------------------------------- #

PRODUCT_NAME = "Blinkit"

SEARCH_QUERIES = [
    "Blinkit review",
    "Blinkit customer review",
    "Blinkit delivery",
    "Blinkit app review",
    "Blinkit vs Zepto",
    "Blinkit vs Instamart",
    "Blinkit grocery",
    "Blinkit experience",
    "Blinkit complaints",
    "Blinkit customer support",
]

# How many candidate videos to pull per individual search query before
# merging/deduping across all queries.
VIDEOS_PER_QUERY = 8

# Final cap on the *combined, deduped* video set across all queries.
# The merge is round-robin across queries so every query gets a fair shot
# at contributing videos rather than the first query dominating the list.
MAX_TOTAL_VIDEOS = 30

# Extra, manually curated video IDs to always include regardless of search
# (useful as a resilience fallback if YouTube search ever breaks — see
# README section "If search stops working"). Leave empty by default.
EXTRA_VIDEO_IDS: list = []

# --------------------------------------------------------------------------- #
# Comment collection configuration
# --------------------------------------------------------------------------- #

# None = no limit (collect every comment YouTube will paginate through).
# A number keeps runtime predictable — 500/video x 30 videos = 15k rows max.
MAX_COMMENTS_PER_VIDEO = 500

# 0 = most-liked first, 1 = most-recent first (matches youtube-comment-
# downloader's own convention). Recent tends to surface more of the raw,
# unfiltered day-to-day feedback that a product-discovery engine wants.
SORT_BY_POPULAR = 0
SORT_BY_RECENT = 1
DEFAULT_SORT = SORT_BY_RECENT

# --------------------------------------------------------------------------- #
# Networking / retry / rate limiting
# --------------------------------------------------------------------------- #

REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0  # seconds; exponential: base**attempt + jitter

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

# scrapers/youtube_comments/config.py -> project root is two levels up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_CSV = OUTPUT_DIR / "blinkit_youtube_comments.csv"
STATE_FILE = OUTPUT_DIR / ".blinkit_youtube_scraper_state.json"
LOG_FILE = OUTPUT_DIR / "blinkit_youtube_scraper.log"

# --------------------------------------------------------------------------- #
# Output schema
# --------------------------------------------------------------------------- #

OUTPUT_COLUMNS = [
    "source",
    "search_query",
    "video_title",
    "video_id",
    "video_url",
    "channel_name",
    "comment_id",
    "comment",
    "author",
    "likes",
    "reply_count",
    "published_at",
]
