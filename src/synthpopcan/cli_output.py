"""Terminal output helpers for the SynthPopCan CLI."""

from __future__ import annotations

import csv
import json

from rich.table import Table

from synthpopcan.console import print_summary_table, print_table

__all__ = [
    "format_file_access_error",
    "format_fit_value_error",
    "format_nonconvergence_message",
    "format_report_number",
    "format_report_percent",
    "print_census_profile_characteristics_table",
    "print_ipf_control_suggestions_table",
    "print_ipf_input_check_table",
    "print_ipf_report_table",
    "print_seed_check_table",
    "print_tree_column_suggestions_table",
    "print_tree_geography_feasibility_table",
    "print_tree_output_validation_report_table",
    "print_validation_report_table",
    "print_wds_inspection_table",
    "print_wds_metadata_explanation_table",
    "write_output",
    "write_wds_search_results",
]


def format_file_access_error(path: object, action: str, exc: OSError) -> str:
    """Build a friendly CLI message for input/output file access failures."""

    reason = getattr(exc, "strerror", None) or str(exc)
    return (
        f"Could not {action} {path}: {reason}. "
        "Check that the path is correct and that SynthPopCan has permission "
        "to access it."
    )


def write_output(
    payload: object, output_format: str, *, title: str | None = None
) -> None:
    """Write a JSON payload or render a compact human-readable table."""

    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, dict):
        print_summary_table(payload, title=title)
        return
    print(payload)


def write_wds_search_results(rows: list[dict[str, str]], output_format: str) -> None:
    """Render WDS search results in table, TSV, or JSON form."""

    if output_format == "json":
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    if output_format == "tsv":
        _write_wds_search_tsv(rows)
        return
    _write_wds_search_table(rows)


def _write_wds_search_tsv(rows: list[dict[str, str]]) -> None:
    """Write WDS search rows as a script-friendly tab-separated table."""

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


def _write_wds_search_table(rows: list[dict[str, str]]) -> None:
    """Render WDS search rows as a readable terminal table."""

    table = Table(title="StatCan WDS Tables")
    table.add_column("Product ID", no_wrap=True)
    table.add_column("CANSIM ID", no_wrap=True)
    table.add_column("Date Range", no_wrap=True)
    table.add_column("Title")

    for row in rows:
        table.add_row(
            row.get("product_id", ""),
            row.get("cansim_id", ""),
            _format_date_range(row.get("start_date", ""), row.get("end_date", "")),
            row.get("title_en", ""),
        )

    print_table(table)


def print_wds_metadata_explanation_table(summary: dict[str, object]) -> None:
    """Render a WDS product summary with dimension previews and next commands."""

    print_summary_table(
        {
            "product_id": summary.get("product_id", ""),
            "date_range": summary.get("date_range", ""),
            "dimensions": ", ".join(
                str(value) for value in summary.get("dimensions", [])
            ),
            "suitability": _wds_suitability_label(
                summary.get("ipf_suitability", {})
            ),
            "ipf_hint": summary.get("ipf_hint", ""),
        },
        title="StatCan WDS Table",
    )

    _print_wds_dimension_preview_table(summary.get("dimension_previews", []))

    table = Table(title="Next Commands")
    table.add_column("Step", justify="right", no_wrap=True)
    table.add_column("Command")
    for index, command in enumerate(summary.get("next_commands", []), start=1):
        table.add_row(str(index), str(command))
    print_table(table)


def _wds_suitability_label(value: object) -> str:
    """Convert a WDS suitability status object into a short user-facing label."""

    if not isinstance(value, dict):
        return ""
    status = value.get("status")
    if status == "likely_age_sex_controls":
        return "Likely age/sex controls"
    if status == "possible_totals_only":
        return "Possible totals only"
    if status == "unclear":
        return "Unclear"
    return str(status or "")


def _print_wds_dimension_preview_table(previews: object) -> None:
    """Render short member previews for each WDS dimension when available."""

    if not isinstance(previews, list) or not previews:
        return

    table = Table(title="Dimension Preview")
    table.add_column("Dimension", no_wrap=True)
    table.add_column("Members")
    table.add_column("Total", justify="right", no_wrap=True)

    for preview in previews:
        if not isinstance(preview, dict):
            continue
        members = preview.get("members", [])
        member_text = ""
        if isinstance(members, list):
            member_text = ", ".join(str(member) for member in members)
        if preview.get("truncated"):
            member_text = f"{member_text}, ..." if member_text else "..."
        table.add_row(
            str(preview.get("name", "")),
            member_text,
            str(preview.get("member_count", "")),
        )

    print_table(table)


def print_census_profile_characteristics_table(rows: list[dict[str, str]]) -> None:
    """Render Census Profile characteristic counts for mapping inspection."""

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
    """Render local WDS ZIP inspection results and starter normalization hints."""

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
    """Render suggested household/person column blocks for tree workflows."""

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
    """Render geography-level model-design feasibility advice."""

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
            _first_model_design_move(model_design),
            str(model_design.get("aggregation_hint", "")),
        )

    print_table(table)


def _first_model_design_move(model_design: dict[str, object]) -> str:
    """Return the first actionable model-design move from an advisor payload."""

    strategy = str(model_design.get("block_strategy", ""))
    if strategy == "use_requested_blocks":
        return "train and audit requested blocks"
    if strategy == "start_with_reduced_blocks":
        return "start with reduced target set"
    if strategy == "minimal_or_aggregate":
        return "aggregate or use minimal targets"
    return strategy


