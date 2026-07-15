"""Small-area linked synthesis commands."""

from __future__ import annotations

__all__ = ["small_area"]

import json
from pathlib import Path

import click

from synthpopcan.cli_output import click_file_access_error, click_value_error
from synthpopcan.console import print_wrote
from synthpopcan.diagnostics import format_categories, format_number
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    estimate_small_area_run,
)

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


@click.group("geo")
# Keep the Python object named for the field term while exposing a shorter CLI group.
def small_area() -> None:
    """Assign and calibrate linked households to target geographies."""


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
@click.argument("population_dir", metavar="POPULATION", type=_PATH)
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
    population_dir: Path,
    controls_path: Path,
    person_controls_path: Path | None,
    geo_dimension: str,
    geo_column: str | None,
    output_dir: Path,
    include_weights: bool,
    max_iterations: int,
    tolerance: float,
    pool_size: int | None,
    subsample_seed: int,
    output_format: str,
) -> None:
    """Calibrate linked household/person candidates to geography controls."""

    households_path, persons_path = _linked_population_paths(population_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    households_out, persons_out = _linked_population_paths(output_dir)
    report_out = output_dir / "report.json"
    weights_out = output_dir / "weights.csv" if include_weights else None
    output_geo_column = geo_column or geo_dimension

    try:
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            person_controls_path=person_controls_path,
            geography_dimension=geo_dimension,
            geography_column=output_geo_column,
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

    print_wrote(households_out)
    print_wrote(persons_out)
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
    required=True,
    type=_PATH,
    help=_BOUNDARIES_HELP,
)
@click.option(
    "--geo-column",
    required=True,
    help="Column in the household CSV that holds the geography ID (e.g. ct or ada).",
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
@click.option(
    "--out",
    "out_path",
    default=None,
    type=_PATH,
    help=(
        "Destination HTML file. "
        "Defaults to <households-stem>-map.html in the same directory."
    ),
)
@click.option(
    "--title",
    default=None,
    help="Map title shown in the panel. Defaults to the output filename stem.",
)
@click.option(
    "--coord-precision",
    default=5,
    type=int,
    show_default=True,
    help="Decimal places kept in WGS-84 coordinates (5 ≈ 1 m; 3 halves file size).",
)
def map_command(
    population_path: Path,
    persons_path: Path | None,
    boundaries_path: Path,
    geo_column: str,
    geo_id_field: str | None,
    out_path: Path | None,
    title: str | None,
    coord_precision: int,
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
    """
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
    candidates_path: Path | None,
    geo_prefix: str | None,
    geo_level_value: str | None,
    controls_out: Path | None,
    candidates_out: Path | None,
    hhsize_cap: int,
    household_size_group_column: str,
) -> None:
    """Build IPF control tables from a StatCan Census Profile for small-area synthesis.

    Reads household-size (members 52–56) and tenure (members 1618–1619) margins
    from a 2247-variable Census Profile, scales them to the target household count,
    and writes a long-format controls CSV ready for ``calibrate`` or
    ``synthesize``. Household-size controls use
    household_size_group by default because Census Profile combines 5-or-more
    person households into one category.  When --candidates is supplied, also
    writes that grouped column while preserving exact household_size.

    Geographies missing either margin are automatically dropped (they would cause
    an IPF dimension mismatch in calibration).

    See the small-area documentation for worked examples.
    """
    from synthpopcan.small_area_controls import (
        extract_controls_from_profile,
        scale_and_validate_controls,
        write_controls_csv,
        write_recoded_candidates,
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
        raw = extract_controls_from_profile(
            profile_path,
            geo_column,
            geo_prefix=geo_prefix,
            geo_level_value=geo_level_value,
        )
    except OSError as exc:
        raise click_file_access_error(profile_path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

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
    if dropped:
        click.echo(
            f"  Dropped {len(dropped):,} {geo_column} unit(s) "
            "missing hhsize or tenure data"
        )
    hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
    tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
    click.echo(
        f"  Scaled {len(scaled):,} units to "
        f"{hhsize_total:,} households (hhsize), {tenure_total:,} (tenure)"
    )

    try:
        write_controls_csv(
            scaled,
            controls_out,
            geo_column,
            household_size_column=household_size_group_column,
        )
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
        click.echo(
            f"  synthpopcan geo calibrate {candidates_out} \\\n"
            f"    --controls {controls_out} \\\n"
            f"    --geo-dimension {geo_column} \\\n"
            f"    --pool-size 10000 \\\n"
            f"    --out calibrated-population/"
        )
    else:
        click.echo("\nNext step:")
        click.echo(
            f"  synthpopcan geo synthesize MODEL \\\n"
            f"    --households {target_total} \\\n"
            f"    --controls {controls_out} \\\n"
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
    "--out-dir",
    "out_dir",
    required=True,
    type=_PATH,
    help="Directory where the GeoJSON file (and temporary shapefile) will be saved.",
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
    out_dir: Path,
    coord_precision: int,
    url: str | None,
) -> None:
    """Download and convert a StatCan 2016 census boundary shapefile to GeoJSON.

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

        synthpopcan geo boundaries --geo-level ct --out-dir data/boundaries/

    The 2016 boundary ZIPs are sourced from Statistics Canada's geography
    program.  An internet connection is required.
    """
    from synthpopcan.map_render import prepare_boundaries_geojson
    from synthpopcan.statcan import (
        _BOUNDARY_2016_DOWNLOADS,
        BoundaryDownload,
        fetch_boundary_zip,
    )

    entry: BoundaryDownload = _BOUNDARY_2016_DOWNLOADS[geo_level.lower()]

    click.echo(f"Downloading {entry.description} boundary file…", err=True)
    try:
        shp_path = fetch_boundary_zip(geo_level, out_dir, url=url)
    except OSError as exc:
        raise click.ClickException(f"Download failed: {exc}") from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    click.echo(f"  Shapefile: {shp_path}", err=True)
    click.echo("Converting to WGS-84 GeoJSON…", err=True)

    geojson_path = out_dir / f"2016-boundary-{geo_level.lower()}.geojson"
    try:
        prepare_boundaries_geojson(
            shp_path,
            id_field=entry.id_field,
            out_path=geojson_path,
            coord_precision=coord_precision,
        )
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
    geo_dimension: str,
    geo_column: str | None,
    output_dir: Path,
    include_weights: bool,
    random_seed: int | None,
    pool_size: int | None,
    subsample_seed: int,
    max_household_size: int | None,
    household_size_group_column: str,
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
        validate_package_allows_generation,
    )
    from synthpopcan.tree import generate_linked_population_to_csv

    output_dir.mkdir(parents=True, exist_ok=True)
    households_out, persons_out = _linked_population_paths(output_dir)
    report_out = output_dir / "report.json"
    weights_out = output_dir / "weights.csv" if include_weights else None
    output_geo_column = geo_column or geo_dimension

    try:
        package, _, _ = _read_package_path_or_id(package_path)
    except OSError as exc:
        raise click_file_access_error(Path(package_path), "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    try:
        validate_package_allows_generation(package)
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
                geography_dimension=geo_dimension,
                geography_column=output_geo_column,
                households_out=households_out,
                persons_out=persons_out,
                weights_out=weights_out,
                report_out=report_out,
                pool_size=pool_size,
                subsample_seed=subsample_seed,
            )
        except OSError as exc:
            raise click_file_access_error(
                exc.filename or controls_path,
                "read or write",
                exc,
            ) from exc
        except ValueError as exc:
            raise click_value_error(exc) from exc

    print_wrote(households_out)
    print_wrote(persons_out)
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
