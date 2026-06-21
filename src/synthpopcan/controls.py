"""Normalized control table parsing."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

from synthpopcan.ipf import IPFMargin


@dataclass
class _MarginGroup:
    dimensions: tuple[str, ...]
    cells: list[ControlCell]
    seen_keys: set[tuple[str, ...]]


@dataclass(frozen=True)
class ControlCell:
    categories: dict[str, str]
    count: float


@dataclass(frozen=True)
class ControlMargin:
    name: str
    dimensions: tuple[str, ...]
    cells: tuple[ControlCell, ...]

    def to_ipf_margin(self) -> IPFMargin:
        return IPFMargin(
            self.dimensions,
            {
                tuple(
                    cell.categories[dimension] for dimension in self.dimensions
                ): cell.count
                for cell in self.cells
            },
        )


@dataclass(frozen=True)
class ControlTable:
    margins: tuple[ControlMargin, ...]
    dimensions: tuple[str, ...]

    def to_ipf_margins(self) -> list[IPFMargin]:
        return [margin.to_ipf_margin() for margin in self.margins]


def read_control_table(path: Path) -> ControlTable:
    grouped: dict[str, _MarginGroup] = {}
    used_dimensions: set[str] = set()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row_number, row in enumerate(reader, start=2):
            dimensions = parse_dimensions(row.get("dimensions", ""))
            if not dimensions:
                raise ValueError(f"controls row {row_number} has no dimensions")
            try:
                count = float(row["count"])
            except KeyError as exc:
                raise ValueError("controls CSV requires a count column") from exc
            except ValueError as exc:
                raise ValueError(
                    f"controls row {row_number} has invalid count"
                ) from exc

            margin_label = row.get("margin", "").strip()
            margin_key = margin_label or "|".join(dimensions)
            group = grouped.setdefault(margin_key, _MarginGroup(dimensions, [], set()))
            if group.dimensions != dimensions:
                raise ValueError(
                    f"controls row {row_number} margin {margin_label!r} mixes "
                    f"dimensions {group.dimensions!r} and {dimensions!r}"
                )

            key = tuple(row.get(dimension, "") for dimension in dimensions)
            if key in group.seen_keys:
                raise ValueError(
                    f"controls row {row_number} duplicates target {key!r} "
                    f"for dimensions {dimensions!r}"
                )
            group.seen_keys.add(key)
            for dimension in dimensions:
                used_dimensions.add(dimension)
            group.cells.append(
                ControlCell(
                    categories={
                        dimension: row.get(dimension, "") for dimension in dimensions
                    },
                    count=count,
                )
            )

    margins = tuple(
        ControlMargin(name, group.dimensions, tuple(group.cells))
        for name, group in grouped.items()
    )
    table_dimensions = tuple(
        field
        for field in fieldnames
        if field not in {"margin", "dimensions", "count"} and field in used_dimensions
    )
    return ControlTable(margins=margins, dimensions=table_dimensions)


def read_control_margins(path: Path) -> list[IPFMargin]:
    return read_control_table(path).to_ipf_margins()


def read_wds_control_table(
    path: Path,
    *,
    dimensions: tuple[str, ...],
    count_column: str,
    margin_name: str,
) -> ControlTable:
    if not dimensions:
        raise ValueError("WDS controls require at least one dimension")
    with ZipFile(path) as archive:
        csv_name = find_wds_csv_member(archive)
        with archive.open(csv_name) as raw_handle:
            handle = TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(handle)
            cells: list[ControlCell] = []
            seen_keys: set[tuple[str, ...]] = set()
            for row_number, row in enumerate(reader, start=2):
                missing = [
                    column
                    for column in (*dimensions, count_column)
                    if column not in row
                ]
                if missing:
                    raise ValueError(
                        f"WDS row {row_number} is missing columns: {', '.join(missing)}"
                    )
                key = tuple(row[dimension] for dimension in dimensions)
                if key in seen_keys:
                    raise ValueError(
                        f"WDS row {row_number} duplicates target {key!r} "
                        f"for dimensions {dimensions!r}"
                    )
                seen_keys.add(key)
                try:
                    count = float(row[count_column])
                except ValueError as exc:
                    raise ValueError(f"WDS row {row_number} has invalid count") from exc
                cells.append(
                    ControlCell(
                        categories={
                            dimension: row[dimension] for dimension in dimensions
                        },
                        count=count,
                    )
                )

    return ControlTable(
        margins=(ControlMargin(margin_name, dimensions, tuple(cells)),),
        dimensions=dimensions,
    )


def find_wds_csv_member(archive: ZipFile) -> str:
    csv_names = [
        name
        for name in archive.namelist()
        if not name.endswith("/") and name.lower().endswith(".csv")
    ]
    if not csv_names:
        raise ValueError("WDS ZIP does not contain a CSV file")
    if len(csv_names) > 1:
        raise ValueError("WDS ZIP contains multiple CSV files")
    return csv_names[0]


def write_control_table(path: Path, table: ControlTable) -> None:
    fieldnames = ["margin", "dimensions", *table.dimensions, "count"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for margin in table.margins:
            for cell in margin.cells:
                writer.writerow(
                    {
                        "margin": margin.name,
                        "dimensions": ",".join(margin.dimensions),
                        **{
                            dimension: cell.categories.get(dimension, "")
                            for dimension in table.dimensions
                        },
                        "count": format_count(cell.count),
                    }
                )


def parse_dimensions(value: str) -> tuple[str, ...]:
    separator = "|" if "|" in value else ","
    return tuple(part.strip() for part in value.split(separator) if part.strip())


def format_count(count: float) -> str:
    rounded = round(count)
    if abs(count - rounded) < 1e-9:
        return str(rounded)
    return f"{count:.12g}"
