"""
appstore_scraper.py
====================

Apple App Store review scraper — requests / beautifulsoup4 / pandas / json /
time only, no third-party app-store-scraping libraries.

--------------------------------------------------------------------------
WHAT'S ACTUALLY GOING ON (live-verified — read before running)
--------------------------------------------------------------------------
The classic reverse-engineering trick most tutorials describe is:
    1. Fetch the apps.apple.com product page as an Ember.js app.
    2. Pull a bearer token out of a <meta name="web-experience-app/config/
       environment"> tag embedded in the raw HTML.
    3. Call Apple's internal AMP API (https://amp-api.apps.apple.com/v1/
       catalog/{country}/apps/{app_id}/reviews) with that token, paginating
       via the `next` field the API returns.
This was verified against the (now archived) `app-store-scraper` project's
actual source and was correct as of when that project was maintained.

It no longer works. A live fetch of the plain Blinkit product page
(https://apps.apple.com/in/app/blinkit-groceries-more/id960335206) confirmed
the `web-experience-app/config/environment` meta tag is gone — Apple has
since changed its web frontend. The AMP-API/token path is kept below only as
a best-effort secondary source: cheap to try, harmless if it fails, free
upside if Apple ever exposes an equivalent token again.

What IS confirmed live-working with a plain, unauthenticated `requests.get`:
Apple server-renders a genuine (if limited) set of reviews — title, star
rating, date, reviewer, body text, developer response — directly into the
HTML of:

    https://apps.apple.com/{country}/app/{slug}/id{app_id}?see-all=reviews&platform=iphone

This exists for crawlability/SEO (so Google can index real review text), and
needs no JavaScript execution and no auth. Confirmed by directly fetching
the live Blinkit page while building this script: it returned ~5 real,
readable reviews with developer responses. The known limitation is that
there is no working pagination for this view — it caps at a small teaser
set per app/country. That ceiling is Apple's choice for anonymous access,
not a bug here.

So the priority order this script actually uses is:
    1. PRIMARY   — server-rendered "Ratings & Reviews" page (no auth,
                   confirmed working, small yield).
    2. SECONDARY — Apple's internal AMP API via an extracted bearer token
                   (best-effort; likely non-functional right now, see above).
    3. TERTIARY  — legacy customer-reviews RSS feed (best-effort; heavily
                   throttled / often returns empty, but the only source that
                   still reports app_version when it does respond).

Apple's only *documented, contractually stable* review API is the App Store
Connect "Customer Reviews" endpoint, which only works for apps you own in
App Store Connect — not usable here since we don't own the Blinkit listing.

If a run comes back empty, this script prints a diagnostic report (which
markers are/aren't present in the raw HTML, what <meta>/<script> tags
actually exist) and exact Chrome DevTools steps to find whatever request
Apple's frontend uses today, so the extraction logic can be fixed precisely
instead of guessed at again.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

LANDING_HOST = "https://apps.apple.com"
AMP_API_HOSTS = [
    "https://amp-api.apps.apple.com",
    "https://amp-api-edge.apps.apple.com",
]
RSS_FALLBACK_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/"
    "page={page}/id={app_id}/sortby=mostrecent/json"
)

REQUEST_TIMEOUT = 15  # seconds
DEFAULT_DELAY = 1.2  # seconds between paginated requests (be a good citizen)
MAX_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

REQUIRED_COLUMNS = [
    "reviewer",
    "review_title",
    "review",
    "rating",
    "review_date",
    "app_version",
    "country",
    "source",
    "app_id",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("appstore_scraper")


# --------------------------------------------------------------------------- #
# Data container
# --------------------------------------------------------------------------- #


@dataclass
class ScrapeTarget:
    country: str
    app_slug: str
    app_id: str
    landing_url: str = field(init=False)

    def __post_init__(self):
        self.country = self.country.lower()
        self.landing_url = (
            f"{LANDING_HOST}/{self.country}/app/{self.app_slug}/id{self.app_id}"
        )


def parse_app_store_url(url: str) -> ScrapeTarget:
    """Parse a standard apps.apple.com product URL into its components."""
    match = re.search(
        r"apps\.apple\.com/(?P<country>[a-z]{2})/app/(?P<slug>[^/?]+)/id(?P<id>\d+)",
        url,
    )
    if not match:
        raise ValueError(
            f"Could not parse App Store URL: {url!r}. "
            "Expected format: https://apps.apple.com/<country>/app/<slug>/id<digits>"
        )
    return ScrapeTarget(
        country=match.group("country"),
        app_slug=match.group("slug"),
        app_id=match.group("id"),
    )


# --------------------------------------------------------------------------- #
# HTTP session with retries
# --------------------------------------------------------------------------- #


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_get(
    session: requests.Session, url: str, **kwargs
) -> Optional[requests.Response]:
    """GET with exception handling; returns None on hard failure."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    kwargs.setdefault("headers", {})
    kwargs["headers"].setdefault("User-Agent", random.choice(USER_AGENTS))
    try:
        return session.get(url, **kwargs)
    except requests.exceptions.RequestException as exc:
        logger.error("Request to %s failed: %s", url, exc)
        return None


