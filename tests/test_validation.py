import csv
import json
from pathlib import Path

import pytest
from click.exceptions import ClickException

from synthpopcan.controls import read_control_table
from synthpopcan.validation import build_control_validation_report


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


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
