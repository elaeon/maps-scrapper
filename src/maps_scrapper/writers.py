import csv
import json
import os
from collections.abc import Iterable
from dataclasses import asdict, fields
from pathlib import Path

from .models import Place

PLACE_FIELDS = [f.name for f in fields(Place)]


def infer_format(path: str | os.PathLike[str]) -> str:
    return "jsonl" if Path(path).suffix.lower() == ".jsonl" else "csv"


def append_records(
    path: str | os.PathLike[str],
    places: Iterable[Place],
    *,
    format: str = "csv",
    append: bool = False,
) -> int:
    records = [asdict(p) for p in places]
    if not records:
        return 0

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
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"unsupported format: {format!r}")

    return len(records)
