"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

from typing import Any, Literal, cast

__all__ = ["main", "resolve_data_root"]

import os
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

from synthpopcan import __version__
from synthpopcan.cli_enrichment import enrich
from synthpopcan.cli_exchange import bundle
from synthpopcan.cli_geo import small_area
from synthpopcan.cli_ipf import ipf
from synthpopcan.cli_microdata import microdata
from synthpopcan.cli_output import (
    click_file_access_error,
    click_value_error,
    format_report_number,
    parse_columns,
    print_census_profile_characteristics_table,
    print_tree_output_validation_report_table,
    print_validation_report_table,
    print_wds_inspection_table,
    print_wds_metadata_explanation_table,
    read_csv_rows,
    split_columns,
    write_json_object,
    write_output,
    write_report,
    write_wds_search_results,
)
from synthpopcan.cli_tree import (
    generate_model_population,
    inspect_linked_tree_package_command,
    model_build,
)
from synthpopcan.console import (
    make_table,
    print_checks_table,
    print_success,
    print_table,
    print_wrote,
)
from synthpopcan.controls import (
    build_wds_category_mapping_template,
    census_profile_template,
    inspect_census_profile_characteristics,
    inspect_wds_zip,
    read_category_mapping,
    read_census_profile_control_table,
    read_control_margins,
    read_control_table,
    read_wds_control_table,
    read_wds_selection,
    write_control_table,
)
from synthpopcan.geodata import fetch_display_boundaries, geodata_cache_dir
from synthpopcan.localdata import inspect_local_data_layout
from synthpopcan.models import (
    fetch_model_package,
    model_catalogue,
    model_catalogue_entry,
    remove_cached_model,
)
from synthpopcan.sources import (
    _is_private_path,
    inspect_source_root,
    read_source_sample,
    read_source_schema,
)
from synthpopcan.statcan import (
    CENSUS_PROFILE_GEO_LEVELS,
    fetch_census_profile,
    fetch_wds_metadata,
    fetch_wds_table,
    search_wds_tables,
    summarize_wds_metadata,
)
from synthpopcan.tree import validate_linked_population
from synthpopcan.validation import build_tree_output_validation_report
from synthpopcan.webapp import serve_webapp, validate_loopback_host
from synthpopcan.workflows.ipf import validate_ipf_artifact
from synthpopcan.workflows.types import IPFValidationRequest

_PATH = click.Path(path_type=Path)


