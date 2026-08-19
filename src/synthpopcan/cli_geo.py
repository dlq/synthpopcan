"""Small-area linked synthesis commands."""

from __future__ import annotations

__all__ = ["small_area"]

import json
from collections.abc import Mapping
from pathlib import Path

import click

from synthpopcan.cli_output import click_file_access_error, click_value_error
from synthpopcan.console import print_wrote
from synthpopcan.control_packs import (
    build_control_pack_evidence,
    list_builtin_control_packs,
    load_control_pack,
    plan_control_pack,
    write_control_pack,
    write_control_pack_evidence,
)
from synthpopcan.controls import read_control_table
from synthpopcan.diagnostics import format_categories, format_number
from synthpopcan.geography import GeographyUniverse, statcan_geography_universe
from synthpopcan.linked_schema import (
    read_linked_population_contract,
    validate_linked_population_contract,
    write_linked_population_contract,
)
from synthpopcan.model_licensing import validate_prepared_model_licensing
from synthpopcan.national_small_area import CANADA_SMALL_AREA_JURISDICTIONS
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    estimate_small_area_run,
)
from synthpopcan.workflows.ipf import read_csv_records

_BOUNDARIES_HELP = (
    "StatCan boundary shapefile (.shp), pre-converted GeoJSON (.geojson), "
    "or the directory containing the shapefile. "
    "For CTs: lct_000b16a_e.shp; for ADAs: lada000b16a_e.shp. "
    "Shapefiles are reprojected automatically. "
    "Use 'geo boundaries' to produce a local GeoJSON once."
)

# Known StatCan geography column → (shapefile name fragment, attribute field)
_GEO_DEFAULTS: dict[str, tuple[str, str]] = {
    "ct": ("lct", "CTUID"),
    "ada": ("lada", "ADAUID"),
    "da": ("lda", "DAUID"),
    "csd": ("lcsd", "CSDUID"),
    "cd": ("lcd", "CDUID"),
    "pr": ("lpr", "PRUID"),
}
_NATIONAL_SMALL_AREA_JURISDICTION_CHOICES = tuple(
    value
    for item in CANADA_SMALL_AREA_JURISDICTIONS
    for value in (item.pruid, item.abbreviation)
)


def _resolve_boundaries(boundaries_path: Path, geo_column: str) -> Path:
    """Return the resolved boundary file path.

    Accepts a ``.geojson`` file directly, a ``.shp`` file directly, or a
    directory (in which case the correct ``.shp`` is located by name).
    """
    if boundaries_path.suffix.lower() == ".geojson":
        return boundaries_path
    if boundaries_path.is_dir():
        col = geo_column.lower()
        fragment, _ = _GEO_DEFAULTS.get(col, ("", ""))
        candidates = list(boundaries_path.glob("*.shp"))
        if fragment:
            candidates = [p for p in candidates if fragment in p.name.lower()]
        if not candidates:
            raise click.ClickException(
                f"No .shp file found in {boundaries_path} "
                f"for geography '{geo_column}'. "
                "Pass the full path to the .shp file instead."
            )
        if len(candidates) > 1:
            raise click.ClickException(
                f"Multiple shapefiles found in {boundaries_path}: "
                + ", ".join(p.name for p in candidates)
                + ". Pass the full path to the .shp file."
            )
        return candidates[0]
    return boundaries_path


def _resolve_id_field(geo_column: str, boundaries_path: Path) -> str:
    """Return the StatCan attribute field name for *geo_column*, or raise."""
    col = geo_column.lower()
    if col in _GEO_DEFAULTS:
        return _GEO_DEFAULTS[col][1]
    # Fallback: uppercase the column and append UID
    # e.g. "cma" → "CMAUID"
    guessed = col.upper() + "UID"
    click.echo(
        f"Warning: unknown geography '{geo_column}', guessing shapefile field "
        f"'{guessed}'. Pass --geo-id-field to override.",
        err=True,
    )
    return guessed


_PATH = click.Path(path_type=Path)


def _linked_population_paths(directory: Path) -> tuple[Path, Path]:
    """Return the conventional household and person paths in an artifact directory."""

    return directory / "households.csv", directory / "persons.csv"


def _linked_population_licensing(
    households_path: Path,
    persons_path: Path,
) -> dict[str, object] | None:
    if households_path.parent.resolve() != persons_path.parent.resolve():
        return None
    manifest_path = households_path.parent / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        contract = read_linked_population_contract(manifest_path)
        licensing = contract.get("licensing")
    except ValueError as linked_error:
        try:
            payload = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            raise linked_error from None
        if not isinstance(payload, dict) or payload.get("schema_version") != (
            "synthpopcan-tree-generation-manifest-v1"
        ):
            raise linked_error
        embedded = payload.get("linked_population")
        if not isinstance(embedded, dict):
            raise linked_error
        validate_linked_population_contract(embedded)
        contract = embedded
        licensing = payload.get("licensing", contract.get("licensing"))
    tables = contract.get("tables")
    if not isinstance(tables, Mapping):
        return None
    households = tables.get("households")
    persons = tables.get("persons")
    if not isinstance(households, Mapping) or not isinstance(persons, Mapping):
        return None
    if (
        households.get("path") != households_path.name
        or persons.get("path") != persons_path.name
    ):
        return None
    return (
        validate_prepared_model_licensing(licensing) if licensing is not None else None
    )


def _optional_geography_universe(
    *,
    census_vintage: int | None,
    geography_level: str | None,
    identifier_namespace: str | None,
    identifier_column: str,
    dguid_column: str | None,
) -> GeographyUniverse | None:
    supplied = (census_vintage, geography_level, identifier_namespace)
    if all(value is None for value in supplied):
        if dguid_column is not None:
            raise click.UsageError(
                "--geo-dguid-column requires the geography identity options"
            )
        return None
    if any(value is None for value in supplied):
        raise click.UsageError(
            "--census-vintage, --geo-level, and --geo-namespace must be "
            "provided together"
        )
    try:
        return GeographyUniverse(
            census_vintage=census_vintage,  # type: ignore[arg-type]
            geography_level=geography_level,  # type: ignore[arg-type]
            identifier_namespace=identifier_namespace,  # type: ignore[arg-type]
            identifier_column=identifier_column,
            dguid_column=dguid_column,
        )
    except ValueError as exc:
        raise click_value_error(exc) from exc


@click.group("geo")
# Keep the Python object named for the field term while exposing a shorter CLI group.
def small_area() -> None:
    """Assign and calibrate linked households to target geographies."""


@small_area.group("control-packs")
def control_packs_group() -> None:
    """Inspect, bind, and plan reviewed small-area control packs."""


@control_packs_group.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"]),
    default="summary",
    show_default=True,
)
def control_packs_list_command(output_format: str) -> None:
    """List built-in control packs for 2016 and 2021."""

    packs = list_builtin_control_packs()
    if output_format == "json":
        click.echo(json.dumps(packs, sort_keys=True))
        return
    for pack in packs:
        click.echo(
            f"{pack['identifier']}  Census {pack['census_vintage']}  "
            f"{str(pack['geography_level']).upper()}"
        )


@control_packs_group.command("show")
@click.argument("pack", metavar="PACK")
@click.option(
    "--out",
    "output_path",
    type=_PATH,
    default=None,
    help="Optionally write the normalized strict manifest to this JSON path.",
)
def control_packs_show_command(pack: str, output_path: Path | None) -> None:
    """Show a built-in pack identifier or strict local pack manifest."""

    try:
        manifest = load_control_pack(pack)
        if output_path is not None:
            write_control_pack(manifest, output_path)
    except ValueError as exc:
        raise click_value_error(exc) from exc
    if output_path is not None:
        print_wrote(output_path)
        return
    click.echo(json.dumps(manifest.as_dict(), indent=2, sort_keys=True))


