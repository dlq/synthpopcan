from __future__ import annotations

import json

from synthpopcan import cli_output


def test_write_output_formats_json_dict_and_plain_text(
    capsys,
    monkeypatch,
) -> None:
    summaries: list[tuple[dict[str, object], str | None]] = []
    monkeypatch.setattr(
        cli_output,
        "print_summary_table",
        lambda payload, *, title=None: summaries.append((payload, title)),
    )

    cli_output.write_output({"b": 2, "a": 1}, "json")
    assert json.loads(capsys.readouterr().out) == {"a": 1, "b": 2}

    cli_output.write_output({"status": "ok"}, "table", title="Summary")
    assert summaries == [({"status": "ok"}, "Summary")]

    cli_output.write_output(["not", "a", "dict"], "table")
    assert "['not', 'a', 'dict']" in capsys.readouterr().out


def test_wds_search_output_formats_json_tsv_and_table(capsys, monkeypatch) -> None:
    printed_tables: list[object] = []
    monkeypatch.setattr(cli_output, "print_table", printed_tables.append)
    rows = [
        {
            "product_id": "13100005",
            "cansim_id": "105-0501",
            "start_date": "1980-01-01",
            "end_date": "1980-01-01",
            "title_en": "Population by age and sex",
        }
    ]

    cli_output.write_wds_search_results(rows, "json")
    assert json.loads(capsys.readouterr().out)[0]["product_id"] == "13100005"

    cli_output.write_wds_search_results(rows, "tsv")
    tsv = capsys.readouterr().out
    assert tsv.splitlines()[0] == (
        "product_id\tcansim_id\tstart_date\tend_date\ttitle_en"
    )
    assert "Population by age and sex" in tsv

    cli_output.write_wds_search_results(rows, "table")
    assert len(printed_tables) == 1


def test_wds_metadata_explanation_and_preview_tables(monkeypatch) -> None:
    summaries: list[tuple[dict[str, object], str | None]] = []
    tables: list[object] = []
    monkeypatch.setattr(
        cli_output,
        "print_summary_table",
        lambda payload, *, title=None: summaries.append((payload, title)),
    )
    monkeypatch.setattr(cli_output, "print_table", tables.append)

    cli_output.print_wds_metadata_explanation_table(
        {
            "product_id": "13100005",
            "date_range": "1980 to 2020",
            "dimensions": ["GEO", "Sex"],
            "ipf_suitability": {"status": "likely_age_sex_controls"},
            "ipf_hint": "Good candidate",
            "dimension_previews": [
                {
                    "name": "Sex",
                    "members": ["Female", "Male"],
                    "member_count": 2,
                    "truncated": True,
                },
                "ignored",
            ],
            "next_commands": ["synthpopcan statcan wds fetch 13100005"],
        }
    )

    assert summaries[0][0]["suitability"] == "Likely age/sex controls"
    assert len(tables) == 2
    assert cli_output._wds_suitability_label({"status": "possible_totals_only"}) == (
        "Possible totals only"
    )
    assert cli_output._wds_suitability_label({"status": "unclear"}) == "Unclear"
    assert cli_output._wds_suitability_label({"status": "custom"}) == "custom"
    assert cli_output._wds_suitability_label(None) == ""


