import json
from pathlib import Path

from synthpopcan.cli import main
from synthpopcan.localdata import _metadata_path, inspect_local_data_layout


def test_inspects_expected_local_data_layout(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    hierarchical_metadata = (
        data_root
        / "raw"
        / "statcan"
        / "2016-census"
        / "metadata"
        / "statcan-2016-hierarchical-pumf"
        / "variable-labels.json"
    )
    hierarchical_metadata.parent.mkdir(parents=True)
    hierarchical_metadata.write_text(
        json.dumps(
            {
                "variable_count": 116,
                "variables": {
                    "HH_ID": {"label": "Key for household table"},
                    "PP_ID": {"label": "Key for person table"},
                },
            }
        )
    )

    checks = inspect_local_data_layout(data_root)

    statuses = {check.name: check.status for check in checks}
    assert statuses["Raw data directory"] == "found"
    assert statuses["2016 hierarchical metadata"] == "found"
    assert statuses["2016 individual metadata"] == "missing"
    hierarchical_check = next(
        check for check in checks if check.name == "2016 hierarchical metadata"
    )
    assert hierarchical_check.detail == "116 variable labels"


def test_inspects_variable_metadata_edge_cases(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    hierarchical_path = _metadata_path(data_root, "statcan-2016-hierarchical-pumf")
    individual_path = _metadata_path(data_root, "statcan-2016-individual-pumf")
    hierarchical_path.parent.mkdir(parents=True)
    individual_path.parent.mkdir(parents=True)
    hierarchical_path.write_text(
        json.dumps({"variables": {"AGEGRP": {"label": "Age group"}}})
    )
    individual_path.write_text("{")
    profile_path = (
        data_root
        / "raw"
        / "statcan"
        / "2016-census"
        / "Census Tract Summaries 2016"
        / "98-401-X2016043_eng_CSV"
        / "98-401-X2016043_English_meta.txt"
    )
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text("metadata")

    checks = {check.name: check for check in inspect_local_data_layout(data_root)}

    assert checks["2016 hierarchical metadata"].detail == "1 variable labels"
    assert checks["2016 individual metadata"].status == "problem"
    assert checks["2016 individual metadata"].detail == "invalid JSON"
    assert checks["2016 Census Profile tract metadata"].status == "found"


def test_inspects_variable_metadata_missing_labels(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    hierarchical_path = _metadata_path(data_root, "statcan-2016-hierarchical-pumf")
    hierarchical_path.parent.mkdir(parents=True)
    hierarchical_path.write_text(json.dumps({"source": "metadata"}))

    checks = {check.name: check for check in inspect_local_data_layout(data_root)}

    assert checks["2016 hierarchical metadata"].status == "problem"
    assert checks["2016 hierarchical metadata"].detail == "missing variable labels"


def test_cli_data_doctor_reports_layout_as_json(tmp_path: Path, capsys) -> None:
    data_root = tmp_path / "data"
    (data_root / "raw").mkdir(parents=True)

    assert (
        main(
            [
                "data",
                "doctor",
                "--data-root",
                str(data_root),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["data_root"] == str(data_root)
    assert payload["checks"][0]["name"] == "Raw data directory"
    assert payload["checks"][0]["status"] == "found"
    assert any(
        check["name"] == "2016 hierarchical metadata"
        and check["status"] == "missing"
        and "variable-labels.json" in check["tip"]
        for check in payload["checks"]
    )


def test_cli_data_doctor_reports_human_readable_table(tmp_path: Path, capsys) -> None:
    data_root = tmp_path / "data"

    assert main(["data", "doctor", "--data-root", str(data_root)]) == 0

    output = capsys.readouterr().out
    assert "Local Data Check" in output
    assert "Raw data directory" in output
    assert "Missing" in output
    assert "Create data/raw or pass" in output
    assert "--data-root PATH" in output


def test_cli_data_doctor_uses_environment_data_root(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    data_root = tmp_path / "env-data"
    (data_root / "raw").mkdir(parents=True)
    monkeypatch.setenv("SYNTHPOPCAN_DATA_ROOT", str(data_root))

    assert main(["data", "doctor", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["data_root"] == str(data_root)
    assert payload["checks"][0]["status"] == "found"


def test_cli_data_doctor_option_overrides_environment_data_root(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    env_root = tmp_path / "env-data"
    option_root = tmp_path / "option-data"
    (env_root / "raw").mkdir(parents=True)
    (option_root / "raw").mkdir(parents=True)
    monkeypatch.setenv("SYNTHPOPCAN_DATA_ROOT", str(env_root))

    assert (
        main(
            [
                "data",
                "doctor",
                "--data-root",
                str(option_root),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["data_root"] == str(option_root)
