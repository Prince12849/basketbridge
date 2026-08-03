"""HTTP helpers: rate limiting, retries with exponential backoff, and a
pre-configured requests.Session."""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, TypeVar

import requests

T = TypeVar("T")

logger = logging.getLogger("blinkit_scraper")


class RateLimiter:
    """Simple token-less rate limiter: sleeps so consecutive calls are
    spaced at least `delay` (+ jitter) seconds apart."""

    def __init__(self, delay: float = 2.0, jitter: float = 0.75) -> None:
        self.delay = delay
        self.jitter = jitter
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        sleep_for = self.delay + random.uniform(0, self.jitter) - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_call = time.monotonic()


def retry(max_retries: int = 4, backoff_base: float = 2.0,
          retry_exceptions: tuple = (requests.RequestException,)) -> Callable:
    """Decorator implementing exponential backoff with jitter.

    Retries on the given exception types and on HTTP 429 / 5xx responses
    (raised as requests.HTTPError by the caller via raise_for_status()).
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == max_retries:
                        break
                    sleep_for = (backoff_base ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                        attempt, max_retries, func.__name__, exc, sleep_for,
                    )
                    time.sleep(sleep_for)
            logger.error("All %d attempts failed for %s: %s",
                         max_retries, func.__name__, last_exc)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def build_session(user_agent: str) -> requests.Session:
    """Return a requests.Session with browser-like headers for public,
    unauthenticated access to reddit.com's read-only JSON/HTML pages."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session