# --------------------------------------------------------------------------- #
# Diagnostics — run automatically on failure so a dead end becomes actionable
# --------------------------------------------------------------------------- #


def diagnose_page(html: str, save_as: str = "appstore_debug_page.html") -> None:
    logger.info("---- DIAGNOSTIC REPORT (raw HTML as seen by `requests`, no JS) ----")
    logger.info("Raw HTML length: %d characters", len(html))

    markers = {
        "web-experience-app/config/environment": "Ember config meta tag (old AMP-token mechanism)",
        "amp-api": "Reference to Apple's AMP API host",
        "amp-api-edge": "Reference to the AMP API edge/mirror host",
        "MEDIA_API": "Old Ember media-api token key",
        "svelte": "Svelte framework marker",
        "__NEXT_DATA__": "Next.js hydration payload marker",
    }
    for marker, desc in markers.items():
        present = marker.lower() in html.lower()
        logger.info("  [%s] %s", "FOUND" if present else "  -  ", desc)

    try:
        soup = BeautifulSoup(html, "html.parser")
        meta_names = [m.get("name") for m in soup.find_all("meta") if m.get("name")]
        logger.info("<meta name=...> tags present (%d): %s", len(meta_names), meta_names)

        script_summaries = [
            {k: v for k, v in s.attrs.items() if k in ("id", "type", "src")}
            for s in soup.find_all("script")
            if any(k in s.attrs for k in ("id", "type", "src"))
        ]
        logger.info(
            "<script> tags with id/type/src (%d, first 15 shown): %s",
            len(script_summaries),
            script_summaries[:15],
        )
    except Exception as exc:  # diagnostics must never crash the run
        logger.debug("Diagnostic parsing failed: %s", exc)

    try:
        Path(save_as).write_text(html, encoding="utf-8")
        logger.info(
            "Full raw HTML saved to %s — open it in a text editor to see "
            "exactly what Apple currently ships to a non-JS client.",
            Path(save_as).resolve(),
        )
    except OSError as exc:
        logger.debug("Could not write debug HTML file: %s", exc)

    logger.info(
        "Ground-truth fix if this keeps failing: open the app page in "
        "Chrome, DevTools -> Network -> Fetch/XHR, scroll the reviews "
        "section, find the request that returns review JSON, and inspect "
        "its exact URL + headers."
    )
    logger.info("---- END DIAGNOSTIC REPORT ----")


# --------------------------------------------------------------------------- #
# PRIMARY: server-rendered "Ratings & Reviews" page (confirmed working,
# no auth needed)
# --------------------------------------------------------------------------- #

