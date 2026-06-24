import csv
import json
from pathlib import Path

import pytest
from click.exceptions import ClickException

from synthpopcan.controls import read_control_table
from synthpopcan.validation import (
    build_control_validation_report,
    build_tree_output_validation_report,
    safe_proportion,
)


def test_validates_weighted_rows_against_controls(tmp_path: Path) -> None:
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,age,count\nage,age,young,60\nage,age,old,40\n"
    )
    table = read_control_table(controls_path)

    report = build_control_validation_report(
        table,
        [
            {"id": "1", "age": "young"},
            {"id": "2", "age": "old"},
        ],
        [60.0, 40.0],
        tolerance=0.0,
    )

    assert report["passed"] is True
    assert report["max_abs_error"] == 0.0
    assert report["margin_summaries"] == [
        {
            "name": "age",
            "dimensions": ["age"],
            "cells": 2,
            "target_total": 100.0,
            "actual_total": 100.0,
            "max_abs_error": 0.0,
            "max_relative_error": 0.0,
        }
    ]


def test_validation_report_fails_when_artifact_differs_from_controls(
    tmp_path: Path,
) -> None:
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,age,count\nage,age,young,60\nage,age,old,40\n"
    )
    table = read_control_table(controls_path)

    report = build_control_validation_report(
        table,
        [
            {"id": "1", "age": "young"},
            {"id": "2", "age": "old"},
        ],
        [50.0, 50.0],
        tolerance=0.0,
    )

    assert report["passed"] is False
    assert report["max_abs_error"] == 10.0
    assert (
        report["issues"][0]["message"]
        == "Largest validation error is 10 for age=young."
    )


def test_cli_validates_weight_output_as_json(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    controls_path.write_text(
        "margin,dimensions,age,count\nage,age,young,60\nage,age,old,40\n"
    )
    write_csv(
        weights_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "60"},
            {"id": "2", "age": "old", "weight": "40"},
        ],
    )

    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["artifact_kind"] == "weights"
    assert report["population_records"] == 2


def test_cli_validation_fails_over_tolerance(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    controls_path.write_text(
        "margin,dimensions,age,count\nage,age,young,60\nage,age,old,40\n"
    )
    write_csv(
        weights_path,
        ["id", "age", "weight"],
        [
            {"id": "1", "age": "young", "weight": "50"},
            {"id": "2", "age": "old", "weight": "50"},
        ],
    )

    with pytest.raises(ClickException, match="Validation failed"):
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
            ]
        )


