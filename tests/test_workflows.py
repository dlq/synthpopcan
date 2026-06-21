import csv
import json
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
