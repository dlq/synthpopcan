from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import pytest

from synthpopcan.api import read_model_package
from synthpopcan.cli_tree import _build_linked_package_inspection
from synthpopcan.model_licensing import (
    PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
    normalize_prepared_model_licensing,
    statcan_prepared_model_licensing,
    synthetic_demo_model_licensing,
    validate_prepared_model_licensing,
)
from synthpopcan.models import model_payload
from synthpopcan.workflows.models import inspect_prepared_model


def test_packaged_schema_v1_examples_pin_all_supported_contracts() -> None:
    fixture = json.loads(
        files("synthpopcan.contracts")
        .joinpath("prepared-model-licensing-v1-examples.json")
        .read_text()
    )

    assert (
        fixture["schema_version"] == "synthpopcan-prepared-model-licensing-examples-v1"
    )
    assert fixture["contract_schema_version"] == (
        PREPARED_MODEL_LICENSING_SCHEMA_VERSION
    )
    examples = fixture["examples"]
    assert set(examples) == {
        "census-2016-project-default",
        "census-2021-project-default",
        "synthetic-only",
        "unclassified-legacy",
    }
    assert examples["census-2016-project-default"] == (
        statcan_prepared_model_licensing(2016)
    )
    assert examples["census-2021-project-default"] == (
        statcan_prepared_model_licensing(2021)
    )
    assert examples["synthetic-only"] == synthetic_demo_model_licensing()
    assert (
        examples["unclassified-legacy"]
        == normalize_prepared_model_licensing({})["licensing"]
    )
    for contract in examples.values():
        assert validate_prepared_model_licensing(contract) == contract


@pytest.mark.parametrize(
    ("year", "catalogue"),
    [
        (2016, "98M0002X2016001"),
        (2021, "98M0001X2021002"),
    ],
)
def test_census_contract_has_scoped_cumulative_layers_and_exact_source(
    year: int,
    catalogue: str,
) -> None:
    licensing = statcan_prepared_model_licensing(year)

    assert licensing["schema_version"] == PREPARED_MODEL_LICENSING_SCHEMA_VERSION
    assert licensing["package_basis"] == "census-derived"
    presentation = licensing["presentation"]
    assert presentation["mode"] == "cumulative-layers-not-alternatives"
    assert presentation["alternative_licence_choice"] is False
    assert (
        "does not license, replace, or supersede Statistics Canada Information"
        in presentation["statement"]
    )

    authored = licensing["authored_material"]
    assert authored["rights_holder"] == "Darcy Quesnel"
    assert authored["licence"]["spdx_id"] == "CC-BY-4.0"
    assert authored["grant_scope"]["only_rights_owned_or_controlled"] is True
    assert authored["grant_scope"]["only_to_extent_protected"] is True
    assert set(authored["grant_scope"]["materials"]) == {
        "original selection",
        "original organization",
        "original documentation",
        "original schema representation",
        "original model representation",
    }
    assert set(authored["excluded_material"]) == {
        "Statistics Canada Information",
        "source classifications and labels",
        "facts and factual data",
        "numeric results not protected by applicable law",
    }

    source = licensing["source_information"]
    assert source["classification"] == "Information"
    assert source["product"]["catalogue_number"] == catalogue
    assert source["product"]["reference_year"] == year
    assert source["licence"]["url"] == (
        "https://www.statcan.gc.ca/en/terms-conditions/open-licence"
    )
    assert source["prescribed_notice"].startswith("Adapted from Statistics Canada,")
    assert source["prescribed_notice"].endswith(
        "This does not constitute an endorsement by Statistics Canada of this product."
    )
    assert {item["id"] for item in source["continuing_conditions"]} >= {
        "source-acknowledgment",
        "accurate-reproduction",
        "no-endorsement",
        "no-misrepresentation",
        "no-identification-linkage",
    }

    policy_decision = licensing["policy_decision"]
    assert policy_decision["status"] == "accepted"
    assert policy_decision["basis"] == "maintainer-selected-permissive-default"
    assert policy_decision["decision_record"]["id"] == "ADR-0014"
    assert policy_decision["decision_record"]["status"] == "accepted"
    assert policy_decision["decided_by"] == "Darcy Quesnel"
    assert policy_decision["decided_on"] == "2026-08-15"
    assert policy_decision["external_legal_review"] == "not-obtained"
    assert "privacy safeguards" in policy_decision["statement"]
    assert "not legal advice" in policy_decision["statement"]
    assert json.loads(json.dumps(licensing, allow_nan=False)) == licensing
    assert validate_prepared_model_licensing(licensing) == licensing


