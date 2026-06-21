"""Command-line entry point for SynthPopCan."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from synthpopcan import __version__
from synthpopcan.ipf import IPFMargin, fit_ipf
from synthpopcan.statcan import (
    fetch_census_profile_2016,
    fetch_wds_metadata,
    fetch_wds_table,
    search_wds_tables,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synthpopcan",
        description="Canadian synthetic population tooling.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    ipf_parser = subparsers.add_parser("ipf", help="Run IPF workflows.")
    ipf_subparsers = ipf_parser.add_subparsers(dest="ipf_command")
    ipf_run = ipf_subparsers.add_parser("run", help="Fit seed records to controls.")
    ipf_run.add_argument("--seed", required=True, type=Path, help="Seed records CSV.")
    ipf_run.add_argument(
        "--controls",
        required=True,
        type=Path,
        help="Control totals CSV in long margin format.",
    )
    ipf_run.add_argument("--out", required=True, type=Path, help="Output weighted CSV.")
    ipf_run.add_argument(
        "--weight-field",
        default=None,
        help="Optional seed CSV column containing initial weights.",
    )
    ipf_run.add_argument("--max-iterations", default=100, type=int)
    ipf_run.add_argument("--tolerance", default=1e-6, type=float)
    ipf_run.set_defaults(func=run_ipf)

    statcan_parser = subparsers.add_parser(
        "statcan", help="Fetch Statistics Canada data."
    )
    statcan_subparsers = statcan_parser.add_subparsers(dest="statcan_command")

    wds_parser = statcan_subparsers.add_parser("wds", help="Fetch WDS table data.")
    wds_subparsers = wds_parser.add_subparsers(dest="wds_command")
    wds_fetch = wds_subparsers.add_parser(
        "fetch", help="Download a full WDS table CSV ZIP by product ID."
    )
    wds_fetch.add_argument("product_id", help="StatsCan WDS product/table ID.")
    wds_fetch.add_argument("--lang", default="en", choices=["en", "fr"])
    wds_fetch.add_argument("--out-dir", required=True, type=Path)
    wds_fetch.set_defaults(func=run_statcan_wds_fetch)
    wds_search = wds_subparsers.add_parser(
        "search", help="Search the WDS table inventory."
    )
    wds_search.add_argument("query", help="Search terms for table titles or IDs.")
    wds_search.add_argument("--limit", default=10, type=int)
    wds_search.add_argument(
        "--format",
        choices=["table", "tsv", "json"],
        default="table",
        help="Output format for search results.",
    )
    wds_search.set_defaults(func=run_statcan_wds_search)
    wds_metadata = wds_subparsers.add_parser(
        "metadata", help="Fetch WDS cube metadata by product ID."
    )
    wds_metadata.add_argument("product_id", help="StatsCan WDS product/table ID.")
    wds_metadata.add_argument("--out", type=Path, help="Optional JSON output path.")
    wds_metadata.set_defaults(func=run_statcan_wds_metadata)

    census_parser = statcan_subparsers.add_parser(
        "census-profile", help="Fetch Census Profile bulk downloads."
    )
    census_subparsers = census_parser.add_subparsers(dest="census_profile_command")
    census_fetch = census_subparsers.add_parser(
        "fetch", help="Download a known Census Profile bulk CSV."
    )
    census_fetch.add_argument("--year", required=True, choices=["2016"])
    census_fetch.add_argument("--geo-level", required=True)
    census_fetch.add_argument("--out-dir", required=True, type=Path)
    census_fetch.set_defaults(func=run_statcan_census_profile_fetch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
    return 0


def run_ipf(args: argparse.Namespace) -> None:
    seed_rows = read_csv(args.seed)
    margins = read_control_margins(args.controls)
    result = fit_ipf(
        seed_rows,
        margins,
        weight_field=args.weight_field,
        max_iterations=args.max_iterations,
        tolerance=args.tolerance,
    )
    write_weighted_seed(args.out, seed_rows, result.weights)


def run_statcan_wds_fetch(args: argparse.Namespace) -> None:
    fetch_wds_table(args.product_id, args.out_dir, args.lang)


def run_statcan_wds_search(args: argparse.Namespace) -> None:
    write_wds_search_results(
        search_wds_tables_for_cli(args.query, args.limit),
        args.format,
    )


def run_statcan_wds_metadata(args: argparse.Namespace) -> None:
    metadata = fetch_wds_metadata(args.product_id)
    payload = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(payload)
    else:
        print(payload, end="")


def run_statcan_census_profile_fetch(args: argparse.Namespace) -> None:
    if args.year != "2016":
        raise ValueError("only the 2016 Census Profile registry is currently supported")
    fetch_census_profile_2016(args.geo_level, args.out_dir)


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


def format_weight(weight: float) -> str:
    rounded = round(weight)
    if abs(weight - rounded) < 1e-9:
        return str(rounded)
    return f"{weight:.12g}"


if __name__ == "__main__":
    raise SystemExit(main())
