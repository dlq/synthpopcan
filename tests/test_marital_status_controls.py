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


@pytest.mark.parametrize("vintage", [2016, 2021])
def test_broad_and_marital_status_tract_acceptance(tmp_path, vintage):
    from collections import Counter
    from itertools import product
    from pathlib import Path

    from synthpopcan.control_packs import (
        apply_control_pack_derivations,
        load_compatibility_registry,
        load_control_pack,
    )

    # Independently calculated from the published age and marital vectors.
    targets = {
        2016: [
            (550, 166, 182, 177, 20),
            (480, 175, 300, 90, 40),
            (475, 480, 191, 269, 85),
        ],
        2021: [
            (612, 226, 257, 165, 60),
            (498, 157, 346, 89, 35),
            (590, 600, 269, 346, 115),
        ],
    }[vintage]
    tracts = dict(zip(("4620053.00", "4620054.00", "4620056.00"), targets, strict=True))
    field = "MarStH" if vintage == 2016 else "MARSTH"
    sex = "SEX" if vintage == 2016 else "GENDER"
    pack_id = f"statcan-{vintage}-broad-ct-v1"
    marital_id = f"statcan-{vintage}-marital-status-ct-v1"
    pack = load_control_pack(pack_id)
    source = Path(__file__).parent / "fixtures" / "marital_status" / f"{vintage}.csv"

    def write_csv(path, rows):
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def read_csv(path):
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))

    categories = (
        "never_married",
        "married",
        "common_law",
        "separated_divorced_widowed",
        "under_15_not_applicable",
    )
    # The child is linked to the married adult. Duplicate candidates exercise
    # fractional weights without changing the total contribution of a profile.
    households, persons = [], []
    for category, members in (
        (1, [(1, "3")]),
        (2, [(2, "12")]),
        (3, [(3, "13")]),
        (4, [(4, "8")]),
        (5, [(2, "12"), (8, "2")]),
    ):
        for copy in range(2):
            identifier = f"h{category}-{copy}"
            households.append(
                dict(
                    synthetic_household_id=identifier,
                    household_size=str(len(members)),
                    TENUR=str(1 + category % 2),
                    DTYPE="1",
                    CONDO="0",
                    BEDRM=str(len(members)),
                    ROOM="4",
                    NOS="1",
                    BUILT="1",
                    REPAIR="1",
                )
            )
            for status, member_age in members:
                persons.append(
                    {
                        "synthetic_person_id": f"{identifier}-{status}",
                        "synthetic_household_id": identifier,
                        "AGEGRP": member_age,
                        field: str(status),
                        sex: str(1 + category % 2),
                        "CITIZEN": "1",
                        "IMMSTAT": "1",
                        "GENSTAT": "1",
                        "VISMIN": "1",
                    }
                )
    hh_path, pp_path = tmp_path / "households.csv", tmp_path / "persons.csv"
    write_csv(hh_path, households)
    write_csv(pp_path, persons)
    hh_derived, pp_derived = apply_control_pack_derivations(pack, households, persons)
    for row in pp_derived:
        row["age_group_3"] = {"2": "0_14", "12": "65_plus", "13": "65_plus"}.get(
            row["AGEGRP"], "15_64"
        )
        row["marital_status_15_plus"] = (
            categories[int(row[field]) - 1] if row["AGEGRP"] != "2" else categories[-1]
        )
    registries = {c.identifier: c for c in load_compatibility_registry().controls}
    controls = {"household": [], "person": []}
    cells = {}
    universe = {}
    for ct, counts in tracts.items():
        never, married, common, other, child = counts
        profile_counts = (never, married - child, common, other, child)
        universe[ct] = dict.fromkeys(
            ("total_population", "persons_in_private_households"), sum(counts)
        )
        cells[ct] = {
            "marital_status_15_plus": (
                ("marital_status_15_plus",),
                dict(zip(((c,) for c in categories), counts, strict=True)),
            )
        }
        for margin in pack.margins:
            unit = margin.entity_level
            dims = tuple(margin.dimensions[1:])
            name = margin.control_identifier
            expected = dict.fromkeys(
                product(
                    *(
                        [c.target_category for c in axis.categories]
                        for axis in registries[name].source_axes
                    )
                ),
                0,
            )
            for row in hh_derived if unit == "household" else pp_derived:
                identifier = row["synthetic_household_id"]
                if identifier.endswith("-0"):
                    expected[tuple(row[dim] for dim in dims)] += profile_counts[
                        int(identifier[1]) - 1
                    ]
            cells[ct][name] = (dims, expected)
            controls[unit].extend(
                {
                    "margin": name,
                    "dimensions": ",".join(("ct", *dims)),
                    "ct": ct,
                    **dict(zip(dims, category, strict=True)),
                    "count": count,
                }
                for category, count in expected.items()
            )

    def write_controls(unit):
        path = tmp_path / f"{unit}-controls.csv"
        rows = controls[unit]
        columns = dict.fromkeys(key for row in rows for key in row)
        write_csv(path, [{key: row.get(key, "") for key in columns} for row in rows])
        return path

    hh_controls, pp_controls = write_controls("household"), write_controls("person")
    universe_path, evidence_path = (
        tmp_path / "universe.json",
        tmp_path / "evidence.json",
    )
    runner = CliRunner()
    common_args = [
        "--controls",
        str(hh_controls),
        "--person-controls",
        str(pp_controls),
    ]

    def bind_evidence():
        universe_path.write_text(json.dumps(universe))
        result = runner.invoke(
            cli,
            [
                "geo",
                "control-packs",
                "evidence",
                pack_id,
                *common_args,
                "--universe-evidence",
                str(universe_path),
                "--out",
                str(evidence_path),
            ],
        )
        assert result.exit_code == 0, result.output

    def calibrate(name, marital_source=source, conditional_pack=marital_id):
        output = tmp_path / name
        result = runner.invoke(
            cli,
            [
                "geo",
                "calibrate",
                str(hh_path),
                "--persons",
                str(pp_path),
                *common_args,
                "--control-pack",
                pack_id,
                "--control-pack-evidence",
                str(evidence_path),
                "--marital-status-pack",
                conditional_pack,
                "--marital-status-controls",
                str(marital_source),
                "--geo-dimension",
                "ct",
                "--include-weights",
                "--out",
                str(output),
            ],
        )
        return result, output

    bind_evidence()
    result, output = calibrate("joint")
    assert result.exit_code == 0, (result.output, result.exception)
    report = json.loads((output / "report.json").read_text())
    assert report["control_pack_plan"]["passed"]
    realized_households = read_csv(output / "households.csv")
    realized_persons = read_csv(output / "persons.csv")
    weights = {
        (r["target_geography"], r["source_candidate_household_id"]): float(r["weight"])
        for r in read_csv(output / "weights.csv")
    }
    lookup = {r["synthetic_household_id"]: r["ct"] for r in realized_households}
    assert all(lookup[r["synthetic_household_id"]] == r["ct"] for r in realized_persons)
    assert Counter(r["synthetic_household_id"] for r in realized_persons) == {
        r["synthetic_household_id"]: int(r["household_size"])
        for r in realized_households
    }
    for ct, margins in cells.items():
        tract_report = report["geographies"][ct]
        assert tract_report["converged"]
        fractional = {
            r["name"]: r["max_abs_error"] for r in tract_report["margin_summaries"]
        }
        realized = {
            r["name"]: r["max_abs_error"]
            for r in tract_report["realized_margin_summaries"]
        }
        assert fractional.keys() == realized.keys() == margins.keys()
        for name, (dims, expected) in margins.items():
            is_household = name in {
                m.control_identifier
                for m in pack.margins
                if m.entity_level == "household"
            }
            fitted_counts, realized_counts = Counter(), Counter()
            for row in hh_derived if is_household else pp_derived:
                fitted_counts[tuple(row[d] for d in dims)] += weights[
                    ct, row["synthetic_household_id"]
                ]
            for row in realized_households if is_household else realized_persons:
                if row["ct"] == ct:
                    realized_counts[tuple(row[d] for d in dims)] += 1
            assert realized_counts.keys() <= expected.keys()
            assert fitted_counts.keys() <= expected.keys()
            fit_error = max(abs(fitted_counts[k] - v) for k, v in expected.items())
            realized_error = max(
                abs(realized_counts[k] - v) for k, v in expected.items()
            )
            assert fractional[name] == pytest.approx(fit_error, abs=1e-8)
            assert fit_error <= 1e-6
            assert realized[name] == realized_error == 0

    wrong_vintage = 2021 if vintage == 2016 else 2016
    result, output = calibrate(
        "wrong-vintage",
        conditional_pack=f"statcan-{wrong_vintage}-marital-status-ct-v1",
    )
    assert result.exit_code == 1
    assert "requires its matching Statistics Canada CT geography" in result.output
    assert not list(output.glob("*.csv"))

    suppressed = tmp_path / "suppressed.csv"
    source_rows = read_csv(source)
    next(
        r
        for r in source_rows
        if r["ct"] == "4620054.00" and r["marital_status"] == "9" and r["age_20"] == "3"
    )["value"] = ""
    write_csv(suppressed, source_rows)
    result, output = calibrate("suppressed", suppressed)
    assert result.exit_code == 1
    assert "4620054.00: unavailable or invalid" in result.output
    assert not list(output.glob("*.csv"))

    child_cell = next(
        row
        for row in controls["person"]
        if row["ct"] == "4620054.00"
        and row.get("age_group_3") == "0_14"
        and row["count"]
    )
    adult_cell = next(
        row
        for row in controls["person"]
        if row["ct"] == "4620054.00"
        and row.get("age_group_3") == "15_64"
        and row["count"]
    )
    child_cell["count"] -= 1
    adult_cell["count"] += 1
    write_controls("person")
    bind_evidence()
    result, output = calibrate("wrong-child-count")
    assert result.exit_code == 1
    assert (
        "does not match the reconciled marital-status under-15 target" in result.output
    )
    assert not list(output.glob("*.csv"))
    child_cell["count"] += 1
    adult_cell["count"] -= 1

    # Keep broad evidence internally valid while making every person total
    # disagree with the independent marital source.
    for name in {row["margin"] for row in controls["person"]}:
        next(
            row
            for row in controls["person"]
            if row["ct"] == "4620054.00" and row["margin"] == name and row["count"]
        )["count"] += 1
    universe["4620054.00"] = {
        key: value + 1 for key, value in universe["4620054.00"].items()
    }
    write_controls("person")
    bind_evidence()
    result, output = calibrate("wrong-total")
    assert result.exit_code == 1
    assert (
        "4620054.00:" in result.output
        and "evidenced private-household person total" in result.output
    )
    assert not list(output.glob("*.csv"))
