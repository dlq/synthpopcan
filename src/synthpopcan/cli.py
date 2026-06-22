"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import click

from synthpopcan import __version__
from synthpopcan.cli_ipf import ipf, read_population_artifact
from synthpopcan.cli_microdata import microdata
from synthpopcan.cli_output import (
    format_report_number,
    print_census_profile_characteristics_table,
    print_tree_output_validation_report_table,
    print_validation_report_table,
    write_output,
    write_wds_search_results,
)
from synthpopcan.cli_tree import tree
from synthpopcan.console import print_checks_table, print_wrote
from synthpopcan.controls import (
    census_profile_template,
    inspect_census_profile_characteristics,
    read_category_mapping,
    read_census_profile_control_table,
    read_control_margins,
    read_control_table,
    read_wds_control_table,
    write_control_table,
)
from synthpopcan.localdata import inspect_local_data_layout
from synthpopcan.sources import (
    inspect_source_root,
    is_private_path,
    read_source_sample,
    read_source_schema,
)
from synthpopcan.statcan import (
    fetch_census_profile_2016,
    fetch_wds_metadata,
    fetch_wds_table,
    search_wds_tables,
)
from synthpopcan.tree import validate_linked_population
from synthpopcan.validation import (
    build_control_validation_report,
    build_tree_output_validation_report,
)

PATH = click.Path(path_type=Path)


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


@cli.group()
def validate() -> None:
    """Validate generated artifacts against controls."""


@validate.command("controls")
@click.option(
    "--population",
    "population_path",
    required=True,
    type=PATH,
    help="Weights or expanded synthetic population CSV.",
)
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=PATH,
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
    type=PATH,
    help="Generated household CSV.",
)
@click.option(
    "--persons",
    "persons_path",
    required=True,
    type=PATH,
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
    type=PATH,
    help="Generated synthetic rows CSV.",
)
@click.option(
    "--training",
    "training_path",
    required=True,
    type=PATH,
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
    type=PATH,
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
    if data_root is not None:
        return data_root
    env_value = os.environ.get("SYNTHPOPCAN_DATA_ROOT")
    if env_value:
        return Path(env_value)
    return Path("data")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_column_list(value: str, label: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException(f"at least one {label} value is required")
    return columns


def parse_optional_column_list(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


@cli.group()
def sources() -> None:
    """Inspect local source files safely."""


@sources.command("inspect")
@click.argument("root", type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_sources(root: Path, output_format: str) -> None:
    """Summarize files under a local source root."""
    write_output(inspect_source_root(root), output_format)


@sources.command("schema")
@click.argument("path", type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def inspect_source_schema(path: Path, output_format: str) -> None:
    """Inspect source file columns without printing rows."""
    write_output(read_source_schema(path), output_format)


@sources.command("sample")
@click.argument("path", type=PATH)
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
    if is_private_path(path) and not allow_private:
        raise click.ClickException("sampling private data requires --allow-private")
    try:
        write_output(read_source_sample(path, rows), output_format)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@cli.group()
def controls() -> None:
    """Normalize and validate IPF control tables."""


@controls.group(name="census-profile")
def census_profile_controls() -> None:
    """Inspect Census Profile files and mapping templates."""


@controls.command("validate")
@click.argument("path", type=PATH)
def validate_controls(path: Path) -> None:
    """Validate a normalized long control CSV."""
    read_control_margins(path)


@controls.command("from-csv")
@click.argument("source", type=PATH)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=PATH,
    help="Output normalized controls CSV.",
)
def normalize_controls_from_csv(source: Path, out_path: Path) -> None:
    """Normalize a local long control CSV."""
    table = read_control_table(source)
    write_control_table(out_path, table)
    print_wrote(out_path)


@controls.command("from-wds")
@click.argument("source", type=PATH)
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
    "--mapping", "mapping_path", type=PATH, help="Optional category mapping JSON."
)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=PATH,
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
        table = read_wds_control_table(
            source,
            dimensions=parse_columns(dimensions),
            count_column=count_column,
            margin_name=margin_name,
            category_mapping=read_category_mapping(mapping_path)
            if mapping_path
            else None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_control_table(out_path, table)
    print_wrote(out_path)


@controls.command("from-census-profile")
@click.argument("source", type=PATH)
@click.option(
    "--mapping",
    "mapping_path",
    required=True,
    type=PATH,
    help="JSON mapping from Census Profile rows to control categories.",
)
@click.option(
    "--out",
    "out_path",
    required=True,
    type=PATH,
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
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_control_table(out_path, table)
    print_wrote(out_path)


@census_profile_controls.command("inspect")
@click.argument("source", type=PATH)
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
@click.option("--out", "out_path", required=True, type=PATH)
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
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
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
@click.option("--out-dir", required=True, type=PATH)
def run_statcan_wds_fetch(product_id: str, out_dir: Path, lang: str) -> None:
    """Download a full WDS table CSV ZIP by product ID."""
    print_wrote(fetch_wds_table(product_id, out_dir, lang))


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
    write_wds_search_results(
        search_wds_tables_for_cli(query, limit),
        output_format,
    )


@wds.command("metadata")
@click.argument("product_id")
@click.option("--out", "out_path", type=PATH, help="Optional JSON output path.")
def run_statcan_wds_metadata(product_id: str, out_path: Path | None) -> None:
    """Fetch WDS cube metadata by product ID."""
    metadata = fetch_wds_metadata(product_id)
    payload = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if out_path:
        out_path.write_text(payload)
        print_wrote(out_path)
    else:
        print(payload, end="")


@statcan.group(name="census-profile")
def census_profile() -> None:
    """Fetch Census Profile bulk downloads."""


@census_profile.command("fetch")
@click.option("--year", required=True, type=click.Choice(["2016"]))
@click.option("--geo-level", required=True)
@click.option("--out-dir", required=True, type=PATH)
def run_statcan_census_profile_fetch(year: str, geo_level: str, out_dir: Path) -> None:
    """Download a known Census Profile bulk CSV."""
    if year != "2016":
        raise ValueError("only the 2016 Census Profile registry is currently supported")
    print_wrote(fetch_census_profile_2016(geo_level, out_dir))


def search_wds_tables_for_cli(query: str, limit: int) -> list[dict[str, str]]:
    return [result.as_dict() for result in search_wds_tables(query, limit)]


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException("at least one column is required")
    return columns


if __name__ == "__main__":
    raise SystemExit(main())
