"""Education Profile parsing and linked conditional calibration."""

import csv
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from synthpopcan.api import LinkedPopulationFiles, calibrate_small_area
from synthpopcan.cli import cli
from synthpopcan.geography import GeographyUniverse


@pytest.mark.parametrize("year", [2016, 2021])
@pytest.mark.parametrize("case", ["valid", "suppressed", "companion", "duplicate"])
def test_education_calibration(tmp_path, year, case):
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
        members = [
            1135,
            1683,
            672,
            1684,
            1685,
            1688,
            1689,
            1690,
            1691,
            1693,
            1694,
            1695,
            1696,
            1697,
        ]
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
        members = [
            1522,
            1998,
            126,
            1999,
            2000,
            2004,
            2005,
            2006,
            2007,
            2009,
            2010,
            2011,
            2012,
            2013,
        ]
    values = [20, 15, 5 if case == "companion" else 15, 5, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0]
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
        "synthetic_person_id,synthetic_household_id,AGEGRP,HDGREE,group\n"
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
            "--education-pack",
            f"statcan-{year}-education-ct-v1",
            "--education-profile",
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
            "duplicate": "duplicate education",
        }
        assert expected[case] in result.output
        assert not (out / "persons.csv").exists()
        with patch("synthpopcan.small_area_synthesis.fit_linked_by_geography") as fit:
            with pytest.raises(ValueError, match=expected[case]):
                calibrate_small_area(
                    LinkedPopulationFiles(households=hh, persons=pp),
                    hc,
                    person_controls=pc,
                    geography_dimension="ct",
                    geography_universe=GeographyUniverse(
                        census_vintage=year,
                        geography_level="ct",
                        identifier_namespace=f"statcan:census:{year}:ct",
                        identifier_column="ct",
                    ),
                    education_pack=f"statcan-{year}-education-ct-v1",
                    education_profile_path=profile,
                    output_dir=tmp_path / "python-out",
                )
            fit.assert_not_called()
        return
    assert result.exit_code == 0, result.output
    report = json.loads((out / "report.json").read_text())
    evidence = report["education_controls"]["geographies"][tract]
    assert evidence["under_15_target"] == 5
    assert evidence["eligible_targets"]["no_credential"] == 8
    assert evidence["eligible_targets"]["university_above_bachelor"] == 7
    assert evidence["eligible_targets"]["secondary"] == 0
    assert report["summary"]["realized_max_abs_error"] == 0

    python_result = calibrate_small_area(
        LinkedPopulationFiles(households=hh, persons=pp),
        hc,
        person_controls=pc,
        geography_dimension="ct",
        geography_universe=GeographyUniverse(
            census_vintage=year,
            geography_level="ct",
            identifier_namespace=f"statcan:census:{year}:ct",
            identifier_column="ct",
        ),
        education_pack=f"statcan-{year}-education-ct-v1",
        education_profile_path=profile,
        integerization="swap",
        include_weights=True,
        output_dir=tmp_path / "python-out",
    )
    python_report = json.loads(python_result.report_path.read_text())
    assert python_report["education_controls"] == report["education_controls"]
    assert python_report["summary"]["realized_max_abs_error"] == 0


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("wrong-vintage", "matching Statistics Canada CT geography"),
        ("wrong-header", "Expected the 2021 Census Profile"),
        ("short-row", "incomplete education Profile CSV row"),
        ("wrong-dguid", "incompatible education Profile geography"),
        ("non-base-five", "is not base-five"),
        ("missing", "missing education Profile rows"),
        ("rounding", "exceed the rounding envelope"),
    ],
)
def test_education_profile_rejects_invalid_source(tmp_path, case, expected):
    from synthpopcan._education_packs import prepare_pack_targets
    from synthpopcan.geography import statcan_geography_universe

    tract = "4620053.00"
    profile = tmp_path / "profile.csv"
    header = [
        "CENSUS_YEAR",
        "GEO_LEVEL",
        "ALT_GEO_CODE",
        "DGUID",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
        "SYMBOL",
    ]
    counts = dict.fromkeys(
        [1999, 2000, 2004, 2005, 2006, 2007, 2009, 2010, 2011, 2012, 2013], 0
    )
    counts.update({1522: 20, 1998: 15, 126: 15, 1999: 15})
    if case == "wrong-header":
        header[-1] = "UNEXPECTED"
    if case == "non-base-five":
        counts[1999] = 16
    if case == "missing":
        del counts[2013]
    if case == "rounding":
        counts[1999] = 100
    dguid = "wrong" if case == "wrong-dguid" else f"2021S0507{tract}"
    with profile.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        if case == "short-row":
            writer.writerow([2021, "Census tract", tract])
        else:
            writer.writerows(
                [2021, "Census tract", tract, dguid, member, count, ""]
                for member, count in counts.items()
            )
    universe = statcan_geography_universe(
        2016 if case == "wrong-vintage" else 2021, "ct", "ct"
    )
    with pytest.raises(ValueError, match=expected):
        prepare_pack_targets("statcan-2021-education-ct-v1", profile, universe, {tract})
