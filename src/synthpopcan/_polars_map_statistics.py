"""Optional native map reductions over bounded, conservatively parsed CSV blocks.

Input strings are released after each block. Categorical household keys,
reduced counts and exact numeric median samples remain until the final merge.
Unusual CSV or integer syntax delegates the whole calculation to the reference
implementation; partial native results are never published.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from synthpopcan._columnar_csv import (
    BoundedCSVFallbackError,
    iter_string_frames,
    load_polars,
)
from synthpopcan._map_statistics import _AGES, _CHILDREN, _SENIORS
from synthpopcan._person_map_statistics import _CATEGORIES, _INCOMES, _METRICS

_HOUSEHOLD_ID = "synthetic_household_id"
_HOUSEHOLD_FIELDS = ("TENUR", "DTYPE", "REPAIR", "household_size", "SHELCO")
_PERSON_FIELDS = tuple(
    dict.fromkeys(
        (
            "AGEGRP",
            *(category.field for category in _CATEGORIES),
            *(source for source, _, _ in _INCOMES),
            "age_under_20",
            "age_65_plus",
            "visible_minority",
        )
    )
)
_INT64_MAX = (1 << 63) - 1
_UINT64_MAX = (1 << 64) - 1
_MAX_EXACT_SUM = (1 << 53) - 1
_MAX_SIZE = 1_000_000
_MAX_INCOME = 99_999_998


class _MapStatistics:
    def __init__(self, polars: Any, geography_column: str) -> None:
        self.pl = polars
        self.geography_column = geography_column
        # Separate per-calculation dictionaries release source string buffers
        # without growing a process-wide categorical cache across map requests.
        self.geography_type = polars.Categorical(polars.Categories.random())
        self.household_type = polars.Categorical(polars.Categories.random())
        self.household_size_sum = 0
        self.income_abs_sum = 0
        self.household_count = 0
        self.person_count = 0

    def number(self, name: str) -> Any:
        return self.pl.col("__number_" + name)

    def known(self, value: Any, valid: Any) -> Any:
        return value.is_in(tuple(valid)).fill_null(False)

    def count(self, predicate: Any) -> Any:
        return predicate.cast(self.pl.UInt64).sum()

    def valid_income(self) -> Any:
        value = self.number("TOTINC")
        return self._income_is_valid(value)

    @staticmethod
    def _income_is_valid(value: Any) -> Any:
        # Avoid abs(Int64 minimum), which could wrap before sentinel checks.
        return (
            value.is_between(-_MAX_INCOME, _MAX_INCOME)
            & ~value.is_in((-88_888_888, 88_888_888))
        ).fill_null(False)

    def prepare(self, frame: Any, fields: tuple[str, ...], *, households=False) -> Any:
        pl = self.pl
        # Parse once, then inspect unusual integer syntax only where native
        # conversion failed. Most Census fields are ordinary ASCII integers.
        frame = frame.with_columns(
            *(
                pl.col(name)
                .str.strip_chars()
                .cast(pl.Int64, strict=False)
                .alias("__number_" + name)
                for name in fields
            ),
            pl.col(self.geography_column).str.strip_chars().alias("__geo"),
        )
        checks = [
            pl.col(self.geography_column)
            .str.contains(r"[\x1c-\x1f]")
            .fill_null(False)
            .any()
        ]
        for name in fields:
            raw = pl.col(name)
            failed = raw.filter(self.number(name).is_null() & raw.is_not_null())
            unusual = r"_|[^\x00-\x7f]"
            if name == "household_size":
                unusual = r"_|[^\x00-\x7f]|^[+\-]?\d"
                checks.append((self.number(name) > _MAX_SIZE).fill_null(False).any())
            checks.append(failed.str.contains(unusual).fill_null(False).any())
        if (
            frame["__geo"].null_count()
            or frame[_HOUSEHOLD_ID].null_count()
            or frame.select(pl.any_horizontal(checks)).item()
        ):
            raise BoundedCSVFallbackError(
                "ambiguous map record or Python integer syntax"
            )
        frame = frame.with_columns(
            pl.col("__geo").cast(self.geography_type),
            pl.col(_HOUSEHOLD_ID).cast(self.household_type),
        )
        self._check_sums(frame, households=households)
        return frame

    def _check_sums(self, frame: Any, *, households: bool) -> None:
        """Bound per-block integer reductions and cumulative merged arithmetic."""
        limit = _MAX_SIZE if households else _MAX_INCOME
        if frame.height * limit > _INT64_MAX:
            raise BoundedCSVFallbackError(
                "map block exceeds exact integer reduction bounds"
            )
        if households:
            self.household_count += frame.height
            size = self.number("household_size")
            self.household_size_sum += int(
                frame.select(size.filter(size > 0).sum()).item()
            )
            total, count = self.household_size_sum, self.household_count
        else:
            self.person_count += frame.height
            self.income_abs_sum += int(
                frame.select(
                    self.number("TOTINC").filter(self.valid_income()).abs().sum()
                ).item()
            )
            total, count = self.income_abs_sum, self.person_count
        if total > min(_INT64_MAX, _MAX_EXACT_SUM) or count > _UINT64_MAX:
            raise BoundedCSVFallbackError(
                "map totals require reference integer arithmetic"
            )

    def blocks(self, path: Path, fields: tuple[str, ...], *, required=()):
        defaults: dict[str, str | None] = {name: None for name in fields}
        defaults[_HOUSEHOLD_ID] = ""
        return iter_string_frames(
            path,
            (self.geography_column, _HOUSEHOLD_ID, *fields),
            optional_defaults=defaults,
            required=required,
        )

    def household_expressions(self) -> list[Any]:
        pl = self.pl
        size, cost = self.number("household_size"), self.number("SHELCO")
        result = [
            pl.len().cast(pl.UInt64).alias("total"),
            size.filter(size > 0).sum().alias("size_sum"),
            self.count((size > 0).fill_null(False)).alias("size_n"),
            cost.filter((cost >= 0) & (cost < 99_999_999)).alias("cost_samples"),
        ]
        for name, source, valid, yes in (
            ("owner", "TENUR", {1, 2, 3}, {1}),
            ("detached", "DTYPE", range(1, 9), {1}),
            ("major_repairs", "REPAIR", {1, 2, 3}, {3}),
        ):
            result.extend(
                (
                    self.count(self.known(self.number(source), valid)).alias(
                        name + "_known"
                    ),
                    self.count(self.known(self.number(source), yes)).alias(
                        name + "_positive"
                    ),
                )
            )
        return result

    def person_expressions(self, present: set[str]) -> list[Any]:
        pl = self.pl
        adult = self.number("AGEGRP").is_between(3, 13).fill_null(False)
        result = [
            pl.len().cast(pl.UInt64).alias("total"),
            self.count(adult).alias("adults"),
        ]
        for metric in _METRICS:
            value = self.number(metric.category.field)
            observed = self.known(value, metric.category.valid)
            if metric.category.adult:
                observed &= adult
            denominator = observed
            if metric.denominator is not None:
                denominator &= self.known(value, metric.denominator)
            result.extend(
                (
                    self.count(observed).alias(metric.name + "_known"),
                    self.count(denominator).alias(metric.name + "_n"),
                    self.count(observed & self.known(value, metric.positive)).alias(
                        metric.name + "_positive"
                    ),
                )
            )
        for field, name, _ in _INCOMES:
            value = self.number(field)
            observed = adult & self._income_is_valid(value)
            result.extend(
                (
                    self.count(observed).alias(name + "_n"),
                    value.filter(observed).alias(name + "_samples"),
                )
            )
        result.extend(self.indicator_expressions(present))
        return result

    def indicator_expressions(self, present: set[str]) -> list[Any]:
        result = []
        for name, indicator, raw, valid, yes in (
            ("child", "age_under_20", "AGEGRP", _AGES, _CHILDREN),
            ("senior", "age_65_plus", "AGEGRP", _AGES, _SENIORS),
            ("immigrant", None, "IMMSTAT", {1, 2, 3}, {2}),
            ("vismin", "visible_minority", "VISMIN", {1, 2}, {1}),
        ):
            if indicator is not None and indicator in present:
                value, valid, yes = self.number(indicator), {0, 1}, {1}
            else:
                value = self.number(raw)
            result.extend(
                (
                    self.count(self.known(value, valid)).alias("hh_" + name + "_known"),
                    self.count(self.known(value, yes)).alias(
                        "hh_" + name + "_positive"
                    ),
                )
            )
        return result

    def merge(self, pieces: list[Any], samples: tuple[str, ...]) -> Any:
        pl = self.pl
        frame = pl.concat(pieces)
        sample_names = {name + "_samples" for name in samples}
        return frame.group_by("__geo", maintain_order=True).agg(
            *(
                pl.col(name).sum()
                for name in frame.columns
                if name != "__geo" and name not in sample_names
            ),
            *(
                pl.col(name + "_samples")
                .list.explode(keep_nulls=False, empty_as_null=False)
                .median()
                .alias(name)
                for name in samples
            ),
        )

    def households(self, path: Path) -> tuple[dict[str, dict[str, Any]], Any]:
        pl = self.pl
        pieces, mappings = [], []
        expressions = self.household_expressions()
        for frame, _present in self.blocks(path, _HOUSEHOLD_FIELDS):
            frame = self.prepare(frame, _HOUSEHOLD_FIELDS, households=True).filter(
                pl.col("__geo") != ""
            )
            pieces.append(frame.group_by("__geo", maintain_order=True).agg(expressions))
            mappings.append(frame.select(_HOUSEHOLD_ID, "__geo"))
        if not pieces:
            raise BoundedCSVFallbackError("empty household map table")
        summaries = {
            row["__geo"]: _household_summary(row)
            for row in self.merge(pieces, ("cost",)).iter_rows(named=True)
        }
        mapping = (
            pl.concat(mappings)
            .group_by(_HOUSEHOLD_ID, maintain_order=True)
            .agg(pl.col("__geo").last())
        )
        return summaries, mapping

    def people(
        self, path: Path, summaries: dict[str, dict[str, Any]]
    ) -> tuple[Any, Any]:
        pl = self.pl
        pieces, incomes = [], []
        expressions = None
        observed = self.valid_income()
        income_expressions = (
            self.count(observed).alias("known"),
            (~observed).any().alias("incomplete"),
            self.number("TOTINC").filter(observed).sum().alias("income"),
        )
        for frame, present in self.blocks(
            path,
            _PERSON_FIELDS,
            required=(self.geography_column, "AGEGRP", "synthetic_person_id"),
        ):
            frame = self.prepare(frame, _PERSON_FIELDS)
            if frame.filter(pl.col("__geo") == "").height:
                raise BoundedCSVFallbackError("empty person map geography")
            if expressions is None:
                expressions = self.person_expressions(present)
            pieces.append(frame.group_by("__geo", maintain_order=True).agg(expressions))
            incomes.append(
                frame.filter(pl.col("__geo").is_in(tuple(summaries)))
                .group_by(_HOUSEHOLD_ID)
                .agg(income_expressions)
            )
        if not pieces:
            raise BoundedCSVFallbackError("empty person map table")
        per_geo = self.merge(pieces, tuple(name for _, name, _ in _INCOMES))
        per_household = (
            pl.concat(incomes)
            .group_by(_HOUSEHOLD_ID)
            .agg(
                pl.col("known").sum(),
                pl.col("incomplete").any(),
                pl.col("income").sum(),
            )
        )
        return per_geo, per_household

    def attach_income(
        self, summaries: dict[str, dict[str, Any]], mapping: Any, incomes: Any
    ) -> None:
        pl = self.pl
        rows = (
            mapping.join(incomes, on=_HOUSEHOLD_ID, how="left", nulls_equal=True)
            .with_columns(
                (
                    pl.col("incomplete").fill_null(True)
                    | (pl.col("known").fill_null(0) == 0)
                ).alias("bad")
            )
            .group_by("__geo")
            .agg(
                pl.col("bad").any().alias("incomplete"),
                pl.col("income").filter(~pl.col("bad")).median().alias("median"),
            )
        )
        for row in rows.iter_rows(named=True):
            summaries[row["__geo"]]["median_hh_income"] = (
                None
                if row["incomplete"] or row["median"] is None
                else round(row["median"])
            )

    def compute(
        self, households_path: Path, persons_path: Path
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        summaries, mapping = self.households(households_path)
        per_geo, incomes = self.people(persons_path, summaries)
        people = {}
        for row in per_geo.iter_rows(named=True):
            geography = row["__geo"]
            people[geography] = _person_summary(row)
            if geography in summaries:
                _attach_indicators(summaries[geography], row)
        for summary in summaries.values():
            if "n_persons" not in summary:
                summary.update(
                    n_persons=0,
                    pct_child=None,
                    pct_senior=None,
                    pct_immigrant=None,
                    pct_vismin=None,
                )
            summary["median_hh_income"] = None
        self.attach_income(summaries, mapping, incomes)
        return summaries, people


def _household_summary(row: dict[str, Any]) -> dict[str, Any]:
    count, total = row["size_n"], row["size_sum"]
    mean = (
        total // count
        if count and total % count == 0
        else total / count
        if count
        else None
    )
    result = {
        "n_households": row["total"],
        "avg_hh_size": round(mean, 2) if mean is not None else None,
    }
    for name in ("owner", "detached", "major_repairs"):
        result["pct_" + name] = (
            round(row[name + "_positive"] / row["total"] * 100, 1)
            if row[name + "_known"] == row["total"]
            else None
        )
    result["median_shelter_cost"] = None if row["cost"] is None else round(row["cost"])
    return result


def _person_summary(row: dict[str, Any]) -> dict[str, Any]:
    result = {"n_persons": row["total"], "n_persons_15_plus": row["adults"]}
    for metric in _METRICS:
        denominator = row[metric.name + "_n"]
        result[metric.name] = (
            round(100 * row[metric.name + "_positive"] / denominator, 2)
            if denominator
            else None
        )
        result[metric.name + "_n"] = denominator
        result[metric.name + "_known"] = row[metric.name + "_known"]
        result[metric.name + "_eligible"] = (
            row["adults"] if metric.category.adult else row["total"]
        )
    for _, name, _ in _INCOMES:
        count, median = row[name + "_n"], row[name]
        result[name] = None if median is None else int(median) if count % 2 else median
        result[name + "_n"] = count
        result[name + "_known"] = count
        result[name + "_eligible"] = row["adults"]
    return result


def _attach_indicators(summary: dict[str, Any], row: dict[str, Any]) -> None:
    summary["n_persons"] = row["total"]
    for name in ("child", "senior", "immigrant", "vismin"):
        summary["pct_" + name] = (
            round(row["hh_" + name + "_positive"] / row["total"] * 100, 1)
            if row["hh_" + name + "_known"] == row["total"]
            else None
        )


def try_compute_linked_statistics(
    households_path: Path, persons_path: Path, geography_column: str
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]] | None:
    """Return exact native summaries, or request the original whole-file path."""
    polars = load_polars()
    if polars is None:
        return None
    try:
        return _MapStatistics(polars, geography_column).compute(
            households_path, persons_path
        )
    except (BoundedCSVFallbackError, polars.exceptions.PolarsError):
        return None
