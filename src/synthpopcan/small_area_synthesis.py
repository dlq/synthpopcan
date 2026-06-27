"""Small-area linked household/person synthesis helpers."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    read_control_table,
)
from synthpopcan.diagnostics import build_ipf_fit_report
from synthpopcan.ipf import IPFResult, NumpyIPFIndex, fit_ipf, fit_ipf_numpy, integerize_weights

HouseholdRow = dict[str, str]
PersonRow = dict[str, str]


@dataclass(frozen=True)
class GeographyHouseholdFit:
    """Fitted candidate-household weights for each target geography."""

    weights_by_geography: dict[str, list[float]]
    reports: dict[str, dict[str, Any]]


def controls_by_geography(
    controls: ControlTable,
    *,
    geography_dimension: str,
) -> dict[str, ControlTable]:
    """Split normalized controls into one control table per target geography.

    The returned control tables remove ``geography_dimension`` from each margin
    so a candidate household pool can be fitted independently to every target
    geography.
    """

    grouped: dict[str, list[ControlMargin]] = defaultdict(list)
    for margin in controls.margins:
        if geography_dimension not in margin.dimensions:
            raise ValueError(
                f"control margin {margin.name!r} does not include geography "
                f"dimension {geography_dimension!r}"
            )
        reduced_dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        if not reduced_dimensions:
            raise ValueError(
                f"control margin {margin.name!r} must include at least one "
                f"dimension besides {geography_dimension!r}"
            )

        cells_by_geography: dict[str, list[ControlCell]] = defaultdict(list)
        for cell in margin.cells:
            geography = cell.categories.get(geography_dimension, "")
            if not geography:
                raise ValueError(
                    f"control margin {margin.name!r} has a cell without "
                    f"{geography_dimension!r}"
                )
            cells_by_geography[geography].append(
                ControlCell(
                    categories={
                        dimension: cell.categories[dimension]
                        for dimension in reduced_dimensions
                    },
                    count=cell.count,
                )
            )
        for geography, cells in cells_by_geography.items():
            grouped[geography].append(
                ControlMargin(
                    name=margin.name,
                    dimensions=reduced_dimensions,
                    cells=tuple(cells),
                )
            )

    return {
        geography: ControlTable(
            margins=tuple(margins),
            dimensions=_control_dimensions(margins),
        )
        for geography, margins in grouped.items()
    }


def fit_households_by_geography(
    households: Sequence[HouseholdRow],
    controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    n_workers: int | None = None,
) -> GeographyHouseholdFit:
    """Fit the same candidate household pool to each target geography.

    Parameters
    ----------
    n_workers:
        Number of threads for parallel geography fitting.  Each geography's
        IPF is independent and numpy releases the GIL during ``bincount``
        and array arithmetic, so threading gives real concurrency.  Defaults
        to ``min(os.cpu_count(), 8)`` when ``None``.
    """

    if not households:
        raise ValueError("at least one candidate household row is required")
    missing_id_rows = [
        index
        for index, household in enumerate(households, start=2)
        if not household.get(household_id_column)
    ]
    if missing_id_rows:
        raise ValueError(
            f"household row {missing_id_rows[0]} requires {household_id_column!r}"
        )

    controls_for_geographies = controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    )
    if not controls_for_geographies:
        raise ValueError("controls contain no target geographies")

    # Pre-build the numpy index once for the whole candidate pool.
    # All geographies share the same dimension structure; only targets differ.
    first_margins = next(iter(controls_for_geographies.values())).to_ipf_margins()
    numpy_index = NumpyIPFIndex.build(households, first_margins)

    _n_workers = min(n_workers or (os.cpu_count() or 1), 8)

    def _fit_geo(
        geo_ctrl_pair: tuple[str, ControlTable],
    ) -> tuple[str, list[float], dict[str, Any]]:
        geography, geo_controls = geo_ctrl_pair
        ipf_margins = geo_controls.to_ipf_margins()
        # fit() returns a raw ndarray; keep it until compute_totals is done
        # to avoid a tolist() → asarray() round-trip in the report step.
        weights_np, converged, iterations, max_abs_error = numpy_index.fit(
            ipf_margins,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        # compute_totals uses numpy bincount, replacing the Python weighted_totals loop
        precomputed = numpy_index.compute_totals(weights_np)
        weights_list = weights_np.tolist()
        result = IPFResult(households, weights_list, converged, iterations, max_abs_error)
        report = build_ipf_fit_report(
            geo_controls, result, precomputed_totals=precomputed
        )
        return geography, weights_list, report

    weights_by_geography: dict[str, list[float]] = {}
    reports: dict[str, dict[str, Any]] = {}

    # ThreadPoolExecutor gives real concurrency here: numpy releases the GIL
    # during bincount and array arithmetic, letting multiple geography fits
    # overlap on separate CPU cores without any data races (each fit allocates
    # its own weights array; enc.cat_ids is shared read-only).
    with ThreadPoolExecutor(max_workers=_n_workers) as executor:
        for geography, weights_list, report in executor.map(
            _fit_geo, controls_for_geographies.items()
        ):
            weights_by_geography[geography] = weights_list
            reports[geography] = report

    return GeographyHouseholdFit(
        weights_by_geography=weights_by_geography,
        reports=reports,
    )


def realize_linked_geography_population(
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
) -> tuple[list[HouseholdRow], list[PersonRow]]:
    """Integerize geography weights and copy linked persons into households."""

    if not weights_by_geography:
        raise ValueError("at least one target geography is required")
    persons_by_household: dict[str, list[PersonRow]] = defaultdict(list)
    for person in persons:
        household_id = person.get(household_id_column, "")
        if household_id:
            persons_by_household[household_id].append(person)

    assigned_households: list[HouseholdRow] = []
    assigned_persons: list[PersonRow] = []
    next_household_number = 1
    next_person_number = 1
    for geography in sorted(weights_by_geography):
        weights = weights_by_geography[geography]
        if len(weights) != len(households):
            raise ValueError(
                f"weights for geography {geography!r} do not match household rows"
            )
        integer_weights = integerize_weights(weights)
        for candidate_index, repeats in enumerate(integer_weights):
            source_household = households[candidate_index]
            source_household_id = source_household[household_id_column]
            for _copy_index in range(repeats):
                assigned_household_id = f"{geography}-{next_household_number}"
                next_household_number += 1
                assigned_household = {
                    **source_household,
                    household_id_column: assigned_household_id,
                    geography_column: geography,
                    "source_candidate_household_id": source_household_id,
                }
                assigned_households.append(assigned_household)
                for source_person in persons_by_household.get(source_household_id, []):
                    assigned_person = {
                        **source_person,
                        person_id_column: f"{geography}-{next_person_number}",
                        household_id_column: assigned_household_id,
                        geography_column: geography,
                        "source_candidate_person_id": source_person.get(
                            person_id_column,
                            "",
                        ),
                    }
                    next_person_number += 1
                    assigned_persons.append(assigned_person)

    return assigned_households, assigned_persons


def calibrate_linked_household_csvs(
    *,
    households_path: Path,
    persons_path: Path,
    controls_path: Path,
    geography_dimension: str,
    geography_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None = None,
    report_out: Path | None = None,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
    pool_size: int | None = None,
    n_workers: int | None = None,
) -> dict[str, Any]:
    """Calibrate linked household/person CSVs to geography controls.

    Parameters
    ----------
    pool_size:
        Maximum number of candidate households to use.  When ``None`` the full
        pool is used.  Values of 5 000–10 000 reproduce aggregate statistics
        (ownership rates, household-size distributions) with near-identical
        accuracy to the full pool while cutting synthesis time by 10× or more.
        Use the full pool only when individual-household uniqueness matters.
    n_workers:
        Number of threads for parallel geography fitting.  Defaults to
        ``min(os.cpu_count(), 8)`` when ``None``.
    """

    # Read all three inputs concurrently — they are I/O-bound and independent.
    with ThreadPoolExecutor(max_workers=3) as _io_ex:
        _hh_f = _io_ex.submit(_read_csv_rows, households_path)
        _p_f = _io_ex.submit(_read_csv_rows, persons_path)
        _ctrl_f = _io_ex.submit(read_control_table, controls_path)
        households = _hh_f.result()
        persons = _p_f.result()
        controls = _ctrl_f.result()

    if pool_size is not None and pool_size < len(households):
        households, persons = _subsample_candidates(
            households,
            persons,
            pool_size,
            household_id_column=household_id_column,
        )

    fit = fit_households_by_geography(
        households,
        controls,
        geography_dimension=geography_dimension,
        household_id_column=household_id_column,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
        n_workers=n_workers,
    )
    realization = _write_realized_population_to_csv(
        households_out,
        persons_out,
        households,
        persons,
        weights_by_geography=fit.weights_by_geography,
        geography_column=geography_column,
        household_id_column=household_id_column,
        person_id_column=person_id_column,
    )

    if weights_out:
        _write_weights_csv(
            weights_out,
            households,
            fit.weights_by_geography,
            household_id_column=household_id_column,
            integer_weights_by_geography=realization["integer_weights"],
        )

    summary = _small_area_report(
        households=households,
        persons=persons,
        assigned_household_count=realization["assigned_households"],
        assigned_person_count=realization["assigned_persons"],
        assigned_households_by_geography=realization["geographies"],
        fit=fit,
        geography_dimension=geography_dimension,
        geography_column=geography_column,
    )
    if report_out:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _control_dimensions(margins: Sequence[ControlMargin]) -> tuple[str, ...]:
    seen: list[str] = []
    for margin in margins:
        for dimension in margin.dimensions:
            if dimension not in seen:
                seen.append(dimension)
    return tuple(seen)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, rows: Sequence[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"no rows to write to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _ordered_fieldnames(rows)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _subsample_candidates(
    households: list[HouseholdRow],
    persons: list[PersonRow],
    pool_size: int,
    *,
    household_id_column: str,
    seed: int = 42,
) -> tuple[list[HouseholdRow], list[PersonRow]]:
    """Return a random subsample of the candidate pool with consistent persons."""
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(households), size=pool_size, replace=False)
    selected_hh = [households[i] for i in indices]
    selected_ids = {hh[household_id_column] for hh in selected_hh}
    selected_persons = [
        p for p in persons if p.get(household_id_column, "") in selected_ids
    ]
    return selected_hh, selected_persons


def _write_realized_population_to_csv(
    households_path: Path,
    persons_path: Path,
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str,
    person_id_column: str,
) -> dict[str, Any]:
    if not households:
        raise ValueError("at least one candidate household row is required")

    # --- Build expand index across all geographies ---
    # Integerize once per geography; cache the result so _write_weights_csv
    # can reuse it without re-calling integerize_weights.
    integer_weights: dict[str, list[int]] = {}
    idx_parts: list[np.ndarray] = []
    geo_parts: list[np.ndarray] = []
    for geography in sorted(weights_by_geography):
        weights = weights_by_geography[geography]
        if len(weights) != len(households):
            raise ValueError(
                f"weights for geography {geography!r} do not match household rows"
            )
        int_w = integerize_weights(weights)
        integer_weights[geography] = int_w
        counts = np.array(int_w, dtype=np.int32)
        nonzero = np.where(counts > 0)[0]
        repeated = np.repeat(nonzero, counts[nonzero])
        idx_parts.append(repeated)
        geo_parts.append(np.full(len(repeated), geography, dtype=object))

    all_idxs = np.concatenate(idx_parts)       # (total_households,)
    all_geos = np.concatenate(geo_parts)        # (total_households,)
    n_hh = len(all_idxs)

    # --- Expand households ---
    df_hh = pd.DataFrame(households)
    df_hh_exp = df_hh.iloc[all_idxs].reset_index(drop=True)
    df_hh_exp["source_candidate_household_id"] = df_hh_exp[household_id_column].values
    df_hh_exp[geography_column] = all_geos

    # Build sequential IDs with numpy string ops — 2× faster than a Python
    # f-string loop over millions of rows.
    seq = np.arange(1, n_hh + 1, dtype=np.int64)
    sep = np.full(n_hh, "-", dtype="U1")
    new_hh_ids = np.char.add(np.char.add(all_geos.astype("U"), sep), seq.astype("U"))
    df_hh_exp[household_id_column] = new_hh_ids
    df_hh_exp["_new_hh_id"] = new_hh_ids
    df_hh_exp["_cand_idx"] = all_idxs

    hh_extra = [c for c in [geography_column, "source_candidate_household_id"]
                if c not in df_hh.columns]
    hh_cols = list(df_hh.columns) + hh_extra

    households_path.parent.mkdir(parents=True, exist_ok=True)
    df_hh_exp[hh_cols].to_csv(households_path, index=False)

    # --- Expand persons ---
    df_p = pd.DataFrame(persons)
    if persons:
        df_hh_idx = df_hh[[household_id_column]].copy()
        df_hh_idx["_cand_idx"] = np.arange(len(df_hh), dtype=np.int32)
        df_p_idx = df_p.merge(df_hh_idx, on=household_id_column, how="left")

        df_p_exp = df_p_idx.merge(
            df_hh_exp[["_cand_idx", "_new_hh_id", geography_column]],
            on="_cand_idx",
            how="inner",
        )
        df_p_exp["source_candidate_person_id"] = df_p_exp[person_id_column]
        df_p_exp[household_id_column] = df_p_exp["_new_hh_id"]
        geo_col = (
            f"{geography_column}_y"
            if f"{geography_column}_x" in df_p_exp.columns
            else geography_column
        )
        df_p_exp[geography_column] = df_p_exp[geo_col]
        n_p = len(df_p_exp)
        seq_p = np.arange(1, n_p + 1, dtype=np.int64)
        sep_p = np.full(n_p, "-", dtype="U1")
        df_p_exp[person_id_column] = np.char.add(
            np.char.add(df_p_exp[geography_column].values.astype("U"), sep_p),
            seq_p.astype("U"),
        )

        p_extra = [c for c in [geography_column, "source_candidate_person_id"]
                   if c not in df_p.columns]
        p_cols = [c for c in list(df_p.columns) + p_extra
                  if c in df_p_exp.columns]
        persons_path.parent.mkdir(parents=True, exist_ok=True)
        df_p_exp[p_cols].to_csv(persons_path, index=False)
        assigned_persons = n_p
    else:
        persons_path.parent.mkdir(parents=True, exist_ok=True)
        persons_path.write_text("")
        assigned_persons = 0

    assigned_by_geography = df_hh_exp[geography_column].value_counts().to_dict()

    return {
        "assigned_households": n_hh,
        "assigned_persons": assigned_persons,
        "geographies": assigned_by_geography,
        "integer_weights": integer_weights,
    }


def _write_weights_csv(
    path: Path,
    households: Sequence[HouseholdRow],
    weights_by_geography: dict[str, list[float]],
    *,
    household_id_column: str,
    integer_weights_by_geography: dict[str, list[int]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "target_geography",
                "source_candidate_household_id",
                "weight",
                "integer_weight",
            ),
        )
        writer.writeheader()
        for geography in sorted(weights_by_geography):
            weights = weights_by_geography[geography]
            if integer_weights_by_geography is not None:
                integer_weights = integer_weights_by_geography[geography]
            else:
                integer_weights = integerize_weights(weights)
            for household, weight, integer_weight in zip(
                households,
                weights,
                integer_weights,
                strict=True,
            ):
                writer.writerow(
                    {
                        "target_geography": geography,
                        "source_candidate_household_id": household[household_id_column],
                        "weight": _format_float(weight),
                        "integer_weight": integer_weight,
                    }
                )


def _small_area_report(
    *,
    households: Sequence[HouseholdRow],
    persons: Sequence[PersonRow],
    assigned_household_count: int,
    assigned_person_count: int,
    assigned_households_by_geography: dict[str, int],
    fit: GeographyHouseholdFit,
    geography_dimension: str,
    geography_column: str,
) -> dict[str, Any]:
    return {
        "schema_version": "synthpopcan-small-area-linked-calibration-v1",
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "candidate_households": len(households),
        "candidate_persons": len(persons),
        "assigned_households": assigned_household_count,
        "assigned_persons": assigned_person_count,
        "geographies": {
            geography: {
                "converged": report["converged"],
                "iterations": report["iterations"],
                "max_abs_error": report["max_abs_error"],
                "assigned_households": assigned_households_by_geography.get(
                    geography,
                    0,
                ),
            }
            for geography, report in sorted(fit.reports.items())
        },
    }


def _ordered_fieldnames(rows: Sequence[dict[str, str]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for fieldname in row:
            if fieldname not in fieldnames:
                fieldnames.append(fieldname)
    return fieldnames


def _format_float(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.12g}"
