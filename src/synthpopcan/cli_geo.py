"""Small-area linked synthesis commands."""

from __future__ import annotations

__all__ = ["small_area"]

import json
from pathlib import Path

import click

from synthpopcan.cli_output import format_file_access_error
from synthpopcan.console import print_wrote
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs

_BOUNDARIES_HELP = (
    "StatCan boundary shapefile (.shp), pre-converted GeoJSON (.geojson), "
    "or the directory containing the shapefile. "
    "For CTs: lct_000b16a_e.shp; for ADAs: lada000b16a_e.shp. "
    "Shapefiles are reprojected automatically. "
    "Use 'geo prepare-boundaries' to produce a local GeoJSON once."
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
    import click as _click

    _click.echo(
        f"Warning: unknown geography '{geo_column}', guessing shapefile field "
        f"'{guessed}'. Pass --geo-id-field to override.",
        err=True,
    )
    return guessed


_PATH = click.Path(path_type=Path)


@click.group("geo")
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
    "--geo-dimension",
    required=True,
    help="Control dimension naming the target geography, such as ct or ada.",
)
@click.option(
    "--geo-column",
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
    geo_dimension: str,
    geo_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None,
    report_out: Path | None,
    household_id_column: str,
    person_id_column: str,
    weight_field: str | None,
    max_iterations: int,
    tolerance: float,
    pool_size: int | None,
    output_format: str,
) -> None:
    """Calibrate linked household/person candidates to geography controls."""

    try:
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            geography_dimension=geo_dimension,
            geography_column=geo_column,
            households_out=households_out,
            persons_out=persons_out,
            weights_out=weights_out,
            report_out=report_out,
            household_id_column=household_id_column,
            person_id_column=person_id_column,
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
            pool_size=pool_size,
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
        f"{len(summary['geographies']):,} {geo_column} value(s)."
    )


# ---------------------------------------------------------------------------
# map command
# ---------------------------------------------------------------------------


