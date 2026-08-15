"""Machine-readable licensing presentation for prepared model packages.

The contract in this module describes licence layers and records the project's
publication default; it does not make a legal determination or alter rights
that a licensor does not own or control. Keep all package builders and legacy
readers on these helpers so package bytes and generated manifests cannot drift
into conflicting licence claims.
"""

from __future__ import annotations

__all__ = [
    "PREPARED_MODEL_LICENSING_SCHEMA_VERSION",
    "STATCAN_OPEN_LICENCE_URL",
    "normalize_prepared_model_licensing",
    "statcan_prepared_model_licensing",
    "synthetic_demo_model_licensing",
    "validate_prepared_model_licensing",
]

import json
import math
from collections.abc import Mapping
from typing import Any

PREPARED_MODEL_LICENSING_SCHEMA_VERSION = "synthpopcan-prepared-model-licensing-v1"
STATCAN_OPEN_LICENCE_URL = "https://www.statcan.gc.ca/en/terms-conditions/open-licence"

_CC_BY_4_URL = "https://creativecommons.org/licenses/by/4.0/"
_MIT_URL = "https://github.com/dlq/synthpopcan/blob/main/LICENSE"
_RIGHTS_HOLDER = "Darcy Quesnel"
_POLICY_DECIDED_ON = "2026-08-15"
_DECISION_RECORD = {
    "id": "ADR-0014",
    "url": (
        "https://github.com/dlq/synthpopcan/blob/main/adr/"
        "0014-separate-prepared-model-and-source-licensing.md"
    ),
}

_STATCAN_PRODUCTS = {
    2016: {
        "title": ("2016 Census Public Use Microdata File (PUMF), Hierarchical File"),
        "catalogue_number": "98M0002X2016001",
        "catalogue_url": (
            "https://www150.statcan.gc.ca/n1/en/catalogue/98M0002X2016001"
        ),
        "reference_year": 2016,
    },
    2021: {
        "title": (
            "Hierarchical File, Census of Population: Public Use Microdata "
            "Files, Census Year 2021"
        ),
        "catalogue_number": "98M0001X2021002",
        "catalogue_url": (
            "https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X2021002"
        ),
        "reference_year": 2021,
    },
}

_AUTHOR_MATERIALS = [
    "original selection",
    "original organization",
    "original documentation",
    "original schema representation",
    "original model representation",
]
_AUTHOR_EXCLUSIONS = [
    "Statistics Canada Information",
    "source classifications and labels",
    "facts and factual data",
    "numeric results not protected by applicable law",
]
_CONTINUING_STATCAN_CONDITIONS = [
    {
        "id": "source-acknowledgment",
        "requirement": "Include and maintain the prescribed notice.",
    },
    {
        "id": "accurate-reproduction",
        "requirement": "Reproduce Statistics Canada Information accurately.",
    },
    {
        "id": "no-endorsement",
        "requirement": "Do not suggest endorsement by Statistics Canada.",
    },
    {
        "id": "no-misrepresentation",
        "requirement": "Do not misrepresent the Information or its source.",
    },
    {
        "id": "lawful-use",
        "requirement": "Do not breach or infringe applicable laws.",
    },
    {
        "id": "no-identification-linkage",
        "requirement": (
            "Do not merge or link Information to attempt to identify a person, "
            "business, or organization."
        ),
    },
    {
        "id": "no-confidential-access-appearance",
        "requirement": (
            "Do not present Information as though identifiable confidential "
            "Statistics Canada information was available."
        ),
    },
    {
        "id": "no-reverse-engineering",
        "requirement": (
            "Do not reverse engineer software provided as part of the Information."
        ),
    },
]


