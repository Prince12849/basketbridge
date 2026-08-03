"""
youtube_scraper.py
====================
Entry point. Ties together video discovery (video_search.py), comment
collection (comment_fetcher.py), and resumable/deduped incremental saving
(state.py) into one run.

Usage:
    python youtube_scraper.py
    python youtube_scraper.py --max-videos 20 --max-comments-per-video 200
    python youtube_scraper.py --sort popular
    python youtube_scraper.py --no-resume   # ignore prior progress, redo everything

Output:
    data/raw/blinkit_youtube_comments.csv  (append-mode, safe to interrupt)
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path
from typing import Optional

from tqdm import tqdm

import config
from utils import setup_logging, parse_count
from video_search import search_videos
from comment_fetcher import fetch_comments_for_video
from state import ScraperState, load_existing_comment_ids

logger = setup_logging()


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def discover_videos(queries: list[str], per_query_limit: int, max_total: int) -> list[dict]:
    """
    Search every query, then merge results round-robin (1st result of query
    A, 1st of query B, ..., 2nd of query A, ...) so the final capped list
    reflects all queries rather than being dominated by whichever query ran
    first. Each video is attributed to the query that first surfaced it and
    is only scraped once even if multiple queries return it.
    """
    per_query_results: dict[str, list[dict]] = {}
    for query in tqdm(queries, desc="Searching YouTube"):
        found = search_videos(query, per_query_limit)
        logger.info("Query %r -> %d candidate video(s).", query, len(found))
        per_query_results[query] = found
        time.sleep(config.REQUEST_DELAY_SECONDS)

    merged: list[dict] = []
    seen_ids: set[str] = set()
    max_len = max((len(v) for v in per_query_results.values()), default=0)

    for i in range(max_len):
        for query, vids in per_query_results.items():
            if len(merged) >= max_total:
                break
            if i >= len(vids):
                continue
            candidate = vids[i]
            if candidate["video_id"] in seen_ids:
                continue
            seen_ids.add(candidate["video_id"])
            candidate = dict(candidate, search_query=query)
            merged.append(candidate)
        if len(merged) >= max_total:
            break

    for video_id in config.EXTRA_VIDEO_IDS:
        if video_id not in seen_ids and len(merged) < max_total:
            seen_ids.add(video_id)
            merged.append(
                {
                    "video_id": video_id,
                    "video_title": "",
                    "channel_name": "",
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "search_query": "manual",
                }
            )

    return merged


# --------------------------------------------------------------------------- #
# Normalization + CSV writing
# --------------------------------------------------------------------------- #


def normalize_comment(raw: dict, video: dict) -> dict:
    return {
        "source": "youtube",
        "search_query": video["search_query"],
        "video_title": video["video_title"],
        "video_id": video["video_id"],
        "video_url": video["video_url"],
        "channel_name": video["channel_name"],
        "comment_id": raw.get("cid"),
        "comment": raw.get("text"),
        "author": raw.get("author"),
        "likes": parse_count(raw.get("votes")),
        "reply_count": parse_count(raw.get("replies")),
        "published_at": raw.get("time"),
    }


def append_rows(csv_path: Path, rows: list[dict], write_header: bool) -> None:
    # utf-8-sig so Excel (and any tool assuming a BOM) renders emoji/Indic
    # scripts/etc. correctly instead of mangling them.
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=config.OUTPUT_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def run(
    max_videos: int,
    max_comments_per_video: Optional[int],
    sort_by: int,
    resume: bool,
) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state = ScraperState(config.STATE_FILE)
    seen_comment_ids = load_existing_comment_ids(config.OUTPUT_CSV)
    write_header = not config.OUTPUT_CSV.exists() or config.OUTPUT_CSV.stat().st_size == 0

    logger.info(
        "Starting run: max_videos=%d, max_comments_per_video=%s, resume=%s",
        max_videos,
        max_comments_per_video or "unlimited",
        resume,
    )

    videos = discover_videos(config.SEARCH_QUERIES, config.VIDEOS_PER_QUERY, max_videos)
    logger.info("Discovered %d unique video(s) to process.", len(videos))

    total_new_comments = 0
    failed_videos = []

    for video in tqdm(videos, desc="Videos"):
        video_id = video["video_id"]

        if resume and state.is_done(video_id):
            logger.info("Skipping already-completed video %s.", video_id)
            continue

        try:
            raw_comments = fetch_comments_for_video(video_id, max_comments_per_video, sort_by)
        except Exception as exc:
            # A single bad video must not kill the whole run.
            logger.error("Giving up on video %s after retries: %s", video_id, exc)
            failed_videos.append(video_id)
            continue

        new_rows = []
        for raw in raw_comments:
            cid = raw.get("cid")
            if not cid or cid in seen_comment_ids:
                continue
            seen_comment_ids.add(cid)
            new_rows.append(normalize_comment(raw, video))

        if new_rows:
            append_rows(config.OUTPUT_CSV, new_rows, write_header)
            write_header = False
            total_new_comments += len(new_rows)
            logger.info(
                "Video %s (%r): saved %d new comment(s) [%d fetched].",
                video_id,
                video["video_title"][:50],
                len(new_rows),
                len(raw_comments),
            )
        else:
            logger.info(
                "Video %s: no new comments (0 found or all already collected).",
                video_id,
            )

        # Mark done regardless of whether new rows were written — an empty
        # comment section is a legitimate, final result, not a failure.
        state.mark_done(video_id)
        time.sleep(config.REQUEST_DELAY_SECONDS + random.uniform(0, 0.5))

    logger.info(
        "Run complete. %d new comment(s) saved -> %s. %d video(s) failed: %s",
        total_new_comments,
        config.OUTPUT_CSV,
        len(failed_videos),
        failed_videos or "none",
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main():
    parser = argparse.ArgumentParser(description="Blinkit YouTube comments scraper (no API key)")
    parser.add_argument(
        "--max-videos",
        type=int,
        default=config.MAX_TOTAL_VIDEOS,
        help=f"Cap on total unique videos processed (default: {config.MAX_TOTAL_VIDEOS}).",
    )
    parser.add_argument(
        "--max-comments-per-video",
        type=int,
        default=config.MAX_COMMENTS_PER_VIDEO,
        help="Cap on comments collected per video. Use 0 for unlimited "
        f"(default: {config.MAX_COMMENTS_PER_VIDEO}).",
    )
    parser.add_argument(
        "--sort",
        choices=["recent", "popular"],
        default="recent",
        help="Comment sort order to request from YouTube (default: recent).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore any prior progress in the state file and re-scrape everything.",
    )
    args = parser.parse_args()

    sort_by = config.SORT_BY_POPULAR if args.sort == "popular" else config.SORT_BY_RECENT
    max_comments = args.max_comments_per_video if args.max_comments_per_video > 0 else None

    run(
        max_videos=args.max_videos,
        max_comments_per_video=max_comments,
        sort_by=sort_by,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
