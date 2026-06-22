"""Microdata commands for the SynthPopCan CLI."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from synthpopcan.cli_output import (
    print_seed_check_table,
    print_tree_column_suggestions_table,
    print_tree_geography_feasibility_table,
    write_output,
)
from synthpopcan.console import print_summary_table, print_wrote
from synthpopcan.microdata import (
    build_tree_geography_feasibility_report,
    check_statcan_2016_household_seed_columns,
    derive_statcan_2016_household_seed_sample,
    export_seed_rows,
    export_training_rows,
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
    suggest_tree_column_blocks,
)

PATH = click.Path(path_type=Path)


@click.group(name="microdata")
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


@microdata.command("suggest-tree-columns")
@click.argument("path", type=PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["statcan-2016-hierarchical"]),
    help="Input microdata adapter format.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the suggestions.",
)
def suggest_microdata_tree_columns(
    path: Path,
    source_format: str,
    output_format: str,
) -> None:
    """Suggest broad tree-model column blocks from known microdata columns."""
    try:
        sample = read_statcan_2016_hierarchical_seed_sample(path)
        report = suggest_tree_column_blocks(sample)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_tree_column_suggestions_table(report)


@microdata.command("tree-geography-feasibility")
@click.argument("path", type=PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["statcan-2016-hierarchical"]),
    help="Input microdata adapter format.",
)
@click.option(
    "--geography-column",
    default="PR",
    show_default=True,
    help="Geography column to evaluate, such as PR or CMA.",
)
@click.option(
    "--household-block",
    default="household_core",
    show_default=True,
    help="Suggested household block to evaluate.",
)
@click.option(
    "--person-block",
    default="person_demographics",
    show_default=True,
    help="Suggested person block to evaluate.",
)
@click.option("--likely-person-rows", default=10_000, type=int, show_default=True)
@click.option("--likely-household-rows", default=4_000, type=int, show_default=True)
@click.option("--borderline-person-rows", default=2_500, type=int, show_default=True)
@click.option("--borderline-household-rows", default=1_000, type=int, show_default=True)
@click.option("--min-support", default=50.0, type=float, show_default=True)
@click.option("--max-purity", default=0.95, type=float, show_default=True)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
)
def tree_geography_feasibility(
    path: Path,
    source_format: str,
    geography_column: str,
    household_block: str,
    person_block: str,
    likely_person_rows: int,
    likely_household_rows: int,
    borderline_person_rows: int,
    borderline_household_rows: int,
    min_support: float,
    max_purity: float,
    output_format: str,
) -> None:
    """Estimate which geographies are plausible for publishable tree models."""
    try:
        sample = read_statcan_2016_hierarchical_seed_sample(path)
        report = build_tree_geography_feasibility_report(
            sample,
            geography_column=geography_column,
            household_block=household_block,
            person_block=person_block,
            likely_person_rows=likely_person_rows,
            likely_household_rows=likely_household_rows,
            borderline_person_rows=borderline_person_rows,
            borderline_household_rows=borderline_household_rows,
            min_support=min_support,
            max_purity=max_purity,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print_tree_geography_feasibility_table(report)


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


@microdata.command("export-training")
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
    type=click.Choice(["household", "person"]),
    help="Training row level.",
)
@click.option(
    "--target-columns",
    required=True,
    help="Comma-separated columns the tree model should generate.",
)
@click.option(
    "--conditioning-columns",
    required=True,
    help="Comma-separated columns used to condition tree generation.",
)
@click.option("--out", "out_path", required=True, type=PATH)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the export summary.",
)
def export_microdata_training(
    path: Path,
    source_format: str,
    level: str,
    target_columns: str,
    conditioning_columns: str,
    out_path: Path,
    output_format: str,
) -> None:
    """Export selected microdata columns as tree training rows."""
    try:
        sample = read_statcan_2016_hierarchical_seed_sample(path)
        rows, summary = export_training_rows(
            sample,
            level=level,  # type: ignore[arg-type]
            target_columns=parse_columns(target_columns),
            conditioning_columns=parse_columns(conditioning_columns),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    write_rows(out_path, rows)
    if output_format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return
    print_summary_table(summary, title="Training Export Summary")
    print_wrote(out_path)


def parse_columns(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(",") if part.strip())
    if not columns:
        raise click.ClickException("at least one column is required")
    return columns


def parse_optional_columns(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV output")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
