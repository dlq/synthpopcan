"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from synthpopcan import __version__
from synthpopcan.ipf import IPFMargin, expand_records, fit_ipf
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
def controls() -> None:
    """Normalize and validate IPF control tables."""


@controls.command("validate")
@click.argument("path", type=PATH)
def validate_controls(path: Path) -> None:
    """Validate a normalized long control CSV."""
    read_control_margins(path)


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
def fit_ipf_command(
    seed_path: Path,
    controls_path: Path,
    out_path: Path,
    weight_field: str | None,
    max_iterations: int,
    tolerance: float,
) -> None:
    """Fit seed records to controls and write compact weights."""
    seed_rows = read_csv(seed_path)
    margins = read_control_margins(controls_path)
    result = fit_ipf(
        seed_rows,
        margins,
        weight_field=weight_field,
        max_iterations=max_iterations,
        tolerance=tolerance,
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
    table = Table(title="StatsCan WDS Tables")
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


def read_weighted_seed(
    path: Path, weight_field: str
) -> tuple[list[dict[str, str]], list[float]]:
    rows: list[dict[str, str]] = []
    weights: list[float] = []
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                weight_value = row.pop(weight_field)
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


def read_control_margins(path: Path) -> list[IPFMargin]:
    grouped: dict[tuple[str, ...], dict[tuple[str, ...], float]] = {}
    with path.open(newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            dimensions = parse_dimensions(row.get("dimensions", ""))
            if not dimensions:
                raise ValueError(f"controls row {row_number} has no dimensions")
            try:
                count = float(row["count"])
            except KeyError as exc:
                raise ValueError("controls CSV requires a count column") from exc
            except ValueError as exc:
                raise ValueError(
                    f"controls row {row_number} has invalid count"
                ) from exc

            key = tuple(row.get(dimension, "") for dimension in dimensions)
            grouped.setdefault(dimensions, {})[key] = count

    return [IPFMargin(dimensions, targets) for dimensions, targets in grouped.items()]


def parse_dimensions(value: str) -> tuple[str, ...]:
    separator = "|" if "|" in value else ","
    return tuple(part.strip() for part in value.split(separator) if part.strip())


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
    expanded = expand_records(rows, weights)
    if not expanded:
        raise ValueError("expanded synthetic population is empty")
    fieldnames = list(expanded[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(expanded)


def format_weight(weight: float) -> str:
    rounded = round(weight)
    if abs(weight - rounded) < 1e-9:
        return str(rounded)
    return f"{weight:.12g}"


if __name__ == "__main__":
    raise SystemExit(main())
