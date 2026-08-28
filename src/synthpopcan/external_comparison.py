"""Pinned external-comparison descriptors, fixtures, and cache handling."""

from __future__ import annotations

__all__ = [
    "EXTERNAL_COMPARISON_SCHEMA_VERSION",
    "read_external_comparison_descriptor",
    "resolve_external_comparison_archive",
    "validate_external_comparison_fixture",
]

import csv
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

EXTERNAL_COMPARISON_SCHEMA_VERSION = "synthpopcan-external-comparison-v1"
_HEX_DIGITS = frozenset("0123456789abcdef")


def read_external_comparison_descriptor(path: Path) -> dict[str, Any]:
    """Read and strictly validate a pinned external-comparison descriptor."""

    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"could not read external comparison descriptor: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("external comparison descriptor must be a JSON object")
    if payload.get("schema_version") != EXTERNAL_COMPARISON_SCHEMA_VERSION:
        raise ValueError("unsupported external comparison descriptor schema")
    for key in (
        "comparison_id",
        "title",
        "source",
        "resource",
        "download_policy",
        "fixture",
    ):
        if key not in payload:
            raise ValueError(f"external comparison descriptor requires {key!r}")
    source = _required_mapping(payload, "source")
    resource = _required_mapping(payload, "resource")
    policy = _required_mapping(payload, "download_policy")
    fixture = _required_mapping(payload, "fixture")
    for key in ("doi", "version", "license", "record_url"):
        _require_text(source.get(key), f"source {key}")
    filename = _safe_filename(resource.get("filename"))
    _require_https(resource.get("url"), "resource URL")
    size = _positive_integer(resource.get("byte_size"), "resource byte_size")
    algorithm, digest = _parse_checksum(resource.get("checksum"))
    if policy.get("default") != "disabled":
        raise ValueError("external comparison downloads must be disabled by default")
    if policy.get("explicit_opt_in_required") is not True:
        raise ValueError("external comparison download must require explicit opt-in")
    if policy.get("cache_outside_git") is not True:
        raise ValueError("external comparison resources must remain outside git")
    maximum = _positive_integer(policy.get("maximum_bytes"), "maximum_bytes")
    if maximum < size:
        raise ValueError("download maximum_bytes is smaller than the pinned resource")
    if fixture.get("contains_external_records") is not False:
        raise ValueError("the committed fixture must not contain external records")
    fixture_path = _safe_relative_path(fixture.get("path"), "fixture path")
    fixture_algorithm, fixture_digest = _parse_checksum(fixture.get("checksum"))
    if fixture_algorithm != "sha256":
        raise ValueError("the committed fixture requires a SHA-256 checksum")
    empirical_payload = payload.get("empirical_aggregate_evidence")
    empirical: dict[str, Any] | None = None
    if empirical_payload is not None:
        if not isinstance(empirical_payload, dict):
            raise ValueError("empirical_aggregate_evidence must be an object")
        empirical_path = _safe_relative_path(
            empirical_payload.get("path"), "empirical aggregate evidence path"
        )
        empirical_algorithm, empirical_digest = _parse_checksum(
            empirical_payload.get("checksum")
        )
        if empirical_algorithm != "sha256":
            raise ValueError("empirical aggregate evidence requires SHA-256")
        if empirical_payload.get("contains_external_records") is not False:
            raise ValueError("empirical evidence must not contain external rows")
        if empirical_payload.get("aggregate_only") is not True:
            raise ValueError("empirical evidence must be aggregate-only")
        empirical = {
            **empirical_payload,
            "path": str(empirical_path),
            "checksum": f"{empirical_algorithm}:{empirical_digest}",
        }
    return {
        **payload,
        "resource": {
            **resource,
            "filename": filename,
            "byte_size": size,
            "checksum": f"{algorithm}:{digest}",
        },
        "download_policy": {**policy, "maximum_bytes": maximum},
        "fixture": {
            **fixture,
            "path": str(fixture_path),
            "checksum": f"{fixture_algorithm}:{fixture_digest}",
        },
        **(
            {"empirical_aggregate_evidence": empirical} if empirical is not None else {}
        ),
    }


