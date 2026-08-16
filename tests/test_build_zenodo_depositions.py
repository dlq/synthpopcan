import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

SCRIPT = Path(__file__).parents[1] / "scripts/build_zenodo_depositions.py"
SPEC = importlib.util.spec_from_file_location("build_zenodo_depositions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_deposition = MODULE.build_deposition


def test_deposition_carries_the_statcan_attribution_notice() -> None:
    deposition = build_deposition(
        "ontario-2021-all-fields", concept_doi="10.5281/zenodo.1234567"
    )
    description = deposition["metadata"]["description"]

    assert "Adapted from Statistics Canada," in description
    assert "does not constitute an endorsement by Statistics Canada" in description
    assert "statcan.gc.ca/en/terms-conditions/open-licence" in description
    assert "not legal anonymization" in description


def test_deposition_links_upward_to_software_and_back_to_source() -> None:
    deposition = build_deposition(
        "montreal-cma-2016-all-fields", concept_doi="10.5281/zenodo.1234567"
    )
    relations = {
        item["relation"]: item["identifier"]
        for item in deposition["metadata"]["related_identifiers"]
    }

    assert relations["isPartOf"] == "10.5281/zenodo.1234567"
    assert relations["isDerivedFrom"].endswith("98M0002X2016001")
    assert "synthpopcan" in relations["isCompiledBy"]


def test_deposition_omits_software_link_when_concept_doi_is_unknown() -> None:
    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    relations = {
        item["relation"] for item in deposition["metadata"]["related_identifiers"]
    }

    assert "isPartOf" not in relations
    assert {"isDerivedFrom", "isCompiledBy"} <= relations


def test_deposition_records_both_checksums_for_integrity() -> None:
    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    payload = deposition["synthpopcan"]
    historical = payload["historical_asset"]

    assert payload["deposit_operation"] == "review-metadata-only"
    assert payload["asset_ready"] is False
    assert historical["contains_embedded_licensing"] is True
    assert len(historical["sha256"]) == 64
    assert len(historical["uncompressed_sha256"]) == 64
    assert historical["uncompressed_size_bytes"] > historical["size_bytes"]
    assert historical["url"].endswith(".json.gz/content")
    assert historical["url"].endswith(f"/{historical['filename']}/content")
    assert historical["filename"].endswith(".json.gz")


def test_deposition_uses_an_attribution_preserving_licence() -> None:
    deposition = build_deposition("quebec-2016-all-fields", concept_doi=None)

    assert deposition["metadata"]["license"] == "other-open"
    assert deposition["metadata"]["access_right"] == "open"
    description = deposition["metadata"]["description"]
    assert "only for rights Darcy Quesnel owns or controls" in description
    assert "https://creativecommons.org/licenses/by/4.0/" in description
    assert "does not license, replace, or supersede Statistics Canada" in description
    assert "Statistics Canada Open Licence" in description
    assert "cumulative, not alternative" in description

    licensing = deposition["synthpopcan"]["licensing"]
    assert licensing["schema_version"] == "synthpopcan-prepared-model-licensing-v1"
    assert licensing["package_basis"] == "census-derived"
    assert licensing["presentation"]["mode"] == "cumulative-layers-not-alternatives"
    assert licensing["presentation"]["alternative_licence_choice"] is False
    policy = licensing["policy_decision"]
    assert policy["status"] == "accepted"
    assert policy["basis"] == "maintainer-selected-permissive-default"
    assert policy["external_legal_review"] == "not-obtained"
    assert licensing["authored_material"]["licence"]["spdx_id"] == "CC-BY-4.0"
    source = licensing["source_information"]
    assert source["licence"]["name"] == "Statistics Canada Open Licence"
    assert source["prescribed_notice"] in description


def test_deposition_fails_closed_on_catalogue_licensing_drift(monkeypatch) -> None:
    catalogue = MODULE.model_catalogue()
    target = next(item for item in catalogue if item["id"] == "quebec-2016-all-fields")
    target["licensing"]["presentation"]["mode"] = "alternative-licence-choice"
    monkeypatch.setattr(MODULE, "model_catalogue", lambda: catalogue)

    with pytest.raises(ValueError, match="authoritative schema-v1"):
        build_deposition("quebec-2016-all-fields", concept_doi=None)


def test_deposition_credits_the_same_authors_as_citation_metadata() -> None:
    """Archived model records must credit the same authors as CITATION.cff."""
    import re
    from pathlib import Path

    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)
    creators = deposition["metadata"]["creators"]

    assert creators, "model records must name their creators"
    for creator in creators:
        # Never infer an ORCID; only record one supplied by its owner.
        assert set(creator) <= {"name", "affiliation", "orcid"}

    citation = Path("CITATION.cff").read_text()
    families = set(re.findall(r"family-names:\s*(\S+)", citation))
    assert {name["name"].split(",")[0] for name in creators} <= families


