"""
consumer_complaints_scraper.py

Scrapes Blinkit complaints from ConsumerComplaints.in and returns/saves ONLY
the real complaint content (title, body, date, status, url) -- no login
boxes, navigation, footers, ads, scripts, SVGs, country lists, or other page
chrome.

Why this is a full rewrite, not a patch
----------------------------------------
The previous version of this file used Playwright to render pages and then
BeautifulSoup with a list of CSS-selector *guesses* (`div.complaint-box`,
`div.complaint-description`, etc.) that were never checked against the real
site. Its own docstring admitted this ("HTML was not available to verify at
write time"). Because none of those guessed selectors exist on the real
site, every extraction silently fell through to a last-resort fallback that
picked the single largest <div>/<p> text blob on the page. On a real complaint
page that "largest blob" is very often a wrapper element that also contains
the nav bar, login widget, related-articles list, footer business directory,
etc. -- because BeautifulSoup's `get_text()` concatenates ALL nested text
under whatever element you select. That combination (wrong selectors +
"grab the biggest div" fallback + no chrome stripping) is exactly why the
CSV ended up full of "Sign In", "Register", country lists, and footer text.

This rewrite:
  1. Targets the real page structure (verified by fetching live pages):
     - a company/listing page  https://www.consumercomplaints.in/bycompany/<slug>.html
       and its paginated form  .../bycompany/<slug>/page/2 , /page/3, ...
     - individual complaint permalinks of the form
       https://www.consumercomplaints.in/<slug>-c<digits>
  2. Uses plain `requests` (the site is server-rendered HTML; no JS engine
     is needed), with real headers, timeouts, and retries.
  3. Actively DELETES known chrome before extracting anything: <script>,
     <style>, <svg>, <nav>, <header>, <footer>, <form>, hidden elements, and
     any element whose class/id names indicate menus, login, cookie
     banners, breadcrumbs, related-content, the footer business directory /
     country list, comment forms, captchas, share widgets, etc.
  4. Extracts the complaint body via content-anchored logic (find the
     complaint's own heading/permalink, then walk forward collecting text
     until a known "boundary" marker such as "Was this information
     helpful", "Related reviews", "Post your Comment", "Contact
     Information", etc.) instead of "biggest text blob on the page". This
     is robust to minor markup/class-name changes because it does not
     depend on any single guessed class name to draw the line -- it depends
     on recognizable, stable *end-of-complaint* phrases the site itself
     prints on every complaint page.
  5. `clean_text()` performs a second pass that trims any of those boundary
     phrases if they still leak into the extracted string, collapses
     whitespace, and strips leftover artifacts.
  6. Every record is validated before being kept; complaints with no real
     body are skipped (never written to the CSV).

Usage
-----
    python consumer_complaints_scraper.py
    python consumer_complaints_scraper.py --max-pages 5 --limit 100
    python consumer_complaints_scraper.py --output data/raw/blinkit_consumer_complaints.csv

Programmatic:
    from consumer_complaints_scraper import ScraperConfig, run_scraper
    df = run_scraper(ScraperConfig(max_pages=5))
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
from requests.adapters import HTTPAdapter
from tqdm import tqdm

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - very old urllib3
    from requests.packages.urllib3.util.retry import Retry  # type: ignore


# ===========================================================================
# Logging
# ===========================================================================

logger = logging.getLogger("blinkit_complaints_scraper")


def setup_logger(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    log = logger
    if log.handlers:
        return log
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    log.addHandler(console)
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    log.propagate = False
    return log


# ===========================================================================
# Configuration
# ===========================================================================

@dataclass
class ScraperConfig:
    base_url: str = "https://www.consumercomplaints.in"
    # The Blinkit company page on ConsumerComplaints.in. This is the real
    # listing surface for a single company's complaints (verified live);
    # it is NOT the same as a generic "?search=" query string, which the
    # previous scraper guessed at and which does not reliably return a
    # clean, paginated list of Blinkit-only complaints.
    company_url: str = "https://www.consumercomplaints.in/bycompany/blinkit-a616132.html"
    company_name: str = "Blinkit"
    # Used to make sure we only ever follow links that are genuinely
    # Blinkit complaint permalinks (requirement: "scrape ONLY Blinkit
    # complaint pages").
    slug_prefix: str = "blinkit"

    source: str = "consumercomplaints.in"

    max_pages: int = 10                 # cap on listing pages to paginate through
    max_complaints: Optional[int] = None  # overall cap on complaints scraped

    min_delay: float = 1.0
    max_delay: float = 2.5
    timeout: float = 15.0
    max_retries: int = 4
    backoff_factor: float = 1.5

    checkpoint_every: int = 20
    output_path: Path = Path("data/raw/blinkit_consumer_complaints.csv")

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    log_level: str = "INFO"
    log_file: Optional[Path] = Path("logs/consumer_complaints_scraper.log")


# ===========================================================================
# Constants: URL patterns, noise selectors, boundary markers
# ===========================================================================

# A complaint permalink looks like "/blinkit-some-slug-c3542692".
COMPLAINT_URL_PATTERN = re.compile(r"-c\d{5,}(?:\.html)?$", re.IGNORECASE)

MIN_COMPLAINT_CHARS = 20

# Elements to remove entirely before any text extraction is attempted.
# Matched both by tag name and, for generic containers, by class/id
# keywords -- so this keeps working even if the site renames a class as
# long as the naming still hints at its purpose (a very common pattern).
NOISE_TAGS = ["script", "style", "svg", "noscript", "nav", "header", "footer", "form", "iframe"]

NOISE_CLASS_ID_KEYWORDS = [
    "login", "signin", "sign-in", "register", "signup", "sign-up",
    "menu", "navbar", "breadcrumb", "sidebar", "side-bar",
    "cookie", "consent", "gdpr",
    "footer", "site-footer",
    "advert", "banner-ad", "adsbygoogle", "sponsor",
    "related", "recommend", "you-may-also",
    "comment-form", "post-comment", "captcha",
    "company-list", "business-directory", "country-list", "country_list",
    "social", "share-", "share_", "follow-us",
    "working-hours", "opening-hours",
    "back-to-top", "scroll-top",
    "byline", "authorinfo", "author-info", "user-name", "reviewer-info",
]

# Phrases that mark the END of a complaint's own text -- everything from
# the first occurrence of any of these onward is cut off. These are the
# site's own recurring UI strings (verified against live pages), so this
# check is resilient to CSS/class changes.
BOUNDARY_PATTERNS = [
    re.compile(r"Was this information helpful.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"\d+\s+other people found this review helpful.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Found this helpful\??.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bHelpful\b\s*$", re.IGNORECASE),
    re.compile(r"Report\s*Copy.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Write a comment.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Add a Comment.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Related reviews.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Post your Comment.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Contact Information.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"View all \d+ Reviews.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Updated by\b.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"This thread was updated on.*", re.IGNORECASE | re.DOTALL),
]

# Exact/near-exact boilerplate lines to drop wholesale from any block of
# extracted text (site chrome, login/nav/footer strings).
BOILERPLATE_LINES = {
    "sign in", "categories", "faq's", "faq", "submit a complaint",
    "terms of use", "privacy policy", "cookie policy", "comment guideliness",
    "comment guidelines", "about us", "contact us", "facebook", "twitter",
    "main menu", "additional", "follow us", "business directory",
    "restored links", "add image", "submit", "close", "report", "copy",
    "helpful", "file a complaint", "get a quick response",
    "to every complaint you post",
}

# Single-letter footer "company-list/a..z" navigation.
_SINGLE_LETTER_RE = re.compile(r"^[a-zA-Z]$")
_COPYRIGHT_RE = re.compile(r"^©\s*\d{4}", re.IGNORECASE)

# Candidate CSS selectors for complaint-body containers. These are tried
# first (fast path); if none match usable content, the boundary-anchored
# structural fallback below takes over. Because we no longer *depend* on
# any one of these being right, a wrong/missing selector degrades
# gracefully instead of producing garbage.
BODY_SELECTOR_CANDIDATES = [
    "div.complaint-description", "div.complaint-body", "div#complaint-text",
    "div.op-content", "div.opdiv", "div.postbody", "td.postbody",
    "div[itemprop='description']", "div.description", "article",
]

TITLE_SELECTOR_CANDIDATES = ["h1", "h2"]

STATUS_KEYWORDS = ("resolved", "unresolved", "pending", "in progress", "closed")


# ===========================================================================
# Data model / output schema
# ===========================================================================

OUTPUT_COLUMNS = [
    "source",
    "company",
    "complaint_title",
    "complaint_text",
    "complaint_date",
    "complaint_status",
    "complaint_url",
]


# ===========================================================================
# HTTP session with retries/timeouts
# ===========================================================================

def build_session(config: ScraperConfig) -> requests.Session:
    """Create a requests.Session with browser-like headers and an HTTP-level
    retry policy (handles connection errors / 429 / 5xx transparently)."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Connection": "keep-alive",
        }
    )
    retry = Retry(
        total=config.max_retries,
        backoff_factor=config.backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_html(session: requests.Session, url: str, timeout: float) -> Optional[str]:
    """Fetch a URL and return its HTML, or None on failure. Never raises --
    callers can skip a failed page without crashing the whole run."""
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        # Guard against mis-detected encodings producing mojibake.
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def polite_delay(config: ScraperConfig) -> None:
    import random
    time.sleep(random.uniform(config.min_delay, config.max_delay))


# ===========================================================================
# Noise removal
# ===========================================================================

def _attr_str(tag, name: str, default: str = "") -> str:
    """Safely read an attribute as a plain str.

    bs4's type stubs declare tag attributes as
    ``str | list[str] | None`` (a multi-valued attribute like ``class``
    can come back as a list). Indexing/calling ``.strip()`` directly on
    that union is what Pylance flags. This helper normalizes any of those
    shapes to a single ``str`` so downstream code (``urljoin``, ``.strip()``,
    etc.) always gets the type it expects.
    """
    val = tag.get(name)
    if val is None:
        return default
    if isinstance(val, (list, tuple)):
        return " ".join(str(v) for v in val) if val else default
    return str(val)


def _looks_noisy(tag) -> bool:
    class_and_id = " ".join(tag.get("class", []) or []) + " " + (tag.get("id") or "")
    class_and_id = class_and_id.lower()
    return any(kw in class_and_id for kw in NOISE_CLASS_ID_KEYWORDS)


def strip_chrome(soup: BeautifulSoup) -> None:
    """Remove scripts/styles/nav/footer/login/ads/etc. IN PLACE so that any
    subsequent text extraction can only ever see complaint-relevant text."""
    # Tag-based removal.
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # HTML comments (some sites hide widgets/ads inside <!-- --> blocks).
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # Class/id keyword based removal (menus, login, cookie banners, related
    # content, footer directory, comment forms, captchas, share widgets...).
    # `find_all(True)` matches every tag; using a lambda instead of the bare
    # literal keeps the bs4 type stubs happy (they expect a Tag predicate,
    # not attrs values typed as bool).
    for tag in soup.find_all(lambda t: True):
        if tag.parent is None:
            continue
        if _looks_noisy(tag):
            tag.decompose()

    # Explicitly hidden elements (display:none / hidden attr / aria-hidden).
    # Using lambda predicates (rather than the `style=`/`attrs=` keyword
    # forms) sidesteps bs4's overloaded find_all() type stubs entirely --
    # those overloads are what Pylance was struggling to resolve.
    _display_none_re = re.compile(r"display\s*:\s*none", re.IGNORECASE)
    for tag in soup.find_all(lambda t: bool(_display_none_re.search(_attr_str(t, "style")))):
        tag.decompose()
    for tag in soup.find_all(lambda t: t.has_attr("hidden")):
        tag.decompose()
    for tag in soup.find_all(lambda t: _attr_str(t, "aria-hidden").lower() == "true"):
        tag.decompose()


# ===========================================================================
# Text cleaning
# ===========================================================================

def clean_text(text: str) -> str:
    """Normalize whitespace, cut off at the first known boundary phrase, and
    drop boilerplate/navigation lines that may have slipped through."""
    if not text:
        return ""

    # Cut at the earliest boundary-phrase match, if any.
    earliest = None
    for pattern in BOUNDARY_PATTERNS:
        m = pattern.search(text)
        if m and (earliest is None or m.start() < earliest):
            earliest = m.start()
    if earliest is not None:
        text = text[:earliest]

    # Drop boilerplate / single-letter nav / copyright lines.
    lines = re.split(r"[\r\n]+", text)
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low in BOILERPLATE_LINES:
            continue
        if _SINGLE_LETTER_RE.match(stripped):
            continue
        if _COPYRIGHT_RE.match(stripped):
            continue
        kept.append(stripped)
    text = " ".join(kept)

    # Collapse whitespace and strip a trailing stray "br" artifact left
    # over from literal <br> text nodes on this site.
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bbr\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


# ===========================================================================
# Listing pages: discovery of complaint links
# ===========================================================================

def _next_listing_url(soup: BeautifulSoup, current_url: str, base_url: str,
                       page_num: int, company_url: str) -> Optional[str]:
    """Find the 'next page' link. Tries explicit rel/class/text markers
    first, then falls back to the site's observed /page/N URL pattern."""
    candidates = [
        soup.select_one("a[rel='next']"),
        soup.select_one("a.next"),
        soup.select_one("li.next a"),
    ]
    for tag in candidates:
        href = _attr_str(tag, "href") if tag else ""
        if href:
            return urljoin(base_url, href)

    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True).lower() in ("next", "»"):
            return urljoin(base_url, _attr_str(a, "href"))

    # Fallback: observed pattern is .../bycompany/<slug>/page/N (no .html).
    parsed = urlparse(company_url)
    slug_path = parsed.path
    if slug_path.endswith(".html"):
        slug_path = slug_path[: -len(".html")]
    slug_path = slug_path.rstrip("/")
    next_url = f"{parsed.scheme}://{parsed.netloc}{slug_path}/page/{page_num + 1}"
    return next_url


