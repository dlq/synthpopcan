"""Adapt independently reconciled age-15+ targets to the linked fitter."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from synthpopcan._conditional_universe import ConditionalPersonUniverse
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.geography import GeographyIdentity, GeographyUniverse

UNDER_15 = "under_15_not_applicable"


@dataclass(frozen=True)
class ConditionalPersonTargets:
    """One family vector and its independent denominator evidence."""

    universe: ConditionalPersonUniverse
    eligible_counts: Mapping[str, float]
    under_15_count: float


def reconcile_conditional_person_margin(
    controls: ControlTable,
    *,
    geography: GeographyUniverse,
    geography_dimension: str,
    field: str,
    eligible_categories: frozenset[str],
    targets: Mapping[str, ConditionalPersonTargets],
) -> ControlTable:
    """Add the explicit child state after checking the eligible denominator."""
    if (
        not eligible_categories
        or "" in eligible_categories
        or UNDER_15 in eligible_categories
    ):
        raise ValueError("conditional controls require distinct eligible categories")
    if field in controls.dimensions or field == geography_dimension:
        raise ValueError(f"conditional field {field!r} is already controlled")
    _validate_existing_person_margins(controls, geography_dimension, targets)
    _validate_child_targets(controls, geography_dimension, targets, field)
    cells = []
    for identifier, target in sorted(targets.items()):
        if set(target.eligible_counts) != eligible_categories:
            raise ValueError(f"{identifier}: conditional categories must be exhaustive")
        target.universe.validate_targets(
            geography.identity(identifier),
            tuple(target.eligible_counts.values()),
            under_15_not_applicable=target.under_15_count,
        )
        counts = {**target.eligible_counts, UNDER_15: target.under_15_count}
        cells.extend(
            ControlCell({geography_dimension: identifier, field: category}, count)
            for category, count in sorted(counts.items())
        )
    margin = ControlMargin(field, (geography_dimension, field), tuple(cells))
    return ControlTable((*controls.margins, margin), (*controls.dimensions, field))


def _validate_existing_person_margins(
    controls: ControlTable,
    geography_dimension: str,
    targets: Mapping[str, ConditionalPersonTargets],
) -> None:
    if not targets:
        raise ValueError("conditional controls require geography evidence")
    for margin in controls.margins:
        if geography_dimension not in margin.dimensions:
            raise ValueError(f"{margin.name}: missing geography dimension")
        totals: dict[str, list[float]] = {}
        for cell in margin.cells:
            totals.setdefault(cell.categories[geography_dimension], []).append(
                cell.count
            )
        if totals.keys() != targets.keys():
            raise ValueError(
                f"{margin.name}: conditional and person geographies differ"
            )
        for identifier, counts in totals.items():
            expected = targets[identifier].universe.all_private_household_persons
            if not math.isclose(math.fsum(counts), expected, rel_tol=0, abs_tol=1e-9):
                raise ValueError(
                    f"{identifier}: {margin.name} does not match the evidenced "
                    "private-household person total"
                )


def _validate_child_targets(controls, dimension, targets, field_name):
    family = field_name.removesuffix("_15_plus").replace("_", "-")
    for margin in controls.margins:
        field = next(
            (
                name
                for name in margin.dimensions
                if name
                in {
                    "age_group_3",
                    "education_15_plus",
                    "marital_status_15_plus",
                    "labour_force_status_15_plus",
                    "work_activity_15_plus",
                }
            ),
            None,
        )
        if field is None:
            continue
        children: dict[str, float] = dict.fromkeys(targets, 0.0)
        for cell in margin.cells:
            if cell.categories[field] == (
                "0_14" if field == "age_group_3" else UNDER_15
            ):
                children[cell.categories[dimension]] += cell.count
        for identifier, count in children.items():
            if not math.isclose(
                count, targets[identifier].under_15_count, rel_tol=0, abs_tol=1e-9
            ):
                raise ValueError(
                    f"{identifier}: {margin.name} under-15 target {count:g} "
                    f"does not match the reconciled "
                    f"{family} under-15 target "
                    f"{targets[identifier].under_15_count:g}"
                )


def classify_conditional_person_field(
    persons: Sequence[Mapping[str, str]],
    *,
    age_field: str,
    age_eligibility: Mapping[str, bool],
    source_field: str,
    output_field: str,
    crosswalk: Mapping[str, str],
    eligible_categories: frozenset[str],
) -> list[dict[str, str]]:
    """Classify each candidate using explicit age and source-code crosswalks."""
    classified = []
    for index, person in enumerate(persons, start=1):
        eligible = age_eligibility.get(person.get(age_field, ""))
        if eligible is None:
            raise ValueError(
                f"person row {index}: unknown age eligibility in {age_field}"
            )
        category = UNDER_15
        if eligible:
            category = crosswalk.get(person.get(source_field, ""), "")
            if category not in eligible_categories:
                raise ValueError(
                    f"person row {index}: unsupported eligible {source_field}"
                )
        classified.append({**person, output_field: category})
    return classified


def load_marital_status_controls(
    path: Path,
    persons: Sequence[Mapping[str, str]],
    controls: ControlTable,
    geography: GeographyUniverse,
    geography_dimension: str,
) -> tuple[list[dict[str, str]], ControlTable, dict[str, object]]:
    """Read an explicit, project-reviewed marital-status control document."""
    data = path.read_bytes()
    payload = json.loads(data)
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "synthpopcan-marital-status-controls-v1"
    ):
        raise ValueError("expected a synthpopcan-marital-status-controls-v1 document")
    age_eligibility = _document_mapping(payload, "age_eligibility", bool)
    crosswalk = _document_mapping(payload, "crosswalk", str)
    categories = frozenset(crosswalk.values())
    if not all(category.strip() for category in categories):
        raise ValueError("marital-status crosswalk categories must be nonblank")
    rows = payload.get("targets")
    if not isinstance(rows, list) or not rows:
        raise ValueError("marital-status controls require per-geography targets")
    targets = {}
    for row in rows:
        target = _read_marital_target(row)
        identifier = target.universe.geography.identifier
        if identifier in targets:
            raise ValueError(f"duplicate marital-status geography {identifier!r}")
        targets[identifier] = target
    controls = reconcile_conditional_person_margin(
        controls,
        geography=geography,
        geography_dimension=geography_dimension,
        field="marital_status_15_plus",
        eligible_categories=categories,
        targets=targets,
    )
    persons = classify_conditional_person_field(
        persons,
        age_field="AGEGRP",
        age_eligibility=age_eligibility,
        source_field="MarStH" if geography.census_vintage == 2016 else "MARSTH",
        output_field="marital_status_15_plus",
        crosswalk=crosswalk,
        eligible_categories=categories,
    )
    return (
        persons,
        controls,
        {
            "marital_status_controls": {
                "path": str(path),
                "byte_size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        },
    )


def apply_builtin_marital_status_pack(
    path, persons, controls, geography, dimension, pack
):
    from synthpopcan._marital_status_packs import (
        AGE_ELIGIBILITY,
        CROSSWALK,
        PACKS,
        prepare_pack_targets,
    )
    from synthpopcan.small_area_synthesis import controls_by_geography

    identifiers = set(controls_by_geography(controls, geography_dimension=dimension))
    targets, evidence = prepare_pack_targets(pack, path, geography, identifiers)
    return _apply_builtin_person_targets(
        persons,
        controls,
        geography,
        dimension,
        targets,
        evidence,
        "marital_status",
        PACKS[pack][2],
        CROSSWALK,
        AGE_ELIGIBILITY,
    )


def apply_builtin_profile_pack(
    path, persons, controls, geography, dimension, pack, family
):
    from synthpopcan._conditional_pack_catalogue import PROFILE_FAMILIES
    from synthpopcan._marital_status_packs import AGE_ELIGIBILITY
    from synthpopcan.small_area_synthesis import controls_by_geography

    source = PROFILE_FAMILIES[family]
    if pack not in source.PACKS:
        raise ValueError(f"Unknown {family.replace('_', '-')} pack {pack!r}")
    identifiers = set(controls_by_geography(controls, geography_dimension=dimension))
    targets, evidence = source.prepare_pack_targets(pack, path, geography, identifiers)
    source_field = source.SOURCE_FIELDS[source.PACKS[pack]]
    return _apply_builtin_person_targets(
        persons,
        controls,
        geography,
        dimension,
        targets,
        evidence,
        family,
        source_field,
        source.CROSSWALK,
        AGE_ELIGIBILITY,
    )


def _apply_builtin_person_targets(
    persons,
    controls,
    geography,
    dimension,
    targets,
    evidence,
    family,
    source_field,
    crosswalk,
    age_eligibility,
):
    field = f"{family}_15_plus"
    categories = frozenset(crosswalk.values())
    controls = reconcile_conditional_person_margin(
        controls,
        geography=geography,
        geography_dimension=dimension,
        field=field,
        eligible_categories=categories,
        targets=targets,
    )
    persons = classify_conditional_person_field(
        persons,
        age_field="AGEGRP",
        age_eligibility=age_eligibility,
        source_field=source_field,
        output_field=field,
        crosswalk=crosswalk,
        eligible_categories=categories,
    )
    from synthpopcan._conditional_pack_catalogue import describe_conditional_pack

    definition = describe_conditional_pack(evidence["pack"])
    return (
        persons,
        controls,
        {f"{family}_controls": {**evidence, "pack_definition": definition}},
    )


def _document_mapping(payload, name, value_type):
    values = payload.get(name)
    if (
        not isinstance(values, dict)
        or not values
        or any(
            not key.strip() or type(value) is not value_type
            for key, value in values.items()
        )
    ):
        raise ValueError(f"marital-status controls require a valid {name} mapping")
    return values


def _read_marital_target(row) -> ConditionalPersonTargets:
    if not isinstance(row, dict) or not isinstance(row.get("geography"), dict):
        raise ValueError(
            "marital-status targets require an explicit geography identity"
        )
    evidence = row.get("source_evidence")
    if not isinstance(evidence, str):
        raise ValueError("marital-status targets require source evidence")
    universe = ConditionalPersonUniverse(
        geography=GeographyIdentity.from_dict(row["geography"]),
        all_private_household_persons=_target_count(
            row, "all_private_household_persons"
        ),
        age_15_plus_persons=_target_count(row, "age_15_plus_persons"),
        under_15_persons=_target_count(row, "under_15_persons"),
        source_evidence=evidence,
    )
    counts = row.get("eligible_counts")
    if not isinstance(counts, dict):
        raise ValueError("marital-status targets require eligible_counts")
    return ConditionalPersonTargets(
        universe, counts, _target_count(row, "under_15_not_applicable")
    )


def _target_count(row: Mapping[str, object], name: str) -> float:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"marital-status target {name} requires an observed count")
    return value
