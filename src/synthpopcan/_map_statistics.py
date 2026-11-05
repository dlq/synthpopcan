"""Observed population statistics for maps; missing values are never zero-filled."""

from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterator, Set
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path
from typing import Any

_BINARY = frozenset({0, 1})
_YES = frozenset({1})
_TENURES = frozenset({1, 2, 3})
_DWELLINGS = frozenset(range(1, 9))
_AGES = frozenset({*range(1, 19), 88})
_CHILDREN = frozenset(range(1, 5))
_SENIORS = frozenset({*range(14, 19), 88})


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

    def category(self, name: str, value: int | None, valid: Set[int], yes: Set[int]):
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
    values.category("owner", _integer(row, "TENUR"), _TENURES, _YES)
    values.category("detached", _integer(row, "DTYPE"), _DWELLINGS, _YES)
    values.category("major_repairs", _integer(row, "REPAIR"), {1, 2, 3}, {3})
    size = _integer(row, "household_size")
    if size is not None and size > 0:
        values.sizes.append(size)
    cost = _integer(row, "SHELCO")
    if cost is not None and 0 <= cost < 99_999_999:
        values.shelter_costs.append(cost)


def _person_observation(row: dict[str, str], values: _Observations) -> None:
    values.total += 1
    _age_observation(row, values)
    values.category("immigrant", _integer(row, "IMMSTAT"), {1, 2, 3}, {2})
    _indicator_observation(
        row, values, "vismin", "visible_minority", "VISMIN", {1, 2}, {1}
    )


def _indicator_observation(
    row: dict[str, str],
    values: _Observations,
    name: str,
    indicator: str,
    raw: str,
    valid: Set[int],
    yes: Set[int],
) -> None:
    """Prefer an explicit binary indicator; missing indicators stay unobserved."""
    if indicator in row:
        values.category(name, _integer(row, indicator), _BINARY, _YES)
    else:
        values.category(name, _integer(row, raw), valid, yes)


def _age_observation(row: dict[str, str], values: _Observations) -> None:
    # 88 is retained for older linked models with a collapsed 65+ category.
    _indicator_observation(
        row, values, "child", "age_under_20", "AGEGRP", _AGES, _CHILDREN
    )
    _indicator_observation(
        row, values, "senior", "age_65_plus", "AGEGRP", _AGES, _SENIORS
    )


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


def _rows(path: Path, wanted) -> Iterator[dict[str, Any]]:
    """Project CSV records without building dictionaries for unused attributes."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        indexes = {name: i for i, name in enumerate(header)}
        fields = tuple(name for name in dict.fromkeys(wanted) if name in indexes)
        positions = tuple(indexes[name] for name in fields)
        extract = itemgetter(*positions) if len(positions) > 1 else None
        maximum = max(positions, default=-1)
        for source in reader:
            if not source:
                continue
            if extract is not None and len(source) > maximum:
                values = extract(source)
            else:
                values = tuple(
                    source[i] if i < len(source) else None for i in positions
                )
            yield dict(zip(fields, values, strict=True))


def _households(path: Path, geography_column: str):
    observations: dict[str, _Observations] = defaultdict(_Observations)
    household_geographies: dict[str, str] = {}
    for row in _rows(
        path,
        (
            geography_column,
            "synthetic_household_id",
            "TENUR",
            "DTYPE",
            "REPAIR",
            "household_size",
            "SHELCO",
        ),
    ):
        geography = row.get(geography_column, "").strip()
        if geography:
            household_geographies[row.get("synthetic_household_id", "")] = geography
            _household_observation(row, observations[geography])
    return observations, household_geographies


def _person_income(row: dict[str, str]) -> int | None:
    income = _integer(row, "TOTINC")
    if income is None or abs(income) == 88_888_888 or abs(income) >= 99_999_999:
        return None
    return income


def _persons(path: Path, geography_column: str, geographies: set[str]):
    observations: dict[str, _Observations] = defaultdict(_Observations)
    incomes: dict[str, int] = defaultdict(int)
    incomplete: set[str] = set()
    for row in _rows(
        path,
        (
            geography_column,
            "synthetic_household_id",
            "AGEGRP",
            "IMMSTAT",
            "VISMIN",
            "age_under_20",
            "age_65_plus",
            "visible_minority",
            "TOTINC",
        ),
    ):
        geography = row.get(geography_column, "").strip()
        if geography not in geographies:
            continue
        _person_observation(row, observations[geography])
        household = row.get("synthetic_household_id", "")
        income = _person_income(row)
        if income is None:
            incomplete.add(household)
        else:
            incomes[household] += income
    return observations, incomes, incomplete


def _income_medians(household_geographies, incomes, incomplete):
    totals: dict[str, list[int]] = defaultdict(list)
    incomplete_geographies: set[str] = set()
    for household, geography in household_geographies.items():
        if household in incomplete or household not in incomes:
            incomplete_geographies.add(geography)
        else:
            totals[geography].append(incomes[household])
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
    return _finish_person_summaries(
        summaries, household_geographies, persons, incomes, incomplete
    )


def _chunk_indicators(frame, geography_column, observations):
    """Reduce the household view's explicit or legacy person indicators."""
    import numpy as np
    import pandas as pd

    from synthpopcan._person_map_statistics import _codes

    codes, geographies = pd.factorize(frame[geography_column], sort=False)
    totals = np.bincount(codes, minlength=len(geographies))
    for i, geography in enumerate(geographies):
        observations[geography].total += int(totals[i])
    for name, indicator, raw, valid, yes in (
        ("child", "age_under_20", "AGEGRP", _AGES, _CHILDREN),
        ("senior", "age_65_plus", "AGEGRP", _AGES, _SENIORS),
        ("immigrant", None, "IMMSTAT", _TENURES, frozenset({2})),
        ("vismin", "visible_minority", "VISMIN", frozenset({1, 2}), _YES),
    ):
        if indicator in frame:
            values = _codes(frame[indicator], _BINARY)
            positive = values == 1
        elif raw in frame:
            values = _codes(frame[raw], valid)
            positive = np.isin(values, tuple(yes))
        else:
            continue
        known = np.bincount(codes[values >= 0], minlength=len(geographies))
        selected = np.bincount(codes[positive], minlength=len(geographies))
        for i, geography in enumerate(geographies):
            observations[geography].observed[name] += int(known[i])
            observations[geography].positive[name] += int(selected[i])


