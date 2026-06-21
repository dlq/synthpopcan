"""Normalized control table parsing."""

from __future__ import annotations

import csv
import json
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


CategoryMapping = dict[str, dict[str, str]]
CENSUS_PROFILE_AGE5_CATEGORIES = {
    "0 to 4 years": {"age": "age_000_004"},
    "5 to 9 years": {"age": "age_005_009"},
    "10 to 14 years": {"age": "age_010_014"},
    "15 to 19 years": {"age": "age_015_019"},
    "20 to 24 years": {"age": "age_020_024"},
    "25 to 29 years": {"age": "age_025_029"},
    "30 to 34 years": {"age": "age_030_034"},
    "35 to 39 years": {"age": "age_035_039"},
    "40 to 44 years": {"age": "age_040_044"},
    "45 to 49 years": {"age": "age_045_049"},
    "50 to 54 years": {"age": "age_050_054"},
    "55 to 59 years": {"age": "age_055_059"},
    "60 to 64 years": {"age": "age_060_064"},
    "65 to 69 years": {"age": "age_065_069"},
    "70 to 74 years": {"age": "age_070_074"},
    "75 to 79 years": {"age": "age_075_079"},
    "80 to 84 years": {"age": "age_080_084"},
    "85 years and over": {"age": "age_085_plus"},
}
CENSUS_PROFILE_SEX_CATEGORIES = {
    "Female": {"sex": "female"},
    "Male": {"sex": "male"},
}


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
    category_mapping: CategoryMapping | None = None,
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
                            dimension: map_category(
                                dimension,
                                row[dimension],
                                category_mapping,
                                row_number,
                            )
                            for dimension in dimensions
                        },
                        count=count,
                    )
                )

    return ControlTable(
        margins=(ControlMargin(margin_name, dimensions, tuple(cells)),),
        dimensions=dimensions,
    )


def read_census_profile_control_table(
    path: Path,
    mapping_path: Path,
) -> ControlTable:
    mapping = read_census_profile_mapping(mapping_path)
    geography = mapping["geography"]
    geography_column = geography["column"]
    geography_dimension = geography["dimension"]
    characteristic_column = mapping["characteristic_column"]
    count_column = mapping["count_column"]
    margin_specs = mapping["margins"]

    cells_by_margin: dict[str, list[ControlCell]] = {
        margin["name"]: [] for margin in margin_specs
    }
    dimensions_by_margin: dict[str, tuple[str, ...]] = {
        margin["name"]: tuple(margin["dimensions"]) for margin in margin_specs
    }
    seen_by_margin: dict[str, set[tuple[str, ...]]] = {
        margin["name"]: set() for margin in margin_specs
    }
    used_dimensions: list[str] = []

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            missing = [
                column
                for column in (geography_column, characteristic_column, count_column)
                if column not in row
            ]
            if missing:
                raise ValueError(
                    f"Census Profile row {row_number} is missing columns: "
                    f"{', '.join(missing)}"
                )
            characteristic = row[characteristic_column]
            for margin in margin_specs:
                categories_by_label = margin["categories"]
                if characteristic not in categories_by_label:
                    continue
                categories = {
                    geography_dimension: row[geography_column],
                    **categories_by_label[characteristic],
                }
                dimensions = tuple(margin["dimensions"])
                key = tuple(categories.get(dimension, "") for dimension in dimensions)
                if key in seen_by_margin[margin["name"]]:
                    raise ValueError(
                        f"Census Profile row {row_number} duplicates target {key!r} "
                        f"for dimensions {dimensions!r}"
                    )
                seen_by_margin[margin["name"]].add(key)
                try:
                    count = float(row[count_column])
                except ValueError as exc:
                    raise ValueError(
                        f"Census Profile row {row_number} has invalid count"
                    ) from exc
                cells_by_margin[margin["name"]].append(ControlCell(categories, count))
                for dimension in dimensions:
                    if dimension not in used_dimensions:
                        used_dimensions.append(dimension)

    margins = tuple(
        ControlMargin(name, dimensions_by_margin[name], tuple(cells))
        for name, cells in cells_by_margin.items()
    )
    return ControlTable(margins=margins, dimensions=tuple(used_dimensions))


