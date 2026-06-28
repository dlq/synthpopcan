"""WDS download and normalization helpers for the local web app."""

from __future__ import annotations
from typing import Any

__all__ = [
    "fetch_wds_zip_bytes",
    "generate_wds_seed_controls_from_zip_bytes",
    "parse_dimensions",
    "resolve_wds_dimensions",
    "suggest_wds_dimensions",
]

import csv
from io import BytesIO, StringIO, TextIOWrapper
from urllib.request import urlopen
from zipfile import ZipFile

from synthpopcan.statcan import fetch_json, wds_download_url

_WDS_METADATA_COLUMNS = {
    "STATUS",
    "SYMBOL",
    "TERMINATED",
    "DECIMALS",
    "SCALAR_FACTOR",
    "SCALAR_ID",
    "VECTOR",
    "COORDINATE",
    "DGUID",
    "UOM",
    "UOM_ID",
}
_WDS_FETCH_TIMEOUT_SECONDS = 30
WdsRow = tuple[int, dict[str, str]]


def fetch_wds_zip_bytes(product_id: str, lang: str = "en") -> tuple[bytes, str]:
    """Fetch a StatCan WDS ZIP through Python to avoid browser CORS limits."""
    source_url = wds_download_url(product_id, lang)
    response = fetch_json(source_url)
    if response.get("status") != "SUCCESS" or not response.get("object"):
        raise ValueError(f"StatCan WDS did not return a download URL for {product_id}")
    download_url = str(response["object"])
    with urlopen(download_url, timeout=_WDS_FETCH_TIMEOUT_SECONDS) as handle:
        return handle.read(), download_url


def generate_wds_seed_controls_from_zip_bytes(
    zip_bytes: bytes,
    *,
    dimensions: tuple[str, ...],
    count_column: str,
) -> dict[str, Any]:
    """Normalize a WDS ZIP into browser-ready seed and control CSV strings."""
    with ZipFile(BytesIO(zip_bytes)) as archive:
        csv_member = _choose_wds_data_csv_member(archive)
        with archive.open(csv_member) as raw_handle:
            handle = TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
            rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("WDS table has no rows")
    numbered_rows = list(enumerate(rows, start=2))
    resolved_dimensions = resolve_wds_dimensions(rows, dimensions)
    if not resolved_dimensions:
        resolved_dimensions = suggest_wds_dimensions(rows, count_column)
    snapshot_rows, reference_period = _snapshot_wds_rows(
        numbered_rows, resolved_dimensions
    )
    control_rows = _normalize_wds_rows(
        snapshot_rows,
        dimensions=resolved_dimensions,
        count_column=count_column,
    )
    seed_rows = _build_seed_rows(control_rows)
    return {
        "csvMember": csv_member,
        "referencePeriod": reference_period,
        "dimensions": list(resolved_dimensions),
        "countColumn": count_column,
        "seedRows": len(seed_rows),
        "controlRows": len(control_rows),
        "seedCsv": _write_csv(seed_rows),
        "controlsCsv": _write_csv(control_rows),
    }


def _choose_wds_data_csv_member(archive: ZipFile) -> str:
    csv_names = [
        name
        for name in archive.namelist()
        if not name.endswith("/") and name.lower().endswith(".csv")
    ]
    data_names = [name for name in csv_names if "metadata" not in name.lower()]
    selected = data_names[0] if data_names else (csv_names[0] if csv_names else None)
    if selected is None:
        raise ValueError("WDS ZIP does not contain a CSV file")
    return selected


def parse_dimensions(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        items = value.replace("|", ",").split(",")
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    return tuple(item.strip() for item in items if item.strip())


def resolve_wds_dimensions(
    rows: list[dict[str, str]], dimensions: tuple[str, ...]
) -> tuple[str, ...]:
    columns = list(rows[0])
    columns_by_lower = {column.lower(): column for column in columns}
    resolved: list[str] = []
    for dimension in dimensions:
        if dimension in columns:
            resolved.append(dimension)
        elif dimension.lower() == "geography" and "GEO" in columns:
            resolved.append("GEO")
        else:
            resolved.append(columns_by_lower.get(dimension.lower(), dimension))
    return tuple(resolved)


def suggest_wds_dimensions(
    rows: list[dict[str, str]], count_column: str
) -> tuple[str, ...]:
    return tuple(
        column
        for column in rows[0]
        if column != count_column
        and column != "REF_DATE"
        and column.upper() not in _WDS_METADATA_COLUMNS
    )


def _snapshot_wds_rows(
    rows: list[WdsRow], dimensions: tuple[str, ...]
) -> tuple[list[WdsRow], str | None]:
    first_row = rows[0][1]
    if "REF_DATE" not in first_row or "REF_DATE" in dimensions:
        return rows, None
    reference_periods = sorted(
        {row["REF_DATE"] for _, row in rows if row.get("REF_DATE")},
        key=_reference_period_sort_key,
    )
    if not reference_periods:
        return rows, None
    reference_period = reference_periods[-1]
    snapshot_rows = [
        (row_number, row)
        for row_number, row in rows
        if row.get("REF_DATE") == reference_period
    ]
    return snapshot_rows, reference_period


def _reference_period_sort_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def _normalize_wds_rows(
    rows: list[WdsRow], *, dimensions: tuple[str, ...], count_column: str
) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    control_rows: list[dict[str, str]] = []
    for row_number, row in rows:
        if row.get(count_column, "") == "":
            continue
        missing = [
            column for column in (*dimensions, count_column) if column not in row
        ]
        if missing:
            raise ValueError(
                f"WDS row {row_number} is missing columns: {', '.join(missing)}"
            )
        key = tuple(row[dimension] for dimension in dimensions)
        if key in seen:
            raise ValueError(f"WDS row {row_number} duplicates control cell {key!r}")
        seen.add(key)
        try:
            count = float(row[count_column])
        except ValueError as exc:
            raise ValueError(f"WDS row {row_number} has invalid count") from exc
        control_rows.append(
            {
                "margin": "wds",
                "dimensions": ",".join(dimensions),
                **{dimension: row[dimension] for dimension in dimensions},
                "count": _format_count(count),
            }
        )
    return control_rows


def _build_seed_rows(control_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    seed_rows: list[dict[str, str]] = []
    for row in control_rows:
        dimensions = parse_dimensions(row["dimensions"])
        values = {dimension: row.get(dimension, "") for dimension in dimensions}
        key = tuple(values.items())
        if key not in seen:
            seen.add(key)
            seed_rows.append({"id": f"seed-{len(seed_rows) + 1}", **values})
    return seed_rows


def _write_csv(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def _format_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
