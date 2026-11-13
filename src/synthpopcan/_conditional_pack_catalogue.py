"""Inspectable definitions of the separately versioned conditional tract packs."""

import synthpopcan._education_packs as _education_packs
import synthpopcan._labour_force_packs as _labour_force_packs
import synthpopcan._marital_status_packs as _marital_status_packs
import synthpopcan._work_activity_packs as _work_activity_packs
from synthpopcan._conditional_controls import UNDER_15
from synthpopcan._control_pack_catalogue import (
    _broad_pack_payload,
    _catalogue_definition_sha256,
)
from synthpopcan.linked_schema import LINKED_POPULATION_SCHEMA_VERSION

PROFILE_FAMILIES = {
    "education": _education_packs,
    "labour_force_status": _labour_force_packs,
    "work_activity": _work_activity_packs,
}


def describe_conditional_pack(identifier: str) -> dict[str, object] | None:
    """Return a fresh, checksummed definition for a built-in conditional pack."""
    if identifier in _marital_status_packs.PACKS:
        family = "marital_status"
        source = _marital_status_packs
        year, doi, field = source.PACKS[identifier]
        target_source = {
            "format": "marital-status-tract-csv",
            "doi": doi,
            "age_members": list(source.ADULT_AGES),
            "all_ages_member": 1,
            "under_15_member": 2,
            "total_marital_status_member": 1,
            "category_members": _category_members(
                source.CROSSWALK, source.MARITAL_MEMBERS
            ),
        }
    else:
        matches = (
            (name, module)
            for name, module in PROFILE_FAMILIES.items()
            if identifier in module.PACKS
        )
        match = next(matches, None)
        if match is None:
            return None
        family, source = match
        year = source.PACKS[identifier]
        field = source.SOURCE_FIELDS[year]
        all_ages, adults, companions, groups = source.PROFILE_ROWS[year]
        target_source = {
            "format": "statcan-census-profile-tract-zip-or-csv",
            "all_ages_row": all_ages,
            "age_15_plus_row": adults,
            "companion_rows": list(companions),
            "companion_tolerance": 5,
            "category_rows": _category_members(source.CROSSWALK, groups),
            "rounding_limit": source.ROUNDING_LIMIT,
        }
    crosswalk = dict(source.CROSSWALK)
    broad = _broad_pack_payload(year, "ct")
    definition: dict[str, object] = {
        "schema_version": "synthpopcan-conditional-control-pack-v1",
        "identifier": identifier,
        "version": 1,
        "family": family,
        "census_vintage": year,
        "geography_level": "ct",
        "identifier_namespace": f"statcan:census:{year}:ct",
        "linked_schema_version": LINKED_POPULATION_SCHEMA_VERSION,
        "compatible_broad_pack": broad["identifier"],
        "compatible_broad_definition_sha256": broad["definition_sha256"],
        "population": "private-household-persons",
        "minimum_age": 15,
        "age_field": "AGEGRP",
        "age_eligibility": dict(_marital_status_packs.AGE_ELIGIBILITY),
        "under_15_category": UNDER_15,
        "source_field": field,
        "output_field": f"{family}_15_plus",
        "category_order": list(dict.fromkeys(crosswalk.values())),
        "crosswalk": crosswalk,
        "target_source": target_source,
        "reconciliation": "base-five-proportional-largest-remainder",
        "unavailable_count_policy": "reject-selected-tract",
    }
    definition["definition_sha256"] = _catalogue_definition_sha256(definition)
    return definition


def _category_members(crosswalk, groups):
    return {
        category: list(members)
        for category, members in zip(
            dict.fromkeys(crosswalk.values()), groups, strict=True
        )
    }