def get_listing_pages(session: requests.Session, config: ScraperConfig) -> Iterable[str]:
    """Generator that yields raw HTML for each listing (company) page, up to
    config.max_pages, following pagination. Stops early if a page fetch
    fails or returns no new complaint links."""
    url = config.company_url
    page_num = 1
    pbar = tqdm(total=config.max_pages, desc="Listing pages", unit="page")
    try:
        while url and page_num <= config.max_pages:
            html = fetch_html(session, url, config.timeout)
            pbar.update(1)
            if html is None:
                logger.warning("Stopping pagination: could not fetch page %d (%s)", page_num, url)
                break

            yield html

            soup = BeautifulSoup(html, "html.parser")
            links_on_page = extract_complaint_links(html, config.base_url, config.slug_prefix)
            if not links_on_page:
                logger.info("No complaint links found on listing page %d -- stopping.", page_num)
                break

            next_url = _next_listing_url(soup, url, config.base_url, page_num, config.company_url)
            if not next_url or next_url == url:
                break
            url = next_url
            page_num += 1
            polite_delay(config)
    finally:
        pbar.close()


def extract_complaint_links(html: str, base_url: str, slug_prefix: str) -> List[str]:
    """Pull every unique Blinkit complaint permalink out of a listing page."""
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    seen: Set[str] = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, _attr_str(a, "href"))
        path = urlparse(href).path.lower()
        if not COMPLAINT_URL_PATTERN.search(path):
            continue
        # Restrict strictly to Blinkit complaints, per requirements.
        slug = path.rsplit("/", 1)[-1]
        if not slug.startswith(slug_prefix.lower()):
            continue
        if href not in seen:
            seen.add(href)
            links.append(href)

    return links


