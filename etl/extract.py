"""Extract: read the raw order export. Nothing is cleaned here: rows come out exactly as the source has them."""
import csv
from collections.abc import Iterator
from pathlib import Path

import obskitpy


@obskitpy.traced("extract")
def extract(path: Path, limit: int = 0) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in _read(handle):
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    return rows


def _read(handle) -> Iterator[dict[str, str]]:
    yield from csv.DictReader(handle)
