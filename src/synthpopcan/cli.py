"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import click
from rich.table import Table

from synthpopcan import __version__
from synthpopcan.console import (
    print_checks_table,
    print_summary_table,
    print_table,
    print_wrote,
)
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
from synthpopcan.diagnostics import build_ipf_fit_report, build_ipf_input_report
from synthpopcan.ipf import fit_ipf, integerize_weights
from synthpopcan.localdata import inspect_local_data_layout
from synthpopcan.microdata import (
    check_statcan_2016_household_seed_columns,
    derive_statcan_2016_household_seed_sample,
    export_seed_rows,
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
)
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
from synthpopcan.validation import build_control_validation_report

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


@cli.group(name="microdata")
def microdata() -> None:
    """Inspect and normalize census microdata seed samples."""


@microdata.command("inspect")
@click.argument("path", type=PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["fixture-v1", "statcan-2016-hierarchical"]),
    help="Input microdata adapter format.",
)
@click.option(
    "--level",
    default=None,
    type=click.Choice(["household", "person"]),
    help="Seed sample level.",
)
@click.option("--weight-column", default=None, help="Optional weight column.")
@click.option(
    "--geography-columns",
    default="",
    help="Comma-separated geography columns.",
)
@click.option("--id-columns", default="", help="Comma-separated ID columns.")
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the inspection summary.",
)
def inspect_microdata(
    path: Path,
    source_format: str,
    level: str,
    weight_column: str | None,
    geography_columns: str,
    id_columns: str,
    output_format: str,
) -> None:
    """Inspect a census microdata seed sample without printing rows."""
    try:
        if source_format == "fixture-v1":
            if level is None:
                raise click.ClickException("fixture-v1 requires --level")
            sample = read_fixture_seed_sample(
                path,
                level=level,
                weight_column=weight_column,
                geography_columns=parse_optional_columns(geography_columns),
                id_columns=parse_optional_columns(id_columns),
            )
        else:
            sample = read_statcan_2016_hierarchical_seed_sample(path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_output(sample.as_summary(), output_format, title="Microdata Summary")


@microdata.command("check-seed")
@click.argument("path", type=PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["statcan-2016-hierarchical"]),
    help="Input microdata adapter format.",
)
@click.option(
    "--level",
    required=True,
    type=click.Choice(["household"]),
    help="Seed sample level to check.",
)
@click.option(
    "--columns",
    required=True,
    help="Comma-separated columns to include as seed attributes.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the seed check.",
)
def check_microdata_seed(
    path: Path,
    source_format: str,
    level: str,
    columns: str,
    output_format: str,
) -> None:
    """Check whether selected microdata columns can be exported as seed rows."""
    try:
        selected_columns = parse_columns(columns)
        sample = read_statcan_2016_hierarchical_seed_sample(path)
        report = check_statcan_2016_household_seed_columns(
            sample,
            columns=selected_columns,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_seed_check_table(report)


@microdata.command("export-seed")
@click.argument("path", type=PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["fixture-v1", "statcan-2016-hierarchical"]),
    help="Input microdata adapter format.",
)
@click.option(
    "--level",
    default=None,
    type=click.Choice(["household", "person"]),
    help="Seed sample level for fixture-v1.",
)
@click.option(
    "--columns",
    required=True,
    help="Comma-separated columns to include as seed attributes.",
)
@click.option("--weight-column", default=None, help="Optional fixture weight column.")
@click.option(
    "--geography-columns",
    default="",
    help="Comma-separated fixture geography columns.",
)
@click.option("--id-columns", default="", help="Comma-separated fixture ID columns.")
@click.option("--out", "out_path", required=True, type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the export summary.",
)
def export_microdata_seed(
    path: Path,
    source_format: str,
    level: str | None,
    columns: str,
    weight_column: str | None,
    geography_columns: str,
    id_columns: str,
    out_path: Path,
    output_format: str,
) -> None:
    """Export selected microdata columns as an IPF seed CSV."""
    try:
        selected_columns = parse_columns(columns)
        if source_format == "fixture-v1":
            if level is None:
                raise click.ClickException("fixture-v1 requires --level")
            sample = read_fixture_seed_sample(
                path,
                level=level,
                weight_column=weight_column,
                geography_columns=parse_optional_columns(geography_columns),
                id_columns=parse_optional_columns(id_columns),
            )
        else:
            sample = read_statcan_2016_hierarchical_seed_sample(path)
            if level == "household":
                sample = derive_statcan_2016_household_seed_sample(
                    sample,
                    columns=selected_columns,
                )
        rows, summary = export_seed_rows(sample, columns=selected_columns)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_rows(out_path, rows)
    if output_format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print_summary_table(summary, title="Seed Export Summary")
    print_wrote(out_path)


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
def ipf() -> None:
    """Run IPF workflows."""