def test_contract_rejects_unknown_vintages() -> None:
    with pytest.raises(ValueError, match="supports Census years 2016 and 2021"):
        statcan_prepared_model_licensing(2031)


def test_validator_rejects_drift_and_non_json_values() -> None:
    drifted = statcan_prepared_model_licensing(2016)
    drifted["authored_material"]["licence"]["spdx_id"] = "MIT"
    with pytest.raises(ValueError, match="authoritative schema-v1"):
        validate_prepared_model_licensing(drifted)

    non_json = statcan_prepared_model_licensing(2016)
    non_json["authored_material"]["excluded_material"] = ("tuple",)
    with pytest.raises(ValueError, match="non-JSON value: tuple"):
        validate_prepared_model_licensing(non_json)

    non_finite = statcan_prepared_model_licensing(2016)
    non_finite["authored_material"]["excluded_material"] = [float("nan")]
    with pytest.raises(ValueError, match="non-finite number"):
        validate_prepared_model_licensing(non_finite)

    non_string_key = statcan_prepared_model_licensing(2016)
    non_string_key["authored_material"]["excluded_material"] = [{1: "value"}]
    with pytest.raises(ValueError, match="non-string object key"):
        validate_prepared_model_licensing(non_string_key)


def test_validator_rejects_every_semantic_boundary_failure() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        validate_prepared_model_licensing([])
    with pytest.raises(ValueError, match="unsupported prepared-model licensing"):
        validate_prepared_model_licensing({})

    cases: list[tuple[str, object]] = []
    missing_source = statcan_prepared_model_licensing(2021)
    missing_source["source_information"] = None
    cases.append(("requires source_information", missing_source))

    missing_product = statcan_prepared_model_licensing(2021)
    missing_product["source_information"]["product"] = None
    cases.append(("requires a source product", missing_product))

    invalid_catalogue_type = statcan_prepared_model_licensing(2021)
    invalid_catalogue_type["source_information"]["product"]["catalogue_number"] = 1
    cases.append(("catalogue_number must be a string", invalid_catalogue_type))

    unknown_catalogue = statcan_prepared_model_licensing(2021)
    unknown_catalogue["source_information"]["product"]["catalogue_number"] = (
        "98M0001X2031002"
    )
    cases.append(("unsupported Statistics Canada source catalogue", unknown_catalogue))

    missing_policy_decision = statcan_prepared_model_licensing(2021)
    missing_policy_decision["policy_decision"] = None
    cases.append(("requires policy_decision", missing_policy_decision))

    invalid_policy_status = statcan_prepared_model_licensing(2021)
    invalid_policy_status["policy_decision"]["status"] = "pending"
    cases.append(
        ("unsupported Census-derived policy decision status", invalid_policy_status)
    )

    invalid_basis = statcan_prepared_model_licensing(2021)
    invalid_basis["package_basis"] = "mixed"
    cases.append(("unsupported prepared-model licensing package_basis", invalid_basis))

    for message, value in cases:
        with pytest.raises(ValueError, match=message):
            validate_prepared_model_licensing(value)


def test_demo_bytes_have_a_distinct_synthetic_only_contract() -> None:
    demo_path = Path("src/synthpopcan/models/demo-linked-household-person-package.json")
    raw_demo = json.loads(demo_path.read_text())
    expected = synthetic_demo_model_licensing()

    assert raw_demo["licensing"] == expected
    assert expected["package_basis"] == "synthetic-only"
    assert expected["authored_material"]["licence"]["spdx_id"] == "MIT"
    assert expected["source_information"] is None
    assert expected["policy_decision"]["status"] == "not-applicable"
    assert validate_prepared_model_licensing(expected) == expected


