"""Build IPF control tables from StatCan Census Profile CSVs."""

from __future__ import annotations

__all__ = [
    "extract_controls_from_profile",
    "recode_household_size",
    "scale_and_validate_controls",
    "write_controls_csv",
    "write_recoded_candidates",
]

import csv
from collections import defaultdict
from collections.abc import Sequence
from itertools import chain
from pathlib import Path

# Member IDs are consistent across 2016 Census Profiles (2247-variable form).
_HHSIZE_MEMBERS: dict[str, str] = {
    "52": "1",  # 1 person
    "53": "2",  # 2 persons
    "54": "3",  # 3 persons
    "55": "4",  # 4 persons
    "56": "5",  # 5 or more persons
}
_TENURE_MEMBERS: dict[str, str] = {
    "1618": "1",  # Owner
    "1619": "2",  # Renter
    "1620": "2",  # Band housing (combined with renter in the hierarchical PUMF)
}

# The 2021 profile renamed the member-id column and revised characteristic IDs.
_HHSIZE_MEMBERS_2021: dict[str, str] = {
    "51": "1",
    "52": "2",
    "53": "3",
    "54": "4",
    "55": "5",
}
_TENURE_MEMBERS_2021: dict[str, str] = {
    "1415": "1",
    "1416": "2",
    "1417": "2",  # Local government / First Nation / Indian band dwelling
}

# GEO_LEVEL value in each census profile that identifies the target geography rows.
_GEO_LEVEL_FOR_COLUMN: dict[str, str] = {
    "ada": "3",
    "ct": "2",
    "csd": "3",
    "cd": "2",
    "da": "4",
}
_GEO_LEVEL_FOR_COLUMN_2021: dict[str, str] = {
    "ada": "Aggregate dissemination area",
    "ct": "Census tract",
    "csd": "Census subdivision",
    "cd": "Census division",
    "da": "Dissemination area",
}


def _find_col(fields: Sequence[str], fragment: str) -> str:
    try:
        return next(c for c in fields if fragment in c)
    except StopIteration as err:
        raise ValueError(
            f"Could not find a column containing {fragment!r}. "
            f"Available columns: {fields}"
        ) from err


def extract_controls_from_profile(
    profile_path: Path,
    geography_column: str,
    *,
    geo_prefix: str | None = None,
    geo_ids: set[str] | None = None,
    geo_level_value: str | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """Read a StatCan Census Profile CSV and return raw hhsize + tenure counts.

    Parameters
    ----------
    profile_path:
        Path to the Census Profile bulk CSV (2247-variable form, e.g. the ADA
        or CT profile fetched with ``synthpopcan statcan census-profile fetch``).
    geography_column:
        Target geography type: ``"ada"``, ``"ct"``, etc.  Determines which
        GEO_LEVEL rows to read.
    geo_prefix:
        Optional prefix to filter geo codes (e.g. ``"35"`` for Ontario ADAs,
        ``"462"`` for Montreal CTs).  When omitted all geographies are included.
    geo_ids:
        Optional exact identifier set for bounded, reviewed selections. This
        may be combined with ``geo_prefix``; both filters must then match.
    geo_level_value:
        Override the GEO_LEVEL filter value.  Inferred from *geography_column*
        when not provided.

    Returns
    -------
    dict
        ``{geo_id: {"hhsize": {cat: count}, "tenure": {cat: count}}}``
    """
    data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"hhsize": {}, "tenure": {}}
    )

    # StatCan profile ZIPs use a legacy single-byte encoding in both vintages;
    # 2021 geography names can contain bytes that are not valid UTF-8.
    with profile_path.open(newline="", encoding="latin-1") as fh:
        header_line = fh.readline()
        raw_fields = next(csv.reader([header_line]), [])
        is_2021 = "CHARACTERISTIC_ID" in raw_fields
        if is_2021 and geo_ids is not None:
            # The official 2021 bulk profile is many gigabytes. Its first three
            # fields are fixed and comma-free (year, DGUID, ALT_GEO_CODE), so
            # discard unselected geography rows before constructing dictionaries.
            selected_lines = (
                line
                for line in fh
                if len(parts := line.split(",", 3)) >= 3
                and parts[2].strip().strip('"') in geo_ids
            )
            reader = csv.DictReader(chain((header_line,), selected_lines))
        else:
            reader = csv.DictReader(chain((header_line,), fh))
        if is_2021:
            mem_col = "CHARACTERISTIC_ID"
            val_col = "C1_COUNT_TOTAL"
            geo_col = "ALT_GEO_CODE"
            hhsize_members = _HHSIZE_MEMBERS_2021
            tenure_members = _TENURE_MEMBERS_2021
            levels = _GEO_LEVEL_FOR_COLUMN_2021
        else:
            # Locate 2016 columns by partial match across ADA, CT, and DA files.
            mem_col = _find_col(raw_fields, "Member ID: Profile")
            val_col = _find_col(raw_fields, "[1]: Total")
            geo_col = _find_col(raw_fields, "GEO_CODE")
            hhsize_members = _HHSIZE_MEMBERS
            tenure_members = _TENURE_MEMBERS
            levels = _GEO_LEVEL_FOR_COLUMN

        target_level = geo_level_value or levels.get(geography_column.lower())
        if target_level is None:
            raise ValueError(
                f"Unknown geography column {geography_column!r}. "
                f"Known values: {sorted(levels)}. "
                "Use --geo-level-value to provide the GEO_LEVEL string explicitly."
            )

        for row in reader:
            if row.get("GEO_LEVEL", "").strip() != target_level:
                continue
            geo = row[geo_col].strip()
            if geo_prefix and not geo.startswith(geo_prefix):
                continue
            if geo_ids is not None and geo not in geo_ids:
                continue
            mid = row[mem_col].strip()
            raw = row[val_col].strip().replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            if mid in hhsize_members:
                data[geo]["hhsize"][hhsize_members[mid]] = val
            elif mid in tenure_members:
                category = tenure_members[mid]
                data[geo]["tenure"][category] = (
                    data[geo]["tenure"].get(category, 0.0) + val
                )

    return dict(data)


