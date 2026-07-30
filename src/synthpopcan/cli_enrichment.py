"""Source-independent external-data enrichment commands."""

from __future__ import annotations

__all__ = ["enrich"]

import json
from pathlib import Path

import click

from synthpopcan.cli_output import click_file_access_error, click_value_error
from synthpopcan.console import print_wrote
from synthpopcan.enrichment import (
    import_normalized_layer,
    read_enrichment_manifest,
    read_resource_record,
    read_source_profile,
    register_resource,
    verify_enrichment_manifest,
)
from synthpopcan.geography import GeographyUniverse

_PATH = click.Path(path_type=Path)


@click.group()
def enrich() -> None:
    """Register sources and attach validated sidecar layers to populations."""


@enrich.command("register-resource")
@click.argument("resource_path", metavar="RESOURCE", type=_PATH)
@click.option(
    "--source-profile",
    "source_profile_path",
    required=True,
    type=_PATH,
    help="Versioned source-profile JSON.",
)
@click.option(
    "--acquired-at",
    required=True,
    help="Retrieval or registration timestamp, normally ISO 8601 UTC.",
)
@click.option("--media-type", required=True, help="Resource media type.")
@click.option(
    "--public-locator",
    default=None,
    help="Public authoritative URL; ignored for non-public acquisition modes.",
)
@click.option(
    "--opaque-local-id",
    default=None,
    help="Non-sensitive local identity; generated when omitted for non-public data.",
)
@click.option("--out", "output_path", required=True, type=_PATH)
def register_resource_command(
    resource_path: Path,
    source_profile_path: Path,
    acquired_at: str,
    media_type: str,
    public_locator: str | None,
    opaque_local_id: str | None,
    output_path: Path,
) -> None:
    """Create an immutable checksum record without embedding local file paths."""
    try:
        source = read_source_profile(source_profile_path)
        resource = register_resource(
            resource_path,
            source,
            acquired_at=acquired_at,
            media_type=media_type,
            public_locator=public_locator,
            opaque_local_id=opaque_local_id,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(resource.as_dict(), indent=2, sort_keys=True) + "\n"
        )
    except OSError as exc:
        raise click_file_access_error(
            Path(exc.filename) if exc.filename else resource_path,
            "read or write",
            exc,
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(output_path)


@enrich.command("import")
@click.argument("population_directory", metavar="POPULATION", type=_PATH)
@click.argument("layer_path", metavar="LAYER", type=_PATH)
@click.option(
    "--source-profile",
    "source_profile_path",
    required=True,
    type=_PATH,
    help="Versioned source-profile JSON.",
)
@click.option(
    "--resource-record",
    "resource_record_path",
    required=True,
    type=_PATH,
    help="Immutable resource-record JSON.",
)
@click.option("--layer-id", required=True, help="Stable normalized-layer identifier.")
@click.option(
    "--layer-class",
    required=True,
    type=click.Choice(
        [
            "area-attributes",
            "facilities-points",
            "household-person",
            "networks-activities-relationships",
        ]
    ),
)
@click.option(
    "--key-column",
    "key_columns",
    required=True,
    multiple=True,
    help="Layer key column; repeat for composite keys.",
)
@click.option(
    "--variable",
    "variables",
    multiple=True,
    help="Normalized value column; repeat for multiple variables.",
)
@click.option(
    "--observed-status",
    default="observed",
    type=click.Choice(["observed", "derived", "modeled"]),
    show_default=True,
)
@click.option(
    "--limitation",
    "limitations",
    multiple=True,
    help="Reader-facing limitation; repeat as needed.",
)
@click.option("--base-census-vintage", type=int, default=None)
@click.option("--base-geo-level", default=None)
@click.option("--base-geo-namespace", default=None)
@click.option("--base-geo-column", default=None)
@click.option("--base-dguid-column", default=None)
@click.option("--out", "output_directory", required=True, type=_PATH)
@click.option(
    "--format",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json"]),
    show_default=True,
)
def import_layer_command(
    population_directory: Path,
    layer_path: Path,
    source_profile_path: Path,
    resource_record_path: Path,
    layer_id: str,
    layer_class: str,
    key_columns: tuple[str, ...],
    variables: tuple[str, ...],
    observed_status: str,
    limitations: tuple[str, ...],
    base_census_vintage: int | None,
    base_geo_level: str | None,
    base_geo_namespace: str | None,
    base_geo_column: str | None,
    base_dguid_column: str | None,
    output_directory: Path,
    output_format: str,
) -> None:
    """Validate and publish a normalized layer without changing base tables."""
    try:
        source = read_source_profile(source_profile_path)
        resource = read_resource_record(resource_record_path)
        geography_values = (
            base_census_vintage,
            base_geo_level,
            base_geo_namespace,
            base_geo_column,
        )
        if any(value is not None for value in geography_values) and not all(
            value is not None for value in geography_values
        ):
            raise ValueError(
                "base Census vintage, level, namespace, and column must be "
                "provided together"
            )
        if all(value is not None for value in geography_values):
            assert base_census_vintage is not None
            assert base_geo_level is not None
            assert base_geo_namespace is not None
            assert base_geo_column is not None
            base_geography = GeographyUniverse(
                census_vintage=base_census_vintage,
                geography_level=base_geo_level,
                identifier_namespace=base_geo_namespace,
                identifier_column=base_geo_column,
                dguid_column=base_dguid_column,
            )
        else:
            base_geography = None
        command = click.get_current_context().command_path
        manifest, validation = import_normalized_layer(
            population_directory,
            layer_path,
            output_directory,
            source=source,
            resource=resource,
            layer_id=layer_id,
            layer_class=layer_class,
            key_columns=key_columns,
            variables=variables,
            base_geography=base_geography,
            observed_status=observed_status,
            reproduction_request={
                "workflow": "enrichment",
                "operation": "import-normalized-layer",
                "command": command,
                "population": str(population_directory),
                "layer": str(layer_path),
            },
            limitations=limitations,
        )
    except OSError as exc:
        raise click_file_access_error(
            Path(exc.filename) if exc.filename else layer_path,
            "read or write",
            exc,
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(output_directory / "manifest.json")
    print_wrote(output_directory / layer_path.name)
    result = {"manifest": manifest.as_dict(), "validation": validation}
    if output_format == "json":
        click.echo(json.dumps(result, sort_keys=True))
    else:
        click.echo(
            f"Validated {validation['rows']:,} rows for layer {layer_id}; "
            "the base population was not modified."
        )


@enrich.command("validate")
@click.argument("manifest_path", metavar="MANIFEST", type=_PATH)
@click.option(
    "--population",
    "population_directory",
    required=True,
    type=_PATH,
    help="Directory containing the referenced linked-population v1 files.",
)
@click.option(
    "--format",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json"]),
    show_default=True,
)
def validate_enrichment_command(
    manifest_path: Path,
    population_directory: Path,
    output_format: str,
) -> None:
    """Recompute base and sidecar hashes recorded by an enrichment manifest."""
    try:
        manifest = read_enrichment_manifest(manifest_path)
        report = verify_enrichment_manifest(
            manifest,
            manifest_path.parent,
            base_directory=population_directory,
        )
    except OSError as exc:
        raise click_file_access_error(
            Path(exc.filename) if exc.filename else manifest_path,
            "read",
            exc,
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    if output_format == "json":
        click.echo(json.dumps(report, sort_keys=True))
    elif report["passed"]:
        click.echo("Enrichment manifest and base population hashes are valid.")
    else:
        issues = report.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        for issue in issues:
            click.echo(f"Problem: {issue}")
    if not report["passed"]:
        raise click.ClickException("enrichment validation failed")
