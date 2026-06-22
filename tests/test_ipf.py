import csv
import json
from pathlib import Path

import pytest

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.diagnostics import build_ipf_fit_report, build_ipf_input_report
from synthpopcan.ipf import IPFMargin, expand_records, fit_ipf


def test_fit_ipf_matches_two_one_way_margins() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "young", "sex": "M"},
        {"age": "old", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0}),
        IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0}),
    ]

    result = fit_ipf(records, margins, tolerance=1e-9)

    assert result.converged
    assert result.iterations > 0
    assert result.weights == pytest.approx([30.0, 30.0, 20.0, 20.0])
    assert result.margin_totals(("age",)) == pytest.approx(
        {("young",): 60.0, ("old",): 40.0}
    )
    assert result.margin_totals(("sex",)) == pytest.approx({("F",): 50.0, ("M",): 50.0})


def test_fit_ipf_reports_missing_seed_cells() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "old", "sex": "F"},
    ]
    margins = [
        IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0}),
    ]

    with pytest.raises(ValueError, match="no seed records"):
        fit_ipf(records, margins)


def test_ipf_input_report_finds_missing_and_unused_seed_categories() -> None:
    control_table = ControlTable(
        margins=(
            ControlMargin(
                name="sex",
                dimensions=("sex",),
                cells=(
                    ControlCell({"sex": "F"}, 50.0),
                    ControlCell({"sex": "M"}, 50.0),
                ),
            ),
        ),
        dimensions=("sex",),
    )

    report = build_ipf_input_report(
        [
            {"id": "1", "sex": "F"},
            {"id": "2", "sex": "X"},
        ],
        control_table,
    )

    assert report == {
        "passed": False,
        "seed_records": 2,
        "control_margins": 1,
        "dimensions": [
            {
                "dimension": "sex",
                "status": "problem",
                "seed_column": "found",
                "control_categories": ["F", "M"],
                "seed_categories": ["F", "X"],
                "missing_categories": ["M"],
                "unused_seed_categories": ["X"],
                "detail": "missing control categories: M; unused seed categories: X",
            }
        ],
        "unsupported_cells": [
            {
                "margin": "sex",
                "dimensions": ["sex"],
                "categories": {"sex": "M"},
                "target": 50.0,
            }
        ],
        "suggested_next_steps": [
            (
                "Column/category mismatch for dimension 'sex': controls include "
                "'M', but the seed does not. If this came from WDS labels, run "
                "`synthpopcan controls wds mapping-template ... --dimensions "
                '"sex" --out categories.json`, fill in the target seed labels, '
                "then rerun `controls from-wds --mapping categories.json`."
            ),
        ],
    }


def test_expand_records_integerizes_weights_with_seed_ids() -> None:
    records = [
        {"id": "a", "age": "young", "sex": "F"},
        {"id": "b", "age": "old", "sex": "M"},
    ]

    expanded = expand_records(records, [1.2, 2.8])

    assert expanded == [
        {"synthetic_id": "1", "seed_id": "a", "age": "young", "sex": "F"},
        {"synthetic_id": "2", "seed_id": "b", "age": "old", "sex": "M"},
        {"synthetic_id": "3", "seed_id": "b", "age": "old", "sex": "M"},
        {"synthetic_id": "4", "seed_id": "b", "age": "old", "sex": "M"},
    ]