def statcan_prepared_model_licensing(census_year: int) -> dict[str, Any]:
    """Return the authoritative layered presentation for one PUMF year.

    The project default is deliberately permissive for rights controlled by the
    maintainer while preserving the Statistics Canada source licence,
    attribution and privacy conditions as a cumulative layer.  The recorded
    policy is a maintainer decision, not an assertion of external legal review.
    """

    try:
        product = _STATCAN_PRODUCTS[census_year]
    except KeyError as exc:
        raise ValueError(
            "prepared-model licensing supports Census years 2016 and 2021"
        ) from exc
    notice = (
        f"Adapted from Statistics Canada, {product['title']} "
        f"({product['catalogue_number']}), {product['reference_year']}. "
        "This does not constitute an endorsement by Statistics Canada of this "
        "product."
    )
    return {
        "schema_version": PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
        "package_basis": "census-derived",
        "presentation": {
            "mode": "cumulative-layers-not-alternatives",
            "alternative_licence_choice": False,
            "statement": (
                "The licence layers are cumulative, not alternatives. CC BY 4.0 "
                "does not license, replace, or supersede Statistics Canada "
                "Information or rights governed by the Statistics Canada Open "
                "Licence."
            ),
        },
        "authored_material": {
            "rights_holder": _RIGHTS_HOLDER,
            "licence": {
                "spdx_id": "CC-BY-4.0",
                "name": "Creative Commons Attribution 4.0 International",
                "url": _CC_BY_4_URL,
            },
            "grant_scope": {
                "only_rights_owned_or_controlled": True,
                "only_to_extent_protected": True,
                "materials": list(_AUTHOR_MATERIALS),
                "statement": (
                    "CC BY 4.0 is offered only for rights Darcy Quesnel owns or "
                    "controls in the named original material, and only to the "
                    "extent that material is protected by applicable law."
                ),
            },
            "excluded_material": list(_AUTHOR_EXCLUSIONS),
        },
        "source_information": {
            "provider": "Statistics Canada",
            "classification": "Information",
            "product": {
                "title": product["title"],
                "catalogue_number": product["catalogue_number"],
                "catalogue_url": product["catalogue_url"],
                "reference_year": product["reference_year"],
            },
            "licence": {
                "name": "Statistics Canada Open Licence",
                "url": STATCAN_OPEN_LICENCE_URL,
            },
            "prescribed_notice": notice,
            "continuing_conditions": [
                dict(condition) for condition in _CONTINUING_STATCAN_CONDITIONS
            ],
        },
        "policy_decision": _accepted_project_policy_decision(),
    }


def synthetic_demo_model_licensing() -> dict[str, Any]:
    """Return the distinct single-layer presentation for the synthetic demo."""

    return {
        "schema_version": PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
        "package_basis": "synthetic-only",
        "presentation": {
            "mode": "single-synthetic-authored-layer",
            "alternative_licence_choice": False,
            "statement": (
                "This bundled teaching package uses synthetic toy rows only; it "
                "does not contain a Statistics Canada licence layer."
            ),
        },
        "authored_material": {
            "rights_holder": _RIGHTS_HOLDER,
            "licence": {
                "spdx_id": "MIT",
                "name": "MIT License",
                "url": _MIT_URL,
            },
            "grant_scope": {
                "only_rights_owned_or_controlled": True,
                "only_to_extent_protected": True,
                "materials": [
                    "synthetic demonstration selection and organization",
                    "synthetic demonstration documentation",
                    "synthetic schema and model representation",
                ],
                "statement": (
                    "The MIT License applies to the authored synthetic teaching "
                    "package only to the extent Darcy Quesnel owns or controls "
                    "protected rights in it."
                ),
            },
            "excluded_material": [
                "facts and factual data",
                "numeric results not protected by applicable law",
            ],
        },
        "source_information": None,
        "policy_decision": {
            "status": "not-applicable",
            "basis": "not-applicable",
            "decision_record": None,
            "decided_by": None,
            "decided_on": None,
            "external_legal_review": "not-applicable",
            "statement": (
                "The synthetic-only teaching package is governed directly by its "
                "MIT authored-material licence; the Census-derived project default "
                "does not apply."
            ),
        },
    }


