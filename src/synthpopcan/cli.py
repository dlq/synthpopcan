"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
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
from rich.table import Table

from synthpopcan import __version__
from synthpopcan.cli_geo import small_area
from synthpopcan.cli_ipf import ipf, read_population_artifact
from synthpopcan.cli_microdata import microdata
from synthpopcan.cli_output import (
    format_file_access_error,
    format_report_number,
    print_census_profile_characteristics_table,
    print_tree_output_validation_report_table,
    print_validation_report_table,
    print_wds_inspection_table,
    print_wds_metadata_explanation_table,
    write_output,
    write_wds_search_results,
)
from synthpopcan.cli_tree import tree
from synthpopcan.console import (
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
    write_control_table,
)
from synthpopcan.localdata import inspect_local_data_layout
from synthpopcan.models import (
    fetch_model_package,
    model_cache_path,
    model_catalogue,
    remove_cached_model,
)
from synthpopcan.sources import (
    _is_private_path,
    inspect_source_root,
    read_source_sample,
    read_source_schema,
)
from synthpopcan.statcan import (
    fetch_census_profile_2016,
    fetch_wds_metadata,
    fetch_wds_table,
    search_wds_tables,
    summarize_wds_metadata,
)
from synthpopcan.tree import validate_linked_population
from synthpopcan.validation import (
    build_control_validation_report,
    build_tree_output_validation_report,
)
from synthpopcan.webapp import serve_webapp

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
def cli() -> None:
    """Canadian synthetic population tooling."""


cli.add_command(microdata)
cli.add_command(ipf)
cli.add_command(tree)
cli.add_command(small_area)


@cli.group()
def models() -> None:
    """List, fetch, and manage downloadable model packages."""


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
    table = Table(title="Model Packages")
    table.add_column("Package ID")
    table.add_column("Availability")
    table.add_column("Summary")
    for model in catalogue["models"]:
        table.add_row(
            str(model["id"]),
            format_model_availability(model),
            format_model_catalogue_summary(model),
        )
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
        raise click.ClickException(str(exc)) from exc
    print_success(f"Model package ready: {path}")


@models.command("path")
@click.argument("model_id")
def print_model_path(model_id: str) -> None:
    """Print where a downloadable model package is stored."""
    try:
        path = model_cache_path(model_id)
    except KeyError as exc:
        raise click.ClickException(f"unknown model package: {model_id}") from exc
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
        print_workflow_choice_guide()


@guide.command("ipf")
def guide_ipf() -> None:
    """Show the IPF from margin tables path."""
    print_ipf_workflow_guide()


@guide.command("model")
def guide_model() -> None:
    """Show the generate from existing model path."""
    print_model_workflow_guide()


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
def serve(host: str, port: int, open_browser: bool) -> None:
    """Serve the local SynthPopCan web app."""
    print_success(f"Serving SynthPopCan at http://{host}:{port}/")
    serve_webapp(host=host, port=port, open_browser=open_browser)


def print_workflow_choice_guide() -> None:
    table = Table(title="Choose a Workflow")
    table.add_column("Workflow", no_wrap=True)
    table.add_column("Use When")
    table.add_column("Next Command", no_wrap=True)
    table.add_row(
        "IPF from margin tables",
        (
            "You have seed rows, want to find or prepare margin/control totals, "
            "and need fitted weights or expanded rows."
        ),
        "synthpopcan guide ipf",
    )
    table.add_row(
        "Generate from existing model",
        (
            "You have a prepared household/person model package and want to "
            "export synthetic household and person rows."
        ),
        "synthpopcan guide model",
    )
    print_table(table)


def print_ipf_workflow_guide() -> None:
    table = Table(title="IPF from Margin Tables")
    table.add_column("Step", justify="right", no_wrap=True)
    table.add_column("Setup Path", no_wrap=True)
    table.add_column("Command or Next Step")
    table.add_row(
        "1",
        "Use a demo or make templates",
        "synthpopcan serve",
    )
    table.add_row(
        "2",
        "Generate from a StatCan table",
        'synthpopcan statcan wds search "population age sex"',
    )
    table.add_row(
        "3",
        "Inspect product",
        "synthpopcan statcan wds explain PRODUCT_ID",
    )
    table.add_row(
        "4",
        "Prepare IPF inputs",
        (
            "synthpopcan controls wds inspect TABLE.zip\n"
            "synthpopcan controls from-wds TABLE.zip --dimensions "
            '"GEO,Age group,Sex" --count-column VALUE --out controls.csv'
        ),
    )
    table.add_row(
        "5",
        "Run IPF",
        (
            "synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv\n"
            "synthpopcan ipf fit --seed seed.csv --controls controls.csv "
            "--out weights.csv --report fit-report.json"
        ),
    )
    table.add_row(
        "6",
        "Preview or validate",
        (
            "synthpopcan ipf report fit-report.json\n"
            "synthpopcan validate controls --population weights.csv "
            "--controls controls.csv --kind weights"
        ),
    )
    print_table(table)