def test_source_and_tree_helper_tables(monkeypatch) -> None:
    summaries: list[tuple[dict[str, object], str | None]] = []
    tables: list[object] = []
    monkeypatch.setattr(
        cli_output,
        "print_summary_table",
        lambda payload, *, title=None: summaries.append((payload, title)),
    )
    monkeypatch.setattr(cli_output, "print_table", tables.append)

    cli_output.print_census_profile_characteristics_table(
        [{"characteristic": "Age", "example_count": "10", "rows": "2"}]
    )
    cli_output.print_wds_inspection_table(
        {
            "csv_member": "table.csv",
            "row_count": 10,
            "columns": ["GEO", "Sex", "VALUE"],
            "count_column_candidates": ["VALUE"],
            "dimension_candidates": ["GEO", "Sex"],
            "suggested_command": "synthpopcan controls from-wds table.zip",
        }
    )
    cli_output.print_tree_column_suggestions_table(
        {
            "source_format": "statcan-2016-hierarchical",
            "geography_columns": ["PR"],
            "excluded_columns": ["WEIGHT"],
            "blocks": [
                {
                    "name": "person_demographics",
                    "level": "person",
                    "target_columns": ["AGEGRP"],
                    "conditioning_columns": ["PR"],
                    "missing_target_columns": ["SEX"],
                },
                "ignored",
            ],
        }
    )
    cli_output.print_tree_geography_feasibility_table(
        {
            "source_format": "statcan-2016-hierarchical",
            "geography_column": "PR",
            "regions": [
                {
                    "geography": "24",
                    "tier": "likely",
                    "person_rows": 1000,
                    "household_rows": 400,
                    "person_min_support": 50.0,
                    "person_max_purity": 0.2,
                    "model_design": {
                        "block_strategy": "start_with_reduced_blocks",
                        "aggregation_hint": "province",
                    },
                },
                {"geography": "bad", "model_design": "not-a-dict"},
                "ignored",
            ],
        }
    )

    assert [title for _, title in summaries] == [
        "WDS Table Inspection",
        "Column Suggestion Summary",
        "Tree Geography Feasibility Summary",
    ]
    assert len(tables) == 4
    assert (
        cli_output._first_model_design_move({"block_strategy": "use_requested_blocks"})
        == "train and audit requested blocks"
    )
    assert (
        cli_output._first_model_design_move({"block_strategy": "minimal_or_aggregate"})
        == "aggregate or use minimal targets"
    )
    assert cli_output._first_model_design_move({"block_strategy": "custom"}) == "custom"


def test_ipf_and_validation_report_tables(monkeypatch) -> None:
    summaries: list[tuple[dict[str, object], str | None]] = []
    tables: list[object] = []
    monkeypatch.setattr(
        cli_output,
        "print_summary_table",
        lambda payload, *, title=None: summaries.append((payload, title)),
    )
    monkeypatch.setattr(cli_output, "print_table", tables.append)

    margin_summary = {
        "name": "age",
        "dimensions": ["age"],
        "cells": 2,
        "target_total": 100,
        "fitted_total": 99.5,
        "actual_total": 99.5,
        "max_abs_error": 0.5,
        "max_relative_error": 0.005,
    }
    issue = {
        "severity": "warning",
        "margin": "age",
        "message": "largest residual",
        "tip": "check categories",
    }

    cli_output.print_ipf_report_table(
        {
            "converged": False,
            "iterations": 10,
            "seed_records": 4,
            "max_abs_error": 0.5,
            "margin_summaries": [margin_summary, "ignored"],
            "issues": [issue, "ignored"],
            "suggested_next_steps": ["inspect controls"],
        }
    )
    cli_output.print_ipf_input_check_table(
        {
            "passed": False,
            "seed_records": 4,
            "control_margins": 1,
            "unsupported_cells": [1],
            "dimensions": [
                {
                    "dimension": "age",
                    "status": "missing",
                    "seed_column": "missing",
                    "missing_categories": ["old"],
                    "unused_seed_categories": ["young"],
                    "detail": "needs source column",
                },
                "ignored",
            ],
            "suggested_next_steps": ["add age"],
        }
    )
    cli_output.print_ipf_control_suggestions_table(
        {
            "unit": "person",
            "seed_records": 10,
            "available_columns": ["age"],
            "geography_columns": ["GEO"],
            "usable_controls": [
                "ignored",
                {
                    "column": "age",
                    "role": "target",
                    "statcan_search": "age",
                    "reason": "present",
                },
            ],
            "enrichment_candidates": [
                "ignored",
                {
                    "column": "income",
                    "role": "enrichment",
                    "statcan_search": "income",
                    "reason": "missing",
                },
            ],
            "next_commands": ["synthpopcan statcan wds search age"],
        }
    )
    suggestions = next(
        table for table in tables if table.title == "IPF Control Suggestions"
    )
    assert [column.header for column in suggestions.columns] == [
        "Column",
        "Decision",
        "Search Terms",
        "Why It Matters",
    ]
    cli_output.print_validation_report_table(
        {
            "passed": False,
            "artifact_kind": "weights",
            "population_records": 4,
            "max_abs_error": 0.5,
            "tolerance": 0.1,
            "margin_summaries": [margin_summary, "ignored"],
            "issues": [issue],
        }
    )
    cli_output.print_tree_output_validation_report_table(
        {
            "passed": False,
            "artifact_kind": "tree",
            "training_records": 10,
            "generated_records": 5,
            "max_abs_proportion_delta": 0.2,
            "tolerance": 0.05,
            "comparisons": [
                {
                    "dimensions": ["age"],
                    "cells": [{}, {}],
                    "training_total": 10,
                    "generated_total": 5,
                    "max_abs_proportion_delta": 0.2,
                },
                "ignored",
            ],
            "issues": [issue],
        }
    )
    cli_output.print_seed_check_table(
        {
            "passed": False,
            "source_format": "fixture",
            "level": "household",
            "households": 2,
            "people": 5,
            "checks": [
                {
                    "column": "TENUR",
                    "role": "selected household column",
                    "status": "conflict",
                    "detail": "not constant",
                },
                "ignored",
            ],
        }
    )

    assert "IPF Fit Summary" in [title for _, title in summaries]
    assert len(tables) >= 11