# ===========================================================================
# Complaint detail page parsing
# ===========================================================================

def _extract_title(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"property": "og:title"}) or soup.find(
        "meta", attrs={"name": "twitter:title"}
    )
    if meta and meta.get("content"):
        title = _attr_str(meta, "content").strip()
    else:
        h1 = soup.find(["h1", "h2"])
        title = h1.get_text(" ", strip=True) if h1 else ""
        if not title and soup.title:
            title = soup.title.get_text(strip=True)

    # Titles are typically "Company — Complaint Title"; keep only the part
    # after the dash if present, since `company` is stored separately.
    for dash in (" — ", " - ", ": "):
        if dash in title:
            _, _, rest = title.partition(dash)
            if rest.strip():
                title = rest.strip()
            break
    return title


def _extract_date(soup: BeautifulSoup) -> str:
    time_tag = soup.find("time")
    if time_tag:
        val = _attr_str(time_tag, "datetime") or time_tag.get_text(strip=True)
        if val:
            return val.strip()

    text = soup.get_text(" ", strip=True)
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group()
    return ""


def _extract_status(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True).lower()
    for kw in STATUS_KEYWORDS:
        if kw in text:
            return kw.title()
    return "Unresolved"


def _extract_body(soup: BeautifulSoup) -> str:
    # Fast path: known/likely selectors.
    for sel in BODY_SELECTOR_CANDIDATES:
        tag = soup.select_one(sel)
        if tag:
            text = clean_text(tag.get_text(" ", strip=True))
            if len(text) >= MIN_COMPLAINT_CHARS:
                return text

    # Structural fallback: anchor on the complaint's own permalink/heading,
    # then walk forward collecting paragraph-like text until we hit a
    # boundary marker or run out of siblings. This does not depend on any
    # particular class name, only on document order relative to the
    # heading -- which is stable even when styling/classes change.
    heading = soup.find(["h1", "h2"])
    start_node = heading if heading else soup.body or soup

    collected: List[str] = []
    total_len = 0
    min_block_chars = 30  # skip short metadata snippets (byline, date, tags)
    for el in start_node.find_all_next(["p", "div", "span", "li"]):
        el_text = el.get_text(" ", strip=True)
        if not el_text:
            continue
        if any(pattern.search(el_text) for pattern in BOUNDARY_PATTERNS):
            # Keep whatever precedes the boundary phrase in this node, then stop.
            trimmed = clean_text(el_text)
            if trimmed:
                collected.append(trimmed)
            break
        if len(el_text) < min_block_chars:
            continue
        collected.append(el_text)
        total_len += len(el_text)
        if total_len > 4000:  # safety cap
            break

    combined = clean_text(" ".join(collected))
    return combined


