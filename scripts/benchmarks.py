"""Developer benchmark tools for SynthPopCan.

Usage::

    uv run python scripts/benchmarks.py ipf
    uv run python scripts/benchmarks.py ipf-backends --case easy_balanced
    uv run python scripts/benchmarks.py model-run --out-dir /tmp/model-bench
    uv run python scripts/benchmarks.py tree-linked SOURCE --out-dir /tmp/bench
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter, sleep

import click
from rich.console import Console

from synthpopcan.benchmarks import (
    PROVINCE_SCALE_SMALL_AREA_BUDGET,
    build_ipf_benchmark_cases,
    build_small_area_benchmark_fixture,
    run_ipf_benchmarks,
    run_small_area_benchmark,
)
from synthpopcan.console import make_table
from synthpopcan.ipf import IPFResult, fit_ipf
from synthpopcan.jobs import JobManager
from synthpopcan.runs import RunStore
from synthpopcan.tree_benchmark import run_linked_tree_benchmark


@click.group()
def cli() -> None:
    """Developer benchmark tools."""


# ---------------------------------------------------------------------------
# ipf
# ---------------------------------------------------------------------------


@cli.command("ipf")
@click.option(
    "--seed-records",
    default=50_000,
    show_default=True,
    type=int,
    help="Seed rows per benchmark case.",
)
def benchmark_ipf(seed_records: int) -> None:
    """Run IPF benchmark fixtures."""
    rows = run_ipf_benchmarks(seed_records=seed_records)
    table = make_table(title="IPF Benchmarks")
    table.add_column("Case")
    table.add_column("Seed Rows", justify="right")
    table.add_column("Cells", justify="right")
    table.add_column("Iterations", justify="right")
    table.add_column("Converged")
    table.add_column("Max Error", justify="right")
    table.add_column("Fit Seconds", justify="right")
    table.add_column("Expanded Rows", justify="right")
    table.add_column("Hint")
    for row in rows:
        table.add_row(
            str(row["case"]),
            _fmt_int(row["seed_records"]),
            _fmt_int(row["margin_cells"]),
            _fmt_int(row["iterations"]),
            str(row["converged"]),
            _fmt_float(row["max_abs_error"]),
            _fmt_float(row["fit_seconds"]),
            _fmt_int(row["expanded_rows"]),
            str(row["dependency_hint"]),
        )
    Console(width=120).print(table)


@cli.command("small-area")
@click.option("--candidate-households", default=10_000, show_default=True, type=int)
@click.option("--target-geographies", default=100, show_default=True, type=int)
@click.option(
    "--target-households-per-geography",
    default=4_000,
    show_default=True,
    type=int,
)
@click.option(
    "--province-scale",
    is_flag=True,
    help="Use the tracked province-scale calibration budget profile.",
)
@click.option("--workers", default=None, type=int)
def benchmark_small_area(
    candidate_households: int,
    target_geographies: int,
    target_households_per_geography: int,
    province_scale: bool,
    workers: int | None,
) -> None:
    """Run the repeated-geography small-area calibration benchmark."""
    budget = None
    if province_scale:
        budget = PROVINCE_SCALE_SMALL_AREA_BUDGET
        candidate_households = budget.candidate_households
        target_geographies = budget.target_geographies
        target_households_per_geography = (
            budget.target_households // budget.target_geographies
        )
    households, controls = build_small_area_benchmark_fixture(
        candidate_households=candidate_households,
        target_geographies=target_geographies,
        target_households_per_geography=target_households_per_geography,
    )
    result = run_small_area_benchmark(
        households,
        controls,
        geography_dimension="geo",
        n_workers=workers,
    )
    table = make_table(title="Small-Area Calibration Benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Candidate households", _fmt_int(result["candidate_households"]))
    table.add_row("Target geographies", _fmt_int(result["target_geographies"]))
    table.add_row("Target households", _fmt_int(result["target_households"]))
    table.add_row("Retained weight cells", _fmt_int(result["weight_cells"]))
    table.add_row(
        "Estimated retained weights",
        _fmt_bytes(result["estimated_retained_weight_bytes"]),
    )
    table.add_row("Fit seconds", _fmt_float(result["fit_seconds"]))
    table.add_row(
        "Converged geographies",
        _fmt_int(result["converged_geographies"]),
    )
    if budget is not None:
        within_budget = (
            float(result["fit_seconds"]) <= budget.max_fit_seconds
            and int(result["estimated_retained_weight_bytes"])
            <= budget.max_retained_weight_bytes
        )
        table.add_row("Province-scale budget", "pass" if within_budget else "fail")
    Console(width=120).print(table)


@cli.command("model-run")
@click.option(
    "--out-dir",
    required=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Durable benchmark workspace.",
)
@click.option("--households", default=50_000, show_default=True, type=int)
@click.option("--chunk-size", default=1_000, show_default=True, type=int)
@click.option(
    "--province-scale",
    is_flag=True,
    help="Opt in to 4.5 million households using the production job path.",
)
def benchmark_model_run(
    out_dir: Path,
    households: int,
    chunk_size: int,
    province_scale: bool,
) -> None:
    """Run prepared-model generation through the durable web-app job path."""
    if province_scale:
        households = 4_500_000
    if households <= 0 or chunk_size <= 0:
        raise click.UsageError("households and chunk size must be positive")
    estimated_bytes = households * 4 * 256
    out_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(out_dir).free < estimated_bytes * 2:
        raise click.ClickException(
            "insufficient disk headroom for the requested prepared-model run"
        )

    store = RunStore(out_dir)
    manifest = store.create_model_run(
        {
            "workflow": "model",
            "inputs": {"model_id": "demo-linked-household-person"},
            "options": {
                "households": households,
                "conditions": {"geo": "Demo North"},
                "random_seed": 13,
                "chunk_size": chunk_size,
            },
        }
    )
    run_id = str(manifest["run_id"])
    manager = JobManager(store)
    start = perf_counter()
    try:
        manager.enqueue(run_id)
        while True:
            manifest = store.load_run(run_id)
            if manifest["status"] in {
                "succeeded",
                "failed",
                "cancelled",
                "interrupted",
            }:
                break
            sleep(0.05)
    finally:
        manager.shutdown()
    elapsed = perf_counter() - start
    if manifest["status"] != "succeeded":
        raise click.ClickException(
            f"prepared-model benchmark ended in state {manifest['status']}"
        )

    table = make_table(title="Durable Prepared-Model Benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Run ID", run_id)
    table.add_row("Households", _fmt_int(manifest["summary"]["generated_households"]))
    table.add_row("Persons", _fmt_int(manifest["summary"]["generated_persons"]))
    table.add_row("Chunk size", _fmt_int(chunk_size))
    table.add_row("Elapsed seconds", _fmt_float(elapsed))
    table.add_row(
        "Artifact bytes",
        _fmt_bytes(sum(int(item["byte_size"]) for item in manifest["artifacts"])),
    )
    table.add_row("Workspace", str(out_dir))
    Console(width=120).print(table)


# ---------------------------------------------------------------------------
# ipf-backends
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EncodedNumpyMargin:
    codes: object
    active: object
    targets: object


@dataclass(frozen=True)
class _EncodedSparseMargin:
    matrix: object
    targets: object


@cli.command("ipf-backends")
@click.option(
    "--seed-records",
    default=50_000,
    show_default=True,
    type=int,
    help="Seed rows per benchmark case.",
)
@click.option(
    "--case",
    default="all",
    show_default=True,
    type=click.Choice(
        [
            "easy_balanced",
            "moderate_three_margin",
            "high_cardinality_inconsistent",
            "all",
        ]
    ),
    help="Benchmark case to run.",
)
def benchmark_ipf_backends(seed_records: int, case: str) -> None:
    """Compare experimental IPF backends against the current implementation."""
    cases = build_ipf_benchmark_cases(seed_records=seed_records)
    if case != "all":
        cases = [c for c in cases if c.name == case]

    rows: list[dict[str, object]] = []
    for c in cases:
        rows.append(_run_current_backend(c))
        rows.append(_run_numpy_backend(c))
        rows.append(_run_scipy_sparse_backend(c))
        rows.append(_run_polars_probe(c))

    table = make_table(title="Experimental IPF Backend Benchmarks")
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
            _fmt_opt_int(row.get("iterations")),
            str(row.get("converged", "")),
            _fmt_opt_float(row.get("max_abs_error")),
            _fmt_opt_float(row.get("fit_seconds")),
            str(row.get("note", "")),
        )
    Console(width=140).print(table)


def _run_current_backend(case) -> dict[str, object]:
    start = perf_counter()
    result = fit_ipf(
        case.records,
        case.margins,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return _result_row(case.name, "current_python", perf_counter() - start, result)


def _run_numpy_backend(case) -> dict[str, object]:
    if importlib.util.find_spec("numpy") is None:
        return _unavailable_row(case.name, "numpy_bincount", "NumPy is not installed.")
    import numpy as np  # type: ignore[import-not-found]

    start = perf_counter()
    encoded = _encode_numpy_margins(case.records, case.margins, np)
    weights = np.ones(len(case.records), dtype=np.float64)
    result = _fit_numpy_encoded(
        case.records,
        weights,
        encoded,
        np,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return _result_row(case.name, "numpy_bincount", perf_counter() - start, result)


def _run_scipy_sparse_backend(case) -> dict[str, object]:
    if importlib.util.find_spec("numpy") is None:
        return _unavailable_row(case.name, "scipy_csr", "NumPy is not installed.")
    if importlib.util.find_spec("scipy") is None:
        return _unavailable_row(case.name, "scipy_csr", "SciPy is not installed.")
    import numpy as np  # type: ignore[import-not-found]
    from scipy import sparse  # type: ignore[import-not-found]

    start = perf_counter()
    encoded = _encode_sparse_margins(case.records, case.margins, np, sparse)
    weights = np.ones(len(case.records), dtype=np.float64)
    result = _fit_sparse_encoded(
        case.records,
        weights,
        encoded,
        np,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return _result_row(case.name, "scipy_csr", perf_counter() - start, result)


def _run_polars_probe(case) -> dict[str, object]:
    if importlib.util.find_spec("polars") is None:
        return _unavailable_row(
            case.name,
            "polars_groupby",
            "Polars is not installed; likely useful for CSV/table prep, "
            "not IPF updates.",
        )
    import polars as pl  # type: ignore[import-not-found]

    start = perf_counter()
    result = _fit_polars_groupby(
        case.records,
        case.margins,
        pl,
        max_iterations=case.max_iterations,
        tolerance=case.tolerance,
    )
    return _result_row(case.name, "polars_groupby", perf_counter() - start, result)


def _encode_numpy_margins(records, margins, np):
    encoded = []
    for margin in margins:
        target_keys = list(margin.targets)
        key_to_code = {key: i for i, key in enumerate(target_keys)}
        codes = np.full(len(records), -1, dtype=np.int64)
        for ri, record in enumerate(records):
            key = tuple(str(record[d]) for d in margin.dimensions)
            if key in key_to_code:
                codes[ri] = key_to_code[key]
        active = codes >= 0
        for key, target in margin.targets.items():
            if target > 0 and not np.any(codes == key_to_code[key]):
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )
        encoded.append(
            _EncodedNumpyMargin(
                codes=codes,
                active=active,
                targets=np.array(
                    [margin.targets[k] for k in target_keys], dtype=np.float64
                ),
            )
        )
    return encoded


def _encode_sparse_margins(records, margins, np, sparse):
    encoded = []
    for margin in margins:
        target_keys = list(margin.targets)
        key_to_row = {key: i for i, key in enumerate(target_keys)}
        rows_idx, cols_idx = [], []
        for ri, record in enumerate(records):
            key = tuple(str(record[d]) for d in margin.dimensions)
            if key in key_to_row:
                rows_idx.append(key_to_row[key])
                cols_idx.append(ri)
        data = np.ones(len(rows_idx), dtype=np.float64)
        matrix = sparse.csr_matrix(
            (data, (rows_idx, cols_idx)),
            shape=(len(target_keys), len(records)),
            dtype=np.float64,
        )
        for key, target in margin.targets.items():
            if target > 0 and matrix[key_to_row[key]].nnz == 0:
                raise ValueError(
                    f"margin {margin.dimensions!r} target {key!r} has no seed records"
                )
        encoded.append(
            _EncodedSparseMargin(
                matrix=matrix,
                targets=np.array(
                    [margin.targets[k] for k in target_keys], dtype=np.float64
                ),
            )
        )
    return encoded


def _fit_numpy_encoded(
    records, weights, encoded_margins, np, *, max_iterations, tolerance
):
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for enc in encoded_margins:
            active_codes = enc.codes[enc.active]
            current = np.bincount(
                active_codes, weights=weights[enc.active], minlength=len(enc.targets)
            )
            ratio = np.divide(
                enc.targets, current, out=np.ones_like(enc.targets), where=current != 0
            )
            weights[enc.active] *= ratio[active_codes]
        max_abs_error = _numpy_max_abs_error(weights, encoded_margins, np)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights.tolist(), True, iteration, max_abs_error)
    return IPFResult(records, weights.tolist(), False, max_iterations, max_abs_error)


def _numpy_max_abs_error(weights, encoded_margins, np):
    err = 0.0
    for enc in encoded_margins:
        current = np.bincount(
            enc.codes[enc.active],
            weights=weights[enc.active],
            minlength=len(enc.targets),
        )
        err = max(err, float(np.max(np.abs(current - enc.targets))))
    return err


def _fit_sparse_encoded(
    records, weights, encoded_margins, np, *, max_iterations, tolerance
):
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for enc in encoded_margins:
            current = enc.matrix @ weights
            ratio = np.divide(
                enc.targets, current, out=np.ones_like(enc.targets), where=current != 0
            )
            update = enc.matrix.T @ ratio
            active = update != 0
            weights[active] *= update[active]
        max_abs_error = _sparse_max_abs_error(weights, encoded_margins, np)
        if max_abs_error <= tolerance:
            return IPFResult(records, weights.tolist(), True, iteration, max_abs_error)
    return IPFResult(records, weights.tolist(), False, max_iterations, max_abs_error)


def _sparse_max_abs_error(weights, encoded_margins, np):
    err = 0.0
    for enc in encoded_margins:
        current = enc.matrix @ weights
        err = max(err, float(np.max(np.abs(current - enc.targets))))
    return err


def _fit_polars_groupby(records, margins, pl, *, max_iterations, tolerance):
    frame = pl.DataFrame(
        [{str(k): str(v) for k, v in r.items()} for r in records]
    ).with_columns(pl.lit(1.0).alias("_weight"))
    target_frames = [_polars_target_frame(m, pl) for m in margins]
    max_abs_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for margin, targets in zip(margins, target_frames, strict=True):
            dims = list(margin.dimensions)
            current = frame.group_by(dims).agg(
                pl.col("_weight").sum().alias("_current")
            )
            ratios = targets.join(current, on=dims, how="left").with_columns(
                (pl.col("_target") / pl.col("_current")).alias("_ratio")
            )
            frame = (
                frame.join(ratios.select([*dims, "_ratio"]), on=dims, how="left")
                .with_columns(
                    pl.when(pl.col("_ratio").is_not_null())
                    .then(pl.col("_weight") * pl.col("_ratio"))
                    .otherwise(pl.col("_weight"))
                    .alias("_weight")
                )
                .drop("_ratio")
            )
        max_abs_error = _polars_max_abs_error(frame, margins, target_frames, pl)
        if max_abs_error <= tolerance:
            return IPFResult(
                records, frame["_weight"].to_list(), True, iteration, max_abs_error
            )
    return IPFResult(
        records, frame["_weight"].to_list(), False, max_iterations, max_abs_error
    )


def _polars_target_frame(margin, pl):
    return pl.DataFrame(
        [
            {**{d: key[i] for i, d in enumerate(margin.dimensions)}, "_target": target}
            for key, target in margin.targets.items()
        ]
    )


def _polars_max_abs_error(frame, margins, target_frames, pl):
    err = 0.0
    for margin, targets in zip(margins, target_frames, strict=True):
        dims = list(margin.dimensions)
        current = frame.group_by(dims).agg(pl.col("_weight").sum().alias("_current"))
        residuals = targets.join(current, on=dims, how="left").with_columns(
            (pl.col("_current").fill_null(0.0) - pl.col("_target"))
            .abs()
            .alias("_abs_error")
        )
        err = max(err, float(residuals["_abs_error"].max()))
    return err


def _result_row(case_name, backend, fit_seconds, result):
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


def _unavailable_row(case_name, backend, note):
    return {"case": case_name, "backend": backend, "status": "skipped", "note": note}


# ---------------------------------------------------------------------------
# tree-linked
# ---------------------------------------------------------------------------


@cli.command("tree-linked")
@click.argument("source", type=click.Path(path_type=Path))
@click.option("--out-dir", required=True, type=click.Path(path_type=Path))
@click.option(
    "--household-target-columns",
    default="household_size,TENUR",
    show_default=True,
    help="Comma-separated household columns to generate.",
)
@click.option(
    "--household-conditioning-columns",
    default="PR",
    show_default=True,
    help="Comma-separated household conditioning columns.",
)
@click.option(
    "--person-target-columns",
    default="AGEGRP,SEX",
    show_default=True,
    help="Comma-separated person columns to generate.",
)
@click.option(
    "--person-conditioning-columns",
    default="PR,household_size,TENUR",
    show_default=True,
    help="Comma-separated person conditioning columns.",
)
@click.option(
    "--suggested-blocks",
    is_flag=True,
    help="Use named suggested tree-column blocks instead of manual column lists.",
)
@click.option("--household-block", default="household_core", show_default=True)
@click.option("--person-block", default="person_demographics", show_default=True)
@click.option(
    "--condition",
    "conditions",
    multiple=True,
    metavar="COLUMN=VALUE",
    help="Household generation condition. Repeat as needed.",
)
@click.option("--households", default=1_000, show_default=True, type=int)
@click.option(
    "--method",
    default="conditional-frequency",
    show_default=True,
    type=click.Choice(["conditional-frequency", "cart"]),
)
@click.option("--random-seed", default=0, show_default=True, type=int)
@click.option("--min-support", default=5, show_default=True, type=int)
@click.option("--min-samples-leaf", default=5, show_default=True, type=int)
@click.option("--max-depth", default=None, type=int)
@click.option("--tolerance", default=0.05, show_default=True, type=float)
def benchmark_tree_linked(
    source: Path,
    out_dir: Path,
    household_target_columns: str,
    household_conditioning_columns: str,
    person_target_columns: str,
    person_conditioning_columns: str,
    suggested_blocks: bool,
    household_block: str,
    person_block: str,
    conditions: tuple[str, ...],
    households: int,
    method: str,
    random_seed: int,
    min_support: int,
    min_samples_leaf: int,
    max_depth: int | None,
    tolerance: float,
) -> None:
    """Run a linked household/person tree benchmark.

    SOURCE is a StatCan 2016 hierarchical CSV.
    """
    parsed_conditions: dict[str, str] = {}
    for cond in conditions:
        if "=" not in cond:
            raise click.BadParameter(
                f"{cond!r} must be COLUMN=VALUE", param_hint="--condition"
            )
        col, val = cond.split("=", 1)
        parsed_conditions[col] = val

    summary = run_linked_tree_benchmark(
        source,
        output_dir=out_dir,
        household_target_columns=None
        if suggested_blocks
        else _parse_columns(household_target_columns),
        household_conditioning_columns=None
        if suggested_blocks
        else _parse_columns(household_conditioning_columns),
        person_target_columns=None
        if suggested_blocks
        else _parse_columns(person_target_columns),
        person_conditioning_columns=None
        if suggested_blocks
        else _parse_columns(person_conditioning_columns),
        household_block=household_block if suggested_blocks else None,
        person_block=person_block if suggested_blocks else None,
        households=households,
        conditions=parsed_conditions,
        method=method,
        random_seed=random_seed,
        min_support=min_support,
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
        tolerance=tolerance,
    )
    _print_tree_summary(summary)


def _parse_columns(value: str) -> tuple[str, ...]:
    cols = tuple(c.strip() for c in value.split(",") if c.strip())
    if not cols:
        raise click.UsageError("at least one column is required")
    return cols


def _print_tree_summary(summary: dict[str, object]) -> None:
    table = make_table(title="Linked Tree Benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    source = summary["source"]
    generation = summary["generation"]
    timings = summary["timings"]
    linked_validation = summary["linked_validation"]
    distribution_validation = summary["distribution_validation"]
    artifact_sizes = summary["artifact_sizes_bytes"]
    column_source = summary["column_source"]
    outputs = summary["outputs"]

    assert isinstance(source, dict)
    assert isinstance(generation, dict)
    assert isinstance(timings, dict)
    assert isinstance(linked_validation, dict)
    assert isinstance(distribution_validation, dict)
    assert isinstance(artifact_sizes, dict)
    assert isinstance(column_source, dict)
    assert isinstance(outputs, dict)

    table.add_row("Source records", _fmt_int(source["records"]))
    table.add_row("Source households", _fmt_int(source["households"]))
    table.add_row("Column source", _fmt_column_source(column_source))
    table.add_row("Generated households", _fmt_int(generation["households"]))
    table.add_row("Generated persons", _fmt_int(generation["persons"]))
    table.add_row(
        "Generated avg household size", _fmt_float(generation["average_household_size"])
    )
    table.add_row("Linked validation passed", str(linked_validation["passed"]))
    table.add_row(
        "Household distribution passed",
        str(distribution_validation["household_passed"]),
    )
    table.add_row(
        "Person distribution passed", str(distribution_validation["person_passed"])
    )
    table.add_row(
        "Household max delta",
        _fmt_percent(distribution_validation["household_max_delta"]),
    )
    table.add_row(
        "Person max delta", _fmt_percent(distribution_validation["person_max_delta"])
    )
    table.add_row(
        "Distribution warnings",
        _fmt_int(distribution_validation["household_warnings"])
        + " household / "
        + _fmt_int(distribution_validation["person_warnings"])
        + " person",
    )
    table.add_row(
        "Training subset records",
        _fmt_int(distribution_validation["training_household_records"])
        + " household / "
        + _fmt_int(distribution_validation["training_person_records"])
        + " person",
    )
    table.add_row(
        "Training avg household size",
        _fmt_float(distribution_validation["training_average_household_size"]),
    )
    table.add_row("Read source seconds", _fmt_float(timings["read_source_seconds"]))
    table.add_row(
        "Derive training seconds", _fmt_float(timings["derive_training_seconds"])
    )
    table.add_row("Train models seconds", _fmt_float(timings["train_models_seconds"]))
    table.add_row("Generate seconds", _fmt_float(timings["generate_seconds"]))
    table.add_row("Validate seconds", _fmt_float(timings["validate_seconds"]))
    table.add_row("Peak RSS", _fmt_bytes(summary["peak_rss_bytes"]))
    table.add_row("Household model", _fmt_bytes(artifact_sizes["household_model"]))
    table.add_row("Person model", _fmt_bytes(artifact_sizes["person_model"]))
    table.add_row(
        "Synthetic households CSV", _fmt_bytes(artifact_sizes["synthetic_households"])
    )
    table.add_row(
        "Synthetic persons CSV", _fmt_bytes(artifact_sizes["synthetic_persons"])
    )
    table.add_row("Summary JSON", str(outputs["summary"]))

    Console(width=120).print(table)


# ---------------------------------------------------------------------------
# Shared formatters
# ---------------------------------------------------------------------------


def _fmt_int(v: object) -> str:
    return f"{int(v):,}"


def _fmt_float(v: object) -> str:
    return f"{float(v):.6g}"


def _fmt_percent(v: object) -> str:
    return f"{float(v):.2%}"


def _fmt_bytes(v: object) -> str:
    b = int(v)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if b < 1024 or unit == "GiB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
        b //= 1024
    raise AssertionError("unreachable")


def _fmt_opt_int(v: object) -> str:
    return "" if v is None else _fmt_int(v)


def _fmt_opt_float(v: object) -> str:
    return "" if v is None else _fmt_float(v)


def _fmt_column_source(v: dict[str, object]) -> str:
    if v.get("mode") == "profile":
        return f"{v['profile']} ({v['household_block']} + {v['person_block']})"
    return str(v["mode"])


if __name__ == "__main__":
    cli()
