"""Labour-force Profile parsing and linked conditional calibration."""

import csv
import json

import pytest
from click.testing import CliRunner

from synthpopcan.cli import cli


@pytest.mark.parametrize("year", [2016, 2021])
@pytest.mark.parametrize("case", ["valid", "suppressed", "companion", "duplicate"])
def test_labour_force_calibration(tmp_path, year, case):
    tract = "4620053.00"
    profile = tmp_path / "profile.csv"
    if year == 2016:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "GEO_CODE (POR)",
            "Member ID: Profile of Census Tracts (2247)",
            "Dim: Sex (3): Member ID: [1]: Total - Sex",
        ]
        prefix = [year, 2, tract]
        members = [1135, 1865, 672, 1683, 1867, 1868, 1869]
    else:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "ALT_GEO_CODE",
            "DGUID",
            "CHARACTERISTIC_ID",
            "C1_COUNT_TOTAL",
            "SYMBOL",
        ]
        prefix = [year, "Census tract", tract, f"2021S0507{tract}"]
        members = [1522, 2223, 126, 1998, 2225, 2226, 2227]
    values = [20, 15, 15, 5 if case == "companion" else 15, 5, 5, 0]
    field = "LFTAG" if year == 2016 else "LFACT"
    rows = [
        [*prefix, member, value, "x" if case == "suppressed" and i == 4 else ""]
        if year == 2021
        else [*prefix, member, "x" if case == "suppressed" and i == 4 else value]
        for i, (member, value) in enumerate(zip(members, values, strict=True))
    ]
    if case == "duplicate":
        rows.append(rows[-1])
    with profile.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    hh, pp, hc, pc = [tmp_path / f"{name}.csv" for name in ("hh", "pp", "hc", "pc")]
    hh.write_text("synthetic_household_id,household_size\na,1\nb,1\nc,2\n")
    pp.write_text(
        f"synthetic_person_id,synthetic_household_id,AGEGRP,{field},group\n"
        "p1,a,3,1,all\np2,b,12,8,all\np3,c,3,1,all\np4,c,2,99,all\n"
    )
    hc.write_text(
        f"margin,dimensions,ct,household_size,count\n"
        f'size,"ct,household_size",{tract},1,10\n'
        f'size,"ct,household_size",{tract},2,5\n'
    )
    pc.write_text(
        f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all,20\n'
    )
    out = tmp_path / "out"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(hh),
            "--persons",
            str(pp),
            "--controls",
            str(hc),
            "--person-controls",
            str(pc),
            "--labour-force-pack",
            f"statcan-{year}-labour-force-status-ct-v1",
            "--labour-force-profile",
            str(profile),
            "--geo-dimension",
            "ct",
            "--census-vintage",
            str(year),
            "--geo-level",
            "ct",
            "--geo-namespace",
            f"statcan:census:{year}:ct",
            "--integerization",
            "swap",
            "--include-weights",
            "--out",
            str(out),
        ],
    )
    if case != "valid":
        assert result.exit_code == 1, result.output
        expected = {
            "suppressed": "unavailable or invalid",
            "companion": "denominators",
            "duplicate": "duplicate labour-force status",
        }
        assert expected[case] in result.output
        assert not (out / "persons.csv").exists()
        return
    assert result.exit_code == 0, result.output
    report = json.loads((out / "report.json").read_text())
    evidence = report["labour_force_status_controls"]["geographies"][tract]
    assert evidence["under_15_target"] == 5
    assert evidence["eligible_targets"]["employed"] == 8
    assert evidence["eligible_targets"]["unemployed"] == 7
    assert evidence["eligible_targets"]["not_in_labour_force"] == 0
    assert report["summary"]["realized_max_abs_error"] == 0
