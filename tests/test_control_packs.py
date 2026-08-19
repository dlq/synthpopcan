from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

import synthpopcan as spc
import synthpopcan.control_packs as control_pack_module
from synthpopcan.cli import main
from synthpopcan.control_packs import (
    COMPATIBILITY_REGISTRY_SCHEMA_VERSION,
    CONTROL_PACK_SCHEMA_VERSION,
    CandidateDerivation,
    ControlCompatibilityRegistry,
    ControlDefinition,
    ControlPackEvidence,
    ControlPackManifest,
    GeographyUniverseEvidence,
    SourceAxis,
    SourceCategory,
    UniverseDefinition,
    apply_control_pack_derivations,
    build_control_pack_evidence,
    control_table_sha256,
    list_builtin_control_packs,
    load_compatibility_registry,
    load_control_pack,
    load_control_pack_evidence,
    plan_control_pack,
    read_control_pack,
    read_control_pack_evidence,
    validate_control_pack_compatibility,
    write_control_pack,
    write_control_pack_evidence,
)
from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    write_control_table,
)
from synthpopcan.geography import GeographyUniverse
from synthpopcan.linked_schema import LINKED_POPULATION_SCHEMA_VERSION
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    fit_linked_by_geography,
    realize_linked_geography_population,
)

_GEOGRAPHY_IDS = {
    "csd": "2466023",
    "ct": "4620055.00",
    "ada": "24660239",
    "da": "24660244",
}

_RELEASED_CORE_PACK_HASHES = {
    "statcan-2016-core-private-household-csd-v1": (
        "4209134e304bf7fb1d240e1d238c9e352fc7f7d6ab4cb66585a2426bd91a4820"
    ),
    "statcan-2016-core-private-household-ct-v1": (
        "5bd972460b1ebb18ddfff43ad0ef9d1681eedf6250d5f5a268386b08698d88b4"
    ),
    "statcan-2016-core-private-household-ada-v1": (
        "8b9cde2c15acada5941dd62f3efe050fdc923f02db1d93eb3c0fd518efaf6948"
    ),
    "statcan-2016-core-private-household-da-v1": (
        "48d47e976e8ef1deef0ae080120763c7dd405e663ebcd4a5007212bda929086f"
    ),
    "statcan-2021-core-private-household-csd-v1": (
        "725cb1b151c18182f76fb8c06dfab8ccb0f32ec0530663d3189f9fc5630b10ff"
    ),
    "statcan-2021-core-private-household-ct-v1": (
        "65c54ab30692638bed6b98989c3b12521d1eb0798e0191bb966d96ea59babb7e"
    ),
    "statcan-2021-core-private-household-ada-v1": (
        "11f0fa365b60a83b1e446df77b225265bf8822195d47c22bf28c2fac6c95fb22"
    ),
    "statcan-2021-core-private-household-da-v1": (
        "0fa1e1810aebfe88799210aac5d85da22428f9ecbc405445728e8c299b5fce00"
    ),
}