_DATE_PATTERNS = [
    r"^\d{1,2}[/\u200f]\d{1,2}[/\u200f]\d{2,4}$",           # 10/10/2023
    r"^\d{1,2}\s+[A-Za-z]{3,9}(\s+\d{2,4})?$",              # 21 Jul / 21 Jul 2024
    r"^(today|yesterday)$",
    r"^\d+\s+(day|days|hour|hours|minute|minutes|week|weeks|month|months)\s+ago$",
]
_RATING_ATTR_PATTERN = re.compile(r"(\d(?:\.\d)?)\s*(?:out of|/)\s*5", re.IGNORECASE)
_STAR_MARKER_PATTERN = re.compile(r"^[1-5]$")
# Marks the language-switcher links that appear right after the review list
# and before the country selector — used as a hard stop boundary so the last
# review's parser doesn't run on into footer/navigation content.
_BOUNDARY_TAGS = {"footer", "nav"}
_MAX_WALK_STEPS = 400  # safety valve against unbounded walks


def _looks_like_date(text: str) -> bool:
    text = text.strip()
    return any(re.match(p, text, re.IGNORECASE) for p in _DATE_PATTERNS)


def _find_rating_in_block(tags: list) -> Optional[float]:
    """
    Star ratings on this page are rendered visually (filled/empty icons),
    not as plain text — the "1 2 3 4 5" fragments in the markup are star
    *position* markers, not the score. The real value has to come from an
    element attribute (aria-label, title, data-*, etc). We scan every
    attribute of every tag in the block for a "N out of 5" / "N/5" pattern
    rather than betting on one exact attribute name, since that markup can
    change without notice and degrading to `None` is safer than guessing.
    """
    for t in tags:
        if not isinstance(t, Tag):
            continue
        for value in t.attrs.values():
            text = value if isinstance(value, str) else " ".join(value)
            match = _RATING_ATTR_PATTERN.search(text)
            if match:
                return float(match.group(1))
    return None


def _find_page_boundary_position(soup: BeautifulSoup) -> Optional[int]:
    """
    Locate where the review list ends and footer/language-switcher/country
    -selector content begins, ONCE per page. Using the boundary tag's own
    position isn't enough: a bare label that immediately precedes it in the
    markup (e.g. a country name like "India" sitting right before the
    language-switcher links) is a *preceding sibling*, not a descendant of
    the boundary tag, so it would still leak into whichever review block is
    being walked when the parser reaches it. To catch that, once a boundary
    tag is found we walk backward and absorb any short (<=40 char),
    period-free text/tags immediately before it — real review prose is
    reliably longer and reliably contains punctuation, so this doesn't risk
    eating genuine review content. Returns the flat document-order index of
    the resulting cutoff, or None if no boundary marker was found at all.
    """
    all_nodes = list(soup.descendants)
    for pos, node in enumerate(all_nodes):
        if not (isinstance(node, Tag) and (node.name in _BOUNDARY_TAGS or node.has_attr("hreflang"))):
            continue
        cutoff = pos
        back = pos - 1
        while back >= 0:
            prev = all_nodes[back]
            if isinstance(prev, Tag):
                if prev.name in ("h1", "h2", "h3"):
                    break
                back -= 1
                continue
            text = str(prev).strip()
            if not text:
                back -= 1
                continue
            if len(text) <= 40 and "." not in text:
                cutoff = back
                back -= 1
                continue
            break
        return cutoff
    return None


