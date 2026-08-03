"""CSV writer for the unified post/comment output schema."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

from .models import OUTPUT_COLUMNS

logger = logging.getLogger("blinkit_scraper")


class CSVWriter:
    """Incrementally writes rows to the output CSV so progress is not lost
    if the scraper is interrupted."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._writer: csv.DictWriter | None = None
        self._rows_written = 0

    def __enter__(self) -> "CSVWriter":
        self._file = open(self.output_path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=OUTPUT_COLUMNS)
        self._writer.writeheader()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._file:
            self._file.close()
        logger.info("CSV writer closed. Total rows written: %d", self._rows_written)

    def write_row(self, row: dict) -> None:
        assert self._writer is not None, "Writer not initialised - use as a context manager"
        self._writer.writerow({col: row.get(col, "") for col in OUTPUT_COLUMNS})
        self._rows_written += 1

    def write_rows(self, rows: Iterable[dict]) -> None:
        for row in rows:
            self.write_row(row)

    @property
    def rows_written(self) -> int:
        return self._rows_written
