"""Shared orchestration for maintained public enrichment adapters."""

from __future__ import annotations

__all__ = [
    "ReferenceDatasetAdapter",
    "ReferenceEnrichmentArtifacts",
    "enrichment_cache_dir",
    "run_reference_enrichment",
]

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar, Protocol

from synthpopcan.enrichment import (
    ResourceRecord,
    SourceProfile,
    acquire_public_resource,
    import_normalized_layer,
    register_resource,
)
from synthpopcan.geography import GeographyUniverse


class ReferenceDatasetAdapter(Protocol):
    """Dataset-specific operations consumed by the shared public workflow."""

    @property
    def dataset_id(self) -> str: ...

    @property
    def resource_url(self) -> str: ...

    @property
    def expected_sha256(self) -> str: ...

    @property
    def layer_id(self) -> str: ...

    @property
    def layer_class(self) -> str: ...

    @property
    def layer_filename(self) -> str: ...

    key_columns: ClassVar[tuple[str, ...]]

    @property
    def variables(self) -> tuple[str, ...]: ...

    limitations: ClassVar[tuple[str, ...]]

    @property
    def requires_base_geography(self) -> bool: ...

    @property
    def max_download_bytes(self) -> int: ...

    def describe(self) -> SourceProfile:
        """Return the reviewed source profile for this adapter revision."""

        ...

    def normalize_archive(
        self,
        archive_path: Path,
        output_path: Path,
    ) -> Mapping[str, object]:
        """Normalize reviewed source bytes and return source validation."""

        ...

    def reproduction_parameters(self) -> Mapping[str, object]:
        """Return source-specific parameters needed to repeat normalization."""

        ...


@dataclass(frozen=True)
class ReferenceEnrichmentArtifacts:
    """Files and validation emitted by a maintained enrichment workflow."""

    layer: Path
    manifest: Path
    source_profile: Path
    resource_record: Path
    validation_report: Path
    validation: Mapping[str, object]