def print_model_workflow_guide() -> None:
    table = Table(title="Generate from Existing Model")
    table.add_column("Step", justify="right", no_wrap=True)
    table.add_column("Setup Path", no_wrap=True)
    table.add_column("Command or Next Step")
    table.add_row(
        "1",
        "Use premade model",
        "synthpopcan serve",
    )
    table.add_row(
        "2",
        "Inspect selected model",
        "synthpopcan models list\n"
        "synthpopcan models fetch montreal-cma-2016-all-fields\n"
        "synthpopcan tree inspect-package demo-linked-household-person",
    )
    table.add_row(
        "3",
        "Generate rows",
        (
            "synthpopcan tree generate-from-package demo-linked-household-person "
            "--households 100 --households-out households.csv "
            "--persons-out persons.csv"
        ),
    )
    table.add_row(
        "4",
        "Preview or validate",
        (
            "synthpopcan validate linked-output --households households.csv "
            "--persons persons.csv"
        ),
    )
    print_table(table)


def format_model_availability(model: dict[str, object]) -> str:
    if model.get("distribution") == "bundled":
        return "Bundled"
    if model.get("installed"):
        return "Downloaded"
    return "Download with `synthpopcan models fetch`"


def format_model_catalogue_summary(model: dict[str, object]) -> str:
    parts = [
        str(model.get("name", "")),
        f"Geography: {model.get('geography', '')}",
        f"Status: {model.get('release_status', '')}",
    ]
    size = model.get("size_bytes")
    if isinstance(size, int):
        parts.append(f"Download: {size / (1024 * 1024):.1f} MB")
    default_generation = model.get("default_generation")
    if isinstance(default_generation, dict):
        households = default_generation.get("households")
        conditions = default_generation.get("conditions")
        if households:
            default = f"{households} households"
            if conditions:
                default = f"{default}; {conditions}"
            parts.append(f"Default: {default}")
    return "\n".join(part for part in parts if part)


@cli.group()
def validate() -> None:
    """Validate generated artifacts against controls."""


