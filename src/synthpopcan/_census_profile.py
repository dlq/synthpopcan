"""Internal Census Profile layout detection and row projection.

The public control readers intentionally retain their different policies for
invalid counts and incomplete vectors.  This module owns only the common CSV
schema and row mechanics so those policies cannot drift with the two StatCan
bulk-profile layouts.
"""

from __future__ import annotations

import csv
from collections.abc import Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import cast

GEO_LEVELS_2016: dict[str, str] = {
    "ada": "3",
    "ct": "2",
    "csd": "3",
    "cd": "2",
    "da": "4",
}
GEO_LEVELS_2021: dict[str, str] = {
    "ada": "Aggregate dissemination area",
    "ct": "Census tract",
    "csd": "Census subdivision",
    "cd": "Census division",
    "da": "Dissemination area",
}
GEO_LEVELS_2021_FR: dict[str, str] = {
    "ada": "Aire de diffusion agrégée",
    "ct": "Secteur de recensement",
    "csd": "Subdivision de recensement",
    "cd": "Division de recensement",
    "da": "Aire de diffusion",
}


def find_column(fields: Sequence[str], fragment: str) -> str:
    """Return the first header containing *fragment*, preserving legacy errors."""

    try:
        return next(column for column in fields if fragment in column)
    except StopIteration as error:
        raise ValueError(
            f"Could not find a column containing {fragment!r}. "
            f"Available columns: {fields}"
        ) from error


