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

FAMILY_CONCEPTS = {
    "marital_status": "person.marital-status",
    "education": "person.education",
    "labour_force_status": "person.labour-force",
    "work_activity": "person.work-activity",
}

# These digests are part of the published v1 definitions. A change to a
# crosswalk or source rule requires a new pack version, not a silent rewrite.
DEFINITION_DIGESTS = {
    "statcan-2016-marital-status-ct-v1": (
        "3dcae991649aadcea59c27e6506c588bfd8792f9af18b8a0326517e7805c29ab"
    ),
    "statcan-2016-education-ct-v1": (
        "d4249e864064e8e8313ee61f9948315089663ac1ca9446e14f3fa89842df9fbb"
    ),
    "statcan-2016-labour-force-status-ct-v1": (
        "e6af73cc5bd4d27a8430621de8a77a51b0835209d07c5482b1e76ab31be08f01"
    ),
    "statcan-2016-work-activity-ct-v1": (
        "ad3a446bbe42ce501d21f5fec5da09d1d52ba38f65fa4a423d53d351b1342423"
    ),
    "statcan-2021-marital-status-ct-v1": (
        "7488af4b2dea2c92ac35d6cf98fbcdf87566493e1c72aca29e71e98ca1fb7327"
    ),
    "statcan-2021-education-ct-v1": (
        "07edd25e04cdd14b51631843edbfb4acf8a2c5930b6516e637543b2d4568690a"
    ),
    "statcan-2021-labour-force-status-ct-v1": (
        "3173b0755336bae7f7c3caf9bac81796d96701b84e83941b7ff4ba5f8f69b5e2"
    ),
    "statcan-2021-work-activity-ct-v1": (
        "2869422bd35d8e70bc5fa7d255f89922f8f0ce9e6f627e7fc8348332f4d740af"
    ),
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
    digest = _catalogue_definition_sha256(definition)
    if digest != DEFINITION_DIGESTS.get(identifier):
        raise ValueError(f"conditional pack {identifier!r} definition digest mismatch")
    definition["definition_sha256"] = digest
    return definition


def _category_members(crosswalk, groups):
    return {
        category: list(members)
        for category, members in zip(
            dict.fromkeys(crosswalk.values()), groups, strict=True
        )
    }
