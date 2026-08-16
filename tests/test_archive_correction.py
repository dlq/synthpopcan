from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import pytest

from synthpopcan._archive_correction import (
    archive_correction_registry_updates,
    load_archive_correction_evidence,
    validate_archive_correction_evidence,
)
from synthpopcan.models import model_catalogue_entry, model_registry_entry


def test_tracked_archive_correction_evidence_is_complete_and_sanitized() -> None:
    evidence = load_archive_correction_evidence()

    assert evidence["recorded_on"] == "2026-08-16"
    assert evidence["target"] == "PRODUCTION"
    assert evidence["api"] == "https://zenodo.org/api"
    assert len(evidence["models"]) == 32
    assert evidence["verification"] == {
        "candidate_assets_verified": 32,
        "candidate_compressed_bytes": 43_967_253,
        "candidate_uncompressed_bytes": 3_765_538_331,
        "concepts_verified": 32,
        "historical_assets_verified": 32,
        "historical_compressed_bytes": 49_557_434,
        "historical_uncompressed_bytes": 3_765_430_651,
        "latest_links_verified": 32,
        "metadata_corrections_verified": 32,
        "mutable_drafts_found": 0,
        "new_versions_verified": 32,
        "operations_verified": 64,
        "registry_updates_verified": 32,
        "terminal_predecessor_query_artifacts": 32,
    }

    serialized = str(evidence)
    for forbidden in (
        "access_token",
        "bucket_url",
        "file://",
        "/Users/",
        "/deposit/",
        "/api/files/",
    ):
        assert forbidden not in serialized


def test_verified_archive_updates_are_the_runtime_registry_source() -> None:
    updates = archive_correction_registry_updates()

    assert len(updates) == 32
    assert len({item["model_id"] for item in updates}) == 32
    assert len({item["record_id"] for item in updates}) == 32
    assert len({item["version_doi"] for item in updates}) == 32
    for update in updates:
        model_id = str(update["model_id"])
        registry = model_registry_entry(model_id)
        catalogue = model_catalogue_entry(model_id)
        expected = {
            "archive_filename": update["filename"],
            "contains_embedded_licensing": True,
            "doi": update["concept_doi"],
            "record_id": update["record_id"],
            "release_version": update["release_version"],
            "sha256": update["sha256"],
            "size_bytes": update["size_bytes"],
            "uncompressed_sha256": update["uncompressed_sha256"],
            "uncompressed_size_bytes": update["uncompressed_size_bytes"],
            "url": update["url"],
            "version_doi": update["version_doi"],
        }
        assert all(registry[field] == value for field, value in expected.items())
        assert registry["filename"] == str(update["filename"]).removesuffix(".gz")
        assert catalogue["doi"] == update["concept_doi"]
        assert catalogue["record_id"] == update["record_id"]
        assert catalogue["version_doi"] == update["version_doi"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_id", "create-new-version:commandeered"),
        ("record_id", 21461537),
        ("version_doi", "10.5281/zenodo.1"),
        ("url", "https://zenodo.org/api/records/1/files/wrong.json.gz/content"),
    ],
)
def test_archive_correction_evidence_rejects_bound_field_drift(
    field: str, value: object
) -> None:
    evidence = deepcopy(load_archive_correction_evidence())
    evidence["models"][0]["corrected"][field] = value

    with pytest.raises(ValueError):
        validate_archive_correction_evidence(evidence)


def test_archive_correction_evidence_rejects_private_execution_state() -> None:
    evidence = deepcopy(load_archive_correction_evidence())
    evidence["execution_authority"]["new_package_version"] = (
        "file:///Users/example/private-candidate.json"
    )

    with pytest.raises(ValueError, match="private execution state"):
        validate_archive_correction_evidence(evidence)


def test_tracked_evidence_loader_rejects_byte_drift(tmp_path: Path) -> None:
    source = files("synthpopcan").joinpath("archive_correction_evidence_v1.json")
    changed = tmp_path / "changed.json"
    changed.write_bytes(source.read_bytes() + b" ")

    with pytest.raises(ValueError, match="evidence digest changed"):
        load_archive_correction_evidence(changed)


def test_archive_correction_evidence_binds_both_licensing_contracts() -> None:
    evidence = deepcopy(load_archive_correction_evidence())
    evidence["execution_authority"]["licensing_sha256_by_census_year"]["2021"] = (
        "0" * 64
    )

    with pytest.raises(ValueError, match="licensing digests changed"):
        validate_archive_correction_evidence(evidence)
