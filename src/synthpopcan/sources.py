"""Local source inspection helpers."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

__all__ = ["inspect_source_root", "read_source_sample", "read_source_schema"]


def inspect_source_root(root: Path) -> dict[str, Any]:
    """Summarize files under a local source-data root.

    The result includes the root path, total file count, and extension counts.
    It does not parse source files or expose sample rows.
    """

    files = [path for path in root.rglob("*") if path.is_file()]
    extensions = Counter(path.suffix.lower() or "<none>" for path in files)
    return {
        "root": str(root),
        "files": len(files),
        "extensions": dict(sorted(extensions.items())),
    }


def read_source_schema(path: Path) -> dict[str, Any]:
    """Read the delimiter and header row from a local tabular source file."""

    delimiter = sniff_delimiter(path)
    with path.open(newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        columns = next(reader, [])
    return {
        "path": str(path),
        "delimiter": delimiter,
        "columns": columns,
    }


def read_source_sample(path: Path, rows: int) -> dict[str, Any]:
    """Read a small sample from a local tabular source file.

    The result includes path, delimiter, columns, and up to ``rows`` row
    dictionaries. Callers should treat sampled rows as potentially private.
    """

    if rows < 1:
        raise ValueError("rows must be at least 1")
    delimiter = sniff_delimiter(path)
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        sample = []
        for index, row in enumerate(reader):
            if index >= rows:
                break
            sample.append(dict(row))
    return {
        "path": str(path),
        "delimiter": delimiter,
        "columns": reader.fieldnames or [],
        "rows": sample,
    }


def sniff_delimiter(path: Path) -> str:
    with path.open(newline="") as handle:
        sample = handle.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t|;").delimiter
    except csv.Error:
        return "\t" if path.suffix.lower() in {".tab", ".tsv"} else ","


def is_private_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(
        current == "data" and following == "private"
        for current, following in zip(parts, parts[1:], strict=False)
    )
