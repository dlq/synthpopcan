"""Run developer-facing IPF benchmark fixtures."""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from synthpopcan.benchmarks import run_ipf_benchmarks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-records",
        default=50_000,
        type=int,
        help="Seed rows per benchmark case.",
    )
    args = parser.parse_args()

    rows = run_ipf_benchmarks(seed_records=args.seed_records)
    table = Table(title="IPF Benchmarks")
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
            format_int(row["seed_records"]),
            format_int(row["margin_cells"]),
            format_int(row["iterations"]),
            str(row["converged"]),
            format_float(row["max_abs_error"]),
            format_float(row["fit_seconds"]),
            format_int(row["expanded_rows"]),
            str(row["dependency_hint"]),
        )

    Console(width=120).print(table)
    return 0


def format_int(value: object) -> str:
    return f"{int(value):,}"


def format_float(value: object) -> str:
    return f"{float(value):.6g}"


if __name__ == "__main__":
    raise SystemExit(main())