def enrichment_cache_dir() -> Path:
    """Return the user cache used for maintained public enrichment resources."""

    override = os.environ.get("SYNTHPOPCAN_ENRICHMENT_CACHE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "synthpopcan" / "enrichment"
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "synthpopcan" / "enrichment"


def run_reference_enrichment(
    population_directory: Path,
    output_directory: Path,
    adapter: ReferenceDatasetAdapter,
    *,
    resource_path: Path | None = None,
    cache_directory: Path | None = None,
    acquired_at: str | None = None,
    base_geography: GeographyUniverse | None = None,
) -> ReferenceEnrichmentArtifacts:
    """Acquire, normalize, validate, and publish one reviewed public adapter.

    Maintained adapters share bounded acquisition, immutable resource identity,
    linked-population preservation, sidecar publication, and durable validation.
    Dataset modules retain responsibility for source schemas and semantics.
    """

    if population_directory.resolve() == output_directory.resolve():
        raise ValueError(
            "enrichment output directory must differ from the base population directory"
        )
    source = adapter.describe()
    if adapter.requires_base_geography and base_geography is None:
        raise ValueError(f"{adapter.dataset_id} requires an explicit base geography")
    if (
        base_geography is not None
        and source.geography is not None
        and base_geography.canonical_key != source.geography.canonical_key
    ):
        raise ValueError(
            f"{adapter.dataset_id} requires "
            f"{source.geography.census_vintage} "
            f"{source.geography.geography_level.upper()} geography; received "
            f"{base_geography.census_vintage} "
            f"{base_geography.geography_level.upper()}"
        )

    timestamp = acquired_at or _utc_timestamp()
    _validate_acquired_at(timestamp)
    archive, resource = _resolve_resource(
        adapter,
        source,
        resource_path=resource_path,
        cache_directory=cache_directory,
        acquired_at=timestamp,
    )
    if resource.sha256 != adapter.expected_sha256:
        raise ValueError(
            f"{adapter.dataset_id} resource revision is not reviewed: expected "
            f"{adapter.expected_sha256}, observed {resource.sha256}"
        )

    with TemporaryDirectory(prefix="synthpopcan-enrichment-") as temporary:
        normalized_path = Path(temporary) / adapter.layer_filename
        source_validation = dict(adapter.normalize_archive(archive, normalized_path))
        if source_validation.get("passed") is not True:
            raise ValueError(f"{adapter.dataset_id} source validation failed")
        manifest, layer_validation = import_normalized_layer(
            population_directory,
            normalized_path,
            output_directory,
            source=source,
            resource=resource,
            layer_id=adapter.layer_id,
            layer_class=adapter.layer_class,
            key_columns=adapter.key_columns,
            variables=adapter.variables,
            base_geography=base_geography,
            observed_status="observed",
            reproduction_request={
                "workflow": "enrichment",
                "operation": "maintained-reference-adapter",
                "dataset_id": adapter.dataset_id,
                "source_version": source.source_version,
                "resource_url": adapter.resource_url,
                "resource_sha256": resource.sha256,
                "base_geography": (
                    base_geography.as_dict() if base_geography is not None else None
                ),
                "parameters": dict(adapter.reproduction_parameters()),
            },
            limitations=adapter.limitations,
            require_geography_match=adapter.requires_base_geography,
        )

    combined_validation: dict[str, object] = {
        "schema_version": "synthpopcan-reference-enrichment-validation-v1",
        "passed": bool(
            source_validation.get("passed") and layer_validation.get("passed")
        ),
        "dataset_id": adapter.dataset_id,
        "source_version": source.source_version,
        "resource_sha256": resource.sha256,
        "source_validation": source_validation,
        "layer_validation": layer_validation,
        "base_linkage": (
            "validated" if base_geography is not None else "not-requested"
        ),
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    source_path = output_directory / "source-profile.json"
    resource_path_out = output_directory / "resource-record.json"
    validation_path = output_directory / "validation.json"
    _write_json_atomic(source_path, source.as_dict())
    _write_json_atomic(resource_path_out, resource.as_dict())
    _write_json_atomic(validation_path, combined_validation)

    return ReferenceEnrichmentArtifacts(
        layer=output_directory / adapter.layer_filename,
        manifest=output_directory / "manifest.json",
        source_profile=source_path,
        resource_record=resource_path_out,
        validation_report=validation_path,
        validation=combined_validation,
    )


def _resolve_resource(
    adapter: ReferenceDatasetAdapter,
    source: SourceProfile,
    *,
    resource_path: Path | None,
    cache_directory: Path | None,
    acquired_at: str,
) -> tuple[Path, ResourceRecord]:
    if resource_path is None:
        cache_root = cache_directory or enrichment_cache_dir()
        cached_path = (
            cache_root
            / "objects"
            / adapter.expected_sha256[:2]
            / adapter.expected_sha256
        )
        if cached_path.is_file():
            cached_record = register_resource(
                cached_path,
                source,
                acquired_at=acquired_at,
                media_type="application/zip",
                public_locator=adapter.resource_url,
            )
            if cached_record.sha256 != adapter.expected_sha256:
                raise ValueError("content-addressed enrichment cache collision")
            return cached_path, cached_record
        return acquire_public_resource(
            source,
            cache_root,
            acquired_at=acquired_at,
            media_type="application/zip",
            resource_url=adapter.resource_url,
            max_bytes=adapter.max_download_bytes,
        )
    return resource_path, register_resource(
        resource_path,
        source,
        acquired_at=acquired_at,
        media_type="application/zip",
        public_locator=adapter.resource_url,
    )


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_acquired_at(value: str) -> None:
    if value != value.strip():
        raise ValueError("acquired_at must be a timezone-aware ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "acquired_at must be a timezone-aware ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("acquired_at must be a timezone-aware ISO 8601 timestamp")
