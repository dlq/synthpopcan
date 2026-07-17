"""IPF commands and CSV helpers for the SynthPopCan CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synthpopcan.calibration import build_control_suggestion_report
from synthpopcan.cli_output import (
    click_file_access_error,
    click_value_error,
    format_fit_value_error,
    format_nonconvergence_message,
    print_ipf_control_suggestions_table,
    print_ipf_input_check_table,
    print_ipf_report_table,
    read_csv_rows,
    write_report,
)
from synthpopcan.console import print_wrote
from synthpopcan.workflows.ipf import (
    IPFNonConvergenceError,
    check_ipf_inputs,
    expand_ipf_weights,
    fit_ipf_files,
    read_population_artifact,
    read_weighted_seed,
    write_expanded_seed,
    write_weighted_seed,
)
from synthpopcan.workflows.types import IPFExpandRequest, IPFFitRequest

_PATH = click.Path(path_type=Path)

_read_weighted_seed = read_weighted_seed
_write_expanded_seed = write_expanded_seed
_write_weighted_seed = write_weighted_seed

__all__ = [
    "ipf",
    "read_population_artifact",
]


@click.group()
def ipf() -> None:
    """Run IPF workflows."""


@ipf.command("check-inputs")
@click.option(
    "--seed", "seed_path", required=True, type=_PATH, help="Seed records CSV."
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def _check_ipf_inputs(
    seed_path: Path,
    controls_path: Path,
    output_format: str,
) -> None:
    """Check whether seed records cover the control dimensions and categories."""
    try:
        report = check_ipf_inputs(seed_path, controls_path)
    except OSError as exc:
        raise click_file_access_error(exc.filename, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    write_report(report, output_format, print_ipf_input_check_table)


@ipf.command("suggest-controls")
@click.option(
    "--seed", "seed_path", required=True, type=_PATH, help="Seed records CSV."
)
@click.option(
    "--unit",
    default="auto",
    type=click.Choice(["auto", "household", "person"]),
    show_default=True,
    help="Generated-row unit to consider for calibration controls.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def _suggest_ipf_controls(
    seed_path: Path,
    unit: str,
    output_format: str,
) -> None:
    """Suggest calibration-control directions from generated or seed rows."""
    try:
        seed_rows = read_csv_rows(seed_path)
    except OSError as exc:
        raise click_file_access_error(seed_path, "read", exc) from exc
    report = build_control_suggestion_report(
        seed_rows, unit=unit, seed_path=str(seed_path)
    )
    write_report(report, output_format, print_ipf_control_suggestions_table)


@ipf.command("fit")
@click.option(
    "--seed", "seed_path", required=True, type=_PATH, help="Seed records CSV."
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--out", "out_path", required=True, type=_PATH, help="Output weighted CSV."
)
@click.option(
    "--weight-column",
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
@click.option("--report", "report_path", type=_PATH, help="Optional JSON fit report.")
def _fit_ipf_command(
    seed_path: Path,
    controls_path: Path,
    out_path: Path,
    weight_column: str | None,
    max_iterations: int,
    tolerance: float,
    allow_nonconverged: bool,
    report_path: Path | None,
) -> None:
    """Fit seed records to controls and write compact weights."""
    request = IPFFitRequest(
        seed_path=seed_path,
        controls_path=controls_path,
        output_path=out_path,
        weight_column=weight_column,
        max_iterations=max_iterations,
        tolerance=tolerance,
        allow_nonconverged=allow_nonconverged,
        report_path=report_path,
    )
    try:
        fit_ipf_files(request)
    except OSError as exc:
        error_path = Path(exc.filename) if exc.filename else seed_path
        action = "write" if error_path in {out_path, report_path} else "read"
        raise click_file_access_error(error_path, action, exc) from exc
    except ValueError as exc:
        raise click_value_error(exc, format_fit_value_error) from exc
    except IPFNonConvergenceError as exc:
        raise click.ClickException(format_nonconvergence_message(exc.report)) from exc
    if report_path:
        print_wrote(report_path)
    print_wrote(out_path)


@ipf.command("expand")
@click.option(
    "--weights",
    "weights_path",
    required=True,
    type=_PATH,
    help="Fitted seed weights CSV from ipf fit.",
)
@click.option(
    "--out", "out_path", required=True, type=_PATH, help="Output synthetic CSV."
)
@click.option(
    "--weight-column",
    default="weight",
    show_default=True,
    help="Column containing fitted weights.",
)
def _expand_ipf(weights_path: Path, out_path: Path, weight_column: str) -> None:
    """Expand fitted weights into full synthetic rows."""
    try:
        expand_ipf_weights(
            IPFExpandRequest(
                weights_path=weights_path,
                output_path=out_path,
                weight_column=weight_column,
            )
        )
    except OSError as exc:
        raise click_file_access_error(
            exc.filename or weights_path, "access", exc
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(out_path)


@ipf.command("report")
@click.argument("path", type=_PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def _report_ipf(path: Path, output_format: str) -> None:
    """Print a fit report summary from ipf fit --report JSON."""
    try:
        report = json.loads(path.read_text())
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"{path} is not valid JSON") from exc
    write_report(report, output_format, print_ipf_report_table)
