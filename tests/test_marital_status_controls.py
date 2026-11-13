"""Exercise explicit age-15+ targets through the CLI command."""

import csv
import json

import pytest
from click.testing import CliRunner

from synthpopcan.cli import cli
from synthpopcan.geography import statcan_geography_identity


@pytest.mark.parametrize("vintage,field", [(2016, "MarStH"), (2021, "MARSTH")])
@pytest.mark.parametrize("wrong_total", [False, True])
def test_marital_status_calibration(tmp_path, vintage, field, wrong_total):
    households = tmp_path / "seed-h.csv"
    persons = tmp_path / "seed-p.csv"
    household_controls = tmp_path / "household-controls.csv"
    person_controls = tmp_path / "person-controls.csv"
    marital_controls = tmp_path / "marital.json"
    output = tmp_path / "output"
    geography = statcan_geography_identity(vintage, "ct", "4620001.00")
    households.write_text("synthetic_household_id,household_size\nh1,2\nh2,1\nh3,1\n")
    persons.write_text(
        f"synthetic_person_id,synthetic_household_id,AGEGRP,{field},group\n"
        "p1,h1,adult,m,all\np2,h1,child,,all\np3,h2,adult,s,all\np4,h3,adult,o,all\n"
    )
    household_controls.write_text(
        "margin,dimensions,ct,household_size,count\n"
        'size,"ct,household_size",4620001.00,1,1\n'
        'size,"ct,household_size",4620001.00,2,1\n'
    )
    person_controls.write_text(
        'margin,dimensions,ct,group,count\npeople,"ct,group",4620001.00,all,3\n'
    )
    marital_controls.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-marital-status-controls-v1",
                "age_eligibility": {"adult": True, "child": False},
                "crosswalk": {"m": "married", "s": "single", "o": "other"},
                "targets": [
                    {
                        "geography": geography.as_dict(),
                        "all_private_household_persons": 3,
                        "age_15_plus_persons": 2,
                        "under_15_persons": 1,
                        "under_15_not_applicable": 1,
                        "source_evidence": "fictional independent denominator",
                        "eligible_counts": {
                            "married": 1,
                            "single": 2 if wrong_total else 1,
                            "other": 0,
                        },
                    }
                ],
            }
        )
    )
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(households),
            "--persons",
            str(persons),
            "--controls",
            str(household_controls),
            "--person-controls",
            str(person_controls),
            "--marital-status-controls",
            str(marital_controls),
            "--geo-dimension",
            "ct",
            "--census-vintage",
            str(vintage),
            "--geo-level",
            "ct",
            "--geo-namespace",
            geography.identifier_namespace,
            "--out",
            str(output),
        ],
    )
    if wrong_total:
        assert result.exit_code == 1
        assert "age-15+ denominator" in result.output
        assert not (output / "persons.csv").exists()
        return

    assert result.exit_code == 0, result.output
    with (output / "persons.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_source = {row["source_candidate_person_id"]: row for row in rows}
    assert {key: row["marital_status_15_plus"] for key, row in by_source.items()} == {
        "p1": "married",
        "p2": "under_15_not_applicable",
        "p3": "single",
    }
    assert (
        by_source["p1"]["synthetic_household_id"]
        == by_source["p2"]["synthetic_household_id"]
    )
    report = json.loads((output / "report.json").read_text())
    assert report["summary"]["converged_count"] == 1
    assert report["summary"]["realized_max_abs_error"] == 0
    assert report["marital_status_controls"]["sha256"]