def validate_external_comparison_fixture(descriptor_path: Path) -> dict[str, Any]:
    """Verify the committed schema-only fixture without network access."""

    descriptor = read_external_comparison_descriptor(descriptor_path)
    fixture = descriptor["fixture"]
    fixture_path = (descriptor_path.parent / fixture["path"]).resolve()
    root = descriptor_path.parent.resolve()
    if not fixture_path.is_relative_to(root):
        raise ValueError("external comparison fixture escapes its descriptor directory")
    if not fixture_path.is_file():
        raise ValueError("external comparison fixture is missing")
    actual_checksum = f"sha256:{_file_digest(fixture_path, 'sha256')}"
    if actual_checksum != fixture["checksum"]:
        raise ValueError("external comparison fixture checksum does not match")
    with fixture_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []
    expected_columns = descriptor.get("schema_crosswalk", {}).get("external_fields")
    if not isinstance(expected_columns, list) or not all(
        isinstance(column, str) and column for column in expected_columns
    ):
        raise ValueError("schema_crosswalk.external_fields must be a string list")
    missing = sorted(set(expected_columns) - set(columns))
    if missing:
        raise ValueError(
            "external comparison fixture is missing fields: " + ", ".join(missing)
        )
    empirical_result: dict[str, Any] | None = None
    empirical = descriptor.get("empirical_aggregate_evidence")
    if isinstance(empirical, dict):
        empirical_path = (descriptor_path.parent / empirical["path"]).resolve()
        if not empirical_path.is_relative_to(root):
            raise ValueError("empirical aggregate evidence escapes its directory")
        if not empirical_path.is_file():
            raise ValueError("empirical aggregate evidence is missing")
        actual_empirical_checksum = f"sha256:{_file_digest(empirical_path, 'sha256')}"
        if actual_empirical_checksum != empirical["checksum"]:
            raise ValueError("empirical aggregate evidence checksum does not match")
        try:
            empirical_payload = json.loads(empirical_path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"could not read empirical aggregate evidence: {exc}"
            ) from exc
        if (
            not isinstance(empirical_payload, dict)
            or empirical_payload.get("schema_version")
            != "synthpopcan-external-aggregate-comparison-v1"
        ):
            raise ValueError("unsupported empirical aggregate evidence schema")
        safety = empirical_payload.get("public_safety")
        if not isinstance(safety, dict) or safety.get("aggregate_only") is not True:
            raise ValueError("empirical evidence lacks aggregate-only safety metadata")
        if safety.get("contains_source_rows") is not False:
            raise ValueError("empirical evidence may not contain source rows")
        empirical_result = {
            "path": str(empirical_path),
            "checksum": actual_empirical_checksum,
            "schema_version": empirical_payload["schema_version"],
            "aggregate_only": True,
        }
    return {
        "schema_version": EXTERNAL_COMPARISON_SCHEMA_VERSION,
        "passed": True,
        "comparison_id": descriptor["comparison_id"],
        "network_accessed": False,
        "contains_external_records": False,
        "fixture_path": str(fixture_path),
        "fixture_checksum": actual_checksum,
        "rows": len(rows),
        "columns": columns,
        "empirical_aggregate_evidence": empirical_result,
    }


def resolve_external_comparison_archive(
    descriptor_path: Path,
    cache_dir: Path,
    *,
    allow_download: bool = False,
    downloader: Callable[[str, Path, int], None] | None = None,
) -> Path:
    """Return a verified cached archive, downloading only after explicit opt-in.

    The caller must provide ``downloader`` when enabling a transfer.  This
    deliberate boundary prevents the 9.6 GB reference archive from being
    fetched accidentally by tests or an ordinary library import.
    """

    descriptor = read_external_comparison_descriptor(descriptor_path)
    resource = descriptor["resource"]
    destination = cache_dir / resource["filename"]
    if destination.is_file():
        _verify_pinned_resource(destination, resource)
        return destination
    if not allow_download:
        raise FileNotFoundError(
            "external comparison archive is not cached; downloading is opt-in"
        )
    if downloader is None:
        raise ValueError(
            "an explicit downloader is required for external comparison data"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.download")
    if temporary.exists():
        raise ValueError("external comparison temporary download already exists")
    try:
        downloader(
            str(resource["url"]),
            temporary,
            int(descriptor["download_policy"]["maximum_bytes"]),
        )
        _verify_pinned_resource(temporary, resource)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _verify_pinned_resource(path: Path, resource: Mapping[str, Any]) -> None:
    expected_size = int(resource["byte_size"])
    if path.stat().st_size != expected_size:
        raise ValueError("external comparison archive byte size does not match")
    algorithm, expected = _parse_checksum(resource["checksum"])
    if _file_digest(path, algorithm) != expected:
        raise ValueError("external comparison archive checksum does not match")


def _file_digest(path: Path, algorithm: str) -> str:
    digest = (
        hashlib.md5(usedforsecurity=False) if algorithm == "md5" else hashlib.sha256()
    )
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_checksum(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or ":" not in value:
        raise ValueError("checksum must include its algorithm")
    algorithm, digest = value.split(":", 1)
    expected_length = {"md5": 32, "sha256": 64}.get(algorithm)
    if (
        expected_length is None
        or len(digest) != expected_length
        or not set(digest) <= _HEX_DIGITS
    ):
        raise ValueError("checksum must be a lowercase MD5 or SHA-256 digest")
    return algorithm, digest


def _safe_filename(value: object) -> str:
    _require_text(value, "resource filename")
    assert isinstance(value, str)
    if Path(value).name != value or value in {".", ".."}:
        raise ValueError("resource filename must be a plain filename")
    return value


def _safe_relative_path(value: object, label: str) -> Path:
    _require_text(value, label)
    assert isinstance(value, str)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must remain below the descriptor directory")
    return path


def _require_https(value: object, label: str) -> None:
    _require_text(value, label)
    assert isinstance(value, str)
    if not value.startswith("https://"):
        raise ValueError(f"{label} must use HTTPS")


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"external comparison descriptor requires object {key!r}")
    return value


def _require_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