def test_deposition_description_does_not_repeat_the_source_title() -> None:
    """The licence paragraph should not restate what attribution already said."""
    deposition = build_deposition("montreal-cma-2016-all-fields", concept_doi=None)
    description = deposition["metadata"]["description"]

    # The product title belongs in the attribution notice only; the licence
    # paragraph links to the source rather than restating it. The catalogue
    # number legitimately recurs inside the link href.
    assert (
        description.count(
            "2016 Census Public Use Microdata File (PUMF), Hierarchical File"
        )
        == 1
    )
    assert "local 2016" not in description


def test_rights_correction_plan_skips_all_32_completed_versions() -> None:
    first = MODULE.build_rights_correction_plan()
    second = MODULE.build_rights_correction_plan()

    assert first == second
    assert first["network_writes"] is False
    assert first["existing_record_count"] == 0
    assert first["corrected_record_count"] == 32
    assert first["actions"] == []
    assert first["current_policy_decision"] == "accepted"
    assert (
        "- **Archive correction implementation:** Completed"
        in first["policy"]["production_gates"]
    )
    assert first["policy"]["production_gates"] == [
        "- **Status:** Accepted",
        "- **Archive correction implementation:** Completed",
    ]


def test_generated_metadata_is_review_only_and_describes_corrected_bytes() -> None:
    deposition = build_deposition("ontario-2021-all-fields", concept_doi=None)

    assert deposition["synthpopcan"]["asset_ready"] is False
    assert "asset_url" not in deposition["synthpopcan"]
    assert "verified non-overwriting archive version" in deposition["metadata"]["notes"]
    assert "Published package integrity" in deposition["metadata"]["description"]
    assert "review context only" not in deposition["metadata"]["description"]


