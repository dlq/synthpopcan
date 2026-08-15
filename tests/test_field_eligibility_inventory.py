"""Contract tests for the pre-1.0 hierarchical PUMF field inventory."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/build_field_eligibility_inventory.py"
ARTIFACT = ROOT / "docs/_static/hierarchical-pumf-field-eligibility-v1.json"
SPEC = importlib.util.spec_from_file_location(
    "build_field_eligibility_inventory", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    """Load the committed inventory once for contract tests."""

    value = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_value_label_parser_preserves_categories_and_stops_at_save() -> None:
    text = """
VALUE LABELS
 AGE
 1 "Under 18"
 2 "18 years and over"
 /
 STATUS
 8 "Not available"
 /
.
SAVE OUTFILE='ignored.sav'.
"""

    assert MODULE.parse_spss_value_labels(text) == {
        "AGE": {"1": "Under 18", "2": "18 years and over"},
        "STATUS": {"8": "Not available"},
    }


def test_value_label_parser_rejects_missing_section() -> None:
    with pytest.raises(ValueError, match="VALUE LABELS"):
        MODULE.parse_spss_value_labels("VARIABLE LABELS")


def test_inventory_covers_each_ordered_source_header_once(
    inventory: dict[str, object],
) -> None:
    fields = inventory["fields"]
    sources = inventory["sources"]
    assert isinstance(fields, list)
    assert isinstance(sources, list)
    assert inventory["schema_version"] == (
        "synthpopcan-hierarchical-pumf-field-eligibility-v1"
    )

    by_vintage: dict[int, list[dict[str, object]]] = {2016: [], 2021: []}
    for field in fields:
        assert isinstance(field, dict)
        by_vintage[int(field["census_vintage"])].append(field)

    for source in MODULE.SOURCES:
        source_record = next(
            item for item in sources if item["census_vintage"] == source.vintage
        )
        header_value = source_record["ordered_header"]
        assert isinstance(header_value, list)
        assert all(isinstance(name, str) for name in header_value)
        header = tuple(header_value)
        records = by_vintage[source.vintage]
        assert len(records) == len(header)
        assert {record["source_name"] for record in records} == set(header)
        assert len({record["field_id"] for record in records}) == len(header)
        assert source_record["field_count"] == len(header)
        assert source_record["csv_header_sha256"] == MODULE.header_sha256(header)
        for hash_name in (
            "source_data_sha256",
            "metadata_sha256",
            "spss_metadata_sha256",
        ):
            digest = source_record[hash_name]
            assert isinstance(digest, str)
            assert len(digest) == 64
            assert set(digest) <= set("0123456789abcdef")
        assert source_record["source_data_redistributed"] is False


def test_inventory_reconciles_all_current_source_targets(
    inventory: dict[str, object],
) -> None:
    fields = inventory["fields"]
    sources = inventory["sources"]
    assert isinstance(fields, list)
    assert isinstance(sources, list)
    for source in MODULE.SOURCES:
        source_record = next(
            item for item in sources if item["census_vintage"] == source.vintage
        )
        header = tuple(source_record["ordered_header"])
        expected = MODULE.current_source_targets(source, header)
        actual = {
            field["source_name"]
            for field in fields
            if field["census_vintage"] == source.vintage
            and field["permitted_role"] == "target"
        }
        assert len(expected) == 35
        assert actual == expected


@pytest.mark.parametrize("vintage", [2016, 2021])
def test_identifiers_weights_and_geographies_are_explicit_non_targets(
    inventory: dict[str, object], vintage: int
) -> None:
    fields = inventory["fields"]
    assert isinstance(fields, list)
    roles = {
        field["source_name"]: field["permitted_role"]
        for field in fields
        if field["census_vintage"] == vintage
    }
    assert {roles[name] for name in ("HH_ID", "EF_ID", "CF_ID", "PP_ID")} == {
        "structural_key"
    }
    assert {roles[name] for name in ("PR", "CMA")} == {"condition"}
    assert roles["WEIGHT"] == "validation_only"
    assert all(roles[f"WT{number}"] == "validation_only" for number in range(1, 17))


def test_every_field_has_a_complete_review_decision(
    inventory: dict[str, object],
) -> None:
    fields = inventory["fields"]
    assert isinstance(fields, list)
    required = {
        "categories",
        "source_universe",
        "concept_id",
        "cross_vintage",
        "entity_level",
        "within_entity_constancy",
        "missing_codes",
        "not_applicable_codes",
        "observed",
        "permitted_role",
        "recommended_representation",
        "dependencies",
        "consistency_invariants",
        "control_compatibility",
        "disclosure_and_interpretation_concerns",
        "review",
    }
    allowed_roles = {
        "target",
        "condition",
        "derive",
        "structural_key",
        "validation_only",
        "defer",
        "exclude",
    }
    for field in fields:
        assert isinstance(field, dict)
        assert required <= field.keys()
        assert field["permitted_role"] in allowed_roles
        assert field["review"]["status"] in {
            "reviewed_current_profile",
            "reviewed_non_target",
            "provisional_defer",
        }
        assert field["control_compatibility"]["status"] in {
            "candidate_requires_crosswalk",
            "uncontrolled",
        }
        assert field["observed"]["entity_observations"] > 0
        assert 0 <= field["observed"]["missing_fraction"] <= 1
        assert 0 <= field["observed"]["not_applicable_fraction"] <= 1
        assert (
            field["observed"]["applicable_observations"]
            + field["observed"]["missing_observations"]
            + field["observed"]["not_applicable_observations"]
            == field["observed"]["entity_observations"]
        )


def test_artifact_contains_only_published_category_metadata(
    inventory: dict[str, object],
) -> None:
    """Do not copy raw observed codes or per-category frequencies into docs."""

    fields = inventory["fields"]
    assert isinstance(fields, list)
    assert "\ufffd" not in ARTIFACT.read_text(encoding="utf-8")
    for field in fields:
        assert isinstance(field, dict)
        categories = field["categories"]
        assert isinstance(categories, list)
        assert all(set(category) == {"code", "label"} for category in categories)
        if field["entity_level"] in {"identifier", "weight"}:
            assert categories == []


def test_exact_local_inputs_regenerate_the_committed_artifact(
    inventory: dict[str, object],
) -> None:
    """Regenerate when maintainers have the ignored public-use source workspace."""

    inputs = [
        path
        for source in MODULE.SOURCES
        for path in (source.csv_path, source.metadata_path, source.spss_path)
    ]
    if not all(path.exists() for path in inputs):
        pytest.skip("locally acquired Statistics Canada source workspace is absent")
    assert MODULE.build_inventory() == inventory


def test_cross_vintage_changes_are_not_flattened(
    inventory: dict[str, object],
) -> None:
    fields = inventory["fields"]
    assert isinstance(fields, list)
    by_id = {field["field_id"]: field for field in fields}
    assert by_id["2016:SEX"]["cross_vintage"] == {
        "counterpart": "GENDER",
        "relationship": "definition_changed",
    }
    assert by_id["2021:CIP2021"]["cross_vintage"] == {
        "counterpart": "CIP2011",
        "relationship": "classification_changed",
    }
    assert by_id["2021:NOC21"]["cross_vintage"] == {
        "counterpart": "NOCS",
        "relationship": "classification_changed",
    }
    assert by_id["2021:HLMOSTEN"]["cross_vintage"] == {
        "counterpart": "HLAEN",
        "relationship": "question_and_derivation_changed",
    }


def test_inventory_records_family_applicability_evidence(
    inventory: dict[str, object],
) -> None:
    fields = inventory["fields"]
    assert isinstance(fields, list)
    by_id = {field["field_id"]: field for field in fields}
    evidence = by_id["2021:EFDIMBM_2018"]["within_entity_constancy"]
    assert evidence["status"] == "verified_constant_among_applicable_values"
    assert evidence["applicable_failures"] == 0
    assert evidence["raw_differences_including_special_codes"] > 0
    assert by_id["2021:EFDIMBM_2018"]["missing_codes"] == ["88888888"]
    assert by_id["2021:EFDIMBM_2018"]["not_applicable_codes"] == []
    assert by_id["2021:FCOND"]["missing_codes"] == ["88888888"]
    assert by_id["2021:FCOND"]["not_applicable_codes"] == ["99999999"]
    assert by_id["2021:FCOND"]["observed"]["not_applicable_observations"] > 0
    assert by_id["2021:EF_RP"]["permitted_role"] == "defer"
    assert (
        "requires_explicit_family_entity_semantics"
        in by_id["2021:EF_RP"]["disclosure_and_interpretation_concerns"]
    )
