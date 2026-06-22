"""Compare experimental IPF update backends against the current implementation."""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter

from rich.console import Console
from rich.table import Table

from synthpopcan.benchmarks import build_ipf_benchmark_cases
from synthpopcan.ipf import IPFMargin, IPFResult, Record, fit_ipf


@dataclass(frozen=True)
class EncodedNumpyMargin:
    codes: object
    active: object
    targets: object


@dataclass(frozen=True)
class EncodedSparseMargin:
    matrix: object
    targets: object


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-records",
        default=50_000,
        type=int,
        help="Seed rows per benchmark case.",
    )
    parser.add_argument(
        "--case",
        choices=[
            "easy_balanced",
            "moderate_three_margin",
            "high_cardinality_inconsistent",
            "all",
        ],
        default="all",
        help="Benchmark case to run.",
    )
    args = parser.parse_args()

    cases = build_ipf_benchmark_cases(seed_records=args.seed_records)
    if args.case != "all":
        cases = [case for case in cases if case.name == args.case]

    rows: list[dict[str, object]] = []
    for case in cases:
        rows.append(run_current_backend(case))
        rows.append(run_numpy_backend(case))
        rows.append(run_scipy_sparse_backend(case))
        rows.append(run_polars_probe(case))

    table = Table(title="Experimental IPF Backend Benchmarks")
    table.add_column("Case")
    table.add_column("Backend")
    table.add_column("Status")
    table.add_column("Iterations", justify="right")
    table.add_column("Converged")
    table.add_column("Max Error", justify="right")
    table.add_column("Fit Seconds", justify="right")
    table.add_column("Note")

    for row in rows:
        table.add_row(
            str(row["case"]),
            str(row["backend"]),
            str(row["status"]),
            format_optional_int(row.get("iterations")),
            str(row.get("converged", "")),
            format_optional_float(row.get("max_abs_error")),
            format_optional_float(row.get("fit_seconds")),
            str(row.get("note", "")),
        )

    Console(width=140).print(table)
    return 0


