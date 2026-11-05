"""Person-level maps using the explicit 2021 hierarchical PUMF codebook.

Shares use known eligible person records. Missing and inapplicable values do
not become observations; their coverage is exposed alongside each measure.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class _Category:
    field: str
    valid: frozenset[int]
    adult: bool = False


@dataclass(frozen=True)
class _Metric:
    name: str
    label: str
    category: _Category
    positive: frozenset[int]
    universe: str = "all people with a known value"
    denominator: frozenset[int] | None = None


def _metric(
    name: str,
    label: str,
    source: str,
    valid: Iterable[int],
    positive: Iterable[int],
    *,
    adult: bool = False,
    denominator: Iterable[int] | None = None,
) -> _Metric:
    return _Metric(
        name,
        label,
        _Category(source, frozenset(valid), adult),
        frozenset(positive),
        "known labour-force participants aged 15+"
        if denominator is not None
        else "people aged 15+ with a known value"
        if adult
        else "all people with a known value",
        frozenset(denominator) if denominator is not None else None,
    )


_METRICS = (
    _metric("pct_age_0_14", "% aged 0–14", "AGEGRP", range(1, 14), {1, 2}),
    _metric("pct_age_15_24", "% aged 15–24", "AGEGRP", range(1, 14), {3, 4}),
    _metric("pct_age_25_44", "% aged 25–44", "AGEGRP", range(1, 14), {5, 6, 7, 8}),
    _metric("pct_age_45_64", "% aged 45–64", "AGEGRP", range(1, 14), {9, 10, 11}),
    _metric("pct_age_65_plus", "% aged 65+", "AGEGRP", range(1, 14), {12, 13}),
    _metric("pct_women", "% women+", "GENDER", {1, 2}, {1}),
    _metric("pct_men", "% men+", "GENDER", {1, 2}, {2}),
    _metric(
        "pct_canadian_citizens", "% Canadian citizens", "CITIZEN", {1, 2, 3}, {1, 2}
    ),
    _metric("pct_immigrants", "% immigrants", "IMMSTAT", {1, 2, 3}, {2}),
    _metric(
        "pct_nonpermanent_residents",
        "% non-permanent residents",
        "IMMSTAT",
        {1, 2, 3},
        {3},
    ),
    _metric("pct_first_generation", "% first generation", "GENSTAT", {1, 2, 3, 4}, {1}),
    _metric(
        "pct_second_generation", "% second generation", "GENSTAT", {1, 2, 3, 4}, {2, 3}
    ),
    _metric(
        "pct_third_generation",
        "% third generation or later",
        "GENSTAT",
        {1, 2, 3, 4},
        {4},
    ),
    _metric("pct_visible_minority", "% visible minority", "VISMIN", {0, 1}, {1}),
    _metric(
        "pct_partnered",
        "% married or common-law (15+)",
        "MARSTH",
        {1, 2, 3, 4},
        {2, 3},
        adult=True,
    ),
    _metric(
        "pct_no_diploma",
        "% no certificate/diploma (15+)",
        "HDGREE",
        range(1, 9),
        {1},
        adult=True,
    ),
    _metric(
        "pct_high_school_only",
        "% high-school diploma only (15+)",
        "HDGREE",
        range(1, 9),
        {2},
        adult=True,
    ),
    _metric(
        "pct_postsecondary",
        "% postsecondary qualification (15+)",
        "HDGREE",
        range(1, 9),
        range(3, 9),
        adult=True,
    ),
    _metric(
        "pct_bachelor_plus",
        "% bachelor's degree or higher (15+)",
        "HDGREE",
        range(1, 9),
        {7, 8},
        adult=True,
    ),
    _metric(
        "employment_rate",
        "Employment rate (15+, reference week)",
        "LFACT",
        range(1, 15),
        {1, 2},
        adult=True,
    ),
    _metric(
        "participation_rate",
        "Labour-force participation rate (15+)",
        "LFACT",
        range(1, 15),
        range(1, 11),
        adult=True,
    ),
    _metric(
        "unemployment_rate",
        "Unemployment rate (labour force)",
        "LFACT",
        range(1, 15),
        range(3, 11),
        adult=True,
        denominator=range(1, 11),
    ),
    _metric(
        "pct_full_time_2020",
        "% mainly full-time workers (2020)",
        "FPTWK",
        {1, 2},
        {1},
        adult=True,
    ),
    *(
        _metric(f"pct_{prefix}_{language}", f"% {label}: {name}", source, {0, 1}, {1})
        for prefix, label, fields in (
            (
                "mother_tongue",
                "mother tongue",
                (
                    ("english", "English", "MTNEN"),
                    ("french", "French", "MTNFR"),
                ),
            ),
            (
                "home_language",
                "home language",
                (
                    ("english", "English", "HLMOSTEN"),
                    ("french", "French", "HLMOSTFR"),
                ),
            ),
        )
        for language, name, source in fields
    ),
    _metric(
        "pct_mother_tongue_other",
        "% non-official mother tongue",
        "MTNNO",
        range(1, 11),
        range(2, 11),
    ),
    _metric(
        "pct_home_language_other",
        "% non-official language at home",
        "HLMOSTNO",
        range(1, 11),
        range(2, 11),
    ),
)
_CATEGORIES = tuple(dict.fromkeys(metric.category for metric in _METRICS))
_INCOMES = (
    ("TOTINC", "median_personal_income", "Median personal income (15+, 2020)"),
    ("EMPIN", "median_employment_income", "Median employment income (15+, 2020)"),
)


def _parse_number(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _number(row: dict[str, str], name: str) -> int | None:
    return _parse_number(row.get(name))


def _median(counts: Counter[int]) -> int | float | None:
    total = sum(counts.values())
    if not total:
        return None
    lower, upper = (total - 1) // 2, total // 2
    accumulated = 0
    left = None
    for value in sorted(counts):
        accumulated += counts[value]
        if left is None and lower < accumulated:
            left = value
        if upper < accumulated:
            assert left is not None
            return value if total % 2 else (left + value) / 2
    raise AssertionError("income histogram has inconsistent counts")


@dataclass
class _People:
    total: int = 0
    adults: int = 0
    counts: dict[_Category, Counter[int]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    incomes: dict[str, Counter[int]] = field(
        default_factory=lambda: defaultdict(Counter)
    )

    def observe(self, row: dict[str, str]) -> None:
        self.total += 1
        age = _number(row, "AGEGRP")
        adult = age is not None and 3 <= age <= 13
        self.adults += adult
        for category in _CATEGORIES:
            if category.adult and not adult:
                continue
            value = _number(row, category.field)
            if value in category.valid:
                self.counts[category][value] += 1
        if adult:
            self.observe_income(row)

    def observe_income(self, row: dict[str, str]) -> None:
        for source, _, _ in _INCOMES:
            value = _number(row, source)
            if (
                value is not None
                and abs(value) != 88_888_888
                and abs(value) < 99_999_999
            ):
                self.incomes[source][value] += 1

    def summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "n_persons": self.total,
            "n_persons_15_plus": self.adults,
        }
        for metric in _METRICS:
            counts = self.counts[metric.category]
            known = sum(counts.values())
            denominator = (
                sum(counts[v] for v in metric.denominator)
                if metric.denominator is not None
                else known
            )
            numerator = sum(counts[v] for v in metric.positive)
            eligible = self.adults if metric.category.adult else self.total
            result[metric.name] = (
                round(100 * numerator / denominator, 2) if denominator else None
            )
            result[metric.name + "_n"] = denominator
            result[metric.name + "_known"] = known
            result[metric.name + "_eligible"] = eligible
        for source, name, _ in _INCOMES:
            observations = self.incomes[source]
            result[name] = _median(observations)
            result[name + "_n"] = sum(observations.values())
            result[name + "_known"] = sum(observations.values())
            result[name + "_eligible"] = self.adults
        return result


def _chunks(
    path: Path,
    geography_column: str,
    size: int = 100_000,
    *,
    extra_fields: Iterable[str] = (),
):
    """Keep CSV record semantics, including blank records and quoted newlines."""
    wanted = tuple(
        dict.fromkeys(
            (
                geography_column,
                "AGEGRP",
                *(c.field for c in _CATEGORIES),
                *(s for s, _, _ in _INCOMES),
                *extra_fields,
            )
        )
    )
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        required = {geography_column, "synthetic_person_id", "AGEGRP"}
        missing = required - set(header)
        if missing:
            raise ValueError(
                "Person-attribute maps require a person CSV with columns: "
                + ", ".join(sorted(missing))
            )
        # DictReader uses the last occurrence of duplicated header names.
        indexes = {name: i for i, name in enumerate(header)}
        fields = [name for name in wanted if name in indexes]
        positions = [indexes[name] for name in fields]
        extract = (
            itemgetter(*positions)
            if len(positions) > 1
            else lambda record: (record[positions[0]],)
        )
        maximum = max(positions)
        rows = []
        line = 1
        for source in reader:
            if not source:
                continue
            line += 1
            row = (
                extract(source)
                if len(source) > maximum
                else tuple(source[i] if i < len(source) else None for i in positions)
            )
            raw_geography = row[0]
            geography = raw_geography.strip() if isinstance(raw_geography, str) else ""
            if not geography:
                raise ValueError(
                    f"Person row {line} has no {geography_column} assignment; "
                    "assign geography before mapping."
                )
            if geography != row[0]:
                row = (geography, *row[1:])
            rows.append(row)
            if len(rows) == size:
                yield pd.DataFrame.from_records(rows, columns=fields)
                rows = []
        if rows:
            yield pd.DataFrame.from_records(rows, columns=fields)


def _codes(values, valid):
    raw_codes, raw_values = pd.factorize(values, sort=False)
    lookup = np.array(
        [value if (value := _parse_number(raw)) in valid else -1 for raw in raw_values]
        + [-1],
        dtype=np.int64,
    )
    return lookup[raw_codes]


def _observe_chunk(frame, geography_column, people):
    geo_codes, geographies = pd.factorize(frame[geography_column], sort=False)
    age = _codes(frame["AGEGRP"], range(1, 14))
    adult = (age >= 3) & (age <= 13)
    totals = np.bincount(geo_codes, minlength=len(geographies))
    adults = np.bincount(geo_codes[adult], minlength=len(geographies))
    for i, geography in enumerate(geographies):
        people[geography].total += int(totals[i])
        people[geography].adults += int(adults[i])
    for category in _CATEGORIES:
        if category.field not in frame:
            continue
        values = (
            age
            if category.field == "AGEGRP"
            else _codes(frame[category.field], category.valid)
        )
        observed = values >= 0
        if category.adult:
            observed &= adult
        width = max(category.valid) + 1
        counts = np.bincount(
            geo_codes[observed] * width + values[observed],
            minlength=len(geographies) * width,
        ).reshape(len(geographies), width)
        for i, geography in enumerate(geographies):
            people[geography].counts[category].update(
                {
                    int(value): int(counts[i, value])
                    for value in np.flatnonzero(counts[i])
                }
            )
    for source, _, _ in _INCOMES:
        if source not in frame:
            continue
        counts = (
            frame.loc[adult]
            .groupby([geography_column, source], sort=False, dropna=False)
            .size()
        )
        for (geography, raw), count in counts.items():
            value = _parse_number(raw)
            if (
                value is not None
                and abs(value) != 88_888_888
                and abs(value) < 99_999_999
            ):
                people[geography].incomes[source][value] += int(count)


def compute_person_statistics(
    path: Path, geography_column: str
) -> dict[str, dict[str, Any]]:
    """Aggregate person records in bounded chunks with exact histogram medians."""
    people: dict[str, _People] = defaultdict(_People)
    for frame in _chunks(path, geography_column):
        _observe_chunk(frame, geography_column, people)
    return {geography: value.summary() for geography, value in people.items()}
