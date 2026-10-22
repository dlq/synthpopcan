"""Control pack contracts behaviour and regression tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.control_pack_fixtures import (
    _evidence,
    _population,
    _tables,
)

from synthpopcan.control_packs import (
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
    build_control_pack_evidence,
    control_table_sha256,
    load_compatibility_registry,
    load_control_pack,
    read_control_pack,
    read_control_pack_evidence,
    write_control_pack,
    write_control_pack_evidence,
)
from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
)


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


def test_nested_manifest_mutation_fails_closed_at_use_and_serialization() -> None:
    """Pydantic's frozen shell must not permit stale semantic checksums at use."""

    pack = load_control_pack("statcan-2021-core-private-household-da-v1")
    pack.known_limitations.append("mutation that bypasses shallow frozen=True")

    with pytest.raises(ValueError, match="definition_sha256"):
        load_control_pack(pack)
    with pytest.raises(ValueError, match="definition_sha256"):
        pack.as_dict()


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