def run_current_backend(case) -> dict[str, object]:
    start = perf_counter()
    result = fit_ipf(
        case.records,
        case.margins,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return result_row(case.name, "current_python", perf_counter() - start, result)


def run_numpy_backend(case) -> dict[str, object]:
    if importlib.util.find_spec("numpy") is None:
        return unavailable_row(case.name, "numpy_bincount", "NumPy is not installed.")
    import numpy as np

    start = perf_counter()
    encoded = encode_numpy_margins(case.records, case.margins, np)
    weights = np.ones(len(case.records), dtype=np.float64)
    result = fit_numpy_encoded(
        case.records,
        weights,
        encoded,
        np,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return result_row(case.name, "numpy_bincount", perf_counter() - start, result)


def run_scipy_sparse_backend(case) -> dict[str, object]:
    if importlib.util.find_spec("numpy") is None:
        return unavailable_row(case.name, "scipy_csr", "NumPy is not installed.")
    if importlib.util.find_spec("scipy") is None:
        return unavailable_row(case.name, "scipy_csr", "SciPy is not installed.")
    import numpy as np
    from scipy import sparse

    start = perf_counter()
    encoded = encode_sparse_margins(case.records, case.margins, np, sparse)
    weights = np.ones(len(case.records), dtype=np.float64)
    result = fit_sparse_encoded(
        case.records,
        weights,
        encoded,
        np,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return result_row(case.name, "scipy_csr", perf_counter() - start, result)


def run_polars_probe(case) -> dict[str, object]:
    if importlib.util.find_spec("polars") is None:
        return unavailable_row(
            case.name,
            "polars_groupby",
            "Polars is not installed; likely useful for CSV/table prep, "
            "not IPF updates.",
        )
    import polars as pl

    start = perf_counter()
    result = fit_polars_groupby(
        case.records,
        case.margins,
        pl,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return result_row(case.name, "polars_groupby", perf_counter() - start, result)


def encode_numpy_margins(
    records: Sequence[Record],
    margins: Sequence[IPFMargin],
    np,
) -> list[EncodedNumpyMargin]:
    encoded: list[EncodedNumpyMargin] = []
    for margin in margins:
        target_keys = list(margin.targets)
        key_to_code = {key: index for index, key in enumerate(target_keys)}
        codes = np.full(len(records), -1, dtype=np.int64)
        for record_index, record in enumerate(records):
            key = tuple(str(record[dimension]) for dimension in margin.dimensions)
            if key in key_to_code:
                codes[record_index] = key_to_code[key]
        active = codes >= 0
        for key, target in margin.targets.items():
            if target > 0 and not np.any(codes == key_to_code[key]):
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )
        encoded.append(
            EncodedNumpyMargin(
                codes=codes,
                active=active,
                targets=np.array(
                    [margin.targets[key] for key in target_keys],
                    dtype=np.float64,
                ),
            )
        )
    return encoded


def encode_sparse_margins(
    records: Sequence[Record],
    margins: Sequence[IPFMargin],
    np,
    sparse,
) -> list[EncodedSparseMargin]:
    encoded: list[EncodedSparseMargin] = []
    for margin in margins:
        target_keys = list(margin.targets)
        key_to_row = {key: index for index, key in enumerate(target_keys)}
        rows: list[int] = []
        cols: list[int] = []
        for record_index, record in enumerate(records):
            key = tuple(str(record[dimension]) for dimension in margin.dimensions)
            if key in key_to_row:
                rows.append(key_to_row[key])
                cols.append(record_index)
        data = np.ones(len(rows), dtype=np.float64)
        matrix = sparse.csr_matrix(
            (data, (rows, cols)),
            shape=(len(target_keys), len(records)),
            dtype=np.float64,
        )
        for key, target in margin.targets.items():
            row = key_to_row[key]
            if target > 0 and matrix[row].nnz == 0:
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )
        encoded.append(
            EncodedSparseMargin(
                matrix=matrix,
                targets=np.array(
                    [margin.targets[key] for key in target_keys],
                    dtype=np.float64,
                ),
            )
        )
    return encoded


def fit_numpy_encoded(
    records: Sequence[Record],
    weights,
    encoded_margins: Sequence[EncodedNumpyMargin],
    np,
    *,
    max_iterations: int,
    tolerance: float,
) -> IPFResult:
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for encoded in encoded_margins:
            active_codes = encoded.codes[encoded.active]
            current = np.bincount(
                active_codes,
                weights=weights[encoded.active],
                minlength=len(encoded.targets),
            )
            ratio = np.divide(
                encoded.targets,
                current,
                out=np.ones_like(encoded.targets),
                where=current != 0,
            )
            weights[encoded.active] *= ratio[active_codes]
        max_abs_error = numpy_max_abs_error(weights, encoded_margins, np)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights.tolist(), True, iteration, max_abs_error)
    return IPFResult(records, weights.tolist(), False, max_iterations, max_abs_error)


def numpy_max_abs_error(
    weights,
    encoded_margins: Sequence[EncodedNumpyMargin],
    np,
) -> float:
    max_abs_error = 0.0
    for encoded in encoded_margins:
        current = np.bincount(
            encoded.codes[encoded.active],
            weights=weights[encoded.active],
            minlength=len(encoded.targets),
        )
        max_abs_error = max(
            max_abs_error,
            float(np.max(np.abs(current - encoded.targets))),
        )
    return max_abs_error


def fit_sparse_encoded(
    records: Sequence[Record],
    weights,
    encoded_margins: Sequence[EncodedSparseMargin],
    np,
    *,
    max_iterations: int,
    tolerance: float,
) -> IPFResult:
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for encoded in encoded_margins:
            current = encoded.matrix @ weights
            ratio = np.divide(
                encoded.targets,
                current,
                out=np.ones_like(encoded.targets),
                where=current != 0,
            )
            update = encoded.matrix.T @ ratio
            active = update != 0
            weights[active] *= update[active]
        max_abs_error = sparse_max_abs_error(weights, encoded_margins, np)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights.tolist(), True, iteration, max_abs_error)
    return IPFResult(records, weights.tolist(), False, max_iterations, max_abs_error)