def _chunk_household_incomes(frame, incomes, incomplete):
    """Sum bounded per-record integer incomes without floating-point reduction."""
    import numpy as np
    import pandas as pd

    from synthpopcan._person_map_statistics import _parse_number

    identifiers = (
        frame["synthetic_household_id"]
        if "synthetic_household_id" in frame
        else pd.Series("", index=frame.index)
    )
    codes, names = pd.factorize(identifiers, sort=False, use_na_sentinel=False)
    # CSV identifiers are strings or a missing trailing cell (None). Pandas
    # represents the latter as NaN in an index; preserve DictReader's None key.
    names = [name if isinstance(name, str) else None for name in names]
    values = np.zeros(len(frame), dtype=np.int64)
    known = np.zeros(len(frame), dtype=bool)
    if "TOTINC" in frame:
        raw_codes, raw_values = pd.factorize(frame["TOTINC"], sort=False)
        parsed = [_parse_number(value) for value in raw_values]
        valid = [
            value is not None and abs(value) != 88_888_888 and abs(value) < 99_999_999
            for value in parsed
        ]
        lookup = np.array(
            [value if valid[i] else 0 for i, value in enumerate(parsed)] + [0],
            dtype=np.int64,
        )
        validity = np.array([*valid, False], dtype=bool)
        values, known = lookup[raw_codes], validity[raw_codes]
    totals = np.zeros(len(names), dtype=np.int64)
    # Each reader chunk has at most 100,000 records and each valid income has
    # abs(value) < 100,000,000, so this integer reduction cannot overflow int64.
    # Conversion to Python int below also preserves sums spanning chunks.
    np.add.at(totals, codes[known], values[known])
    for index in np.unique(codes[known]):
        incomes[names[index]] += int(totals[index])
    for index in np.unique(codes[~known]):
        incomplete.add(names[index])


def _finish_person_summaries(
    summaries, household_geographies, observations, incomes, incomplete
):
    medians = _income_medians(household_geographies, incomes, incomplete)
    for geography, summary in summaries.items():
        values = observations.get(geography, _Observations())
        summary.update(
            n_persons=values.total,
            pct_child=values.proportion("child"),
            pct_senior=values.proportion("senior"),
            pct_immigrant=values.proportion("immigrant"),
            pct_vismin=values.proportion("vismin"),
            median_hh_income=medians.get(geography),
        )
    return summaries


def compute_linked_statistics(
    households_path: Path, persons_path: Path, geography_column: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Compute household and explicit 2021 person views in one person CSV pass.

    The household view retains its legacy-code fallback and strict complete-
    observation policy. The person view retains its own 2021 eligible/known
    denominators. Sharing input records does not combine those definitions.
    """
    from synthpopcan._columnar_csv import should_use_polars

    if should_use_polars(households_path, persons_path):
        from synthpopcan._polars_map_statistics import try_compute_linked_statistics

        accelerated = try_compute_linked_statistics(
            households_path, persons_path, geography_column
        )
        if accelerated is not None:
            return accelerated
    return _compute_linked_statistics_reference(
        households_path, persons_path, geography_column
    )


def _compute_linked_statistics_reference(
    households_path: Path, persons_path: Path, geography_column: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Retain stdlib CSV and exact Python arithmetic as the fallback definition."""
    from synthpopcan._person_map_statistics import _chunks, _observe_chunk, _People

    households, household_geographies = _households(households_path, geography_column)
    summaries = {key: _household_summary(value) for key, value in households.items()}
    people: dict[str, Any] = defaultdict(_People)
    observations: dict[str, _Observations] = defaultdict(_Observations)
    incomes: dict[Any, int] = defaultdict(int)
    incomplete: set[Any] = set()
    for frame in _chunks(
        persons_path,
        geography_column,
        extra_fields=(
            "synthetic_household_id",
            "age_under_20",
            "age_65_plus",
            "visible_minority",
        ),
    ):
        _observe_chunk(frame, geography_column, people)
        selected = frame.loc[frame[geography_column].isin(summaries)]
        if not selected.empty:
            _chunk_indicators(selected, geography_column, observations)
            _chunk_household_incomes(selected, incomes, incomplete)
    return (
        _finish_person_summaries(
            summaries, household_geographies, observations, incomes, incomplete
        ),
        {geography: values.summary() for geography, values in people.items()},
    )