@validate.command("controls")
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
    "--weight-field",
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
def validate_controls_output(
    population_path: Path,
    controls_path: Path,
    artifact_kind: str,
    weight_field: str,
    tolerance: float,
    output_format: str,
) -> None:
    """Validate a generated population against normalized controls."""
    try:
        control_table = read_control_table(controls_path)
        rows, weights = read_population_artifact(
            population_path,
            artifact_kind,
            weight_field,
        )
        report = build_control_validation_report(
            control_table,
            rows,
            weights,
            tolerance=tolerance,
            artifact_kind=artifact_kind,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or controls_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_validation_report_table(report)

    if not report["passed"]:
        raise click.ClickException(
            "Validation failed; generated artifact does not match controls "
            f"within tolerance {format_report_number(tolerance)}."
        )


@validate.command("linked-output")
@click.option(
    "--households",
    "households_path",
    required=True,
    type=_PATH,
    help="Generated household CSV.",
)
@click.option(
    "--persons",
    "persons_path",
    required=True,
    type=_PATH,
    help="Generated person CSV.",
)
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
def validate_linked_output(
    households_path: Path,
    persons_path: Path,
    household_id_column: str,
    person_household_id_column: str,
    household_size_column: str,
    output_format: str,
) -> None:
    """Validate person rows are linked to generated households."""
    try:
        report = validate_linked_population(
            households=read_csv(households_path),
            persons=read_csv(persons_path),
            household_id_column=household_id_column,
            person_household_id_column=person_household_id_column,
            household_size_column=household_size_column,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or households_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    write_output(report, output_format, title="Linked Output Validation")

    if not report["passed"]:
        raise click.ClickException(
            "Linked output validation found household/person linkage problems."
        )


@validate.command("tree-output")
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
    "--weight-field",
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
def validate_tree_output(
    generated_path: Path,
    training_path: Path,
    target_columns: str,
    conditioning_columns: str,
    weight_field: str | None,
    tolerance: float,
    output_format: str,
) -> None:
    """Compare generated tree rows with the training-view distributions."""
    try:
        report = build_tree_output_validation_report(
            training_rows=read_csv(training_path),
            generated_rows=read_csv(generated_path),
            target_columns=parse_column_list(target_columns, "target columns"),
            conditioning_columns=parse_optional_column_list(conditioning_columns),
            weight_field=weight_field,
            tolerance=tolerance,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or training_path, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_tree_output_validation_report_table(report)

    if not report["passed"]:
        raise click.ClickException(
            "Tree output validation found distribution shifts or unknown "
            f"categories beyond tolerance {format_report_number(tolerance)}."
        )


@cli.group(name="data")
def data_group() -> None:
    """Check local data and metadata setup."""


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
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print_checks_table(payload["checks"], title="Local Data Check")


def resolve_data_root(data_root: Path | None) -> Path:
    """Resolve the data root from CLI option, environment, or local default."""

    if data_root is not None:
        return data_root
    env_value = os.environ.get("SYNTHPOPCAN_DATA_ROOT")
    if env_value:
        return Path(env_value)
    return Path("data")


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file as string-valued dictionaries for validation commands."""

    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_column_list(value: str, label: str) -> tuple[str, ...]:
    """Parse a required comma-separated column list for Click callbacks."""

    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException(f"at least one {label} value is required")
    return columns


def parse_optional_column_list(value: str) -> tuple[str, ...]:
    """Parse an optional comma-separated column list for Click callbacks."""

    return tuple(part.strip() for part in value.split(",") if part.strip())


@cli.group()
def sources() -> None:
    """Inspect local source files safely."""


@sources.command("inspect")
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
        raise click.ClickException(format_file_access_error(root, "read", exc)) from exc


@sources.command("schema")
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
        raise click.ClickException(format_file_access_error(path, "read", exc)) from exc


@sources.command("sample")
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
        raise click.ClickException(format_file_access_error(path, "read", exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.group()
def controls() -> None:
    """Normalize and validate IPF control tables."""


@controls.group(name="census-profile")
def census_profile_controls() -> None:
    """Inspect Census Profile files and mapping templates."""


@controls.group(name="wds")
def wds_controls() -> None:
    """Inspect local StatCan WDS ZIPs before normalization."""


@controls.command("validate")
@click.argument("path", type=_PATH)
def validate_controls(path: Path) -> None:
    """Validate a normalized long control CSV."""
    try:
        read_control_margins(path)
    except OSError as exc:
        raise click.ClickException(format_file_access_error(path, "read", exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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
        raise click.ClickException(
            format_file_access_error(exc.filename or source, "access", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
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
            )
        with console.status("Writing normalized controls CSV..."):
            write_control_table(out_path, table)
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or source, "access", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(format_wds_control_error(exc, source)) from exc
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
        raise click.ClickException(
            format_file_access_error(source, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_wds_inspection_table(report)


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
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or source, "access", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
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
        raise click.ClickException(
            format_file_access_error(exc.filename or source, "access", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
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
        raise click.ClickException(
            format_file_access_error(source, "read", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    print_census_profile_characteristics_table(rows)


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
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(out_path, "write", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
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
        raise click.ClickException(
            format_file_access_error(out_dir, "write to", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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
        raise click.ClickException(str(exc)) from exc
    write_wds_search_results(rows, output_format)


@wds.command("metadata")
@click.argument("product_id")
@click.option("--out", "out_path", type=_PATH, help="Optional JSON output path.")
def run_statcan_wds_metadata(product_id: str, out_path: Path | None) -> None:
    """Fetch WDS cube metadata by product ID."""
    try:
        metadata = fetch_wds_metadata(product_id)
        payload = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        if out_path:
            out_path.write_text(payload)
            print_wrote(out_path)
        else:
            print(payload, end="")
    except OSError as exc:
        action = "write" if out_path else "fetch"
        target = out_path if out_path else f"StatCan WDS metadata for {product_id}"
        raise click.ClickException(
            format_file_access_error(target, action, exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print_wds_metadata_explanation_table(summary)


@statcan.group(name="census-profile")
def census_profile() -> None:
    """Fetch Census Profile bulk downloads."""


@census_profile.command("fetch")
@click.option("--year", required=True, type=click.Choice(["2016"]))
@click.option("--geo-level", required=True)
@click.option("--out-dir", required=True, type=_PATH)
def run_statcan_census_profile_fetch(year: str, geo_level: str, out_dir: Path) -> None:
    """Download a known Census Profile bulk CSV."""
    if year != "2016":
        raise click.ClickException(
            "Only the 2016 Census Profile registry is currently supported."
        )
    try:
        print_wrote(fetch_census_profile_2016(geo_level, out_dir))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(out_dir, "write to", exc)
        ) from exc


def search_wds_tables_for_cli(query: str, limit: int) -> list[dict[str, str]]:
    return [result.as_dict() for result in search_wds_tables(query, limit)]


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException("at least one column is required")
    return columns


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
