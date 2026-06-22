"""Terminal output helpers for the SynthPopCan CLI."""

from __future__ import annotations

import csv
import json

from rich.table import Table

from synthpopcan.console import print_summary_table, print_table


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


def print_wds_metadata_explanation_table(summary: dict[str, object]) -> None:
    print_summary_table(
        {
            "product_id": summary.get("product_id", ""),
            "date_range": summary.get("date_range", ""),
            "dimensions": ", ".join(
                str(value) for value in summary.get("dimensions", [])
            ),
            "ipf_hint": summary.get("ipf_hint", ""),
        },
        title="StatCan WDS Table",
    )

    table = Table(title="Next Commands")
    table.add_column("Step", justify="right", no_wrap=True)
    table.add_column("Command")
    for index, command in enumerate(summary.get("next_commands", []), start=1):
        table.add_row(str(index), str(command))
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


def print_wds_inspection_table(report: dict[str, object]) -> None:
    print_summary_table(
        {
            "csv_member": report.get("csv_member", ""),
            "rows": report.get("row_count", ""),
            "columns": len(report.get("columns", [])),
            "count_candidates": ", ".join(
                str(value) for value in report.get("count_column_candidates", [])
            ),
        },
        title="WDS Table Inspection",
    )

    table = Table(title="Starter Normalization Settings")
    table.add_column("Setting", no_wrap=True)
    table.add_column("Value")
    table.add_row(
        "Dimensions",
        ", ".join(str(value) for value in report.get("dimension_candidates", [])),
    )
    table.add_row("Command", str(report.get("suggested_command", "")))
    print_table(table)


def print_tree_column_suggestions_table(report: dict[str, object]) -> None:
    table = Table(title="Tree Column Suggestions")
    table.add_column("Block")
    table.add_column("Level")
    table.add_column("Targets")
    table.add_column("Conditioning")
    table.add_column("Missing")

    for block in report.get("blocks", []):
        if not isinstance(block, dict):
            continue
        table.add_row(
            str(block.get("name", "")),
            str(block.get("level", "")),
            ", ".join(str(value) for value in block.get("target_columns", [])),
            ", ".join(str(value) for value in block.get("conditioning_columns", [])),
            ", ".join(str(value) for value in block.get("missing_target_columns", [])),
        )

    print_summary_table(
        {
            "source_format": report.get("source_format", ""),
            "geography_columns": ", ".join(
                str(value) for value in report.get("geography_columns", [])
            ),
            "excluded_columns": len(report.get("excluded_columns", [])),
        },
        title="Column Suggestion Summary",
    )
    print_table(table)


def print_tree_geography_feasibility_table(report: dict[str, object]) -> None:
    print_summary_table(
        {
            "source_format": report.get("source_format", ""),
            "geography_column": report.get("geography_column", ""),
            "regions": len(report.get("regions", [])),
        },
        title="Tree Geography Feasibility Summary",
    )

    table = Table(title="Tree Geography Feasibility")
    table.add_column("Geography", no_wrap=True)
    table.add_column("Tier", no_wrap=True)
    table.add_column("Persons", justify="right")
    table.add_column("Households", justify="right")
    table.add_column("Person Min Support", justify="right")
    table.add_column("Max Purity", justify="right")
    table.add_column("First Move")
    table.add_column("Aggregation Hint")

    for region in report.get("regions", []):
        if not isinstance(region, dict):
            continue
        model_design = region.get("model_design", {})
        if not isinstance(model_design, dict):
            model_design = {}
        table.add_row(
            str(region.get("geography", "")),
            str(region.get("tier", "")),
            format_report_number(region.get("person_rows")),
            format_report_number(region.get("household_rows")),
            format_report_number(region.get("person_min_support")),
            format_report_percent(region.get("person_max_purity")),
            first_model_design_move(model_design),
            str(model_design.get("aggregation_hint", "")),
        )

    print_table(table)


def first_model_design_move(model_design: dict[str, object]) -> str:
    strategy = str(model_design.get("block_strategy", ""))
    if strategy == "use_requested_blocks":
        return "train and audit requested blocks"
    if strategy == "start_with_reduced_blocks":
        return "start with reduced target set"
    if strategy == "minimal_or_aggregate":
        return "aggregate or use minimal targets"
    return strategy


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
    print_next_steps_table(report.get("suggested_next_steps", []))


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


def print_tree_output_validation_report_table(report: dict[str, object]) -> None:
    table = Table(title="Tree Output Distribution Check")
    table.add_column("Dimensions")
    table.add_column("Cells", justify="right")
    table.add_column("Training", justify="right")
    table.add_column("Generated", justify="right")
    table.add_column("Max Delta", justify="right")

    for row in report.get("comparisons", []):
        if not isinstance(row, dict):
            continue
        table.add_row(
            ", ".join(str(value) for value in row.get("dimensions", [])),
            format_report_number(len(row.get("cells", []))),
            format_report_number(row.get("training_total")),
            format_report_number(row.get("generated_total")),
            format_report_percent(row.get("max_abs_proportion_delta")),
        )

    print_summary_table(
        {
            "status": "Passed" if report.get("passed") else "Needs attention",
            "artifact_kind": report.get("artifact_kind", ""),
            "training_records": report.get("training_records", ""),
            "generated_records": report.get("generated_records", ""),
            "max_delta": format_report_percent(report.get("max_abs_proportion_delta")),
            "tolerance": format_report_percent(report.get("tolerance")),
        },
        title="Tree Output Validation Summary",
    )
    print_issues_table(report.get("issues", []), title="Tree Output Issues")
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


def print_next_steps_table(steps: object) -> None:
    if not isinstance(steps, list) or not steps:
        return
    table = Table(title="Next Steps")
    table.add_column("Step")
    for step in steps:
        table.add_row(str(step))
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