@ipf.command("check-inputs")
@click.option("--seed", "seed_path", required=True, type=PATH, help="Seed records CSV.")
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def check_ipf_inputs(
    seed_path: Path,
    controls_path: Path,
    output_format: str,
) -> None:
    """Check whether seed records cover the control dimensions and categories."""
    seed_rows = read_csv(seed_path)
    control_table = read_control_table(controls_path)
    report = build_ipf_input_report(seed_rows, control_table)
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_ipf_input_check_table(report)


@ipf.command("fit")
@click.option("--seed", "seed_path", required=True, type=PATH, help="Seed records CSV.")
@click.option(
    "--controls",
    "controls_path",
    required=True,
    type=PATH,
    help="Control totals CSV in long margin format.",
)
@click.option(
    "--out", "out_path", required=True, type=PATH, help="Output weighted CSV."
)
@click.option(
    "--weight-field",
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
@click.option("--report", "report_path", type=PATH, help="Optional JSON fit report.")
def fit_ipf_command(
    seed_path: Path,
    controls_path: Path,
    out_path: Path,
    weight_field: str | None,
    max_iterations: int,
    tolerance: float,
    allow_nonconverged: bool,
    report_path: Path | None,
) -> None:
    """Fit seed records to controls and write compact weights."""
    seed_rows = read_csv(seed_path)
    control_table = read_control_table(controls_path)
    try:
        result = fit_ipf(
            seed_rows,
            control_table.to_ipf_margins(),
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    except ValueError as exc:
        raise click.ClickException(format_fit_value_error(exc)) from exc
    report = build_ipf_fit_report(control_table, result)
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    if not result.converged and not allow_nonconverged:
        raise click.ClickException(format_nonconvergence_message(report))
    write_weighted_seed(out_path, seed_rows, result.weights)
    if report_path:
        print_wrote(report_path)
    print_wrote(out_path)


@ipf.command("expand")
@click.option(
    "--weights",
    "weights_path",
    required=True,
    type=PATH,
    help="Fitted seed weights CSV from ipf fit.",
)
@click.option(
    "--out", "out_path", required=True, type=PATH, help="Output synthetic CSV."
)
@click.option(
    "--weight-field",
    default="weight",
    show_default=True,
    help="Column containing fitted weights.",
)
def expand_ipf(weights_path: Path, out_path: Path, weight_field: str) -> None:
    """Expand fitted weights into full synthetic rows."""
    seed_rows, weights = read_weighted_seed(weights_path, weight_field)
    write_expanded_seed(out_path, seed_rows, weights)
    print_wrote(out_path)


@ipf.command("report")
@click.argument("path", type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def report_ipf(path: Path, output_format: str) -> None:
    """Print a fit report summary from ipf fit --report JSON."""
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"{path} is not valid JSON") from exc
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_ipf_report_table(report)


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


def write_output(
    payload: object, output_format: str, *, title: str | None = None
) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, dict):
        print_summary_table(payload, title=title)
        return
    print(payload)


def write_wds_search_results(rows: list[dict[str, str]], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    if output_format == "tsv":
        write_wds_search_tsv(rows)
        return
    write_wds_search_table(rows)


def write_wds_search_tsv(rows: list[dict[str, str]]) -> None:
    fieldnames = ["product_id", "cansim_id", "start_date", "end_date", "title_en"]
    writer = csv.DictWriter(
        _StdoutWriter(),
        fieldnames=fieldnames,
        delimiter="\t",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)


def write_wds_search_table(rows: list[dict[str, str]]) -> None:
    table = Table(title="StatCan WDS Tables")
    table.add_column("Product ID", no_wrap=True)
    table.add_column("CANSIM ID", no_wrap=True)
    table.add_column("Date Range", no_wrap=True)
    table.add_column("Title")

    for row in rows:
        table.add_row(
            row.get("product_id", ""),
            row.get("cansim_id", ""),
            format_date_range(row.get("start_date", ""), row.get("end_date", "")),
            row.get("title_en", ""),
        )

    print_table(table)


def print_census_profile_characteristics_table(rows: list[dict[str, str]]) -> None:
    table = Table(title="Census Profile Characteristics")
    table.add_column("Characteristic")
    table.add_column("Example Count", justify="right")
    table.add_column("Rows", justify="right")
    for row in rows:
        table.add_row(
            row.get("characteristic", ""),
            row.get("example_count", ""),
            row.get("rows", ""),
        )
    print_table(table)


def print_ipf_report_table(report: dict[str, object]) -> None:
    table = Table(title="IPF Fit Report")
    table.add_column("Margin")
    table.add_column("Dimensions")
    table.add_column("Cells", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Fitted", justify="right")
    table.add_column("Max Error", justify="right")
    table.add_column("Max Rel. Error", justify="right")

    for row in report.get("margin_summaries", []):
        if not isinstance(row, dict):
            continue
        table.add_row(
            str(row.get("name", "")),
            ", ".join(str(value) for value in row.get("dimensions", [])),
            format_report_number(row.get("cells")),
            format_report_number(row.get("target_total")),
            format_report_number(row.get("fitted_total")),
            format_report_number(row.get("max_abs_error")),
            format_report_percent(row.get("max_relative_error")),
        )

    print_summary_table(
        {
            "status": "Converged" if report.get("converged") else "Not converged",
            "iterations": report.get("iterations", ""),
            "seed_records": report.get("seed_records", ""),
            "max_abs_error": format_report_number(report.get("max_abs_error")),
        },
        title="IPF Fit Summary",
    )
    print_issues_table(report.get("issues", []), title="Fit Issues")
    print_table(table)


def print_ipf_input_check_table(report: dict[str, object]) -> None:
    print_summary_table(
        {
            "status": "Passed" if report.get("passed") else "Needs attention",
            "seed_records": report.get("seed_records", ""),
            "control_margins": report.get("control_margins", ""),
            "unsupported_cells": len(report.get("unsupported_cells", [])),
        },
        title="IPF Input Summary",
    )

    table = Table(title="IPF Input Check")
    table.add_column("Dimension", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Seed Column", no_wrap=True)
    table.add_column("Miss")
    table.add_column("Unused")
    table.add_column("Detail", no_wrap=True)
    for row in report.get("dimensions", []):
        if not isinstance(row, dict):
            continue
        status = "OK" if row.get("status") == "ok" else "Problem"
        if row.get("seed_column") == "missing":
            seed_column = "Missing column"
        else:
            seed_column = "Found"
        table.add_row(
            str(row.get("dimension", "")),
            status,
            seed_column,
            ", ".join(str(value) for value in row.get("missing_categories", [])),
            ", ".join(str(value) for value in row.get("unused_seed_categories", [])),
            str(row.get("detail", "")),
        )
    print_table(table)


def print_validation_report_table(report: dict[str, object]) -> None:
    table = Table(title="Control Validation")
    table.add_column("Margin")
    table.add_column("Dimensions")
    table.add_column("Cells", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Max Error", justify="right")
    table.add_column("Max Rel. Error", justify="right")

    for row in report.get("margin_summaries", []):
        if not isinstance(row, dict):
            continue
        table.add_row(
            str(row.get("name", "")),
            ", ".join(str(value) for value in row.get("dimensions", [])),
            format_report_number(row.get("cells")),
            format_report_number(row.get("target_total")),
            format_report_number(row.get("actual_total")),
            format_report_number(row.get("max_abs_error")),
            format_report_percent(row.get("max_relative_error")),
        )

    print_summary_table(
        {
            "status": "Passed" if report.get("passed") else "Failed",
            "artifact_kind": report.get("artifact_kind", ""),
            "population_records": report.get("population_records", ""),
            "max_abs_error": format_report_number(report.get("max_abs_error")),
            "tolerance": format_report_number(report.get("tolerance")),
        },
        title="Validation Summary",
    )
    print_issues_table(report.get("issues", []), title="Validation Issues")
    print_table(table)


def print_seed_check_table(report: dict[str, object]) -> None:
    print_summary_table(
        {
            "status": "Passed" if report.get("passed") else "Needs attention",
            "source_format": report.get("source_format", ""),
            "level": report.get("level", ""),
            "households": report.get("households", ""),
            "people": report.get("people", ""),
        },
        title="Seed Check Summary",
    )

    table = Table(title="Seed Column Check")
    table.add_column("Column", no_wrap=True)
    table.add_column("Role", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail")
    for row in report.get("checks", []):
        if not isinstance(row, dict):
            continue
        status = "OK" if row.get("status") == "ok" else "Problem"
        role = str(row.get("role", ""))
        if role == "selected household column":
            role = "household column"
        table.add_row(
            str(row.get("column", "")),
            role,
            status,
            str(row.get("detail", "")),
        )
    print_table(table)


def print_issues_table(issues: object, *, title: str) -> None:
    if not isinstance(issues, list) or not issues:
        return
    table = Table(title=title)
    table.add_column("Severity")
    table.add_column("Margin")
    table.add_column("Problem")
    table.add_column("Tip")
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        table.add_row(
            str(issue.get("severity", "")),
            str(issue.get("margin", "")),
            str(issue.get("message", "")),
            str(issue.get("tip", "")),
        )
    print_table(table)


def format_nonconvergence_message(report: dict[str, object]) -> str:
    message = (
        "IPF did not converge "
        f"after {format_report_number(report.get('iterations'))} iterations; "
        f"max absolute error is {format_report_number(report.get('max_abs_error'))}."
    )
    issue = first_report_issue(report)
    if issue is not None:
        message = f"{message} {issue.get('message', '')} {issue.get('tip', '')}"
    return f"{message} Use --allow-nonconverged to write the fitted weights anyway."


def first_report_issue(report: dict[str, object]) -> dict[str, object] | None:
    issues = report.get("issues", [])
    if not isinstance(issues, list) or not issues:
        return None
    issue = issues[0]
    return issue if isinstance(issue, dict) else None


def format_fit_value_error(exc: ValueError) -> str:
    message = str(exc)
    if "has no seed records" in message:
        return (
            "Seed records do not cover a positive control cell. "
            f"{message}. Add seed rows for that category, use a broader seed "
            "sample, or remap/drop zero-support control categories."
        )
    return message


def format_report_number(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        rounded = round(value)
        if abs(value - rounded) < 1e-9:
            return f"{rounded:,}"
        return f"{value:.6g}"
    return str(value) if value is not None else ""


def format_report_percent(value: object) -> str:
    if not isinstance(value, int | float):
        return ""
    if value == float("inf"):
        return "inf"
    return f"{value * 100:.6g}%"


def format_date_range(start_date: str, end_date: str) -> str:
    start = start_date[:10]
    end = end_date[:10]
    if start and start == end:
        return start
    return f"{start} to {end}".strip()


class _StdoutWriter:
    def write(self, value: str) -> int:
        print(value, end="")
        return len(value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException("at least one column is required")
    return columns


def parse_optional_columns(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def read_weighted_seed(
    path: Path, weight_field: str
) -> tuple[list[dict[str, str]], list[float]]:
    rows: list[dict[str, str]] = []
    weights: list[float] = []
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            selected_weight_field = (
                "fitted_weight"
                if weight_field == "weight" and "fitted_weight" in row
                else weight_field
            )
            try:
                weight_value = row.pop(selected_weight_field)
            except KeyError as exc:
                raise ValueError(
                    f"weights CSV requires a {weight_field!r} column"
                ) from exc
            try:
                weights.append(float(weight_value))
            except ValueError as exc:
                raise ValueError(
                    f"weights row {row_number} has invalid weight"
                ) from exc
            rows.append(row)
    return rows, weights


def read_population_artifact(
    path: Path,
    artifact_kind: str,
    weight_field: str,
) -> tuple[list[dict[str, str]], list[float]]:
    if artifact_kind == "weights":
        return read_weighted_seed(path, weight_field)
    if artifact_kind == "expanded":
        rows = read_csv(path)
        return rows, [1.0 for _row in rows]
    raise ValueError(f"unknown population artifact kind {artifact_kind!r}")


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV output")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_weighted_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> None:
    if not rows:
        raise ValueError("cannot write weighted output for empty seed rows")
    weight_column = "weight" if "weight" not in rows[0] else "fitted_weight"
    fieldnames = [*rows[0].keys(), weight_column]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row, weight in zip(rows, weights, strict=True):
            writer.writerow({**row, weight_column: format_weight(weight)})


def write_expanded_seed(
    path: Path, rows: list[dict[str, str]], weights: list[float]
) -> None:
    counts = integerize_weights(weights)
    if sum(counts) == 0:
        raise ValueError("expanded synthetic population is empty")
    fieldnames = [
        "synthetic_id",
        "seed_id",
        *(field for field in rows[0] if field != "id"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        synthetic_id = 1
        for source_index, row in enumerate(rows, start=1):
            seed_id = str(row.get("id", source_index))
            attributes = {key: value for key, value in row.items() if key != "id"}
            for _ in range(counts[source_index - 1]):
                writer.writerow(
                    {
                        "synthetic_id": str(synthetic_id),
                        "seed_id": seed_id,
                        **attributes,
                    }
                )
                synthetic_id += 1


def format_weight(weight: float) -> str:
    rounded = round(weight)
    if abs(weight - rounded) < 1e-9:
        return str(rounded)
    return f"{weight:.12g}"


if __name__ == "__main__":
    raise SystemExit(main())