@control_packs_group.command("evidence")
@click.argument("pack", metavar="PACK")
@click.option("--controls", "controls_path", required=True, type=_PATH)
@click.option(
    "--person-controls",
    "person_controls_path",
    required=True,
    type=_PATH,
)
@click.option(
    "--universe-evidence",
    "universe_evidence_path",
    required=True,
    type=_PATH,
    help=(
        "JSON mapping each control geography to total_population and "
        "persons_in_private_households; an envelope may also include "
        "geographies and excluded_geographies."
    ),
)
@click.option("--out", "output_path", required=True, type=_PATH)
def control_packs_evidence_command(
    pack: str,
    controls_path: Path,
    person_controls_path: Path,
    universe_evidence_path: Path,
    output_path: Path,
) -> None:
    """Bind exact controls to reviewed source and universe evidence."""

    try:
        manifest = load_control_pack(pack)
        household_controls = read_control_table(controls_path)
        person_controls = read_control_table(person_controls_path)
        raw = _read_json_object(universe_evidence_path)
        raw_geographies = raw.get("geographies", raw)
        if not isinstance(raw_geographies, Mapping):
            raise ValueError("universe evidence geographies must be a JSON object")
        geographies: dict[str, Mapping[str, object]] = {}
        for geography, value in raw_geographies.items():
            if not isinstance(geography, str) or not isinstance(value, Mapping):
                raise ValueError(
                    "universe evidence must map geography strings to JSON objects"
                )
            geographies[geography] = value
        raw_exclusions = raw.get("excluded_geographies", {})
        if not isinstance(raw_exclusions, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_exclusions.items()
        ):
            raise ValueError("excluded_geographies must map strings to reasons")
        evidence = build_control_pack_evidence(
            manifest,
            household_controls,
            person_controls,
            geographies=geographies,
            controls_source_revisions=manifest.source_revisions,
            excluded_geographies={
                str(key): str(value) for key, value in raw_exclusions.items()
            },
        )
        write_control_pack_evidence(evidence, output_path)
    except OSError as exc:
        filename = exc.filename or universe_evidence_path
        raise click_file_access_error(Path(filename), "read or write", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(output_path)


@control_packs_group.command("plan")
@click.argument("pack", metavar="PACK")
@click.argument("population_path", metavar="POPULATION", type=_PATH)
@click.option("--persons", "persons_path", type=_PATH)
@click.option("--controls", "controls_path", required=True, type=_PATH)
@click.option(
    "--person-controls",
    "person_controls_path",
    required=True,
    type=_PATH,
)
@click.option("--evidence", "evidence_path", required=True, type=_PATH)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"]),
    default="summary",
    show_default=True,
)
def control_packs_plan_command(
    pack: str,
    population_path: Path,
    persons_path: Path | None,
    controls_path: Path,
    person_controls_path: Path,
    evidence_path: Path,
    output_format: str,
) -> None:
    """Check a pack, candidates, controls, and evidence without fitting."""

    if population_path.is_dir():
        households_path, inferred_persons = _linked_population_paths(population_path)
        if persons_path is None:
            persons_path = inferred_persons
    else:
        households_path = population_path
        if persons_path is None:
            raise click.UsageError(
                "--persons is required when POPULATION is a household CSV"
            )
    try:
        plan = plan_control_pack(
            pack,
            read_csv_records(households_path),
            read_csv_records(persons_path),
            read_control_table(controls_path),
            read_control_table(person_controls_path),
            evidence=evidence_path,
        )
    except OSError as exc:
        filename = exc.filename or households_path
        raise click_file_access_error(Path(filename), "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    if output_format == "json":
        click.echo(json.dumps(plan, sort_keys=True))
    else:
        status = "PASS" if plan["passed"] else "FAIL"
        geographies = plan.get("geographies", {})
        geography_count = (
            geographies.get("count", 0) if isinstance(geographies, Mapping) else 0
        )
        click.echo(
            f"{status}: {plan['pack']['identifier']} for {geography_count} geographies"
        )
        for issue in plan["issues"]:
            if isinstance(issue, Mapping):
                click.echo(
                    f"  {str(issue.get('severity', 'error')).upper()}: "
                    f"{issue.get('message', '')}"
                )
    if not plan["passed"]:
        raise click.exceptions.Exit(1)


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) for key in payload
    ):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


