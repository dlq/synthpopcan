"""Microdata commands for the SynthPopCan CLI."""

from __future__ import annotations

__all__ = ["microdata"]

import csv
from pathlib import Path
from typing import Any

import click

from synthpopcan.cli_output import (
    click_file_access_error,
    click_value_error,
    parse_columns,
    print_seed_check_table,
    print_tree_column_suggestions_table,
    print_tree_geography_feasibility_table,
    split_columns,
    write_output,
    write_report,
)
from synthpopcan.console import print_summary_table, print_wrote
from synthpopcan.microdata import (
    SeedSample,
    build_tree_geography_feasibility_report,
    check_statcan_hierarchical_household_seed_columns,
    derive_statcan_hierarchical_household_seed_sample,
    export_seed_rows,
    export_training_rows,
    inspect_statcan_microdata,
    read_fixture_seed_sample,
    read_statcan_2016_individual_seed_sample,
    read_statcan_2021_individual_seed_sample,
    read_statcan_hierarchical_seed_sample,
    suggest_tree_column_blocks,
)

_PATH = click.Path(path_type=Path)
_HIERARCHICAL_FORMATS = [
    "statcan-2016-hierarchical",
    "statcan-2021-hierarchical",
]
_INDIVIDUAL_FORMATS = ["statcan-2016-individual", "statcan-2021-individual"]
_STATCAN_FORMATS = [*_HIERARCHICAL_FORMATS, *_INDIVIDUAL_FORMATS]


def _read_fixture_sample(
    path: Path,
    *,
    level: str | None,
    weight_column: str | None,
    geo_columns: str,
    id_columns: str,
) -> SeedSample:
    """Read a ``fixture-v1`` seed sample, requiring an explicit ``--level``."""

    if level is None:
        raise click.ClickException(
            "When --input-format fixture-v1 is used, pass "
            "--level household or --level person."
        )
    return read_fixture_seed_sample(
        path,
        level=level,  # type: ignore[arg-type]
        weight_column=weight_column,
        geography_columns=_parse_optional_columns(geo_columns),
        id_columns=_parse_optional_columns(id_columns),
    )


def _write_export_summary(
    summary: dict[str, Any],
    output_format: str,
    out_path: Path,
    title: str,
) -> None:
    """Write an export summary report, noting the output file for table output."""

    write_report(
        summary,
        output_format,
        lambda payload: print_summary_table(payload, title=title),
    )
    if output_format != "json":
        print_wrote(out_path)


def _read_statcan_sample(
    path: Path,
    *,
    source_format: str,
    columns: tuple[str, ...] | None = None,
) -> SeedSample:
    if source_format == "statcan-2016-individual":
        return read_statcan_2016_individual_seed_sample(path, columns=columns)
    if source_format == "statcan-2021-individual":
        return read_statcan_2021_individual_seed_sample(path, columns=columns)
    return read_statcan_hierarchical_seed_sample(
        path,
        source_format=source_format,
        columns=columns,
    )


@click.group(name="microdata")
def microdata() -> None:
    """Inspect and normalize census microdata seed samples."""


@microdata.command("inspect")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["fixture-v1", *_STATCAN_FORMATS]),
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
    "--geo-columns",
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
    geo_columns: str,
    id_columns: str,
    output_format: str,
) -> None:
    """Inspect a census microdata seed sample without printing rows."""
    try:
        if source_format == "fixture-v1":
            sample = _read_fixture_sample(
                path,
                level=level,
                weight_column=weight_column,
                geo_columns=geo_columns,
                id_columns=id_columns,
            )
        else:
            summary = inspect_statcan_microdata(path, source_format=source_format)
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    if source_format == "fixture-v1":
        summary = sample.as_summary()
    write_output(summary, output_format, title="Microdata Summary")


@microdata.command("check-seed")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    default="statcan-2016-hierarchical",
    type=click.Choice(_HIERARCHICAL_FORMATS),
    show_default=True,
    help="Hierarchical PUMF adapter format.",
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
    columns: str,
    output_format: str,
) -> None:
    """Check whether selected microdata columns can be exported as seed rows."""
    try:
        selected_columns = parse_columns(columns)
        sample = read_statcan_hierarchical_seed_sample(
            path,
            source_format=source_format,
            columns=selected_columns,
        )
        report = check_statcan_hierarchical_household_seed_columns(
            sample,
            columns=selected_columns,
        )
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    write_report(report, output_format, print_seed_check_table)


@microdata.command("suggest-tree-columns")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    default="statcan-2016-hierarchical",
    type=click.Choice(_HIERARCHICAL_FORMATS),
    show_default=True,
    help="Hierarchical PUMF adapter format.",
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
        sample = read_statcan_hierarchical_seed_sample(
            path,
            source_format=source_format,
        )
        report = suggest_tree_column_blocks(sample)
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    write_report(report, output_format, print_tree_column_suggestions_table)


