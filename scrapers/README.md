# Blinkit Reddit Scraper

Scrapes publicly available Reddit discussions about Blinkit (and quick-commerce
competitors) **without using the Reddit API / PRAW**. Built for the AI Product
Discovery Engine's data-ingestion pipeline.

## How it works

Three scraping methods, tried in order, with automatic fallback:

1. **Reddit JSON endpoints** (`https://www.reddit.com/r/<sub>/search.json`,
   `https://www.reddit.com/r/<sub>/comments/<id>.json`) — fast, structured,
   no auth required. Primary method.
2. **old.reddit.com HTML** — parsed with BeautifulSoup. Used automatically if
   the JSON endpoint fails or is rate-limited.
3. **Playwright headless browser** — last resort, used only if both of the
   above fail (e.g. Reddit changes markup or blocks the request). Optional
   dependency; the scraper works fine without it installed, it just skips
   this fallback.

Every request goes through a `RateLimiter` (politeness delay + jitter) and a
`retry` decorator (exponential backoff on network errors / HTTP 429/5xx).
Failures on individual posts/queries are logged and skipped — the run never
aborts because of one bad request.

## Install

```bash
pip install -r requirements.txt
# Optional, only needed for the Playwright fallback:
playwright install chromium
```

## Run

```bash
python main.py
```

Output is written incrementally to `data/raw/blinkit_reddit.csv` (configurable).

### Useful flags

```bash
python main.py --max-posts 500 --max-comments 80
python main.py --output data/raw/blinkit_reddit.csv
python main.py --subreddits india,bangalore,startups
python main.py --queries "Blinkit refund,Blinkit vs Zepto"
python main.py --no-global-search   # restrict to the subreddit list only
python main.py --no-playwright      # JSON + HTML only, no browser fallback
python main.py --delay 3.0          # be more conservative with rate limiting
```

## Output schema (`data/raw/blinkit_reddit.csv`)

| column          | description                                   |
|-----------------|------------------------------------------------|
| source          | always `reddit`                                |
| type            | `post` or `comment`                            |
| subreddit       | subreddit name                                 |
| post_id         | Reddit post id (posts only)                    |
| parent_post_id  | post id the comment belongs to (comments only) |
| comment_id      | Reddit comment id (comments only)               |
| title           | post title (posts only)                        |
| text            | post body / comment text                       |
| author          | Reddit username, or `[unknown]`/`[deleted]`    |
| score           | upvote score                                   |
| num_comments    | comment count (posts only)                     |
| created_at      | ISO-8601 UTC timestamp                         |
| url             | permalink                                      |

Posts and comments are deduplicated in-memory across all queries/subreddits
during a run (the same post can legitimately surface from multiple search
queries).

## Project layout

```
reddit_scraper/
  config.py             # queries, subreddits, limits, rate-limit settings
  logger.py             # console + file logging setup
  http_utils.py         # RateLimiter, retry decorator, requests.Session builder
  models.py             # PostRecord / CommentRecord -> unified CSV row
  dedupe.py             # SeenTracker (in-memory id sets)
  writer.py             # incremental CSV writer
  json_scraper.py       # method 1: reddit .json endpoints
  html_scraper.py       # method 2: old.reddit.com HTML
  playwright_scraper.py # method 3: headless browser (optional dep)
  scraper.py            # orchestrator: fallback chain, tqdm, stats
main.py                 # CLI entrypoint
requirements.txt
```

## Notes / good-citizen defaults

- Default delay is 2s (+jitter) between requests — tune with `--delay`.
- A descriptive `User-Agent` is set (Reddit is more likely to rate-limit
  generic/missing user agents).
- This scrapes only publicly visible pages that don't require login. It does
  not bypass authentication, CAPTCHAs, or paywalls.
- Respect Reddit's [robots.txt](https://www.reddit.com/robots.txt) and terms
  of use for your use case/jurisdiction, and keep request volume reasonable.
