import csv
import json
from pathlib import Path

import pytest

import synthpopcan.ipf as ipf_module
from synthpopcan.cli_ipf import (
    _format_weight,
    _read_weighted_seed,
    _write_expanded_seed,
    _write_weighted_seed,
    read_population_artifact,
)
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.diagnostics import (
    build_control_total_checks,
    build_ipf_fit_report,
    build_ipf_input_report,
    format_number,
    relative_error,
)
from synthpopcan.ipf import (
    IPFMargin,
    calculate_max_abs_error,
    expand_records,
    fit_ipf,
    integerize_weights,
    validate_margin_coverage,
    weighted_totals,
)


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


def test_ipf_margin_rejects_invalid_targets() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        IPFMargin((), {(): 1.0})
    with pytest.raises(ValueError, match="does not match dimensions"):
        IPFMargin(("age",), {("young", "extra"): 1.0})
    with pytest.raises(ValueError, match="must be non-negative"):
        IPFMargin(("age",), {("young",): -1.0})


def test_fit_ipf_rejects_invalid_run_settings_and_weights() -> None:
    records = [{"age": "young", "weight": "1"}]
    margins = [IPFMargin(("age",), {("young",): 1.0})]

    with pytest.raises(ValueError, match="at least one seed record"):
        fit_ipf([], margins)
    with pytest.raises(ValueError, match="at least one margin"):
        fit_ipf(records, [])
    with pytest.raises(ValueError, match="max_iterations"):
        fit_ipf(records, margins, max_iterations=0)
    with pytest.raises(ValueError, match="tolerance"):
        fit_ipf(records, margins, tolerance=-0.1)
    with pytest.raises(ValueError, match="weight field"):
        fit_ipf([{"age": "young"}], margins, weight_field="weight")
    with pytest.raises(ValueError, match="seed weights"):
        fit_ipf([{"age": "young", "weight": "-1"}], margins, weight_field="weight")
    with pytest.raises(ValueError, match="no seed records"):
        fit_ipf(
            [{"age": "young", "weight": "0"}],
            margins,
            weight_field="weight",
        )


def test_fit_ipf_handles_zero_targets_and_reports_nonconvergence() -> None:
    records = [{"age": "young"}, {"age": "old"}]
    zero_target = [IPFMargin(("age",), {("young",): 0.0, ("old",): 0.0})]
    impossible_without_positive_target = [IPFMargin(("age",), {("missing",): 0.0})]

    result = fit_ipf(records, zero_target)

    assert result.converged is True
    assert result.weights == [0.0, 0.0]
    missing_zero = fit_ipf(records, impossible_without_positive_target)
    assert missing_zero.converged is True

    nonconverged = fit_ipf(
        [
            {"age": "young", "sex": "F"},
            {"age": "old", "sex": "M"},
            {"age": "young", "sex": "M"},
        ],
        [
            IPFMargin(("age",), {("young",): 70.0, ("old",): 30.0}),
            IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0}),
        ],
        max_iterations=1,
        tolerance=0.0,
    )
    assert nonconverged.converged is False


def test_integerize_and_aggregate_ipf_helpers_cover_edge_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [{"age": "young"}, {"age": "old"}]
    weights = [1.2, 1.8]
    margins = [IPFMargin(("age",), {("young",): 1.0, ("old",): 2.0})]

    assert integerize_weights(weights) == [1, 2]

    # Regression: fractional weights (pool >> target) must preserve group proportions.
    # Largest-remainder failed here: with 4 owners (weight ~0.024 each) and 3 renters
    # (weight ~0.034 each), all draws went to renters because their per-candidate
    # weight was uniformly higher. Systematic sampling correctly distributes them.
    small_pool = [{"TENUR": "1"}] * 28 + [{"TENUR": "2"}] * 22  # 50 candidates
    frac_weights = [6.78 / 28] * 28 + [7.42 / 22] * 22  # targets: ~7 owners, ~7 renters
    frac_counts = integerize_weights(frac_weights)
    owner_total = sum(
        c for h, c in zip(small_pool, frac_counts, strict=True) if h["TENUR"] == "1"
    )
    renter_total = sum(
        c for h, c in zip(small_pool, frac_counts, strict=True) if h["TENUR"] == "2"
    )
    assert owner_total > 0, (
        "systematic sampling must select at least some owner candidates"
    )
    assert renter_total > 0, (
        "systematic sampling must select at least some renter candidates"
    )
    assert owner_total + renter_total == round(sum(frac_weights))

    with pytest.raises(ValueError, match="non-negative"):
        integerize_weights([1.0, -0.1])
    with monkeypatch.context() as patched:
        patched.setattr(ipf_module, "round", lambda _value: -1, raising=False)
        with pytest.raises(ValueError, match="integerized total"):
            integerize_weights([0.1])
    assert expand_records([{"age": "young"}], [1.0]) == [
        {"synthetic_id": "1", "seed_id": "1", "age": "young"}
    ]
    assert weighted_totals(records, weights, ("age",)) == {
        ("young",): 1.2,
        ("old",): 1.8,
    }
    assert calculate_max_abs_error(records, weights, margins) == pytest.approx(0.2)
    validate_margin_coverage(records, margins)
    with pytest.raises(ValueError, match="missing dimension"):
        weighted_totals([{"age": "young"}], [1.0], ("sex",))


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