def test_cli_output_formatting_helpers() -> None:
    cli_output._print_wds_dimension_preview_table([])
    cli_output._print_wds_dimension_preview_table("not-a-list")
    cli_output._print_issues_table("not-a-list", title="Issues")
    cli_output._print_next_steps_table("not-a-list")

    assert cli_output.format_nonconvergence_message(
        {
            "iterations": 10,
            "max_abs_error": 1.5,
            "issues": [{"message": "Bad fit.", "tip": "Check controls."}],
        }
    ) == (
        "IPF did not converge after 10 iterations; max absolute error is 1.5. "
        "Bad fit. Check controls. Use --allow-nonconverged to write the fitted "
        "weights anyway."
    )
    assert cli_output._first_report_issue({"issues": []}) is None
    assert cli_output._first_report_issue({"issues": ["bad"]}) is None
    assert cli_output.format_fit_value_error(ValueError("x has no seed records")) == (
        "Seed records do not cover a positive control cell. x has no seed "
        "records. Add seed rows for that category, use a broader seed sample, "
        "or remap/drop zero-support control categories."
    )
    assert cli_output.format_fit_value_error(ValueError("other")) == "other"
    assert cli_output.format_report_number(1000) == "1,000"
    assert cli_output.format_report_number(2.0) == "2"
    assert cli_output.format_report_number(1.23456789) == "1.23457"
    assert cli_output.format_report_number(None) == ""
    assert cli_output.format_report_percent(0.125) == "12.5%"
    assert cli_output.format_report_percent(float("inf")) == "inf"
    assert cli_output.format_report_percent("n/a") == ""
    assert cli_output._format_date_range("2020-01-01", "2020-01-01") == "2020-01-01"
    assert cli_output._format_date_range("2020-01-01", "2021-01-01") == (
        "2020-01-01 to 2021-01-01"
    )


# ---------------------------------------------------------------------------
# cli_output.py — _control_suggestion_note branches (from test_coverage_gaps2.py)
# ---------------------------------------------------------------------------


def test_control_suggestion_note_with_reason_but_no_role() -> None:
    result = cli_output._control_suggestion_note(
        {"reason": "Use this as a control"}, "Run synthpopcan validate"
    )
    assert result == "Use this as a control Run synthpopcan validate"


def test_control_suggestion_note_with_no_role_and_no_reason() -> None:
    result = cli_output._control_suggestion_note({}, "Run synthpopcan validate")
    assert result == "Run synthpopcan validate"