def fit_polars_groupby(
    records: Sequence[Record],
    margins: Sequence[IPFMargin],
    pl,
    *,
    max_iterations: int,
    tolerance: float,
) -> IPFResult:
    frame = pl.DataFrame(
        [{str(key): str(value) for key, value in record.items()} for record in records]
    ).with_columns(pl.lit(1.0).alias("_weight"))

    target_frames = [polars_target_frame(margin, pl) for margin in margins]
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for margin, targets in zip(margins, target_frames, strict=True):
            dimensions = list(margin.dimensions)
            current = frame.group_by(dimensions).agg(
                pl.col("_weight").sum().alias("_current")
            )
            ratios = targets.join(current, on=dimensions, how="left").with_columns(
                (pl.col("_target") / pl.col("_current")).alias("_ratio")
            )
            frame = (
                frame.join(
                    ratios.select([*dimensions, "_ratio"]),
                    on=dimensions,
                    how="left",
                )
                .with_columns(
                    pl.when(pl.col("_ratio").is_not_null())
                    .then(pl.col("_weight") * pl.col("_ratio"))
                    .otherwise(pl.col("_weight"))
                    .alias("_weight")
                )
                .drop("_ratio")
            )
        max_abs_error = polars_max_abs_error(frame, margins, target_frames, pl)
        if max_abs_error <= tolerance:
            return IPFResult(
                records,
                frame["_weight"].to_list(),
                True,
                iteration,
                max_abs_error,
            )
    return IPFResult(
        records,
        frame["_weight"].to_list(),
        False,
        max_iterations,
        max_abs_error,
    )


def polars_target_frame(margin: IPFMargin, pl):
    return pl.DataFrame(
        [
            {
                **{
                    dimension: key[index]
                    for index, dimension in enumerate(margin.dimensions)
                },
                "_target": target,
            }
            for key, target in margin.targets.items()
        ]
    )


def polars_max_abs_error(
    frame,
    margins: Sequence[IPFMargin],
    target_frames: Sequence[object],
    pl,
) -> float:
    max_abs_error = 0.0
    for margin, targets in zip(margins, target_frames, strict=True):
        dimensions = list(margin.dimensions)
        current = frame.group_by(dimensions).agg(
            pl.col("_weight").sum().alias("_current")
        )
        residuals = targets.join(current, on=dimensions, how="left").with_columns(
            (pl.col("_current").fill_null(0.0) - pl.col("_target"))
            .abs()
            .alias("_abs_error")
        )
        max_abs_error = max(max_abs_error, float(residuals["_abs_error"].max()))
    return max_abs_error


def sparse_max_abs_error(
    weights,
    encoded_margins: Sequence[EncodedSparseMargin],
    np,
) -> float:
    max_abs_error = 0.0
    for encoded in encoded_margins:
        current = encoded.matrix @ weights
        max_abs_error = max(
            max_abs_error,
            float(np.max(np.abs(current - encoded.targets))),
        )
    return max_abs_error


def result_row(
    case_name: str,
    backend: str,
    fit_seconds: float,
    result: IPFResult,
) -> dict[str, object]:
    return {
        "case": case_name,
        "backend": backend,
        "status": "ok",
        "iterations": result.iterations,
        "converged": result.converged,
        "max_abs_error": result.max_abs_error,
        "fit_seconds": fit_seconds,
        "note": "",
    }


def unavailable_row(case_name: str, backend: str, note: str) -> dict[str, object]:
    return {
        "case": case_name,
        "backend": backend,
        "status": "skipped",
        "note": note,
    }


def format_optional_int(value: object) -> str:
    return "" if value is None else f"{int(value):,}"


def format_optional_float(value: object) -> str:
    return "" if value is None else f"{float(value):.6g}"


if __name__ == "__main__":
    raise SystemExit(main())
