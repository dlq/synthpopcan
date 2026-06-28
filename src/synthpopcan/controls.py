"""Normalized control table parsing."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from synthpopcan.ipf import IPFMargin

__all__ = [
    "CategoryMapping",
    "ControlCell",
    "ControlMargin",
    "ControlTable",
    "build_wds_category_mapping_template",
    "census_profile_template",
    "inspect_census_profile_characteristics",
    "inspect_wds_zip",
    "read_category_mapping",
    "read_census_profile_control_table",
    "read_census_profile_mapping",
    "read_control_margins",
    "read_control_table",
    "read_wds_control_table",
    "write_control_table",
]


@dataclass
class _MarginGroup:
    dimensions: tuple[str, ...]
    cells: list[ControlCell]
    seen_keys: set[tuple[str, ...]]


@dataclass(frozen=True)
class ControlCell:
    """One target count in a normalized control table.

    Parameters
    ----------
    categories:
        Mapping from dimension names to canonical category values, such as
        ``{"age": "age_025_029", "sex": "female"}``.
    count:
        Target population count for that exact combination of categories.
    """

    categories: dict[str, str]
    count: float


@dataclass(frozen=True)
class ControlMargin:
    """A named collection of target cells over the same dimensions.

    A margin represents one table of constraints, such as age by sex or
    household size by tenure. Every cell in the margin must use the same ordered
    ``dimensions`` so it can be converted into an IPF margin.

    Parameters
    ----------
    name:
        Human-readable margin label used in reports.
    dimensions:
        Ordered dimension names that define each category tuple.
    cells:
        Target cells belonging to this margin.
    """

    name: str
    dimensions: tuple[str, ...]
    cells: tuple[ControlCell, ...]

    def to_ipf_margin(self) -> IPFMargin:
        """Convert this control margin into the IPF margin representation."""

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
    """A normalized set of one or more control margins.

    Control tables are the bridge between source-specific files, such as
    Statistics Canada downloads, and the generic IPF engine. They preserve the
    margins as interpretable objects and can be converted to IPF margins when
    fitting weights.

    Parameters
    ----------
    margins:
        Margins that should be applied to the same synthetic-population
        workflow.
    dimensions:
        Union of the category dimensions used by the margins, in file order.
    """

    margins: tuple[ControlMargin, ...]
    dimensions: tuple[str, ...]

    def to_ipf_margins(self) -> list[IPFMargin]:
        """Convert all margins in this table into IPF margins."""

        return [margin.to_ipf_margin() for margin in self.margins]


CategoryMapping = dict[str, dict[str, str]]
_WDS_METADATA_COLUMNS = {
    "STATUS",
    "SYMBOL",
    "TERMINATED",
    "DECIMALS",
    "SCALAR_FACTOR",
    "VECTOR",
    "COORDINATE",
    "DGUID",
    "UOM",
    "UOM_ID",
}
_CENSUS_PROFILE_AGE5_CATEGORIES = {
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
_CENSUS_PROFILE_SEX_CATEGORIES = {
    "Female": {"sex": "female"},
    "Male": {"sex": "male"},
}


def read_control_table(path: Path) -> ControlTable:
    """Read a normalized controls CSV into a :class:`ControlTable`.

    The CSV must include ``margin``, ``dimensions``, category columns, and
    ``count``. Rows are grouped into margins by the ``margin`` value. The
    ``dimensions`` column is a comma-separated list naming the category columns
    that define a cell.

    Raises
    ------
    ValueError
        If required columns are missing, counts are not numeric, a margin mixes
        dimensions, or a target cell is duplicated.
    """

    grouped: dict[str, _MarginGroup] = {}
    used_dimensions: set[str] = set()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row_number, row in enumerate(reader, start=2):
            dimensions = _parse_dimensions(row.get("dimensions", ""))
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
    """Read a normalized controls CSV and return IPF-ready margins.

    This is a convenience wrapper around :func:`read_control_table` for callers
    that only need the IPF representation.
    """

    return read_control_table(path).to_ipf_margins()


def read_wds_control_table(
    path: Path,
    *,
    dimensions: tuple[str, ...],
    count_column: str,
    margin_name: str,
    category_mapping: CategoryMapping | None = None,
) -> ControlTable:
    """Read a Statistics Canada WDS ZIP as a normalized control table.

    ``dimensions`` and ``count_column`` name columns inside the ZIP's CSV file.
    ``category_mapping`` can translate source labels into seed-data category
    codes before the controls are passed to IPF. The returned table contains one
    margin named by ``margin_name``.

    Raises
    ------
    ValueError
        If the ZIP cannot be interpreted as a WDS table, required columns are
        missing, counts are invalid, or the same target cell appears twice.
    """

    if not dimensions:
        raise ValueError("WDS controls require at least one dimension")
    try:
        archive = ZipFile(path)
    except BadZipFile as exc:
        raise ValueError(f"{path} is not a valid WDS ZIP") from exc
    with archive:
        csv_name = _find_wds_csv_member(archive)
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
                            dimension: _map_category(
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


def inspect_wds_zip(path: Path, *, sample_rows: int = 5) -> dict[str, Any]:
    """Inspect a WDS ZIP and return columns, sample rows, and command hints.

    The result is a plain dictionary suitable for JSON output. It includes the
    selected CSV member, row count, candidate count columns, candidate dimension
    columns, sample rows, and a suggested command-line normalization command.
    """

    if sample_rows < 1:
        raise ValueError("sample rows must be at least 1")
    try:
        archive = ZipFile(path)
    except BadZipFile as exc:
        raise ValueError(f"{path} is not a valid WDS ZIP") from exc
    with archive:
        csv_name = _find_wds_csv_member(archive)
        with archive.open(csv_name) as raw_handle:
            handle = TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows: list[dict[str, str]] = []
            numeric_probe_values = {column: [] for column in columns}
            row_count = 0
            for row in reader:
                row_count += 1
                if len(rows) < sample_rows:
                    rows.append(row)
                for column in columns:
                    value = row.get(column, "")
                    if value and len(numeric_probe_values[column]) < 25:
                        numeric_probe_values[column].append(value)

    value_columns = [column for column in columns if column.upper() == "VALUE"]
    count_candidates = value_columns or [
        column
        for column in columns
        if column.upper() not in _WDS_METADATA_COLUMNS
        and _values_are_numeric(numeric_probe_values[column])
    ]
    dimension_candidates = [
        column
        for column in columns
        if column not in count_candidates
        and column.upper() not in _WDS_METADATA_COLUMNS
    ]
    dimensions_arg = ",".join(dimension_candidates)
    count_column = count_candidates[0] if count_candidates else "VALUE"
    return {
        "csv_member": csv_name,
        "columns": columns,
        "row_count": row_count,
        "count_column_candidates": count_candidates,
        "dimension_candidates": dimension_candidates,
        "sample_rows": rows[:sample_rows],
        "suggested_command": (
            f"synthpopcan controls from-wds {path} "
            f"--dimensions '{dimensions_arg}' "
            f"--count-column {count_column} "
            "--margin-name wds "
            "--out controls.csv"
        ),
    }


def build_wds_category_mapping_template(
    path: Path,
    *,
    dimensions: tuple[str, ...],
    preset: str = "blank",
) -> CategoryMapping:
    """Build a source-to-canonical category mapping template for a WDS ZIP.

    The returned mapping has the shape ``{dimension: {source_label:
    canonical_label}}``. The ``canonical`` preset fills known age and sex
    Census Profile labels where possible; ``blank`` leaves every target empty
    for manual review.
    """

    if not dimensions:
        raise ValueError("WDS mapping template requires at least one dimension")
    if preset not in {"blank", "canonical"}:
        raise ValueError("Unknown WDS mapping preset. Use one of: blank, canonical.")
    categories: dict[str, set[str]] = {dimension: set() for dimension in dimensions}
    try:
        archive = ZipFile(path)
    except BadZipFile as exc:
        raise ValueError(f"{path} is not a valid WDS ZIP") from exc
    with archive:
        csv_name = _find_wds_csv_member(archive)
        with archive.open(csv_name) as raw_handle:
            handle = TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [
                dimension for dimension in dimensions if dimension not in fieldnames
            ]
            if missing:
                raise ValueError(f"WDS CSV is missing columns: {', '.join(missing)}")
            for row in reader:
                for dimension in dimensions:
                    value = row.get(dimension, "")
                    if value:
                        categories[dimension].add(value)

    return {
        dimension: {
            value: _preset_wds_category(dimension, value, preset)
            for value in sorted(values)
        }
        for dimension, values in categories.items()
    }


def _preset_wds_category(dimension: str, value: str, preset: str) -> str:
    if preset == "blank":
        return ""

    dimension_key = dimension.casefold()
    if "age" in dimension_key:
        categories = _CENSUS_PROFILE_AGE5_CATEGORIES.get(value)
        if categories:
            return categories["age"]
    if dimension_key in {"sex", "gender"}:
        categories = _CENSUS_PROFILE_SEX_CATEGORIES.get(value)
        if categories:
            return categories["sex"]
    return ""


def read_census_profile_control_table(
    path: Path,
    mapping_path: Path,
) -> ControlTable:
    """Normalize a Census Profile CSV using a JSON mapping file.

    The mapping file identifies the geography column, characteristic column,
    count column, and one or more margins whose characteristic labels should be
    converted into canonical categories.
    """

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
    """List characteristic labels from a Census Profile CSV.

    This helps users discover the exact source labels needed in a mapping file.
    Each returned dictionary includes the characteristic label, an example
    count, and the number of source rows with that label.
    """

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
    """Return a starter mapping template for common Census Profile margins.

    Supported template names are ``"age5"`` and ``"sex"``. The returned object
    can be written as JSON, reviewed, and passed to
    :func:`read_census_profile_control_table`.
    """

    template_name = name.lower()
    if template_name == "age5":
        margin_name = "age"
        dimensions = [geography_dimension, "age"]
        categories = _CENSUS_PROFILE_AGE5_CATEGORIES
    elif template_name == "sex":
        margin_name = "sex"
        dimensions = [geography_dimension, "sex"]
        categories = _CENSUS_PROFILE_SEX_CATEGORIES
    else:
        raise ValueError("Unknown Census Profile template. Use one of: age5, sex.")
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
    """Read and validate a Census Profile control mapping JSON file.

    The function validates the high-level structure and raises ``ValueError``
    for missing keys before any source CSV is processed.
    """

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


def _find_wds_csv_member(archive: ZipFile) -> str:
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


def _values_are_numeric(values: list[str]) -> bool:
    if not values:
        return False
    for value in values[:25]:
        try:
            float(value)
        except ValueError:
            return False
    return True


def read_category_mapping(path: Path) -> CategoryMapping:
    """Read and validate a WDS category mapping JSON file.

    The mapping must be a JSON object whose values are objects mapping source
    labels to canonical category values.
    """

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


def _map_category(
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
    """Write a :class:`ControlTable` to the normalized controls CSV format.

    The output can be read back with :func:`read_control_table` or used by the
    command-line IPF workflows.
    """

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
                        "count": _format_count(cell.count),
                    }
                )


def _parse_dimensions(value: str) -> tuple[str, ...]:
    separator = "|" if "|" in value else ","
    return tuple(part.strip() for part in value.split(separator) if part.strip())


def _format_count(count: float) -> str:
    rounded = round(count)
    if abs(count - rounded) < 1e-9:
        return str(rounded)
    return f"{count:.12g}"
