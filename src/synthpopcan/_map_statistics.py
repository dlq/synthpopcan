"""Observed population statistics for maps; missing values are never zero-filled."""

from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class _Observations:
    total: int = 0
    observed: Counter[str] = field(default_factory=Counter)
    positive: Counter[str] = field(default_factory=Counter)
    sizes: list[int] = field(default_factory=list)
    shelter_costs: list[int] = field(default_factory=list)

    def proportion(self, name: str) -> float | None:
        if not self.total or self.observed[name] != self.total:
            return None
        return round(self.positive[name] / self.total * 100, 1)

    def category(self, name: str, value: int | None, valid: set[int], yes: set[int]):
        if value in valid:
            self.observed[name] += 1
            self.positive[name] += value in yes


def _integer(row: dict[str, str], name: str) -> int | None:
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError):
        return None


def _household_observation(row: dict[str, str], values: _Observations) -> None:
    values.total += 1
    values.category("owner", _integer(row, "TENUR"), {1, 2, 3}, {1})
    values.category("detached", _integer(row, "DTYPE"), set(range(1, 9)), {1})
    values.category("major_repairs", _integer(row, "REPAIR"), {1, 2, 3}, {3})
    size = _integer(row, "household_size")
    if size is not None and size > 0:
        values.sizes.append(size)
    cost = _integer(row, "SHELCO")
    if cost is not None and 1 <= cost < 99_999_999:
        values.shelter_costs.append(cost)


def _person_observation(row: dict[str, str], values: _Observations) -> None:
    values.total += 1
    age = _integer(row, "AGEGRP")
    # 88 is retained for older linked models with a collapsed 65+ category.
    ages = {*range(1, 19), 88}
    values.category("child", age, ages, set(range(1, 5)))
    values.category("senior", age, ages, {*range(14, 19), 88})
    values.category("immigrant", _integer(row, "IMMSTAT"), {1, 2, 3}, {2})
    values.category("vismin", _integer(row, "VISMIN"), {1, 2}, {1})


def _household_summary(values: _Observations) -> dict[str, Any]:
    return {
        "n_households": values.total,
        "avg_hh_size": (
            round(statistics.mean(values.sizes), 2) if values.sizes else None
        ),
        "pct_owner": values.proportion("owner"),
        "pct_detached": values.proportion("detached"),
        "pct_major_repairs": values.proportion("major_repairs"),
        "median_shelter_cost": (
            round(statistics.median(values.shelter_costs))
            if values.shelter_costs
            else None
        ),
    }


def _households(path: Path, geography_column: str):
    observations: dict[str, _Observations] = defaultdict(_Observations)
    household_geographies: dict[str, str] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            geography = row.get(geography_column, "").strip()
            if geography:
                household_geographies[row.get("synthetic_household_id", "")] = geography
                _household_observation(row, observations[geography])
    return observations, household_geographies


def _persons(path: Path, geography_column: str, geographies: set[str]):
    observations: dict[str, _Observations] = defaultdict(_Observations)
    incomes: dict[str, list[int]] = defaultdict(list)
    incomplete: set[str] = set()
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            geography = row.get(geography_column, "").strip()
            if geography not in geographies:
                continue
            _person_observation(row, observations[geography])
            household = row.get("synthetic_household_id", "")
            income = _integer(row, "TOTINC")
            if income is None or abs(income) >= 99_999_999:
                incomplete.add(household)
            else:
                incomes[household].append(income)
    return observations, incomes, incomplete


def _income_medians(household_geographies, incomes, incomplete):
    totals: dict[str, list[int]] = defaultdict(list)
    incomplete_geographies: set[str] = set()
    for household, geography in household_geographies.items():
        if household in incomplete or household not in incomes:
            incomplete_geographies.add(geography)
        else:
            totals[geography].append(sum(incomes[household]))
    return {
        geography: (
            None
            if geography in incomplete_geographies
            else round(statistics.median(values))
        )
        for geography, values in totals.items()
    }


def compute_geo_statistics(
    households_path: Path, geography_column: str, persons_path: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Calculate statistics; percentages and income require complete observations."""
    households, household_geographies = _households(households_path, geography_column)
    summaries = {key: _household_summary(value) for key, value in households.items()}
    if persons_path is None:
        return summaries
    persons, incomes, incomplete = _persons(
        persons_path, geography_column, set(summaries)
    )
    medians = _income_medians(household_geographies, incomes, incomplete)
    for geography, summary in summaries.items():
        values = persons.get(geography, _Observations())
        summary.update(
            n_persons=values.total,
            pct_child=values.proportion("child"),
            pct_senior=values.proportion("senior"),
            pct_immigrant=values.proportion("immigrant"),
            pct_vismin=values.proportion("vismin"),
            median_hh_income=medians.get(geography),
        )
    return summaries
