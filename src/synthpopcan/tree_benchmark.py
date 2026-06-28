"""Developer-facing linked tree benchmark workflow."""

from __future__ import annotations

from typing import Any

__all__ = ["resolve_benchmark_columns", "run_linked_tree_benchmark"]

import csv
import json
import resource
import sys
import time
from pathlib import Path

from synthpopcan.microdata import (
    SeedSample,
    export_training_rows,
    read_statcan_2016_hierarchical_seed_sample,
    resolve_tree_column_block_pair,
)
from synthpopcan.tree import (
    generate_linked_population,
    read_tree_training_sample,
    train_cart_model,
    train_frequency_model,
    validate_linked_population,
    write_generated_rows,
    write_tree_model,
)
from synthpopcan.validation import build_tree_output_validation_report


def run_linked_tree_benchmark(
    source: Path,
    *,
    output_dir: Path,
    household_target_columns: tuple[str, ...] | None,
    household_conditioning_columns: tuple[str, ...] | None,
    person_target_columns: tuple[str, ...] | None,
    person_conditioning_columns: tuple[str, ...] | None,
    household_block: str | None = None,
    person_block: str | None = None,
    households: int,
    conditions: dict[str, str] | None = None,
    method: str = "conditional-frequency",
    random_seed: int = 0,
    min_support: int = 5,
    min_samples_leaf: int = 5,
    max_depth: int | None = None,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _benchmark_paths(output_dir)
    timings: dict[str, float] = {}

    start = time.perf_counter()
    sample = read_statcan_2016_hierarchical_seed_sample(source)
    timings["read_source_seconds"] = _elapsed_seconds(start)
    (
        household_target_columns,
        household_conditioning_columns,
        person_target_columns,
        person_conditioning_columns,
        column_source,
    ) = resolve_benchmark_columns(
        sample,
        household_target_columns=household_target_columns,
        household_conditioning_columns=household_conditioning_columns,
        person_target_columns=person_target_columns,
        person_conditioning_columns=person_conditioning_columns,
        household_block=household_block,
        person_block=person_block,
    )

    start = time.perf_counter()
    household_rows, household_export = export_training_rows(
        sample,
        level="household",
        target_columns=household_target_columns,
        conditioning_columns=household_conditioning_columns,
    )
    _write_csv(paths["household_training"], household_rows)
    person_rows, person_export = export_training_rows(
        sample,
        level="person",
        target_columns=person_target_columns,
        conditioning_columns=person_conditioning_columns,
    )
    _write_csv(paths["person_training"], person_rows)
    timings["derive_training_seconds"] = _elapsed_seconds(start)

    start = time.perf_counter()
    household_model = _train_model_from_csv(
        paths["household_training"],
        level="household",
        target_columns=household_target_columns,
        conditioning_columns=household_conditioning_columns,
        method=method,
        random_seed=random_seed,
        min_support=min_support,
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
    )
    person_model = _train_model_from_csv(
        paths["person_training"],
        level="person",
        target_columns=person_target_columns,
        conditioning_columns=person_conditioning_columns,
        method=method,
        random_seed=random_seed,
        min_support=min_support,
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
    )
    write_tree_model(paths["household_model"], household_model)
    write_tree_model(paths["person_model"], person_model)
    timings["train_models_seconds"] = _elapsed_seconds(start)

    start = time.perf_counter()
    synthetic_households, synthetic_persons = generate_linked_population(
        household_model,
        person_model,
        households=households,
        household_conditions=conditions,
        random_seed=random_seed,
    )
    write_generated_rows(paths["synthetic_households"], synthetic_households)
    write_generated_rows(paths["synthetic_persons"], synthetic_persons)
    timings["generate_seconds"] = _elapsed_seconds(start)

    start = time.perf_counter()
    linked_validation = validate_linked_population(
        synthetic_households,
        synthetic_persons,
    )
    validation_conditions = conditions or {}
    household_validation_rows = _filter_rows(household_rows, validation_conditions)
    person_validation_rows = _filter_rows(person_rows, validation_conditions)
    household_distribution_validation = build_tree_output_validation_report(
        training_rows=household_validation_rows,
        generated_rows=synthetic_households,
        target_columns=household_target_columns,
        conditioning_columns=household_conditioning_columns,
        weight_field="WEIGHT",
        tolerance=tolerance,
    )
    person_distribution_validation = build_tree_output_validation_report(
        training_rows=person_validation_rows,
        generated_rows=synthetic_persons,
        target_columns=person_target_columns,
        conditioning_columns=person_conditioning_columns,
        weight_field="WEIGHT",
        tolerance=tolerance,
    )
    _write_json(paths["linked_validation"], linked_validation)
    _write_json(
        paths["household_distribution_validation"],
        household_distribution_validation,
    )
    _write_json(paths["person_distribution_validation"], person_distribution_validation)
    timings["validate_seconds"] = _elapsed_seconds(start)

    summary = {
        "source": {
            "path": str(source),
            "records": len(sample.records),
            "households": sample.metadata.get("households", 0),
            "source_format": sample.source_format,
        },
        "method": method,
        "random_seed": random_seed,
        "conditions": conditions or {},
        "column_source": column_source,
        "training": {
            "household": household_export,
            "person": person_export,
        },
        "generation": {
            "households": len(synthetic_households),
            "persons": len(synthetic_persons),
            "_average_household_size": _average_household_size(synthetic_households),
        },
        "linked_validation": {
            "passed": linked_validation["passed"],
            "issues": len(linked_validation["issues"]),
        },
        "distribution_validation": {
            "household_passed": household_distribution_validation["passed"],
            "person_passed": person_distribution_validation["passed"],
            "household_max_delta": household_distribution_validation[
                "max_abs_proportion_delta"
            ],
            "person_max_delta": person_distribution_validation[
                "max_abs_proportion_delta"
            ],
            "household_warnings": len(household_distribution_validation["issues"]),
            "person_warnings": len(person_distribution_validation["issues"]),
            "training_household_records": len(household_validation_rows),
            "training_person_records": len(person_validation_rows),
            "training_average_household_size": _average_household_size(
                household_validation_rows
            ),
            "tolerance": tolerance,
        },
        "timings": timings,
        "_peak_rss_bytes": _peak_rss_bytes(),
        "artifact_sizes_bytes": _artifact_sizes(paths),
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    _write_json(paths["summary"], summary)
    return summary


def resolve_benchmark_columns(
    sample: SeedSample,
    *,
    household_target_columns: tuple[str, ...] | None,
    household_conditioning_columns: tuple[str, ...] | None,
    person_target_columns: tuple[str, ...] | None,
    person_conditioning_columns: tuple[str, ...] | None,
    household_block: str | None,
    person_block: str | None,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    dict[str, Any],
]:
    if household_block or person_block:
        if not household_block or not person_block:
            raise ValueError(
                "household_block and person_block must be provided together"
            )
        return resolve_tree_column_block_pair(
            sample,
            household_block=household_block,
            person_block=person_block,
        )

    return (
        _require_explicit_columns(
            household_target_columns,
            label="household target columns",
        ),
        _require_explicit_columns(
            household_conditioning_columns,
            label="household conditioning columns",
        ),
        _require_explicit_columns(person_target_columns, label="person target columns"),
        _require_explicit_columns(
            person_conditioning_columns,
            label="person conditioning columns",
        ),
        {"mode": "explicit"},
    )


def _require_explicit_columns(
    columns: tuple[str, ...] | None,
    *,
    label: str,
) -> tuple[str, ...]:
    if not columns:
        raise ValueError(f"{label} are required without suggested blocks")
    return columns


def _train_model_from_csv(
    path: Path,
    *,
    level: str,
    target_columns: tuple[str, ...],
    conditioning_columns: tuple[str, ...],
    method: str,
    random_seed: int,
    min_support: int,
    min_samples_leaf: int,
    max_depth: int | None,
):
    sample = read_tree_training_sample(
        path,
        level=level,  # type: ignore[arg-type]
        target_columns=target_columns,
        conditioning_columns=conditioning_columns,
        weight_column="WEIGHT",
    )
    if method == "cart":
        return train_cart_model(
            sample,
            random_seed=random_seed,
            min_samples_leaf=min_samples_leaf,
            max_depth=max_depth,
        )
    if method == "conditional-frequency":
        return train_frequency_model(
            sample,
            random_seed=random_seed,
            min_support=min_support,
        )
    raise ValueError(f"unsupported tree benchmark method: {method}")


def _benchmark_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "household_training": output_dir / "household-training.csv",
        "person_training": output_dir / "person-training.csv",
        "household_model": output_dir / "household-model.json",
        "person_model": output_dir / "person-model.json",
        "synthetic_households": output_dir / "synthetic-households.csv",
        "synthetic_persons": output_dir / "synthetic-persons.csv",
        "linked_validation": output_dir / "linked-validation.json",
        "household_distribution_validation": (
            output_dir / "household-distribution-validation.json"
        ),
        "person_distribution_validation": output_dir
        / "person-distribution-validation.json",
        "summary": output_dir / "benchmark-summary.json",
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty benchmark CSV")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _filter_rows(
    rows: list[dict[str, str]],
    conditions: dict[str, str],
) -> list[dict[str, str]]:
    if not conditions:
        return rows
    return [
        row
        for row in rows
        if all(row.get(column) == value for column, value in conditions.items())
    ]


def _average_household_size(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    total = sum(int(row["household_size"]) for row in rows)
    return round(total / len(rows), 4)


def _artifact_sizes(paths: dict[str, Path]) -> dict[str, int]:
    return {
        key: path.stat().st_size
        for key, path in paths.items()
        if key != "summary" and path.exists()
    }


def _elapsed_seconds(start: float) -> float:
    return round(time.perf_counter() - start, 6)


def _peak_rss_bytes() -> int:
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(peak_rss)
    return int(peak_rss) * 1024
