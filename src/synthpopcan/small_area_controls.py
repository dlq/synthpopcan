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
}

# GEO_LEVEL value in each census profile that identifies the target geography rows.
_GEO_LEVEL_FOR_COLUMN: dict[str, str] = {
    "ada": "3",
    "ct": "2",
    "csd": "3",
    "cd": "2",
    "da": "4",
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
    geo_level_value:
        Override the GEO_LEVEL filter value.  Inferred from *geography_column*
        when not provided.

    Returns
    -------
    dict
        ``{geo_id: {"hhsize": {cat: count}, "tenure": {cat: count}}}``
    """
    target_level = geo_level_value or _GEO_LEVEL_FOR_COLUMN.get(
        geography_column.lower()
    )
    if target_level is None:
        raise ValueError(
            f"Unknown geography column {geography_column!r}. "
            f"Known values: {sorted(_GEO_LEVEL_FOR_COLUMN)}. "
            "Use --geo-level-value to provide the GEO_LEVEL string explicitly."
        )

    data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"hhsize": {}, "tenure": {}}
    )

    with profile_path.open(newline="", encoding="latin-1") as fh:
        reader = csv.DictReader(fh)

        # Locate key columns by partial match (works across ADA, CT, DA profiles)
        raw_fields = reader.fieldnames or []
        mem_col = _find_col(raw_fields, "Member ID: Profile")
        val_col = _find_col(raw_fields, "[1]: Total")
        geo_col = _find_col(raw_fields, "GEO_CODE")

        for row in reader:
            if row.get("GEO_LEVEL", "").strip() != target_level:
                continue
            geo = row[geo_col].strip()
            if geo_prefix and not geo.startswith(geo_prefix):
                continue
            mid = row[mem_col].strip()
            raw = row[val_col].strip().replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            if mid in _HHSIZE_MEMBERS:
                data[geo]["hhsize"][_HHSIZE_MEMBERS[mid]] = val
            elif mid in _TENURE_MEMBERS:
                data[geo]["tenure"][_TENURE_MEMBERS[mid]] = val

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
    scale = target_total / hhsize_grand

    scaled: dict[str, dict[str, dict[str, int]]] = {}
    for geo in sorted(complete):
        hhsize_cats = complete[geo]["hhsize"]
        hhsize_scaled = {
            cat: round(count * scale) for cat, count in hhsize_cats.items()
        }
        hhsize_total = sum(hhsize_scaled.values())

        tenure_cats = complete[geo]["tenure"]
        tenure_raw_total = sum(tenure_cats.values())
        tenure_scale = hhsize_total / tenure_raw_total
        tenure_scaled = {
            cat: round(count * tenure_scale) for cat, count in tenure_cats.items()
        }
        # Fix integer rounding drift so both margins sum identically
        diff = hhsize_total - sum(tenure_scaled.values())
        if diff != 0:
            largest = max(tenure_scaled, key=lambda c: tenure_scaled[c])
            tenure_scaled[largest] += diff

        scaled[geo] = {"hhsize": hhsize_scaled, "tenure": tenure_scaled}

    return scaled, dropped


def write_controls_csv(
    scaled: dict[str, dict[str, dict[str, int]]],
    out_path: Path,
    geography_column: str,
    *,
    household_size_column: str = "household_size",
) -> None:
    """Write a long-format controls CSV consumable by ``calibrate-linked``."""
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