def _classify_review_block(
    anchor: Tag,
    node_position: dict,
    boundary_position: Optional[int],
) -> Optional[dict]:
    """
    Walk forward from a review-title heading (h3) to the next heading (or a
    hard boundary), collecting text + tags in document order, and classify
    the pieces using the field order Apple's SSR reviews markup has been
    observed to use:
        title -> [star markers] -> date -> author -> body
        -> ["Developer Response" -> [date] -> response body]
    """
    title = anchor.get_text(strip=True)
    if not title:
        return None

    collected_tags: list = []
    texts: list[str] = []
    steps = 0
    for el in anchor.next_elements:
        steps += 1
        if steps > _MAX_WALK_STEPS:
            break
        pos = node_position.get(id(el))
        if boundary_position is not None and pos is not None and pos >= boundary_position:
            # Past the review list entirely (footer / language switcher /
            # country selector) — stop regardless of tag type.
            break
        if isinstance(el, Tag):
            if el.name in ("h1", "h2", "h3") or el.name in _BOUNDARY_TAGS:
                break
            collected_tags.append(el)
            continue
        text = str(el).strip()
        if text and text != title:
            texts.append(text)

    # Drop the bare "1".."5" star-position markers — no rating info alone.
    texts = [t for t in texts if not _STAR_MARKER_PATTERN.match(t)]
    if not texts:
        return None

    rating = _find_rating_in_block(collected_tags)

    idx = 0
    review_date = None
    if idx < len(texts) and _looks_like_date(texts[idx]):
        review_date = texts[idx]
        idx += 1

    author = None
    if idx < len(texts) and len(texts[idx]) <= 60 and "developer response" not in texts[idx].lower():
        author = texts[idx]
        idx += 1

    body_parts: list[str] = []
    dev_response_date = None
    dev_response_body = None
    in_dev_response = False
    for text in texts[idx:]:
        if "developer response" in text.lower():
            in_dev_response = True
            continue
        if in_dev_response:
            if dev_response_date is None and _looks_like_date(text):
                dev_response_date = text
                continue
            dev_response_body = (dev_response_body + " " + text) if dev_response_body else text
        else:
            body_parts.append(text)

    body = " ".join(body_parts).strip() or None

    return {
        "reviewer": author,
        "review_title": title,
        "review": body,
        "rating": rating,
        "review_date": review_date,
        "app_version": None,  # not exposed on this view either
        "developer_response": dev_response_body,
        "developer_response_date": dev_response_date,
    }


def fetch_reviews_ssr_page(
    session: requests.Session,
    target: ScrapeTarget,
    locale: str = "en-us",
    dump_html_path: Optional[Path] = None,
) -> list[dict]:
    """
    Primary review source: Apple's server-rendered "Ratings & Reviews" view.
    Confirmed working with a plain unauthenticated GET (no bearer token).
    Known limitation: no working pagination parameter was found, so this
    returns a small teaser set (observed: ~5 reviews) per app/country rather
    than the full corpus — a ceiling Apple imposes on anonymous access.
    """
    params = {"see-all": "reviews", "platform": "iphone", "l": locale}
    headers = {"Accept-Language": f"{locale},en;q=0.8"}

    resp = safe_get(session, target.landing_url, params=params, headers=headers)
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp else "no response"
        logger.warning("SSR reviews page request failed (%s).", status)
        return []

    html = resp.text
    if dump_html_path:
        dump_html_path.parent.mkdir(parents=True, exist_ok=True)
        dump_html_path.write_text(html, encoding="utf-8")
        logger.info("Saved raw SSR HTML for inspection -> %s", dump_html_path)

    soup = BeautifulSoup(html, "html.parser")
    headings = soup.find_all("h3")
    if not headings:
        logger.warning(
            "No <h3> review-title headings found on the SSR reviews page — "
            "Apple may have changed this view's markup."
        )
        diagnose_page(html)
        return []

    all_nodes = list(soup.descendants)
    node_position = {id(n): i for i, n in enumerate(all_nodes)}
    boundary_position = _find_page_boundary_position(soup)

    reviews = []
    seen_keys = set()
    for h3 in headings:
        parsed = _classify_review_block(h3, node_position, boundary_position)
        if not parsed:
            continue
        key = (parsed["review_title"], parsed["reviewer"], (parsed["review"] or "")[:80])
        if key in seen_keys:
            # Apple renders each card twice (a duplicate used for its own
            # detail-overlay/accessibility markup) — keep the first copy.
            continue
        seen_keys.add(key)
        parsed["country"] = target.country.upper()
        parsed["source"] = "App Store (SSR reviews page)"
        parsed["app_id"] = target.app_id
        if parsed["rating"] is None:
            logger.debug(
                "Could not extract a numeric rating for review %r — left blank.",
                parsed["review_title"],
            )
        reviews.append(parsed)

    logger.info("SSR reviews page: %d review(s) extracted.", len(reviews))
    return reviews