def scrape_complaint(session: requests.Session, url: str, config: ScraperConfig) -> Optional[dict]:
    """Fetch and parse a single complaint page. Returns a record dict, or
    None if the page couldn't be fetched or no usable complaint body was
    found (never raises)."""
    html = fetch_html(session, url, config.timeout)
    if html is None:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        strip_chrome(soup)

        title = _extract_title(soup)
        body = _extract_body(soup)
        date_str = _extract_date(soup)
        status = _extract_status(soup)

        if not body:
            logger.info("No complaint body found for %s -- skipping.", url)
            return None

        return {
            "source": config.source,
            "company": config.company_name,
            "complaint_title": title.strip(),
            "complaint_text": body.strip(),
            "complaint_date": date_str.strip(),
            "complaint_status": status.strip(),
            "complaint_url": url,
        }
    except Exception as exc:  # noqa: BLE001 - never let one bad page crash the run
        logger.warning("Failed to parse complaint page %s: %s", url, exc)
        return None


# ===========================================================================
# Validation
# ===========================================================================

def validate_record(record: Optional[dict]) -> bool:
    if not record:
        return False
    text = record.get("complaint_text", "") or ""
    title = record.get("complaint_title", "") or ""
    url = record.get("complaint_url", "") or ""

    if len(text) < MIN_COMPLAINT_CHARS:
        return False
    if text.strip().lower() == title.strip().lower():
        return False
    if not COMPLAINT_URL_PATTERN.search(urlparse(url).path.lower()):
        return False
    # Reject anything that still smells like leaked page chrome.
    low = text.lower()
    if "sign in" in low and "terms of use" in low:
        return False
    return True