@dataclass(frozen=True)
class CensusProfileLayout:
    """Columns and optional vintage metadata for one Census Profile CSV."""

    geography_column: str | None
    characteristic_column: str
    count_column: str
    geography_level_column: str | None = None
    census_vintage: int | None = None
    geography_levels: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def statcan_bulk(cls, fields: Sequence[str]) -> CensusProfileLayout:
        """Detect the supported 2016 or 2021 StatCan bulk-profile layout."""

        if set(fields).intersection({"ID_CARACTÉRISTIQUE", "NIVEAU_GÉO"}):
            return _french_profile_layout(fields)
        return _english_profile_layout(fields)

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Columns projected into every row, in user-facing error order."""

        columns = (
            self.geography_column,
            self.characteristic_column,
            self.count_column,
        )
        return tuple(column for column in columns if column is not None)


def _english_profile_layout(fields: Sequence[str]) -> CensusProfileLayout:
    if "CHARACTERISTIC_ID" in fields:
        return CensusProfileLayout(
            geography_column="ALT_GEO_CODE",
            characteristic_column="CHARACTERISTIC_ID",
            count_column="C1_COUNT_TOTAL",
            geography_level_column="GEO_LEVEL",
            census_vintage=2021,
            geography_levels=GEO_LEVELS_2021,
        )
    # Preserve the historic discovery order and associated diagnostics.
    characteristic_column = find_column(fields, "Member ID: Profile")
    count_column = find_column(fields, "[1]: Total")
    geography_column = find_column(fields, "GEO_CODE")
    return CensusProfileLayout(
        geography_column=geography_column,
        characteristic_column=characteristic_column,
        count_column=count_column,
        geography_level_column="GEO_LEVEL",
        census_vintage=2016,
        geography_levels=GEO_LEVELS_2016,
    )


def _french_profile_layout(fields: Sequence[str]) -> CensusProfileLayout:
    if "CHARACTERISTIC_ID" in fields or any(
        "Member ID: Profile" in column for column in fields
    ):
        raise ValueError("Census Profile mixes French and English columns")
    if "ID_CARACTÉRISTIQUE" in fields:
        return CensusProfileLayout(
            geography_column="CODE_GÉO_ALT",
            characteristic_column="ID_CARACTÉRISTIQUE",
            count_column="C1_CHIFFRE_TOTAL",
            geography_level_column="NIVEAU_GÉO",
            census_vintage=2021,
            geography_levels=GEO_LEVELS_2021_FR,
        )
    return CensusProfileLayout(
        geography_column=find_column(fields, "CODE_GÉO (LDR)"),
        characteristic_column=find_column(fields, "Membre ID: Profil"),
        count_column=find_column(fields, "[1]: Total - Sexe"),
        geography_level_column="NIVEAU_GÉO",
        census_vintage=2016,
        geography_levels=GEO_LEVELS_2016,
    )


@dataclass(frozen=True)
class CensusProfileRow:
    """One Profile row projected through a :class:`CensusProfileLayout`."""

    row_number: int
    geography: str | None
    characteristic: str
    count: str
    geography_level: str | None

    @property
    def normalized_geography(self) -> str:
        """Return the whitespace-normalized geography identifier."""

        return cast(str, self.geography).strip()

    @property
    def normalized_characteristic(self) -> str:
        """Return the whitespace-normalized characteristic identifier."""

        return self.characteristic.strip()

    @property
    def normalized_count(self) -> str:
        """Return the Profile count with whitespace and thousands commas removed."""

        return self.count.strip().replace(",", "")

    def matches_geography(
        self,
        *,
        level: str,
        prefix: str | None,
        identifiers: set[str] | None,
    ) -> bool:
        """Return whether this row belongs to the requested geography selection."""

        if cast(str, self.geography_level).strip() != level:
            return False
        geography = self.normalized_geography
        if prefix and not geography.startswith(prefix):
            return False
        return identifiers is None or geography in identifiers


@contextmanager
def open_census_profile_rows(
    path: Path,
    *,
    layout: CensusProfileLayout | None = None,
    encoding: str | None = None,
    selected_geography_ids: set[str] | None = None,
    validate_required_columns: bool = False,
) -> Generator[
    tuple[CensusProfileLayout, Iterator[CensusProfileRow]],
    None,
    None,
]:
    """Open *path* and yield its resolved layout plus projected rows.

    When no layout is supplied, the StatCan bulk schema is detected from the
    header.  Exact 2021 geography selections retain the early line filter used
    to avoid materializing dictionaries for multi-gigabyte unselected rows.
    """

    with path.open("rb") as binary:
        bom = binary.read(3) == b"\xef\xbb\xbf"
    with path.open(newline="", encoding="utf-8-sig" if bom else encoding) as handle:
        header_line = handle.readline()
        fields = next(csv.reader([header_line]), [])
        resolved = layout or CensusProfileLayout.statcan_bulk(fields)
        lines = handle
        if (
            resolved.census_vintage == 2021
            and resolved.geography_column in {"ALT_GEO_CODE", "CODE_GÉO_ALT"}
            and selected_geography_ids is not None
        ):
            # Official 2021 files start with three fixed, comma-free fields:
            # year, DGUID, and ALT_GEO_CODE.  Filter before DictReader creates
            # a mapping for each otherwise-unselected row.
            lines = (
                line
                for line in handle
                if len(parts := line.split(",", 3)) >= 3
                and parts[2].strip().strip('"') in selected_geography_ids
            )
        reader = csv.reader(chain((header_line,), lines))
        next(reader, None)
        yield (
            resolved,
            _project_rows(
                reader,
                resolved,
                fields=fields,
                validate_required_columns=validate_required_columns,
            ),
        )


def _project_rows(
    reader: Iterator[list[str]],
    layout: CensusProfileLayout,
    *,
    fields: Sequence[str],
    validate_required_columns: bool,
) -> Iterator[CensusProfileRow]:
    positions = {column: index for index, column in enumerate(fields)}
    for row_number, values in enumerate(reader, start=2):
        row = dict(zip(fields, values, strict=False))
        missing = [column for column in layout.required_columns if column not in row]
        if missing and validate_required_columns:
            raise ValueError(
                f"Census Profile row {row_number} is missing columns: "
                f"{', '.join(missing)}"
            )
        geography = (
            None
            if layout.geography_column is None
            else cast(str, row[layout.geography_column])
        )
        geography_level = (
            None
            if layout.geography_level_column is None
            else row.get(layout.geography_level_column, "")
        )
        count = _profile_count(row, values, fields, positions, layout)
        yield CensusProfileRow(
            row_number=row_number,
            geography=geography,
            characteristic=cast(str, row[layout.characteristic_column]),
            count=count,
            geography_level=cast(str | None, geography_level),
        )


def _profile_count(row, values, fields, positions, layout):
    count = cast(str, row[layout.count_column])
    index = positions.get(layout.count_column, -1) + 1
    if (
        layout.census_vintage == 2021
        and 0 < index < min(len(fields), len(values))
        and fields[index] in {"SYMBOL", "SYMBOLE"}
        and values[index].strip()
    ):
        return ""
    return count