# --------------------------------------------------------------------------- #
# SECONDARY (best-effort): Apple's internal AMP API via an extracted token
# --------------------------------------------------------------------------- #


def _find_jwt_in_text(text: str) -> Optional[str]:
    match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text)
    return match.group(0) if match else None


def _search_dict_for_jwt(obj) -> Optional[str]:
    """Recursively search a parsed JSON structure for a JWT-shaped string."""
    if isinstance(obj, str):
        return obj if re.match(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", obj) else None
    if isinstance(obj, dict):
        for value in obj.values():
            found = _search_dict_for_jwt(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _search_dict_for_jwt(item)
            if found:
                return found
    return None


def get_bearer_token(session: requests.Session, landing_url: str) -> Optional[str]:
    """
    Best-effort: fetch the plain product page and try to extract the
    Ember-era AMP API bearer token. Three layered strategies, most to least
    specific. Expected to fail on the current frontend (see module
    docstring) — kept because it's cheap and harmless to attempt, and gives
    a diagnostic report on failure instead of silently doing nothing.
    """
    resp = safe_get(session, landing_url)
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp else "no response"
        logger.info("Could not load product page for token extraction (%s).", status)
        return None

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    meta_tag = soup.find("meta", {"name": "web-experience-app/config/environment"})

    if meta_tag and meta_tag.get("content"):
        raw_content = meta_tag["content"]
        try:
            config = json.loads(urllib.parse.unquote(raw_content))
            token = _search_dict_for_jwt(config)
            if token:
                logger.info("AMP bearer token extracted via meta-tag JSON parse.")
                return token
        except (json.JSONDecodeError, ValueError) as exc:
            logger.debug("Meta-tag JSON parse failed (%s); trying regex fallback.", exc)

        match = re.search(r"token%22%3A%22(.+?)%22", raw_content)
        if match:
            logger.info("AMP bearer token extracted via percent-encoded regex.")
            return match.group(1)

    token = _find_jwt_in_text(html)
    if token:
        logger.info("AMP bearer token found via generic JWT scan.")
        return token

    logger.info(
        "No AMP bearer token found on the product page (expected — see "
        "module docstring, Apple appears to have retired this mechanism)."
    )
    return None


def normalize_amp_review(attrs: dict, country: str, app_id: str) -> dict:
    dev_response = attrs.get("developerResponse", {})
    return {
        "reviewer": attrs.get("userName"),
        "review_title": attrs.get("title"),
        "review": attrs.get("review"),
        "rating": attrs.get("rating"),
        "review_date": attrs.get("date"),
        "app_version": None,  # not exposed by this endpoint
        "country": country.upper(),
        "source": "App Store (AMP API)",
        "app_id": app_id,
        "is_edited": attrs.get("isEdited"),
        "developer_response": dev_response.get("body"),
    }


def fetch_reviews_amp_api(
    session: requests.Session,
    token: str,
    target: ScrapeTarget,
    max_reviews: Optional[int],
    delay: float,
) -> list[dict]:
    """Paginate Apple's internal AMP API using the `next` link it returns."""
    collected: list[dict] = []
    auth_header = token if token.lower().startswith("bearer ") else f"bearer {token}"

    for host in AMP_API_HOSTS:
        url = f"{host}/v1/catalog/{target.country.upper()}/apps/{target.app_id}/reviews"
        headers = {
            "Accept": "application/json",
            "Authorization": auth_header,
            "Origin": LANDING_HOST,
            "Referer": target.landing_url,
            "Connection": "keep-alive",
        }
        params: dict = {}
        seen_offsets: set[str] = set()
        page_reviews: list[dict] = []
        host_failed = False

        while True:
            resp = safe_get(session, url, headers=headers, params=params)
            if resp is None:
                host_failed = True
                break

            if resp.status_code in (401, 403):
                logger.info(
                    "%s rejected the token (HTTP %s) — expected if Apple has "
                    "retired this mechanism.",
                    host,
                    resp.status_code,
                )
                host_failed = True
                break

            if resp.status_code != 200:
                logger.info("%s responded with status %s.", host, resp.status_code)
                host_failed = True
                break

            try:
                payload = resp.json()
            except ValueError:
                logger.info("%s returned non-JSON content.", host)
                host_failed = True
                break

            entries = payload.get("data", [])
            if not entries:
                break

            for entry in entries:
                attrs = entry.get("attributes", {})
                page_reviews.append(normalize_amp_review(attrs, target.country, target.app_id))

            if max_reviews and len(page_reviews) >= max_reviews:
                page_reviews = page_reviews[:max_reviews]
                break

            next_link = payload.get("next")
            if not next_link:
                break
            offset_match = re.search(r"offset=([0-9]+)", next_link)
            if not offset_match:
                break
            offset = offset_match.group(1)
            if offset in seen_offsets:
                break
            seen_offsets.add(offset)
            params = {"offset": offset}
            time.sleep(delay + random.uniform(0, 0.4))

        if page_reviews:
            collected.extend(page_reviews)
            return collected
        if not host_failed:
            return collected

    return collected


# --------------------------------------------------------------------------- #
# TERTIARY (best-effort): legacy customer-reviews RSS feed
# --------------------------------------------------------------------------- #


def normalize_rss_review(entry: dict, country: str, app_id: str) -> Optional[dict]:
    if "im:rating" not in entry:
        return None
    return {
        "reviewer": entry.get("author", {}).get("name", {}).get("label"),
        "review_title": entry.get("title", {}).get("label"),
        "review": entry.get("content", {}).get("label"),
        "rating": entry.get("im:rating", {}).get("label"),
        "review_date": entry.get("updated", {}).get("label"),
        "app_version": entry.get("im:version", {}).get("label"),
        "country": country.upper(),
        "source": "App Store (RSS fallback)",
        "app_id": app_id,
        "is_edited": None,
        "developer_response": None,
    }


def fetch_reviews_rss_fallback(
    session: requests.Session,
    target: ScrapeTarget,
    max_pages: int = 10,
    delay: float = DEFAULT_DELAY,
) -> list[dict]:
    """
    Best-effort fallback using Apple's legacy customer-reviews RSS feed.
    Known to be unreliable: heavily throttled per IP, and the JSON variant
    frequently returns an empty feed even when the app has reviews. Capped
    at 10 pages x ~50 reviews/page by Apple regardless. The only source here
    that reports app_version, when it does respond.
    """
    collected: list[dict] = []
    for page in range(1, max_pages + 1):
        url = RSS_FALLBACK_TEMPLATE.format(country=target.country, page=page, app_id=target.app_id)
        resp = safe_get(session, url, headers={"Accept": "application/json"})
        if resp is None or resp.status_code != 200:
            logger.info("RSS fallback stopped at page %d (bad response).", page)
            break
        try:
            payload = resp.json()
        except ValueError:
            logger.info("RSS fallback stopped at page %d (non-JSON body).", page)
            break

        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            logger.info("RSS fallback: no entries on page %d, stopping.", page)
            break

        page_count = 0
        for entry in entries:
            normalized = normalize_rss_review(entry, target.country, target.app_id)
            if normalized:
                collected.append(normalized)
                page_count += 1
        logger.info("RSS fallback page %d: %d review(s).", page, page_count)
        time.sleep(delay)

    return collected


# --------------------------------------------------------------------------- #
# Orchestration + persistence
# --------------------------------------------------------------------------- #


def scrape_app_store_reviews(
    url: str,
    max_reviews: Optional[int] = 2000,
    delay: float = DEFAULT_DELAY,
    manual_token: Optional[str] = None,
    locale: str = "en-us",
    dump_html_path: Optional[Path] = None,
    skip_amp_api: bool = False,
    skip_rss: bool = False,
) -> pd.DataFrame:
    target = parse_app_store_url(url)
    logger.info(
        "Target -> country=%s, app_id=%s, slug=%s",
        target.country,
        target.app_id,
        target.app_slug,
    )

    session = build_session()
    reviews: list[dict] = []

    # Primary: server-rendered reviews page (no token needed).
    reviews.extend(fetch_reviews_ssr_page(session, target, locale, dump_html_path))

    # Secondary: AMP API (best-effort).
    if not skip_amp_api:
        token = manual_token or get_bearer_token(session, target.landing_url)
        if token:
            amp_reviews = fetch_reviews_amp_api(session, token, target, max_reviews, delay)
            if amp_reviews:
                logger.info("AMP API contributed %d additional review(s).", len(amp_reviews))
            reviews.extend(amp_reviews)

    # Tertiary: legacy RSS feed (best-effort, also gives app_version).
    if not skip_rss:
        rss_reviews = fetch_reviews_rss_fallback(session, target, delay=delay)
        if rss_reviews:
            logger.info("RSS fallback contributed %d additional review(s).", len(rss_reviews))
        reviews.extend(rss_reviews)

    if not reviews:
        logger.error(
            "No reviews retrieved from any source. Manual recovery: open %s "
            "in Chrome, DevTools -> Network -> Fetch/XHR, scroll the "
            "reviews section, and inspect what request actually fetches "
            "them today.",
            target.landing_url,
        )

    df = pd.DataFrame(reviews)
    if df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    ordered_cols = REQUIRED_COLUMNS + [c for c in df.columns if c not in REQUIRED_COLUMNS]
    df = df[ordered_cols]

    before = len(df)
    df = df.drop_duplicates(subset=["reviewer", "review_title", "review", "review_date"])
    if len(df) != before:
        logger.info("Dropped %d duplicate review(s) across sources.", before - len(df))

    return df.reset_index(drop=True)


def save_reviews(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("Saved %d review(s) -> %s", len(df), output_path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main():
    parser = argparse.ArgumentParser(description="Apple App Store review scraper")
    parser.add_argument(
        "--url",
        default="https://apps.apple.com/in/app/blinkit-groceries-more/id960335206",
        help="App Store product page URL.",
    )
    parser.add_argument(
        "--output",
        default=str(
            Path(__file__).resolve().parent.parent / "data" / "raw" / "blinkit_appstore_reviews.csv"
        ),
        help="Output CSV path.",
    )
    parser.add_argument("--max-reviews", type=int, default=2000,
                         help="Cap on AMP API reviews (0 = no limit). SSR/RSS tiers are unaffected.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                         help="Delay in seconds between paginated requests.")
    parser.add_argument(
        "--token", default=None,
        help="Manually supply a bearer token captured from Chrome DevTools "
             "(Network -> Fetch/XHR -> amp-api*.apps.apple.com -> "
             "'authorization' header) to try the AMP API path.",
    )
    parser.add_argument("--locale", default="en-us",
                         help="Locale to request for the SSR reviews page (default: en-us).")
    parser.add_argument(
        "--dump-html", default=None,
        help="Path to save the raw SSR reviews-page HTML for manual inspection.",
    )
    parser.add_argument("--skip-amp-api", action="store_true",
                         help="Skip the AMP API path entirely.")
    parser.add_argument("--skip-rss", action="store_true",
                         help="Skip the legacy RSS fallback entirely.")
    args = parser.parse_args()

    max_reviews = args.max_reviews if args.max_reviews > 0 else None

    df = scrape_app_store_reviews(
        url=args.url,
        max_reviews=max_reviews,
        delay=args.delay,
        manual_token=args.token,
        locale=args.locale,
        dump_html_path=Path(args.dump_html) if args.dump_html else None,
        skip_amp_api=args.skip_amp_api,
        skip_rss=args.skip_rss,
    )
    save_reviews(df, Path(args.output))


if __name__ == "__main__":
    main()