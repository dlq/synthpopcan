"""Tracked, sanitized evidence for the completed prepared-model correction."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

from synthpopcan.model_licensing import statcan_prepared_model_licensing

ARCHIVE_CORRECTION_EVIDENCE_SCHEMA = (
    "synthpopcan-prepared-model-archive-correction-evidence-v1"
)
ARCHIVE_CORRECTION_EVIDENCE_FILENAME = "archive_correction_evidence_v1.json"
ARCHIVE_CORRECTION_EVIDENCE_SHA256 = (
    "f4e8705daa006a1ef1523b3db8bf2c818fa76032d48a4488b0c0d9b2f954a47e"
)
PRODUCTION_ZENODO_API = "https://zenodo.org/api"

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_MODEL_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ASSET_FIELDS = {
    "filename",
    "size_bytes",
    "sha256",
    "uncompressed_size_bytes",
    "uncompressed_sha256",
}
_FORBIDDEN_EVIDENCE_TEXT = (
    "Authorization:",
    "Bearer ",
    "access_token",
    "bucket_url",
    "file://",
    "/Users/",
    "/deposit/",
    "/api/files/",
)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"archive correction evidence {label} must be an object")
    return value


def _exact_fields(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise ValueError(f"archive correction evidence {label} fields changed")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"archive correction evidence {label} must be text")
    return value


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(
            f"archive correction evidence {label} must be a positive integer"
        )
    return value


def _digest(value: object, label: str) -> str:
    digest = _string(value, label)
    if _DIGEST.fullmatch(digest) is None:
        raise ValueError(f"archive correction evidence {label} is not SHA-256")
    return digest


def _record_doi(record_id: int) -> str:
    return f"10.5281/zenodo.{record_id}"


def _asset(value: object, label: str) -> dict[str, Any]:
    asset = _object(value, label)
    _exact_fields(asset, _ASSET_FIELDS, label)
    filename = _string(asset.get("filename"), f"{label}.filename")
    if Path(filename).name != filename or not filename.endswith(".json.gz"):
        raise ValueError(f"archive correction evidence {label}.filename is unsafe")
    _positive_int(asset.get("size_bytes"), f"{label}.size_bytes")
    _digest(asset.get("sha256"), f"{label}.sha256")
    _positive_int(
        asset.get("uncompressed_size_bytes"),
        f"{label}.uncompressed_size_bytes",
    )
    _digest(
        asset.get("uncompressed_sha256"),
        f"{label}.uncompressed_sha256",
    )
    return asset


def _version(
    value: object,
    *,
    model_id: str,
    concept_doi: str,
    operation: str,
    new_package_version: str,
) -> dict[str, Any]:
    version = _object(value, f"{model_id}.{operation}")
    expected_fields = {
        "asset",
        "metadata_sha256",
        "operation_id",
        "package_version",
        "record_id",
        "version_doi",
    }
    if operation == "correct-existing-metadata":
        expected_fields.add("publication_date")
    else:
        expected_fields.add("url")
    _exact_fields(version, expected_fields, f"{model_id}.{operation}")

    asset = _asset(version.get("asset"), f"{model_id}.{operation}.asset")
    metadata_sha256 = _digest(
        version.get("metadata_sha256"),
        f"{model_id}.{operation}.metadata_sha256",
    )
    package_version = _string(
        version.get("package_version"),
        f"{model_id}.{operation}.package_version",
    )
    record_id = _positive_int(
        version.get("record_id"), f"{model_id}.{operation}.record_id"
    )
    if version.get("version_doi") != _record_doi(record_id):
        raise ValueError(
            f"archive correction evidence {model_id}.{operation} DOI is unbound"
        )
    expected_operation_id = ":".join(
        (
            operation,
            model_id,
            package_version,
            str(asset["sha256"]),
            metadata_sha256,
        )
    )
    if version.get("operation_id") != expected_operation_id:
        raise ValueError(
            f"archive correction evidence {model_id}.{operation} identity changed"
        )

    if operation == "correct-existing-metadata":
        publication_date = _string(
            version.get("publication_date"),
            f"{model_id}.{operation}.publication_date",
        )
        try:
            date.fromisoformat(publication_date)
        except ValueError as exc:
            raise ValueError(
                f"archive correction evidence {model_id} date is invalid"
            ) from exc
        if package_version == new_package_version:
            raise ValueError(
                f"archive correction evidence {model_id} lost its old version"
            )
    else:
        if package_version != new_package_version:
            raise ValueError(
                f"archive correction evidence {model_id} corrected version changed"
            )
        filename = str(asset["filename"])
        if new_package_version not in filename:
            raise ValueError(
                f"archive correction evidence {model_id} filename lacks its version"
            )
        expected_url = (
            f"{PRODUCTION_ZENODO_API}/records/{record_id}/files/{filename}/content"
        )
        if version.get("url") != expected_url:
            raise ValueError(
                f"archive correction evidence {model_id} download URL is unbound"
            )

    if not concept_doi.startswith("10.5281/zenodo."):
        raise ValueError(
            f"archive correction evidence {model_id} concept DOI is invalid"
        )
    return version


def validate_archive_correction_evidence(document: object) -> dict[str, Any]:
    """Validate the complete tracked archive transaction and return it."""

    evidence = _object(document, "document")
    _exact_fields(
        evidence,
        {
            "api",
            "execution_authority",
            "models",
            "recorded_on",
            "schema_version",
            "target",
            "verification",
        },
        "document",
    )
    if evidence.get("schema_version") != ARCHIVE_CORRECTION_EVIDENCE_SCHEMA:
        raise ValueError("unsupported archive correction evidence schema")
    if evidence.get("target") != "PRODUCTION" or evidence.get("api") != (
        PRODUCTION_ZENODO_API
    ):
        raise ValueError("archive correction evidence is not for production Zenodo")
    if evidence.get("recorded_on") != "2026-08-16":
        raise ValueError("archive correction evidence date changed")

    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    if any(fragment in serialized for fragment in _FORBIDDEN_EVIDENCE_TEXT):
        raise ValueError("archive correction evidence contains private execution state")

    authority = _object(evidence.get("execution_authority"), "authority")
    _exact_fields(
        authority,
        {
            "candidate_envelope_sha256",
            "execution_index_sha256",
            "executor_commit",
            "licensing_sha256_by_census_year",
            "new_package_version",
        },
        "authority",
    )
    _digest(
        authority.get("candidate_envelope_sha256"),
        "authority.candidate_envelope_sha256",
    )
    _digest(
        authority.get("execution_index_sha256"),
        "authority.execution_index_sha256",
    )
    executor_commit = _string(
        authority.get("executor_commit"), "authority.executor_commit"
    )
    if _COMMIT.fullmatch(executor_commit) is None:
        raise ValueError("archive correction evidence executor commit is invalid")
    licensing_digests = _object(
        authority.get("licensing_sha256_by_census_year"),
        "authority.licensing_sha256_by_census_year",
    )
    if licensing_digests != {
        "2016": "21dd4bfa0014dec4295e2b9155ee54382082d984a9cab775f0863d2c52219392",
        "2021": "efe68065a2f6ca9bb36ee3d5236743cff7e6f6be6edc75c1691a934324e814d8",
    }:
        raise ValueError("archive correction evidence licensing digests changed")
    current_licensing_digests = {
        str(year): hashlib.sha256(
            json.dumps(
                statcan_prepared_model_licensing(year),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        for year in (2016, 2021)
    }
    if licensing_digests != current_licensing_digests:
        raise ValueError(
            "archive correction evidence no longer matches package licensing"
        )
    new_package_version = _string(
        authority.get("new_package_version"), "authority.new_package_version"
    )

    models = evidence.get("models")
    if not isinstance(models, list) or len(models) != 32:
        raise ValueError("archive correction evidence requires exactly 32 models")
    model_ids: list[str] = []
    concept_dois: set[str] = set()
    historical_record_ids: set[int] = set()
    corrected_record_ids: set[int] = set()
    historical_assets: list[dict[str, Any]] = []
    corrected_assets: list[dict[str, Any]] = []
    for raw_model in models:
        model = _object(raw_model, "model")
        _exact_fields(
            model,
            {"concept_doi", "corrected", "historical", "model_id"},
            "model",
        )
        model_id = _string(model.get("model_id"), "model.model_id")
        if _MODEL_ID.fullmatch(model_id) is None:
            raise ValueError("archive correction evidence model ID is invalid")
        concept_doi = _string(model.get("concept_doi"), f"{model_id}.concept_doi")
        historical = _version(
            model.get("historical"),
            model_id=model_id,
            concept_doi=concept_doi,
            operation="correct-existing-metadata",
            new_package_version=new_package_version,
        )
        corrected = _version(
            model.get("corrected"),
            model_id=model_id,
            concept_doi=concept_doi,
            operation="create-new-version",
            new_package_version=new_package_version,
        )
        historical_record_id = int(historical["record_id"])
        corrected_record_id = int(corrected["record_id"])
        if historical_record_id == corrected_record_id:
            raise ValueError(
                f"archive correction evidence {model_id} overwrote its old version"
            )
        if historical["asset"]["filename"] == corrected["asset"]["filename"]:
            raise ValueError(
                f"archive correction evidence {model_id} reused its old filename"
            )
        model_ids.append(model_id)
        concept_dois.add(concept_doi)
        historical_record_ids.add(historical_record_id)
        corrected_record_ids.add(corrected_record_id)
        historical_assets.append(historical["asset"])
        corrected_assets.append(corrected["asset"])

    if model_ids != sorted(set(model_ids)) or len(concept_dois) != 32:
        raise ValueError("archive correction evidence model/concept coverage changed")
    if len(historical_record_ids) != 32 or len(corrected_record_ids) != 32:
        raise ValueError("archive correction evidence record identities are ambiguous")
    if historical_record_ids & corrected_record_ids:
        raise ValueError("archive correction evidence reused a historical record")

    expected_verification = {
        "candidate_assets_verified": 32,
        "candidate_compressed_bytes": sum(
            int(asset["size_bytes"]) for asset in corrected_assets
        ),
        "candidate_uncompressed_bytes": sum(
            int(asset["uncompressed_size_bytes"]) for asset in corrected_assets
        ),
        "concepts_verified": 32,
        "historical_assets_verified": 32,
        "historical_compressed_bytes": sum(
            int(asset["size_bytes"]) for asset in historical_assets
        ),
        "historical_uncompressed_bytes": sum(
            int(asset["uncompressed_size_bytes"]) for asset in historical_assets
        ),
        "latest_links_verified": 32,
        "metadata_corrections_verified": 32,
        "mutable_drafts_found": 0,
        "new_versions_verified": 32,
        "operations_verified": 64,
        "registry_updates_verified": 32,
        "terminal_predecessor_query_artifacts": 32,
    }
    if evidence.get("verification") != expected_verification:
        raise ValueError("archive correction verification totals changed")
    return evidence


def load_archive_correction_evidence(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load and validate tracked evidence without consulting local checkpoints."""

    if path is None:
        raw = (
            files("synthpopcan")
            .joinpath(ARCHIVE_CORRECTION_EVIDENCE_FILENAME)
            .read_bytes()
        )
    else:
        raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_CORRECTION_EVIDENCE_SHA256:
        raise ValueError("tracked archive correction evidence digest changed")
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("archive correction evidence is not valid JSON") from exc
    return validate_archive_correction_evidence(document)


def archive_correction_registry_updates(
    evidence: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Derive the exact 32 runtime registry updates from verified evidence."""

    document = validate_archive_correction_evidence(
        evidence if evidence is not None else load_archive_correction_evidence()
    )
    updates: list[dict[str, Any]] = []
    for model in document["models"]:
        corrected = model["corrected"]
        asset = corrected["asset"]
        updates.append(
            {
                "concept_doi": model["concept_doi"],
                "filename": asset["filename"],
                "model_id": model["model_id"],
                "record_id": corrected["record_id"],
                "release_version": corrected["package_version"],
                "sha256": asset["sha256"],
                "size_bytes": asset["size_bytes"],
                "uncompressed_sha256": asset["uncompressed_sha256"],
                "uncompressed_size_bytes": asset["uncompressed_size_bytes"],
                "url": corrected["url"],
                "version_doi": corrected["version_doi"],
            }
        )
    return updates
