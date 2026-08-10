"""Versioned small-area control-pack definitions and feasibility planning.

The built-in packs are deliberately definitions rather than downloaded Census
counts.  They describe the reviewed source rows, category crosswalks, universe
rules, and candidate derivations needed to turn a bounded Census extract into
household and linked-person controls.  Counts remain separate, inspectable
``ControlTable`` inputs so suppression and geography exclusions cannot be
hidden inside package data.
"""

from __future__ import annotations

__all__ = [
    "COMPATIBILITY_REGISTRY_SCHEMA_VERSION",
    "CONTROL_PACK_SCHEMA_VERSION",
    "ControlCompatibilityRegistry",
    "ControlDefinition",
    "ControlPackEvidence",
    "ControlPackManifest",
    "apply_control_pack_derivations",
    "build_control_pack_evidence",
    "control_table_sha256",
    "list_builtin_control_packs",
    "load_compatibility_registry",
    "load_control_pack",
    "load_control_pack_evidence",
    "plan_control_pack",
    "read_control_pack",
    "read_control_pack_evidence",
    "validate_control_pack_compatibility",
    "write_control_pack",
    "write_control_pack_evidence",
]

import hashlib
import json
import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from synthpopcan.controls import ControlMargin, ControlTable
from synthpopcan.linked_schema import LINKED_POPULATION_SCHEMA_VERSION
from synthpopcan.small_area_synthesis import (
    check_linked_person_calibration_inputs,
    check_small_area_calibration_inputs,
    controls_by_geography,
)

COMPATIBILITY_REGISTRY_SCHEMA_VERSION = "synthpopcan-control-compatibility-registry-v1"
CONTROL_PACK_SCHEMA_VERSION = "synthpopcan-control-pack-v1"
CONTROL_PACK_PLAN_SCHEMA_VERSION = "synthpopcan-control-pack-plan-v1"
CONTROL_PACK_EVIDENCE_SCHEMA_VERSION = "synthpopcan-control-pack-evidence-v1"

_CENSUS_VINTAGES = (2016, 2021)
_GEOGRAPHY_LEVELS = ("csd", "ct", "ada", "da")
_STATCAN_OPEN_LICENCE = "https://www.statcan.gc.ca/en/reference/licence"
_PROFILE_URLS = {
    2016: (
        "https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/"
        "index.cfm?Lang=E"
    ),
    2021: (
        "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/"
        "index.cfm?Lang=E"
    ),
}
_PROFILE_REVISIONS = {
    2016: "Census Profile, 2016 Census, catalogue 98-316-X2016001",
    2021: "Census Profile, 2021 Census, catalogue 98-316-X2021001",
}

EntityLevel = Literal["household", "person"]
GeographyLevel = Literal["csd", "ct", "ada", "da"]
ControlStatus = Literal["implemented", "planned", "validation-only", "unavailable"]


class _BoundaryModel(BaseModel):
    """Reject coercion and unknown fields at persisted contract boundaries."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation with stable field names."""

        return self.model_dump(mode="json")


class ReviewRecord(_BoundaryModel):
    reviewer: str = Field(min_length=1)
    reviewed_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    evidence: list[str] = Field(min_length=1)


class SourceDefinition(_BoundaryModel):
    product: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")
    licence_url: str = Field(pattern=r"^https://")
    root_characteristic_id: str = Field(min_length=1)
    root_label: str = Field(min_length=1)
    estimate_type: Literal["100%-count", "25%-sample-count"]
    unit: Literal["private-households", "persons"]


