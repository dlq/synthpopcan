"""Compare reusable candidate-pool sizes on one national control batch."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from synthpopcan.cli_tree import (
    _read_package_path_or_id,
    package_models,
    validate_package_allows_generation,
)
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.small_area_controls import write_recoded_candidates
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
from synthpopcan.tree import generate_linked_population_to_csv


def _distributions(path: Path, excluded: set[str]) -> dict[str, Counter[str]]:
    distributions: dict[str, Counter[str]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            for column, value in row.items():
                if column not in excluded and not column.casefold().endswith("_id"):
                    distributions.setdefault(column, Counter())[str(value)] += 1
    return distributions


def _total_variation(
    observed: Counter[str],
    reference: Counter[str],
) -> float:
    observed_total = sum(observed.values())
    reference_total = sum(reference.values())
    categories = observed.keys() | reference.keys()
    return 0.5 * sum(
        abs(
            observed.get(category, 0) / observed_total
            - reference.get(category, 0) / reference_total
        )
        for category in categories
    )


def _parse_pool_sizes(value: str) -> list[int]:
    sizes = sorted({int(item) for item in value.split(",")})
    if not sizes or sizes[0] < 1:
        raise argparse.ArgumentTypeError("pool sizes must be positive integers")
    return sizes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--condition-pr", default="10")
    parser.add_argument(
        "--pool-sizes", type=_parse_pool_sizes, default=[10_000, 25_000, 50_000]
    )
    parser.add_argument("--geography-level", choices=("ada", "da"), default="ada")
    parser.add_argument("--geography-column", default="ADAUID")
    parser.add_argument("--fit-workers", type=int, default=4)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument(
        "--reuse-candidates",
        action="store_true",
        help="Reuse existing candidate CSVs in --out after reviewing their origin.",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    candidates = args.out / "candidates"
    candidates.mkdir(exist_ok=True)
    raw_households = candidates / "households-raw.csv"
    households = candidates / "households.csv"
    persons = candidates / "persons.csv"
    if args.reuse_candidates:
        if not households.is_file() or not persons.is_file():
            parser.error("--reuse-candidates requires existing linked candidate CSVs")
        generated_households = sum(1 for _ in households.open()) - 1
        generated_persons = sum(1 for _ in persons.open()) - 1
        model_load_seconds = 0.0
        generation_seconds = 0.0
        label = args.model
    else:
        started = time.perf_counter()
        package, label, _ = _read_package_path_or_id(args.model)
        validate_package_allows_generation(package)
        household_model, person_model = package_models(package)
        model_load_seconds = time.perf_counter() - started
        generation_started = time.perf_counter()
        generated_households, generated_persons = generate_linked_population_to_csv(
            household_model,
            person_model,
            households=max(args.pool_sizes),
            households_path=raw_households,
            persons_path=persons,
            household_conditions={"PR": args.condition_pr},
            household_size_column=str(
                package.get("household_size_column", "household_size")
            ),
            random_seed=args.random_seed + int(args.condition_pr),
        )
        write_recoded_candidates(
            raw_households,
            households,
            hhsize_col=str(package.get("household_size_column", "household_size")),
            group_col="household_size_group",
            cap=5,
        )
        raw_households.unlink()
        generation_seconds = time.perf_counter() - generation_started

    runs: dict[str, dict[str, Any]] = {}
    distributions: dict[str, dict[str, Counter[str]]] = {}
    for pool_size in args.pool_sizes:
        output = args.out / f"pool-{pool_size}"
        output.mkdir(exist_ok=True)
        run_started = time.perf_counter()
        report = calibrate_linked_household_csvs(
            households_path=households,
            persons_path=persons,
            controls_path=args.controls,
            geography_dimension=args.geography_level,
            geography_column=args.geography_column,
            geography_universe=statcan_geography_universe(
                2021,
                args.geography_level,
                args.geography_column,
                dguid_column="DGUID",
            ),
            households_out=output / "households.csv",
            persons_out=output / "persons.csv",
            report_out=output / "report.json",
            pool_size=pool_size,
            subsample_seed=args.random_seed,
            n_workers=args.fit_workers,
            record_timing=True,
        )
        runs[str(pool_size)] = {
            "elapsed_seconds": time.perf_counter() - run_started,
            "assigned_households": report["assigned_households"],
            "assigned_persons": report["assigned_persons"],
            "converged_geographies": report["summary"]["converged_count"],
            "geographies": len(report["geographies"]),
            "fractional_max_abs_error": report["summary"]["max_abs_error"],
            "realized_max_abs_error": report["summary"]["realized_max_abs_error"],
            "timing_seconds": report["timing_seconds"],
        }
        distributions[str(pool_size)] = {
            "households": _distributions(
                output / "households.csv",
                {
                    "synthetic_household_id",
                    args.geography_column,
                    "TENUR",
                    "household_size_group",
                },
            ),
            "persons": _distributions(
                output / "persons.csv",
                {
                    "synthetic_household_id",
                    "synthetic_person_id",
                    args.geography_column,
                },
            ),
        }

    reference_key = str(max(args.pool_sizes))
    for pool_key, units in distributions.items():
        sensitivity: dict[str, dict[str, float]] = {}
        for unit, columns in units.items():
            reference = distributions[reference_key][unit]
            sensitivity[unit] = {
                column: _total_variation(values, reference[column])
                for column, values in columns.items()
                if column in reference
            }
        runs[pool_key]["total_variation_from_largest_pool"] = sensitivity

    result = {
        "schema_version": "synthpopcan-candidate-pool-benchmark-v1",
        "model": label,
        "condition": {"PR": args.condition_pr},
        "controls": str(args.controls),
        "pool_sizes": args.pool_sizes,
        "reference_pool_size": max(args.pool_sizes),
        "generated_rows": {
            "households": generated_households,
            "persons": generated_persons,
        },
        "model_load_seconds": model_load_seconds,
        "candidate_generation_seconds": generation_seconds,
        "runs": runs,
    }
    result_path = args.out / "benchmark.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
