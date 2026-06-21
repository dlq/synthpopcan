"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from synthpopcan import __version__
from synthpopcan.census_microdata import (
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
)
from synthpopcan.controls import (
    read_category_mapping,
    read_control_margins,
    read_control_table,
    read_wds_control_table,
    write_control_table,
)
from synthpopcan.diagnostics import build_ipf_fit_report
from synthpopcan.ipf import fit_ipf, integerize_weights
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
def inspect_census_microdata(
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
    write_output(sample.as_summary(), output_format)


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


@cli.group()
def ipf() -> None:
    """Run IPF workflows."""


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
    result = fit_ipf(
        seed_rows,
        control_table.to_ipf_margins(),
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    if report_path:
        report_path.write_text(
            json.dumps(build_ipf_fit_report(control_table, result), indent=2) + "\n"
        )
    if not result.converged and not allow_nonconverged:
        raise click.ClickException(
            "IPF did not converge "
            f"after {result.iterations} iterations; "
            f"max absolute error is {result.max_abs_error:.12g}. "
            "Use --allow-nonconverged to write the fitted weights anyway."
        )
    write_weighted_seed(out_path, seed_rows, result.weights)


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
    fetch_wds_table(product_id, out_dir, lang)


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
    fetch_census_profile_2016(geo_level, out_dir)


def search_wds_tables_for_cli(query: str, limit: int) -> list[dict[str, str]]:
    return [result.as_dict() for result in search_wds_tables(query, limit)]


def write_output(payload: object, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, dict):
        table = Table()
        table.add_column("Field")
        table.add_column("Value")
        for key, value in payload.items():
            display_value = (
                json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            )
            table.add_row(str(key), display_value)
        Console().print(table)
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

    Console().print(table)


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