class UniverseDefinition(_BoundaryModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    source_label: str = Field(min_length=1)
    calibration_label: str = Field(min_length=1)
    reference_period: str = Field(min_length=1)
    reconciliation: Literal["identity", "zero-collective-only"]
    companion_characteristic_id: str | None = None
    companion_label: str | None = None

    @model_validator(mode="after")
    def _require_companion_for_reconciliation(self) -> Self:
        companion_fields = (
            self.companion_characteristic_id,
            self.companion_label,
        )
        if self.reconciliation == "zero-collective-only" and not all(companion_fields):
            raise ValueError(
                "zero-collective-only universes require a companion characteristic"
            )
        if self.reconciliation == "identity" and any(companion_fields):
            raise ValueError("identity universes cannot declare a companion")
        return self


class SuppressionPolicy(_BoundaryModel):
    suppressed_tokens: list[str] = Field(min_length=1)
    suppressed_cell: Literal["exclude-geography"]
    missing_cell: Literal["exclude-geography"]
    observed_zero: Literal["preserve"]
    rounded_count: Literal["preserve-and-report"]
    vector_tolerance: float = Field(ge=0)


class CandidateDerivation(_BoundaryModel):
    output_field: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    method: Literal["identity", "top-code-integer", "category-crosswalk"]
    categories: dict[str, str] = Field(default_factory=dict)
    cap: int | None = Field(default=None, ge=1)
    unmapped: Literal["reject"] = "reject"

    @model_validator(mode="after")
    def _validate_method_inputs(self) -> Self:
        if self.method == "top-code-integer":
            if self.cap is None or self.categories:
                raise ValueError(
                    "top-code-integer derivations require cap and no categories"
                )
        elif self.method == "category-crosswalk":
            if not self.categories or self.cap is not None:
                raise ValueError(
                    "category-crosswalk derivations require categories and no cap"
                )
        elif self.categories or self.cap is not None:
            raise ValueError("identity derivations cannot declare mapping inputs")
        return self


class SourceCategory(_BoundaryModel):
    target_category: str = Field(min_length=1)
    source_characteristic_ids: list[str] = Field(default_factory=list)
    source_count_columns: list[str] = Field(default_factory=list)
    source_labels: list[str] = Field(min_length=1)
    mapping: Literal["direct", "coarsened", "component"]

    @model_validator(mode="after")
    def _require_source_selector(self) -> Self:
        if not self.source_characteristic_ids and not self.source_count_columns:
            raise ValueError(
                "a source category requires characteristic IDs or count columns"
            )
        return self


class SourceAxis(_BoundaryModel):
    candidate_field: str = Field(min_length=1)
    categories: list[SourceCategory] = Field(min_length=1)

    @model_validator(mode="after")
    def _categories_are_unique(self) -> Self:
        values = [category.target_category for category in self.categories]
        if len(values) != len(set(values)):
            raise ValueError("source-axis target categories must be unique")
        return self


class ControlDefinition(_BoundaryModel):
    identifier: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    concept_identifier: str = Field(pattern=r"^[a-z][a-z0-9.-]*$")
    census_vintage: Literal[2016, 2021]
    entity_level: EntityLevel
    generated_fields: list[str] = Field(min_length=1)
    candidate_derivations: list[CandidateDerivation] = Field(min_length=1)
    source: SourceDefinition
    universe: UniverseDefinition
    geography_levels: list[GeographyLevel] = Field(min_length=1)
    classification: Literal["exact", "coarsened", "component", "banded"]
    source_axes: list[SourceAxis] = Field(min_length=1)
    suppression: SuppressionPolicy
    complete_mutually_exclusive_vector: Literal[True]
    compatible_companion_fields: list[str]
    privacy_notes: list[str] = Field(min_length=1)
    interpretation_notes: list[str] = Field(min_length=1)
    status: Literal["implemented"]
    review: ReviewRecord

    @model_validator(mode="after")
    def _validate_control_shape(self) -> Self:
        derivation_fields = [item.output_field for item in self.candidate_derivations]
        axis_fields = [axis.candidate_field for axis in self.source_axes]
        if len(derivation_fields) != len(set(derivation_fields)):
            raise ValueError("candidate derivation output fields must be unique")
        if axis_fields != derivation_fields:
            raise ValueError(
                "source axes must match candidate derivations in declared order"
            )
        if len(self.geography_levels) != len(set(self.geography_levels)):
            raise ValueError("control geography levels must be unique")
        return self


class FieldCompatibility(_BoundaryModel):
    concept_identifier: str = Field(pattern=r"^[a-z][a-z0-9.-]*$")
    entity_level: EntityLevel
    fields_2016: list[str]
    fields_2021: list[str]
    control_identifiers: list[str]
    status: ControlStatus
    notes: list[str] = Field(min_length=1)


class ControlCompatibilityRegistry(_BoundaryModel):
    schema_version: Literal["synthpopcan-control-compatibility-registry-v1"] = (
        COMPATIBILITY_REGISTRY_SCHEMA_VERSION
    )
    revision: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fields: list[FieldCompatibility] = Field(min_length=1)
    controls: list[ControlDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_registry_references(self) -> Self:
        concepts = [record.concept_identifier for record in self.fields]
        controls = [record.identifier for record in self.controls]
        if len(concepts) != len(set(concepts)):
            raise ValueError("registry concept identifiers must be unique")
        if len(controls) != len(set(controls)):
            raise ValueError("registry control identifiers must be unique")
        known_controls = set(controls)
        for field in self.fields:
            unknown = set(field.control_identifiers) - known_controls
            if unknown:
                raise ValueError(
                    f"registry concept {field.concept_identifier!r} references "
                    f"unknown controls {sorted(unknown)!r}"
                )
        mapped_concepts = {control.concept_identifier for control in self.controls}
        if not mapped_concepts <= set(concepts):
            raise ValueError("every control must map to a registered field concept")
        return self


class PackMargin(_BoundaryModel):
    control_identifier: str = Field(min_length=1)
    entity_level: EntityLevel
    dimensions: list[str] = Field(min_length=1)
    priority: Literal["required"]


class ExpectedGeographies(_BoundaryModel):
    policy: Literal["explicit-bounded-selection"]
    identifiers: list[str] = Field(default_factory=list)
    exclusions: dict[str, str] = Field(default_factory=dict)


class RecommendedCalibration(_BoundaryModel):
    max_iterations: int = Field(ge=1)
    tolerance: float = Field(ge=0)
    integerization: Literal["deterministic-systematic-midpoint-v1"]
    preserve_linkage: Literal[True]
    planning_pool_size: int = Field(ge=1)


class GeographyUniverseEvidence(_BoundaryModel):
    total_population: int | float = Field(ge=0)
    persons_in_private_households: int | float = Field(ge=0)

    @model_validator(mode="after")
    def _numbers_are_finite(self) -> Self:
        if not all(
            math.isfinite(float(value))
            for value in (
                self.total_population,
                self.persons_in_private_households,
            )
        ):
            raise ValueError("universe evidence counts must be finite")
        return self


class ControlPackEvidence(_BoundaryModel):
    """Source and universe evidence bound to exact pack and control tables."""

    schema_version: Literal["synthpopcan-control-pack-evidence-v1"] = (
        CONTROL_PACK_EVIDENCE_SCHEMA_VERSION
    )
    pack_identifier: str = Field(min_length=1)
    pack_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    census_vintage: Literal[2016, 2021]
    geography_level: GeographyLevel
    identifier_namespace: str = Field(min_length=1)
    controls_source_revisions: list[str] = Field(min_length=1)
    household_controls_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    person_controls_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geographies: dict[str, GeographyUniverseEvidence] = Field(min_length=1)
    excluded_geographies: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _evidence_keys_are_valid(self) -> Self:
        if any(not identifier for identifier in self.geographies):
            raise ValueError("universe evidence geography identifiers cannot be empty")
        if set(self.geographies) & set(self.excluded_geographies):
            raise ValueError(
                "a geography cannot be both eligible and explicitly excluded"
            )
        if any(not reason for reason in self.excluded_geographies.values()):
            raise ValueError("excluded geographies require a non-empty reason")
        return self


class ControlPackManifest(_BoundaryModel):
    schema_version: Literal["synthpopcan-control-pack-v1"] = CONTROL_PACK_SCHEMA_VERSION
    identifier: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*-v\d+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    label: str = Field(min_length=1)
    census_vintage: Literal[2016, 2021]
    geography_level: GeographyLevel
    identifier_namespace: str = Field(min_length=1)
    geography_column: str = Field(min_length=1)
    registry_schema_version: Literal["synthpopcan-control-compatibility-registry-v1"]
    registry_revision: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    linked_schema_version: Literal["synthpopcan-linked-population-v1"]
    compatible_model_profiles: list[str]
    required_entity_levels: list[EntityLevel] = Field(min_length=1)
    required_household_fields: list[str] = Field(min_length=1)
    required_person_fields: list[str] = Field(min_length=1)
    common_universe: Literal["linked-private-households"]
    margins: list[PackMargin] = Field(min_length=1)
    expected_geographies: ExpectedGeographies
    source_revisions: list[str] = Field(min_length=1)
    recommended_calibration: RecommendedCalibration
    known_limitations: list[str] = Field(min_length=1)
    permitted_claims: list[str] = Field(min_length=1)
    review: ReviewRecord
    definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_pack_shape(self) -> Self:
        if len(self.required_entity_levels) != len(set(self.required_entity_levels)):
            raise ValueError("required entity levels must be unique")
        margin_ids = [margin.control_identifier for margin in self.margins]
        if len(margin_ids) != len(set(margin_ids)):
            raise ValueError("pack margin controls must be unique")
        expected_checksum = _pack_definition_sha256(self)
        if self.definition_sha256 != expected_checksum:
            raise ValueError(
                "control-pack definition_sha256 does not match its semantic fields"
            )
        return self


def _pack_definition_sha256(pack: ControlPackManifest | Mapping[str, Any]) -> str:
    if isinstance(pack, BaseModel):
        payload = pack.model_dump(mode="json")
    else:
        payload = dict(pack)
    payload.pop("definition_sha256", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source_category(
    target: str,
    labels: list[str],
    *,
    characteristic_ids: list[str] | None = None,
    count_columns: list[str] | None = None,
    mapping: Literal["direct", "coarsened", "component"] = "direct",
) -> dict[str, Any]:
    return {
        "target_category": target,
        "source_characteristic_ids": characteristic_ids or [],
        "source_count_columns": count_columns or [],
        "source_labels": labels,
        "mapping": mapping,
    }


def _review(*evidence: str) -> dict[str, Any]:
    return {
        "reviewer": "SynthPopCan maintainers",
        "reviewed_on": "2026-08-10",
        "evidence": list(evidence),
    }


def _suppression(*, tolerance: float) -> dict[str, Any]:
    return {
        "suppressed_tokens": ["x", "..", "...", "F"],
        "suppressed_cell": "exclude-geography",
        "missing_cell": "exclude-geography",
        "observed_zero": "preserve",
        "rounded_count": "preserve-and-report",
        "vector_tolerance": tolerance,
    }


def _control_definitions() -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for vintage in _CENSUS_VINTAGES:
        sex_field = "SEX" if vintage == 2016 else "GENDER"
        sex_columns = (
            [
                "Dim: Sex (3): Member ID: [2]: Male",
                "Dim: Sex (3): Member ID: [3]: Female",
            ]
            if vintage == 2016
            else ["C2_COUNT_MEN+", "C3_COUNT_WOMEN+"]
        )
        household_size_ids = (
            ["52", "53", "54", "55", "56"]
            if vintage == 2016
            else ["51", "52", "53", "54", "55"]
        )
        tenure_ids = (
            [["1618"], ["1619", "1620"]]
            if vintage == 2016
            else [["1415"], ["1416", "1417"]]
        )
        controls.extend(
            [
                {
                    "identifier": f"statcan.{vintage}.household-size.v1",
                    "concept_identifier": "household.size",
                    "census_vintage": vintage,
                    "entity_level": "household",
                    "generated_fields": ["household_size"],
                    "candidate_derivations": [
                        {
                            "output_field": "household_size_group",
                            "source_field": "household_size",
                            "method": "top-code-integer",
                            "categories": {},
                            "cap": 5,
                            "unmapped": "reject",
                        }
                    ],
                    "source": {
                        "product": "Statistics Canada Census Profile",
                        "revision": _PROFILE_REVISIONS[vintage],
                        "url": _PROFILE_URLS[vintage],
                        "licence_url": _STATCAN_OPEN_LICENCE,
                        "root_characteristic_id": "51" if vintage == 2016 else "50",
                        "root_label": "Total - Private households by household size",
                        "estimate_type": "100%-count",
                        "unit": "private-households",
                    },
                    "universe": {
                        "identifier": "private-households",
                        "source_label": "Private households",
                        "calibration_label": "Linked private households",
                        "reference_period": f"{vintage} Census reference date",
                        "reconciliation": "identity",
                    },
                    "geography_levels": list(_GEOGRAPHY_LEVELS),
                    "classification": "coarsened",
                    "source_axes": [
                        {
                            "candidate_field": "household_size_group",
                            "categories": [
                                _source_category(
                                    str(index),
                                    [
                                        f"{index} person"
                                        if index == 1
                                        else (
                                            "5 or more persons"
                                            if index == 5
                                            else f"{index} persons"
                                        )
                                    ],
                                    characteristic_ids=[member],
                                    mapping="coarsened" if index == 5 else "direct",
                                )
                                for index, member in enumerate(
                                    household_size_ids, start=1
                                )
                            ],
                        }
                    ],
                    "suppression": _suppression(tolerance=0.0),
                    "complete_mutually_exclusive_vector": True,
                    "compatible_companion_fields": [],
                    "privacy_notes": [
                        "Use published aggregate counts only; do not infer hidden "
                        "cells."
                    ],
                    "interpretation_notes": [
                        "Generated household sizes of five or more are top-coded to 5."
                    ],
                    "status": "implemented",
                    "review": _review(
                        "Profile root and child IDs cross-checked against both "
                        "bulk schemas.",
                        "Existing extract_controls_from_profile fixtures cover "
                        "both vintages.",
                    ),
                },
                {
                    "identifier": f"statcan.{vintage}.tenure.v1",
                    "concept_identifier": "household.tenure",
                    "census_vintage": vintage,
                    "entity_level": "household",
                    "generated_fields": ["TENUR"],
                    "candidate_derivations": [
                        {
                            "output_field": "TENUR",
                            "source_field": "TENUR",
                            "method": "identity",
                            "categories": {},
                            "cap": None,
                            "unmapped": "reject",
                        }
                    ],
                    "source": {
                        "product": "Statistics Canada Census Profile",
                        "revision": _PROFILE_REVISIONS[vintage],
                        "url": _PROFILE_URLS[vintage],
                        "licence_url": _STATCAN_OPEN_LICENCE,
                        "root_characteristic_id": (
                            "1617" if vintage == 2016 else "1414"
                        ),
                        "root_label": "Total - Private households by tenure",
                        "estimate_type": "25%-sample-count",
                        "unit": "private-households",
                    },
                    "universe": {
                        "identifier": "private-households",
                        "source_label": "Private households",
                        "calibration_label": "Linked private households",
                        "reference_period": f"{vintage} Census reference date",
                        "reconciliation": "identity",
                    },
                    "geography_levels": list(_GEOGRAPHY_LEVELS),
                    "classification": "coarsened",
                    "source_axes": [
                        {
                            "candidate_field": "TENUR",
                            "categories": [
                                _source_category(
                                    "1",
                                    ["Owner"],
                                    characteristic_ids=tenure_ids[0],
                                ),
                                _source_category(
                                    "2",
                                    (
                                        ["Renter", "Band housing"]
                                        if vintage == 2016
                                        else [
                                            "Renter",
                                            "Local government, First Nation or "
                                            "Indian band dwelling",
                                        ]
                                    ),
                                    characteristic_ids=tenure_ids[1],
                                    mapping="coarsened",
                                ),
                            ],
                        }
                    ],
                    "suppression": _suppression(tolerance=5.0),
                    "complete_mutually_exclusive_vector": True,
                    "compatible_companion_fields": [],
                    "privacy_notes": [
                        "Suppressed or missing 25% sample cells exclude the geography."
                    ],
                    "interpretation_notes": [
                        "Renter and band/local-government/First Nation categories are "
                        "combined because the hierarchical PUMF represents two "
                        "tenure codes."
                    ],
                    "status": "implemented",
                    "review": _review(
                        "Profile root and child IDs cross-checked against both "
                        "bulk schemas.",
                        "Band/local-government category coarsening matches the "
                        "generated TENUR field.",
                    ),
                },
                {
                    "identifier": f"statcan.{vintage}.private-age-gender.v1",
                    "concept_identifier": "person.age-sex-gender",
                    "census_vintage": vintage,
                    "entity_level": "person",
                    "generated_fields": ["AGEGRP", sex_field],
                    "candidate_derivations": [
                        {
                            "output_field": "age_group_3",
                            "source_field": "AGEGRP",
                            "method": "category-crosswalk",
                            "categories": {
                                **{str(value): "0_14" for value in range(1, 4)},
                                **{str(value): "15_64" for value in range(4, 14)},
                                **{str(value): "65_plus" for value in range(14, 19)},
                            },
                            "cap": None,
                            "unmapped": "reject",
                        },
                        {
                            "output_field": sex_field,
                            "source_field": sex_field,
                            "method": "identity",
                            "categories": {},
                            "cap": None,
                            "unmapped": "reject",
                        },
                    ],
                    "source": {
                        "product": "Statistics Canada Census Profile",
                        "revision": _PROFILE_REVISIONS[vintage],
                        "url": _PROFILE_URLS[vintage],
                        "licence_url": _STATCAN_OPEN_LICENCE,
                        "root_characteristic_id": "8",
                        "root_label": "Total - Age groups of the population",
                        "estimate_type": "100%-count",
                        "unit": "persons",
                    },
                    "universe": {
                        "identifier": "private-household-persons-zero-collective",
                        "source_label": "Total population",
                        "calibration_label": "People in linked private households",
                        "reference_period": f"{vintage} Census reference date",
                        "reconciliation": "zero-collective-only",
                        "companion_characteristic_id": (
                            "57" if vintage == 2016 else "56"
                        ),
                        "companion_label": "Number of persons in private households",
                    },
                    "geography_levels": list(_GEOGRAPHY_LEVELS),
                    "classification": "coarsened",
                    "source_axes": [
                        {
                            "candidate_field": "age_group_3",
                            "categories": [
                                _source_category(
                                    "0_14",
                                    ["0 to 14 years"],
                                    characteristic_ids=["9"],
                                    mapping="coarsened",
                                ),
                                _source_category(
                                    "15_64",
                                    ["15 to 64 years"],
                                    characteristic_ids=["13"],
                                    mapping="coarsened",
                                ),
                                _source_category(
                                    "65_plus",
                                    ["65 years and over"],
                                    characteristic_ids=["24"],
                                    mapping="coarsened",
                                ),
                            ],
                        },
                        {
                            "candidate_field": sex_field,
                            "categories": [
                                _source_category(
                                    "1",
                                    ["Male" if vintage == 2016 else "Men+"],
                                    count_columns=[sex_columns[0]],
                                ),
                                _source_category(
                                    "2",
                                    ["Female" if vintage == 2016 else "Women+"],
                                    count_columns=[sex_columns[1]],
                                ),
                            ],
                        },
                    ],
                    "suppression": _suppression(tolerance=0.0),
                    "complete_mutually_exclusive_vector": True,
                    "compatible_companion_fields": ["household_size"],
                    "privacy_notes": [
                        "A geography is eligible only when Profile total population "
                        "equals the published number of persons in private households.",
                        "Any non-zero, missing, or suppressed collective-population "
                        "difference excludes the geography rather than being imputed.",
                    ],
                    "interpretation_notes": [
                        "The Profile age root is total-population data. The strict "
                        "zero-collective reconciliation is what makes it an exact "
                        "private-household control for a bounded geography.",
                        (
                            "2016 SEX codes are not relabelled as gender."
                            if vintage == 2016
                            else (
                                "Men+ and Women+ include redistributed non-binary "
                                "persons."
                            )
                        ),
                    ],
                    "status": "implemented",
                    "review": _review(
                        "Profile age roots and broad child IDs verified against "
                        "metadata.",
                        "Private-household companion total makes the universe test "
                        "explicit.",
                        "The two-category 2021 Men+/Women+ interpretation is retained.",
                    ),
                },
            ]
        )
    return controls


def _field_inventory(controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    implemented = [
        {
            "concept_identifier": "household.size",
            "entity_level": "household",
            "fields_2016": ["household_size"],
            "fields_2021": ["household_size"],
            "control_identifiers": [
                "statcan.2016.household-size.v1",
                "statcan.2021.household-size.v1",
            ],
            "status": "implemented",
            "notes": ["Top-coded to five or more for small-area calibration."],
        },
        {
            "concept_identifier": "household.tenure",
            "entity_level": "household",
            "fields_2016": ["TENUR"],
            "fields_2021": ["TENUR"],
            "control_identifiers": [
                "statcan.2016.tenure.v1",
                "statcan.2021.tenure.v1",
            ],
            "status": "implemented",
            "notes": ["Band/local-government housing is coarsened with renter."],
        },
        {
            "concept_identifier": "person.age-sex-gender",
            "entity_level": "person",
            "fields_2016": ["AGEGRP", "SEX"],
            "fields_2021": ["AGEGRP", "GENDER"],
            "control_identifiers": [
                "statcan.2016.private-age-gender.v1",
                "statcan.2021.private-age-gender.v1",
            ],
            "status": "implemented",
            "notes": [
                "Implemented only where total population equals persons in private "
                "households."
            ],
        },
    ]
    planned_fields = {
        "household.dwelling-type": ("household", ["DTYPE"], ["DTYPE"]),
        "household.rooms": ("household", ["ROOM"], ["ROOM"]),
        "household.bedrooms": ("household", ["BEDRM"], ["BEDRM"]),
        "household.condominium": ("household", ["CONDO"], ["CONDO"]),
        "household.repair": ("household", ["REPAIR"], ["REPAIR"]),
        "household.construction-period": ("household", ["BUILT"], ["BUILT"]),
        "household.housing-suitability": ("household", ["NOS"], ["NOS"]),
        "person.marital-status": ("person", ["MarStH"], ["MARSTH"]),
        "person.citizenship": ("person", ["CITIZEN"], ["CITIZEN"]),
        "person.immigration-status": ("person", ["IMMSTAT"], ["IMMSTAT"]),
        "person.generation-status": ("person", ["GENSTAT"], ["GENSTAT"]),
        "person.place-of-birth": ("person", ["POB"], ["POB"]),
        "person.visible-minority": ("person", ["VISMIN"], ["VISMIN"]),
        "person.education": ("person", ["HDGREE"], ["HDGREE"]),
        "person.labour-force": ("person", ["LFTAG"], ["LFACT"]),
        "person.work-activity": (
            "person",
            ["FPTWK", "WRKACT"],
            ["FPTWK", "WRKACT"],
        ),
        "person.employment-income": ("person", ["EMPIN"], ["EMPIN"]),
        "person.total-income": ("person", ["TOTINC"], ["TOTINC"]),
    }
    unavailable_fields = {
        "household.dwelling-value": ("household", ["VALUE"], ["VALUE"]),
        "household.shelter-cost": ("household", ["SHELCO"], ["SHELCO"]),
        "household.condominium-fee": ("household", ["FCOND"], ["FCOND"]),
        "person.hours-worked": ("person", ["HRSWRK"], ["HRSWRK"]),
        "person.weeks-worked": ("person", ["WKSWRK"], ["WKSWRK"]),
    }
    result = list(implemented)
    for concept, (entity, fields_2016, fields_2021) in planned_fields.items():
        result.append(
            {
                "concept_identifier": concept,
                "entity_level": entity,
                "fields_2016": fields_2016,
                "fields_2021": fields_2021,
                "control_identifiers": [],
                "status": "planned",
                "notes": [
                    "Candidate source family exists, but its crosswalk is outside "
                    "the pre-1.0 control-pack cut line."
                ],
            }
        )
    for concept, (entity, fields_2016, fields_2021) in unavailable_fields.items():
        result.append(
            {
                "concept_identifier": concept,
                "entity_level": entity,
                "fields_2016": fields_2016,
                "fields_2021": fields_2021,
                "control_identifiers": [],
                "status": "unavailable",
                "notes": [
                    "The Census Profile has no matching count distribution; the field "
                    "must not be described as locally controlled."
                ],
            }
        )
    assert controls
    return result


def load_compatibility_registry() -> ControlCompatibilityRegistry:
    """Return the immutable built-in field/control compatibility registry."""

    controls = _control_definitions()
    return ControlCompatibilityRegistry.model_validate(
        {
            "schema_version": COMPATIBILITY_REGISTRY_SCHEMA_VERSION,
            "revision": "2026-08-10",
            "fields": _field_inventory(controls),
            "controls": controls,
        }
    )


def _pack_payload(vintage: int, geography_level: str) -> dict[str, Any]:
    sex_field = "SEX" if vintage == 2016 else "GENDER"
    identifier = f"statcan-{vintage}-core-private-household-{geography_level}-v1"
    payload: dict[str, Any] = {
        "schema_version": CONTROL_PACK_SCHEMA_VERSION,
        "identifier": identifier,
        "version": "1.0.0",
        "label": (
            f"Statistics Canada {vintage} core private-household "
            f"{geography_level.upper()} controls"
        ),
        "census_vintage": vintage,
        "geography_level": geography_level,
        "identifier_namespace": f"statcan:census:{vintage}:{geography_level}",
        "geography_column": geography_level,
        "registry_schema_version": COMPATIBILITY_REGISTRY_SCHEMA_VERSION,
        "registry_revision": "2026-08-10",
        "linked_schema_version": LINKED_POPULATION_SCHEMA_VERSION,
        # Compatibility is field- and linked-schema-based. Model packages do not
        # yet expose a stable public profile identifier, so v1 does not invent one.
        "compatible_model_profiles": [],
        "required_entity_levels": ["household", "person"],
        "required_household_fields": ["household_size", "TENUR"],
        "required_person_fields": ["AGEGRP", sex_field],
        "common_universe": "linked-private-households",
        "margins": [
            {
                "control_identifier": f"statcan.{vintage}.household-size.v1",
                "entity_level": "household",
                "dimensions": [geography_level, "household_size_group"],
                "priority": "required",
            },
            {
                "control_identifier": f"statcan.{vintage}.tenure.v1",
                "entity_level": "household",
                "dimensions": [geography_level, "TENUR"],
                "priority": "required",
            },
            {
                "control_identifier": (f"statcan.{vintage}.private-age-gender.v1"),
                "entity_level": "person",
                "dimensions": [geography_level, "age_group_3", sex_field],
                "priority": "required",
            },
        ],
        "expected_geographies": {
            "policy": "explicit-bounded-selection",
            "identifiers": [],
            "exclusions": {},
        },
        "source_revisions": [_PROFILE_REVISIONS[vintage]],
        "recommended_calibration": {
            "max_iterations": 200,
            "tolerance": 1e-6,
            "integerization": "deterministic-systematic-midpoint-v1",
            "preserve_linkage": True,
            "planning_pool_size": 10_000,
        },
        "known_limitations": [
            "This definition does not include Census counts; a reviewed bounded "
            "extract must accompany every run.",
            "Age-by-sex/gender is eligible only where total population equals "
            "persons in private households; geographies with collective residents "
            "are excluded.",
            "CT coverage is limited to tracted metropolitan areas and agglomerations.",
            "Only household size, tenure, and broad age-by-sex/gender are locally "
            "controlled; other generated fields retain broad-model status.",
        ],
        "permitted_claims": [
            "The realized linked population was calibrated at whole-household level "
            "to the named, validated control cells for the emitted geographies.",
            "Local representativeness is limited to the controlled margins and does "
            "not extend to uncontrolled generated fields.",
        ],
        "review": _review(
            "Control definitions resolve through the 2026-08-10 registry revision.",
            "Bounded CSD, CT, ADA, and DA fixtures exercise identical semantics.",
        ),
    }
    payload["definition_sha256"] = _pack_definition_sha256(payload)
    return payload


def _builtin_packs() -> dict[str, ControlPackManifest]:
    packs = {}
    for vintage in _CENSUS_VINTAGES:
        for geography_level in _GEOGRAPHY_LEVELS:
            pack = ControlPackManifest.model_validate(
                _pack_payload(vintage, geography_level)
            )
            _validate_pack_against_registry(pack)
            packs[pack.identifier] = pack
    return packs


def _validate_pack_against_registry(pack: ControlPackManifest) -> None:
    registry = load_compatibility_registry()
    if pack.registry_schema_version != registry.schema_version:
        raise ValueError("control pack uses an unsupported registry schema version")
    if pack.registry_revision != registry.revision:
        raise ValueError(
            f"control pack requires registry revision {pack.registry_revision}, "
            f"but this installation provides {registry.revision}"
        )
    if pack.geography_column != pack.geography_level:
        raise ValueError("control pack geography_column must match geography_level")
    expected_namespace = f"statcan:census:{pack.census_vintage}:{pack.geography_level}"
    if pack.identifier_namespace != expected_namespace:
        raise ValueError(
            "control pack identifier_namespace does not match vintage and geography"
        )
    controls = {control.identifier: control for control in registry.controls}
    referenced: list[ControlDefinition] = []
    for margin in pack.margins:
        control = controls.get(margin.control_identifier)
        if control is None:
            raise ValueError(
                f"control pack references unknown control {margin.control_identifier!r}"
            )
        referenced.append(control)
        if control.census_vintage != pack.census_vintage:
            raise ValueError(
                f"control {control.identifier!r} has an incompatible census vintage"
            )
        if pack.geography_level not in control.geography_levels:
            raise ValueError(
                f"control {control.identifier!r} does not support "
                f"{pack.geography_level.upper()}"
            )
        if margin.entity_level != control.entity_level:
            raise ValueError(
                f"control {control.identifier!r} has an incompatible entity level"
            )
        expected_dimensions = [
            pack.geography_column,
            *(item.output_field for item in control.candidate_derivations),
        ]
        if margin.dimensions != expected_dimensions:
            raise ValueError(
                f"control {control.identifier!r} requires dimensions "
                f"{expected_dimensions!r}"
            )
    expected_entities = sorted({control.entity_level for control in referenced})
    if sorted(pack.required_entity_levels) != expected_entities:
        raise ValueError("control pack required_entity_levels contradict its margins")
    expected_household_fields = sorted(
        {
            field
            for control in referenced
            if control.entity_level == "household"
            for field in control.generated_fields
        }
    )
    expected_person_fields = sorted(
        {
            field
            for control in referenced
            if control.entity_level == "person"
            for field in control.generated_fields
        }
    )
    if sorted(pack.required_household_fields) != expected_household_fields:
        raise ValueError(
            "control pack required_household_fields contradict its margins"
        )
    if sorted(pack.required_person_fields) != expected_person_fields:
        raise ValueError("control pack required_person_fields contradict its margins")
    expected_revisions = sorted({control.source.revision for control in referenced})
    if sorted(pack.source_revisions) != expected_revisions:
        raise ValueError("control pack source_revisions contradict its controls")


def list_builtin_control_packs() -> tuple[dict[str, Any], ...]:
    """List inspectable metadata for the eight built-in bounded core packs."""

    return tuple(
        {
            "identifier": pack.identifier,
            "version": pack.version,
            "label": pack.label,
            "census_vintage": pack.census_vintage,
            "geography_level": pack.geography_level,
            "identifier_namespace": pack.identifier_namespace,
            "linked_schema_version": pack.linked_schema_version,
            "required_household_fields": list(pack.required_household_fields),
            "required_person_fields": list(pack.required_person_fields),
            "definition_sha256": pack.definition_sha256,
        }
        for pack in _builtin_packs().values()
    )


def read_control_pack(path: str | Path) -> ControlPackManifest:
    """Read a strict v1 control-pack manifest from JSON."""

    source = Path(path)
    try:
        raw = source.read_text()
    except OSError as exc:
        raise ValueError(f"could not read control pack {source}: {exc}") from exc
    try:
        manifest = ControlPackManifest.model_validate_json(raw)
        _validate_pack_against_registry(manifest)
        return manifest
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid control pack {source}: {exc}") from exc


def load_control_pack(
    identifier_or_path: str | Path | ControlPackManifest,
) -> ControlPackManifest:
    """Load a built-in pack by identifier or a user manifest by path."""

    if isinstance(identifier_or_path, ControlPackManifest):
        _validate_pack_against_registry(identifier_or_path)
        return identifier_or_path
    value = str(identifier_or_path)
    packs = _builtin_packs()
    if value in packs:
        return packs[value]
    path = Path(identifier_or_path)
    if path.exists():
        return read_control_pack(path)
    raise ValueError(
        f"unknown control pack {value!r}; available built-ins: "
        + ", ".join(sorted(packs))
    )


def write_control_pack(
    pack: str | Path | ControlPackManifest,
    path: str | Path,
) -> Path:
    """Write a normalized strict control-pack manifest for round-trip use."""

    manifest = load_control_pack(pack)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n"
    )
    return destination


def control_table_sha256(table: ControlTable) -> str:
    """Hash the complete normalized semantics of a control table."""

    payload = [
        {
            "name": margin.name,
            "dimensions": list(margin.dimensions),
            "cells": sorted(
                (
                    {
                        "categories": dict(sorted(cell.categories.items())),
                        "count": float(cell.count),
                    }
                    for cell in margin.cells
                ),
                key=lambda cell: json.dumps(cell, sort_keys=True),
            ),
        }
        for margin in sorted(
            table.margins,
            key=lambda item: (item.name, item.dimensions),
        )
    ]
    encoded = json.dumps(
        {"dimensions": list(table.dimensions), "margins": payload},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_control_pack_evidence(
    pack: str | Path | ControlPackManifest,
    household_controls: ControlTable,
    person_controls: ControlTable,
    *,
    geographies: Mapping[str, Mapping[str, object]],
    controls_source_revisions: Sequence[str],
    excluded_geographies: Mapping[str, str] | None = None,
) -> ControlPackEvidence:
    """Bind source, universe, and exact normalized tables to one pack."""

    manifest = load_control_pack(pack)
    if list(controls_source_revisions) != list(manifest.source_revisions):
        raise ValueError(
            "controls_source_revisions must exactly match the selected pack"
        )
    household_geographies = set(
        controls_by_geography(
            household_controls,
            geography_dimension=manifest.geography_column,
        )
    )
    person_geographies = set(
        controls_by_geography(
            person_controls,
            geography_dimension=manifest.geography_column,
        )
    )
    if household_geographies != person_geographies:
        raise ValueError(
            "household and person controls must cover identical geographies"
        )
    if set(geographies) != household_geographies:
        raise ValueError(
            "universe evidence must cover exactly the normalized control geographies"
        )
    payload = {
        "schema_version": CONTROL_PACK_EVIDENCE_SCHEMA_VERSION,
        "pack_identifier": manifest.identifier,
        "pack_definition_sha256": manifest.definition_sha256,
        "census_vintage": manifest.census_vintage,
        "geography_level": manifest.geography_level,
        "identifier_namespace": manifest.identifier_namespace,
        "controls_source_revisions": list(controls_source_revisions),
        "household_controls_sha256": control_table_sha256(household_controls),
        "person_controls_sha256": control_table_sha256(person_controls),
        "geographies": dict(geographies),
        "excluded_geographies": dict(excluded_geographies or {}),
    }
    return ControlPackEvidence.model_validate(payload)


def read_control_pack_evidence(path: str | Path) -> ControlPackEvidence:
    """Read and validate strict persisted v1 control-pack evidence from disk."""

    source = Path(path)
    try:
        raw = source.read_text()
    except OSError as exc:
        raise ValueError(
            f"could not read control-pack evidence {source}: {exc}"
        ) from exc
    try:
        return ControlPackEvidence.model_validate_json(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid control-pack evidence {source}: {exc}") from exc


def load_control_pack_evidence(
    evidence: str | Path | Mapping[str, object] | ControlPackEvidence,
) -> ControlPackEvidence:
    if isinstance(evidence, ControlPackEvidence):
        return evidence
    if isinstance(evidence, Mapping):
        return ControlPackEvidence.model_validate(evidence)
    return read_control_pack_evidence(evidence)


def write_control_pack_evidence(
    evidence: str | Path | Mapping[str, object] | ControlPackEvidence,
    path: str | Path,
) -> Path:
    """Write normalized control-pack evidence for consistent cross-surface reuse."""

    record = load_control_pack_evidence(evidence)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n"
    )
    return destination


def validate_control_pack_compatibility(
    pack: str | Path | ControlPackManifest,
    *,
    census_vintage: int,
    geography_level: str,
    linked_schema_version: str,
    household_fields: Collection[str],
    person_fields: Collection[str],
    model_profile: str | None = None,
) -> dict[str, Any]:
    """Validate pack/model compatibility without loading any control counts."""

    manifest = load_control_pack(pack)
    issues: list[dict[str, Any]] = []
    if census_vintage != manifest.census_vintage:
        issues.append(
            _issue(
                "incompatible_census_vintage",
                f"pack requires Census {manifest.census_vintage}, got {census_vintage}",
            )
        )
    if geography_level.lower() != manifest.geography_level:
        issues.append(
            _issue(
                "incompatible_geography_level",
                f"pack requires {manifest.geography_level.upper()}, got "
                f"{geography_level.upper()}",
            )
        )
    if linked_schema_version != manifest.linked_schema_version:
        issues.append(
            _issue(
                "incompatible_linked_schema",
                f"pack requires {manifest.linked_schema_version}, got "
                f"{linked_schema_version}",
            )
        )
    if (
        model_profile is not None
        and manifest.compatible_model_profiles
        and model_profile not in set(manifest.compatible_model_profiles)
    ):
        issues.append(
            _issue(
                "incompatible_model_profile",
                f"pack does not declare compatibility with model profile "
                f"{model_profile!r}",
            )
        )
    missing_household = sorted(
        set(manifest.required_household_fields) - set(household_fields)
    )
    if missing_household:
        issues.append(
            _issue(
                "missing_household_fields",
                "candidate households are missing required fields: "
                + ", ".join(missing_household),
                fields=missing_household,
            )
        )
    missing_person = sorted(set(manifest.required_person_fields) - set(person_fields))
    if missing_person:
        issues.append(
            _issue(
                "missing_person_fields",
                "candidate persons are missing required fields: "
                + ", ".join(missing_person),
                fields=missing_person,
            )
        )
    return {
        "schema_version": "synthpopcan-control-pack-compatibility-v1",
        "passed": not issues,
        "pack_identifier": manifest.identifier,
        "pack_definition_sha256": manifest.definition_sha256,
        "census_vintage": census_vintage,
        "geography_level": geography_level.lower(),
        "linked_schema_version": linked_schema_version,
        "model_profile": model_profile,
        "compatibility_basis": "required-fields-and-linked-schema",
        "issues": issues,
    }


def apply_control_pack_derivations(
    pack: str | Path | ControlPackManifest,
    households: Sequence[Mapping[str, str]],
    persons: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Copy candidates and add reviewed pack-specific helper dimensions.

    Linkage identifiers and rows are never changed or split.  A failed mapping
    names the entity, source field, and value rather than inventing a category.
    """

    manifest = load_control_pack(pack)
    registry = load_compatibility_registry()
    by_identifier = {control.identifier: control for control in registry.controls}
    derived_households = [dict(row) for row in households]
    derived_persons = [dict(row) for row in persons]
    for margin in manifest.margins:
        control = by_identifier[margin.control_identifier]
        rows = (
            derived_households
            if control.entity_level == "household"
            else derived_persons
        )
        for derivation in control.candidate_derivations:
            for index, row in enumerate(rows, start=2):
                value = row.get(derivation.source_field, "")
                try:
                    output = _derive_candidate_value(derivation, value)
                except ValueError as exc:
                    raise ValueError(
                        f"{control.entity_level} row {index} field "
                        f"{derivation.source_field!r}: {exc}"
                    ) from exc
                row[derivation.output_field] = output
    return derived_households, derived_persons


def _derive_candidate_value(derivation: CandidateDerivation, value: str) -> str:
    if not value:
        raise ValueError("value is missing")
    if derivation.method == "identity":
        return value
    if derivation.method == "category-crosswalk":
        try:
            return derivation.categories[value]
        except KeyError as exc:
            raise ValueError(f"unmapped category {value!r}") from exc
    assert derivation.cap is not None
    try:
        integer = int(value)
    except ValueError as exc:
        raise ValueError(f"expected an integer, got {value!r}") from exc
    if integer < 1:
        raise ValueError(f"expected a positive integer, got {value!r}")
    return str(min(integer, derivation.cap))


def plan_control_pack(
    pack: str | Path | ControlPackManifest,
    households: Sequence[Mapping[str, str]],
    persons: Sequence[Mapping[str, str]],
    household_controls: ControlTable,
    person_controls: ControlTable,
    *,
    linked_schema_version: str = LINKED_POPULATION_SCHEMA_VERSION,
    model_profile: str | None = None,
    evidence: str | Path | Mapping[str, object] | ControlPackEvidence | None = None,
) -> dict[str, Any]:
    """Return a deterministic feasibility plan for one bounded pack run.

    The planner validates the pack, model fields, exact margin structure,
    geography intersection, candidate categories, linkage, and positive-cell
    support before a fit.  It does not silently remove a margin or geography.
    """

    manifest = load_control_pack(pack)
    issues: list[dict[str, Any]] = []
    evidence_record: ControlPackEvidence | None = None
    if evidence is None:
        issues.append(
            _issue(
                "missing_control_pack_evidence",
                "a bound synthpopcan-control-pack-evidence-v1 record is required",
            )
        )
    else:
        try:
            evidence_record = load_control_pack_evidence(evidence)
        except ValueError as exc:
            issues.append(_issue("invalid_control_pack_evidence", str(exc)))
    if evidence_record is not None:
        issues.extend(
            _evidence_binding_issues(
                manifest,
                evidence_record,
                household_controls,
                person_controls,
            )
        )
    household_fields = set().union(*(row.keys() for row in households))
    person_fields = set().union(*(row.keys() for row in persons))
    compatibility = validate_control_pack_compatibility(
        manifest,
        census_vintage=(
            evidence_record.census_vintage if evidence_record is not None else 0
        ),
        geography_level=(
            evidence_record.geography_level
            if evidence_record is not None
            else "unknown"
        ),
        linked_schema_version=linked_schema_version,
        household_fields=household_fields,
        person_fields=person_fields,
        model_profile=model_profile,
    )
    issues.extend(compatibility["issues"])
    try:
        derived_households, derived_persons = apply_control_pack_derivations(
            manifest, households, persons
        )
    except ValueError as exc:
        issues.append(_issue("candidate_derivation_failed", str(exc)))
        derived_households = [dict(row) for row in households]
        derived_persons = [dict(row) for row in persons]

    structure_issues = _control_structure_issues(
        manifest, household_controls, person_controls
    )
    issues.extend(structure_issues)
    household_geographies = _safe_geographies(
        household_controls,
        manifest.geography_column,
        unit="household",
        issues=issues,
    )
    person_geographies = _safe_geographies(
        person_controls,
        manifest.geography_column,
        unit="person",
        issues=issues,
    )
    common_geographies = sorted(household_geographies & person_geographies)
    if household_geographies != person_geographies:
        issues.append(
            _issue(
                "incompatible_geography_intersection",
                "household and person margins must cover the same bounded "
                "geography identifiers",
                household_only=sorted(household_geographies - person_geographies),
                person_only=sorted(person_geographies - household_geographies),
            )
        )
    if not common_geographies:
        issues.append(
            _issue(
                "empty_geography_intersection",
                "the selected household and person margins share no geography",
            )
        )
    explicit = set(manifest.expected_geographies.identifiers)
    if explicit and set(common_geographies) != explicit:
        issues.append(
            _issue(
                "unexpected_geography_set",
                "controls do not match the manifest's explicit bounded geography set",
                expected=sorted(explicit),
                actual=common_geographies,
            )
        )

    universe_report, universe_issues = _validate_universe_evidence(
        manifest,
        person_controls,
        common_geographies,
        evidence_record,
    )
    issues.extend(universe_issues)
    reconciliation_report, reconciliation_issues = _margin_total_reconciliation(
        manifest,
        household_controls,
        person_controls,
    )
    issues.extend(reconciliation_issues)

    if not structure_issues:
        household_report = check_small_area_calibration_inputs(
            derived_households,
            household_controls,
            geography_dimension=manifest.geography_column,
        )
        person_report = check_linked_person_calibration_inputs(
            derived_households,
            derived_persons,
            person_controls,
            geography_dimension=manifest.geography_column,
        )
        issues.extend(household_report["issues"])
        issues.extend(person_report["issues"])
    else:
        household_report = {"passed": False, "issues": []}
        person_report = {"passed": False, "issues": []}

    constraints = sum(
        len(margin.cells)
        for table in (household_controls, person_controls)
        for margin in table.margins
    )
    contribution_cells = constraints * len(households)
    estimated_bytes = contribution_cells * 8
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") == "warning"]
    return {
        "schema_version": CONTROL_PACK_PLAN_SCHEMA_VERSION,
        "passed": not errors,
        "pack": {
            "identifier": manifest.identifier,
            "version": manifest.version,
            "definition_sha256": manifest.definition_sha256,
            "registry_schema_version": manifest.registry_schema_version,
            "registry_revision": manifest.registry_revision,
            "census_vintage": manifest.census_vintage,
            "geography_level": manifest.geography_level,
            "identifier_namespace": manifest.identifier_namespace,
            "linked_schema_version": manifest.linked_schema_version,
            "common_universe": manifest.common_universe,
        },
        "model_profile": model_profile,
        "geographies": {
            "policy": manifest.expected_geographies.policy,
            "identifiers": common_geographies,
            "count": len(common_geographies),
            "household_only": sorted(household_geographies - person_geographies),
            "person_only": sorted(person_geographies - household_geographies),
        },
        "candidate_population": {
            "households": len(households),
            "persons": len(persons),
            "whole_household_weight_count": len(households),
            "person_assignment": "inherited-via-household",
        },
        "field_status": _field_status(
            manifest,
            household_fields,
            person_fields,
        ),
        "universe_evidence": universe_report,
        "margin_total_reconciliation": reconciliation_report,
        "margins": [
            {
                "control_identifier": margin.control_identifier,
                "entity_level": margin.entity_level,
                "dimensions": list(margin.dimensions),
                "priority": margin.priority,
                "vector_tolerance": _margin_vector_tolerance(manifest, margin),
            }
            for margin in manifest.margins
        ],
        "estimates": {
            "constraints": constraints,
            "candidate_contribution_cells": contribution_cells,
            "dense_contribution_bytes": estimated_bytes,
            "fits_to_run": len(common_geographies),
            "planning_pool_size": manifest.recommended_calibration.planning_pool_size,
        },
        "compatibility": compatibility,
        "household_preflight": household_report,
        "person_preflight": person_report,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": _deduplicate_issues(issues),
    }


def _evidence_binding_issues(
    pack: ControlPackManifest,
    evidence: ControlPackEvidence,
    household_controls: ControlTable,
    person_controls: ControlTable,
) -> list[dict[str, Any]]:
    comparisons: tuple[tuple[str, object, object], ...] = (
        ("pack_identifier", pack.identifier, evidence.pack_identifier),
        (
            "pack_definition_sha256",
            pack.definition_sha256,
            evidence.pack_definition_sha256,
        ),
        ("census_vintage", pack.census_vintage, evidence.census_vintage),
        ("geography_level", pack.geography_level, evidence.geography_level),
        (
            "identifier_namespace",
            pack.identifier_namespace,
            evidence.identifier_namespace,
        ),
        (
            "controls_source_revisions",
            list(pack.source_revisions),
            list(evidence.controls_source_revisions),
        ),
        (
            "household_controls_sha256",
            control_table_sha256(household_controls),
            evidence.household_controls_sha256,
        ),
        (
            "person_controls_sha256",
            control_table_sha256(person_controls),
            evidence.person_controls_sha256,
        ),
    )
    return [
        _issue(
            "control_pack_evidence_mismatch",
            f"control-pack evidence {field!r} does not match the selected "
            "pack or normalized controls",
            field=field,
            expected=expected,
            actual=actual,
        )
        for field, expected, actual in comparisons
        if expected != actual
    ]


def _field_status(
    pack: ControlPackManifest,
    household_fields: Collection[str],
    person_fields: Collection[str],
) -> dict[str, Any]:
    registry = load_compatibility_registry()
    controls = {control.identifier: control for control in registry.controls}
    result: dict[str, Any] = {}
    for entity, fields in (
        ("household", household_fields),
        ("person", person_fields),
    ):
        derivations = [
            derivation
            for margin in pack.margins
            if margin.entity_level == entity
            for derivation in controls[margin.control_identifier].candidate_derivations
        ]
        source_to_derivations: dict[str, list[CandidateDerivation]] = {}
        output_to_source: dict[str, str] = {}
        for derivation in derivations:
            source_to_derivations.setdefault(derivation.source_field, []).append(
                derivation
            )
            if derivation.output_field != derivation.source_field:
                output_to_source[derivation.output_field] = derivation.source_field
        derived_fields = set(output_to_source)
        substantive = sorted(
            {
                field
                for field in (*fields, *derived_fields)
                if not _non_substantive_field(field, pack.geography_column)
            }
        )
        records: list[dict[str, Any]] = []
        for field in substantive:
            if field in output_to_source:
                records.append(
                    {
                        "field": field,
                        "status": "coarsened-derived",
                        "source_field": output_to_source[field],
                        "control_dimensions": [field],
                    }
                )
            elif field in source_to_derivations:
                field_derivations = source_to_derivations[field]
                is_identity = all(
                    derivation.method == "identity" and derivation.output_field == field
                    for derivation in field_derivations
                )
                records.append(
                    {
                        "field": field,
                        "status": (
                            "controlled" if is_identity else "coarsened-to-control"
                        ),
                        "derived_control_fields": sorted(
                            derivation.output_field for derivation in field_derivations
                        ),
                        "derivations": [
                            {
                                "output_field": derivation.output_field,
                                "method": derivation.method,
                                "categories": dict(derivation.categories),
                                "cap": derivation.cap,
                            }
                            for derivation in field_derivations
                        ],
                    }
                )
            else:
                records.append({"field": field, "status": "uncontrolled"})
        result[entity] = {
            "fields": records,
            "controlled_fields": [
                record["field"]
                for record in records
                if record["status"] == "controlled"
            ],
            "coarsened_derived_fields": [
                record["field"]
                for record in records
                if record["status"] == "coarsened-derived"
            ],
            "coarsened_source_fields": [
                record["field"]
                for record in records
                if record["status"] == "coarsened-to-control"
            ],
            "uncontrolled_fields": [
                record["field"]
                for record in records
                if record["status"] == "uncontrolled"
            ],
        }
    return result


def _non_substantive_field(field: str, geography_column: str) -> bool:
    upper = field.upper()
    return (
        field == geography_column
        or upper
        in {
            "PR",
            "CMA",
            "CD",
            "CSD",
            "CT",
            "ADA",
            "DA",
            "DGUID",
            "ALT_GEO_CODE",
            "WEIGHT",
            "STARTING_WEIGHT",
        }
        or field.lower().endswith("_id")
        or field.startswith("synthetic_")
    )


def _margin_vector_tolerance(
    pack: ControlPackManifest,
    margin: PackMargin,
) -> float:
    registry = load_compatibility_registry()
    control = next(
        control
        for control in registry.controls
        if control.identifier == margin.control_identifier
    )
    assert control.census_vintage == pack.census_vintage
    return control.suppression.vector_tolerance


def _margin_total_reconciliation(
    pack: ControlPackManifest,
    household_controls: ControlTable,
    person_controls: ControlTable,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    table_by_entity = {
        "household": household_controls,
        "person": person_controls,
    }
    for entity in ("household", "person"):
        pack_margins = [
            margin for margin in pack.margins if margin.entity_level == entity
        ]
        if len(pack_margins) < 2:
            continue
        table = table_by_entity[entity]
        margins_by_dimensions = {margin.dimensions: margin for margin in table.margins}
        geography_totals: dict[str, dict[str, float]] = {}
        tolerance = max(
            _margin_vector_tolerance(pack, margin) for margin in pack_margins
        )
        for pack_margin in pack_margins:
            actual = margins_by_dimensions.get(tuple(pack_margin.dimensions))
            if actual is None:
                continue
            for cell in actual.cells:
                geography = cell.categories.get(pack.geography_column, "")
                geography_totals.setdefault(geography, {}).setdefault(
                    pack_margin.control_identifier, 0.0
                )
                geography_totals[geography][pack_margin.control_identifier] += (
                    cell.count
                )
        for geography, totals in sorted(geography_totals.items()):
            residual = max(totals.values()) - min(totals.values())
            if residual == 0:
                status = "exact"
            elif residual <= tolerance:
                status = "within-source-tolerance-requires-reconciliation"
            else:
                status = "outside-source-tolerance"
            rows.append(
                {
                    "entity_level": entity,
                    "geography": geography,
                    "totals": totals,
                    "residual": residual,
                    "source_vector_tolerance": tolerance,
                    "status": status,
                }
            )
            if residual:
                issues.append(
                    _issue(
                        "unreconciled_control_totals",
                        f"{entity} margins for geography {geography!r} differ by "
                        f"{residual:g}; normalized controls must reconcile exactly "
                        "before calibration",
                        entity_level=entity,
                        geography=geography,
                        residual=residual,
                        source_vector_tolerance=tolerance,
                        within_source_tolerance=residual <= tolerance,
                    )
                )
    return {
        "required_normalized_residual": 0.0,
        "source_vector_tolerances_are_pre_normalization": True,
        "rows": rows,
    }, issues


def _control_structure_issues(
    pack: ControlPackManifest,
    household_controls: ControlTable,
    person_controls: ControlTable,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    geography_coverage: dict[str, set[str]] = {}
    registry = load_compatibility_registry()
    control_by_identifier = {
        control.identifier: control for control in registry.controls
    }
    for entity, table in (
        ("household", household_controls),
        ("person", person_controls),
    ):
        expected = Counter(
            tuple(margin.dimensions)
            for margin in pack.margins
            if margin.entity_level == entity
        )
        actual = Counter(tuple(margin.dimensions) for margin in table.margins)
        if actual != expected:
            issues.append(
                _issue(
                    "control_margin_structure_mismatch",
                    f"{entity} controls do not match the pack's required margins",
                    entity_level=entity,
                    expected=[list(value) for value in expected.elements()],
                    actual=[list(value) for value in actual.elements()],
                )
            )
            continue
        for pack_margin in (
            margin for margin in pack.margins if margin.entity_level == entity
        ):
            control = control_by_identifier[pack_margin.control_identifier]
            expected_cells = _expected_category_cells(control)
            matching = [
                margin
                for margin in table.margins
                if margin.dimensions == tuple(pack_margin.dimensions)
            ]
            assert len(matching) == 1
            actual_by_geography: dict[str, set[tuple[str, ...]]] = {}
            cell_keys: Counter[tuple[str, ...]] = Counter()
            non_geo_dimensions = tuple(pack_margin.dimensions[1:])
            for cell in matching[0].cells:
                geography = cell.categories.get(pack.geography_column, "")
                categories = tuple(
                    cell.categories.get(dimension, "")
                    for dimension in non_geo_dimensions
                )
                actual_by_geography.setdefault(geography, set()).add(categories)
                cell_keys[(geography, *categories)] += 1
            duplicate_keys = sorted(
                key for key, count in cell_keys.items() if count > 1
            )
            if duplicate_keys:
                issues.append(
                    _issue(
                        "duplicate_control_cells",
                        f"{entity} control {pack_margin.control_identifier!r} "
                        "contains duplicate geography/category cells",
                        entity_level=entity,
                        control_identifier=pack_margin.control_identifier,
                        cells=[list(key) for key in duplicate_keys],
                    )
                )
            geography_coverage[pack_margin.control_identifier] = set(
                actual_by_geography
            ) - {""}
            for geography, actual_cells in sorted(actual_by_geography.items()):
                if actual_cells != expected_cells:
                    issues.append(
                        _issue(
                            "control_category_vector_mismatch",
                            f"{entity} control {pack_margin.control_identifier!r} "
                            f"does not contain its complete reviewed category vector",
                            entity_level=entity,
                            geography=geography,
                            expected=[list(item) for item in sorted(expected_cells)],
                            actual=[list(item) for item in sorted(actual_cells)],
                        )
                    )
    all_geographies = set().union(*geography_coverage.values())
    for margin in pack.margins:
        actual_geographies = geography_coverage.get(margin.control_identifier, set())
        missing = sorted(all_geographies - actual_geographies)
        if missing:
            issues.append(
                _issue(
                    "missing_required_margin_geographies",
                    f"required control {margin.control_identifier!r} is missing "
                    "one or more geographies present in the pack inputs",
                    control_identifier=margin.control_identifier,
                    geographies=missing,
                )
            )
    return issues


def _expected_category_cells(
    control: ControlDefinition,
) -> set[tuple[str, ...]]:
    cells: set[tuple[str, ...]] = {()}
    for axis in control.source_axes:
        cells = {
            (*prefix, category.target_category)
            for prefix in cells
            for category in axis.categories
        }
    return cells


def _validate_universe_evidence(
    pack: ControlPackManifest,
    person_controls: ControlTable,
    geographies: Sequence[str],
    evidence: ControlPackEvidence | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Require explicit zero-collective evidence for the built-in person margin."""

    registry = load_compatibility_registry()
    controls = {control.identifier: control for control in registry.controls}
    requires_reconciliation = any(
        controls[margin.control_identifier].universe.reconciliation
        == "zero-collective-only"
        for margin in pack.margins
        if margin.entity_level == "person"
    )
    if not requires_reconciliation:
        return {"required": False, "geographies": {}}, []
    issues: list[dict[str, Any]] = []
    rows: dict[str, dict[str, float | bool]] = {}
    evidence_geographies = set(evidence.geographies) if evidence is not None else set()
    unexpected = sorted(evidence_geographies - set(geographies))
    if unexpected:
        issues.append(
            _issue(
                "unexpected_universe_evidence_geographies",
                "control-pack evidence contains eligible geographies absent from "
                "the complete control intersection",
                geographies=unexpected,
            )
        )
    person_totals = {
        geography: sum(
            cell.count
            for margin in controls_for_geography.margins
            for cell in margin.cells
        )
        for geography, controls_for_geography in controls_by_geography(
            person_controls,
            geography_dimension=pack.geography_column,
        ).items()
    }
    for geography in geographies:
        values = evidence.geographies.get(geography) if evidence is not None else None
        if values is None:
            issues.append(
                _issue(
                    "missing_private_household_universe_evidence",
                    f"geography {geography!r} requires total-population and "
                    "private-household-population companion counts",
                    geography=geography,
                )
            )
            continue
        total = _finite_evidence_number(values.total_population)
        private = _finite_evidence_number(values.persons_in_private_households)
        if total is None or private is None:
            issues.append(
                _issue(
                    "invalid_private_household_universe_evidence",
                    f"geography {geography!r} has missing or non-numeric "
                    "universe companion counts",
                    geography=geography,
                )
            )
            continue
        zero_collective = total == private
        matches_control = private == person_totals.get(geography)
        rows[geography] = {
            "total_population": total,
            "persons_in_private_households": private,
            "collective_population_difference": total - private,
            "person_control_total": person_totals.get(geography, 0.0),
            "zero_collective": zero_collective,
            "matches_person_control_total": matches_control,
        }
        if not zero_collective:
            issues.append(
                _issue(
                    "nonzero_collective_population",
                    f"geography {geography!r} cannot use the private-household "
                    "age control because total population differs from persons "
                    "in private households",
                    geography=geography,
                    difference=total - private,
                )
            )
        if not matches_control:
            issues.append(
                _issue(
                    "person_control_universe_total_mismatch",
                    f"geography {geography!r} person-control total does not match "
                    "the persons-in-private-households companion count",
                    geography=geography,
                    expected=private,
                    actual=person_totals.get(geography),
                )
            )
    return {
        "required": True,
        "policy": "zero-collective-only",
        "source_total_characteristic_id": "8",
        "companion_characteristic_id": "57" if pack.census_vintage == 2016 else "56",
        "excluded_geographies": (
            dict(evidence.excluded_geographies) if evidence is not None else {}
        ),
        "geographies": rows,
    }, issues


def _finite_evidence_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    result = float(value)
    return result if result >= 0 and math.isfinite(result) else None


def _safe_geographies(
    table: ControlTable,
    geography_column: str,
    *,
    unit: str,
    issues: list[dict[str, Any]],
) -> set[str]:
    try:
        return set(controls_by_geography(table, geography_dimension=geography_column))
    except ValueError as exc:
        issues.append(
            _issue(
                "invalid_control_geography",
                f"{unit} controls: {exc}",
                entity_level=unit,
            )
        )
        return set()


def _issue(kind: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "severity": "error",
        "kind": kind,
        "message": message,
        **details,
    }


def _deduplicate_issues(issues: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for issue in issues:
        key = json.dumps(issue, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def _margin_for_dimensions(
    table: ControlTable,
    dimensions: Sequence[str],
) -> ControlMargin | None:
    """Return the unique matching margin (reserved for interface adapters)."""

    matches = [
        margin for margin in table.margins if margin.dimensions == tuple(dimensions)
    ]
    return matches[0] if len(matches) == 1 else None
