"""
utils.py
========
Small shared helpers used across the scraper: logging setup, a generic retry
decorator with exponential backoff + jitter, and parsing of YouTube's
human-readable count strings ("1.2K", "3,400") into integers.
"""

from __future__ import annotations

import functools
import logging
import random
import re
import time
from typing import Callable, Optional

import config


def setup_logging() -> logging.Logger:
    """Configure root logging once: console + a log file under data/raw/."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        ],
    )
    return logging.getLogger("youtube_scraper")


def retry(
    max_attempts: int = config.MAX_RETRIES,
    backoff_base: float = config.RETRY_BACKOFF_BASE,
    exceptions: tuple = (Exception,),
):
    """
    Retry a function with exponential backoff + jitter. Re-raises the last
    exception once attempts are exhausted so the caller can decide whether
    to skip-and-continue (which is what this scraper does at the video
    level, per the "continue even if some videos fail" requirement).
    """

    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(fn.__module__)
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203 - clarity over micro-perf here
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    wait = backoff_base**attempt + random.uniform(0, 1)
                    logger.warning(
                        "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                        fn.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
            logging.getLogger(fn.__module__).error(
                "%s failed after %d attempt(s): %s", fn.__name__, max_attempts, last_exc
            )
            raise last_exc

        return wrapper

    return decorator


_COUNT_PATTERN = re.compile(r"^([\d,.]+)\s*([KkMmBb]?)$")


def parse_count(value) -> Optional[int]:
    """
    Parse YouTube's rendered like/reply-count text into an int.
    Handles plain numbers ("42"), thousands separators ("3,400"), and
    K/M/B suffixes ("1.2K", "3.4M"). Returns None if it truly can't be
    parsed (rather than guessing) so bad data is visible, not silently 0.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if text == "":
        return 0

    match = _COUNT_PATTERN.match(text.replace(",", ""))
    if not match:
        return None

    number = float(match.group(1))
    suffix = match.group(2).upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(number * multiplier)