def inspect_census_profile_characteristics(
    path: Path,
    *,
    characteristic_column: str = "CHARACTERISTIC_NAME",
    count_column: str = "C1_COUNT_TOTAL",
    search: str | None = None,
    limit: int = 25,
) -> list[dict[str, str]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    search_term = search.lower() if search else None
    rows_by_characteristic: dict[str, dict[str, str]] = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            missing = [
                column
                for column in (characteristic_column, count_column)
                if column not in row
            ]
            if missing:
                raise ValueError(
                    f"Census Profile row {row_number} is missing columns: "
                    f"{', '.join(missing)}"
                )
            characteristic = row[characteristic_column]
            if search_term and search_term not in characteristic.lower():
                continue
            if characteristic not in rows_by_characteristic:
                rows_by_characteristic[characteristic] = {
                    "characteristic": characteristic,
                    "example_count": row[count_column],
                    "rows": "0",
                }
            current = rows_by_characteristic[characteristic]
            current["rows"] = str(int(current["rows"]) + 1)
    return list(rows_by_characteristic.values())[:limit]


def census_profile_template(
    name: str,
    *,
    geography_column: str = "GEO_CODE",
    geography_dimension: str = "geo",
    characteristic_column: str = "CHARACTERISTIC_NAME",
    count_column: str = "C1_COUNT_TOTAL",
) -> dict:
    template_name = name.lower()
    if template_name == "age5":
        margin_name = "age"
        dimensions = [geography_dimension, "age"]
        categories = CENSUS_PROFILE_AGE5_CATEGORIES
    elif template_name == "sex":
        margin_name = "sex"
        dimensions = [geography_dimension, "sex"]
        categories = CENSUS_PROFILE_SEX_CATEGORIES
    else:
        raise ValueError("known Census Profile templates: age5, sex")
    return {
        "geography": {"column": geography_column, "dimension": geography_dimension},
        "characteristic_column": characteristic_column,
        "count_column": count_column,
        "margins": [
            {
                "name": margin_name,
                "dimensions": dimensions,
                "categories": categories,
            }
        ],
    }


def read_census_profile_mapping(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Census Profile mapping must be a JSON object")
    try:
        geography = payload["geography"]
        characteristic_column = payload["characteristic_column"]
        count_column = payload["count_column"]
        margins = payload["margins"]
    except KeyError as exc:
        raise ValueError(f"Census Profile mapping is missing {exc.args[0]!r}") from exc
    if not isinstance(geography, dict):
        raise ValueError("Census Profile mapping geography must be an object")
    if not isinstance(characteristic_column, str) or not isinstance(count_column, str):
        raise ValueError(
            "Census Profile mapping characteristic_column and count_column "
            "must be strings"
        )
    if not isinstance(margins, list) or not margins:
        raise ValueError("Census Profile mapping margins must be a non-empty list")
    try:
        geography_column = geography["column"]
        geography_dimension = geography["dimension"]
    except KeyError as exc:
        raise ValueError(
            f"Census Profile mapping geography is missing {exc.args[0]!r}"
        ) from exc
    if not isinstance(geography_column, str) or not isinstance(
        geography_dimension, str
    ):
        raise ValueError(
            "Census Profile mapping geography column and dimension must be strings"
        )

    normalized_margins = []
    for index, margin in enumerate(margins, start=1):
        if not isinstance(margin, dict):
            raise ValueError(f"Census Profile mapping margin {index} must be an object")
        try:
            name = margin["name"]
            dimensions = margin["dimensions"]
            categories = margin["categories"]
        except KeyError as exc:
            raise ValueError(
                f"Census Profile mapping margin {index} is missing {exc.args[0]!r}"
            ) from exc
        if not isinstance(name, str):
            raise ValueError(f"Census Profile mapping margin {index} name must be text")
        if not isinstance(dimensions, list) or not all(
            isinstance(dimension, str) for dimension in dimensions
        ):
            raise ValueError(
                f"Census Profile mapping margin {index} dimensions must be text"
            )
        if not isinstance(categories, dict):
            raise ValueError(
                f"Census Profile mapping margin {index} categories must be an object"
            )
        normalized_categories = {}
        for source_label, mapped_categories in categories.items():
            if not isinstance(source_label, str) or not isinstance(
                mapped_categories, dict
            ):
                raise ValueError(
                    f"Census Profile mapping margin {index} categories must map "
                    "source labels to objects"
                )
            normalized_categories[source_label] = {
                dimension: value
                for dimension, value in mapped_categories.items()
                if isinstance(dimension, str) and isinstance(value, str)
            }
        normalized_margins.append(
            {
                "name": name,
                "dimensions": dimensions,
                "categories": normalized_categories,
            }
        )
    return {
        "geography": {"column": geography_column, "dimension": geography_dimension},
        "characteristic_column": characteristic_column,
        "count_column": count_column,
        "margins": normalized_margins,
    }


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


def read_category_mapping(path: Path) -> CategoryMapping:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("category mapping must be a JSON object")

    mapping: CategoryMapping = {}
    for dimension, values in payload.items():
        if not isinstance(dimension, str) or not isinstance(values, dict):
            raise ValueError("category mapping must map dimension names to objects")
        mapping[dimension] = {}
        for source, target in values.items():
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("category mapping values must be strings")
            mapping[dimension][source] = target
    return mapping


def map_category(
    dimension: str,
    value: str,
    category_mapping: CategoryMapping | None,
    row_number: int,
) -> str:
    if category_mapping is None or dimension not in category_mapping:
        return value
    try:
        return category_mapping[dimension][value]
    except KeyError as exc:
        raise ValueError(
            f"WDS row {row_number} has unmapped category {value!r} "
            f"for dimension {dimension!r}"
        ) from exc


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
