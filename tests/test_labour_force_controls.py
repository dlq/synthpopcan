"""Labour-force and annual work-activity Profile calibration."""

import csv
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from synthpopcan.api import LinkedPopulationFiles, calibrate_small_area
from synthpopcan.cli import cli
from synthpopcan.geography import statcan_geography_universe


@pytest.mark.parametrize("year", [2016, 2021])
@pytest.mark.parametrize(
    ("family", "case"),
    [
        (family, case)
        for family in ("labour-force", "work-activity")
        for case in ("valid", "suppressed", "companion", "duplicate")
    ]
    + [
        ("work-activity", case)
        for case in (
            "rounding",
            "adult_not_applicable",
            "wrong_vintage",
            "wrong_family",
            "wrong_broad_pack",
            "wrong_total",
            "missing_count",
            "wrong_under_15",
            "wrong_geography",
        )
    ],
)
def test_labour_profile_calibration(tmp_path, year, family, case):
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
    first_code, second_code = 1, 8
    if family == "work-activity":
        field = "WRKACT"
        first_code, second_code = 2, 11
        members = (
            [1135, 1873, 672, 1683, 1874, 1876, 1877, 1865]
            if year == 2016
            else [1522, 2231, 126, 1998, 2232, 2234, 2235, 2223]
        )
        values.append(15)
        if case == "rounding":
            values[4] = 30
        if case == "adult_not_applicable":
            first_code = 99
    pack_suffix = "labour-force-status" if family == "labour-force" else family
    output_field = pack_suffix.replace("-", "_")
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
        f"p1,a,3,{first_code},all\np2,b,12,{second_code},all\n"
        f"p3,c,3,{first_code},all\np4,c,2,99,all\n"
    )
    hc.write_text(
        f"margin,dimensions,ct,household_size,count\n"
        f'size,"ct,household_size",{tract},1,10\n'
        f'size,"ct,household_size",{tract},2,5\n'
    )
    pc.write_text(
        f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all,20\n'
    )
    if case == "wrong_total":
        pc.write_text(
            f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all,25\n'
        )
    if case == "missing_count":
        pc.write_text(
            f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all\n'
        )
    if case == "wrong_under_15":
        pc.write_text(
            f"margin,dimensions,ct,age_group_3,count\n"
            f'age,"ct,age_group_3",{tract},0_14,10\n'
            f'age,"ct,age_group_3",{tract},15_64,10\n'
        )
    if case == "wrong_geography":
        pc.write_text(
            'margin,dimensions,ct,group,count\npeople,"ct,group",4620054.00,all,20\n'
        )
    pack_year = (2021 if year == 2016 else 2016) if case == "wrong_vintage" else year
    if case == "wrong_family":
        pack_suffix = "education"
    out = tmp_path / "out"
    args = [
        "geo",
        "calibrate",
        str(hh),
        "--persons",
        str(pp),
        "--controls",
        str(hc),
        "--person-controls",
        str(pc),
        f"--{family}-pack",
        f"statcan-{pack_year}-{pack_suffix}-ct-v1",
        f"--{family}-profile",
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
    ]
    if case == "wrong_broad_pack":
        args.extend(["--control-pack", f"statcan-{year}-core-private-household-ct-v1"])
    runner = CliRunner()
    if case == "valid":
        result = runner.invoke(cli, args)
    else:
        with patch("synthpopcan.small_area_synthesis.fit_linked_by_geography") as fit:
            result = runner.invoke(cli, args)
            fit.assert_not_called()
    if case != "valid":
        assert result.exit_code == 1, result.output
        expected = {
            "suppressed": "unavailable or invalid",
            "companion": "denominators",
            "duplicate": "duplicate",
            "rounding": "rounding envelope",
            "adult_not_applicable": "unsupported eligible WRKACT",
            "wrong_vintage": "matching Statistics Canada CT geography",
            "wrong_family": "Unknown work-activity pack",
            "wrong_broad_pack": "requires broad pack",
            "wrong_total": "private-household person total",
            "missing_count": "has invalid count",
            "wrong_under_15": "under-15 target",
            "wrong_geography": "missing work activity Profile rows",
        }
        assert expected[case] in result.output
        assert not (out / "persons.csv").exists()
        return
    assert result.exit_code == 0, result.output
    report = json.loads((out / "report.json").read_text())
    provenance = report[f"{output_field}_controls"]
    inspected = runner.invoke(cli, ["geo", "control-packs", "show", provenance["pack"]])
    assert inspected.exit_code == 0, inspected.output
    assert provenance["pack_definition"] == json.loads(inspected.output)
    evidence = provenance["geographies"][tract]
    assert evidence["under_15_target"] == 5
    categories = (
        ("employed", "unemployed", "not_in_labour_force")
        if family == "labour-force"
        else ("did_not_work", "full_year_full_time", "part_year_or_part_time")
    )
    assert evidence["eligible_targets"] == dict(zip(categories, (8, 7, 0), strict=True))
    assert report["summary"]["realized_max_abs_error"] == 0
    kwargs = (
        {"labour_force_pack": provenance["pack"], "labour_force_profile_path": profile}
        if family == "labour-force"
        else {
            "work_activity_pack": provenance["pack"],
            "work_activity_profile_path": profile,
        }
    )
    python_result = calibrate_small_area(
        LinkedPopulationFiles(households=hh, persons=pp),
        hc,
        person_controls=pc,
        geography_dimension="ct",
        geography_universe=statcan_geography_universe(year, "ct", "ct"),
        output_dir=tmp_path / "python-out",
        integerization="swap",
        **kwargs,
    )
    python_report = json.loads(python_result.report_path.read_text())
    assert python_report[f"{output_field}_controls"] == provenance
    assert python_report["summary"]["realized_max_abs_error"] == 0
