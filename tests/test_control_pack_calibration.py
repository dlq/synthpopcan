"""Control pack calibration behaviour and regression tests."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest
from support.control_pack_fixtures import (
    _GEOGRAPHY_IDS,
    _evidence,
    _expanded_population,
    _expanded_tables,
    _population,
    _tables,
    _write_rows,
)

import synthpopcan as spc
from synthpopcan.control_packs import (
    apply_control_pack_derivations,
    load_control_pack,
    plan_control_pack,
)
from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    write_control_table,
)
from synthpopcan.geography import GeographyUniverse
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    fit_linked_by_geography,
    realize_linked_geography_population,
)


def test_beginner_api_lists_reads_builds_plans_and_calibrates_pack(
    tmp_path: Path,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack_id,
        households,
        persons,
        geographies=(_GEOGRAPHY_IDS["da"],),
    )

    assert any(item["identifier"] == pack_id for item in spc.list_control_packs())
    pack = spc.read_control_pack(pack_id)
    evidence = spc.build_control_pack_evidence(
        pack,
        controls,
        person_controls,
        geographies={
            _GEOGRAPHY_IDS["da"]: {
                "total_population": 15,
                "persons_in_private_households": 15,
            }
        },
    )
    plan = spc.plan_control_pack(
        pack,
        spc.LinkedPopulation(households=households, persons=persons),
        controls,
        person_controls,
        evidence=evidence,
    )

    assert spc.read_control_pack_evidence(evidence) == evidence
    assert plan["passed"] is True
    assert plan["geographies"]["identifiers"] == [_GEOGRAPHY_IDS["da"]]
    result = spc.calibrate_small_area(
        spc.LinkedPopulation(households=households, persons=persons),
        controls,
        person_controls=person_controls,
        control_pack=pack,
        control_pack_evidence=evidence,
        geography_dimension="da",
        geography_column="DAUID",
        output_dir=tmp_path / "small-area",
    )
    assert result.details["control_pack_plan"]["passed"] is True
    assert result.details["geography_universe"] == {
        "schema_version": "synthpopcan-geography-universe-v1",
        "census_vintage": 2021,
        "geography_level": "da",
        "identifier_namespace": "statcan:census:2021:da",
        "identifier_column": "DAUID",
        "dguid_column": None,
    }
    assert result.assigned_households == len(households)


def test_low_level_calibration_applies_passing_pack_and_records_provenance(
    tmp_path: Path,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    geography = _GEOGRAPHY_IDS["da"]
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack_id,
        households,
        persons,
        geographies=(geography,),
    )
    evidence = _evidence(pack_id, controls, person_controls, (geography,))
    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    controls_path = tmp_path / "controls.csv"
    person_controls_path = tmp_path / "person-controls.csv"
    _write_rows(households_path, households)
    _write_rows(persons_path, persons)
    write_control_table(controls_path, controls)
    write_control_table(person_controls_path, person_controls)

    with pytest.raises(ValueError, match="incompatible with the selected"):
        calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            person_controls_path=person_controls_path,
            control_pack=pack_id,
            control_pack_evidence=evidence,
            geography_dimension="da",
            geography_column="DAUID",
            geography_universe=GeographyUniverse(
                census_vintage=2016,
                geography_level="da",
                identifier_namespace="statcan:census:2016:da",
                identifier_column="DAUID",
            ),
            households_out=tmp_path / "wrong-households.csv",
            persons_out=tmp_path / "wrong-persons.csv",
        )

    report = calibrate_linked_household_csvs(
        households_path=households_path,
        persons_path=persons_path,
        controls_path=controls_path,
        person_controls_path=person_controls_path,
        control_pack=pack_id,
        control_pack_evidence=evidence,
        geography_dimension="da",
        geography_column="da",
        households_out=tmp_path / "out-households.csv",
        persons_out=tmp_path / "out-persons.csv",
    )

    assert report["control_pack_plan"]["passed"] is True
    assert report["control_pack"]["identifier"] == pack_id
    assert report["control_pack_evidence"]["pack_identifier"] == pack_id
    assert report["methodological_diagnostics"]["schema_version"] == (
        "synthpopcan-validation-profile-v1"
    )
    output_rows = list(csv.DictReader((tmp_path / "out-households.csv").open()))
    assert {row["household_size_group"] for row in output_rows} == {
        "1",
        "2",
        "3",
        "4",
        "5",
    }


@pytest.mark.parametrize("vintage", [2016, 2021])
def test_broad_pack_plans_and_calibrates_all_reviewed_margins(
    tmp_path: Path,
    vintage: int,
) -> None:
    geography = _GEOGRAPHY_IDS["da"]
    pack_id = f"statcan-{vintage}-broad-da-v1"
    households, persons = _expanded_population(vintage)
    controls, person_controls = _expanded_tables(
        pack_id, households, persons, geography=geography
    )
    evidence = _evidence(
        pack_id,
        controls,
        person_controls,
        (geography,),
        private_people=len(persons),
    )
    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is True, [
        (issue.get("kind"), issue.get("dimension"), issue.get("category"))
        for issue in plan["issues"]
    ]
    assert len(controls.margins) == 9
    assert len(person_controls.margins) == 5
    derived_households, _ = apply_control_pack_derivations(
        load_control_pack(pack_id), households, persons
    )
    assert {
        "household_size_group",
        "structural_dwelling_type",
        "bedrooms_group",
        "rooms_group",
        "construction_period_group",
        "repair_group",
    } <= set(derived_households[0])
    _, derived_persons = apply_control_pack_derivations(
        load_control_pack(pack_id), households, persons
    )
    assert {
        "age_group_3",
        "citizenship_group",
        "immigration_status_group",
        "generation_status_group",
        "visible_minority_group",
    } <= set(derived_persons[0])

    households_path = tmp_path / f"households-{vintage}.csv"
    persons_path = tmp_path / f"persons-{vintage}.csv"
    controls_path = tmp_path / f"controls-{vintage}.csv"
    person_controls_path = tmp_path / f"person-controls-{vintage}.csv"
    _write_rows(households_path, households)
    _write_rows(persons_path, persons)
    write_control_table(controls_path, controls)
    write_control_table(person_controls_path, person_controls)
    report = calibrate_linked_household_csvs(
        households_path=households_path,
        persons_path=persons_path,
        controls_path=controls_path,
        person_controls_path=person_controls_path,
        control_pack=pack_id,
        control_pack_evidence=evidence,
        geography_dimension="da",
        geography_column="da",
        households_out=tmp_path / f"out-households-{vintage}.csv",
        persons_out=tmp_path / f"out-persons-{vintage}.csv",
    )

    assert report["control_pack_plan"]["passed"] is True
    assert report["control_pack"]["identifier"] == pack_id
    assert report["methodological_diagnostics"]["schema_version"] == (
        "synthpopcan-validation-profile-v1"
    )


def test_broad_pack_reconciles_each_person_margin_independently() -> None:
    geography = _GEOGRAPHY_IDS["da"]
    pack_id = "statcan-2021-broad-da-v1"
    households, persons = _expanded_population(2021)
    controls, person_controls = _expanded_tables(
        pack_id, households, persons, geography=geography
    )
    altered_margins: list[ControlMargin] = []
    for margin in person_controls.margins:
        cells = list(margin.cells)
        if "citizenship_group" in margin.dimensions:
            first = cells[0]
            cells[0] = ControlCell(dict(first.categories), first.count + 1)
        altered_margins.append(
            ControlMargin(margin.name, margin.dimensions, tuple(cells))
        )
    altered_person_controls = ControlTable(
        tuple(altered_margins), person_controls.dimensions
    )
    evidence = _evidence(
        pack_id,
        controls,
        altered_person_controls,
        (geography,),
        private_people=len(persons),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        controls,
        altered_person_controls,
        evidence=evidence,
    )

    mismatches = [
        issue
        for issue in plan["issues"]
        if issue["kind"] == "person_control_universe_total_mismatch"
    ]
    assert plan["passed"] is False
    assert len(mismatches) == 1
    actual_totals = mismatches[0]["actual"]
    citizenship_key = next(key for key in actual_totals if "citizenship" in key)
    assert actual_totals[citizenship_key] == len(persons) + 1
    assert all(
        total == len(persons)
        for key, total in actual_totals.items()
        if key != citizenship_key
    )


def test_low_level_calibration_fails_closed_without_pack_evidence(
    tmp_path: Path,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    geography = _GEOGRAPHY_IDS["da"]
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack_id,
        households,
        persons,
        geographies=(geography,),
    )
    households_path = tmp_path / "households.csv"
    persons_path = tmp_path / "persons.csv"
    controls_path = tmp_path / "controls.csv"
    person_controls_path = tmp_path / "person-controls.csv"
    _write_rows(households_path, households)
    _write_rows(persons_path, persons)
    write_control_table(controls_path, controls)
    write_control_table(person_controls_path, person_controls)

    with pytest.raises(ValueError, match="feasibility plan did not pass"):
        calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            person_controls_path=person_controls_path,
            control_pack=pack_id,
            geography_dimension="da",
            geography_column="da",
            households_out=tmp_path / "out-households.csv",
            persons_out=tmp_path / "out-persons.csv",
        )


@pytest.mark.parametrize("vintage", [2016, 2021])
@pytest.mark.parametrize("geography_level", ["csd", "ct", "ada", "da"])
def test_bounded_core_pack_plan_and_fit_preserve_whole_households(
    vintage: int,
    geography_level: str,
) -> None:
    pack_id = f"statcan-{vintage}-core-private-household-{geography_level}-v1"
    geography = _GEOGRAPHY_IDS[geography_level]
    households, persons = _population(vintage)
    household_controls, person_controls = _tables(
        pack_id,
        households,
        persons,
        geographies=(geography,),
    )
    evidence = _evidence(
        pack_id,
        household_controls,
        person_controls,
        (geography,),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is True
    assert plan["error_count"] == 0
    assert plan["geographies"]["identifiers"] == [geography]
    assert plan["candidate_population"]["whole_household_weight_count"] == 5
    assert plan["candidate_population"]["person_assignment"] == (
        "inherited-via-household"
    )
    assert plan["field_status"]["household"]["controlled_fields"] == ["TENUR"]
    assert plan["field_status"]["household"]["coarsened_source_fields"] == [
        "household_size"
    ]
    assert plan["field_status"]["household"]["coarsened_derived_fields"] == [
        "household_size_group"
    ]
    assert plan["field_status"]["household"]["uncontrolled_fields"] == [
        "BEDRM",
        "BUILT",
        "CONDO",
        "DTYPE",
        "NOS",
        "REPAIR",
        "ROOM",
    ]
    assert plan["field_status"]["person"]["uncontrolled_fields"] == [
        "CITIZEN",
        "GENSTAT",
        "IMMSTAT",
        "TOTINC",
        "VISMIN",
    ]
    assert plan["field_status"]["person"]["coarsened_source_fields"] == ["AGEGRP"]
    raw_age = next(
        field
        for field in plan["field_status"]["person"]["fields"]
        if field["field"] == "AGEGRP"
    )
    assert raw_age["status"] == "coarsened-to-control"
    assert raw_age["derived_control_fields"] == ["age_group_3"]
    assert raw_age["derivations"][0]["categories"]["14"] == "65_plus"
    assert plan["margin_total_reconciliation"]["rows"][0]["status"] == "exact"

    derived_households, derived_persons = apply_control_pack_derivations(
        pack_id, households, persons
    )
    fit = fit_linked_by_geography(
        derived_households,
        derived_persons,
        household_controls,
        person_controls,
        geography_dimension=geography_level,
        max_iterations=10,
        tolerance=1e-9,
    )
    realized_households, realized_persons = realize_linked_geography_population(
        derived_households,
        derived_persons,
        weights_by_geography=fit.weights_by_geography,
        geography_column=geography_level,
    )

    assert fit.reports[geography]["converged"] is True
    assert len(realized_households) == len(households)
    assert len(realized_persons) == len(persons)
    people_by_household = Counter(
        row["synthetic_household_id"] for row in realized_persons
    )
    assert {
        row["synthetic_household_id"]: people_by_household[
            row["synthetic_household_id"]
        ]
        for row in realized_households
    } == {
        row["synthetic_household_id"]: int(row["household_size"])
        for row in realized_households
    }