def _population(vintage: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sex_field = "SEX" if vintage == 2016 else "GENDER"
    households: list[dict[str, str]] = []
    persons: list[dict[str, str]] = []
    person_index = 0
    for size in range(1, 6):
        household_id = f"h{size}"
        households.append(
            {
                "synthetic_household_id": household_id,
                "household_size": str(size),
                "TENUR": "1" if size % 2 else "2",
                "DTYPE": str((size - 1) % 3 + 1),
                "CONDO": str(size % 2),
                "BEDRM": str(size - 1),
                "ROOM": str((1, 5, 6, 7, 8)[size - 1]),
                "NOS": (
                    str(1 if size % 2 else 2)
                    if vintage == 2016
                    else str(1 if size % 2 else 0)
                ),
                "BUILT": str((1, 4, 6, 8, 11)[size - 1]),
                "REPAIR": str((size - 1) % 3 + 1),
            }
        )
        for _member in range(size):
            age = ("1", "4", "14")[person_index % 3]
            sex = ("1", "2")[(person_index // 3) % 2]
            persons.append(
                {
                    "synthetic_person_id": f"p{person_index + 1}",
                    "synthetic_household_id": household_id,
                    "AGEGRP": age,
                    sex_field: sex,
                    "TOTINC": str(person_index % 4),
                    "CITIZEN": str(person_index % 3 + 1),
                    "IMMSTAT": str(person_index % 3 + 1),
                    "GENSTAT": str(person_index % 4 + 1),
                    "VISMIN": str(
                        (1, 2)[person_index % 2]
                        if vintage == 2016
                        else (1, 0)[person_index % 2]
                    ),
                }
            )
            person_index += 1
    return households, persons


def _expanded_population(
    vintage: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Cover every category in each reviewed expanded-pack margin."""

    sex_field = "SEX" if vintage == 2016 else "GENDER"
    sizes = (1, 2, 3, 4, 5, 1, 2, 3)
    built_codes = (
        ("1", "4", "6", "7", "9", "10", "11", "1")
        if vintage == 2016
        else ("1", "3", "5", "6", "8", "9", "10", "11")
    )
    households: list[dict[str, str]] = []
    persons: list[dict[str, str]] = []
    person_index = 0
    for index, (size, built) in enumerate(
        zip(sizes, built_codes, strict=True), start=1
    ):
        household_id = f"eh{index}"
        households.append(
            {
                "synthetic_household_id": household_id,
                "household_size": str(size),
                "TENUR": str(1 if index % 2 else 2),
                "DTYPE": str((index - 1) % 3 + 1),
                "CONDO": str(index % 2),
                "BEDRM": str((index - 1) % 5),
                "ROOM": str((1, 5, 6, 7, 8)[(index - 1) % 5]),
                "NOS": str(1 if index % 2 else (2 if vintage == 2016 else 0)),
                "BUILT": built,
                "REPAIR": str(3 if index % 3 == 0 else 1),
            }
        )
        for _member in range(size):
            age, sex = (
                ("1", "1"),
                ("1", "2"),
                ("4", "1"),
                ("4", "2"),
                ("14", "1"),
                ("14", "2"),
            )[person_index % 6]
            persons.append(
                {
                    "synthetic_person_id": f"ep{person_index + 1}",
                    "synthetic_household_id": household_id,
                    "AGEGRP": age,
                    sex_field: sex,
                    "TOTINC": str(person_index % 4),
                    "CITIZEN": str(person_index % 3 + 1),
                    "IMMSTAT": str(person_index % 3 + 1),
                    "GENSTAT": str(person_index % 4 + 1),
                    "VISMIN": str(
                        (1, 2)[person_index % 2]
                        if vintage == 2016
                        else (1, 0)[person_index % 2]
                    ),
                }
            )
            person_index += 1
    return households, persons


def _tables(
    pack_id: str,
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    geographies: tuple[str, ...],
) -> tuple[ControlTable, ControlTable]:
    pack = load_control_pack(pack_id)
    derived_households, derived_persons = apply_control_pack_derivations(
        pack, households, persons
    )
    size_counts = Counter(row["household_size_group"] for row in derived_households)
    tenure_counts = Counter(row["TENUR"] for row in derived_households)
    sex_field = "SEX" if pack.census_vintage == 2016 else "GENDER"
    person_counts = Counter(
        (row["age_group_3"], row[sex_field]) for row in derived_persons
    )
    size_cells = tuple(
        ControlCell(
            {pack.geography_column: geography, "household_size_group": category},
            size_counts[category],
        )
        for geography in geographies
        for category in ("1", "2", "3", "4", "5")
    )
    tenure_cells = tuple(
        ControlCell(
            {pack.geography_column: geography, "TENUR": category},
            tenure_counts[category],
        )
        for geography in geographies
        for category in ("1", "2")
    )
    person_cells = tuple(
        ControlCell(
            {
                pack.geography_column: geography,
                "age_group_3": age,
                sex_field: sex,
            },
            person_counts[(age, sex)],
        )
        for geography in geographies
        for age in ("0_14", "15_64", "65_plus")
        for sex in ("1", "2")
    )
    household_controls = ControlTable(
        margins=(
            ControlMargin(
                "household size",
                (pack.geography_column, "household_size_group"),
                size_cells,
            ),
            ControlMargin(
                "tenure",
                (pack.geography_column, "TENUR"),
                tenure_cells,
            ),
        ),
        dimensions=(pack.geography_column, "household_size_group", "TENUR"),
    )
    person_controls = ControlTable(
        margins=(
            ControlMargin(
                "broad age by sex/gender",
                (pack.geography_column, "age_group_3", sex_field),
                person_cells,
            ),
        ),
        dimensions=(pack.geography_column, "age_group_3", sex_field),
    )
    return household_controls, person_controls


def _expanded_tables(
    pack_id: str,
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    geography: str,
) -> tuple[ControlTable, ControlTable]:
    pack = load_control_pack(pack_id)
    definitions = {
        control.identifier: control
        for control in load_compatibility_registry().controls
    }
    derived_households, derived_persons = apply_control_pack_derivations(
        pack, households, persons
    )
    household_margins: list[ControlMargin] = []
    household_dimensions: set[str] = {pack.geography_column}
    for margin in pack.margins:
        if margin.entity_level != "household":
            continue
        dimension = margin.dimensions[1]
        household_dimensions.add(dimension)
        counts = Counter(row[dimension] for row in derived_households)
        categories = tuple(
            category.target_category
            for category in definitions[margin.control_identifier]
            .source_axes[0]
            .categories
        )
        household_margins.append(
            ControlMargin(
                margin.control_identifier,
                tuple(margin.dimensions),
                tuple(
                    ControlCell(
                        {pack.geography_column: geography, dimension: category},
                        count,
                    )
                    for category in categories
                    for count in (counts[category],)
                ),
            )
        )
    person_margins: list[ControlMargin] = []
    person_dimensions: set[str] = {pack.geography_column}
    for margin in pack.margins:
        if margin.entity_level != "person":
            continue
        dimensions = tuple(margin.dimensions[1:])
        person_dimensions.update(dimensions)
        counts = Counter(
            tuple(row[dimension] for dimension in dimensions) for row in derived_persons
        )
        axes = definitions[margin.control_identifier].source_axes
        categories = tuple(
            tuple(category.target_category for category in axis.categories)
            for axis in axes
        )
        person_margins.append(
            ControlMargin(
                margin.control_identifier,
                tuple(margin.dimensions),
                tuple(
                    ControlCell(
                        {
                            pack.geography_column: geography,
                            **dict(zip(dimensions, combination, strict=True)),
                        },
                        counts[combination],
                    )
                    for combination in product(*categories)
                ),
            )
        )
    person_controls = ControlTable(
        margins=tuple(person_margins),
        dimensions=tuple(sorted(person_dimensions)),
    )
    return (
        ControlTable(
            margins=tuple(household_margins),
            dimensions=tuple(sorted(household_dimensions)),
        ),
        person_controls,
    )


def _evidence(
    pack_id: str,
    household_controls: ControlTable,
    person_controls: ControlTable,
    geographies: tuple[str, ...],
    *,
    collective_people: int = 0,
    private_people: int = 15,
) -> ControlPackEvidence:
    pack = load_control_pack(pack_id)
    return build_control_pack_evidence(
        pack,
        household_controls,
        person_controls,
        geographies={
            geography: {
                "total_population": private_people + collective_people,
                "persons_in_private_households": private_people,
            }
            for geography in geographies
        },
        controls_source_revisions=pack.source_revisions,
    )


def _semantic_checksum(payload: dict[str, object]) -> str:
    semantic = dict(payload)
    semantic.pop("definition_sha256", None)
    encoded = json.dumps(
        semantic,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _issue_kinds(plan: dict[str, object]) -> set[str]:
    issues = plan["issues"]
    assert isinstance(issues, list)
    return {str(issue["kind"]) for issue in issues}


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_lists_core_and_expanded_vintage_geography_packs() -> None:
    packs = list_builtin_control_packs()

    assert len(packs) == 24
    assert {item["census_vintage"] for item in packs} == {2016, 2021}
    assert {item["geography_level"] for item in packs} == {
        "csd",
        "ct",
        "ada",
        "da",
    }
    assert all(
        item["linked_schema_version"] == LINKED_POPULATION_SCHEMA_VERSION
        for item in packs
    )
    assert all(len(str(item["definition_sha256"])) == 64 for item in packs)
    assert (
        sum("-core-private-household-" in str(item["identifier"]) for item in packs)
        == 8
    )
    assert sum("-broad-" in str(item["identifier"]) for item in packs) == 8
    assert (
        sum(
            "-expanded-private-household-housing-" in str(item["identifier"])
            for item in packs
        )
        == 8
    )


def test_released_core_pack_definitions_remain_unchanged() -> None:
    actual = {
        str(pack["identifier"]): str(pack["definition_sha256"])
        for pack in list_builtin_control_packs()
        if "-core-private-household-" in str(pack["identifier"])
    }

    assert actual == _RELEASED_CORE_PACK_HASHES


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


def test_control_pack_cli_builds_evidence_and_plans_without_fitting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
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
    universe_path = tmp_path / "universe.json"
    evidence_path = tmp_path / "evidence.json"
    _write_rows(households_path, households)
    _write_rows(persons_path, persons)
    write_control_table(controls_path, controls)
    write_control_table(person_controls_path, person_controls)
    universe_path.write_text(
        json.dumps(
            {
                geography: {
                    "total_population": 15,
                    "persons_in_private_households": 15,
                }
            }
        )
    )

    assert (
        main(
            [
                "geo",
                "control-packs",
                "evidence",
                pack_id,
                "--controls",
                str(controls_path),
                "--person-controls",
                str(person_controls_path),
                "--universe-evidence",
                str(universe_path),
                "--out",
                str(evidence_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert evidence_path.is_file()
    assert (
        main(
            [
                "geo",
                "control-packs",
                "plan",
                pack_id,
                str(households_path),
                "--persons",
                str(persons_path),
                "--controls",
                str(controls_path),
                "--person-controls",
                str(person_controls_path),
                "--evidence",
                str(evidence_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    plan = json.loads(capsys.readouterr().out)
    assert plan["passed"] is True
    assert plan["geographies"]["identifiers"] == [geography]


def test_registry_records_reviewed_crosswalks_and_explicit_deferred_fields() -> None:
    registry = load_compatibility_registry()
    controls = {control.identifier: control for control in registry.controls}
    statuses = {field.concept_identifier: field.status for field in registry.fields}

    assert registry.schema_version == COMPATIBILITY_REGISTRY_SCHEMA_VERSION
    assert registry.revision == "2026-08-19"
    assert len(controls) == 28
    assert statuses["household.size"] == "implemented"
    assert statuses["household.dwelling-type"] == "implemented"
    assert statuses["household.rooms"] == "implemented"
    assert statuses["household.repair"] == "implemented"
    assert statuses["person.citizenship"] == "implemented"
    assert statuses["person.immigration-status"] == "implemented"
    assert statuses["person.generation-status"] == "implemented"
    assert statuses["person.visible-minority"] == "implemented"
    assert statuses["household.dwelling-value"] == "unavailable"
    age_2021 = controls["statcan.2021.private-age-gender.v1"]
    assert age_2021.source.root_characteristic_id == "8"
    assert age_2021.universe.reconciliation == "zero-collective-only"
    assert age_2021.universe.companion_characteristic_id == "56"
    assert [axis.candidate_field for axis in age_2021.source_axes] == [
        "age_group_3",
        "GENDER",
    ]
    assert age_2021.source_axes[1].categories[0].source_count_columns == [
        "C2_COUNT_MEN+"
    ]
    assert age_2021.suppression.suppressed_cell == "exclude-geography"
    dwelling_type = controls["statcan.2021.dwelling-type.v1"]
    assert dwelling_type.source.root_characteristic_id == "41"
    assert dwelling_type.candidate_derivations[0].categories["2"] == "apartment"
    construction = controls["statcan.2016.construction-period.v1"]
    assert construction.candidate_derivations[0].categories["1"] == ("1960_or_before")
    generation = controls["statcan.2021.generation-status.v1"]
    assert generation.universe.identifier == "private-household-persons"
    assert generation.candidate_derivations[0].categories["3"] == "second"


def test_strict_registry_models_reject_contradictory_nested_semantics() -> None:
    registry = load_compatibility_registry()
    identity_universe = registry.controls[0].universe.as_dict()
    identity_universe.update(
        {
            "companion_characteristic_id": "56",
            "companion_label": "Persons in private households",
        }
    )
    with pytest.raises(ValidationError, match="identity universes cannot"):
        UniverseDefinition.model_validate(identity_universe)

    zero_collective = next(
        control.universe.as_dict()
        for control in registry.controls
        if control.universe.reconciliation == "zero-collective-only"
    )
    zero_collective["companion_characteristic_id"] = None
    with pytest.raises(ValidationError, match="require a companion"):
        UniverseDefinition.model_validate(zero_collective)

    invalid_derivations = (
        {
            "output_field": "size_group",
            "source_field": "household_size",
            "method": "top-code-integer",
            "categories": {},
            "cap": None,
            "unmapped": "reject",
        },
        {
            "output_field": "age_group",
            "source_field": "AGEGRP",
            "method": "category-crosswalk",
            "categories": {},
            "cap": None,
            "unmapped": "reject",
        },
        {
            "output_field": "TENUR",
            "source_field": "TENUR",
            "method": "identity",
            "categories": {"1": "owner"},
            "cap": None,
            "unmapped": "reject",
        },
    )
    messages = (
        "top-code-integer derivations require",
        "category-crosswalk derivations require",
        "identity derivations cannot",
    )
    for payload, message in zip(invalid_derivations, messages, strict=True):
        with pytest.raises(ValidationError, match=message):
            CandidateDerivation.model_validate(payload)

    category = registry.controls[0].source_axes[0].categories[0].as_dict()
    category.update({"source_characteristic_ids": [], "source_count_columns": []})
    with pytest.raises(ValidationError, match="requires characteristic IDs"):
        SourceCategory.model_validate(category)

    axis = registry.controls[0].source_axes[0].as_dict()
    axis["categories"] = [axis["categories"][0], axis["categories"][0]]
    with pytest.raises(ValidationError, match="target categories must be unique"):
        SourceAxis.model_validate(axis)

    person_control = next(
        control
        for control in registry.controls
        if len(control.candidate_derivations) == 2
    )
    duplicated_derivation = person_control.as_dict()
    duplicated_derivation["candidate_derivations"][1]["output_field"] = (
        duplicated_derivation["candidate_derivations"][0]["output_field"]
    )
    with pytest.raises(ValidationError, match="output fields must be unique"):
        ControlDefinition.model_validate(duplicated_derivation)

    reordered_axes = person_control.as_dict()
    reordered_axes["source_axes"].reverse()
    with pytest.raises(ValidationError, match="source axes must match"):
        ControlDefinition.model_validate(reordered_axes)

    repeated_geography = registry.controls[0].as_dict()
    repeated_geography["geography_levels"].append(
        repeated_geography["geography_levels"][0]
    )
    with pytest.raises(ValidationError, match="geography levels must be unique"):
        ControlDefinition.model_validate(repeated_geography)


def test_strict_registry_rejects_duplicate_and_dangling_references() -> None:
    payload = load_compatibility_registry().as_dict()
    duplicate_concept = deepcopy(payload)
    duplicate_concept["fields"].append(deepcopy(duplicate_concept["fields"][0]))
    with pytest.raises(ValidationError, match="concept identifiers must be unique"):
        ControlCompatibilityRegistry.model_validate(duplicate_concept)

    duplicate_control = deepcopy(payload)
    duplicate_control["controls"].append(deepcopy(duplicate_control["controls"][0]))
    with pytest.raises(ValidationError, match="control identifiers must be unique"):
        ControlCompatibilityRegistry.model_validate(duplicate_control)

    dangling_reference = deepcopy(payload)
    dangling_reference["fields"][0]["control_identifiers"] = ["unknown.control.v1"]
    with pytest.raises(ValidationError, match="references unknown controls"):
        ControlCompatibilityRegistry.model_validate(dangling_reference)

    unregistered_concept = deepcopy(payload)
    unregistered_concept["controls"][0]["concept_identifier"] = "household.unregistered"
    with pytest.raises(ValidationError, match="map to a registered field concept"):
        ControlCompatibilityRegistry.model_validate(unregistered_concept)


def test_strict_pack_and_evidence_models_reject_ambiguous_identity() -> None:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack.identifier, households, persons, geographies=("24660244",)
    )
    evidence = _evidence(pack.identifier, controls, person_controls, ("24660244",))

    with pytest.raises(ValidationError, match="counts must be finite"):
        GeographyUniverseEvidence.model_validate(
            {
                "total_population": float("inf"),
                "persons_in_private_households": 15,
            }
        )

    empty_identifier = evidence.as_dict()
    empty_identifier["geographies"] = {
        "": {
            "total_population": 15,
            "persons_in_private_households": 15,
        }
    }
    with pytest.raises(ValidationError, match="identifiers cannot be empty"):
        ControlPackEvidence.model_validate(empty_identifier)

    overlapping = evidence.as_dict()
    overlapping["excluded_geographies"] = {"24660244": "suppressed cell"}
    with pytest.raises(ValidationError, match="both eligible and explicitly excluded"):
        ControlPackEvidence.model_validate(overlapping)

    unexplained_exclusion = evidence.as_dict()
    unexplained_exclusion["excluded_geographies"] = {"24660245": ""}
    with pytest.raises(ValidationError, match="require a non-empty reason"):
        ControlPackEvidence.model_validate(unexplained_exclusion)

    duplicate_entity = pack.as_dict()
    duplicate_entity["required_entity_levels"].append("household")
    with pytest.raises(ValidationError, match="entity levels must be unique"):
        ControlPackManifest.model_validate(duplicate_entity)

    duplicate_margin = pack.as_dict()
    duplicate_margin["margins"][1]["control_identifier"] = duplicate_margin["margins"][
        0
    ]["control_identifier"]
    with pytest.raises(ValidationError, match="margin controls must be unique"):
        ControlPackManifest.model_validate(duplicate_margin)


def test_pack_json_round_trip_is_strict_and_checksum_bound(tmp_path: Path) -> None:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    path = write_control_pack(pack, tmp_path / "pack.json")

    assert read_control_pack(path) == pack
    assert pack.schema_version == CONTROL_PACK_SCHEMA_VERSION
    assert pack.as_dict()["identifier"] == pack.identifier

    payload = pack.as_dict()
    payload["label"] = "tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="definition_sha256"):
        read_control_pack(path)


def test_public_pack_and_evidence_loaders_cover_paths_mappings_and_failures(
    tmp_path: Path,
) -> None:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    pack_path = write_control_pack(pack, tmp_path / "nested" / "pack.json")
    assert load_control_pack(pack_path) == pack

    with pytest.raises(ValueError, match="could not read control pack"):
        read_control_pack(tmp_path / "missing-pack.json")
    with pytest.raises(ValueError, match="unknown control pack"):
        load_control_pack("not-a-built-in-control-pack")

    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack.identifier, households, persons, geographies=("24660244",)
    )
    evidence = _evidence(pack.identifier, controls, person_controls, ("24660244",))
    evidence_path = write_control_pack_evidence(
        evidence.as_dict(), tmp_path / "nested" / "evidence.json"
    )
    assert load_control_pack_evidence(evidence.as_dict()) == evidence
    assert load_control_pack_evidence(evidence_path) == evidence

    with pytest.raises(ValueError, match="could not read control-pack evidence"):
        read_control_pack_evidence(tmp_path / "missing-evidence.json")
    invalid_evidence = tmp_path / "invalid-evidence.json"
    invalid_evidence.write_text('{"schema_version":"unsupported"}')
    with pytest.raises(ValueError, match="invalid control-pack evidence"):
        read_control_pack_evidence(invalid_evidence)


def test_loaded_manifest_instances_revalidate_the_installed_registry_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    unsupported_schema = pack.model_copy(
        update={"registry_schema_version": "future-registry-v2"}
    )
    with pytest.raises(ValueError, match="unsupported registry schema"):
        load_control_pack(unsupported_schema)

    registry = load_compatibility_registry()
    first_control_id = pack.margins[0].control_identifier
    narrowed_controls = [
        (
            control.model_copy(update={"geography_levels": ["ct"]})
            if control.identifier == first_control_id
            else control
        )
        for control in registry.controls
    ]
    narrowed_registry = registry.model_copy(update={"controls": narrowed_controls})
    monkeypatch.setattr(
        control_pack_module,
        "load_compatibility_registry",
        lambda: narrowed_registry,
    )
    with pytest.raises(ValueError, match="does not support DA"):
        load_control_pack(pack)


def test_evidence_builder_rejects_revision_and_geography_misbindings() -> None:
    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    households, persons = _population(2021)
    controls, person_controls = _tables(
        pack.identifier, households, persons, geographies=("24660244",)
    )
    with pytest.raises(ValueError, match="source_revisions must exactly match"):
        build_control_pack_evidence(
            pack,
            controls,
            person_controls,
            geographies={
                "24660244": {
                    "total_population": 15,
                    "persons_in_private_households": 15,
                }
            },
            controls_source_revisions=["unreviewed"],
        )

    other_person_controls = _tables(
        pack.identifier, households, persons, geographies=("24660245",)
    )[1]
    with pytest.raises(ValueError, match="identical geographies"):
        build_control_pack_evidence(
            pack,
            controls,
            other_person_controls,
            geographies={
                "24660244": {
                    "total_population": 15,
                    "persons_in_private_households": 15,
                }
            },
            controls_source_revisions=pack.source_revisions,
        )

    with pytest.raises(ValueError, match="cover exactly"):
        build_control_pack_evidence(
            pack,
            controls,
            person_controls,
            geographies={
                "24660245": {
                    "total_population": 15,
                    "persons_in_private_households": 15,
                }
            },
            controls_source_revisions=pack.source_revisions,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["margins"][0].update(
                {"control_identifier": "unknown.control.v1"}
            ),
            "unknown control",
        ),
        (
            lambda payload: payload.update({"registry_revision": "2026-08-09"}),
            "registry revision",
        ),
        (
            lambda payload: payload.update({"required_person_fields": ["AGEGRP"]}),
            "required_person_fields",
        ),
        (
            lambda payload: payload["margins"][2].update(
                {"dimensions": ["da", "AGEGRP", "GENDER"]}
            ),
            "requires dimensions",
        ),
        (
            lambda payload: payload.update({"geography_column": "ct"}),
            "geography_column must match geography_level",
        ),
        (
            lambda payload: payload.update(
                {"identifier_namespace": "statcan:census:2021:ct"}
            ),
            "identifier_namespace",
        ),
        (
            lambda payload: payload["margins"][0].update(
                {"control_identifier": "statcan.2016.household-size.v1"}
            ),
            "incompatible census vintage",
        ),
        (
            lambda payload: payload["margins"][0].update({"entity_level": "person"}),
            "incompatible entity level",
        ),
        (
            lambda payload: payload.update({"required_entity_levels": ["household"]}),
            "required_entity_levels",
        ),
        (
            lambda payload: payload.update({"required_household_fields": ["TENUR"]}),
            "required_household_fields",
        ),
        (
            lambda payload: payload.update({"source_revisions": ["unreviewed"]}),
            "source_revisions",
        ),
    ],
)
def test_external_manifest_semantics_resolve_against_registry(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    payload = load_control_pack("statcan-2021-core-private-household-da-v1").as_dict()
    mutation(payload)
    payload["definition_sha256"] = _semantic_checksum(payload)
    path = tmp_path / "invalid-pack.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match=message):
        read_control_pack(path)


def test_compatibility_uses_fields_and_linked_schema_without_invented_profile_id() -> (
    None
):
    pack = load_control_pack("statcan-2016-core-private-household-ct-v1")

    valid = validate_control_pack_compatibility(
        pack,
        census_vintage=2016,
        geography_level="ct",
        linked_schema_version=LINKED_POPULATION_SCHEMA_VERSION,
        household_fields={"household_size", "TENUR"},
        person_fields={"AGEGRP", "SEX"},
        model_profile="a-user-defined-profile",
    )
    invalid = validate_control_pack_compatibility(
        pack,
        census_vintage=2021,
        geography_level="da",
        linked_schema_version="future-linked-v2",
        household_fields={"TENUR"},
        person_fields={"AGEGRP"},
    )

    assert valid["passed"] is True
    assert valid["compatibility_basis"] == "required-fields-and-linked-schema"
    assert pack.compatible_model_profiles == []
    assert {issue["kind"] for issue in invalid["issues"]} == {
        "incompatible_census_vintage",
        "incompatible_geography_level",
        "incompatible_linked_schema",
        "missing_household_fields",
        "missing_person_fields",
    }


def test_compatibility_rejects_an_undeclared_real_model_profile() -> None:
    payload = load_control_pack("statcan-2021-core-private-household-da-v1").as_dict()
    payload["compatible_model_profiles"] = ["canada-2021-all-fields"]
    payload["definition_sha256"] = _semantic_checksum(payload)
    pack = ControlPackManifest.model_validate(payload)

    report = validate_control_pack_compatibility(
        pack,
        census_vintage=2021,
        geography_level="DA",
        linked_schema_version=LINKED_POPULATION_SCHEMA_VERSION,
        household_fields={"household_size", "TENUR"},
        person_fields={"AGEGRP", "GENDER"},
        model_profile="ontario-2021-all-fields",
    )

    assert report["passed"] is False
    assert _issue_kinds({"issues": report["issues"]}) == {"incompatible_model_profile"}


def test_candidate_derivations_are_non_mutating_and_vintage_specific() -> None:
    households, persons = _population(2021)
    derived_households, derived_persons = apply_control_pack_derivations(
        "statcan-2021-core-private-household-da-v1",
        households,
        persons,
    )

    assert "household_size_group" not in households[0]
    assert "age_group_3" not in persons[0]
    assert [row["household_size_group"] for row in derived_households] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert {row["age_group_3"] for row in derived_persons} == {
        "0_14",
        "15_64",
        "65_plus",
    }
    assert all("GENDER" in row for row in derived_persons)


def test_candidate_derivation_rejects_unmapped_age_without_mutating() -> None:
    households, persons = _population(2016)
    persons[0]["AGEGRP"] = "19"

    with pytest.raises(ValueError, match="unmapped category '19'"):
        apply_control_pack_derivations(
            "statcan-2016-core-private-household-csd-v1",
            households,
            persons,
        )
    assert "age_group_3" not in persons[0]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "value is missing"),
        ("not-an-integer", "expected an integer"),
        ("0", "expected a positive integer"),
    ],
)
def test_candidate_derivation_rejects_invalid_household_size_values(
    value: str | None,
    message: str,
) -> None:
    households, persons = _population(2021)
    if value is None:
        households[0].pop("household_size")
    else:
        households[0]["household_size"] = value

    with pytest.raises(ValueError, match=message):
        apply_control_pack_derivations(
            "statcan-2021-core-private-household-da-v1",
            households,
            persons,
        )


def test_evidence_round_trip_binds_semantically_normalized_control_tables(
    tmp_path: Path,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    tables = _tables(pack_id, households, persons, geographies=("24660244",))
    evidence = _evidence(pack_id, *tables, ("24660244",))
    path = write_control_pack_evidence(evidence, tmp_path / "evidence.json")

    assert read_control_pack_evidence(path) == evidence
    assert evidence.as_dict()["schema_version"] == (
        "synthpopcan-control-pack-evidence-v1"
    )
    int_table = ControlTable(
        margins=(
            ControlMargin(
                "x",
                ("da", "category"),
                (ControlCell({"da": "1", "category": "a"}, 1),),
            ),
        ),
        dimensions=("da", "category"),
    )
    float_table = ControlTable(
        margins=(
            ControlMargin(
                "x",
                ("da", "category"),
                (ControlCell({"da": "1", "category": "a"}, 1.0),),
            ),
        ),
        dimensions=("da", "category"),
    )
    assert control_table_sha256(int_table) == control_table_sha256(float_table)


def test_evidence_model_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ControlPackEvidence.model_validate(
            {
                "schema_version": "synthpopcan-control-pack-evidence-v1",
                "pack_identifier": "x",
                "pack_definition_sha256": "0" * 64,
                "census_vintage": 2021,
                "geography_level": "da",
                "identifier_namespace": "x",
                "controls_source_revisions": ["x"],
                "household_controls_sha256": "0" * 64,
                "person_controls_sha256": "0" * 64,
                "geographies": {
                    "1": {
                        "total_population": 1,
                        "persons_in_private_households": 1,
                    }
                },
                "excluded_geographies": {},
                "unexpected": True,
            }
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


def test_plan_requires_bound_evidence_and_rejects_nonzero_collective_population() -> (
    None
):
    pack_id = "statcan-2016-core-private-household-da-v1"
    households, persons = _population(2016)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )

    missing = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
    )
    nonzero = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=_evidence(
            pack_id,
            household_controls,
            person_controls,
            ("24660244",),
            collective_people=2,
        ),
    )

    assert missing["passed"] is False
    assert "missing_control_pack_evidence" in _issue_kinds(missing)
    assert nonzero["passed"] is False
    assert "nonzero_collective_population" in _issue_kinds(nonzero)


def test_plan_fails_closed_on_constructed_non_numeric_universe_evidence() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    geography = "24660244"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=(geography,)
    )
    evidence = _evidence(pack_id, household_controls, person_controls, (geography,))
    invalid_universe = GeographyUniverseEvidence.model_construct(
        total_population=True,
        persons_in_private_households=15,
    )
    constructed_evidence = evidence.model_copy(
        update={"geographies": {geography: invalid_universe}}
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=constructed_evidence,
    )

    assert plan["passed"] is False
    assert "invalid_private_household_universe_evidence" in _issue_kinds(plan)


def test_plan_deduplicates_identical_downstream_preflight_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    geography = "24660244"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=(geography,)
    )
    duplicate = {
        "severity": "error",
        "kind": "shared_preflight_failure",
        "message": "the shared support check failed",
    }
    monkeypatch.setattr(
        control_pack_module,
        "check_small_area_calibration_inputs",
        lambda *_args, **_kwargs: {"passed": False, "issues": [duplicate]},
    )
    monkeypatch.setattr(
        control_pack_module,
        "check_linked_person_calibration_inputs",
        lambda *_args, **_kwargs: {"passed": False, "issues": [duplicate]},
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=_evidence(
            pack_id,
            household_controls,
            person_controls,
            (geography,),
        ),
    )

    matching = [
        issue for issue in plan["issues"] if issue["kind"] == "shared_preflight_failure"
    ]
    assert matching == [duplicate]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("census_vintage", 2016),
        ("geography_level", "ct"),
        ("identifier_namespace", "statcan:census:2021:ct"),
        ("controls_source_revisions", ["unreviewed source"]),
        ("household_controls_sha256", "0" * 64),
    ],
)
def test_plan_rejects_mislabelled_or_unbound_evidence(field: str, value) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    payload = _evidence(
        pack_id,
        household_controls,
        person_controls,
        ("24660244",),
    ).as_dict()
    payload[field] = value
    evidence = ControlPackEvidence.model_validate(payload)

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "control_pack_evidence_mismatch" in _issue_kinds(plan)


def test_plan_rejects_duplicate_cells_before_ipf_can_overwrite_them() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    size, tenure = household_controls.margins
    household_controls = ControlTable(
        margins=(
            ControlMargin(
                size.name,
                size.dimensions,
                (*size.cells, size.cells[0]),
            ),
            tenure,
        ),
        dimensions=household_controls.dimensions,
    )
    evidence = _evidence(
        pack_id,
        household_controls,
        person_controls,
        ("24660244",),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "duplicate_control_cells" in _issue_kinds(plan)


def test_plan_rejects_required_margin_missing_one_geography() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    geographies = ("24660244", "24660245")
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=geographies
    )
    size, tenure = household_controls.margins
    household_controls = ControlTable(
        margins=(
            size,
            ControlMargin(
                tenure.name,
                tenure.dimensions,
                tuple(
                    cell for cell in tenure.cells if cell.categories["da"] != "24660245"
                ),
            ),
        ),
        dimensions=household_controls.dimensions,
    )
    evidence = _evidence(
        pack_id,
        household_controls,
        person_controls,
        geographies,
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "missing_required_margin_geographies" in _issue_kinds(plan)


@pytest.mark.parametrize(
    ("delta", "status", "within_tolerance"),
    [
        (3, "within-source-tolerance-requires-reconciliation", True),
        (6, "outside-source-tolerance", False),
    ],
)
def test_plan_applies_source_vector_tolerance_but_requires_exact_normalization(
    delta: int,
    status: str,
    within_tolerance: bool,
) -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    size, tenure = household_controls.margins
    changed_cells = list(tenure.cells)
    first = changed_cells[0]
    changed_cells[0] = ControlCell(first.categories, first.count + delta)
    household_controls = ControlTable(
        margins=(
            size,
            ControlMargin(tenure.name, tenure.dimensions, tuple(changed_cells)),
        ),
        dimensions=household_controls.dimensions,
    )
    evidence = _evidence(
        pack_id,
        household_controls,
        person_controls,
        ("24660244",),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )
    row = plan["margin_total_reconciliation"]["rows"][0]
    issue = next(
        item for item in plan["issues"] if item["kind"] == "unreconciled_control_totals"
    )

    assert plan["passed"] is False
    assert row["status"] == status
    assert row["source_vector_tolerance"] == 5.0
    assert issue["within_source_tolerance"] is within_tolerance


def test_plan_rejects_incomplete_category_vector() -> None:
    pack_id = "statcan-2016-core-private-household-csd-v1"
    households, persons = _population(2016)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("2466023",)
    )
    person_margin = person_controls.margins[0]
    person_controls = ControlTable(
        margins=(
            ControlMargin(
                person_margin.name,
                person_margin.dimensions,
                person_margin.cells[:-1],
            ),
        ),
        dimensions=person_controls.dimensions,
    )
    evidence = build_control_pack_evidence(
        pack_id,
        household_controls,
        person_controls,
        geographies={
            "2466023": {
                "total_population": 14,
                "persons_in_private_households": 14,
            }
        },
        controls_source_revisions=load_control_pack(pack_id).source_revisions,
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "control_category_vector_mismatch" in _issue_kinds(plan)


def test_plan_reports_invalid_evidence_and_candidate_derivation_failures() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )

    invalid_evidence = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        person_controls,
        evidence={"schema_version": "unsupported"},
    )
    assert "invalid_control_pack_evidence" in _issue_kinds(invalid_evidence)

    invalid_households = [dict(row) for row in households]
    invalid_households[0]["household_size"] = "unknown"
    derivation_failure = plan_control_pack(
        pack_id,
        invalid_households,
        persons,
        household_controls,
        person_controls,
        evidence=_evidence(
            pack_id,
            household_controls,
            person_controls,
            ("24660244",),
        ),
    )
    assert derivation_failure["passed"] is False
    assert "candidate_derivation_failed" in _issue_kinds(derivation_failure)


def test_plan_reports_disjoint_household_and_person_geographies() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, matching_person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    disjoint_person_controls = _tables(
        pack_id, households, persons, geographies=("24660245",)
    )[1]
    evidence = _evidence(
        pack_id,
        household_controls,
        matching_person_controls,
        ("24660244",),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        household_controls,
        disjoint_person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert {
        "incompatible_geography_intersection",
        "empty_geography_intersection",
        "unexpected_universe_evidence_geographies",
    } <= _issue_kinds(plan)
    assert plan["geographies"]["household_only"] == ["24660244"]
    assert plan["geographies"]["person_only"] == ["24660245"]


def test_plan_enforces_an_external_manifest_explicit_geography_selection() -> None:
    payload = load_control_pack("statcan-2021-core-private-household-da-v1").as_dict()
    payload["expected_geographies"]["identifiers"] = ["24660245"]
    payload["definition_sha256"] = _semantic_checksum(payload)
    pack = ControlPackManifest.model_validate(payload)
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack.identifier, households, persons, geographies=("24660244",)
    )
    evidence = build_control_pack_evidence(
        pack,
        household_controls,
        person_controls,
        geographies={
            "24660244": {
                "total_population": 15,
                "persons_in_private_households": 15,
            }
        },
        controls_source_revisions=pack.source_revisions,
    )

    plan = plan_control_pack(
        pack,
        households,
        persons,
        household_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "unexpected_geography_set" in _issue_kinds(plan)


def test_plan_reports_missing_margin_structure_before_calibration() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    missing_tenure = ControlTable(
        margins=(household_controls.margins[0],),
        dimensions=household_controls.margins[0].dimensions,
    )
    evidence = _evidence(pack_id, missing_tenure, person_controls, ("24660244",))

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        missing_tenure,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "control_margin_structure_mismatch" in _issue_kinds(plan)
    assert plan["household_preflight"] == {"passed": False, "issues": []}


def test_plan_turns_invalid_control_geography_into_a_structured_issue() -> None:
    pack_id = "statcan-2021-core-private-household-da-v1"
    households, persons = _population(2021)
    household_controls, person_controls = _tables(
        pack_id, households, persons, geographies=("24660244",)
    )
    size, tenure = household_controls.margins
    first = size.cells[0]
    invalid_size = ControlMargin(
        size.name,
        size.dimensions,
        (
            ControlCell(
                {"household_size_group": first.categories["household_size_group"]},
                first.count,
            ),
            *size.cells[1:],
        ),
    )
    invalid_controls = ControlTable(
        margins=(invalid_size, tenure),
        dimensions=household_controls.dimensions,
    )
    evidence = _evidence(
        pack_id,
        household_controls,
        person_controls,
        ("24660244",),
    )

    plan = plan_control_pack(
        pack_id,
        households,
        persons,
        invalid_controls,
        person_controls,
        evidence=evidence,
    )

    assert plan["passed"] is False
    assert "invalid_control_geography" in _issue_kinds(plan)
