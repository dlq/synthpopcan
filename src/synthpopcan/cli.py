"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import click

from synthpopcan import __version__
from synthpopcan.cli_microdata import microdata
from synthpopcan.cli_output import (
    format_fit_value_error,
    format_nonconvergence_message,
    format_report_number,
    print_census_profile_characteristics_table,
    print_ipf_input_check_table,
    print_ipf_report_table,
    print_validation_report_table,
    write_output,
    write_wds_search_results,
)
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
from synthpopcan.diagnostics import build_ipf_fit_report, build_ipf_input_report
from synthpopcan.ipf import fit_ipf, integerize_weights
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


cli.add_command(microdata)


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


@cli.group()
def tree() -> None:
    """Tree-based synthetic population generator."""


@tree.command("train")
def train_tree_generator() -> None:
    """Train a tree-based generator model."""
    raise click.ClickException(
        "Tree generator training is not implemented yet. "
        "Use the IPF workflow while the tree prototype contract is being defined."
    )


@tree.command("generate")
def generate_tree_population() -> None:
    """Generate synthetic rows from a trained tree-based model."""
    raise click.ClickException(
        "Tree generator output is not implemented yet. "
        "Use the IPF workflow while the tree prototype contract is being defined."
    )


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException("at least one column is required")
    return columns


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
