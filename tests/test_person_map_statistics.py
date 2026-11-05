"""Independent person-record denominators and CLI population-map checks."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from support.map_fixtures import _write_fake_geojson

from synthpopcan._person_map_statistics import compute_person_statistics
from synthpopcan.cli import cli
from synthpopcan.map_render import _person_variable_specs


def _people(path: Path) -> None:
    records = [
        dict(
            synthetic_person_id="child",
            ct="G1",
            AGEGRP="1",
            GENDER="1",
            HDGREE="7",
            LFACT="1",
            TOTINC="900000",
            EMPIN="900000",
        ),
        dict(
            synthetic_person_id="adult",
            ct="G1",
            AGEGRP="4",
            GENDER="1",
            HDGREE="7",
            LFACT="1",
            TOTINC="0",
            EMPIN="0",
        ),
        dict(
            synthetic_person_id="senior",
            ct="G1",
            AGEGRP="12",
            GENDER="2",
            HDGREE="1",
            LFACT="9",
            TOTINC="-100",
            EMPIN="-25",
        ),
        dict(
            synthetic_person_id="missing",
            ct="G1",
            AGEGRP="13",
            GENDER="8",
            HDGREE="88",
            LFACT="14",
            TOTINC="88888888",
            EMPIN="99999999",
        ),
        dict(
            synthetic_person_id="unknown-age",
            ct="G1",
            AGEGRP="88",
            GENDER="2",
            HDGREE="7",
            LFACT="1",
            TOTINC="900000",
            EMPIN="900000",
        ),
        dict(
            synthetic_person_id="elsewhere",
            ct="G2",
            AGEGRP="3",
            GENDER="2",
            HDGREE="2",
            LFACT="2",
            TOTINC="1000",
            EMPIN="800",
        ),
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def test_person_attributes_use_people_and_age_eligible_known_denominators(tmp_path):
    path = tmp_path / "people.csv"
    _people(path)
    stats = compute_person_statistics(path, "ct")
    first = stats["G1"]
    assert first["n_persons"] == 5
    assert first["n_persons_15_plus"] == 3
    assert first["pct_age_0_14"] == 25
    assert first["pct_age_65_plus"] == 50
    assert first["pct_women"] == 50
    assert first["pct_women_n"] == 4
    assert first["pct_women_eligible"] == 5
    assert first["pct_bachelor_plus"] == 50
    assert first["pct_bachelor_plus_n"] == 2
    assert first["pct_bachelor_plus_eligible"] == 3
    assert first["employment_rate"] == 33.33
    assert first["participation_rate"] == 66.67
    assert first["unemployment_rate"] == 50
    assert first["unemployment_rate_n"] == 2
    assert first["median_personal_income"] == -50
    assert first["median_personal_income_n"] == 2
    assert first["median_employment_income"] == -12.5
    assert stats["G2"]["n_persons"] == 1
    assert stats["G2"]["median_personal_income"] == 1000
    assert first["pct_immigrants"] is None
    specs = _person_variable_specs(stats)
    assert "pct_immigrants" not in {v["field"] for v in specs}
    unemployment = next(v for v in specs if v["field"] == "unemployment_rate")
    assert "labour-force participants" in unemployment["note"]


def test_cli_population_profile_reads_person_csv_without_household_data(tmp_path):
    persons = tmp_path / "people.csv"
    _people(persons)
    boundary = tmp_path / "boundary.geojson"
    _write_fake_geojson(boundary, ["G1", "G2"])
    data = json.loads(boundary.read_text())
    for feature in data["features"]:
        feature["properties"]["LANDAREA"] = 2
    boundary.write_text(json.dumps(data))
    out = tmp_path / "map.html"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "map",
            str(persons),
            "--person-profile",
            "statcan-hierarchical-2021",
            "--boundaries",
            str(boundary),
            "--geo-column",
            "ct",
            "--census-vintage",
            "2021",
            "--geo-level",
            "ct",
            "--geo-namespace",
            "statcan:census:2021:ct",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    html = out.read_text()
    data = json.loads(re.search(r"const GEOJSON = (.*);", html)[1])
    first = data["features"][0]["properties"]
    assert first["n_persons"] == 5
    assert first["persons_per_km2"] == 2.5
    assert first["median_personal_income"] == -50
    assert "n_households" not in first
    assert "pct_owner" not in html
    assert "median_personal_income" in html
    assert 'const VARIABLES = [{"field":"persons_per_km2"' in html
    assert "Denominator:" in html


@pytest.mark.parametrize(
    "header,row,message",
    [
        ("synthetic_person_id,ct\n", "p1,G1\n", "AGEGRP"),
        ("synthetic_person_id,ct,AGEGRP\n", "p1,,4\n", "assign geography"),
    ],
)
def test_person_map_rejects_missing_required_person_inputs(
    tmp_path, header, row, message
):
    path = tmp_path / "people.csv"
    path.write_text(header + row)
    with pytest.raises(ValueError, match=message):
        compute_person_statistics(path, "ct")


def test_source_categories_and_overlapping_language_responses(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text(
        "synthetic_person_id,ct,AGEGRP,CITIZEN,IMMSTAT,GENSTAT,VISMIN,MTNEN,MTNFR,FPTWK\n"
        "p1,G1,4,3,2,1,1,1,1,1\n"
        "p2,G1,1,1,1,4,0,0,1,1\n"
        "p3,G1,12,2,3,2,8,1,0,2\n"
    )
    result = compute_person_statistics(path, "ct")["G1"]
    assert result["pct_canadian_citizens"] == 66.67
    assert result["pct_immigrants"] == 33.33
    assert result["pct_nonpermanent_residents"] == 33.33
    assert result["pct_first_generation"] == 33.33
    assert result["pct_second_generation"] == 33.33
    assert result["pct_third_generation"] == 33.33
    assert result["pct_visible_minority"] == 50
    assert result["pct_mother_tongue_english"] == 66.67
    assert result["pct_mother_tongue_french"] == 66.67
    assert result["pct_full_time_2020"] == 50


def test_unemployment_is_unknown_without_labour_force_participants(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text("synthetic_person_id,ct,AGEGRP,LFACT\np1,G1,13,14\n")
    result = compute_person_statistics(path, "ct")["G1"]
    assert result["unemployment_rate"] is None
    assert result["unemployment_rate_n"] == 0
    assert result["employment_rate"] == 0
    assert result["participation_rate"] == 0


def test_cli_person_profile_rejects_national_plan(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    result = CliRunner().invoke(
        cli, ["geo", "map", str(plan), "--person-profile", "statcan-hierarchical-2021"]
    )
    assert result.exit_code == 2
    assert "rather than a national plan" in result.output


@pytest.mark.parametrize(
    "field,metric",
    [("MTNNO", "pct_mother_tongue_other"), ("HLMOSTNO", "pct_home_language_other")],
)
def test_nonofficial_language_uses_categorical_codes_and_excludes_unavailable(
    tmp_path, field, metric
):
    path = tmp_path / "people.csv"
    path.write_text(
        f"synthetic_person_id,ct,AGEGRP,{field}\n"
        "p1,G1,4,1\np2,G1,4,2\np3,G1,4,10\np4,G1,4,88\np5,G1,4,0\n"
    )
    result = compute_person_statistics(path, "ct")["G1"]
    assert result[metric] == 66.67
    assert result[metric + "_n"] == 3
    assert result[metric + "_eligible"] == 5


def test_every_categorical_profile_matches_governed_source_codes():
    from synthpopcan._person_map_statistics import _CATEGORIES, _METRICS

    pending = [
        json.loads(
            Path("docs/_static/hierarchical-pumf-field-eligibility-v1.json").read_text()
        )
    ]
    fields = {}
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if str(value.get("field_id", "")).startswith("2021:"):
                fields[value["source_name"]] = value
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    for category in _CATEGORIES:
        source = fields[category.field]
        excluded = set(source["missing_codes"]) | set(source["not_applicable_codes"])
        expected = {
            int(c["code"]) for c in source["categories"] if c["code"] not in excluded
        }
        assert category.valid == expected, category.field
    for metric in _METRICS:
        assert metric.positive <= metric.category.valid
        if metric.denominator is not None:
            assert metric.positive <= metric.denominator <= metric.category.valid


def test_chunked_histograms_preserve_numeric_aliases_and_exact_income_medians(
    tmp_path, monkeypatch
):
    from synthpopcan import _person_map_statistics as maps

    path = tmp_path / "people.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["synthetic_person_id", "ct", "AGEGRP", "GENDER", "TOTINC", "note"]
        )
        writer.writerow(["p1", " G1 ", "+03", "1", "2", "quoted\nnewline"])
        writer.writerow(["p2", "G1", "0003", "01", "2", ""])
        writer.writerow([])
        writer.writerow(["p3", "G1", "88", "+1", "90000", ""])
        writer.writerow(["p4", "G2", "4", "2", "-5", ""])
        writer.writerow(["p5", "G2", "4", "2", "6", ""])
        writer.writerow(["p6", "G2", "13", "2", "7", ""])
    original = maps._chunks
    monkeypatch.setattr(
        maps, "_chunks", lambda path, geography: original(path, geography, size=2)
    )
    result = maps.compute_person_statistics(path, "ct")
    assert result["G1"]["n_persons"] == 3
    assert result["G1"]["n_persons_15_plus"] == 2
    assert result["G1"]["pct_women"] == 100
    assert result["G1"]["median_personal_income"] == 2.0
    assert isinstance(result["G1"]["median_personal_income"], float)
    assert result["G1"]["median_personal_income_known"] == 2
    assert result["G2"]["median_personal_income"] == 6
    assert isinstance(result["G2"]["median_personal_income"], int)


def test_csv_record_numbers_skip_empty_records_but_keep_empty_fields(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text(
        'synthetic_person_id,ct,AGEGRP,note\np1,G1,4,"two\nlines"\n\np2,,4,\n'
    )
    with pytest.raises(ValueError, match="Person row 3 has no ct assignment"):
        compute_person_statistics(path, "ct")


def test_duplicate_source_headers_keep_last_field_and_geography_can_be_age(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text("synthetic_person_id,ct,AGEGRP,AGEGRP\np1,G1,1,4\n")
    result = compute_person_statistics(path, "ct")
    assert result["G1"]["n_persons_15_plus"] == 1
    path.write_text("synthetic_person_id,AGEGRP\np1,12\n")
    assert compute_person_statistics(path, "AGEGRP")["12"]["n_persons_15_plus"] == 1


def test_single_person_observer_matches_chunked_histograms(tmp_path):
    from synthpopcan._person_map_statistics import _People

    path = tmp_path / "people.csv"
    _people(path)
    expected = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            expected.setdefault(row["ct"], _People()).observe(row)
    assert compute_person_statistics(path, "ct") == {
        geo: values.summary() for geo, values in expected.items()
    }
