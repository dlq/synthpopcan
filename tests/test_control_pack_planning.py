"""Control pack planning behaviour and regression tests."""

from __future__ import annotations

import pytest
from support.control_pack_fixtures import (
    _evidence,
    _issue_kinds,
    _population,
    _semantic_checksum,
    _tables,
)

import synthpopcan.control_packs as control_pack_module
from synthpopcan.control_packs import (
    ControlPackEvidence,
    ControlPackManifest,
    GeographyUniverseEvidence,
    build_control_pack_evidence,
    load_control_pack,
    plan_control_pack,
)
from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
)


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
    issue = next(
        item for item in plan["issues"] if item["kind"] == "duplicate_control_cells"
    )
    assert set(issue) == {
        "severity",
        "kind",
        "message",
        "entity_level",
        "control_identifier",
        "cells",
    }
    assert issue["cells"] == [["24660244", "1"]]


def test_plan_reports_control_cell_keys_outside_declared_dimensions() -> None:
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
            ControlCell({**first.categories, "unexpected": "value"}, first.count),
            *size.cells[1:],
        ),
    )
    invalid_controls = ControlTable(
        margins=(invalid_size, tenure),
        dimensions=household_controls.dimensions,
    )
    evidence = _evidence(
        pack_id,
        invalid_controls,
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

    issue = next(
        item
        for item in plan["issues"]
        if item["kind"] == "control_cell_structure_mismatch"
    )
    assert plan["passed"] is False
    assert issue["cells"] == [
        {
            "index": 1,
            "missing_dimensions": [],
            "extra_dimensions": ["unexpected"],
        }
    ]


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