def normalize_prepared_model_licensing(
    package: Mapping[str, object],
) -> dict[str, Any]:
    """Validate current licensing or mark unclassified legacy bytes conservatively.

    Provenance strings in arbitrary local JSON are not authority to create a
    licence grant on behalf of this project's maintainer.  Trusted registered
    packages are enriched from their checksum-bound catalogue before they reach
    this generic validator; every other package without an embedded contract is
    explicitly unclassified.
    """

    normalized = dict(package)
    is_synthetic_demo = _is_synthetic_demo(package)
    is_statcan, census_year = _legacy_statcan_source(package)
    if is_synthetic_demo and is_statcan:
        raise ValueError(
            "prepared-model provenance cannot be both synthetic-only and "
            "Statistics Canada-derived"
        )

    if "licensing" in package:
        licensing = validate_prepared_model_licensing(package["licensing"])
        package_basis = licensing["package_basis"]
        if is_synthetic_demo and package_basis not in {
            "synthetic-only",
            "unclassified-legacy",
        }:
            raise ValueError(
                "synthetic-only package provenance conflicts with licensing"
            )
        if is_statcan and package_basis not in {
            "census-derived",
            "unclassified-legacy",
        }:
            raise ValueError(
                "Statistics Canada package provenance requires Census-derived licensing"
            )
        if census_year is not None and package_basis == "census-derived":
            source_information = licensing["source_information"]
            product = source_information["product"]
            expected_catalogue = _STATCAN_PRODUCTS[census_year]["catalogue_number"]
            if product["catalogue_number"] != expected_catalogue:
                raise ValueError(
                    "prepared-model licensing source vintage conflicts with package "
                    "provenance"
                )
        normalized["licensing"] = licensing
        return normalized

    normalized["licensing"] = _unclassified_legacy_licensing()
    return normalized


def validate_prepared_model_licensing(value: object) -> dict[str, Any]:
    """Strictly validate and return a detached JSON-native licensing object."""

    _assert_json_safe(value, path="licensing")
    if not isinstance(value, dict):
        raise ValueError("licensing must be a JSON object")
    schema_version = value.get("schema_version")
    if schema_version != PREPARED_MODEL_LICENSING_SCHEMA_VERSION:
        raise ValueError("unsupported prepared-model licensing schema")

    package_basis = value.get("package_basis")
    if package_basis == "census-derived":
        source = value.get("source_information")
        if not isinstance(source, dict):
            raise ValueError("Census-derived licensing requires source_information")
        product = source.get("product")
        if not isinstance(product, dict):
            raise ValueError("Census-derived licensing requires a source product")
        catalogue_number = product.get("catalogue_number")
        if not isinstance(catalogue_number, str):
            raise ValueError("source product catalogue_number must be a string")
        year_by_catalogue = {
            details["catalogue_number"]: year
            for year, details in _STATCAN_PRODUCTS.items()
        }
        census_year = year_by_catalogue.get(catalogue_number)
        if census_year is None:
            raise ValueError("unsupported Statistics Canada source catalogue")
        policy_decision = value.get("policy_decision")
        if not isinstance(policy_decision, dict):
            raise ValueError("Census-derived licensing requires policy_decision")
        if policy_decision.get("status") != "accepted":
            raise ValueError("unsupported Census-derived policy decision status")
        expected = statcan_prepared_model_licensing(census_year)
    elif package_basis == "synthetic-only":
        expected = synthetic_demo_model_licensing()
    elif package_basis == "unclassified-legacy":
        expected = _unclassified_legacy_licensing()
    else:
        raise ValueError("unsupported prepared-model licensing package_basis")

    if value != expected:
        raise ValueError(
            "prepared-model licensing does not match the authoritative schema-v1 "
            "presentation"
        )
    return json.loads(json.dumps(value, allow_nan=False))