def test_ipf_input_report_explains_missing_columns_as_enrichment_needed() -> None:
    control_table = ControlTable(
        margins=(
            ControlMargin(
                name="education",
                dimensions=("education",),
                cells=(
                    ControlCell({"education": "university"}, 120.0),
                    ControlCell({"education": "no_university"}, 180.0),
                ),
            ),
        ),
        dimensions=("education",),
    )

    report = build_ipf_input_report(
        [
            {"id": "1", "age": "adult", "sex": "F"},
            {"id": "2", "age": "adult", "sex": "M"},
        ],
        control_table,
    )

    assert report["dimensions"][0]["detail"] == (
        "seed column is missing; add this attribute before IPF"
    )
    assert report["suggested_next_steps"] == [
        (
            "Missing seed column for dimension 'education': IPF cannot create "
            "this variable. Add it first with an enrichment/modeling step, "
            "export a seed column named 'education', or choose controls whose "
            "dimensions already exist in the seed. Run `synthpopcan ipf "
            "suggest-controls --seed seed.csv` to inspect usable calibration "
            "columns."
        )
    ]


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


def test_ipf_report_helpers_cover_empty_and_zero_cases() -> None:
    empty_controls = ControlTable(margins=(), dimensions=())

    assert build_control_total_checks(empty_controls) == {
        "status": "ok",
        "totals": [],
        "min_total": 0.0,
        "max_total": 0.0,
        "difference": 0.0,
    }
    assert relative_error(0.0, 0.0) == 0.0
    assert relative_error(1.0, 0.0) == float("inf")
    assert format_number(1000.0) == "1,000"
    assert format_number(1.25) == "1.25"


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


def test_cli_prints_ipf_report_json_and_rejects_invalid_json(
    tmp_path: Path,
    capsys,
) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    report_path = tmp_path / "fit-report.json"
    report_path.write_text(json.dumps({"converged": True, "seed_records": 4}))

    assert main(["ipf", "report", str(report_path), "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "converged": True,
        "seed_records": 4,
    }

    invalid_path = tmp_path / "invalid-report.json"
    invalid_path.write_text("{")
    with pytest.raises(ClickException, match="not valid JSON"):
        main(["ipf", "report", str(invalid_path)])

    with pytest.raises(ClickException, match="Could not read"):
        main(["ipf", "report", str(tmp_path / "missing-report.json")])


def test_cli_ipf_fit_reports_missing_input_files(tmp_path: Path) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "missing-controls.csv"
    seed_path.write_text("id,sex\n1,F\n")

    with pytest.raises(ClickException) as excinfo:
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--out",
                str(tmp_path / "weights.csv"),
            ]
        )

    message = str(excinfo.value)
    assert "Could not read" in message
    assert str(controls_path) in message
    assert "Check that the path is correct" in message


def test_cli_ipf_expand_reports_invalid_weight_file(tmp_path: Path) -> None:
    from click.exceptions import ClickException

    from synthpopcan.cli import main

    weights_path = tmp_path / "not-weights.csv"
    weights_path.write_text("id,age\n1,adult\n")

    with pytest.raises(ClickException, match="requires a 'weight' column"):
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(weights_path),
                "--out",
                str(tmp_path / "expanded.csv"),
            ]
        )


def test_ipf_weight_artifact_helpers_validate_input_files(tmp_path: Path) -> None:
    weights_path = tmp_path / "weights.csv"
    write_csv(
        weights_path,
        ["id", "age", "fitted_weight"],
        [{"id": "1", "age": "young", "fitted_weight": "1.25"}],
    )

    rows, weights = _read_weighted_seed(weights_path, "weight")

    assert rows == [{"id": "1", "age": "young"}]
    assert weights == [1.25]
    assert read_population_artifact(weights_path, "weights", "weight") == (
        rows,
        weights,
    )

    expanded_path = tmp_path / "expanded.csv"
    write_csv(
        expanded_path,
        ["synthetic_id", "age"],
        [
            {"synthetic_id": "1", "age": "young"},
            {"synthetic_id": "2", "age": "old"},
        ],
    )
    assert read_population_artifact(expanded_path, "expanded", "weight") == (
        [
            {"synthetic_id": "1", "age": "young"},
            {"synthetic_id": "2", "age": "old"},
        ],
        [1.0, 1.0],
    )

    with pytest.raises(ValueError, match="unknown population artifact kind"):
        read_population_artifact(weights_path, "rows", "weight")

    missing_weight_path = tmp_path / "missing-weight.csv"
    write_csv(missing_weight_path, ["id", "age"], [{"id": "1", "age": "young"}])
    with pytest.raises(ValueError, match="requires a 'weight' column"):
        _read_weighted_seed(missing_weight_path, "weight")

    invalid_weight_path = tmp_path / "invalid-weight.csv"
    write_csv(invalid_weight_path, ["id", "weight"], [{"id": "1", "weight": "bad"}])
    with pytest.raises(ValueError, match="row 2 has invalid weight"):
        _read_weighted_seed(invalid_weight_path, "weight")


def test_ipf_writers_reject_empty_outputs_and_format_weights(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty seed rows"):
        _write_weighted_seed(tmp_path / "weights.csv", [], [])
    with pytest.raises(ValueError, match="synthetic population is empty"):
        _write_expanded_seed(tmp_path / "expanded.csv", [{"id": "1"}], [0.0])

    output_path = tmp_path / "weights.csv"
    _write_weighted_seed(
        output_path,
        [{"id": "1", "age": "young", "weight": "1"}],
        [1.25],
    )

    assert list(csv.DictReader(output_path.open(newline=""))) == [
        {"id": "1", "age": "young", "weight": "1", "fitted_weight": "1.25"}
    ]
    assert _format_weight(2.0) == "2"
    assert _format_weight(1.25) == "1.25"


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
    assert "Next Steps" in output
    assert "IPF cannot create this variable" in output
    assert "suggest-controls" in output


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
