"""Control packs behaviour and regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.control_pack_fixtures import (
    _RELEASED_CORE_PACK_HASHES,
    _evidence,
    _issue_kinds,
    _population,
    _semantic_checksum,
    _tables,
)

import synthpopcan.control_packs as control_pack_module
from synthpopcan.control_packs import (
    COMPATIBILITY_REGISTRY_SCHEMA_VERSION,
    ControlPackManifest,
    list_builtin_control_packs,
    load_compatibility_registry,
    load_control_pack,
    load_control_pack_evidence,
    read_control_pack,
    read_control_pack_evidence,
    validate_control_pack_compatibility,
    write_control_pack,
    write_control_pack_evidence,
)
from synthpopcan.linked_schema import LINKED_POPULATION_SCHEMA_VERSION


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
