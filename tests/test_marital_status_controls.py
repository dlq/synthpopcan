"""Exercise explicit age-15+ targets through the CLI command."""

import csv
import json

import pytest
from click.testing import CliRunner

from synthpopcan._marital_status_packs import prepare_pack_targets
from synthpopcan.cli import cli
from synthpopcan.geography import statcan_geography_identity, statcan_geography_universe


@pytest.mark.parametrize("vintage,field", [(2016, "MarStH"), (2021, "MARSTH")])
@pytest.mark.parametrize("case", ["json", "wrong-total", "built-in", "suppressed"])
def test_marital_status_calibration(tmp_path, vintage, field, case):
    built_in = case in {"built-in", "suppressed"}
    wrong_total = case == "wrong-total"
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
    pack_args = []
    if built_in:
        persons.write_text(
            f"synthetic_person_id,synthetic_household_id,AGEGRP,{field},group\n"
            "p1,h1,3,2,all\np2,h1,2,8,all\np3,h2,3,1,all\np4,h3,3,4,all\n"
        )
        household_controls.write_text(
            "margin,dimensions,ct,household_size,count\n"
            'size,"ct,household_size",4620001.00,1,5\n'
            'size,"ct,household_size",4620001.00,2,5\n'
        )
        person_controls.write_text(
            person_controls.read_text().replace(",all,3", ",all,15")
        )
        marital_controls = tmp_path / "marital.csv"
        observed = {(1, 1): 15, (1, 2): 5, (1, 3): 10, (3, 3): 5, (6, 3): 5}
        with marital_controls.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ct", "marital_status", "age_20", "value"])
            for status in (1, 3, 4, 6, 7, 8, 9):
                ages = (1, 2, 3, *range(6, 16)) if status == 1 else (3, *range(6, 16))
                for age in ages:
                    value = observed.get((status, age), 0)
                    if case == "suppressed" and (status, age) == (9, 3):
                        value = ""
                    writer.writerow(["4620001.00", status, age, value])
        pack_args = ["--control-pack", f"statcan-{vintage}-marital-status-ct-v1"]
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
            *pack_args,
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
    if case == "suppressed":
        assert result.exit_code == 1
        assert "unavailable or invalid" in result.output
        assert not (output / "persons.csv").exists()
        return
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
        "p3": "never_married" if built_in else "single",
    }
    assert (
        by_source["p1"]["synthetic_household_id"]
        == by_source["p2"]["synthetic_household_id"]
    )
    report = json.loads((output / "report.json").read_text())
    assert report["summary"]["converged_count"] == 1
    assert report["summary"]["realized_max_abs_error"] == 0
    if built_in:
        evidence = report["marital_status_controls"]
        assert evidence["pack"] == pack_args[1]
        assert evidence["input"]["sha256"]
        assert len(rows) == 15
        assert (
            evidence["geographies"]["4620001.00"]["eligible_targets"]["common_law"] == 0
        )
    else:
        assert report["marital_status_controls"]["sha256"]


def test_builtin_reconciles_rounding_without_filling_published_zeros(tmp_path):
    source = tmp_path / "source.csv"
    # The adult age total is 20, but the age cells sum to 25 versus
    # an all-ages total of 30. The marital cells sum to 15.
    observed = {(1, 1): 30, (1, 2): 5, (1, 3): 20, (3, 3): 10, (6, 3): 5}
    with source.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ct", "marital_status", "age_20", "value"])
        for status in (1, 3, 4, 6, 7, 8, 9):
            ages = (1, 2, 3, *range(6, 16)) if status == 1 else (3, *range(6, 16))
            for age in ages:
                writer.writerow(
                    ["4620053.00", status, age, observed.get((status, age), 0)]
                )
    targets, report = prepare_pack_targets(
        "statcan-2021-marital-status-ct-v1",
        source,
        statcan_geography_universe(2021, "ct", "ct"),
        {"4620053.00"},
    )
    target = targets["4620053.00"]
    assert target.under_15_count == 6
    assert target.eligible_counts == {
        "never_married": 8,
        "married": 16,
        "common_law": 0,
        "separated_divorced_widowed": 0,
    }
    assert report["geographies"]["4620053.00"]["source_age_15_plus"] == 20

    source.write_text(
        source.read_text().replace("4620053.00,1,1,30", "4620053.00,1,1,100")
    )
    with pytest.raises(ValueError, match="rounding envelope"):
        prepare_pack_targets(
            "statcan-2021-marital-status-ct-v1",
            source,
            statcan_geography_universe(2021, "ct", "ct"),
            {"4620053.00"},
        )