@microdata.command("feasibility")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    default="statcan-2016-hierarchical",
    type=click.Choice(_HIERARCHICAL_FORMATS),
    show_default=True,
    help="Hierarchical PUMF adapter format.",
)
@click.option(
    "--geo-column",
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
@click.option(
    "--likely-person-rows",
    default=10_000,
    type=int,
    show_default=True,
    help="Person-row count that usually indicates adequate geography support.",
)
@click.option(
    "--likely-household-rows",
    default=4_000,
    type=int,
    show_default=True,
    help="Household-row count that usually indicates adequate geography support.",
)
@click.option(
    "--borderline-person-rows",
    default=2_500,
    type=int,
    show_default=True,
    help="Person-row count below which tree modelling is likely fragile.",
)
@click.option(
    "--borderline-household-rows",
    default=1_000,
    type=int,
    show_default=True,
    help="Household-row count below which tree modelling is likely fragile.",
)
@click.option(
    "--min-support",
    default=50.0,
    type=float,
    show_default=True,
    help="Minimum acceptable support for release-oriented model checks.",
)
@click.option(
    "--max-purity",
    default=0.95,
    type=float,
    show_default=True,
    help="Maximum acceptable dominant-outcome purity for release checks.",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["json", "table"]),
    show_default=True,
    help="Output format for the feasibility report.",
)
def tree_geography_feasibility(
    path: Path,
    source_format: str,
    geo_column: str,
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
        sample = read_statcan_hierarchical_seed_sample(
            path,
            source_format=source_format,
        )
        report = build_tree_geography_feasibility_report(
            sample,
            geography_column=geo_column,
            household_block=household_block,
            person_block=person_block,
            likely_person_rows=likely_person_rows,
            likely_household_rows=likely_household_rows,
            borderline_person_rows=borderline_person_rows,
            borderline_household_rows=borderline_household_rows,
            min_support=min_support,
            max_purity=max_purity,
        )
    except OSError as exc:
        raise click_file_access_error(path, "read", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc

    write_report(report, output_format, print_tree_geography_feasibility_table)


@microdata.command("export-seed")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    required=True,
    type=click.Choice(["fixture-v1", *_STATCAN_FORMATS]),
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
    "--geo-columns",
    default="",
    help="Comma-separated fixture geography columns.",
)
@click.option("--id-columns", default="", help="Comma-separated fixture ID columns.")
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output IPF seed CSV.",
)
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
    geo_columns: str,
    id_columns: str,
    out_path: Path,
    output_format: str,
) -> None:
    """Export selected microdata columns as an IPF seed CSV."""
    try:
        selected_columns = parse_columns(columns)
        if source_format == "fixture-v1":
            sample = _read_fixture_sample(
                path,
                level=level,
                weight_column=weight_column,
                geo_columns=geo_columns,
                id_columns=id_columns,
            )
        else:
            sample = _read_statcan_sample(
                path,
                source_format=source_format,
                columns=selected_columns,
            )
            if level == "household":
                if source_format in _INDIVIDUAL_FORMATS:
                    raise ValueError(
                        f"{source_format} cannot produce household seed rows"
                    )
                sample = derive_statcan_hierarchical_household_seed_sample(
                    sample,
                    columns=selected_columns,
                )
        rows, summary = export_seed_rows(sample, columns=selected_columns)
        write_rows(out_path, rows)
    except OSError as exc:
        raise click_file_access_error(exc.filename or path, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    _write_export_summary(summary, output_format, out_path, "Seed Export Summary")


@microdata.command("export-training")
@click.argument("path", type=_PATH)
@click.option(
    "--input-format",
    "source_format",
    default="statcan-2016-hierarchical",
    type=click.Choice(_STATCAN_FORMATS),
    show_default=True,
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
@click.option(
    "--out",
    "out_path",
    required=True,
    type=_PATH,
    help="Output tree-training CSV.",
)
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
        selected_targets = parse_columns(target_columns)
        selected_conditions = parse_columns(conditioning_columns)
        projected_columns = tuple(
            dict.fromkeys((*selected_conditions, *selected_targets))
        )
        sample = _read_statcan_sample(
            path,
            source_format=source_format,
            columns=projected_columns,
        )
        rows, summary = export_training_rows(
            sample,
            level=level,  # type: ignore[arg-type]
            target_columns=selected_targets,
            conditioning_columns=selected_conditions,
        )
        write_rows(out_path, rows)
    except OSError as exc:
        raise click_file_access_error(exc.filename or path, "access", exc) from exc
    except ValueError as exc:
        raise click_value_error(exc) from exc
    _write_export_summary(summary, output_format, out_path, "Training Export Summary")


def _parse_optional_columns(value: str) -> tuple[str, ...]:
    return split_columns(value)


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV output")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