def print_ipf_report_table(report: dict[str, object]) -> None:
    """Render an IPF fit report with summary, issues, next steps, and margins."""

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
    _print_issues_table(report.get("issues", []), title="Fit Issues")
    _print_next_steps_table(report.get("suggested_next_steps", []))
    print_table(table)


def print_ipf_input_check_table(report: dict[str, object]) -> None:
    """Render seed/control compatibility checks before fitting IPF."""

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
            seed_column = "Needs enrichment"
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
    _print_next_steps_table(report.get("suggested_next_steps", []))


def print_ipf_control_suggestions_table(report: dict[str, object]) -> None:
    """Render suggested StatCan control directions for generated or seed rows."""

    print_summary_table(
        {
            "unit": report.get("unit", ""),
            "seed_records": report.get("seed_records", ""),
            "columns": len(report.get("available_columns", [])),
            "geography_columns": ", ".join(
                str(value) for value in report.get("geography_columns", [])
            ),
        },
        title="IPF Control Suggestion Summary",
    )

    table = Table(title="IPF Control Suggestions")
    table.add_column("Column", no_wrap=True)
    table.add_column("Decision", no_wrap=True)
    table.add_column("Search Terms")
    table.add_column("Why It Matters")
    for row in report.get("usable_controls", []):
        if not isinstance(row, dict):
            continue
        table.add_row(
            str(row.get("column", "")),
            "Use now",
            str(row.get("statcan_search", "")),
            _control_suggestion_note(row, "Review categories before IPF."),
        )
    for row in report.get("enrichment_candidates", []):
        if not isinstance(row, dict):
            continue
        table.add_row(
            str(row.get("column", "")),
            "Add first",
            str(row.get("statcan_search", "")),
            _control_suggestion_note(row, "Add this column before IPF."),
        )
    print_table(table)
    _print_next_steps_table(report.get("next_commands", []))


def _control_suggestion_note(row: dict[str, object], default_next_step: str) -> str:
    """Combine the role and reason into one readable control-suggestion note."""

    role = str(row.get("role", "")).strip()
    reason = str(row.get("reason", "")).strip()
    if role and reason:
        return f"{role}: {reason} {default_next_step}"
    if reason:
        return f"{reason} {default_next_step}"
    return default_next_step


def print_validation_report_table(report: dict[str, object]) -> None:
    """Render control-validation results for weighted or expanded populations."""

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
    _print_issues_table(report.get("issues", []), title="Validation Issues")
    print_table(table)


def print_tree_output_validation_report_table(report: dict[str, object]) -> None:
    """Render generated tree-output distribution checks against training rows."""

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
    _print_issues_table(report.get("issues", []), title="Tree Output Issues")
    print_table(table)


def print_seed_check_table(report: dict[str, object]) -> None:
    """Render microdata seed-column checks for household-level exports."""

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


def _print_issues_table(issues: object, *, title: str) -> None:
    """Render issue dictionaries when a report includes problems or warnings."""

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


def _print_next_steps_table(steps: object) -> None:
    """Render plain-language next steps when a report can suggest them."""

    if not isinstance(steps, list) or not steps:
        return
    table = Table(title="Next Steps")
    table.add_column("Step")
    for step in steps:
        table.add_row(str(step))
    print_table(table)


def format_nonconvergence_message(report: dict[str, object]) -> str:
    """Build the terminal error shown when IPF stops before convergence."""

    message = (
        "IPF did not converge "
        f"after {format_report_number(report.get('iterations'))} iterations; "
        f"max absolute error is {format_report_number(report.get('max_abs_error'))}."
    )
    issue = _first_report_issue(report)
    if issue is not None:
        message = f"{message} {issue.get('message', '')} {issue.get('tip', '')}"
    return f"{message} Use --allow-nonconverged to write the fitted weights anyway."


def _first_report_issue(report: dict[str, object]) -> dict[str, object] | None:
    """Return the first structured issue from a report, if one exists."""

    issues = report.get("issues", [])
    if not isinstance(issues, list) or not issues:
        return None
    issue = issues[0]
    return issue if isinstance(issue, dict) else None


def format_fit_value_error(exc: ValueError) -> str:
    """Add modelling context to common low-level IPF fit errors."""

    message = str(exc)
    if "has no seed records" in message:
        return (
            "Seed records do not cover a positive control cell. "
            f"{message}. Add seed rows for that category, use a broader seed "
            "sample, or remap/drop zero-support control categories."
        )
    return message


def format_report_number(value: object) -> str:
    """Format report numbers with commas and compact floating-point output."""

    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        rounded = round(value)
        if abs(value - rounded) < 1e-9:
            return f"{rounded:,}"
        return f"{value:.6g}"
    return str(value) if value is not None else ""


def format_report_percent(value: object) -> str:
    """Format a proportion as a compact percentage for report tables."""

    if not isinstance(value, int | float):
        return ""
    if value == float("inf"):
        return "inf"
    return f"{value * 100:.6g}%"


def _format_date_range(start_date: str, end_date: str) -> str:
    """Format WDS start/end timestamps as a compact date range."""

    start = start_date[:10]
    end = end_date[:10]
    if start and start == end:
        return start
    return f"{start} to {end}".strip()


class _StdoutWriter:
    def write(self, value: str) -> int:
        print(value, end="")
        return len(value)