def _unclassified_legacy_licensing() -> dict[str, Any]:
    return {
        "schema_version": PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
        "package_basis": "unclassified-legacy",
        "presentation": {
            "mode": "unclassified-legacy",
            "alternative_licence_choice": False,
            "statement": (
                "No licence grant or source layer was inferred from these legacy "
                "package bytes; inspect and classify their provenance before "
                "redistribution."
            ),
        },
        "authored_material": {
            "rights_holder": "Not asserted",
            "licence": {
                "spdx_id": "NOASSERTION",
                "name": "Not asserted",
                "url": None,
            },
            "grant_scope": {
                "only_rights_owned_or_controlled": True,
                "only_to_extent_protected": True,
                "materials": [],
                "statement": "No authored-material licence grant was inferred.",
            },
            "excluded_material": list(_AUTHOR_EXCLUSIONS),
        },
        "source_information": None,
        "policy_decision": {
            "status": "unresolved",
            "basis": "unclassified-legacy",
            "decision_record": None,
            "decided_by": None,
            "decided_on": None,
            "external_legal_review": "not-obtained",
            "statement": (
                "No project licensing default was inferred. Source and rights "
                "classification must be resolved before redistribution."
            ),
        },
    }


def _accepted_project_policy_decision() -> dict[str, Any]:
    decision_record = dict(_DECISION_RECORD)
    decision_record["status"] = "accepted"
    return {
        "status": "accepted",
        "basis": "maintainer-selected-permissive-default",
        "decision_record": decision_record,
        "decided_by": _RIGHTS_HOLDER,
        "decided_on": _POLICY_DECIDED_ON,
        "external_legal_review": "not-obtained",
        "statement": (
            "This is the project's maintained publication and licensing default, "
            "subject to the cumulative licence layers, provenance requirements, "
            "and privacy safeguards recorded here. It is not legal advice or a "
            "claim of external legal review."
        ),
    }


def _is_synthetic_demo(package: Mapping[str, object]) -> bool:
    privacy = package.get("privacy")
    if isinstance(privacy, Mapping) and privacy.get("safe_demo") is True:
        return True
    provenance = package.get("provenance")
    if isinstance(provenance, Mapping):
        if provenance.get("contains_real_microdata") is False:
            return True
    return False


def _legacy_statcan_source(
    package: Mapping[str, object],
) -> tuple[bool, int | None]:
    evidence: list[str] = []
    provider_is_statcan = False
    for field in ("catalogue_metadata", "source_provenance", "provenance"):
        value = package.get(field)
        if not isinstance(value, Mapping):
            continue
        evidence.extend(str(item) for item in value.values() if isinstance(item, str))
        if value.get("provider") == "Statistics Canada":
            provider_is_statcan = True
    training = package.get("training_manifest")
    if isinstance(training, Mapping):
        source = training.get("source")
        if isinstance(source, Mapping):
            evidence.extend(
                str(item) for item in source.values() if isinstance(item, str)
            )
            source_format = source.get("source_format")
            if isinstance(source_format, str) and source_format.startswith("statcan-"):
                provider_is_statcan = True

    joined = " ".join(evidence)
    if not provider_is_statcan and "Statistics Canada" not in joined:
        return False, None
    matching_years = {
        year
        for year, product in _STATCAN_PRODUCTS.items()
        if str(year) in joined or product["catalogue_number"] in joined
    }
    if len(matching_years) > 1:
        raise ValueError(
            "prepared-model provenance contains conflicting 2016 and 2021 "
            "Statistics Canada source vintages"
        )
    if matching_years:
        return True, matching_years.pop()
    return True, None


def _assert_json_safe(value: object, *, path: str) -> None:
    if value is None or isinstance(value, str | bool):
        return
    if type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _assert_json_safe(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string object key")
            _assert_json_safe(item, path=f"{path}.{key}")
        return
    raise ValueError(f"{path} contains a non-JSON value: {type(value).__name__}")
