"""Run a developer linked household/person tree benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from synthpopcan.tree_benchmark import run_linked_tree_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="StatCan 2016 hierarchical CSV.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--household-target-columns",
        default="household_size,TENUR",
        help="Comma-separated household columns to generate.",
    )
    parser.add_argument(
        "--household-conditioning-columns",
        default="PR",
        help="Comma-separated household conditioning columns.",
    )
    parser.add_argument(
        "--person-target-columns",
        default="AGEGRP,SEX",
        help="Comma-separated person columns to generate.",
    )
    parser.add_argument(
        "--person-conditioning-columns",
        default="PR,household_size,TENUR",
        help="Comma-separated person conditioning columns.",
    )
    parser.add_argument(
        "--suggested-blocks",
        action="store_true",
        help="Use named suggested tree-column blocks instead of manual column lists.",
    )
    parser.add_argument(
        "--household-block",
        default="household_core",
        help="Suggested household block to use with --suggested-blocks.",
    )
    parser.add_argument(
        "--person-block",
        default="person_demographics",
        help="Suggested person block to use with --suggested-blocks.",
    )
    parser.add_argument(
        "--condition",
        action="append",
        default=[],
        help="Household generation condition as COLUMN=VALUE. Repeat as needed.",
    )
    parser.add_argument("--households", default=1_000, type=int)
    parser.add_argument(
        "--method",
        default="conditional-frequency",
        choices=["conditional-frequency", "cart"],
    )
    parser.add_argument("--random-seed", default=0, type=int)
    parser.add_argument("--min-support", default=5, type=int)
    parser.add_argument("--min-samples-leaf", default=5, type=int)
    parser.add_argument("--max-depth", default=None, type=int)
    parser.add_argument("--tolerance", default=0.05, type=float)
    args = parser.parse_args()

    summary = run_linked_tree_benchmark(
        args.source,
        output_dir=args.out_dir,
        household_target_columns=(
            None
            if args.suggested_blocks
            else parse_columns(args.household_target_columns)
        ),
        household_conditioning_columns=(
            None
            if args.suggested_blocks
            else parse_columns(args.household_conditioning_columns)
        ),
        person_target_columns=(
            None if args.suggested_blocks else parse_columns(args.person_target_columns)
        ),
        person_conditioning_columns=(
            None
            if args.suggested_blocks
            else parse_columns(args.person_conditioning_columns)
        ),
        household_block=args.household_block if args.suggested_blocks else None,
        person_block=args.person_block if args.suggested_blocks else None,
        households=args.households,
        conditions=parse_conditions(args.condition),
        method=args.method,
        random_seed=args.random_seed,
        min_support=args.min_support,
        min_samples_leaf=args.min_samples_leaf,
        max_depth=args.max_depth,
        tolerance=args.tolerance,
    )
    print_summary(summary)
    return 0


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(column.strip() for column in value.split(",") if column.strip())
    if not columns:
        raise ValueError("at least one column is required")
    return columns


def parse_conditions(values: list[str]) -> dict[str, str]:
    conditions: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"condition {value!r} must use COLUMN=VALUE")
        column, condition_value = value.split("=", 1)
        conditions[column] = condition_value
    return conditions


def print_summary(summary: dict[str, object]) -> None:
    table = Table(title="Linked Tree Benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    source = summary["source"]
    generation = summary["generation"]
    timings = summary["timings"]
    linked_validation = summary["linked_validation"]
    distribution_validation = summary["distribution_validation"]
    artifact_sizes = summary["artifact_sizes_bytes"]
    column_source = summary["column_source"]
    if not isinstance(source, dict):
        raise ValueError("benchmark summary source must be an object")
    if not isinstance(generation, dict):
        raise ValueError("benchmark summary generation must be an object")
    if not isinstance(timings, dict):
        raise ValueError("benchmark summary timings must be an object")
    if not isinstance(linked_validation, dict):
        raise ValueError("benchmark summary linked validation must be an object")
    if not isinstance(distribution_validation, dict):
        raise ValueError("benchmark summary distribution validation must be an object")
    if not isinstance(artifact_sizes, dict):
        raise ValueError("benchmark summary artifact sizes must be an object")
    if not isinstance(column_source, dict):
        raise ValueError("benchmark summary column source must be an object")

    table.add_row("Source records", format_int(source["records"]))
    table.add_row("Source households", format_int(source["households"]))
    table.add_row("Column source", format_column_source(column_source))
    table.add_row("Generated households", format_int(generation["households"]))
    table.add_row("Generated persons", format_int(generation["persons"]))
    table.add_row(
        "Generated avg household size",
        format_float(generation["average_household_size"]),
    )
    table.add_row("Linked validation passed", str(linked_validation["passed"]))
    table.add_row(
        "Household distribution passed",
        str(distribution_validation["household_passed"]),
    )
    table.add_row(
        "Person distribution passed",
        str(distribution_validation["person_passed"]),
    )
    table.add_row(
        "Household max delta",
        format_percent(distribution_validation["household_max_delta"]),
    )
    table.add_row(
        "Person max delta",
        format_percent(distribution_validation["person_max_delta"]),
    )
    table.add_row(
        "Distribution warnings",
        format_int(distribution_validation["household_warnings"])
        + " household / "
        + format_int(distribution_validation["person_warnings"])
        + " person",
    )
    table.add_row(
        "Training subset records",
        format_int(distribution_validation["training_household_records"])
        + " household / "
        + format_int(distribution_validation["training_person_records"])
        + " person",
    )
    table.add_row(
        "Training avg household size",
        format_float(distribution_validation["training_average_household_size"]),
    )
    table.add_row("Read source seconds", format_float(timings["read_source_seconds"]))
    table.add_row(
        "Derive training seconds",
        format_float(timings["derive_training_seconds"]),
    )
    table.add_row("Train models seconds", format_float(timings["train_models_seconds"]))
    table.add_row("Generate seconds", format_float(timings["generate_seconds"]))
    table.add_row("Validate seconds", format_float(timings["validate_seconds"]))
    outputs = summary["outputs"]
    if not isinstance(outputs, dict):
        raise ValueError("benchmark summary outputs must be an object")
    table.add_row("Peak RSS", format_bytes(summary["peak_rss_bytes"]))
    table.add_row("Household model", format_bytes(artifact_sizes["household_model"]))
    table.add_row("Person model", format_bytes(artifact_sizes["person_model"]))
    table.add_row(
        "Synthetic households CSV",
        format_bytes(artifact_sizes["synthetic_households"]),
    )
    table.add_row(
        "Synthetic persons CSV",
        format_bytes(artifact_sizes["synthetic_persons"]),
    )
    table.add_row("Summary JSON", str(outputs["summary"]))

    Console(width=120).print(table)


def format_int(value: object) -> str:
    return f"{int(value):,}"


def format_float(value: object) -> str:
    return f"{float(value):.6g}"


def format_percent(value: object) -> str:
    return f"{float(value):.2%}"


def format_bytes(value: object) -> str:
    bytes_value = int(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if bytes_value < 1024 or unit == "GiB":
            return f"{bytes_value:.1f} {unit}" if unit != "B" else f"{bytes_value} B"
        bytes_value /= 1024
    raise AssertionError("unreachable")


def format_column_source(value: dict[str, object]) -> str:
    if value.get("mode") == "profile":
        return (
            f"{value['profile']} ({value['household_block']} + {value['person_block']})"
        )
    return str(value["mode"])


if __name__ == "__main__":
    raise SystemExit(main())
