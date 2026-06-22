"""Developer-facing linked tree benchmark workflow."""

from __future__ import annotations

import csv
import json
import resource
import sys
import time
from pathlib import Path

from synthpopcan.microdata import (
    export_training_rows,
    read_statcan_2016_hierarchical_seed_sample,
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
    household_target_columns: tuple[str, ...],
    household_conditioning_columns: tuple[str, ...],
    person_target_columns: tuple[str, ...],
    person_conditioning_columns: tuple[str, ...],
    households: int,
    conditions: dict[str, str] | None = None,
    method: str = "conditional-frequency",
    random_seed: int = 0,
    min_support: int = 5,
    min_samples_leaf: int = 5,
    max_depth: int | None = None,
    tolerance: float = 0.05,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = benchmark_paths(output_dir)
    timings: dict[str, float] = {}

    start = time.perf_counter()
    sample = read_statcan_2016_hierarchical_seed_sample(source)
    timings["read_source_seconds"] = elapsed_seconds(start)

    start = time.perf_counter()
    household_rows, household_export = export_training_rows(
        sample,
        level="household",
        target_columns=household_target_columns,
        conditioning_columns=household_conditioning_columns,
    )
    write_csv(paths["household_training"], household_rows)
    person_rows, person_export = export_training_rows(
        sample,
        level="person",
        target_columns=person_target_columns,
        conditioning_columns=person_conditioning_columns,
    )
    write_csv(paths["person_training"], person_rows)
    timings["derive_training_seconds"] = elapsed_seconds(start)

    start = time.perf_counter()
    household_model = train_model_from_csv(
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
    person_model = train_model_from_csv(
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
    timings["train_models_seconds"] = elapsed_seconds(start)

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
    timings["generate_seconds"] = elapsed_seconds(start)

    start = time.perf_counter()
    linked_validation = validate_linked_population(
        synthetic_households,
        synthetic_persons,
    )
    household_distribution_validation = build_tree_output_validation_report(
        training_rows=household_rows,
        generated_rows=synthetic_households,
        target_columns=household_target_columns,
        conditioning_columns=household_conditioning_columns,
        weight_field="WEIGHT",
        tolerance=tolerance,
    )
    person_distribution_validation = build_tree_output_validation_report(
        training_rows=person_rows,
        generated_rows=synthetic_persons,
        target_columns=person_target_columns,
        conditioning_columns=person_conditioning_columns,
        weight_field="WEIGHT",
        tolerance=tolerance,
    )
    write_json(paths["linked_validation"], linked_validation)
    write_json(
        paths["household_distribution_validation"],
        household_distribution_validation,
    )
    write_json(paths["person_distribution_validation"], person_distribution_validation)
    timings["validate_seconds"] = elapsed_seconds(start)

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
        "training": {
            "household": household_export,
            "person": person_export,
        },
        "generation": {
            "households": len(synthetic_households),
            "persons": len(synthetic_persons),
        },
        "linked_validation": {
            "passed": linked_validation["passed"],
            "issues": len(linked_validation["issues"]),
        },
        "distribution_validation": {
            "household_passed": household_distribution_validation["passed"],
            "person_passed": person_distribution_validation["passed"],
            "tolerance": tolerance,
        },
        "timings": timings,
        "peak_rss_bytes": peak_rss_bytes(),
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    write_json(paths["summary"], summary)
    return summary


def train_model_from_csv(
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


def benchmark_paths(output_dir: Path) -> dict[str, Path]:
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


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty benchmark CSV")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def elapsed_seconds(start: float) -> float:
    return round(time.perf_counter() - start, 6)


def peak_rss_bytes() -> int:
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(peak_rss)
    return int(peak_rss) * 1024
