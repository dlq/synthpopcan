"""Command-line adapter for simulator-neutral exchange bundles."""

from __future__ import annotations

__all__ = ["bundle"]

import json
from pathlib import Path

import click

from synthpopcan.console import print_success, print_wrote
from synthpopcan.exchange import create_exchange_bundle, validate_exchange_bundle
from synthpopcan.geography import GeographyUniverse

_PATH = click.Path(path_type=Path)


@click.group()
def bundle() -> None:
    """Create and verify portable household/person exchange bundles."""


@bundle.command("create")
@click.argument("population", type=_PATH)
@click.option("--out", "output_dir", required=True, type=_PATH)
@click.option("--census-vintage", type=int, default=None)
@click.option("--geography-level", default=None)
@click.option("--identifier-namespace", default=None)
@click.option("--geography-column", default=None)
@click.option("--run-manifest", type=_PATH, default=None)
@click.option(
    "--access",
    "access_classification",
    type=click.Choice(["public", "local", "licensed", "restricted"]),
    default="local",
    show_default=True,
)
@click.option(
    "--redistribution",
    "redistribution_status",
    type=click.Choice(["permitted", "not-permitted", "not-assessed"]),
    default="not-assessed",
    show_default=True,
)
@click.option("--limitation", "limitations", multiple=True)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def create_bundle_command(
    population: Path,
    output_dir: Path,
    census_vintage: int | None,
    geography_level: str | None,
    identifier_namespace: str | None,
    geography_column: str | None,
    run_manifest: Path | None,
    access_classification: str,
    redistribution_status: str,
    limitations: tuple[str, ...],
    output_format: str,
) -> None:
    """Create a validated population-contribution bundle from linked CSVs."""

    try:
        geography = _geography_universe(
            census_vintage,
            geography_level,
            identifier_namespace,
            geography_column,
        )
        reproduction = {
            "interface": "cli",
            "command": "synthpopcan bundle create",
            "arguments": {
                "population": str(population),
                "out": str(output_dir),
                "census_vintage": census_vintage,
                "geography_level": geography_level,
                "identifier_namespace": identifier_namespace,
                "geography_column": geography_column,
                "run_manifest": str(run_manifest) if run_manifest else None,
                "access": access_classification,
                "redistribution": redistribution_status,
                "limitations": list(limitations),
            },
        }
        result = create_exchange_bundle(
            population,
            output_dir,
            geography_universe=geography,
            run_manifest=run_manifest,
            reproduction=reproduction,
            access_classification=access_classification,
            redistribution_status=redistribution_status,
            limitations=limitations,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    payload = {
        "directory": str(result.directory),
        "artifacts": {
            "manifest": str(result.manifest),
            "households": str(result.households),
            "persons": str(result.persons),
            "linked_population": str(result.linked_population),
            "data_dictionary": str(result.data_dictionary),
            "provenance": str(result.provenance),
            "validation": str(result.validation),
        },
        "validation_report": dict(result.report),
    }
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    for path in payload["artifacts"].values():
        print_wrote(Path(path))
    print_success(f"Portable population bundle ready: {result.directory}")
    click.echo(result.directory)


@bundle.command("validate")
@click.argument("bundle_dir", metavar="BUNDLE", type=_PATH)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def validate_bundle_command(bundle_dir: Path, output_format: str) -> None:
    """Recompute bundle hashes, shapes, linkage, and metadata checks."""

    report = validate_exchange_bundle(bundle_dir)
    if output_format == "json":
        click.echo(json.dumps(report, indent=2, sort_keys=True))
    else:
        if report["passed"]:
            print_success("Exchange bundle validation passed")
        else:
            click.echo("Exchange bundle validation failed:", err=True)
            for issue in report["issues"]:
                click.echo(f"- {issue}", err=True)
    if not report["passed"]:
        raise click.ClickException("Exchange bundle validation failed.")


def _geography_universe(
    census_vintage: int | None,
    geography_level: str | None,
    identifier_namespace: str | None,
    geography_column: str | None,
) -> GeographyUniverse | None:
    values = (
        census_vintage,
        geography_level,
        identifier_namespace,
        geography_column,
    )
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(
            "Census geography requires --census-vintage, --geography-level, "
            "--identifier-namespace, and --geography-column together"
        )
    assert census_vintage is not None
    assert geography_level is not None
    assert identifier_namespace is not None
    assert geography_column is not None
    return GeographyUniverse(
        census_vintage=census_vintage,
        geography_level=geography_level,
        identifier_namespace=identifier_namespace,
        identifier_column=geography_column,
    )
