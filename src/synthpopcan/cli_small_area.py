"""Small-area linked synthesis commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synthpopcan.cli_output import format_file_access_error
from synthpopcan.console import print_wrote
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs

_PATH = click.Path(path_type=Path)


@click.group("small-area")
def small_area() -> None:
    """Assign and calibrate linked households to target geographies."""


@small_area.command("calibrate-linked")
@click.option(
    "--households",
    "households_path",
    required=True,
    type=_PATH,
    help="Candidate household CSV generated from a linked model package.",
)
@click.option(
    "--persons",
    "persons_path",
    required=True,
    type=_PATH,
    help="Candidate person CSV linked to the household CSV.",
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Normalized controls with one target geography dimension.",
)
@click.option(
    "--geography-dimension",
    required=True,
    help="Control dimension naming the target geography, such as ct or ada.",
)
@click.option(
    "--geography-column",
    required=True,
    help="Column name to write on assigned household and person rows.",
)
@click.option(
    "--households-out",
    required=True,
    type=_PATH,
    help="Destination CSV for assigned household rows.",
)
@click.option(
    "--persons-out",
    required=True,
    type=_PATH,
    help="Destination CSV for assigned person rows.",
)
@click.option(
    "--weights-out",
    type=_PATH,
    help="Optional fitted household weights CSV; may be large.",
)
@click.option(
    "--report",
    "report_out",
    type=_PATH,
    help="Optional JSON report with convergence and geography summaries.",
)
@click.option(
    "--household-id-column",
    default="synthetic_household_id",
    show_default=True,
    help="Household ID column shared by household and person CSVs.",
)
@click.option(
    "--person-id-column",
    default="synthetic_person_id",
    show_default=True,
    help="Person ID column in the candidate person CSV.",
)
@click.option("--weight-field", help="Optional candidate-household starting weight.")
@click.option(
    "--max-iterations",
    default=100,
    type=int,
    show_default=True,
    help="Maximum IPF iterations per target geography.",
)
@click.option(
    "--tolerance",
    default=1e-6,
    type=float,
    show_default=True,
    help="Convergence tolerance per target geography.",
)
@click.option(
    "--format",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json"]),
    show_default=True,
    help="Print a short summary or the full machine-readable report.",
)
def calibrate_linked_command(
    households_path: Path,
    persons_path: Path,
    controls_path: Path,
    geography_dimension: str,
    geography_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None,
    report_out: Path | None,
    household_id_column: str,
    person_id_column: str,
    weight_field: str | None,
    max_iterations: int,
    tolerance: float,
    output_format: str,
) -> None:
    """Calibrate linked household/person candidates to geography controls."""

    try:
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            geography_dimension=geography_dimension,
            geography_column=geography_column,
            households_out=households_out,
            persons_out=persons_out,
            weights_out=weights_out,
            report_out=report_out,
            household_id_column=household_id_column,
            person_id_column=person_id_column,
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    except OSError as exc:
        filename = exc.filename or households_path
        raise click.ClickException(
            format_file_access_error(Path(filename), "process", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    print_wrote(households_out)
    print_wrote(persons_out)
    if weights_out:
        print_wrote(weights_out)
    if report_out:
        print_wrote(report_out)
    if output_format == "json":
        click.echo(json.dumps(summary, sort_keys=True))
        return
    click.echo(
        "Assigned "
        f"{summary['assigned_households']:,} household row(s) and "
        f"{summary['assigned_persons']:,} person row(s) across "
        f"{len(summary['geographies']):,} {geography_column} value(s)."
    )