@small_area.command("estimate")
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Normalized controls CSV with one target geography dimension.",
)
@click.option(
    "--geo-dimension",
    required=True,
    help="Dimension name in controls, such as ct or ada.",
)
@click.option(
    "--candidate-households",
    required=True,
    type=int,
    help="Number of candidate household rows planned for calibration.",
)
@click.option(
    "--pool-size",
    type=int,
    default=None,
    help="Optional --pool-size value planned for geo calibrate or geo synthesize.",
)
@click.option(
    "--average-persons-per-household",
    default=2.22,
    type=float,
    show_default=True,
    help="Approximate person rows per assigned household for output-size estimates.",
)
@click.option(
    "--format",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json"]),
    show_default=True,
    help="Print a short summary or the full machine-readable estimate.",
)
def estimate_command(
    controls_path: Path,
    geo_dimension: str,
    candidate_households: int,
    pool_size: int | None,
    average_persons_per_household: float,
    output_format: str,
) -> None:
    """Estimate small-area output scale and recommended run surface."""
    from synthpopcan.controls import read_control_table

    try:
        controls = read_control_table(controls_path)
        estimate = estimate_small_area_run(
            controls,
            geography_dimension=geo_dimension,
            candidate_households=candidate_households,
            pool_size=pool_size,
            average_persons_per_household=average_persons_per_household,
        )
    except OSError as exc:
        filename = exc.filename or controls_path
        raise click_file_access_error(Path(filename), "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    if output_format == "json":
        click.echo(json.dumps(estimate, sort_keys=True))
        return

    click.echo(
        f"Target geographies: {estimate['target_geographies']:,}\n"
        f"Target households: {estimate['target_households']:,}\n"
        f"Estimated persons: {estimate['estimated_persons']:,}\n"
        f"Estimated output rows: {estimate['estimated_total_output_rows']:,}\n"
        f"Calibration pool: {estimate['calibration_pool_size']:,} of "
        f"{estimate['candidate_households']:,} candidates\n"
        f"Fits to run: {estimate['fits_to_run']:,}\n"
        "Recommended surface: "
        f"{_format_surface_recommendation(str(estimate['recommended_surface']))}"
    )
    click.echo("Guidance:")
    for item in estimate["guidance"]:
        click.echo(f"  - {item}")


def _format_surface_recommendation(recommendation: str) -> str:
    if recommendation == "web_app_ok":
        return "web app, CLI, or Python API"
    if recommendation == "cli_or_python_api":
        return "CLI or Python API"
    return recommendation


@small_area.command("calibrate")
@click.argument("population_path", metavar="POPULATION", type=_PATH)
@click.option(
    "--persons",
    "persons_path",
    type=_PATH,
    help="Person CSV when POPULATION is a household CSV.",
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Normalized controls with one target geography dimension.",
)
@click.option(
    "--person-controls",
    "person_controls_path",
    type=_PATH,
    help=(
        "Optional person-level controls with the same target geographies. "
        "Household weights are jointly refined while links remain intact."
    ),
)
@click.option(
    "--control-pack",
    default=None,
    help="Built-in control-pack identifier or strict local manifest JSON.",
)
@click.option(
    "--control-pack-evidence",
    type=_PATH,
    default=None,
    help="Evidence JSON bound to the selected pack and exact control tables.",
)
@click.option(
    "--geo-dimension",
    required=True,
    help="Control dimension naming the target geography, such as ct or ada.",
)
@click.option(
    "--geo-column",
    default=None,
    help="Output geography column. Defaults to --geo-dimension.",
)
@click.option(
    "--census-vintage",
    type=int,
    default=None,
    help="Census year defining the target geography identifiers.",
)
@click.option(
    "--geo-level",
    default=None,
    help="Explicit geography level such as da, ada, ct, or csd.",
)
@click.option(
    "--geo-namespace",
    default=None,
    help="Stable identifier namespace, such as statcan:census:2021:da.",
)
@click.option(
    "--geo-dguid-column",
    default=None,
    help="Optional DGUID column carried by the same geography resource.",
)
@click.option(
    "--out",
    "output_dir",
    required=True,
    type=_PATH,
    help="Output directory for linked rows and the calibration report.",
)
@click.option(
    "--include-weights",
    is_flag=True,
    help="Also write the potentially large fitted weights CSV.",
)
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
    "--pool-size",
    "pool_size",
    default=None,
    type=int,
    help=(
        "Maximum candidate households to use. "
        "5 000–10 000 reproduces aggregate statistics with near-identical "
        "accuracy to the full pool and runs ~10× faster. "
        "Omit when individual-household uniqueness matters."
    ),
)
@click.option(
    "--subsample-seed",
    "subsample_seed",
    default=42,
    type=int,
    show_default=True,
    help=(
        "Seed for the --pool-size candidate subsample. Vary it to check how "
        "sensitive results are to which candidates are drawn. Ignored without "
        "--pool-size."
    ),
)
@click.option(
    "--format",
    "output_format",
    default="summary",
    type=click.Choice(["summary", "json"]),
    show_default=True,
    help="Print a short summary or the full machine-readable report.",
)
def calibrate_command(
    population_path: Path,
    persons_path: Path | None,
    controls_path: Path,
    person_controls_path: Path | None,
    control_pack: str | None,
    control_pack_evidence: Path | None,
    geo_dimension: str,
    geo_column: str | None,
    census_vintage: int | None,
    geo_level: str | None,
    geo_namespace: str | None,
    geo_dguid_column: str | None,
    output_dir: Path,
    include_weights: bool,
    max_iterations: int,
    tolerance: float,
    pool_size: int | None,
    subsample_seed: int,
    output_format: str,
) -> None:
    """Calibrate linked household/person candidates to geography controls."""

    if population_path.is_dir():
        households_path, inferred_persons = _linked_population_paths(population_path)
        if persons_path is None:
            persons_path = inferred_persons
    else:
        households_path = population_path
        if persons_path is None:
            raise click.UsageError(
                "--persons is required when POPULATION is a household CSV"
            )
    input_licensing = _linked_population_licensing(households_path, persons_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    households_out, persons_out = _linked_population_paths(output_dir)
    report_out = output_dir / "report.json"
    weights_out = output_dir / "weights.csv" if include_weights else None
    output_geo_column = geo_column or geo_dimension
    geography_universe = _optional_geography_universe(
        census_vintage=census_vintage,
        geography_level=geo_level,
        identifier_namespace=geo_namespace,
        identifier_column=output_geo_column,
        dguid_column=geo_dguid_column,
    )

    try:
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            person_controls_path=person_controls_path,
            control_pack=control_pack,
            control_pack_evidence=control_pack_evidence,
            geography_dimension=geo_dimension,
            geography_column=output_geo_column,
            geography_universe=geography_universe,
            households_out=households_out,
            persons_out=persons_out,
            weights_out=weights_out,
            report_out=report_out,
            max_iterations=max_iterations,
            tolerance=tolerance,
            pool_size=pool_size,
            subsample_seed=subsample_seed,
        )
    except OSError as exc:
        filename = exc.filename or households_path
        raise click_file_access_error(Path(filename), "read or write", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    manifest_out = output_dir / "manifest.json"
    write_linked_population_contract(
        manifest_out,
        households_out,
        persons_out,
        geography_column=output_geo_column,
        licensing=input_licensing,
    )

    print_wrote(households_out)
    print_wrote(persons_out)
    print_wrote(manifest_out)
    if weights_out is not None:
        print_wrote(weights_out)
    print_wrote(report_out)
    if output_format == "json":
        click.echo(json.dumps(summary, sort_keys=True))
        return
    hh_n = summary["assigned_households"]
    p_n = summary["assigned_persons"]
    geo_n = len(summary["geographies"])
    click.echo(
        f"Assigned {hh_n:,} households and {p_n:,} persons "
        f"across {geo_n:,} {output_geo_column} geographies."
    )
    _print_calibrate_linked_diagnostics(summary)


def _print_calibrate_linked_diagnostics(summary: dict[str, object]) -> None:
    report_summary = summary.get("summary", {})
    if not isinstance(report_summary, dict):
        return
    non_converged_count = int(report_summary.get("non_converged_count", 0) or 0)
    if non_converged_count:
        noun = "geography" if non_converged_count == 1 else "geographies"
        click.echo(f"{non_converged_count:,} {noun} did not converge.")

    input_checks = summary.get("input_checks", {})
    if isinstance(input_checks, dict):
        for unit_report in input_checks.values():
            if not isinstance(unit_report, dict):
                continue
            for issue in unit_report.get("issues", []):
                if isinstance(issue, dict) and issue.get("severity") == "warning":
                    click.echo(f"Preflight warning: {issue.get('message', '')}")

    residuals = report_summary.get("largest_residuals", [])
    if isinstance(residuals, list) and residuals:
        first = residuals[0]
        if isinstance(first, dict):
            click.echo(f"Largest residual: {_format_small_area_residual(first)}")

    steps = summary.get("suggested_next_steps", [])
    if isinstance(steps, list) and steps:
        click.echo("Next steps:")
        for step in steps:
            click.echo(f"  - {step}")


def _format_small_area_residual(row: dict[str, object]) -> str:
    categories = row.get("categories", {})
    category_label = (
        format_categories({str(k): str(v) for k, v in categories.items()})
        if isinstance(categories, dict)
        else ""
    )
    parts = [
        format_number(_coerce_float(row.get("abs_error", 0.0))),
        str(row.get("geography", "")),
        str(row.get("margin", "")),
        category_label,
    ]
    return " ".join(part for part in parts if part)


def _coerce_float(value: object) -> float:
    if not isinstance(value, int | float | str):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# map command
# ---------------------------------------------------------------------------


@small_area.command("map")
@click.argument("population_path", metavar="POPULATION", type=_PATH)
@click.option(
    "--persons",
    "persons_path",
    default=None,
    type=_PATH,
    help=(
        "Optional person CSV when POPULATION is a household CSV. "
        "Adds person-level variables: persons, % children, % seniors, "
        "% immigrants, % visible minority, median household income."
    ),
)
@click.option(
    "--boundaries",
    "boundaries_path",
    default=None,
    type=_PATH,
    help=(
        f"{_BOUNDARIES_HELP} Inferred from a completed national plan when "
        "POPULATION is plan.json or its directory."
    ),
)
@click.option(
    "--geo-column",
    default=None,
    help=(
        "Column in the household CSV that holds the geography ID (e.g. ct or ada). "
        "Inferred from a completed national plan."
    ),
)
@click.option(
    "--geo-id-field",
    default=None,
    help=(
        "Attribute field in the shapefile matching the geography column. "
        "Inferred automatically for known StatCan geographies "
        "(ct→CTUID, ada→ADAUID, da→DAUID, …)."
    ),
)
@click.option("--census-vintage", type=int, default=None)
@click.option("--geo-level", default=None)
@click.option("--geo-namespace", default=None)
@click.option("--geo-dguid-column", default=None)
@click.option(
    "--jurisdiction",
    "jurisdiction_values",
    multiple=True,
    type=click.Choice(
        [item.pruid for item in CANADA_SMALL_AREA_JURISDICTIONS]
        + [item.abbreviation.lower() for item in CANADA_SMALL_AREA_JURISDICTIONS],
        case_sensitive=False,
    ),
    help=(
        "Render one or more completed province/territory subsets of a partial "
        "national plan."
    ),
)
@click.option(
    "--out",
    "out_path",
    default=None,
    type=_PATH,
    help=(
        "Destination HTML file. Defaults to <households-stem>-map.html for a "
        "CSV and national-map.html beside a national plan."
    ),
)
@click.option(
    "--title",
    default=None,
    help="Map title shown in the panel. Defaults to the output filename stem.",
)
@click.option(
    "--coord-precision",
    default=None,
    type=click.IntRange(min=0, max=6),
    help=(
        "Decimal places kept in WGS-84 coordinates. Defaults to 5 for a single "
        "population and 3 for a national plan."
    ),
)
def map_command(
    population_path: Path,
    persons_path: Path | None,
    boundaries_path: Path | None,
    geo_column: str | None,
    geo_id_field: str | None,
    census_vintage: int | None,
    geo_level: str | None,
    geo_namespace: str | None,
    geo_dguid_column: str | None,
    jurisdiction_values: tuple[str, ...],
    out_path: Path | None,
    title: str | None,
    coord_precision: int | None,
) -> None:
    """Generate a MapLibre GL JS choropleth map from synthesis output.

    The resulting HTML file is self-contained and opens directly in a browser.
    It uses WebGL for fast rendering and fetches base-map tiles from OpenFreeMap
    (requires an internet connection when viewing).

    Minimal usage:

    \b
        synthpopcan geo map \\
            synthetic-households.csv \\
            --boundaries /path/to/statcan-boundaries/ \\
            --geo-column ct

    A completed national run needs no repeated boundary or geography options:

    \b
        synthpopcan geo map data/work/canada-ada-2021
    """
    national_plan_path = (
        population_path / "plan.json"
        if population_path.is_dir() and (population_path / "plan.json").is_file()
        else (
            population_path
            if population_path.is_file() and population_path.name == "plan.json"
            else None
        )
    )
    if national_plan_path is not None:
        if persons_path is not None:
            raise click.UsageError(
                "--persons must be omitted when POPULATION is a national plan"
            )
        from synthpopcan.api import render_small_area_map

        selector_lookup = {
            selector.casefold(): item.pruid
            for item in CANADA_SMALL_AREA_JURISDICTIONS
            for selector in (item.pruid, item.abbreviation)
        }
        jurisdiction_pruids = (
            tuple(selector_lookup[value.casefold()] for value in jurisdiction_values)
            if jurisdiction_values
            else None
        )

        try:
            if jurisdiction_pruids is not None:
                destination = render_small_area_map(
                    households=national_plan_path,
                    out=out_path,
                    title=title,
                    coord_precision=coord_precision,
                    jurisdiction_pruids=jurisdiction_pruids,
                )
            else:
                destination = render_small_area_map(
                    households=national_plan_path,
                    out=out_path,
                    title=title,
                    coord_precision=coord_precision,
                )
        except OSError as exc:
            raise click_file_access_error(
                national_plan_path,
                "process",
                exc,
            ) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc
        print_wrote(destination)
        click.echo(
            f"Open {destination} in a browser to explore the synthesis results.",
            err=True,
        )
        click.echo(destination)
        return

    if boundaries_path is None:
        raise click.UsageError("--boundaries is required for a population CSV")
    if geo_column is None:
        raise click.UsageError("--geo-column is required for a population CSV")
    coord_precision = 5 if coord_precision is None else coord_precision

    from synthpopcan.map_render import render_synthesis_map

    if population_path.is_dir():
        households_path, inferred_persons = _linked_population_paths(population_path)
        if persons_path is None:
            persons_path = inferred_persons
    else:
        households_path = population_path

    boundaries_path = _resolve_boundaries(boundaries_path, geo_column)
    if geo_id_field is None:
        geo_id_field = _resolve_id_field(geo_column, boundaries_path)
    if out_path is None:
        if population_path.is_dir():
            out_path = population_path / "map.html"
        else:
            out_path = households_path.parent / (households_path.stem + "-map.html")
    if title is None:
        title = out_path.stem.replace("-", " ").replace("_", " ").title()
    geography_universe = _optional_geography_universe(
        census_vintage=census_vintage,
        geography_level=geo_level,
        identifier_namespace=geo_namespace,
        identifier_column=geo_column,
        dguid_column=geo_dguid_column,
    )

    try:
        render_synthesis_map(
            households_path=households_path,
            persons_path=persons_path,
            boundaries_path=boundaries_path,
            geography_column=geo_column,
            geography_id_field=geo_id_field,
            out_path=out_path,
            title=title,
            coord_precision=coord_precision,
            geography_context=(
                geography_universe.as_dict() if geography_universe is not None else None
            ),
        )
    except ImportError as exc:
        raise click.ClickException(
            f"Missing dependency: {exc}. Install pyshp: pip install pyshp"
        ) from exc
    except OSError as exc:
        filename = exc.filename or households_path
        raise click_file_access_error(Path(filename), "process", exc) from exc
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    print_wrote(out_path)
    click.echo(
        f"Open {out_path} in a browser to explore the synthesis results.", err=True
    )
    click.echo(out_path)


# ---------------------------------------------------------------------------
# controls command
# ---------------------------------------------------------------------------


@small_area.command("controls")
@click.option(
    "--profile",
    "profile_path",
    required=True,
    type=_PATH,
    help=(
        "StatCan Census Profile bulk CSV (2247-variable form). "
        "Fetch with: synthpopcan statcan census-profile fetch --geo-level ada"
    ),
)
@click.option(
    "--geo-column",
    required=True,
    help=(
        "Target geography type: ada, ct, csd, cd, or da. "
        "Determines which GEO_LEVEL rows to read from the profile."
    ),
)
@click.option(
    "--target",
    "target_total",
    required=True,
    type=int,
    help="Total household count to scale controls to (e.g. 5500000).",
)
@click.option(
    "--control-pack",
    "control_pack_identifier",
    default=None,
    help=(
        "Optional built-in control pack. Expanded housing packs extract and "
        "scale every reviewed household margin; omit for the legacy household-"
        "size and tenure preparation path."
    ),
)
@click.option(
    "--candidates",
    "candidates_path",
    default=None,
    type=_PATH,
    help=(
        "Linked population directory to recode for calibration. "
        "household_size values above 5 are capped at 5 to match Census categories. "
        "Omit when using geo synthesize, which handles recoding itself."
    ),
)
@click.option(
    "--geo-prefix",
    default=None,
    help=(
        "Filter to geographies whose ID starts with this prefix. "
        "Use the two-digit province code for ADAs (e.g. 35=Ontario, 24=Quebec). "
        "Use the three-digit CMA code for CTs (e.g. 462=Montreal). "
        "Omit to include all geographies in the profile."
    ),
)
@click.option(
    "--geo-level-value",
    default=None,
    help=(
        "Override the GEO_LEVEL value used to filter profile rows "
        "(default: 3 for ada/csd/da, 2 for ct/cd). "
        "Only needed for non-standard profiles."
    ),
)
@click.option(
    "--controls-out",
    "controls_out",
    default=None,
    type=_PATH,
    help=(
        "Destination path for the controls CSV. "
        "Defaults to <candidates-stem>-controls-<target>.csv "
        "beside the candidates file."
    ),
)
@click.option(
    "--candidates-out",
    "candidates_out",
    default=None,
    type=_PATH,
    help=(
        "Destination directory for the recoded linked population. "
        "Defaults to <candidates-name>-recoded beside the candidates directory."
    ),
)
@click.option(
    "--hhsize-cap",
    default=5,
    type=int,
    show_default=True,
    help="Group household_size values at this maximum category.",
)
@click.option(
    "--household-size-group-column",
    default="household_size_group",
    show_default=True,
    help=(
        "Column used for Census-style household-size groups. "
        "Use household_size only for old workflows that intentionally overwrite "
        "exact household sizes."
    ),
)
def controls_command(
    profile_path: Path,
    geo_column: str,
    target_total: int,
    control_pack_identifier: str | None,
    candidates_path: Path | None,
    geo_prefix: str | None,
    geo_level_value: str | None,
    controls_out: Path | None,
    candidates_out: Path | None,
    hhsize_cap: int,
    household_size_group_column: str,
) -> None:
    """Build IPF control tables from a StatCan Census Profile for small-area synthesis.

    By default, reads household-size and tenure margins from a Census Profile.
    With ``--control-pack``, reads every reviewed household margin declared by
    that pack. It scales them to the target household count and writes a
    long-format controls CSV ready for ``calibrate`` or ``synthesize``.
    Household-size controls use
    household_size_group by default because Census Profile combines 5-or-more
    person households into one category.  When --candidates is supplied, also
    writes that grouped column while preserving exact household_size.

    Geographies missing any required margin are automatically dropped (they
    would cause an IPF dimension mismatch in calibration).

    See the small-area documentation for worked examples.
    """
    from synthpopcan.small_area_controls import (
        extract_controls_from_profile,
        extract_household_controls_for_pack,
        scale_and_validate_controls,
        scale_and_validate_pack_controls,
        write_controls_csv,
        write_pack_controls_csv,
        write_recoded_candidates,
    )

    selected_pack = None
    if control_pack_identifier is not None:
        from synthpopcan.control_packs import load_control_pack

        try:
            selected_pack = load_control_pack(control_pack_identifier)
        except (OSError, ValueError) as exc:
            raise click_value_error(ValueError(str(exc))) from exc
        if selected_pack.geography_level != geo_column.lower():
            raise click_value_error(
                ValueError(
                    f"control pack requires {selected_pack.geography_level!r}, "
                    f"but --geo-column is {geo_column!r}"
                )
            )

    # Default output paths
    if controls_out is None:
        if candidates_path is not None:
            controls_out = candidates_path.parent / (
                f"{candidates_path.name}-controls-{target_total}.csv"
            )
        else:
            controls_out = Path(f"{geo_column}-controls-{target_total}.csv")
    if candidates_out is None and candidates_path is not None:
        candidates_out = candidates_path.parent / f"{candidates_path.name}-recoded"
    if (
        candidates_path is not None
        and candidates_out is not None
        and candidates_path.resolve() == candidates_out.resolve()
    ):
        raise click_value_error(
            ValueError("--candidates-out must differ from --candidates")
        )

    click.echo(f"Reading profile: {profile_path}")
    try:
        if selected_pack is None:
            raw = extract_controls_from_profile(
                profile_path,
                geo_column,
                geo_prefix=geo_prefix,
                geo_level_value=geo_level_value,
            )
        else:
            raw = extract_household_controls_for_pack(
                profile_path,
                selected_pack,
                geo_prefix=geo_prefix,
                geo_level_value=geo_level_value,
            )
    except OSError as exc:
        raise click_file_access_error(profile_path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    if selected_pack is None:
        n_hhsize = sum(
            1 for d in raw.values() if d.get("hhsize") and sum(d["hhsize"].values()) > 0
        )
        n_tenure = sum(
            1 for d in raw.values() if d.get("tenure") and sum(d["tenure"].values()) > 0
        )
        click.echo(
            f"  {len(raw):,} {geo_column} units found  "
            f"({n_hhsize:,} with hhsize data, {n_tenure:,} with tenure data)"
        )
        scaled, dropped = scale_and_validate_controls(raw, target_total)
    else:
        household_dimensions = [
            margin.dimensions[1]
            for margin in selected_pack.margins
            if margin.entity_level == "household"
        ]
        click.echo(
            f"  {len(raw):,} {geo_column} units found for "
            f"{len(household_dimensions)} household margins"
        )
        scaled, dropped = scale_and_validate_pack_controls(
            raw, selected_pack, target_total
        )
    if dropped:
        click.echo(
            f"  Dropped {len(dropped):,} {geo_column} unit(s) "
            "with incomplete or zero required control vectors"
        )
    if selected_pack is None:
        hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
        tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
        click.echo(
            f"  Scaled {len(scaled):,} units to "
            f"{hhsize_total:,} households (hhsize), {tenure_total:,} (tenure)"
        )
    else:
        click.echo(
            f"  Scaled {len(scaled):,} units and all household margins to "
            f"{target_total:,} households"
        )

    try:
        if selected_pack is None:
            write_controls_csv(
                scaled,
                controls_out,
                geo_column,
                household_size_column=household_size_group_column,
            )
        else:
            write_pack_controls_csv(scaled, controls_out, selected_pack)
    except OSError as exc:
        raise click_file_access_error(controls_out, "write", exc) from exc
    print_wrote(controls_out)

    if candidates_path is not None:
        import shutil

        candidate_households, candidate_persons = _linked_population_paths(
            candidates_path
        )
        click.echo(
            f"Recoding candidates ({household_size_group_column} grouped at "
            f"{hhsize_cap}+): "
            f"{candidates_path}"
        )
        assert candidates_out is not None
        candidates_out.mkdir(parents=True, exist_ok=True)
        output_households, output_persons = _linked_population_paths(candidates_out)
        try:
            n_rows = write_recoded_candidates(
                candidate_households,
                output_households,
                group_col=household_size_group_column,
                cap=hhsize_cap,
            )
            shutil.copyfile(candidate_persons, output_persons)
        except OSError as exc:
            raise click_file_access_error(candidates_path, "recode", exc) from exc
        click.echo(f"  {n_rows:,} rows written")
        print_wrote(output_households)
        print_wrote(output_persons)
        click.echo("\nNext step:")
        pack_options = (
            "    --person-controls person-controls.csv \\\n"
            f"    --control-pack {selected_pack.identifier} \\\n"
            "    --control-pack-evidence control-pack-evidence.json \\\n"
            if selected_pack is not None
            else ""
        )
        click.echo(
            f"  synthpopcan geo calibrate {candidates_out} \\\n"
            f"    --controls {controls_out} \\\n"
            f"{pack_options}"
            f"    --geo-dimension {geo_column} \\\n"
            f"    --pool-size 10000 \\\n"
            f"    --out calibrated-population/"
        )
    else:
        click.echo("\nNext step:")
        pack_options = (
            "    --person-controls person-controls.csv \\\n"
            f"    --control-pack {selected_pack.identifier} \\\n"
            "    --control-pack-evidence control-pack-evidence.json \\\n"
            if selected_pack is not None
            else ""
        )
        click.echo(
            f"  synthpopcan geo synthesize MODEL \\\n"
            f"    --households {target_total} \\\n"
            f"    --controls {controls_out} \\\n"
            f"{pack_options}"
            f"    --geo-dimension {geo_column} \\\n"
            f"    --max-household-size 5 \\\n"
            f"    --household-size-group-column {household_size_group_column} \\\n"
            f"    --out calibrated-population/"
        )


# ---------------------------------------------------------------------------
# boundaries command
# ---------------------------------------------------------------------------

_KNOWN_GEO_LEVELS = ("ct", "ada", "da", "csd", "cd", "pr")


@small_area.command("boundaries")
@click.option(
    "--geo-level",
    required=True,
    type=click.Choice(_KNOWN_GEO_LEVELS, case_sensitive=False),
    help="Geography level to download: ct, ada, da, csd, cd, or pr.",
)
@click.option(
    "--census-year",
    default="2016",
    type=click.Choice(("2016", "2021")),
    show_default=True,
    help="Boundary vintage. CT, ADA, DA, and CSD are supported for both years.",
)
@click.option(
    "--out-dir",
    "out_dir",
    required=True,
    type=_PATH,
    help="Directory where the GeoJSON file and provenance manifest will be saved.",
)
@click.option(
    "--coord-precision",
    default=5,
    type=int,
    show_default=True,
    help="Decimal places kept in WGS-84 coordinates (5 ≈ 1 m; 3 halves file size).",
)
@click.option(
    "--url",
    default=None,
    help="Override the StatCan download URL (useful for cached mirrors).",
)
def boundaries_command(
    geo_level: str,
    census_year: str,
    out_dir: Path,
    coord_precision: int,
    url: str | None,
) -> None:
    """Download and convert a StatCan census boundary shapefile to GeoJSON.

    Downloads the boundary ZIP for the specified geography level from Statistics
    Canada, extracts the shapefile, and converts it from NAD83 / Statistics
    Canada Lambert to WGS-84 GeoJSON.  The resulting ``.geojson`` file can be
    passed directly to ``geo map --boundaries``, eliminating the need to keep
    the original shapefile around.

    \b
    Supported geography levels:
        ct   — Census tracts
        ada  — Aggregate dissemination areas
        da   — Dissemination areas
        csd  — Census subdivisions
        cd   — Census divisions
        pr   — Provinces and territories

    \b
    Example:

        synthpopcan geo boundaries --census-year 2021 --geo-level ct \
          --out-dir data/derived/statcan/census/2021/boundaries/

    Boundary ZIPs are sourced from Statistics Canada's geography program. An
    internet connection is required. The 2021 products are cartographic files;
    their DGUID values are retained in the output.
    """
    from synthpopcan.map_render import prepare_boundaries_geojson
    from synthpopcan.statcan import (
        BoundaryDownload,
        fetch_boundary_zip,
        file_integrity,
        get_boundary_download,
        write_manifest,
    )

    year = int(census_year)
    try:
        entry: BoundaryDownload = get_boundary_download(geo_level, year)
    except ValueError as exc:
        raise click_value_error(exc) from exc

    click.echo(f"Downloading {entry.description} boundary file…", err=True)
    try:
        shp_path = fetch_boundary_zip(geo_level, out_dir, census_year=year, url=url)
    except OSError as exc:
        raise click.ClickException(f"Download failed: {exc}") from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    source_manifest_path = out_dir / f"{year}-boundary-{entry.geo_level}.json"
    click.echo(f"  Shapefile: {shp_path}", err=True)
    click.echo("Converting to WGS-84 GeoJSON…", err=True)

    geojson_path = out_dir / f"{year}-boundary-{geo_level.lower()}.geojson"
    property_fields = entry.property_fields
    try:
        prepare_boundaries_geojson(
            shp_path,
            id_field=entry.id_field,
            out_path=geojson_path,
            coord_precision=coord_precision,
            property_fields=property_fields,
            trust_ring_winding=True,
        )
        source_manifest = json.loads(source_manifest_path.read_text())
        write_manifest(
            source_manifest_path,
            {
                "schema_version": "synthpopcan-statcan-resource-v1",
                "source": (
                    f"Statistics Canada {year} census cartographic boundary files"
                ),
                "source_revision": entry.zip_name,
                "census_year": year,
                "geo_level": entry.geo_level,
                "description": entry.description,
                "source_url": url or entry.url,
                "source_shapefile": shp_path.name,
                "source_components_retained": False,
                "source_resources": source_manifest["resources"],
                "geojson_path": str(geojson_path),
                "geojson_id_source_field": entry.id_field,
                "geojson_properties": ["geo_id", *property_fields],
                "geography": statcan_geography_universe(
                    year,
                    entry.geo_level,
                    "geo_id",
                    dguid_column=(
                        "DGUID" if "DGUID" in entry.property_fields else None
                    ),
                ).as_dict(),
                "resource": {
                    "path": str(geojson_path),
                    **file_integrity(geojson_path),
                },
            },
        )
        for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            shp_path.with_suffix(suffix).unlink(missing_ok=True)
    except ImportError as exc:
        raise click.ClickException(
            f"Missing dependency: {exc}. Install pyshp: pip install pyshp"
        ) from exc
    except OSError as exc:
        raise click_file_access_error(geojson_path, "write", exc) from exc

    print_wrote(geojson_path)
    click.echo(
        f"\nPass this file to geo map with:\n  --boundaries {geojson_path}",
        err=True,
    )
    click.echo(geojson_path)


@small_area.command("relationship-file")
@click.option(
    "--out-dir",
    "out_dir",
    required=True,
    type=_PATH,
    help="Directory where the 2021 relationship CSV and manifest will be saved.",
)
@click.option(
    "--url",
    default=None,
    help="Override the StatCan download URL (useful for cached mirrors).",
)
def relationship_file_command(out_dir: Path, url: str | None) -> None:
    """Download the 2021 dissemination-geographies relationship CSV.

    The dissemination-block-level file links CT, ADA, and other 2021 Census
    geographies to their parent areas through DGUID columns.
    """
    from synthpopcan.statcan import fetch_dgrf_2021

    click.echo(
        "Downloading 2021 Dissemination Geographies Relationship File…",
        err=True,
    )
    try:
        csv_path = fetch_dgrf_2021(out_dir, url=url)
    except OSError as exc:
        raise click.ClickException(f"Download failed: {exc}") from exc
    print_wrote(csv_path)
    click.echo(csv_path)


@small_area.group("national-da")
def national_da_group() -> None:
    """Plan and execute restartable 2021 DA synthesis across Canada."""


@small_area.group("national-ada")
def national_ada_group() -> None:
    """Plan and execute restartable 2021 ADA synthesis across Canada."""


@national_da_group.command("fetch-profiles")
@click.option(
    "--out-dir",
    required=True,
    type=_PATH,
    help="Directory for the six official regional DA profile files.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Download a regional profile again even when its CSV already exists.",
)
def national_da_fetch_profiles_command(out_dir: Path, force: bool) -> None:
    """Download the six regional Census Profiles covering all of Canada."""

    _national_fetch_profiles(out_dir, force, "da")


@national_ada_group.command("fetch-profiles")
@click.option(
    "--out-dir",
    required=True,
    type=_PATH,
    help="Directory for the official national ADA profile file.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Download the ADA profile again even when its CSV already exists.",
)
def national_ada_fetch_profiles_command(out_dir: Path, force: bool) -> None:
    """Download the national Census Profile covering all Canadian ADAs."""

    _national_fetch_profiles(out_dir, force, "ada")


def _national_fetch_profiles(
    out_dir: Path,
    force: bool,
    geography_level: str,
) -> None:
    from synthpopcan.national_small_area import (
        national_2021_profile_paths,
        required_2021_profile_keys,
    )
    from synthpopcan.statcan import fetch_census_profile

    existing_paths = national_2021_profile_paths(out_dir, geography_level)
    for profile_key in required_2021_profile_keys(geography_level):
        destination = existing_paths[profile_key]
        if destination.is_file() and not force:
            click.echo(f"Using existing {destination}", err=True)
            continue
        click.echo(f"Downloading {profile_key}…", err=True)
        try:
            destination = fetch_census_profile(
                profile_key,
                destination.parent,
                census_year=2021,
            )
        except OSError as exc:
            raise click.ClickException(
                f"Could not download {profile_key}: {exc}"
            ) from exc
        print_wrote(destination)
    click.echo(out_dir)


@national_da_group.command("prepare")
@click.option(
    "--profiles-dir",
    required=True,
    type=_PATH,
    help="Directory containing all six regional 2021 DA profile CSVs.",
)
@click.option(
    "--boundaries",
    "boundary_path",
    required=True,
    type=_PATH,
    help="National 2021 DA GeoJSON boundary file.",
)
@click.option(
    "--relationships",
    "relationship_path",
    required=True,
    type=_PATH,
    help="Final 2021 Dissemination Geographies Relationship CSV.",
)
@click.option(
    "--out",
    "output_directory",
    required=True,
    type=_PATH,
    help="Destination for the national plan and restartable batch inputs.",
)
@click.option(
    "--max-households-per-batch",
    default=100_000,
    type=click.IntRange(min=1),
    show_default=True,
    help="Maximum target households in one synthesis batch.",
)
def national_da_prepare_command(
    profiles_dir: Path,
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    max_households_per_batch: int,
) -> None:
    """Prepare controls and jurisdiction boundaries for every Canadian DA."""

    _national_prepare_command(
        profiles_dir,
        boundary_path,
        relationship_path,
        output_directory,
        max_households_per_batch,
        "da",
    )


@national_ada_group.command("prepare")
@click.option(
    "--profiles-dir",
    required=True,
    type=_PATH,
    help="Directory containing the national 2021 ADA profile CSV.",
)
@click.option(
    "--boundaries",
    "boundary_path",
    required=True,
    type=_PATH,
    help="National 2021 ADA GeoJSON boundary file.",
)
@click.option(
    "--relationships",
    "relationship_path",
    required=True,
    type=_PATH,
    help="Final 2021 Dissemination Geographies Relationship CSV.",
)
@click.option(
    "--out",
    "output_directory",
    required=True,
    type=_PATH,
    help="Destination for the national plan and restartable batch inputs.",
)
@click.option(
    "--max-households-per-batch",
    default=100_000,
    type=click.IntRange(min=1),
    show_default=True,
    help="Maximum target households in one synthesis batch.",
)
def national_ada_prepare_command(
    profiles_dir: Path,
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    max_households_per_batch: int,
) -> None:
    """Prepare controls and jurisdiction boundaries for every Canadian ADA."""

    _national_prepare_command(
        profiles_dir,
        boundary_path,
        relationship_path,
        output_directory,
        max_households_per_batch,
        "ada",
    )


def _national_prepare_command(
    profiles_dir: Path,
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    max_households_per_batch: int,
    geography_level: str,
) -> None:
    from synthpopcan.national_small_area import (
        national_2021_profile_paths,
        prepare_canada_small_area_plan,
    )

    profile_paths = national_2021_profile_paths(profiles_dir, geography_level)
    missing = [str(path) for path in profile_paths.values() if not path.is_file()]
    if missing:
        raise click.UsageError(
            "Missing required profile files:\n  " + "\n  ".join(missing)
        )
    try:
        manifest = prepare_canada_small_area_plan(
            profile_paths,
            boundary_path,
            relationship_path,
            output_directory,
            geography_level=geography_level,
            max_households_per_batch=max_households_per_batch,
            progress=lambda message: click.echo(message, err=True),
        )
    except OSError as exc:
        raise click_file_access_error(output_directory, "read or write", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    coverage = manifest["coverage"]
    assert isinstance(coverage, dict)
    batches = manifest["batches"]
    assert isinstance(batches, list)
    click.echo(
        f"Planned {len(batches):,} restartable batches across "
        f"{coverage['jurisdictions']} provinces and territories; "
        f"{coverage['usable_geographies']:,} of "
        f"{coverage['expected_geographies']:,} "
        f"{geography_level.upper()}s have usable controls."
    )
    print_wrote(output_directory / "plan.json")
    click.echo(output_directory / "plan.json")


@national_da_group.command("run")
@click.argument("package_path", metavar="MODEL")
@click.option(
    "--plan",
    "plan_path",
    required=True,
    type=_PATH,
    help="National DA plan.json produced by national-da prepare.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=None,
    help="Run at most this many unfinished batches, useful for validation.",
)
@click.option(
    "--jurisdiction",
    "jurisdiction_values",
    multiple=True,
    type=click.Choice(
        _NATIONAL_SMALL_AREA_JURISDICTION_CHOICES,
        case_sensitive=False,
    ),
    help="Run only one province/territory PRUID or abbreviation; repeatable.",
)
@click.option(
    "--random-seed",
    type=int,
    default=42,
    show_default=True,
    help="Base seed; each batch receives a deterministic distinct seed.",
)
@click.option(
    "--condition-by-jurisdiction/--no-condition-by-jurisdiction",
    default=True,
    show_default=True,
    help=(
        "Condition a national model on the batch's PUMF province or combined "
        "northern category before generation."
    ),
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Record a failed batch and continue with the remaining plan.",
)
@click.option(
    "--candidate-pool-size",
    type=click.IntRange(min=1),
    default=10_000,
    show_default=True,
    help="Reusable candidate households per PUMF condition.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1, max=8),
    default=1,
    show_default=True,
    help="Independent batch processes to run concurrently.",
)
@click.option(
    "--fit-workers",
    type=click.IntRange(min=1, max=8),
    default=4,
    show_default=True,
    help="Geography-fitting threads used inside each batch process.",
)
@click.option(
    "--force-candidate-pools",
    is_flag=True,
    help="Regenerate conditioned candidate pools even when their evidence matches.",
)
@click.option(
    "--maps/--no-maps",
    default=False,
    show_default=True,
    help="Create a detailed self-contained map for each completed batch.",
)
@click.option(
    "--national-map/--no-national-map",
    default=True,
    show_default=True,
    help="Create a national polygon choropleth after the plan completes.",
)
@click.option(
    "--allow-low-disk",
    is_flag=True,
    help="Run even when free space is below the plan's conservative estimate.",
)
def national_da_run_command(
    package_path: str,
    plan_path: Path,
    limit: int | None,
    jurisdiction_values: tuple[str, ...],
    random_seed: int,
    condition_by_jurisdiction: bool,
    continue_on_error: bool,
    candidate_pool_size: int,
    workers: int,
    fit_workers: int,
    force_candidate_pools: bool,
    maps: bool,
    national_map: bool,
    allow_low_disk: bool,
) -> None:
    """Execute or resume every unfinished batch in a national DA plan."""

    _run_national_small_area_command(
        package_path=package_path,
        plan_path=plan_path,
        limit=limit,
        jurisdiction_values=jurisdiction_values,
        random_seed=random_seed,
        condition_by_jurisdiction=condition_by_jurisdiction,
        continue_on_error=continue_on_error,
        candidate_pool_size=candidate_pool_size,
        workers=workers,
        fit_workers=fit_workers,
        force_candidate_pools=force_candidate_pools,
        maps=maps,
        national_map=national_map,
        allow_low_disk=allow_low_disk,
        expected_geography_level="da",
    )


@national_ada_group.command("run")
@click.argument("package_path", metavar="MODEL")
@click.option(
    "--plan",
    "plan_path",
    required=True,
    type=_PATH,
    help="National ADA plan.json produced by national-ada prepare.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=None,
    help="Run at most this many unfinished batches, useful for validation.",
)
@click.option(
    "--jurisdiction",
    "jurisdiction_values",
    multiple=True,
    type=click.Choice(
        _NATIONAL_SMALL_AREA_JURISDICTION_CHOICES,
        case_sensitive=False,
    ),
    help="Run only one province/territory PRUID or abbreviation; repeatable.",
)
@click.option(
    "--random-seed",
    type=int,
    default=42,
    show_default=True,
    help="Base seed; each batch receives a deterministic distinct seed.",
)
@click.option(
    "--condition-by-jurisdiction/--no-condition-by-jurisdiction",
    default=True,
    show_default=True,
    help=(
        "Condition a national model on the batch's PUMF province or combined "
        "northern category before generation."
    ),
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Record a failed batch and continue with the remaining plan.",
)
@click.option(
    "--candidate-pool-size",
    type=click.IntRange(min=1),
    default=10_000,
    show_default=True,
    help="Reusable candidate households per PUMF condition.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1, max=8),
    default=1,
    show_default=True,
    help="Independent batch processes to run concurrently.",
)
@click.option(
    "--fit-workers",
    type=click.IntRange(min=1, max=8),
    default=4,
    show_default=True,
    help="Geography-fitting threads used inside each batch process.",
)
@click.option(
    "--force-candidate-pools",
    is_flag=True,
    help="Regenerate conditioned candidate pools even when their evidence matches.",
)
@click.option(
    "--maps/--no-maps",
    default=False,
    show_default=True,
    help="Create a detailed self-contained map for each completed batch.",
)
@click.option(
    "--national-map/--no-national-map",
    default=True,
    show_default=True,
    help="Create a national polygon choropleth after the plan completes.",
)
@click.option(
    "--allow-low-disk",
    is_flag=True,
    help="Run even when free space is below the plan's conservative estimate.",
)
def national_ada_run_command(
    package_path: str,
    plan_path: Path,
    limit: int | None,
    jurisdiction_values: tuple[str, ...],
    random_seed: int,
    condition_by_jurisdiction: bool,
    continue_on_error: bool,
    candidate_pool_size: int,
    workers: int,
    fit_workers: int,
    force_candidate_pools: bool,
    maps: bool,
    national_map: bool,
    allow_low_disk: bool,
) -> None:
    """Execute or resume every unfinished batch in a national ADA plan."""

    _run_national_small_area_command(
        package_path=package_path,
        plan_path=plan_path,
        limit=limit,
        jurisdiction_values=jurisdiction_values,
        random_seed=random_seed,
        condition_by_jurisdiction=condition_by_jurisdiction,
        continue_on_error=continue_on_error,
        candidate_pool_size=candidate_pool_size,
        workers=workers,
        fit_workers=fit_workers,
        force_candidate_pools=force_candidate_pools,
        maps=maps,
        national_map=national_map,
        allow_low_disk=allow_low_disk,
        expected_geography_level="ada",
    )


def _run_national_small_area_command(
    *,
    package_path: str,
    plan_path: Path,
    limit: int | None,
    jurisdiction_values: tuple[str, ...],
    random_seed: int,
    condition_by_jurisdiction: bool,
    continue_on_error: bool,
    candidate_pool_size: int,
    workers: int,
    fit_workers: int,
    force_candidate_pools: bool,
    maps: bool,
    national_map: bool,
    allow_low_disk: bool,
    expected_geography_level: str,
) -> None:
    """Execute one shared DA/ADA national plan."""

    import hashlib
    import shutil
    import time
    from functools import partial

    from synthpopcan.cli_tree import (
        _read_package_path_or_id,
        package_models,
        validate_package_allows_generation,
    )
    from synthpopcan.national_execution import (
        NationalBatchRunConfiguration,
        build_national_geography_summary,
        find_cached_national_candidate_pools,
        prepare_national_candidate_pools,
        run_national_cached_batch,
    )
    from synthpopcan.national_small_area import execute_canada_small_area_plan
    from synthpopcan.statcan import file_integrity

    selector_lookup = {
        selector.casefold(): item.pruid
        for item in CANADA_SMALL_AREA_JURISDICTIONS
        for selector in (item.pruid, item.abbreviation)
    }
    jurisdiction_pruids = (
        {selector_lookup[value.casefold()] for value in jurisdiction_values}
        if jurisdiction_values
        else None
    )

    try:
        plan_payload = json.loads(plan_path.read_text())
    except OSError as exc:
        raise click_file_access_error(plan_path, "read", exc) from exc
    storage = (
        plan_payload.get("storage_estimate") if isinstance(plan_payload, dict) else None
    )
    geography = (
        plan_payload.get("geography") if isinstance(plan_payload, dict) else None
    )
    if not isinstance(geography, Mapping):
        raise click.UsageError("The national plan has no geography identity.")
    geography_level = geography.get("geography_level")
    identifier_column = geography.get("identifier_column")
    identifier_namespace = geography.get("identifier_namespace")
    if geography_level != expected_geography_level:
        raise click.UsageError(
            f"This command requires a {expected_geography_level.upper()} plan, "
            f"not {geography_level!r}."
        )
    if not isinstance(identifier_column, str) or not isinstance(
        identifier_namespace, str
    ):
        raise click.UsageError("The national plan geography identity is incomplete.")
    if isinstance(storage, dict):
        required = storage.get("recommended_free_space_bytes")
        if isinstance(required, int):
            free = shutil.disk_usage(plan_path.parent).free
            if free < required and not allow_low_disk:
                raise click.UsageError(
                    "The national plan conservatively recommends "
                    f"{required / 1024**3:.1f} GiB free, but only "
                    f"{free / 1024**3:.1f} GiB is available. Free space, reduce "
                    "the plan, or pass --allow-low-disk after reviewing the risk."
                )

    pumf_pr_values = (
        {
            item.pumf_pr
            for item in CANADA_SMALL_AREA_JURISDICTIONS
            if item.pruid in jurisdiction_pruids
        }
        if jurisdiction_pruids is not None
        else None
    )
    local_package_path = Path(package_path)
    model_evidence: dict[str, object] | None = None
    if local_package_path.is_file():
        model_evidence = {
            "label": package_path,
            "path": str(local_package_path),
            **file_integrity(local_package_path),
        }
    pool_reports = (
        find_cached_national_candidate_pools(
            plan_path,
            model_evidence=model_evidence,
            requested_pool_size=candidate_pool_size,
            base_seed=random_seed,
            condition_by_jurisdiction=condition_by_jurisdiction,
            pumf_pr_values=pumf_pr_values,
        )
        if model_evidence is not None and not force_candidate_pools
        else None
    )
    if pool_reports is not None:
        click.echo(
            "Verified reusable candidate pools without loading the model", err=True
        )
    else:
        package_started = time.perf_counter()
        try:
            package, package_label, package_source_path = _read_package_path_or_id(
                package_path
            )
            validate_package_allows_generation(package)
            household_model, person_model = package_models(package)
        except OSError as exc:
            raise click_file_access_error(Path(package_path), "read", exc) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc
        if package_source_path is not None:
            model_evidence = {
                "label": package_label,
                "path": str(package_source_path),
                **file_integrity(package_source_path),
            }
        else:
            canonical = json.dumps(
                package,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            model_evidence = {
                "label": package_label,
                "schema_version": package.get("schema_version"),
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "byte_size": len(canonical),
            }
        package_seconds = time.perf_counter() - package_started
        click.echo(f"Loaded model package once in {package_seconds:.1f}s", err=True)

        try:
            pool_reports = prepare_national_candidate_pools(
                plan_path,
                household_model=household_model,
                person_model=person_model,
                household_size_column=str(
                    package.get("household_size_column", "household_size")
                ),
                model_evidence=model_evidence,
                requested_pool_size=candidate_pool_size,
                base_seed=random_seed,
                condition_by_jurisdiction=condition_by_jurisdiction,
                pumf_pr_values=pumf_pr_values,
                force=force_candidate_pools,
                progress=lambda message: click.echo(message, err=True),
            )
        except OSError as exc:
            raise click_file_access_error(
                plan_path.parent,
                "read or write",
                exc,
            ) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc

    if condition_by_jurisdiction:
        pool_manifests = {
            pumf_pr: str(
                (
                    plan_path.parent
                    / "candidate-pools"
                    / f"pr-{pumf_pr}"
                    / "manifest.json"
                ).relative_to(plan_path.parent)
            )
            for pumf_pr in pool_reports
        }
    else:
        all_manifest = str(
            (
                plan_path.parent / "candidate-pools" / "all" / "manifest.json"
            ).relative_to(plan_path.parent)
        )
        pool_manifests = {
            item.pumf_pr: all_manifest for item in CANADA_SMALL_AREA_JURISDICTIONS
        }
    configuration = NationalBatchRunConfiguration(
        pool_manifests=pool_manifests,
        geography_level=expected_geography_level,
        identifier_column=identifier_column,
        identifier_namespace=identifier_namespace,
        fit_workers=fit_workers,
    )
    run_batch = partial(
        run_national_cached_batch,
        configuration=configuration,
    )

    try:
        plan = execute_canada_small_area_plan(
            plan_path,
            run_batch,
            limit=limit,
            continue_on_error=continue_on_error,
            jurisdiction_pruids=jurisdiction_pruids,
            workers=workers,
        )
    except OSError as exc:
        raise click_file_access_error(plan_path, "read or write", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    if maps:
        _render_deferred_national_maps(
            plan_path,
            plan,
            jurisdiction_pruids=jurisdiction_pruids,
            geography_level=expected_geography_level,
            identifier_column=identifier_column,
        )
    national_summary = build_national_geography_summary(plan_path)
    if national_map and _national_plan_is_complete(plan):
        national_summary = _render_national_summary_map(
            plan_path,
            plan,
            national_summary,
            geography_level=expected_geography_level,
            identifier_column=identifier_column,
        )
    last_execution = plan.get("last_execution")
    click.echo(json.dumps(last_execution, indent=2, sort_keys=True))
    summary_geographies = _required_summary_int(national_summary, "geographies")
    summary_households = _required_summary_int(
        national_summary,
        "assigned_households",
    )
    summary_persons = _required_summary_int(national_summary, "assigned_persons")
    click.echo(
        f"National summary: {summary_geographies:,} geographies, "
        f"{summary_households:,} households, "
        f"{summary_persons:,} persons.",
        err=True,
    )


def _required_batch_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_summary_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _national_plan_is_complete(plan: Mapping[str, object]) -> bool:
    return plan.get("status") == "completed"


def _render_national_summary_map(
    plan_path: Path,
    plan: Mapping[str, object],
    national_summary: dict[str, object],
    *,
    geography_level: str,
    identifier_column: str,
) -> dict[str, object]:
    """Render and record completed-plan polygon and point overviews."""

    from synthpopcan.map_render import (
        render_geography_summary_point_map,
        render_national_plan_map,
    )
    from synthpopcan.statcan import file_integrity

    inputs = plan.get("inputs")
    boundaries = inputs.get("boundaries") if isinstance(inputs, Mapping) else None
    boundary_value = boundaries.get("path") if isinstance(boundaries, Mapping) else None
    if not isinstance(boundary_value, str):
        raise ValueError("national plan boundary input path is invalid")
    output = plan_path.parent
    boundary_path = Path(boundary_value)
    if not boundary_path.is_absolute() and not boundary_path.is_file():
        boundary_path = output / boundary_path
    map_path = output / "national-map.html"
    display_boundaries_path = output / "national-map.geojson"
    point_map_path = output / "national-points-map.html"
    points_path = output / "national-points.geojson"
    point_report = render_geography_summary_point_map(
        summary_path=output / "national-geography-summary.csv",
        boundaries_path=boundary_path,
        geography_column=identifier_column,
        out_path=point_map_path,
        points_path=points_path,
        geography_context=statcan_geography_universe(
            2021,
            geography_level,
            identifier_column,
            dguid_column="DGUID",
        ).as_dict(),
    )
    report = render_national_plan_map(
        plan_path=plan_path,
        geography_level=geography_level,
        geography_column=identifier_column,
        out_path=map_path,
    )
    report["point_overview"] = point_report
    artifacts = national_summary.setdefault("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("national summary artifacts must be an object")
    artifacts["map"] = {
        "path": map_path.name,
        **file_integrity(map_path),
    }
    artifacts["map_boundaries"] = {
        "path": display_boundaries_path.name,
        **file_integrity(display_boundaries_path),
    }
    statistics = report.get("statistics")
    statistics_artifact = (
        statistics.get("artifact") if isinstance(statistics, Mapping) else None
    )
    if not isinstance(statistics_artifact, Mapping):
        raise ValueError("national map statistics artifact is invalid")
    artifacts["map_statistics"] = dict(statistics_artifact)
    statistics_manifest_path = output / "national-map-statistics.json"
    artifacts["map_statistics_manifest"] = {
        "path": statistics_manifest_path.name,
        **file_integrity(statistics_manifest_path),
    }
    artifacts["point_map"] = {
        "path": point_map_path.name,
        **file_integrity(point_map_path),
    }
    artifacts["map_points"] = {
        "path": points_path.name,
        **file_integrity(points_path),
    }
    national_summary["map"] = report
    summary_path = output / "national-summary.json"
    temporary = summary_path.with_name(f".{summary_path.name}.tmp")
    temporary.write_text(json.dumps(national_summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(summary_path)
    return national_summary


def _render_deferred_national_maps(
    plan_path: Path,
    plan: Mapping[str, object],
    *,
    jurisdiction_pruids: set[str] | None,
    geography_level: str,
    identifier_column: str,
) -> None:
    """Render missing batch maps only after population checkpoints exist."""

    import os
    import time

    from synthpopcan.map_render import render_synthesis_map
    from synthpopcan.statcan import file_integrity

    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    for record in records:
        if not isinstance(record, Mapping):
            continue
        if (
            jurisdiction_pruids is not None
            and record.get("jurisdiction_pruid") not in jurisdiction_pruids
        ):
            continue
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            continue
        batch_path = plan_path.parent / manifest_value
        batch = json.loads(batch_path.read_text())
        if not isinstance(batch, dict) or batch.get("status") != "completed":
            continue
        result = batch.get("result")
        if not isinstance(result, dict):
            continue
        artifacts = result.setdefault("artifacts", {})
        if not isinstance(artifacts, dict):
            continue
        existing = artifacts.get("map")
        if isinstance(existing, Mapping):
            existing_path = existing.get("path")
            if (
                isinstance(existing_path, str)
                and (plan_path.parent / existing_path).is_file()
            ):
                continue

        output = plan_path.parent / _required_batch_text(
            batch,
            "output_directory",
        )
        households, persons = _linked_population_paths(output)
        boundaries = plan_path.parent / _required_batch_text(batch, "boundaries")
        map_path = output / "map.html"
        batch_id = _required_batch_text(batch, "batch_id")
        click.echo(f"Rendering deferred map for {batch_id}", err=True)
        started = time.perf_counter()
        render_synthesis_map(
            households_path=households,
            persons_path=persons,
            boundaries_path=boundaries,
            geography_column=identifier_column,
            geography_id_field="geo_id",
            out_path=map_path,
            title=f"Synthetic population — batch {batch_id}",
            geography_context=statcan_geography_universe(
                2021,
                geography_level,
                identifier_column,
                dguid_column="DGUID",
            ).as_dict(),
        )
        artifacts["map"] = {
            "path": str(map_path.relative_to(plan_path.parent)),
            **file_integrity(map_path),
        }
        timing = result.setdefault("timing_seconds", {})
        if isinstance(timing, dict):
            timing["deferred_map"] = time.perf_counter() - started
        temporary = batch_path.with_name(f".{batch_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(batch, indent=2, sort_keys=True) + "\n")
        temporary.replace(batch_path)


@small_area.command("synthesize")
@click.argument("package_path", metavar="MODEL")
@click.option(
    "--households",
    "household_count",
    required=True,
    type=int,
    help="Number of candidate households to generate before calibration.",
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Normalized controls CSV with a geography dimension column.",
)
@click.option(
    "--person-controls",
    "person_controls_path",
    type=_PATH,
    help="Optional linked-person controls CSV for joint calibration.",
)
@click.option(
    "--control-pack",
    default=None,
    help="Built-in control-pack identifier or strict local manifest JSON.",
)
@click.option(
    "--control-pack-evidence",
    type=_PATH,
    default=None,
    help="Evidence JSON bound to the selected pack and exact control tables.",
)
@click.option(
    "--geo-dimension",
    required=True,
    help="Dimension name in controls (e.g. ct, ada).",
)
@click.option(
    "--geo-column",
    default=None,
    help="Output geography column. Defaults to --geo-dimension.",
)
@click.option(
    "--census-vintage",
    type=int,
    default=None,
    help="Census year defining the target geography identifiers.",
)
@click.option(
    "--geo-level",
    default=None,
    help="Explicit geography level such as da, ada, ct, or csd.",
)
@click.option(
    "--geo-namespace",
    default=None,
    help="Stable identifier namespace, such as statcan:census:2021:da.",
)
@click.option(
    "--geo-dguid-column",
    default=None,
    help="Optional DGUID column carried by the same geography resource.",
)
@click.option(
    "--out",
    "output_dir",
    required=True,
    type=_PATH,
    help="Output directory for linked rows and the calibration report.",
)
@click.option(
    "--include-weights",
    is_flag=True,
    help="Also write the potentially large fitted weights CSV.",
)
@click.option(
    "--random-seed",
    type=int,
    default=None,
    help="Random seed for generation.",
)
@click.option(
    "--condition",
    "condition_values",
    multiple=True,
    metavar="COLUMN=VALUE",
    help="Condition candidate household generation; repeat for multiple columns.",
)
@click.option(
    "--pool-size",
    type=int,
    default=None,
    help="Maximum candidate households to use for calibration.",
)
@click.option(
    "--subsample-seed",
    type=int,
    default=42,
    show_default=True,
    help=(
        "Seed for the --pool-size candidate subsample. Keep this fixed when "
        "varying --random-seed, or vary it independently to test sensitivity."
    ),
)
@click.option(
    "--max-household-size",
    type=int,
    default=None,
    help=(
        "Group household_size at this maximum category before calibration. "
        "Use 5 when controls are built from the Census Profile, which groups "
        "'5 or more persons' into a single category."
    ),
)
@click.option(
    "--household-size-group-column",
    default="household_size_group",
    show_default=True,
    help=(
        "Temporary candidate column used for grouped household-size controls. "
        "Use household_size only for old controls that expect destructive capping."
    ),
)
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
def synthesize_command(
    package_path: str,
    household_count: int,
    controls_path: Path,
    person_controls_path: Path | None,
    control_pack: str | None,
    control_pack_evidence: Path | None,
    geo_dimension: str,
    geo_column: str | None,
    census_vintage: int | None,
    geo_level: str | None,
    geo_namespace: str | None,
    geo_dguid_column: str | None,
    output_dir: Path,
    include_weights: bool,
    random_seed: int | None,
    condition_values: tuple[str, ...],
    pool_size: int | None,
    subsample_seed: int,
    max_household_size: int | None,
    household_size_group_column: str,
    max_iterations: int,
    tolerance: float,
    output_format: str,
) -> None:
    """Generate linked candidates from a package and calibrate to small-area controls.

    MODEL is a local linked model package JSON or a premade model ID from
    ``synthpopcan models list``.

    See the small-area documentation for worked examples.
    """
    import tempfile

    from synthpopcan.cli_tree import (
        _read_package_path_or_id,
        package_models,
        parse_conditions,
        validate_package_allows_generation,
    )
    from synthpopcan.tree import generate_linked_population_to_csv

    output_dir.mkdir(parents=True, exist_ok=True)
    households_out, persons_out = _linked_population_paths(output_dir)
    report_out = output_dir / "report.json"
    weights_out = output_dir / "weights.csv" if include_weights else None
    output_geo_column = geo_column or geo_dimension
    geography_universe = _optional_geography_universe(
        census_vintage=census_vintage,
        geography_level=geo_level,
        identifier_namespace=geo_namespace,
        identifier_column=output_geo_column,
        dguid_column=geo_dguid_column,
    )

    try:
        package, _, _ = _read_package_path_or_id(package_path)
    except OSError as exc:
        raise click_file_access_error(Path(package_path), "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    input_licensing = validate_prepared_model_licensing(package.get("licensing"))

    try:
        validate_package_allows_generation(package)
        conditions = parse_conditions(condition_values)
    except ValueError as exc:
        raise click_value_error(exc) from exc

    household_model, person_model = package_models(package)
    household_size_column = str(package.get("household_size_column", "household_size"))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        candidates_households = tmp / "candidates-households.csv"
        candidates_persons = tmp / "candidates-persons.csv"

        try:
            generate_linked_population_to_csv(
                household_model,
                person_model,
                households=household_count,
                households_path=candidates_households,
                persons_path=candidates_persons,
                household_size_column=household_size_column,
                household_conditions=conditions,
                random_seed=random_seed,
            )
        except OSError as exc:
            raise click_file_access_error(candidates_households, "write", exc) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc

        if max_household_size is not None:
            from synthpopcan.small_area_controls import write_recoded_candidates

            recoded_households = tmp / "candidates-households-recoded.csv"
            write_recoded_candidates(
                candidates_households,
                recoded_households,
                hhsize_col=household_size_column,
                group_col=household_size_group_column,
                cap=max_household_size,
            )
            candidates_households = recoded_households

        try:
            summary = calibrate_linked_household_csvs(
                households_path=candidates_households,
                persons_path=candidates_persons,
                controls_path=controls_path,
                person_controls_path=person_controls_path,
                control_pack=control_pack,
                control_pack_evidence=control_pack_evidence,
                geography_dimension=geo_dimension,
                geography_column=output_geo_column,
                geography_universe=geography_universe,
                households_out=households_out,
                persons_out=persons_out,
                weights_out=weights_out,
                report_out=report_out,
                pool_size=pool_size,
                subsample_seed=subsample_seed,
                max_iterations=max_iterations,
                tolerance=tolerance,
            )
        except OSError as exc:
            raise click_file_access_error(
                exc.filename or controls_path,
                "read or write",
                exc,
            ) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc

    manifest_out = output_dir / "manifest.json"
    write_linked_population_contract(
        manifest_out,
        households_out,
        persons_out,
        geography_column=output_geo_column,
        licensing=input_licensing,
    )

    print_wrote(households_out)
    print_wrote(persons_out)
    print_wrote(manifest_out)
    if weights_out is not None:
        print_wrote(weights_out)
    print_wrote(report_out)
    if output_format == "json":
        click.echo(json.dumps(summary, sort_keys=True))
        return
    hh_n = summary["assigned_households"]
    p_n = summary["assigned_persons"]
    geo_n = len(summary["geographies"])
    click.echo(
        f"Generated and assigned {hh_n:,} households and {p_n:,} persons "
        f"across {geo_n:,} {output_geo_column} geographies."
    )
    _print_calibrate_linked_diagnostics(summary)