def test_cli_runs_ipf_from_csv_files_as_expanded_synthetic_data(
    tmp_path: Path,
) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "60",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "40",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "50",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(weights_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert rows[0] == {
        "synthetic_id": "1",
        "seed_id": "1",
        "age": "young",
        "sex": "F",
    }
    assert len(rows) == 100
    assert count_rows(rows, "age") == {"young": 60, "old": 40}
    assert count_rows(rows, "sex") == {"F": 50, "M": 50}


def test_cli_runs_ipf_from_csv_files_as_weights_by_default(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "60",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "40",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "50",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert [row["weight"] for row in rows] == ["30", "30", "20", "20"]


def test_cli_suggests_household_calibration_controls_from_seed_columns(
    tmp_path: Path,
    capsys,
) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "candidate-households.csv"
    write_csv(
        seed_path,
        ["synthetic_household_id", "geo", "household_size", "tenure", "rooms"],
        [
            {
                "synthetic_household_id": "1",
                "geo": "QC",
                "household_size": "2",
                "tenure": "owner",
                "rooms": "5",
            },
            {
                "synthetic_household_id": "2",
                "geo": "QC",
                "household_size": "1",
                "tenure": "renter",
                "rooms": "3",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "suggest-controls",
                "--seed",
                str(seed_path),
                "--unit",
                "household",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "synthpopcan-ipf-control-suggestions-v1"
    assert report["unit"] == "household"
    assert report["seed_records"] == 2
    assert report["available_columns"] == [
        "synthetic_household_id",
        "geo",
        "household_size",
        "tenure",
        "rooms",
    ]
    assert report["geography_columns"] == ["geo"]
    assert [item["column"] for item in report["usable_controls"]] == [
        "household_size",
        "tenure",
        "rooms",
    ]
    assert report["enrichment_candidates"][0]["column"] == "dwelling_type"
    assert report["next_commands"] == [
        "synthpopcan statcan wds search household size",
        "synthpopcan statcan wds explain PRODUCT_ID",
        (f"synthpopcan ipf check-inputs --seed {seed_path} --controls controls.csv"),
    ]


def test_cli_suggests_person_calibration_controls_from_seed_columns(
    tmp_path: Path,
    capsys,
) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "candidate-persons.csv"
    write_csv(
        seed_path,
        ["synthetic_person_id", "PR", "age_group", "sex", "marital_status"],
        [
            {
                "synthetic_person_id": "1",
                "PR": "24",
                "age_group": "adult",
                "sex": "F",
                "marital_status": "single",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "suggest-controls",
                "--seed",
                str(seed_path),
                "--unit",
                "auto",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["unit"] == "person"
    assert report["geography_columns"] == ["PR"]
    assert [item["column"] for item in report["usable_controls"]] == [
        "age_group",
        "sex",
        "marital_status",
    ]
    assert report["enrichment_candidates"][0]["column"] == "immigration_status"


def test_cli_prints_control_suggestions_table(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "candidate-households.csv"
    write_csv(
        seed_path,
        ["geo", "household_size", "tenure"],
        [{"geo": "QC", "household_size": "2", "tenure": "owner"}],
    )

    assert (
        main(
            [
                "ipf",
                "suggest-controls",
                "--seed",
                str(seed_path),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "IPF Control Suggestions" in output
    assert "household_size" in output
    assert "statcan wds search household size" in output


def test_cli_fit_writes_diagnostics_report(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "60",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "40",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "50",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(output_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )

    report = json.loads(report_path.read_text())
    assert report["converged"] is True
    assert report["iterations"] > 0
    assert report["max_abs_error"] == pytest.approx(0.0)
    assert report["seed_records"] == 4
    assert report["margins"][0] == {
        "name": "age",
        "dimensions": ["age"],
        "cells": [
            {
                "categories": {"age": "young"},
                "target": 60.0,
                "fitted": 60.0,
                "residual": 0.0,
            },
            {
                "categories": {"age": "old"},
                "target": 40.0,
                "fitted": 40.0,
                "residual": 0.0,
            },
        ],
    }


def test_ipf_report_includes_margin_summaries() -> None:
    control_table = ControlTable(
        margins=(
            ControlMargin(
                name="age",
                dimensions=("age",),
                cells=(
                    ControlCell({"age": "young"}, 60.0),
                    ControlCell({"age": "old"}, 40.0),
                ),
            ),
        ),
        dimensions=("age",),
    )
    result = fit_ipf(
        [
            {"age": "young"},
            {"age": "old"},
        ],
        [IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0})],
    )

    report = build_ipf_fit_report(control_table, result)

    assert report["margin_summaries"] == [
        {
            "name": "age",
            "dimensions": ["age"],
            "cells": 2,
            "target_total": 100.0,
            "fitted_total": 100.0,
            "max_abs_error": 0.0,
            "max_relative_error": 0.0,
        }
    ]


def test_nonconverged_ipf_report_includes_actionable_issues() -> None:
    control_table = ControlTable(
        margins=(
            ControlMargin(
                name="age",
                dimensions=("age",),
                cells=(
                    ControlCell({"age": "young"}, 50.0),
                    ControlCell({"age": "old"}, 50.0),
                ),
            ),
            ControlMargin(
                name="sex",
                dimensions=("sex",),
                cells=(
                    ControlCell({"sex": "F"}, 80.0),
                    ControlCell({"sex": "M"}, 20.0),
                ),
            ),
        ),
        dimensions=("age", "sex"),
    )
    result = fit_ipf(
        [
            {"age": "young", "sex": "F"},
            {"age": "old", "sex": "M"},
        ],
        control_table.to_ipf_margins(),
        max_iterations=2,
    )

    report = build_ipf_fit_report(control_table, result)

    assert report["converged"] is False
    assert report["issues"][0]["kind"] == "cell_residual"
    assert report["issues"][0]["margin"] == "age"
    assert report["issues"][0]["categories"] == {"age": "young"}
    assert report["issues"][0]["message"].startswith("Largest residual is 30")
    assert "Check whether this control conflicts" in report["issues"][0]["tip"]


def test_ipf_report_summarizes_inconsistent_margin_totals() -> None:
    control_table = ControlTable(
        margins=(
            ControlMargin(
                name="age",
                dimensions=("age",),
                cells=(
                    ControlCell({"age": "young"}, 60.0),
                    ControlCell({"age": "old"}, 40.0),
                ),
            ),
            ControlMargin(
                name="sex",
                dimensions=("sex",),
                cells=(
                    ControlCell({"sex": "F"}, 70.0),
                    ControlCell({"sex": "M"}, 40.0),
                ),
            ),
        ),
        dimensions=("age", "sex"),
    )
    result = fit_ipf(
        [
            {"age": "young", "sex": "F"},
            {"age": "young", "sex": "M"},
            {"age": "old", "sex": "F"},
            {"age": "old", "sex": "M"},
        ],
        control_table.to_ipf_margins(),
        max_iterations=2,
    )

    report = build_ipf_fit_report(control_table, result)

    assert report["control_total_checks"] == {
        "status": "inconsistent",
        "totals": [
            {"margin": "age", "dimensions": ["age"], "target_total": 100.0},
            {"margin": "sex", "dimensions": ["sex"], "target_total": 110.0},
        ],
        "min_total": 100.0,
        "max_total": 110.0,
        "difference": 10.0,
    }
    assert report["issues"][0]["kind"] == "inconsistent_control_totals"
    assert (
        "Control margins do not agree on total population"
        in (report["issues"][0]["message"])
    )
    assert report["suggested_next_steps"][0] == (
        "Review the source tables or mappings: control margins have different "
        "total populations, so IPF cannot satisfy all controls exactly."
    )


def test_cli_prints_human_readable_ipf_report(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    report_path = tmp_path / "fit-report.json"
    report_path.write_text(
        json.dumps(
            {
                "converged": True,
                "iterations": 3,
                "max_abs_error": 0.0,
                "seed_records": 4,
                "suggested_next_steps": [
                    "Review the source tables or mappings before trusting this fit."
                ],
                "issues": [
                    {
                        "severity": "warning",
                        "kind": "cell_residual",
                        "margin": "age",
                        "categories": {"age": "young"},
                        "message": "Largest residual is 30 for age=young.",
                        "tip": (
                            "Check whether this control conflicts with another margin."
                        ),
                    }
                ],
                "margin_summaries": [
                    {
                        "name": "age",
                        "dimensions": ["age"],
                        "cells": 2,
                        "target_total": 100.0,
                        "fitted_total": 100.0,
                        "max_abs_error": 0.0,
                        "max_relative_error": 0.0,
                    }
                ],
                "margins": [],
            }
        )
    )

    assert main(["ipf", "report", str(report_path)]) == 0

    output = capsys.readouterr().out
    assert "IPF Fit Report" in output
    assert "Converged" in output
    assert "Fit Issues" in output
    assert "Largest residual" in output
    assert "Next Steps" in output
    assert "Review the source tables" in output
    assert "age" in output
    assert "100" in output


def test_cli_expands_fitted_weight_when_seed_has_initial_weight(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"

    write_csv(
        seed_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "1"},
            {"id": "2", "age": "old", "weight": "1"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "count"],
        [
            {"margin": "age", "dimensions": "age", "age": "young", "count": "10"},
            {"margin": "age", "dimensions": "age", "age": "old", "count": "20"},
        ],
    )

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(weights_path),
                "--weight-field",
                "weight",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert len(rows) == 30
    assert count_rows(rows, "age") == {"young": 10, "old": 20}


def test_cli_expands_rows_without_materializing_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from synthpopcan.cli import main

    weights_path = tmp_path / "weights.csv"
    output_path = tmp_path / "synthetic.csv"
    write_csv(
        weights_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "2"},
            {"id": "2", "age": "old", "weight": "1"},
        ],
    )

    def fail_if_materialized(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("expand_records should not be used by CLI expansion")

    monkeypatch.setattr("synthpopcan.ipf.expand_records", fail_if_materialized)

    assert (
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    rows = list(csv.DictReader(output_path.open(newline="")))
    assert rows == [
        {"synthetic_id": "1", "seed_id": "1", "age": "young"},
        {"synthetic_id": "2", "seed_id": "1", "age": "young"},
        {"synthetic_id": "3", "seed_id": "2", "age": "old"},
    ]


def test_cli_fit_fails_when_ipf_does_not_converge(tmp_path: Path) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"

    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "50",
            },
            {
                "margin": "age",
                "dimensions": "age",
                "age": "old",
                "sex": "",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "80",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "M",
                "count": "20",
            },
        ],
    )

    with pytest.raises(ClickException, match="Largest residual"):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(output_path),
                "--max-iterations",
                "2",
            ]
        )
    assert not output_path.exists()


def test_cli_fit_explains_unsupported_control_cells(tmp_path: Path) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    output_path = tmp_path / "weights.csv"
    write_csv(
        seed_path,
        ["id", "sex"],
        [
            {"id": "1", "sex": "F"},
            {"id": "2", "sex": "F"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "sex", "count"],
        [
            {"margin": "sex", "dimensions": "sex", "sex": "F", "count": "50"},
            {"margin": "sex", "dimensions": "sex", "sex": "M", "count": "50"},
        ],
    )

    with pytest.raises(ClickException, match="Seed records do not cover"):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(output_path),
            ]
        )
    assert not output_path.exists()


def test_cli_checks_ipf_inputs_as_json(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    write_csv(
        seed_path,
        ["id", "sex"],
        [
            {"id": "1", "sex": "F"},
            {"id": "2", "sex": "X"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "sex", "count"],
        [
            {"margin": "sex", "dimensions": "sex", "sex": "F", "count": "50"},
            {"margin": "sex", "dimensions": "sex", "sex": "M", "count": "50"},
        ],
    )

    assert (
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is False
    assert report["dimensions"][0]["dimension"] == "sex"
    assert report["dimensions"][0]["missing_categories"] == ["M"]
    assert report["dimensions"][0]["unused_seed_categories"] == ["X"]


def test_cli_checks_ipf_inputs_as_readable_table(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    write_csv(
        seed_path,
        ["id", "age"],
        [
            {"id": "1", "age": "young"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {
                "margin": "age",
                "dimensions": "age",
                "age": "young",
                "sex": "",
                "count": "50",
            },
            {
                "margin": "sex",
                "dimensions": "sex",
                "age": "",
                "sex": "F",
                "count": "50",
            },
        ],
    )

    assert (
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "IPF Input Check" in output
    assert "Needs attention" in output
    assert "age" in output
    assert "OK" in output
    assert "sex" in output
    assert "Missing column" in output
    assert "Next Steps" in output
    assert "export a seed column named 'sex'" in output


def count_rows(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[field]] = counts.get(row[field], 0) + 1
    return counts


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
