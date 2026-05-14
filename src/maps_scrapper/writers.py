import csv
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import asdict, fields
from pathlib import Path

from .models import Place

PLACE_FIELDS: list = [f.name for f in fields(Place)]


def infer_format(path: str | os.PathLike[str]) -> str:
    return "jsonl" if Path(path).suffix.lower() == ".jsonl" else "csv"


def _write_jsonl(records: list[dict], f) -> None:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_records(
    path: str | os.PathLike[str] | None,
    places: Iterable[Place],
    *,
    format: str = "jsonl",
    append: bool = False,
) -> int:
    records = [asdict(p) for p in places]
    if not records:
        return 0

    if path is None:
        _write_jsonl(records, sys.stdout)
        sys.stdout.flush()
        return len(records)

    file_exists = os.path.isfile(path)
    mode = "a" if append else "w"

    if format == "csv":
        write_header = not (append and file_exists)
        with open(path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PLACE_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(records)
    elif format == "jsonl":
        with open(path, mode, encoding="utf-8") as f:
            _write_jsonl(records, f)
    else:
        raise ValueError(f"unsupported format: {format!r}")

    return len(records)
