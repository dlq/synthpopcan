import csv
import json
import shutil
from pathlib import Path

from synthpopcan.cli import main


def test_microdata_seed_to_validated_ipf_weights_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    microdata_path = tmp_path / "hierarchical.csv"
    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    microdata_path.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,1,adult,F,owner\n"
        "1,11,111,11102,1,child,M,owner\n"
    )
    controls_path.write_text(
        "margin,dimensions,AGEGRP,SEX,count\n"
        "age,AGEGRP,adult,,100\n"
        "age,AGEGRP,child,,100\n"
        "sex,SEX,,F,100\n"
        "sex,SEX,,M,100\n"
    )

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(seed_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--weight-field",
                "WEIGHT",
                "--out",
                str(weights_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
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

    seed_rows = list(csv.DictReader(seed_path.open(newline="")))
    weight_rows = list(csv.DictReader(weights_path.open(newline="")))
    validation_report = json.loads(capsys.readouterr().out)

    assert seed_rows == [
        {"PP_ID": "11101", "AGEGRP": "adult", "SEX": "F", "WEIGHT": "1"},
        {"PP_ID": "11102", "AGEGRP": "child", "SEX": "M", "WEIGHT": "1"},
    ]
    assert [row["weight"] for row in weight_rows] == ["100", "100"]
    assert json.loads(report_path.read_text())["converged"] is True
    assert validation_report["passed"] is True


def test_tracked_microdata_ipf_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/workflows/microdata_ipf")
    microdata_path = tmp_path / "hierarchical.csv"
    controls_path = tmp_path / "controls.csv"
    seed_path = tmp_path / "seed.csv"
    weights_path = tmp_path / "weights.csv"
    report_path = tmp_path / "fit-report.json"

    shutil.copyfile(fixture_root / "hierarchical.csv", microdata_path)
    shutil.copyfile(fixture_root / "controls.csv", controls_path)

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(seed_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert seed_path.read_text() == (fixture_root / "expected-seed.csv").read_text()

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed_path),
                "--controls",
                str(controls_path),
                "--weight-field",
                "WEIGHT",
                "--out",
                str(weights_path),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

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


def test_tracked_microdata_tree_tutorial_fixture_workflow(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_root = Path("tests/fixtures/workflows/microdata_tree")
    microdata_path = tmp_path / "hierarchical.csv"
    training_path = tmp_path / "person-training.csv"
    model_path = tmp_path / "person-model.json"
    generated_path = tmp_path / "synthetic-people.csv"

    shutil.copyfile(fixture_root / "hierarchical.csv", microdata_path)

    assert (
        main(
            [
                "microdata",
                "export-training",
                str(microdata_path),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--out",
                str(training_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        training_path.read_text()
        == (fixture_root / "expected-person-training.csv").read_text()
    )

    assert (
        main(
            [
                "tree",
                "train",
                str(training_path),
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--weight-column",
                "WEIGHT",
                "--out",
                str(model_path),
                "--random-seed",
                "7",
            ]
        )
        == 0
    )
    capsys.readouterr()

    model = json.loads(model_path.read_text())
    assert model["model_type"] == "conditional-frequency"
    assert model["privacy"]["contains_raw_rows"] is False

    assert (
        main(
            [
                "tree",
                "generate",
                str(model_path),
                "--rows",
                "2",
                "--condition",
                "TENUR=owner",
                "--condition",
                "household_size=2",
                "--out",
                str(generated_path),
            ]
        )
        == 0
    )

    generated_rows = list(csv.DictReader(generated_path.open(newline="")))
    assert generated_rows == [
        {
            "synthetic_id": "1",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "adult",
            "SEX": "F",
        },
        {
            "synthetic_id": "2",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "adult",
            "SEX": "F",
        },
    ]