@small_area.command("map")
@click.option(
    "--households",
    "households_path",
    required=True,
    type=_PATH,
    help="Synthesis household CSV (output of calibrate-linked).",
)
@click.option(
    "--persons",
    "persons_path",
    default=None,
    type=_PATH,
    help=(
        "Synthesis person CSV (output of calibrate-linked). "
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
    households_path: Path,
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
            --households synthetic-households.csv \\
            --boundaries /path/to/statcan-boundaries/ \\
            --geo-column ct
    """
    from synthpopcan.map_render import render_synthesis_map

    # Resolve optional args
    boundaries_path = _resolve_boundaries(boundaries_path, geo_column)
    if geo_id_field is None:
        geo_id_field = _resolve_id_field(geo_column, boundaries_path)
    if out_path is None:
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
        raise click.ClickException(
            format_file_access_error(Path(filename), "process", exc)
        ) from exc
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    print_wrote(out_path)
    click.echo(f"Open {out_path} in a browser to explore the synthesis results.")


# ---------------------------------------------------------------------------
# build-controls command
# ---------------------------------------------------------------------------


@small_area.command("build-controls")
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
        "Synthesis household CSV to recode for use as calibrate-linked candidates. "
        "household_size values above 5 are capped at 5 to match Census categories. "
        "Omit when using synthesize-from-package, which handles recoding itself."
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
        "Destination path for the recoded candidates CSV. "
        "Defaults to <candidates-stem>-recoded.csv beside the candidates file."
    ),
)
@click.option(
    "--hhsize-cap",
    default=5,
    type=int,
    show_default=True,
    help="Cap household_size at this value when writing the recoded candidates CSV.",
)
def build_controls_command(
    profile_path: Path,
    geo_column: str,
    target_total: int,
    candidates_path: Path | None,
    geo_prefix: str | None,
    geo_level_value: str | None,
    controls_out: Path | None,
    candidates_out: Path | None,
    hhsize_cap: int,
) -> None:
    """Build IPF control tables from a StatCan Census Profile for small-area synthesis.

    Reads household-size (members 52–56) and tenure (members 1618–1619) margins
    from a 2247-variable Census Profile, scales them to the target household count,
    and writes a long-format controls CSV ready for ``calibrate-linked`` or
    ``synthesize-from-package``.  When --candidates is supplied, also recodes
    that CSV by capping household_size at 5 to match the Census categories.

    Geographies missing either margin are automatically dropped (they would cause
    an IPF dimension mismatch in calibrate-linked).

    \b
    Example — Ontario ADAs, scaled to 5.5 M households (with candidate recoding):

        synthpopcan geo build-controls \\
            --profile 2016-census-profile-ada.csv \\
            --geo-column ada \\
            --geo-prefix 35 \\
            --target 5500000 \\
            --candidates synthetic-households-5.5m.csv

    \b
    Example — Quebec City CTs, controls only (for use with synthesize-from-package):

        synthpopcan geo build-controls \\
            --profile 98-401-X2016043_English_CSV_data.csv \\
            --geo-column ct \\
            --geo-prefix 421 \\
            --target 338000 \\
            --controls-out quebec-city-ct-controls.csv
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
            controls_out = (
                candidates_path.parent
                / f"{candidates_path.stem}-controls-{target_total}.csv"
            )
        else:
            controls_out = Path(f"{geo_column}-controls-{target_total}.csv")
    if candidates_out is None and candidates_path is not None:
        candidates_out = candidates_path.parent / f"{candidates_path.stem}-recoded.csv"

    click.echo(f"Reading profile: {profile_path}")
    try:
        raw = extract_controls_from_profile(
            profile_path,
            geo_column,
            geo_prefix=geo_prefix,
            geo_level_value=geo_level_value,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(profile_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

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
        write_controls_csv(scaled, controls_out, geo_column)
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(controls_out, "write", exc)
        ) from exc
    print_wrote(controls_out)

    if candidates_path is not None:
        click.echo(
            f"Recoding candidates (household_size capped at {hhsize_cap}): "
            f"{candidates_path}"
        )
        assert candidates_out is not None
        try:
            n_rows = write_recoded_candidates(
                candidates_path, candidates_out, cap=hhsize_cap
            )
        except OSError as exc:
            raise click.ClickException(
                format_file_access_error(candidates_path, "recode", exc)
            ) from exc
        click.echo(f"  {n_rows:,} rows written")
        print_wrote(candidates_out)
        click.echo("\nNext step:")
        click.echo(
            f"  synthpopcan geo calibrate-linked \\\n"
            f"    --households {candidates_out} \\\n"
            f"    --persons <persons-csv> \\\n"
            f"    --controls {controls_out} \\\n"
            f"    --geo-dimension {geo_column} \\\n"
            f"    --geo-column {geo_column} \\\n"
            f"    --pool-size 10000 \\\n"
            f"    --households-out <output-households.csv> \\\n"
            f"    --persons-out <output-persons.csv>"
        )
    else:
        click.echo("\nNext step:")
        click.echo(
            f"  synthpopcan geo synthesize-from-package <package.json> \\\n"
            f"    --households {target_total} \\\n"
            f"    --controls {controls_out} \\\n"
            f"    --geo-dimension {geo_column} \\\n"
            f"    --geo-column {geo_column} \\\n"
            f"    --max-household-size 5 \\\n"
            f"    --households-out <output-households.csv> \\\n"
            f"    --persons-out <output-persons.csv>"
        )


# ---------------------------------------------------------------------------
# prepare-boundaries command
# ---------------------------------------------------------------------------

_KNOWN_GEO_LEVELS = ("ct", "ada", "da", "csd", "cd", "pr")


@small_area.command("prepare-boundaries")
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
def prepare_boundaries_command(
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

        synthpopcan geo prepare-boundaries --geo-level ct --out-dir data/boundaries/

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

    click.echo(f"Downloading {entry.description} boundary file…")
    try:
        shp_path = fetch_boundary_zip(geo_level, out_dir, url=url)
    except OSError as exc:
        raise click.ClickException(f"Download failed: {exc}") from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"  Shapefile: {shp_path}")
    click.echo("Converting to WGS-84 GeoJSON…")

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
        raise click.ClickException(
            format_file_access_error(geojson_path, "write", exc)
        ) from exc

    from synthpopcan.console import print_wrote

    print_wrote(geojson_path)
    click.echo(f"\nPass this file to geo map with:\n  --boundaries {geojson_path}")


@small_area.command("synthesize-from-package")
@click.argument("package_path", type=_PATH, metavar="PACKAGE")
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
    "--geo-dimension",
    required=True,
    help="Dimension name in controls (e.g. ct, ada).",
)
@click.option(
    "--geo-column",
    required=True,
    help="Column name to write in output rows.",
)
@click.option("--households-out", required=True, type=_PATH)
@click.option("--persons-out", required=True, type=_PATH)
@click.option("--weights-out", type=_PATH, help="Optional weights CSV path.")
@click.option(
    "--report",
    "report_out",
    type=_PATH,
    help="Optional calibration report JSON path.",
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
    "--max-household-size",
    type=int,
    default=None,
    help=(
        "Cap household_size at this value before calibration. Use 5 when controls "
        "are built from the Census Profile, which groups '5 or more persons' into "
        "a single category."
    ),
)
def synthesize_from_package_command(
    package_path: Path,
    household_count: int,
    controls_path: Path,
    geo_dimension: str,
    geo_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None,
    report_out: Path | None,
    random_seed: int | None,
    pool_size: int | None,
    max_household_size: int | None,
) -> None:
    """Generate linked candidates from a package and calibrate to small-area controls.

    PACKAGE is a local linked model package JSON produced by
    ``geo tree package-linked-models``.

    \b
    Example:

        synthpopcan geo synthesize-from-package package.json \\
          --households 50000 \\
          --controls ada-controls.csv \\
          --geo-dimension ada \\
          --geo-column ada \\
          --households-out small-area-households.csv \\
          --persons-out small-area-persons.csv \\
          --report calibration-report.json
    """
    import tempfile

    from synthpopcan.cli_tree import (
        package_models,
        read_linked_model_package,
        validate_package_allows_generation,
    )
    from synthpopcan.tree import generate_linked_population_to_csv

    try:
        package = read_linked_model_package(package_path)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        validate_package_allows_generation(package)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

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
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

        if max_household_size is not None:
            _cap_column_inplace(
                candidates_households, household_size_column, max_household_size
            )

        try:
            summary = calibrate_linked_household_csvs(
                households_path=candidates_households,
                persons_path=candidates_persons,
                controls_path=controls_path,
                geography_dimension=geo_dimension,
                geography_column=geo_column,
                households_out=households_out,
                persons_out=persons_out,
                weights_out=weights_out,
                report_out=report_out,
                pool_size=pool_size,
            )
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

    print_wrote(households_out)
    print_wrote(persons_out)
    if weights_out:
        print_wrote(weights_out)
    if report_out:
        print_wrote(report_out)
    click.echo(json.dumps(summary, sort_keys=True))


def _cap_column_inplace(path: Path, column: str, cap: int) -> None:
    """Rewrite *path* with integer values in *column* capped at *cap*."""
    import csv as _csv

    tmp = path.with_suffix(".tmp")
    with path.open(newline="") as src, tmp.open("w", newline="") as dst:
        reader = _csv.DictReader(src)
        assert reader.fieldnames
        writer = _csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            try:
                if int(row[column]) > cap:
                    row[column] = str(cap)
            except (ValueError, KeyError):
                pass
            writer.writerow(row)
    tmp.replace(path)
