"""IPF commands and CSV helpers for the SynthPopCan CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from synthpopcan.cli_output import (
    format_fit_value_error,
    format_nonconvergence_message,
    print_ipf_input_check_table,
    print_ipf_report_table,
)
from synthpopcan.console import print_wrote
from synthpopcan.controls import read_control_table
from synthpopcan.diagnostics import build_ipf_fit_report, build_ipf_input_report
from synthpopcan.ipf import fit_ipf, integerize_weights

PATH = click.Path(path_type=Path)


@click.group()
def ipf() -> None:
    """Run IPF workflows."""


@ipf.command("check-inputs")
@click.option("--seed", "seed_path", required=True, type=PATH, help="Seed records CSV.")
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def check_ipf_inputs(
    seed_path: Path,
    controls_path: Path,
    output_format: str,
) -> None:
    """Check whether seed records cover the control dimensions and categories."""
    seed_rows = read_csv(seed_path)
    control_table = read_control_table(controls_path)
    report = build_ipf_input_report(seed_rows, control_table)
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_ipf_input_check_table(report)


@ipf.command("fit")
@click.option("--seed", "seed_path", required=True, type=PATH, help="Seed records CSV.")
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--out", "out_path", required=True, type=PATH, help="Output weighted CSV."
)
@click.option(
    "--weight-field",
    default=None,
    help="Optional seed CSV column containing initial weights.",
)
@click.option("--max-iterations", default=100, type=int, show_default=True)
@click.option("--tolerance", default=1e-6, type=float, show_default=True)
@click.option(
    "--allow-nonconverged",
    is_flag=True,
    help="Write weights even when IPF does not meet the convergence tolerance.",
)
@click.option("--report", "report_path", type=PATH, help="Optional JSON fit report.")
def fit_ipf_command(
    seed_path: Path,
    controls_path: Path,
    out_path: Path,
    weight_field: str | None,
    max_iterations: int,
    tolerance: float,
    allow_nonconverged: bool,
    report_path: Path | None,
) -> None:
    """Fit seed records to controls and write compact weights."""
    seed_rows = read_csv(seed_path)
    control_table = read_control_table(controls_path)
    try:
        result = fit_ipf(
            seed_rows,
            control_table.to_ipf_margins(),
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    except ValueError as exc:
        raise click.ClickException(format_fit_value_error(exc)) from exc
    report = build_ipf_fit_report(control_table, result)
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    if not result.converged and not allow_nonconverged:
        raise click.ClickException(format_nonconvergence_message(report))
    write_weighted_seed(out_path, seed_rows, result.weights)
    if report_path:
        print_wrote(report_path)
    print_wrote(out_path)


@ipf.command("expand")
@click.option(
    "--weights",
    "weights_path",
    required=True,
    type=PATH,
    help="Fitted seed weights CSV from ipf fit.",
)
@click.option(
    "--out", "out_path", required=True, type=PATH, help="Output synthetic CSV."
)
@click.option(
    "--weight-field",
    default="weight",
    show_default=True,
    help="Column containing fitted weights.",
)
def expand_ipf(weights_path: Path, out_path: Path, weight_field: str) -> None:
    """Expand fitted weights into full synthetic rows."""
    seed_rows, weights = read_weighted_seed(weights_path, weight_field)
    write_expanded_seed(out_path, seed_rows, weights)
    print_wrote(out_path)


@ipf.command("report")
@click.argument("path", type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def report_ipf(path: Path, output_format: str) -> None:
    """Print a fit report summary from ipf fit --report JSON."""
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"{path} is not valid JSON") from exc
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_ipf_report_table(report)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_weighted_seed(
    path: Path, weight_field: str
) -> tuple[list[dict[str, str]], list[float]]:
    rows: list[dict[str, str]] = []
    weights: list[float] = []
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            selected_weight_field = (
                "fitted_weight"
                if weight_field == "weight" and "fitted_weight" in row
                else weight_field
            )
            try:
                weight_value = row.pop(selected_weight_field)
            except KeyError as exc:
                raise ValueError(
                    f"weights CSV requires a {weight_field!r} column"
                ) from exc
            try:
                weights.append(float(weight_value))
            except ValueError as exc:
                raise ValueError(
                    f"weights row {row_number} has invalid weight"
                ) from exc
            rows.append(row)
    return rows, weights


def read_population_artifact(
    path: Path,
    artifact_kind: str,
    weight_field: str,
) -> tuple[list[dict[str, str]], list[float]]:
    if artifact_kind == "weights":
        return read_weighted_seed(path, weight_field)
    if artifact_kind == "expanded":
        rows = read_csv(path)
        return rows, [1.0 for _row in rows]
    raise ValueError(f"unknown population artifact kind {artifact_kind!r}")


def write_weighted_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> None:
    if not rows:
        raise ValueError("cannot write weighted output for empty seed rows")
    weight_column = "weight" if "weight" not in rows[0] else "fitted_weight"
    fieldnames = [*rows[0].keys(), weight_column]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, weight in zip(rows, weights, strict=True):
            writer.writerow({**row, weight_column: format_weight(weight)})


def write_expanded_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> None:
    counts = integerize_weights(weights)
    if sum(counts) == 0:
        raise ValueError("expanded synthetic population is empty")
    fieldnames = [
        "synthetic_id",
        "seed_id",
        *(field for field in rows[0] if field != "id"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        synthetic_id = 1
        for source_index, row in enumerate(rows, start=1):
            seed_id = str(row.get("id", source_index))
            attributes = {key: value for key, value in row.items() if key != "id"}
            for _ in range(counts[source_index - 1]):
                writer.writerow(
                    {
                        "synthetic_id": str(synthetic_id),
                        "seed_id": seed_id,
                        **attributes,
                    }
                )
                synthetic_id += 1


def format_weight(weight: float) -> str:
    rounded = round(weight)
    if abs(weight - rounded) < 1e-9:
        return str(rounded)
    return f"{weight:.12g}"