def test_unlicensed_local_package_is_unclassified_and_non_destructive() -> None:
    demo = model_payload("demo-linked-household-person")
    legacy_census = deepcopy(demo)
    legacy_census.pop("licensing")
    legacy_census.pop("catalogue_metadata")
    legacy_census["privacy"]["safe_demo"] = False
    legacy_census["provenance"].pop("contains_real_microdata")
    legacy_census["source_provenance"] = {
        "provider": "Statistics Canada",
        "title": "2021 Census Hierarchical PUMF",
    }
    legacy_census["training_manifest"] = {
        "source": {"source_format": "statcan-2021-hierarchical"}
    }

    normalized = normalize_prepared_model_licensing(legacy_census)
    licensing = normalized["licensing"]
    assert "licensing" not in legacy_census
    assert licensing["package_basis"] == "unclassified-legacy"
    assert licensing["authored_material"]["rights_holder"] == "Not asserted"
    assert licensing["authored_material"]["licence"]["spdx_id"] == "NOASSERTION"
    assert inspect_prepared_model(legacy_census)["licensing"] == licensing
    assert _build_linked_package_inspection(legacy_census, None)["licensing"] == (
        licensing
    )
    assert normalize_prepared_model_licensing(normalized) == normalized

    unclassified = normalize_prepared_model_licensing(
        {"schema_version": "synthpopcan-linked-tree-package-v1"}
    )["licensing"]
    assert unclassified["package_basis"] == "unclassified-legacy"
    assert unclassified["authored_material"]["licence"]["spdx_id"] == "NOASSERTION"


def test_legacy_normalization_fails_closed_on_provenance_contradictions() -> None:
    census_2016 = {
        "source_provenance": {
            "provider": "Statistics Canada",
            "title": "2016 Census Hierarchical PUMF",
        }
    }
    mismatched = {
        **census_2016,
        "licensing": statcan_prepared_model_licensing(2021),
    }
    with pytest.raises(ValueError, match="source vintage conflicts"):
        normalize_prepared_model_licensing(mismatched)

    statcan_with_demo_licensing = {
        **census_2016,
        "licensing": synthetic_demo_model_licensing(),
    }
    with pytest.raises(ValueError, match="requires Census-derived licensing"):
        normalize_prepared_model_licensing(statcan_with_demo_licensing)

    contradictory_source = {
        **census_2016,
        "privacy": {"safe_demo": True},
    }
    with pytest.raises(ValueError, match="both synthetic-only and Statistics Canada"):
        normalize_prepared_model_licensing(contradictory_source)

    synthetic_with_census_licensing = {
        "provenance": {"contains_real_microdata": False},
        "licensing": statcan_prepared_model_licensing(2021),
    }
    with pytest.raises(ValueError, match="synthetic-only package provenance conflicts"):
        normalize_prepared_model_licensing(synthetic_with_census_licensing)


def test_unlicensed_local_provenance_never_invents_a_rights_grant() -> None:
    statcan = normalize_prepared_model_licensing(
        {
            "training_manifest": {
                "source": {"source_format": "statcan-2021-hierarchical"}
            }
        }
    )
    assert statcan["licensing"]["package_basis"] == "unclassified-legacy"

    synthetic = normalize_prepared_model_licensing({"privacy": {"safe_demo": True}})
    assert synthetic["licensing"]["package_basis"] == "unclassified-legacy"

    future = normalize_prepared_model_licensing(
        {
            "source_provenance": {
                "provider": "Statistics Canada",
                "title": "Future Census source",
            }
        }
    )
    assert future["licensing"]["package_basis"] == "unclassified-legacy"

    with pytest.raises(ValueError, match="conflicting 2016 and 2021"):
        normalize_prepared_model_licensing(
            {
                "source_provenance": {
                    "provider": "Statistics Canada",
                    "title": "2016 and 2021 Census PUMF",
                },
            }
        )


def test_package_reader_strictly_validates_existing_licensing(tmp_path: Path) -> None:
    package = model_payload("demo-linked-household-person")
    package["licensing"]["source_information"] = {"provider": "Statistics Canada"}
    path = tmp_path / "malformed-package.json"
    path.write_text(json.dumps(package))

    with pytest.raises(ValueError, match="authoritative schema-v1"):
        read_model_package(path)


def test_batch_builder_embeds_the_authoritative_contract() -> None:
    source = Path("scripts/build_all_model_packages.py").read_text()

    assert '"licensing": statcan_prepared_model_licensing(year)' in source