def test_correction_plan_mode_writes_only_a_no_network_plan(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        MODULE.main, ["--correction-plan", "--out", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert "no Zenodo request was made" in result.output
    assert [path.name for path in tmp_path.iterdir()] == [
        "prepared-model-rights-correction.json"
    ]
    plan = json.loads((tmp_path / "prepared-model-rights-correction.json").read_text())
    assert plan["network_writes"] is False
    assert plan["existing_record_count"] == 0
    assert plan["corrected_record_count"] == 32


def test_candidate_mapping_builds_executable_metadata_and_new_version_manifests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model_id = "ontario-2021-all-fields"
    review = build_deposition(model_id, concept_doi=None)
    entry = next(item for item in MODULE.model_catalogue() if item["id"] == model_id)
    historical = MODULE.model_registry_entry(model_id).copy()
    historical["contains_embedded_licensing"] = False
    monkeypatch.setattr(MODULE, "model_registry_entry", lambda unused: historical)
    filename = f"{model_id}-v1.0.0-corrected.json.gz"
    asset_url = (tmp_path / filename).resolve().as_uri()
    historical_asset = {
        "filename": MODULE._archive_filename(historical),
        "size_bytes": historical["size_bytes"],
        "sha256": historical["sha256"],
        "uncompressed_size_bytes": historical["uncompressed_size_bytes"],
        "uncompressed_sha256": historical["uncompressed_sha256"],
        "contains_embedded_licensing": False,
    }
    candidate_asset = {
        "filename": filename,
        "asset_url": asset_url,
        "size_bytes": 100,
        "sha256": "2" * 64,
        "uncompressed_size_bytes": 200,
        "uncompressed_sha256": "3" * 64,
        "contains_embedded_licensing": True,
    }
    candidate = {
        "model_id": model_id,
        "census_vintage": entry["census_vintage"],
        "package_schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "existing_package_version": entry["release_version"],
        "existing_record_id": 12346,
        "existing_concept_doi": entry["doi"],
        "existing_version_doi": "10.5281/zenodo.12346",
        "new_package_version": "v1.0.0-corrected",
        "licensing_schema_version": review["synthpopcan"]["licensing"][
            "schema_version"
        ],
        "historical_asset": historical_asset,
        "candidate_asset": candidate_asset,
        "filename": filename,
        "asset_url": asset_url,
        "size_bytes": 100,
        "sha256": "2" * 64,
        "uncompressed_size_bytes": 200,
        "uncompressed_sha256": "3" * 64,
        "licensing": review["synthpopcan"]["licensing"],
        "transformation": "rights-metadata-only-top-level-field-insertion",
        "model_retrained": False,
        "historical_json_preserved_except_inserted_licensing": True,
    }
    input_path = tmp_path / "candidates.json"
    input_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-correction-candidates-v1",
                "build_scope": "test-subset",
                "production_coverage_complete": False,
                "production_ready": False,
                "non_production_reason": "bounded test subset",
                "network_writes": False,
                "model_retrained": False,
                "new_package_version": "v1.0.0-corrected",
                "candidate_count": 1,
                "candidate_model_ids": [model_id],
                "candidates": {model_id: candidate},
            }
        )
    )
    output = tmp_path / "out"

    missing_concept = CliRunner().invoke(
        MODULE.main,
        [
            "--correction-candidates",
            str(input_path),
            "--out",
            str(tmp_path / "missing-concept"),
        ],
    )
    assert missing_concept.exit_code == 2
    assert "--concept-doi is required" in missing_concept.output

    result = CliRunner().invoke(
        MODULE.main,
        [
            "--correction-candidates",
            str(input_path),
            "--concept-doi",
            "10.5281/zenodo.999",
            "--out",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    metadata = json.loads((output / f"{model_id}.metadata-correction.json").read_text())
    version = json.loads((output / f"{model_id}.new-version.json").read_text())
    execution = json.loads((output / "execution-index.json").read_text())
    assert metadata["synthpopcan"]["deposit_operation"] == ("correct-existing-metadata")
    assert metadata["synthpopcan"]["metadata_ready"] is False
    assert version["synthpopcan"]["deposit_operation"] == "create-new-version"
    assert version["synthpopcan"]["asset_ready"] is False
    assert version["metadata"]["version"] == "v1.0.0-corrected"
    assert "Corrected package integrity" in version["metadata"]["description"]
    assert "review context only" not in version["metadata"]["description"]
    assert version["synthpopcan"]["licensing"] == candidate["licensing"]
    for manifest in (metadata, version):
        assert manifest["synthpopcan"]["model_retrained"] is False
        assert (
            manifest["synthpopcan"][
                "historical_json_preserved_except_inserted_licensing"
            ]
            is True
        )
        assert (
            manifest["synthpopcan"]["package_schema_version"]
            == candidate["package_schema_version"]
        )
        assert [
            relation
            for relation in manifest["metadata"]["related_identifiers"]
            if relation["relation"] == "isPartOf"
        ] == [
            {
                "relation": "isPartOf",
                "identifier": "10.5281/zenodo.999",
                "resource_type": "software",
            }
        ]
    assert execution["schema_version"] == (
        "synthpopcan-zenodo-correction-execution-index-v1"
    )
    assert len(execution["operations"]) == 2
    assert execution["production_ready"] is False
    assert execution["candidate_model_ids"] == [model_id]
    assert execution["candidate_envelope_sha256"]
    assert execution["new_package_version"] == "v1.0.0-corrected"
    assert {operation["operation_id"] for operation in execution["operations"]} == {
        MODULE._correction_operation_descriptor(metadata)["operation_id"],
        MODULE._correction_operation_descriptor(version)["operation_id"],
    }

    original_bundle = {
        path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
    }
    repeated = CliRunner().invoke(
        MODULE.main,
        [
            "--correction-candidates",
            str(input_path),
            "--concept-doi",
            "10.5281/zenodo.999",
            "--out",
            str(output),
        ],
    )
    assert repeated.exit_code == 2
    assert "refusing to overwrite correction bundle" in repeated.output
    assert {
        path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
    } == original_bundle
