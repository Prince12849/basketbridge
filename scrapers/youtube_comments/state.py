"""
state.py
========
Two pieces of state make interrupted runs safe to resume:

1. ScraperState — a small JSON file tracking which video_ids have been
   *fully* processed (all their comments collected and written). On
   restart, already-done videos are skipped entirely.

2. load_existing_comment_ids — reads comment_id values already present in
   the output CSV so that even a *retried* video (e.g. one that failed
   halfway through last run and was never marked done) can never produce
   duplicate rows: every comment is deduped by id before being written,
   regardless of which run first wrote it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ScraperState:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.completed_video_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.completed_video_ids = set(data.get("completed_video_ids", []))
            logger.info(
                "Resumed prior state: %d video(s) already completed.",
                len(self.completed_video_ids),
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read state file (%s) — starting fresh.", exc)

    def is_done(self, video_id: str) -> bool:
        return video_id in self.completed_video_ids

    def mark_done(self, video_id: str) -> None:
        self.completed_video_ids.add(video_id)
        self._save()

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"completed_video_ids": sorted(self.completed_video_ids)}, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.state_path)  # atomic on POSIX and Windows


def load_existing_comment_ids(csv_path: Path) -> set:
    """Load comment_id values already saved, for cross-run dedup."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return set()
    import pandas as pd

    try:
        df = pd.read_csv(csv_path, usecols=["comment_id"], dtype=str)
        return set(df["comment_id"].dropna().tolist())
    except Exception as exc:
        logger.warning(
            "Could not read existing output CSV for dedup (%s) — "
            "assuming no prior comments.",
            exc,
        )
        return set()