def scale_and_validate_controls(
    raw: dict[str, dict[str, dict[str, float]]],
    target_total: int,
) -> tuple[dict[str, dict[str, dict[str, int]]], list[str]]:
    """Scale raw counts to *target_total* and return (scaled, dropped_geos).

    Geographies missing either margin (hhsize or tenure) or with all-zero totals
    are dropped and reported so the caller can warn the user.
    """
    complete = {
        geo: d
        for geo, d in raw.items()
        if d.get("hhsize")
        and sum(d["hhsize"].values()) > 0
        and d.get("tenure")
        and sum(d["tenure"].values()) > 0
    }
    dropped = [g for g in raw if g not in complete]

    hhsize_grand = sum(sum(d["hhsize"].values()) for d in complete.values())
    if hhsize_grand == 0:
        raise ValueError("No household-size totals found in profile data.")
    if target_total < 0:
        raise ValueError("target total must be non-negative")

    household_keys = [
        (geo, category)
        for geo in sorted(complete)
        for category in sorted(complete[geo]["hhsize"])
    ]
    household_allocations = _allocate_integer_counts(
        [complete[geo]["hhsize"][category] for geo, category in household_keys],
        target_total,
    )
    allocated_households = dict(zip(household_keys, household_allocations, strict=True))

    scaled: dict[str, dict[str, dict[str, int]]] = {}
    for geo in sorted(complete):
        hhsize_cats = complete[geo]["hhsize"]
        hhsize_scaled = {
            category: allocated_households[(geo, category)]
            for category in sorted(hhsize_cats)
        }
        hhsize_total = sum(hhsize_scaled.values())

        tenure_cats = complete[geo]["tenure"]
        tenure_keys = sorted(tenure_cats)
        tenure_allocations = _allocate_integer_counts(
            [tenure_cats[category] for category in tenure_keys], hhsize_total
        )
        tenure_scaled = dict(zip(tenure_keys, tenure_allocations, strict=True))

        scaled[geo] = {"hhsize": hhsize_scaled, "tenure": tenure_scaled}

    return scaled, dropped


def _allocate_integer_counts(values: list[float], target_total: int) -> list[int]:
    """Allocate an exact integer total proportionally with deterministic ties."""

    if not values:
        return []
    source_total = sum(values)
    if source_total <= 0:
        raise ValueError("control values must have a positive total")
    exact = [value * target_total / source_total for value in values]
    allocated = [int(value) for value in exact]
    remaining = target_total - sum(allocated)
    order = sorted(
        range(len(values)),
        key=lambda index: (-(exact[index] - allocated[index]), index),
    )
    for index in order[:remaining]:
        allocated[index] += 1
    return allocated


def write_controls_csv(
    scaled: dict[str, dict[str, dict[str, int]]],
    out_path: Path,
    geography_column: str,
    *,
    household_size_column: str = "household_size",
) -> None:
    """Write a long-format controls CSV consumable by ``geo calibrate``."""
    geo_col = geography_column
    fieldnames = [
        "margin",
        "dimensions",
        geo_col,
        "TENUR",
        household_size_column,
        "count",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for geo in sorted(scaled):
            for cat, count in sorted(scaled[geo].get("tenure", {}).items()):
                writer.writerow(
                    {
                        "margin": f"{geo_col} tenure",
                        "dimensions": f"{geo_col},TENUR",
                        geo_col: geo,
                        "TENUR": cat,
                        household_size_column: "",
                        "count": count,
                    }
                )
            for cat, count in sorted(scaled[geo].get("hhsize", {}).items()):
                writer.writerow(
                    {
                        "margin": f"{geo_col} hhsize",
                        "dimensions": f"{geo_col},{household_size_column}",
                        geo_col: geo,
                        "TENUR": "",
                        household_size_column: cat,
                        "count": count,
                    }
                )


def recode_household_size(value: str, *, cap: int = 5) -> str:
    """Return the Census-style household-size group for an exact size value.

    Canadian Census Profile household-size controls commonly publish exact
    categories for one through four people, then a single ``5 or more`` bucket.
    SynthPopCan stores that grouped bucket as ``"5"`` so it fits the member IDs
    used by the 2016 Census Profile bulk files.
    """
    try:
        size = int(value)
    except ValueError:
        return value
    return str(min(size, cap))


def write_recoded_candidates(
    candidates_path: Path,
    out_path: Path,
    *,
    hhsize_col: str = "household_size",
    group_col: str = "household_size_group",
    cap: int = 5,
) -> int:
    """Copy candidates with a Census-style household-size group column.

    The exact household size is preserved unless ``group_col`` is the same as
    ``hhsize_col``.  That explicit overwrite mode is kept for old workflows,
    but new Census Profile controls should use ``household_size_group``.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with candidates_path.open(newline="") as src, out_path.open("w", newline="") as dst:
        reader = csv.DictReader(src)
        assert reader.fieldnames, "empty candidates file"
        fieldnames = list(reader.fieldnames)
        if group_col not in fieldnames:
            fieldnames.append(group_col)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            if hhsize_col in row:
                row[group_col] = recode_household_size(row[hhsize_col], cap=cap)
            writer.writerow(row)
            n += 1
    return n