def test_cli_validation_wraps_bad_population_artifacts(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    controls_path.write_text("margin,dimensions,age,count\nage,age,young,1\n")
    write_csv(weights_path, ["id", "age"], [{"id": "1", "age": "young"}])

    with pytest.raises(ClickException, match="requires a 'weight' column"):
        main(
            [
                "validate",
                "controls",
                "--population",
                str(weights_path),
                "--controls",
                str(controls_path),
                "--kind",
                "weights",
            ]
        )


def test_cli_validates_expanded_output(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    controls_path = tmp_path / "controls.csv"
    population_path = tmp_path / "synthetic.csv"
    controls_path.write_text(
        "margin,dimensions,age,count\nage,age,young,2\nage,age,old,1\n"
    )
    write_csv(
        population_path,
        ["synthetic_id", "seed_id", "age"],
        [
            {"synthetic_id": "1", "seed_id": "1", "age": "young"},
            {"synthetic_id": "2", "seed_id": "1", "age": "young"},
            {"synthetic_id": "3", "seed_id": "2", "age": "old"},
        ],
    )

    assert (
        main(
            [
                "validate",
                "controls",
                "--population",
                str(population_path),
                "--controls",
                str(controls_path),
                "--kind",
                "expanded",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["artifact_kind"] == "expanded"
    assert report["population_records"] == 3


def test_cli_validates_linked_output_and_reports_failures(
    tmp_path: Path,
    capsys,
) -> None:
    from synthpopcan.cli import main

    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    write_csv(
        households_path,
        ["synthetic_household_id", "household_size"],
        [{"synthetic_household_id": "h1", "household_size": "2"}],
    )
    write_csv(
        persons_path,
        ["synthetic_person_id", "synthetic_household_id"],
        [
            {"synthetic_person_id": "p1", "synthetic_household_id": "h1"},
            {"synthetic_person_id": "p2", "synthetic_household_id": "h1"},
        ],
    )

    assert (
        main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out)["passed"] is True

    write_csv(
        persons_path,
        ["synthetic_person_id", "synthetic_household_id"],
        [{"synthetic_person_id": "p1", "synthetic_household_id": "missing"}],
    )
    with pytest.raises(ClickException, match="linkage problems"):
        main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
            ]
        )


def test_cli_linked_output_wraps_validation_value_errors(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    write_csv(
        households_path,
        ["synthetic_household_id"],
        [{"synthetic_household_id": "h1"}],
    )
    write_csv(
        persons_path,
        ["synthetic_person_id", "synthetic_household_id"],
        [{"synthetic_person_id": "p1", "synthetic_household_id": "h1"}],
    )

    with pytest.raises(ClickException, match="linkage problems"):
        main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
            ]
        )


def test_tree_output_validation_compares_target_distributions() -> None:
    report = build_tree_output_validation_report(
        training_rows=[
            {"AGEGRP": "adult", "SEX": "F", "WEIGHT": "2"},
            {"AGEGRP": "child", "SEX": "M", "WEIGHT": "1"},
        ],
        generated_rows=[
            {"AGEGRP": "adult", "SEX": "F"},
            {"AGEGRP": "adult", "SEX": "F"},
            {"AGEGRP": "child", "SEX": "M"},
        ],
        target_columns=("AGEGRP", "SEX"),
        conditioning_columns=(),
        weight_field="WEIGHT",
        tolerance=0.0,
    )

    assert report["passed"] is True
    assert report["training_records"] == 2
    assert report["generated_records"] == 3
    assert report["max_abs_proportion_delta"] == 0.0
    assert report["comparisons"][0]["dimensions"] == ["AGEGRP"]
    assert report["comparisons"][2]["dimensions"] == ["AGEGRP", "SEX"]


def test_tree_output_validation_flags_unknown_generated_categories() -> None:
    report = build_tree_output_validation_report(
        training_rows=[{"AGEGRP": "adult", "SEX": "F", "WEIGHT": "1"}],
        generated_rows=[
            {"AGEGRP": "adult", "SEX": "F"},
            {"AGEGRP": "senior", "SEX": "F"},
        ],
        target_columns=("AGEGRP", "SEX"),
        conditioning_columns=(),
        weight_field="WEIGHT",
        tolerance=0.2,
    )

    assert report["passed"] is False
    assert report["issues"][0]["kind"] == "unknown_generated_category"
    assert report["issues"][0]["dimensions"] == ["AGEGRP"]
    assert report["issues"][0]["categories"] == {"AGEGRP": "senior"}


def test_tree_output_validation_rejects_missing_inputs() -> None:
    with pytest.raises(ValueError, match="training rows are required"):
        build_tree_output_validation_report(
            training_rows=[],
            generated_rows=[{"AGEGRP": "adult"}],
            target_columns=("AGEGRP",),
            conditioning_columns=(),
        )
    with pytest.raises(ValueError, match="generated rows are required"):
        build_tree_output_validation_report(
            training_rows=[{"AGEGRP": "adult"}],
            generated_rows=[],
            target_columns=("AGEGRP",),
            conditioning_columns=(),
        )
    with pytest.raises(ValueError, match="at least one target column"):
        build_tree_output_validation_report(
            training_rows=[{"AGEGRP": "adult"}],
            generated_rows=[{"AGEGRP": "adult"}],
            target_columns=(),
            conditioning_columns=(),
        )


def test_tree_output_validation_rejects_bad_weight_fields() -> None:
    with pytest.raises(ValueError, match="require a 'WEIGHT' column"):
        build_tree_output_validation_report(
            training_rows=[{"AGEGRP": "adult"}],
            generated_rows=[{"AGEGRP": "adult"}],
            target_columns=("AGEGRP",),
            conditioning_columns=(),
            weight_field="WEIGHT",
        )
    with pytest.raises(ValueError, match="training row 2 has invalid weight"):
        build_tree_output_validation_report(
            training_rows=[{"AGEGRP": "adult", "WEIGHT": "not-a-number"}],
            generated_rows=[{"AGEGRP": "adult"}],
            target_columns=("AGEGRP",),
            conditioning_columns=(),
            weight_field="WEIGHT",
        )


def test_tree_output_validation_flags_distribution_shift() -> None:
    report = build_tree_output_validation_report(
        training_rows=[{"AGEGRP": "adult"}, {"AGEGRP": "child"}],
        generated_rows=[{"AGEGRP": "adult"}, {"AGEGRP": "adult"}],
        target_columns=("AGEGRP",),
        conditioning_columns=(),
        tolerance=0.1,
    )

    assert report["passed"] is False
    assert report["issues"][0]["kind"] == "distribution_shift"
    assert report["issues"][0]["categories"] == {"AGEGRP": "adult"}
    assert safe_proportion(1.0, 0.0) == 0.0


def test_cli_validates_tree_output_as_json(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    training_path = tmp_path / "person-training.csv"
    generated_path = tmp_path / "synthetic-people.csv"
    write_csv(
        training_path,
        ["AGEGRP", "SEX", "WEIGHT"],
        [
            {"AGEGRP": "adult", "SEX": "F", "WEIGHT": "2"},
            {"AGEGRP": "child", "SEX": "M", "WEIGHT": "1"},
        ],
    )
    write_csv(
        generated_path,
        ["synthetic_id", "AGEGRP", "SEX"],
        [
            {"synthetic_id": "1", "AGEGRP": "adult", "SEX": "F"},
            {"synthetic_id": "2", "AGEGRP": "adult", "SEX": "F"},
            {"synthetic_id": "3", "AGEGRP": "child", "SEX": "M"},
        ],
    )

    assert (
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                "AGEGRP,SEX",
                "--weight-field",
                "WEIGHT",
                "--tolerance",
                "0",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["generated_records"] == 3
    assert report["max_abs_proportion_delta"] == 0.0


def test_cli_validates_tree_output_as_table_and_reports_failures(
    tmp_path: Path,
    capsys,
) -> None:
    from synthpopcan.cli import main

    training_path = tmp_path / "person-training.csv"
    generated_path = tmp_path / "synthetic-people.csv"
    write_csv(training_path, ["AGEGRP"], [{"AGEGRP": "adult"}])
    write_csv(generated_path, ["AGEGRP"], [{"AGEGRP": "adult"}])

    assert (
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                "AGEGRP",
            ]
        )
        == 0
    )
    assert "Tree Output Validation" in capsys.readouterr().out

    write_csv(generated_path, ["AGEGRP"], [{"AGEGRP": "child"}])
    with pytest.raises(ClickException, match="distribution shifts"):
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                "AGEGRP",
            ]
        )


