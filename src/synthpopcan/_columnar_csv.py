"""Optional native CSV parsing with bounded buffers and conservative fallback.

The fast path accepts plain UTF-8 records. Quoting, unusual line endings and
ambiguous values are left to the owning operation's reference CSV parser.
"""

from __future__ import annotations

import csv
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import numpy as np

MIN_COLUMNAR_BYTES = 4 * 1024 * 1024
CSV_CHUNK_BYTES = 8 * 1024 * 1024


class BoundedCSVFallbackError(Exception):
    """The reference parser must restart the operation from the original file."""


def should_use_polars(*paths: Path) -> bool:
    """Avoid optional imports and native startup costs for small inputs."""
    try:
        return any(path.stat().st_size >= MIN_COLUMNAR_BYTES for path in paths) and (
            find_spec("polars") is not None
        )
    except (OSError, ImportError, ValueError):
        # Metadata probes must not replace the reference reader's diagnostics
        # or change which of several invalid inputs it checks first.
        return False


def load_polars():
    """Use only the tested CSV API; unrelated older installations stay optional."""
    try:
        polars = import_module("polars")
    except ImportError:
        return None
    version = str(getattr(polars, "__version__", "0")).split(".")
    if tuple(int(part) if part.isdigit() else 0 for part in version[:2]) < (2, 1):
        return None
    return polars


def _plain_blocks(path: Path, chunk_bytes: int):
    """Yield complete records; never mmap or load the full population file."""
    if chunk_bytes < 1:
        raise ValueError("CSV chunk size must be positive")
    pending, first = b"", True
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            data = pending + chunk
            _check_plain_records(data)
            if first:
                header_end = data.find(b"\n")
                if header_end < 0:
                    pending = data
                    continue
                data, first = data[header_end + 1 :], False
            end = data.rfind(b"\n")
            if end < 0:
                pending = data
                continue
            block, pending = data[: end + 1], data[end + 1 :]
            if block:
                yield block
    if pending.endswith(b"\r"):
        raise BoundedCSVFallbackError("bare carriage return")
    if pending and not first:
        yield pending


def _check_plain_records(data: bytes) -> None:
    if b'"' in data or b"\x00" in data or b"\xef\xbb\xbf" in data:
        raise BoundedCSVFallbackError("quoted, NUL-containing or BOM-containing record")
    raw = np.frombuffer(data, dtype=np.uint8)
    carriage_returns = np.flatnonzero(raw[:-1] == 13)
    if np.any(raw[carriage_returns + 1] != 10):
        raise BoundedCSVFallbackError("bare carriage return")
    # A record bounds every field, including unselected columns. Offset
    # differences avoid allocating one Python bytes object per source record.
    limit = csv.field_size_limit()
    if len(data) > limit:
        offsets = np.flatnonzero(raw == 10)
        lengths = np.diff(offsets, prepend=-1, append=len(data)) - 1
        if lengths.max(initial=0) > limit:
            raise BoundedCSVFallbackError("record exceeds reference field-size limit")


def iter_string_frames(
    path: Path,
    selected_names,
    *,
    optional_defaults=None,
    required=(),
    chunk_bytes=None,
    truncate_ragged_lines=True,
):
    """Yield projected string frames, source ordinals and original header names.

    Duplicate names use their final position, matching DictReader. Nulls stay
    null: each caller decides whether their meaning needs reference parsing.
    ``required`` checks header presence, while missing optional columns receive
    their explicit defaults. ``__source_row`` preserves ordering across groups.
    """
    pl = load_polars()
    if pl is None:
        raise BoundedCSVFallbackError("compatible optional Polars is unavailable")
    with path.open(newline="") as handle:
        header = next(csv.reader(handle), [])
    present = set(header)
    if not header or set(required) - present:
        raise BoundedCSVFallbackError("missing required header")
    defaults = {} if optional_defaults is None else optional_defaults
    selected = tuple(dict.fromkeys(selected_names))
    if set(selected) - present - set(defaults):
        raise BoundedCSVFallbackError("missing selected header")
    positions = {name: index for index, name in enumerate(header)}
    indexes = sorted({positions[name] for name in selected if name in positions})
    schema = {f"_column_{i}": pl.String for i in range(len(header))}
    offset = 0
    for block in _plain_blocks(
        path, CSV_CHUNK_BYTES if chunk_bytes is None else chunk_bytes
    ):
        frame = pl.read_csv(
            block,
            has_header=False,
            schema=schema,
            columns=indexes,
            empty_string_is_null=True,
            row_index_name="__source_row",
            truncate_ragged_lines=truncate_ragged_lines,
            raise_if_empty=False,
        )
        # Keep global ordinals wider than Polars' per-buffer row index.
        frame = frame.with_columns(
            (pl.col("__source_row").cast(pl.UInt64) + offset).alias("__source_row")
        )
        offset += frame.height
        yield (
            frame.select(
                "__source_row",
                *(
                    (
                        pl.col(f"_column_{positions[name]}")
                        if name in positions
                        else pl.lit(defaults[name], dtype=pl.String)
                    ).alias(name)
                    for name in selected
                ),
            ),
            present,
        )
