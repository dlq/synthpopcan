"""Reviewed Census catalogue data and deterministic built-in pack payloads."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from synthpopcan.linked_schema import LINKED_POPULATION_SCHEMA_VERSION

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
_CURRENT_REGISTRY_REVISION = "2026-08-19"
_SUPPORTED_REGISTRY_REVISIONS = {"2026-08-10", _CURRENT_REGISTRY_REVISION}


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
        controls.extend(_housing_control_definitions(vintage))
        controls.extend(_demographic_control_definitions(vintage))
    return controls


def _housing_control_definitions(vintage: int) -> list[dict[str, Any]]:
    """Return reviewed occupied-dwelling/private-household control families."""

    if vintage == 2016:
        specifications = [
            (
                "dwelling-type",
                "household.dwelling-type",
                "DTYPE",
                "structural_dwelling_type",
                "41",
                "Total - Occupied private dwellings by structural type of dwelling",
                {
                    "1": "single_detached",
                    "2": "apartment",
                    "3": "other",
                    "8": "__missing__",
                },
                [
                    ("single_detached", ["42"], ["Single-detached house"]),
                    (
                        "apartment",
                        ["43", "47", "48"],
                        [
                            "Apartment in a building that has five or more storeys",
                            "Apartment or flat in a duplex",
                            "Apartment in a building that has fewer than five storeys",
                        ],
                    ),
                    (
                        "other",
                        ["45", "46", "49", "50"],
                        [
                            "Semi-detached house",
                            "Row house",
                            "Other single-attached house",
                            "Movable dwelling",
                        ],
                    ),
                ],
            ),
            (
                "condominium",
                "household.condominium",
                "CONDO",
                "CONDO",
                "1621",
                "Total - Occupied private dwellings by condominium status",
                {"0": "0", "1": "1", "8": "__missing__"},
                [
                    ("1", ["1622"], ["Condominium"]),
                    ("0", ["1623"], ["Not condominium"]),
                ],
            ),
            (
                "bedrooms",
                "household.bedrooms",
                "BEDRM",
                "bedrooms_group",
                "1624",
                "Total - Occupied private dwellings by number of bedrooms",
                {
                    "0": "0",
                    "1": "1",
                    "2": "2",
                    "3": "3",
                    "4": "4_plus",
                    "5": "4_plus",
                    "8": "__missing__",
                },
                [
                    ("0", ["1625"], ["No bedrooms"]),
                    ("1", ["1626"], ["1 bedroom"]),
                    ("2", ["1627"], ["2 bedrooms"]),
                    ("3", ["1628"], ["3 bedrooms"]),
                    ("4_plus", ["1629"], ["4 or more bedrooms"]),
                ],
            ),
            (
                "rooms",
                "household.rooms",
                "ROOM",
                "rooms_group",
                "1630",
                "Total - Occupied private dwellings by number of rooms",
                {
                    **{str(value): "1_4" for value in range(1, 5)},
                    **{str(value): str(value) for value in range(5, 8)},
                    **{str(value): "8_plus" for value in range(8, 12)},
                    "88": "__missing__",
                },
                [
                    ("1_4", ["1631"], ["1 to 4 rooms"]),
                    ("5", ["1632"], ["5 rooms"]),
                    ("6", ["1633"], ["6 rooms"]),
                    ("7", ["1634"], ["7 rooms"]),
                    ("8_plus", ["1635"], ["8 or more rooms"]),
                ],
            ),
            (
                "housing-suitability",
                "household.housing-suitability",
                "NOS",
                "NOS",
                "1640",
                "Total - Private households by housing suitability",
                {"1": "1", "2": "2", "8": "__missing__"},
                [("1", ["1641"], ["Suitable"]), ("2", ["1642"], ["Not suitable"])],
            ),
            (
                "construction-period",
                "household.construction-period",
                "BUILT",
                "construction_period_group",
                "1643",
                "Total - Occupied private dwellings by period of construction",
                {
                    "1": "1960_or_before",
                    "2": "1960_or_before",
                    "3": "1960_or_before",
                    "4": "1961_1980",
                    "5": "1961_1980",
                    "6": "1981_1990",
                    "7": "1991_2000",
                    "8": "1991_2000",
                    "9": "2001_2005",
                    "10": "2006_2010",
                    "11": "2011_2016",
                    "88": "__missing__",
                },
                [
                    ("1960_or_before", ["1644"], ["1960 or before"]),
                    ("1961_1980", ["1645"], ["1961 to 1980"]),
                    ("1981_1990", ["1646"], ["1981 to 1990"]),
                    ("1991_2000", ["1647"], ["1991 to 2000"]),
                    ("2001_2005", ["1648"], ["2001 to 2005"]),
                    ("2006_2010", ["1649"], ["2006 to 2010"]),
                    ("2011_2016", ["1650"], ["2011 to 2016"]),
                ],
            ),
            (
                "repair-condition",
                "household.repair",
                "REPAIR",
                "repair_group",
                "1651",
                "Total - Occupied private dwellings by dwelling condition",
                {"1": "regular_minor", "2": "regular_minor", "3": "major"},
                [
                    (
                        "regular_minor",
                        ["1652"],
                        ["Only regular maintenance or minor repairs needed"],
                    ),
                    ("major", ["1653"], ["Major repairs needed"]),
                ],
            ),
        ]
    else:
        specifications = [
            (
                "dwelling-type",
                "household.dwelling-type",
                "DTYPE",
                "structural_dwelling_type",
                "41",
                "Total - Occupied private dwellings by structural type of dwelling",
                {
                    "1": "single_detached",
                    "2": "apartment",
                    "3": "other",
                    "8": "__missing__",
                },
                [
                    ("single_detached", ["42"], ["Single-detached house"]),
                    (
                        "apartment",
                        ["45", "46", "47"],
                        [
                            "Apartment or flat in a duplex",
                            "Apartment in a building that has fewer than five storeys",
                            "Apartment in a building that has five or more storeys",
                        ],
                    ),
                    (
                        "other",
                        ["43", "44", "48", "49"],
                        [
                            "Semi-detached house",
                            "Row house",
                            "Other single-attached house",
                            "Movable dwelling",
                        ],
                    ),
                ],
            ),
            (
                "condominium",
                "household.condominium",
                "CONDO",
                "CONDO",
                "1418",
                "Total - Occupied private dwellings by condominium status",
                {"0": "0", "1": "1", "8": "__missing__"},
                [
                    ("1", ["1419"], ["Condominium"]),
                    ("0", ["1420"], ["Not condominium"]),
                ],
            ),
            (
                "bedrooms",
                "household.bedrooms",
                "BEDRM",
                "bedrooms_group",
                "1421",
                "Total - Occupied private dwellings by number of bedrooms",
                {
                    "0": "0",
                    "1": "1",
                    "2": "2",
                    "3": "3",
                    "4": "4_plus",
                    "5": "4_plus",
                    "8": "__missing__",
                },
                [
                    ("0", ["1422"], ["No bedrooms"]),
                    ("1", ["1423"], ["1 bedroom"]),
                    ("2", ["1424"], ["2 bedrooms"]),
                    ("3", ["1425"], ["3 bedrooms"]),
                    ("4_plus", ["1426"], ["4 or more bedrooms"]),
                ],
            ),
            (
                "rooms",
                "household.rooms",
                "ROOM",
                "rooms_group",
                "1427",
                "Total - Occupied private dwellings by number of rooms",
                {
                    **{str(value): "1_4" for value in range(1, 5)},
                    **{str(value): str(value) for value in range(5, 8)},
                    **{str(value): "8_plus" for value in range(8, 12)},
                },
                [
                    ("1_4", ["1428"], ["1 to 4 rooms"]),
                    ("5", ["1429"], ["5 rooms"]),
                    ("6", ["1430"], ["6 rooms"]),
                    ("7", ["1431"], ["7 rooms"]),
                    ("8_plus", ["1432"], ["8 or more rooms"]),
                ],
            ),
            (
                "housing-suitability",
                "household.housing-suitability",
                "NOS",
                "NOS",
                "1437",
                "Total - Private households by housing suitability",
                {"0": "0", "1": "1"},
                [("1", ["1438"], ["Suitable"]), ("0", ["1439"], ["Not suitable"])],
            ),
            (
                "construction-period",
                "household.construction-period",
                "BUILT",
                "construction_period_group",
                "1440",
                "Total - Occupied private dwellings by period of construction",
                {
                    "1": "1960_or_before",
                    "2": "1960_or_before",
                    "3": "1961_1980",
                    "4": "1961_1980",
                    "5": "1981_1990",
                    "6": "1991_2000",
                    "7": "1991_2000",
                    "8": "2001_2005",
                    "9": "2006_2010",
                    "10": "2011_2015",
                    "11": "2016_2021",
                    "88": "__missing__",
                },
                [
                    ("1960_or_before", ["1441"], ["1960 or before"]),
                    ("1961_1980", ["1442"], ["1961 to 1980"]),
                    ("1981_1990", ["1443"], ["1981 to 1990"]),
                    ("1991_2000", ["1444"], ["1991 to 2000"]),
                    ("2001_2005", ["1445"], ["2001 to 2005"]),
                    ("2006_2010", ["1446"], ["2006 to 2010"]),
                    ("2011_2015", ["1447"], ["2011 to 2015"]),
                    ("2016_2021", ["1448"], ["2016 to 2021"]),
                ],
            ),
            (
                "repair-condition",
                "household.repair",
                "REPAIR",
                "repair_group",
                "1449",
                "Total - Occupied private dwellings by dwelling condition",
                {"1": "regular_minor", "2": "regular_minor", "3": "major"},
                [
                    (
                        "regular_minor",
                        ["1450"],
                        ["Only regular maintenance and minor repairs needed"],
                    ),
                    ("major", ["1451"], ["Major repairs needed"]),
                ],
            ),
        ]

    controls: list[dict[str, Any]] = []
    for (
        slug,
        concept,
        source_field,
        output_field,
        root_id,
        root_label,
        derivation,
        categories,
    ) in specifications:
        controls.append(
            {
                "identifier": f"statcan.{vintage}.{slug}.v1",
                "concept_identifier": concept,
                "census_vintage": vintage,
                "entity_level": "household",
                "generated_fields": [source_field],
                "candidate_derivations": [
                    {
                        "output_field": output_field,
                        "source_field": source_field,
                        "method": "category-crosswalk",
                        "categories": derivation,
                        "cap": None,
                        "unmapped": "reject",
                    }
                ],
                "source": {
                    "product": "Statistics Canada Census Profile",
                    "revision": _PROFILE_REVISIONS[vintage],
                    "url": _PROFILE_URLS[vintage],
                    "licence_url": _STATCAN_OPEN_LICENCE,
                    "root_characteristic_id": root_id,
                    "root_label": root_label,
                    "estimate_type": "100%-count"
                    if slug == "dwelling-type"
                    else "25%-sample-count",
                    "unit": "private-households",
                },
                "universe": {
                    "identifier": "private-households",
                    "source_label": "Occupied private dwellings/private households",
                    "calibration_label": "Linked private households",
                    "reference_period": f"{vintage} Census reference date",
                    "reconciliation": "identity",
                },
                "geography_levels": list(_GEOGRAPHY_LEVELS),
                "classification": "coarsened",
                "source_axes": [
                    {
                        "candidate_field": output_field,
                        "categories": [
                            _source_category(
                                target,
                                labels,
                                characteristic_ids=ids,
                                mapping="coarsened",
                            )
                            for target, ids, labels in categories
                        ],
                    }
                ],
                "suppression": _suppression(tolerance=5.0),
                "complete_mutually_exclusive_vector": True,
                "compatible_companion_fields": ["household_size"],
                "privacy_notes": [
                    "Suppressed or incomplete vectors exclude the geography; "
                    "no hidden cells are inferred."
                ],
                "interpretation_notes": [
                    "One occupied private dwelling is treated as the dwelling of "
                    "one linked private household.",
                    "PUMF missing codes remain outside the published vector and "
                    "receive zero fitted support when complete household margins "
                    "reconcile.",
                ],
                "status": "implemented",
                "review": {
                    "reviewer": "SynthPopCan maintainers",
                    "reviewed_on": "2026-08-19",
                    "evidence": [
                        "Vintage-specific Profile roots and child IDs were checked "
                        "against the local official bulk products.",
                        "PUMF categories were checked against the packaged "
                        "field-eligibility inventory.",
                    ],
                },
            }
        )
    return controls


def _demographic_control_definitions(vintage: int) -> list[dict[str, Any]]:
    """Return reviewed person controls with a private-household universe."""

    if vintage == 2016:
        specifications = [
            (
                "citizenship",
                "person.citizenship",
                "CITIZEN",
                "citizenship_group",
                "1135",
                "Total - Citizenship for the population in private households",
                {
                    "1": "canadian",
                    "2": "canadian",
                    "3": "not_canadian",
                    "8": "__missing__",
                },
                [
                    ("canadian", ["1136"], ["Canadian citizens"]),
                    ("not_canadian", ["1139"], ["Not Canadian citizens"]),
                ],
            ),
            (
                "immigration-status",
                "person.immigration-status",
                "IMMSTAT",
                "immigration_status_group",
                "1140",
                "Total - Immigrant status and period of immigration for the "
                "population in private households",
                {
                    "1": "non_immigrant",
                    "2": "immigrant",
                    "3": "non_permanent_resident",
                    "8": "__missing__",
                },
                [
                    ("non_immigrant", ["1141"], ["Non-immigrants"]),
                    ("immigrant", ["1142"], ["Immigrants"]),
                    ("non_permanent_resident", ["1150"], ["Non-permanent residents"]),
                ],
            ),
            (
                "generation-status",
                "person.generation-status",
                "GENSTAT",
                "generation_status_group",
                "1278",
                "Total - Generation status for the population in private households",
                {
                    "1": "first",
                    "2": "second",
                    "3": "second",
                    "4": "third_or_later",
                    "8": "__missing__",
                },
                [
                    ("first", ["1279"], ["First generation"]),
                    ("second", ["1280"], ["Second generation"]),
                    ("third_or_later", ["1281"], ["Third generation or more"]),
                ],
            ),
            (
                "visible-minority",
                "person.visible-minority",
                "VISMIN",
                "visible_minority_group",
                "1323",
                "Total - Visible minority for the population in private households",
                {
                    "1": "visible_minority",
                    "2": "not_visible_minority",
                    "8": "__missing__",
                },
                [
                    (
                        "visible_minority",
                        ["1324"],
                        ["Total visible minority population"],
                    ),
                    ("not_visible_minority", ["1337"], ["Not a visible minority"]),
                ],
            ),
        ]
    else:
        specifications = [
            (
                "citizenship",
                "person.citizenship",
                "CITIZEN",
                "citizenship_group",
                "1522",
                "Total - Citizenship for the population in private households",
                {
                    "1": "canadian",
                    "2": "canadian",
                    "3": "not_canadian",
                    "8": "__missing__",
                },
                [
                    ("canadian", ["1523"], ["Canadian citizens"]),
                    ("not_canadian", ["1526"], ["Not Canadian citizens"]),
                ],
            ),
            (
                "immigration-status",
                "person.immigration-status",
                "IMMSTAT",
                "immigration_status_group",
                "1527",
                "Total - Immigrant status and period of immigration for the "
                "population in private households",
                {
                    "1": "non_immigrant",
                    "2": "immigrant",
                    "3": "non_permanent_resident",
                    "8": "__missing__",
                },
                [
                    ("non_immigrant", ["1528"], ["Non-immigrants"]),
                    ("immigrant", ["1529"], ["Immigrants"]),
                    ("non_permanent_resident", ["1537"], ["Non-permanent residents"]),
                ],
            ),
            (
                "generation-status",
                "person.generation-status",
                "GENSTAT",
                "generation_status_group",
                "1665",
                "Total - Generation status for the population in private households",
                {
                    "1": "first",
                    "2": "second",
                    "3": "second",
                    "4": "third_or_later",
                    "8": "__missing__",
                },
                [
                    ("first", ["1666"], ["First generation"]),
                    ("second", ["1667"], ["Second generation"]),
                    ("third_or_later", ["1668"], ["Third generation or more"]),
                ],
            ),
            (
                "visible-minority",
                "person.visible-minority",
                "VISMIN",
                "visible_minority_group",
                "1683",
                "Total - Visible minority for the population in private households",
                {
                    "0": "not_visible_minority",
                    "1": "visible_minority",
                    "8": "__missing__",
                },
                [
                    (
                        "visible_minority",
                        ["1684"],
                        ["Total visible minority population"],
                    ),
                    ("not_visible_minority", ["1697"], ["Not a visible minority"]),
                ],
            ),
        ]

    controls: list[dict[str, Any]] = []
    for (
        slug,
        concept,
        source_field,
        output_field,
        root_id,
        root_label,
        mapping,
        categories,
    ) in specifications:
        controls.append(
            {
                "identifier": f"statcan.{vintage}.{slug}.v1",
                "concept_identifier": concept,
                "census_vintage": vintage,
                "entity_level": "person",
                "generated_fields": [source_field],
                "candidate_derivations": [
                    {
                        "output_field": output_field,
                        "source_field": source_field,
                        "method": "category-crosswalk",
                        "categories": mapping,
                        "cap": None,
                        "unmapped": "reject",
                    }
                ],
                "source": {
                    "product": "Statistics Canada Census Profile",
                    "revision": _PROFILE_REVISIONS[vintage],
                    "url": _PROFILE_URLS[vintage],
                    "licence_url": _STATCAN_OPEN_LICENCE,
                    "root_characteristic_id": root_id,
                    "root_label": root_label,
                    "estimate_type": "25%-sample-count",
                    "unit": "persons",
                },
                "universe": {
                    "identifier": "private-household-persons",
                    "source_label": "Population in private households",
                    "calibration_label": "People in linked private households",
                    "reference_period": f"{vintage} Census reference date",
                    "reconciliation": "identity",
                },
                "geography_levels": list(_GEOGRAPHY_LEVELS),
                "classification": "coarsened",
                "source_axes": [
                    {
                        "candidate_field": output_field,
                        "categories": [
                            _source_category(
                                target,
                                labels,
                                characteristic_ids=characteristic_ids,
                                mapping="coarsened",
                            )
                            for target, characteristic_ids, labels in categories
                        ],
                    }
                ],
                "suppression": _suppression(tolerance=5.0),
                "complete_mutually_exclusive_vector": True,
                "compatible_companion_fields": ["household_size"],
                "privacy_notes": [
                    "Use published aggregate counts only; suppressed or missing "
                    "cells exclude the geography."
                ],
                "interpretation_notes": [
                    "This family is limited to the published population in "
                    "private households and changes whole-household weights.",
                    "Independently rounded category counts must be reconciled "
                    "to the common published private-household-person total "
                    "before pack evidence is built.",
                    *(
                        [
                            "The visible-minority terminology is retained from "
                            "the Census source and must be interpreted in its "
                            "vintage-specific statistical context."
                        ]
                        if slug == "visible-minority"
                        else []
                    ),
                ],
                "status": "implemented",
                "review": _review(
                    "Profile root and child IDs cross-checked against both "
                    "bulk schemas.",
                    "PUMF categories are coarsened only where the Profile "
                    "publishes an aggregate.",
                ),
            }
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
    controls_by_concept: dict[str, list[str]] = {}
    for control in controls:
        controls_by_concept.setdefault(control["concept_identifier"], []).append(
            control["identifier"]
        )
    for concept, (entity, fields_2016, fields_2021) in planned_fields.items():
        implemented_controls = sorted(controls_by_concept.get(concept, []))
        result.append(
            {
                "concept_identifier": concept,
                "entity_level": entity,
                "fields_2016": fields_2016,
                "fields_2021": fields_2021,
                "control_identifiers": implemented_controls,
                "status": "implemented" if implemented_controls else "planned",
                "notes": (
                    [
                        "Reviewed vintage-specific crosswalks are available in "
                        "the expanded housing packs."
                    ]
                    if implemented_controls
                    else [
                        "Candidate source family exists, but its crosswalk and "
                        "universe are not yet implemented."
                    ]
                ),
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
    payload["definition_sha256"] = _catalogue_definition_sha256(payload)
    return payload


def _expanded_housing_pack_payload(
    vintage: int, geography_level: str
) -> dict[str, Any]:
    """Build an additive pack with all reviewed housing control families."""

    sex_field = "SEX" if vintage == 2016 else "GENDER"
    identifier = (
        f"statcan-{vintage}-expanded-private-household-housing-{geography_level}-v1"
    )
    housing_margins = [
        ("dwelling-type", "structural_dwelling_type"),
        ("condominium", "CONDO"),
        ("bedrooms", "bedrooms_group"),
        ("rooms", "rooms_group"),
        ("housing-suitability", "NOS"),
        ("construction-period", "construction_period_group"),
        ("repair-condition", "repair_group"),
    ]
    payload = _pack_payload(vintage, geography_level)
    payload.update(
        {
            "identifier": identifier,
            "version": "1.1.0",
            "label": (
                f"Statistics Canada {vintage} expanded private-household housing "
                f"{geography_level.upper()} controls"
            ),
            "registry_revision": _CURRENT_REGISTRY_REVISION,
            "required_household_fields": [
                "household_size",
                "TENUR",
                "DTYPE",
                "CONDO",
                "BEDRM",
                "ROOM",
                "NOS",
                "BUILT",
                "REPAIR",
            ],
            "required_person_fields": ["AGEGRP", sex_field],
            "margins": [
                *payload["margins"][:2],
                *[
                    {
                        "control_identifier": f"statcan.{vintage}.{slug}.v1",
                        "entity_level": "household",
                        "dimensions": [geography_level, dimension],
                        "priority": "required",
                    }
                    for slug, dimension in housing_margins
                ],
                payload["margins"][2],
            ],
            "known_limitations": [
                "This definition does not include Census counts; a reviewed "
                "bounded extract must accompany every run.",
                "All nine household vectors must describe the same linked "
                "private-household universe and reconcile after suppression "
                "handling.",
                "Age-by-sex/gender is eligible only where total population equals "
                "persons in private households.",
                "Missing Profile cells are not imputed, and a positive control "
                "category without candidate support fails planning.",
                "CT coverage is limited to tracted metropolitan areas and "
                "agglomerations.",
                "Person characteristics beyond broad age-by-sex/gender remain "
                "uncontrolled in this pack.",
            ],
            "review": {
                "reviewer": "SynthPopCan maintainers",
                "reviewed_on": "2026-08-19",
                "evidence": [
                    "Nine household control vectors and the linked-person vector "
                    "resolve through the 2026-08-19 registry revision.",
                    "Vintage-specific source rows and PUMF crosswalks are covered "
                    "by extraction, derivation, planning, and calibration tests.",
                ],
            },
        }
    )
    payload["definition_sha256"] = _catalogue_definition_sha256(payload)
    return payload


def _broad_pack_payload(vintage: int, geography_level: str) -> dict[str, Any]:
    """Build the broadest pack whose controls share the private-household scope."""

    payload = _expanded_housing_pack_payload(vintage, geography_level)
    demographic_margins = [
        ("citizenship", "citizenship_group"),
        ("immigration-status", "immigration_status_group"),
        ("generation-status", "generation_status_group"),
        ("visible-minority", "visible_minority_group"),
    ]
    sex_field = "SEX" if vintage == 2016 else "GENDER"
    payload.update(
        {
            "identifier": f"statcan-{vintage}-broad-{geography_level}-v1",
            "label": (
                f"Statistics Canada {vintage} broad private-household "
                f"{geography_level.upper()} controls"
            ),
            "required_person_fields": [
                "AGEGRP",
                sex_field,
                "CITIZEN",
                "IMMSTAT",
                "GENSTAT",
                "VISMIN",
            ],
            "margins": [
                *payload["margins"],
                *[
                    {
                        "control_identifier": f"statcan.{vintage}.{slug}.v1",
                        "entity_level": "person",
                        "dimensions": [geography_level, dimension],
                        "priority": "required",
                    }
                    for slug, dimension in demographic_margins
                ],
            ],
            "known_limitations": [
                *payload["known_limitations"],
                "Citizenship, immigrant status, generation status, and "
                "visible-minority status use published 25% sample counts for "
                "people in private households.",
                "Marital status, place of birth, education, labour, language, "
                "work activity, and income require different conditional or "
                "banded contracts and are intentionally excluded.",
            ],
            "review": _review(
                "Four additional person vectors use an explicit population-in-"
                "private-households universe.",
                "All person margins refine whole-household weights without "
                "detaching linked people.",
            ),
        }
    )
    payload["definition_sha256"] = _catalogue_definition_sha256(payload)
    return payload


def _catalogue_definition_sha256(pack):
    payload = dict(pack)
    payload.pop("definition_sha256", None)
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