def main(argv: list[str] | None = None) -> int:
    cli.main(args=argv, standalone_mode=False)
    return 0


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=False,
)
@click.version_option(__version__, prog_name="synthpopcan")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Canadian synthetic population tooling."""
    if ctx.invoked_subcommand is None:
        _print_workflow_choice_guide()


cli.add_command(microdata)
cli.add_command(ipf)
cli.add_command(small_area)
cli.add_command(enrich)
cli.add_command(bundle)


@cli.group()
def geodata() -> None:
    """Fetch and inspect prepared display-boundary assets."""


@geodata.command("fetch")
@click.argument("census_year", type=int)
@click.argument(
    "geography_level",
    type=click.Choice(["ct", "da", "ada", "csd"]),
)
@click.option(
    "--pruid",
    default=None,
    help="Province/territory PRUID for regional assets.",
)
@click.option(
    "--catalogue",
    type=_PATH,
    default=None,
    help="Local geodata catalogue JSON.",
)
def fetch_geodata(
    census_year: int,
    geography_level: str,
    pruid: str | None,
    catalogue: Path | None,
) -> None:
    """Download and verify a prepared display-boundary GeoJSON."""

    try:
        path = fetch_display_boundaries(
            census_year,
            geography_level,
            pruid=pruid,
            catalogue=catalogue,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    print_success(f"Prepared display boundaries ready: {path}")
    click.echo(path)


@geodata.command("cache-dir")
def geodata_cache_directory() -> None:
    """Print the local cache directory for prepared display boundaries."""

    click.echo(geodata_cache_dir())


@cli.group()
def models() -> None:
    """Discover, fetch, generate from, and build model packages."""


models.add_command(generate_model_population)
models.add_command(model_build)
model_build.add_command(inspect_linked_tree_package_command, "inspect")


@models.command("list")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def list_models(output_format: str) -> None:
    """List demo and downloadable model packages."""
    catalogue = {"models": model_catalogue()}
    if output_format == "json":
        write_output(catalogue, "json")
        return
    table = make_table(title="Model Packages")
    table.add_column("Package ID")
    table.add_column("Geography")
    table.add_column("Vintage")
    table.add_column("Size")
    table.add_column("Availability")
    for model in catalogue["models"]:
        table.add_row(
            str(model["id"]),
            str(model["geography"]),
            str(model["census_vintage"]),
            _format_model_size(model),
            _format_model_availability(model),
        )
    print_table(table)


@models.command("show")
@click.argument("model_id")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def show_model(model_id: str, output_format: str) -> None:
    """Show provenance, privacy, size, and generation details for one model."""
    try:
        model = model_catalogue_entry(model_id)
    except KeyError as exc:
        raise click.ClickException(f"unknown model package: {model_id}") from exc
    if output_format == "json":
        write_output(model, "json")
        return
    table = make_table(title=str(model["name"]))
    table.add_column("Field")
    table.add_column("Value")
    for field, value in _model_detail_rows(model):
        table.add_row(field, value)
    print_table(table)


@models.command("fetch")
@click.argument("model_id")
def fetch_model(model_id: str) -> None:
    """Download a model package into the local cache."""
    try:
        progress_console = Console(stderr=True)
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeElapsedColumn(),
            console=progress_console,
        ) as progress:
            task_id = progress.add_task(f"Fetching {model_id}", total=None)

            def update_progress(downloaded: int, total: int | None) -> None:
                progress.update(task_id, completed=downloaded, total=total)

            path = fetch_model_package(
                model_id,
                progress_callback=update_progress,
            )
    except KeyError as exc:
        raise click.ClickException(f"unknown model package: {model_id}") from exc
    except OSError as exc:
        raise click.ClickException(f"could not fetch {model_id}: {exc}") from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_success(f"Model package ready: {path}")
    click.echo(path)


@models.command("remove")
@click.argument("model_id")
def remove_model(model_id: str) -> None:
    """Remove a downloaded model package from the local cache."""
    try:
        removed = remove_cached_model(model_id)
    except KeyError as exc:
        raise click.ClickException(f"unknown model package: {model_id}") from exc
    if removed:
        print_success(f"Removed cached model package: {model_id}")
    else:
        print_success(f"No cached downloadable model package found for {model_id}")


@cli.group(invoke_without_command=True)
@click.pass_context
def guide(ctx: click.Context) -> None:
    """Show beginner workflow guidance."""
    if ctx.invoked_subcommand is None:
        _print_workflow_choice_guide()


@guide.command("ipf")
def guide_ipf() -> None:
    """Show the IPF from margin tables path."""
    _print_ipf_workflow_guide()


@guide.command("model")
def guide_model() -> None:
    """Show the generate from existing model path."""
    _print_model_workflow_guide()


@guide.command("small-area")
def guide_small_area() -> None:
    """Show the linked small-area synthesis path."""
    _print_small_area_workflow_guide()


@cli.command("serve")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host interface for the local web app.",
)
@click.option(
    "--port",
    default=8000,
    show_default=True,
    type=click.IntRange(1, 65535),
    help="Port for the local web app.",
)
@click.option(
    "--open/--no-open",
    "open_browser",
    default=True,
    show_default=True,
    help="Open the web app in your default browser.",
)
@click.option(
    "--workspace",
    default=Path("synthpopcan-runs"),
    show_default=True,
    type=_PATH,
    help="Managed workspace for local uploads, runs, and artifacts.",
)
def serve(host: str, port: int, open_browser: bool, workspace: Path) -> None:
    """Serve the local SynthPopCan web app."""
    try:
        normalized_host = validate_loopback_host(host)
        browser_host = (
            f"[{normalized_host}]" if ":" in normalized_host else normalized_host
        )
        print_success(f"Serving SynthPopCan at http://{browser_host}:{port}/")
        serve_webapp(
            host=normalized_host,
            port=port,
            workspace=workspace,
            open_browser=open_browser,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _print_workflow_choice_guide() -> None:
    click.echo("Choose a Workflow\n")
    _print_guide_item(
        "1. IPF from margin tables",
        "Seed rows already contain the variables in the controls.",
        "synthpopcan guide ipf",
    )
    _print_guide_item(
        "2. Generate from an existing model",
        "A prepared package should generate linked households and people.",
        "synthpopcan guide model",
    )
    _print_guide_item(
        "3. Linked small-area synthesis",
        "Linked candidates must be calibrated and assigned to target areas.",
        "synthpopcan guide small-area",
    )
    click.echo("Other tasks: synthpopcan --help")


def _print_ipf_workflow_guide() -> None:
    click.echo("IPF from Margin Tables\n")
    click.echo("Offline teaching path (fictional data):\n")
    _print_command_step(
        1,
        "Create the teaching files.",
        "synthpopcan data example ipf --out-dir ipf-example",
    )
    _print_command_step(
        2,
        "Check and fit the inputs.",
        "synthpopcan ipf check-inputs --seed ipf-example/seed.csv "
        "--controls ipf-example/controls.csv\n"
        "synthpopcan ipf fit --seed ipf-example/seed.csv "
        "--controls ipf-example/controls.csv --out ipf-example/weights.csv "
        "--report ipf-example/fit-report.json",
    )
    _print_command_step(
        3,
        "Review and validate the fit.",
        "synthpopcan ipf report ipf-example/fit-report.json\n"
        "synthpopcan validate ipf --population ipf-example/weights.csv "
        "--controls ipf-example/controls.csv --kind weights",
    )
    click.echo(
        "Research controls from Statistics Canada require a network connection:\n"
    )
    _print_command_step(
        4,
        "Find, inspect, and download a suitable WDS product.",
        'synthpopcan statcan wds search "population age sex"\n'
        "synthpopcan statcan wds explain PRODUCT_ID\n"
        "synthpopcan statcan wds fetch PRODUCT_ID --out-dir statcan-table",
    )
    _print_command_step(
        5,
        "Inspect and normalize the downloaded controls; replace the placeholders.",
        "synthpopcan controls wds inspect TABLE.zip\n"
        "synthpopcan controls from-wds TABLE.zip --dimensions "
        '"GEO,Age group,Sex" --count-column VALUE --out controls.csv',
    )
    click.echo(
        "Use a reviewed seed CSV with those controls, then repeat steps 2 and 3."
    )


def _print_model_workflow_guide() -> None:
    click.echo("Generate from an Existing Model\n")
    click.echo("Offline teaching path (bundled synthetic model):\n")
    _print_command_step(
        1,
        "Inspect the package and its limitations.",
        "synthpopcan models show demo-linked-household-person",
    )
    _print_command_step(
        2,
        "Generate linked households and people.",
        "synthpopcan models generate demo-linked-household-person "
        "--households 10 --condition 'geo=Demo North' --random-seed 13 "
        "--out population",
    )
    _print_command_step(
        3,
        "Validate the household and person links.",
        "synthpopcan validate linked population",
    )
    click.echo("Discover research packages with: synthpopcan models list")
    click.echo("Downloadable packages require a network connection and models fetch.")


def _print_small_area_workflow_guide() -> None:
    click.echo("Linked Small-Area Synthesis\n")
    click.echo("Template path: replace MODEL, PROFILE.csv, and the target scale.\n")
    _print_command_step(
        1,
        "Prepare normalized controls.",
        "synthpopcan geo controls --profile PROFILE.csv --geo-column ct "
        "--target 10000 --controls-out controls.csv",
    )
    _print_command_step(
        2,
        "Estimate the run before generating output.",
        "synthpopcan geo estimate --controls controls.csv --geo-dimension ct "
        "--candidate-households 10000",
    )
    _print_command_step(
        3,
        "Generate linked candidates and calibrate them.",
        "synthpopcan geo synthesize MODEL --households 10000 "
        "--controls controls.csv --geo-dimension ct --out small-area",
    )
    _print_command_step(
        4,
        "Validate the links; map only when matching boundaries are available.",
        "synthpopcan validate linked small-area\n"
        "synthpopcan geo map small-area --boundaries boundaries.geojson "
        "--geo-column ct",
    )


def _print_guide_item(title: str, use_when: str, next_command: str) -> None:
    click.echo(title)
    click.echo(f"   Use when: {use_when}")
    click.echo(f"   Next: {next_command}\n")


def _print_command_step(number: int, instruction: str, commands: str) -> None:
    click.echo(f"{number}. {instruction}")
    for command in commands.splitlines():
        click.echo(f"   {command}")
    click.echo()


def _format_model_availability(model: dict[str, Any]) -> str:
    if model.get("distribution") == "bundled":
        return "Bundled"
    if model.get("installed"):
        return "Downloaded"
    return "Download"


def _format_model_size(model: dict[str, Any]) -> str:
    size = model.get("size_bytes")
    if isinstance(size, int):
        return f"{size / (1024 * 1024):.1f} MB"
    return "Bundled"


def _format_model_doi(model: dict[str, Any]) -> str:
    """Render the archival DOI, or say plainly that a package has none."""

    doi = model.get("doi")
    if not doi:
        return "Not archived; bundled with the package"
    return f"https://doi.org/{doi}"


def _model_detail_rows(model: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("Package ID", str(model["id"])),
        ("Geography", str(model["geography"])),
        ("Census vintage", str(model["census_vintage"])),
        ("Availability", _format_model_availability(model)),
        ("Compressed size", _format_model_size(model)),
        ("Release status", str(model["release_status"])),
        ("Asset release", str(model["release_version"])),
        ("Cite as", _format_model_doi(model)),
        ("Source", str(model["provenance"])),
        ("Source licence", str(model["source_licence"])),
        ("Privacy", str(model["privacy_review_status"])),
        ("Generation guidance", str(model["generation_limits"])),
        ("Known limitations", str(model["known_limitations"])),
    ]


@cli.group()
def validate() -> None:
    """Validate IPF, linked-population, and model outputs."""


@validate.command("ipf")
@click.option(
    "--population",
    "population_path",
    required=True,
    type=_PATH,
    help="Weights or expanded synthetic population CSV.",
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=_PATH,
    help="Normalized controls CSV.",
)
@click.option(
    "--kind",
    "artifact_kind",
    required=True,
    type=click.Choice(["weights", "expanded"]),
    help="Population artifact type.",
)
@click.option(
    "--weight-column",
    default="weight",
    show_default=True,
    help="Weight column for --kind weights.",
)
@click.option("--tolerance", default=1e-6, type=float, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def validate_ipf_output_command(
    population_path: Path,
    controls_path: Path,
    artifact_kind: str,
    weight_column: str,
    tolerance: float,
    output_format: str,
) -> None:
    """Validate a generated population against normalized controls."""
    request = IPFValidationRequest(
        population_path=population_path,
        controls_path=controls_path,
        artifact_kind=cast(Literal["weights", "expanded"], artifact_kind),
        weight_column=weight_column,
        tolerance=tolerance,
    )
    try:
        result = validate_ipf_artifact(request)
    except OSError as exc:
        raise click_file_access_error(
            exc.filename or controls_path, "read", exc
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    report = result.report
    write_report(report, output_format, print_validation_report_table)

    if not report["passed"]:
        raise click.ClickException(
            "Validation failed; generated artifact does not match controls "
            f"within tolerance {format_report_number(tolerance)}."
        )


@validate.command("linked")
@click.argument("population_dir", metavar="POPULATION", type=_PATH)
@click.option(
    "--household-id-column",
    default="synthetic_household_id",
    show_default=True,
    help="Household identifier column in the household CSV.",
)
@click.option(
    "--person-household-id-column",
    default="synthetic_household_id",
    show_default=True,
    help="Household identifier column in the person CSV.",
)
@click.option(
    "--household-size-column",
    default="household_size",
    show_default=True,
    help="Household column containing the expected number of persons.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def validate_linked_command(
    population_dir: Path,
    household_id_column: str,
    person_household_id_column: str,
    household_size_column: str,
    output_format: str,
) -> None:
    """Validate person rows are linked to generated households."""
    households_path = population_dir / "households.csv"
    persons_path = population_dir / "persons.csv"
    try:
        report = validate_linked_population(
            households=read_csv_rows(households_path),
            persons=read_csv_rows(persons_path),
            household_id_column=household_id_column,
            person_household_id_column=person_household_id_column,
            household_size_column=household_size_column,
        )
    except OSError as exc:
        raise click_file_access_error(
            exc.filename or households_path, "read", exc
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    write_output(report, output_format, title="Linked Output Validation")

    if not report["passed"]:
        raise click.ClickException(
            "Linked output validation found household/person linkage problems."
        )


@validate.command("model")
@click.option(
    "--generated",
    "generated_path",
    required=True,
    type=_PATH,
    help="Generated synthetic rows CSV.",
)
@click.option(
    "--training",
    "training_path",
    required=True,
    type=_PATH,
    help="Training view CSV used to train the tree model.",
)
@click.option(
    "--target-columns",
    required=True,
    help="Comma-separated target columns to compare.",
)
@click.option(
    "--conditioning-columns",
    default="",
    help="Optional comma-separated conditioning columns to compare.",
)
@click.option(
    "--weight-column",
    default=None,
    help="Optional training row weight column.",
)
@click.option("--tolerance", default=0.05, type=float, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def validate_model_command(
    generated_path: Path,
    training_path: Path,
    target_columns: str,
    conditioning_columns: str,
    weight_column: str | None,
    tolerance: float,
    output_format: str,
) -> None:
    """Compare generated tree rows with the training-view distributions."""
    try:
        report = build_tree_output_validation_report(
            training_rows=read_csv_rows(training_path),
            generated_rows=read_csv_rows(generated_path),
            target_columns=_parse_column_list(target_columns, "target columns"),
            conditioning_columns=_parse_optional_column_list(conditioning_columns),
            weight_field=weight_column,
            tolerance=tolerance,
        )
    except OSError as exc:
        raise click_file_access_error(
            exc.filename or training_path, "read", exc
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    write_report(report, output_format, print_tree_output_validation_report_table)

    if not report["passed"]:
        raise click.ClickException(
            "Tree output validation found distribution shifts or unknown "
            f"categories beyond tolerance {format_report_number(tolerance)}."
        )


@cli.group(name="data")
def data_group() -> None:
    """Inspect local data files and check setup."""


@data_group.command("example")
@click.argument("name", type=click.Choice(["ipf"]))
@click.option("--out-dir", required=True, type=_PATH)
@click.option("--force", is_flag=True, help="Replace existing example files.")
def write_example_data(name: str, out_dir: Path, force: bool) -> None:
    """Write small fictional teaching files for a documented workflow."""

    files = {
        "seed.csv": ("PP_ID,AGEGRP,SEX,WEIGHT\n11101,adult,F,1\n11102,child,M,1\n"),
        "controls.csv": (
            "margin,dimensions,AGEGRP,SEX,count\n"
            "age,AGEGRP,adult,,100\n"
            "age,AGEGRP,child,,100\n"
            "sex,SEX,,F,100\n"
            "sex,SEX,,M,100\n"
        ),
    }
    existing = [
        out_dir / filename for filename in files if (out_dir / filename).exists()
    ]
    if existing and not force:
        names = ", ".join(path.name for path in existing)
        raise click.ClickException(
            f"Example files already exist in {out_dir}: {names}. "
            "Choose another --out-dir or pass --force to replace them."
        )
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        for filename, contents in files.items():
            path = out_dir / filename
            path.write_text(contents, encoding="utf-8")
            print_wrote(path)
    except OSError as exc:
        raise click_file_access_error(out_dir, "write to", exc) from exc
    click.echo(f"Wrote the fictional {name} teaching example; it is not census data.")


@data_group.command("doctor")
@click.option(
    "--data-root",
    type=_PATH,
    default=None,
    help=(
        "Local data directory to check. Defaults to SYNTHPOPCAN_DATA_ROOT, then data/."
    ),
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def data_doctor(data_root: Path, output_format: str) -> None:
    """Check whether expected local data files are available."""
    data_root = resolve_data_root(data_root)
    checks = inspect_local_data_layout(data_root)
    payload = {
        "data_root": str(data_root),
        "checks": [check.as_dict() for check in checks],
    }
    if output_format == "json":
        write_output(payload, "json")
        return
    print_checks_table(
        [check.as_dict() for check in checks],
        title="Local Data Check",
    )


def resolve_data_root(data_root: Path | None) -> Path:
    """Resolve the data root from CLI option, environment, or local default."""

    if data_root is not None:
        return data_root
    env_value = os.environ.get("SYNTHPOPCAN_DATA_ROOT")
    if env_value:
        return Path(env_value)
    return Path("data")


def _parse_column_list(value: str, label: str) -> tuple[str, ...]:
    """Parse a required comma-separated column list for Click callbacks."""

    columns = split_columns(value)
    if not columns:
        raise click.ClickException(f"at least one {label} value is required")
    return columns


def _parse_optional_column_list(value: str) -> tuple[str, ...]:
    """Parse an optional comma-separated column list for Click callbacks."""

    return split_columns(value)


@data_group.command("inspect")
@click.argument("root", type=_PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_sources(root: Path, output_format: str) -> None:
    """Summarize files under a local source root."""
    try:
        write_output(inspect_source_root(root), output_format)
    except OSError as exc:
        raise click_file_access_error(root, "read", exc) from exc


@data_group.command("schema")
@click.argument("path", type=_PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_source_schema(path: Path, output_format: str) -> None:
    """Inspect source file columns without printing rows."""
    try:
        write_output(read_source_schema(path), output_format)
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc


@data_group.command("sample")
@click.argument("path", type=_PATH)
@click.option("--rows", default=5, type=int, show_default=True)
@click.option("--allow-private", is_flag=True, help="Allow sampling private paths.")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def sample_source(
    path: Path, rows: int, allow_private: bool, output_format: str
) -> None:
    """Print a small source file sample."""
    if _is_private_path(path) and not allow_private:
        raise click.ClickException(
            "Refusing to print rows from a private data path. "
            "Pass --allow-private if you understand the data sensitivity."
        )
    try:
        write_output(read_source_sample(path, rows), output_format)
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc


@cli.group()
def controls() -> None:
    """Normalize and validate IPF control tables."""


@controls.group(name="census-profile")
def census_profile_controls() -> None:
    """Inspect Census Profile files and mapping templates."""


@controls.group(name="wds")
def wds_controls() -> None:
    """Inspect local StatCan WDS ZIPs before normalization."""


@controls.command("check")
@click.argument("path", type=_PATH)
def check_controls_command(path: Path) -> None:
    """Validate a normalized long control CSV."""
    try:
        read_control_margins(path)
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_success(f"Controls are valid: {path}")


@controls.command("from-csv")
@click.argument("source", type=_PATH)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output normalized controls CSV.",
)
def normalize_controls_from_csv(source: Path, out_path: Path) -> None:
    """Normalize a local long control CSV."""
    try:
        table = read_control_table(source)
        write_control_table(out_path, table)
    except OSError as exc:
        raise click_file_access_error(exc.filename or source, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(out_path)


@controls.command("from-wds")
@click.argument("source", type=_PATH)
@click.option(
    "--dimensions",
    required=True,
    help="Comma-separated WDS columns to use as control dimensions.",
)
@click.option("--count-column", required=True, help="WDS column containing counts.")
@click.option(
    "--margin-name",
    default="wds",
    show_default=True,
    help="Name for the generated control margin.",
)
@click.option(
    "--mapping", "mapping_path", type=_PATH, help="Optional category mapping JSON."
)
@click.option(
    "--selection",
    "selection_path",
    type=_PATH,
    help="Optional category-selection JSON exported by the web app.",
)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output normalized controls CSV.",
)
def normalize_controls_from_wds(
    source: Path,
    dimensions: str,
    count_column: str,
    margin_name: str,
    mapping_path: Path | None,
    selection_path: Path | None,
    out_path: Path,
) -> None:
    """Normalize a local StatCan WDS CSV ZIP."""
    try:
        console = Console(stderr=True)
        with console.status("Reading and normalizing WDS ZIP..."):
            table = read_wds_control_table(
                source,
                dimensions=parse_columns(dimensions),
                count_column=count_column,
                margin_name=margin_name,
                category_mapping=read_category_mapping(mapping_path)
                if mapping_path
                else None,
                selection=read_wds_selection(selection_path)
                if selection_path
                else None,
            )
        with console.status("Writing normalized controls CSV..."):
            write_control_table(out_path, table)
    except OSError as exc:
        raise click_file_access_error(exc.filename or source, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(
            exc, lambda error: format_wds_control_error(error, source)
        ) from exc
    print_wrote(out_path)


def format_wds_control_error(exc: ValueError, source: Path) -> str:
    """Attach actionable WDS normalization next steps to common errors."""

    message = str(exc)
    if "unmapped category" in message:
        return (
            f"{message}\n"
            "Next step: regenerate or edit the category mapping, for example "
            f"`synthpopcan controls wds mapping-template {source} "
            '--dimensions "COLUMN" --preset canonical --out categories.json`.'
        )
    if "missing columns" in message:
        return (
            f"{message}\n"
            "Next step: inspect the ZIP column names with "
            f"`synthpopcan controls wds inspect {source}` and rerun "
            "`controls from-wds` with the displayed dimension and count columns."
        )
    return message


@wds_controls.command("inspect")
@click.argument("source", type=_PATH)
@click.option("--sample-rows", default=5, type=int, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_wds_controls(source: Path, sample_rows: int, output_format: str) -> None:
    """Inspect a local StatCan WDS ZIP and suggest a controls command."""
    try:
        report = inspect_wds_zip(source, sample_rows=sample_rows)
    except OSError as exc:
        raise click_file_access_error(source, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    write_report(report, output_format, print_wds_inspection_table)


@wds_controls.command("mapping-template")
@click.argument("source", type=_PATH)
@click.option(
    "--dimensions",
    required=True,
    help="Comma-separated WDS columns whose categories need mapping.",
)
@click.option(
    "--preset",
    default="blank",
    type=click.Choice(["blank", "canonical"]),
    show_default=True,
    help="Optionally prefill common StatCan labels.",
)
@click.option("--out", "out_path", required=True, type=_PATH)
def write_wds_mapping_template(
    source: Path,
    dimensions: str,
    preset: str,
    out_path: Path,
) -> None:
    """Write a starter WDS category mapping JSON."""
    try:
        payload = build_wds_category_mapping_template(
            source,
            dimensions=parse_columns(dimensions),
            preset=preset,
        )
        write_json_object(out_path, payload)
    except OSError as exc:
        raise click_file_access_error(exc.filename or source, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(out_path)


@controls.command("from-census-profile")
@click.argument("source", type=_PATH)
@click.option(
    "--mapping",
    "mapping_path",
    required=True,
    type=_PATH,
    help="JSON mapping from Census Profile rows to control categories.",
)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output normalized controls CSV.",
)
def normalize_controls_from_census_profile(
    source: Path,
    mapping_path: Path,
    out_path: Path,
) -> None:
    """Normalize a local StatCan Census Profile CSV."""
    try:
        table = read_census_profile_control_table(source, mapping_path)
        write_control_table(out_path, table)
    except OSError as exc:
        raise click_file_access_error(exc.filename or source, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(out_path)


@census_profile_controls.command("inspect")
@click.argument("source", type=_PATH)
@click.option(
    "--characteristic-column",
    default="CHARACTERISTIC_NAME",
    show_default=True,
    help="Column containing Census Profile characteristic labels.",
)
@click.option(
    "--count-column",
    default="C1_COUNT_TOTAL",
    show_default=True,
    help="Column containing counts to preview.",
)
@click.option("--search", default=None, help="Filter characteristic labels.")
@click.option("--limit", default=25, type=int, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_census_profile_controls(
    source: Path,
    characteristic_column: str,
    count_column: str,
    search: str | None,
    limit: int,
    output_format: str,
) -> None:
    """List candidate Census Profile characteristic rows."""
    try:
        rows = inspect_census_profile_characteristics(
            source,
            characteristic_column=characteristic_column,
            count_column=count_column,
            search=search,
            limit=limit,
        )
    except OSError as exc:
        raise click_file_access_error(source, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    write_report(rows, output_format, print_census_profile_characteristics_table)


@census_profile_controls.command("template")
@click.argument("name", type=click.Choice(["age5", "sex"]))
@click.option(
    "--geo-column",
    default="GEO_CODE",
    show_default=True,
    help="Census Profile geography code column.",
)
@click.option(
    "--geo-dimension",
    default="geo",
    show_default=True,
    help="Output control dimension name for geography.",
)
@click.option(
    "--characteristic-column",
    default="CHARACTERISTIC_NAME",
    show_default=True,
    help="Census Profile characteristic label column.",
)
@click.option(
    "--count-column",
    default="C1_COUNT_TOTAL",
    show_default=True,
    help="Census Profile count column.",
)
@click.option("--out", "out_path", required=True, type=_PATH)
def write_census_profile_template(
    name: str,
    geo_column: str,
    geo_dimension: str,
    characteristic_column: str,
    count_column: str,
    out_path: Path,
) -> None:
    """Write a starter Census Profile mapping JSON."""
    try:
        payload = census_profile_template(
            name,
            geography_column=geo_column,
            geography_dimension=geo_dimension,
            characteristic_column=characteristic_column,
            count_column=count_column,
        )
        write_json_object(out_path, payload)
    except OSError as exc:
        raise click_file_access_error(out_path, "write", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    print_wrote(out_path)


@cli.group()
def statcan() -> None:
    """Fetch Statistics Canada data."""


@statcan.group()
def wds() -> None:
    """Fetch WDS table data."""


@wds.command("fetch")
@click.argument("product_id")
@click.option(
    "--lang", default="en", type=click.Choice(["en", "fr"]), show_default=True
)
@click.option("--out-dir", required=True, type=_PATH)
def run_statcan_wds_fetch(product_id: str, out_dir: Path, lang: str) -> None:
    """Download a full WDS table CSV ZIP by product ID."""
    try:
        console = Console(stderr=True)
        with console.status(f"Downloading StatCan WDS table {product_id}..."):
            zip_path = fetch_wds_table(product_id, out_dir, lang)
        print_wrote(zip_path)
    except OSError as exc:
        raise click_file_access_error(out_dir, "write to", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    click.echo(zip_path)


@wds.command("search")
@click.argument("query")
@click.option("--limit", default=10, type=int, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "tsv", "json"]),
    show_default=True,
    help="Output format for search results.",
)
def run_statcan_wds_search(query: str, limit: int, output_format: str) -> None:
    """Search the WDS table inventory."""
    try:
        rows = search_wds_tables_for_cli(query, limit)
    except OSError as exc:
        raise click.ClickException(f"Could not search StatCan WDS: {exc}") from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    write_wds_search_results(rows, output_format)


@wds.command("metadata")
@click.argument("product_id")
@click.option("--out", "out_path", type=_PATH, help="Optional JSON output path.")
def run_statcan_wds_metadata(product_id: str, out_path: Path | None) -> None:
    """Fetch WDS cube metadata by product ID."""
    try:
        metadata = fetch_wds_metadata(product_id)
        if out_path:
            write_json_object(out_path, metadata)
            print_wrote(out_path)
        else:
            write_output(metadata, "json")
    except OSError as exc:
        action = "write" if out_path else "fetch"
        target = out_path if out_path else f"StatCan WDS metadata for {product_id}"
        raise click_file_access_error(target, action, exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc


@wds.command("explain")
@click.argument("product_id")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def run_statcan_wds_explain(product_id: str, output_format: str) -> None:
    """Explain a WDS table and show next IPF-control commands."""
    try:
        summary = summarize_wds_metadata(fetch_wds_metadata(product_id))
    except OSError as exc:
        raise click.ClickException(
            f"Could not fetch StatCan WDS metadata for {product_id}: {exc}"
        ) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    write_report(summary, output_format, print_wds_metadata_explanation_table)


@statcan.group(name="census-profile")
def census_profile() -> None:
    """Fetch Census Profile bulk downloads."""


@census_profile.command("fetch")
@click.option(
    "--year",
    "census_year",
    type=click.Choice(("2016", "2021")),
    default="2016",
    show_default=True,
    help="Census vintage.",
)
@click.option(
    "--geo-level",
    required=True,
    type=click.Choice(CENSUS_PROFILE_GEO_LEVELS, case_sensitive=False),
    help="Census Profile bulk-download geography product.",
)
@click.option("--out-dir", required=True, type=_PATH)
def run_statcan_census_profile_fetch(
    census_year: str, geo_level: str, out_dir: Path
) -> None:
    """Download a known Census Profile bulk CSV."""
    try:
        path = fetch_census_profile(
            geo_level,
            out_dir,
            census_year=int(census_year),
        )
    except ValueError as exc:
        raise click_value_error(exc) from exc
    except OSError as exc:
        raise click_file_access_error(out_dir, "write to", exc) from exc
    print_wrote(path)
    click.echo(path)


def search_wds_tables_for_cli(query: str, limit: int) -> list[dict[str, str]]:
    return [result.as_dict() for result in search_wds_tables(query, limit)]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