def test_cli_tree_output_wraps_bad_target_column_input(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    training_path = tmp_path / "person-training.csv"
    generated_path = tmp_path / "synthetic-people.csv"
    write_csv(training_path, ["AGEGRP"], [{"AGEGRP": "adult"}])
    write_csv(generated_path, ["AGEGRP"], [{"AGEGRP": "adult"}])

    with pytest.raises(ClickException, match="at least one target columns"):
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                " , ",
            ]
        )


def test_cli_tree_output_wraps_report_validation_errors(tmp_path: Path) -> None:
    from click import ClickException

    from synthpopcan.cli import main

    training_path = tmp_path / "person-training.csv"
    generated_path = tmp_path / "synthetic-people.csv"
    write_csv(training_path, ["AGEGRP"], [{"AGEGRP": "adult"}])
    write_csv(generated_path, ["AGEGRP"], [{"AGEGRP": "adult"}])

    with pytest.raises(ClickException, match="WEIGHT"):
        main(
            [
                "validate",
                "tree-output",
                "--generated",
                str(generated_path),
                "--training",
                str(training_path),
                "--target-columns",
                "AGEGRP",
                "--weight-field",
                "WEIGHT",
            ]
        )


def test_cli_linked_output_wraps_validation_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from click import ClickException

    import synthpopcan.cli as cli

    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    write_csv(households_path, ["household_id"], [{"household_id": "h1"}])
    write_csv(persons_path, ["household_id"], [{"household_id": "h1"}])

    def fail_validation(**_kwargs):
        raise ValueError("linked validation failed")

    monkeypatch.setattr(cli, "validate_linked_population", fail_validation)

    with pytest.raises(ClickException, match="linked validation failed"):
        cli.main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
                "--household-id-column",
                "household_id",
                "--person-household-id-column",
                "household_id",
                "--household-size-column",
                "household_size",
            ]
        )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
