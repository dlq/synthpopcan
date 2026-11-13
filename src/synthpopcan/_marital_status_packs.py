"""Reconcile the verified Statistics Canada private-household CT tables."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path

from synthpopcan._conditional_controls import ConditionalPersonTargets
from synthpopcan._conditional_universe import ConditionalPersonUniverse
from synthpopcan._profile_preparation import allocate_observed
from synthpopcan.geography import GeographyUniverse

PACKS = {
    "statcan-2016-marital-status-ct-v1": (2016, "10.5683/SP3/CDKEOF", "MarStH"),
    "statcan-2021-marital-status-ct-v1": (2021, "10.5683/SP3/UHEPKL", "MARSTH"),
}
AGE_ELIGIBILITY = {str(code): code >= 3 for code in range(1, 14)}
CROSSWALK = {
    "1": "never_married",
    "2": "married",
    "3": "common_law",
    "4": "separated_divorced_widowed",
}
_MARITAL_MEMBERS = ((6,), (3,), (4,), (7, 8, 9))
_ADULT_AGES = (3, *range(6, 16))
_REQUIRED_CELLS = frozenset(
    (status, age)
    for status in (1, 3, 4, 6, 7, 8, 9)
    for age in (1, 2, *_ADULT_AGES)
    if status == 1 or age in _ADULT_AGES
)


def _read_cells(
    path: Path, identifiers: set[str]
) -> dict[str, dict[tuple[int, int], int]]:
    cells: dict[str, dict[tuple[int, int], int]] = {geo: {} for geo in identifiers}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["ct", "marital_status", "age_20", "value"]:
            raise ValueError(
                "Marital-status source CSV requires ct,marital_status,age_20,value"
            )
        for row in reader:
            geo = row["ct"]
            if geo not in cells:
                continue
            key = (int(row["marital_status"]), int(row["age_20"]))
            if key not in _REQUIRED_CELLS:
                continue
            if key in cells[geo]:
                raise ValueError(f"{geo}: duplicate marital-status source cell {key}")
            value = row["value"]
            if value is None or not value.isascii() or not value.isdecimal():
                raise ValueError(
                    f"{geo}: unavailable or invalid marital-status source cell {key}"
                )
            count = int(value)
            if count % 5:
                raise ValueError(
                    f"{geo}: marital-status source counts must be multiples of five"
                )
            cells[geo][key] = count
    return cells


def _reconcile(
    geo: str,
    cells: Mapping[tuple[int, int], int],
    geography: GeographyUniverse,
    doi: str,
) -> tuple[ConditionalPersonTargets, dict[str, object]]:
    if cells.keys() != _REQUIRED_CELLS:
        raise ValueError(f"{geo}: missing or suppressed marital-status source cells")
    total, child = cells[1, 1], cells[1, 2]
    adult = sum(cells[1, age] for age in _ADULT_AGES)
    observed = [
        sum(cells[member, age] for member in members for age in _ADULT_AGES)
        for members in _MARITAL_MEMBERS
    ]
    # Each base-five rounded count can differ by up to four from the
    # unrounded integer. The envelopes count the cells on both sides.
    age_limit = 4 * (len(_ADULT_AGES) + 2)
    marital_limit = 4 * len(_ADULT_AGES) * (1 + sum(map(len, _MARITAL_MEMBERS)))
    if (
        abs(total - adult - child) > age_limit
        or abs(adult - sum(observed)) > marital_limit
    ):
        raise ValueError(f"{geo}: marital-status counts exceed the rounding envelope")
    if not total or (adult == 0) != (sum(observed) == 0):
        raise ValueError(f"{geo}: incompatible zero totals in marital-status source")
    adult_target, child_target = allocate_observed([adult, child], total)
    normalized = allocate_observed(observed, adult_target)
    counts = dict(zip(CROSSWALK.values(), normalized, strict=True))
    universe = ConditionalPersonUniverse(
        geography.identity(geo), total, adult_target, child_target, f"doi:{doi}"
    )
    return ConditionalPersonTargets(universe, counts, child_target), {
        "source_all_ages": total,
        "source_age_15_plus": adult,
        "source_under_15": child,
        "source_categories": dict(zip(CROSSWALK.values(), observed, strict=True)),
        "age_15_plus_target": adult_target,
        "under_15_target": child_target,
        "eligible_targets": counts,
    }


def prepare_pack_targets(
    pack: str, path: Path, geography: GeographyUniverse, identifiers: set[str]
) -> tuple[dict[str, ConditionalPersonTargets], dict[str, object]]:
    vintage, doi, _ = PACKS[pack]
    if geography.canonical_key != (vintage, "ct", f"statcan:census:{vintage}:ct"):
        raise ValueError(f"{pack} requires its matching Statistics Canada CT geography")
    from synthpopcan.statcan import file_integrity

    fingerprint = file_integrity(path)
    targets = {}
    adjustments = {}
    for geo, cells in sorted(_read_cells(path, identifiers).items()):
        targets[geo], adjustments[geo] = _reconcile(geo, cells, geography, doi)
    if file_integrity(path) != fingerprint:
        raise ValueError("Marital-status source CSV changed while being read")
    return targets, {
        "pack": pack,
        "source": f"doi:{doi}",
        "input": {"path": str(path), **fingerprint},
        "rounding": "base-five aggregate envelope; proportional largest remainder",
        "geographies": adjustments,
    }