# ===========================================================================
# Deduplication + incremental checkpointing
# ===========================================================================

def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()


def save_checkpoint(records: List[dict], path: Path) -> None:
    """Write current progress to CSV (overwrites with the full set collected
    so far). Safe to call repeatedly; called every `checkpoint_every`
    complaints and once more at the end of the run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in records:
            writer.writerow({col: row.get(col, "") for col in OUTPUT_COLUMNS})


# ===========================================================================
# Orchestration
# ===========================================================================

def run_scraper(config: ScraperConfig) -> pd.DataFrame:
    setup_logger(config.log_level, config.log_file)
    logger.info("Starting Blinkit ConsumerComplaints.in scrape.")
    logger.info("Company page: %s | max_pages=%d | max_complaints=%s",
                config.company_url, config.max_pages, config.max_complaints)

    session = build_session(config)

    # --- Discovery phase: collect unique, deduplicated complaint URLs -----
    discovered: List[str] = []
    seen_norm: Set[str] = set()
    for html in get_listing_pages(session, config):
        for link in extract_complaint_links(html, config.base_url, config.slug_prefix):
            key = normalize_url(link)
            if key not in seen_norm:
                seen_norm.add(key)
                discovered.append(link)
        if config.max_complaints and len(discovered) >= config.max_complaints:
            discovered = discovered[: config.max_complaints]
            break

    logger.info("Discovery complete: %d unique Blinkit complaint URLs found.", len(discovered))

    # --- Scrape phase -------------------------------------------------
    records: List[dict] = []
    stats = {"scraped": 0, "skipped_invalid": 0, "failed": 0}

    pbar = tqdm(discovered, desc="Scraping complaints", unit="complaint")
    for i, url in enumerate(pbar, start=1):
        pbar.set_postfix_str(url.rsplit("/", 1)[-1][:40])
        record = scrape_complaint(session, url, config)

        if validate_record(record):
            records.append(record)  # type: ignore[arg-type]
            stats["scraped"] += 1
        elif record is None:
            stats["failed"] += 1
        else:
            stats["skipped_invalid"] += 1

        if config.checkpoint_every and i % config.checkpoint_every == 0:
            save_checkpoint(records, config.output_path)
            logger.info("Checkpoint saved: %d valid complaints so far.", len(records))

        polite_delay(config)

    # --- Final save -----------------------------------------------------
    df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    if not df.empty:
        df = df.drop_duplicates(subset=["complaint_url"]).reset_index(drop=True)
    save_checkpoint(df.to_dict(orient="records"), config.output_path)

    logger.info("Scrape complete. Valid complaints saved: %d", len(df))
    logger.info("Stats: %s", stats)
    logger.info("Output written to: %s", config.output_path)

    return df


# ===========================================================================
# CLI
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Blinkit complaints from ConsumerComplaints.in"
    )
    parser.add_argument("--company-url", type=str,
                        default="https://www.consumercomplaints.in/bycompany/blinkit-a616132.html")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Maximum listing pages to paginate through (default: 10)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap on total complaints to scrape (default: unlimited)")
    parser.add_argument("--output", type=str, default="data/raw/blinkit_consumer_complaints.csv",
                        help="Output CSV path (default: data/raw/blinkit_consumer_complaints.csv)")
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=2.5)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--log-file", type=str, default="logs/consumer_complaints_scraper.log",
                        help="Log file path (default: logs/consumer_complaints_scraper.log; "
                             "pass an empty string to disable file logging)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ScraperConfig(
        company_url=args.company_url,
        max_pages=args.max_pages,
        max_complaints=args.limit,
        output_path=Path(args.output),
        checkpoint_every=args.checkpoint_every,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        timeout=args.timeout,
        max_retries=args.max_retries,
        log_level=args.log_level,
        log_file=Path(args.log_file) if args.log_file else None,
    )
    df = run_scraper(config)
    print(f"\nSaved {len(df)} valid Blinkit complaints to {config.output_path}")


if __name__ == "__main__":
    main()