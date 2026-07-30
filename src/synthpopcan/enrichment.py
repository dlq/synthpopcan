"""Versioned, source-independent external-data enrichment contracts."""

from __future__ import annotations

__all__ = [
    "ENRICHMENT_MANIFEST_SCHEMA_VERSION",
    "RESOURCE_RECORD_SCHEMA_VERSION",
    "SOURCE_PROFILE_SCHEMA_VERSION",
    "EnrichmentLayer",
    "EnrichmentManifest",
    "ResourceRecord",
    "SourceAdapter",
    "SourceProfile",
    "acquire_public_resource",
    "build_enrichment_layer",
    "build_enrichment_manifest",
    "import_normalized_layer",
    "read_enrichment_manifest",
    "read_resource_record",
    "read_source_profile",
    "register_resource",
    "validate_normalized_layer",
    "verify_enrichment_manifest",
    "write_enrichment_manifest",
]

import csv
import hashlib
import json
import os
import re
import secrets
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from synthpopcan.geography import GeographyUniverse

SOURCE_PROFILE_SCHEMA_VERSION = "synthpopcan-source-profile-v1"
RESOURCE_RECORD_SCHEMA_VERSION = "synthpopcan-resource-record-v1"
ENRICHMENT_MANIFEST_SCHEMA_VERSION = "synthpopcan-enrichment-manifest-v1"
_LAYER_SCHEMA_VERSION = "synthpopcan-enrichment-layer-v1"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_STABLE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_ACQUISITION_MODES = frozenset(
    {"public-download", "public-api", "local-provided", "licensed", "restricted"}
)
_ACCESS_CLASSES = frozenset({"public", "local", "licensed", "restricted"})
_RESOURCE_STATUSES = frozenset({"current", "superseded", "withdrawn", "rejected"})
_LAYER_CLASSES = frozenset(
    {
        "area-attributes",
        "facilities-points",
        "household-person",
        "networks-activities-relationships",
    }
)


@dataclass(frozen=True)
class SourceProfile:
    """Dataset identity, authority, semantics, access, and stewardship metadata."""

    source_id: str
    publisher_id: str
    titles: Mapping[str, str]
    descriptions: Mapping[str, str]
    canonical_url: str
    acquisition_mode: str
    authority: str
    licence_id: str
    source_version: str
    publication_date: str
    observation_period: Mapping[str, str]
    unit_of_observation: str
    access_classification: str
    redistribution_status: str
    geography: GeographyUniverse | None = None
    translation_provenance: Mapping[str, str] | None = None
    known_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_stable_id(self.source_id, "source_id")
        _validate_stable_id(self.publisher_id, "publisher_id")
        _validate_language_map(self.titles, "titles")
        _validate_language_map(self.descriptions, "descriptions")
        for value, label in (
            (self.canonical_url, "canonical_url"),
            (self.authority, "authority"),
            (self.licence_id, "licence_id"),
            (self.source_version, "source_version"),
            (self.publication_date, "publication_date"),
            (self.unit_of_observation, "unit_of_observation"),
            (self.redistribution_status, "redistribution_status"),
        ):
            _validate_text(value, label)
        if self.acquisition_mode not in _ACQUISITION_MODES:
            raise ValueError("unsupported acquisition_mode")
        if self.access_classification not in _ACCESS_CLASSES:
            raise ValueError("unsupported access_classification")
        if (
            self.acquisition_mode in {"public-download", "public-api"}
            and self.access_classification != "public"
        ):
            raise ValueError("public acquisition requires public access classification")
        if (
            self.acquisition_mode in {"licensed", "restricted"}
            and self.access_classification != self.acquisition_mode
        ):
            raise ValueError(
                f"{self.acquisition_mode} acquisition requires matching access "
                "classification"
            )
        _validate_string_mapping(self.observation_period, "observation_period")
        if self.translation_provenance is not None:
            _validate_string_mapping(
                self.translation_provenance,
                "translation_provenance",
            )
        for limitation in self.known_limitations:
            _validate_text(limitation, "known limitation")

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": SOURCE_PROFILE_SCHEMA_VERSION,
            "source_id": self.source_id,
            "publisher_id": self.publisher_id,
            "titles": dict(self.titles),
            "descriptions": dict(self.descriptions),
            "canonical_url": self.canonical_url,
            "acquisition_mode": self.acquisition_mode,
            "authority": self.authority,
            "licence_id": self.licence_id,
            "source_version": self.source_version,
            "publication_date": self.publication_date,
            "observation_period": dict(self.observation_period),
            "unit_of_observation": self.unit_of_observation,
            "access_classification": self.access_classification,
            "redistribution_status": self.redistribution_status,
            "geography": self.geography.as_dict() if self.geography else None,
            "translation_provenance": (
                dict(self.translation_provenance)
                if self.translation_provenance is not None
                else None
            ),
            "known_limitations": list(self.known_limitations),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> SourceProfile:
        """Parse and validate a versioned source profile."""
        if payload.get("schema_version") != SOURCE_PROFILE_SCHEMA_VERSION:
            raise ValueError("unsupported source profile schema")
        geography_payload = payload.get("geography")
        geography = (
            GeographyUniverse.from_dict(_mapping(geography_payload, "geography"))
            if geography_payload is not None
            else None
        )
        translation = payload.get("translation_provenance")
        limitations = payload.get("known_limitations", [])
        if not isinstance(limitations, list) or not all(
            isinstance(value, str) for value in limitations
        ):
            raise ValueError("known_limitations must be a list of strings")
        return cls(
            source_id=_text(payload, "source_id"),
            publisher_id=_text(payload, "publisher_id"),
            titles=_string_mapping(payload, "titles"),
            descriptions=_string_mapping(payload, "descriptions"),
            canonical_url=_text(payload, "canonical_url"),
            acquisition_mode=_text(payload, "acquisition_mode"),
            authority=_text(payload, "authority"),
            licence_id=_text(payload, "licence_id"),
            source_version=_text(payload, "source_version"),
            publication_date=_text(payload, "publication_date"),
            observation_period=_string_mapping(payload, "observation_period"),
            unit_of_observation=_text(payload, "unit_of_observation"),
            access_classification=_text(payload, "access_classification"),
            redistribution_status=_text(payload, "redistribution_status"),
            geography=geography,
            translation_provenance=(
                _string_mapping(payload, "translation_provenance")
                if translation is not None
                else None
            ),
            known_limitations=tuple(limitations),
        )


@dataclass(frozen=True)
class ResourceRecord:
    """Immutable identity and integrity metadata for one source revision."""

    resource_id: str
    source_id: str
    source_version: str
    acquisition_mode: str
    acquired_at: str
    media_type: str
    byte_size: int
    sha256: str
    status: str = "current"
    public_locator: str | None = None
    opaque_local_id: str | None = None
    publisher_checksum: str | None = None
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_stable_id(self.resource_id, "resource_id")
        _validate_stable_id(self.source_id, "source_id")
        for value, label in (
            (self.source_version, "source_version"),
            (self.acquired_at, "acquired_at"),
            (self.media_type, "media_type"),
        ):
            _validate_text(value, label)
        if self.acquisition_mode not in _ACQUISITION_MODES:
            raise ValueError("unsupported acquisition_mode")
        if (
            not isinstance(self.byte_size, int)
            or isinstance(self.byte_size, bool)
            or self.byte_size < 0
        ):
            raise ValueError("byte_size must be a non-negative integer")
        _validate_sha256(self.sha256, "sha256")
        if self.status not in _RESOURCE_STATUSES:
            raise ValueError("unsupported resource status")
        if self.public_locator is not None:
            _validate_text(self.public_locator, "public_locator")
        if (
            self.acquisition_mode in {"public-download", "public-api"}
            and self.public_locator is None
        ):
            raise ValueError("public resource records require public_locator")
        if self.acquisition_mode in {"local-provided", "licensed", "restricted"}:
            if self.public_locator is not None:
                raise ValueError(
                    "non-public resource records cannot expose a public locator"
                )
            if self.opaque_local_id is None:
                raise ValueError("non-public resource records require opaque_local_id")
        if self.opaque_local_id is not None:
            _validate_stable_id(self.opaque_local_id, "opaque_local_id")
        if self.publisher_checksum is not None:
            _validate_text(self.publisher_checksum, "publisher_checksum")
        for resource_id in self.derived_from:
            _validate_stable_id(resource_id, "derived_from resource ID")

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": RESOURCE_RECORD_SCHEMA_VERSION,
            "resource_id": self.resource_id,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "acquisition_mode": self.acquisition_mode,
            "acquired_at": self.acquired_at,
            "media_type": self.media_type,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "status": self.status,
            "public_locator": self.public_locator,
            "opaque_local_id": self.opaque_local_id,
            "publisher_checksum": self.publisher_checksum,
            "derived_from": list(self.derived_from),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ResourceRecord:
        """Parse and validate a versioned resource record."""
        if payload.get("schema_version") != RESOURCE_RECORD_SCHEMA_VERSION:
            raise ValueError("unsupported resource record schema")
        byte_size = payload.get("byte_size")
        if not isinstance(byte_size, int) or isinstance(byte_size, bool):
            raise ValueError("byte_size must be an integer")
        derived_from = payload.get("derived_from", [])
        if not isinstance(derived_from, list) or not all(
            isinstance(value, str) for value in derived_from
        ):
            raise ValueError("derived_from must be a list of resource IDs")
        return cls(
            resource_id=_text(payload, "resource_id"),
            source_id=_text(payload, "source_id"),
            source_version=_text(payload, "source_version"),
            acquisition_mode=_text(payload, "acquisition_mode"),
            acquired_at=_text(payload, "acquired_at"),
            media_type=_text(payload, "media_type"),
            byte_size=byte_size,
            sha256=_text(payload, "sha256"),
            status=_text(payload, "status"),
            public_locator=_optional_text(payload, "public_locator"),
            opaque_local_id=_optional_text(payload, "opaque_local_id"),
            publisher_checksum=_optional_text(payload, "publisher_checksum"),
            derived_from=tuple(derived_from),
        )


@dataclass(frozen=True)
class EnrichmentLayer:
    """One normalized sidecar layer linked without widening the base tables."""

    layer_id: str
    layer_class: str
    table_path: str
    sha256: str
    row_count: int
    key_columns: tuple[str, ...]
    variables: tuple[str, ...]
    source_id: str
    resource_id: str
    observed_status: str
    geography: GeographyUniverse | None = None

    def __post_init__(self) -> None:
        _validate_stable_id(self.layer_id, "layer_id")
        if self.layer_class not in _LAYER_CLASSES:
            raise ValueError("unsupported enrichment layer class")
        if Path(self.table_path).name != self.table_path:
            raise ValueError("layer table_path must be a filename")
        _validate_sha256(self.sha256, "layer sha256")
        if (
            not isinstance(self.row_count, int)
            or isinstance(self.row_count, bool)
            or self.row_count < 0
        ):
            raise ValueError("layer row_count must be non-negative")
        _validate_columns(self.key_columns, "key_columns")
        _validate_columns(self.variables, "variables", allow_empty=True)
        if set(self.key_columns) & set(self.variables):
            raise ValueError("layer keys and variables must be distinct")
        _validate_stable_id(self.source_id, "source_id")
        _validate_stable_id(self.resource_id, "resource_id")
        if self.observed_status not in {"observed", "derived", "modeled"}:
            raise ValueError("unsupported observed_status")

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": _LAYER_SCHEMA_VERSION,
            "layer_id": self.layer_id,
            "layer_class": self.layer_class,
            "table_path": self.table_path,
            "media_type": "text/csv",
            "sha256": self.sha256,
            "row_count": self.row_count,
            "key_columns": list(self.key_columns),
            "variables": list(self.variables),
            "source_id": self.source_id,
            "resource_id": self.resource_id,
            "observed_status": self.observed_status,
            "geography": self.geography.as_dict() if self.geography else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> EnrichmentLayer:
        """Parse and validate a versioned layer descriptor."""
        if payload.get("schema_version") != _LAYER_SCHEMA_VERSION:
            raise ValueError("unsupported enrichment layer schema")
        if payload.get("media_type") != "text/csv":
            raise ValueError("enrichment layer v1 requires CSV")
        geography_payload = payload.get("geography")
        row_count = payload.get("row_count")
        if not isinstance(row_count, int) or isinstance(row_count, bool):
            raise ValueError("row_count must be an integer")
        return cls(
            layer_id=_text(payload, "layer_id"),
            layer_class=_text(payload, "layer_class"),
            table_path=_text(payload, "table_path"),
            sha256=_text(payload, "sha256"),
            row_count=row_count,
            key_columns=_string_tuple(payload, "key_columns"),
            variables=_string_tuple(payload, "variables"),
            source_id=_text(payload, "source_id"),
            resource_id=_text(payload, "resource_id"),
            observed_status=_text(payload, "observed_status"),
            geography=(
                GeographyUniverse.from_dict(
                    _mapping(geography_payload, "layer geography")
                )
                if geography_payload is not None
                else None
            ),
        )


@dataclass(frozen=True)
class EnrichmentManifest:
    """Composition record for immutable base tables and sidecar layers."""

    base_population: Mapping[str, object]
    sources: tuple[SourceProfile, ...]
    resources: tuple[ResourceRecord, ...]
    layers: tuple[EnrichmentLayer, ...]
    reproduction_request: Mapping[str, object]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_base_population(self.base_population)
        source_ids = [source.source_id for source in self.sources]
        resource_ids = [resource.resource_id for resource in self.resources]
        layer_ids = [layer.layer_id for layer in self.layers]
        for values, label in (
            (source_ids, "source IDs"),
            (resource_ids, "resource IDs"),
            (layer_ids, "layer IDs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"enrichment manifest has duplicate {label}")
        sources = set(source_ids)
        resources = {resource.resource_id: resource for resource in self.resources}
        for resource in self.resources:
            if resource.source_id not in sources:
                raise ValueError("resource record refers to an unknown source")
        for layer in self.layers:
            if layer.source_id not in sources:
                raise ValueError("enrichment layer refers to an unknown source")
            resource = resources.get(layer.resource_id)
            if resource is None or resource.source_id != layer.source_id:
                raise ValueError("enrichment layer resource lineage is invalid")
        if not isinstance(self.reproduction_request, Mapping):
            raise ValueError("reproduction_request must be an object")
        for limitation in self.limitations:
            _validate_text(limitation, "limitation")

    def as_dict(self) -> dict[str, object]:
        """Return the versioned JSON representation."""
        return {
            "schema_version": ENRICHMENT_MANIFEST_SCHEMA_VERSION,
            "base_population": dict(self.base_population),
            "sources": [source.as_dict() for source in self.sources],
            "resources": [resource.as_dict() for resource in self.resources],
            "layers": [layer.as_dict() for layer in self.layers],
            "reproduction_request": dict(self.reproduction_request),
            "limitations": list(self.limitations),
            "base_population_mutated": False,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> EnrichmentManifest:
        """Parse and validate a versioned enrichment manifest."""
        if payload.get("schema_version") != ENRICHMENT_MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported enrichment manifest schema")
        if payload.get("base_population_mutated") is not False:
            raise ValueError("enrichment manifest must not mutate the base population")
        return cls(
            base_population=_mapping(
                payload.get("base_population"),
                "base_population",
            ),
            sources=tuple(
                SourceProfile.from_dict(item)
                for item in _mapping_sequence(payload, "sources")
            ),
            resources=tuple(
                ResourceRecord.from_dict(item)
                for item in _mapping_sequence(payload, "resources")
            ),
            layers=tuple(
                EnrichmentLayer.from_dict(item)
                for item in _mapping_sequence(payload, "layers")
            ),
            reproduction_request=_mapping(
                payload.get("reproduction_request"),
                "reproduction_request",
            ),
            limitations=_string_tuple(payload, "limitations"),
        )


class SourceAdapter(Protocol):
    """Common workflow stages implemented by maintained source-specific adapters."""

    def describe(self) -> SourceProfile: ...

    def acquire_or_reference(self) -> ResourceRecord: ...

    def normalize(self, resource: ResourceRecord, output_path: Path) -> Path: ...

    def link(
        self,
        normalized_path: Path,
        population_directory: Path,
        output_path: Path,
    ) -> Path: ...

    def validate(self, layer_path: Path) -> Mapping[str, object]: ...

    def publish_or_retain(
        self,
        layer_path: Path,
        output_directory: Path,
    ) -> Mapping[str, object]: ...


def acquire_public_resource(
    source: SourceProfile,
    cache_root: Path,
    *,
    acquired_at: str,
    media_type: str,
    resource_url: str | None = None,
    max_bytes: int = 512 * 1024 * 1024,
    timeout: float = 60.0,
    publisher_sha256: str | None = None,
) -> tuple[Path, ResourceRecord]:
    """Retrieve one public HTTPS resource into an immutable addressed cache."""
    if source.acquisition_mode not in {"public-download", "public-api"}:
        raise ValueError("only public acquisition modes may retrieve a URL")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    url = resource_url or source.canonical_url
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("public resource retrieval requires an HTTPS URL")
    if publisher_sha256 is not None:
        _validate_sha256(publisher_sha256, "publisher_sha256")

    cache_root.mkdir(parents=True, exist_ok=True)
    temporary = cache_root / f".resource-{secrets.token_hex(12)}.part"
    digest = hashlib.sha256()
    byte_size = 0
    request = Request(url, headers={"User-Agent": "SynthPopCan/0.7"})
    try:
        with urlopen(request, timeout=timeout) as response, temporary.open("xb") as out:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > max_bytes:
                raise ValueError("public resource exceeds the configured size limit")
            while chunk := response.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > max_bytes:
                    raise ValueError(
                        "public resource exceeds the configured size limit"
                    )
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if byte_size == 0:
            raise ValueError("public resource is empty")
        observed_sha256 = digest.hexdigest()
        if publisher_sha256 is not None and observed_sha256 != publisher_sha256:
            raise ValueError("public resource does not match publisher_sha256")
        destination = cache_root / "objects" / observed_sha256[:2] / observed_sha256
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing_sha256, existing_size = _file_digest(destination)
            if (existing_sha256, existing_size) != (observed_sha256, byte_size):
                raise ValueError("content-addressed cache collision")
            temporary.unlink()
        else:
            os.replace(temporary, destination)
        return (
            destination,
            ResourceRecord(
                resource_id=f"resource:{observed_sha256}",
                source_id=source.source_id,
                source_version=source.source_version,
                acquisition_mode=source.acquisition_mode,
                acquired_at=acquired_at,
                media_type=media_type,
                byte_size=byte_size,
                sha256=observed_sha256,
                public_locator=url,
                publisher_checksum=(
                    f"sha256:{publisher_sha256}"
                    if publisher_sha256 is not None
                    else None
                ),
            ),
        )
    finally:
        temporary.unlink(missing_ok=True)


def register_resource(
    path: Path,
    source: SourceProfile,
    *,
    acquired_at: str,
    media_type: str,
    public_locator: str | None = None,
    opaque_local_id: str | None = None,
    status: str = "current",
    publisher_checksum: str | None = None,
    derived_from: Sequence[str] = (),
) -> ResourceRecord:
    """Hash a resource and create a path-safe immutable revision record."""
    digest, byte_size = _file_digest(path)
    if source.acquisition_mode in {"local-provided", "licensed", "restricted"}:
        public_locator = None
        opaque_local_id = opaque_local_id or f"local:{digest[:24]}"
    return ResourceRecord(
        resource_id=f"resource:{digest}",
        source_id=source.source_id,
        source_version=source.source_version,
        acquisition_mode=source.acquisition_mode,
        acquired_at=acquired_at,
        media_type=media_type,
        byte_size=byte_size,
        sha256=digest,
        status=status,
        public_locator=public_locator,
        opaque_local_id=opaque_local_id,
        publisher_checksum=publisher_checksum,
        derived_from=tuple(derived_from),
    )


def validate_normalized_layer(
    path: Path,
    layer: EnrichmentLayer,
    *,
    base_geography: GeographyUniverse | None = None,
    base_identifiers: Sequence[str] = (),
) -> dict[str, object]:
    """Validate normalized CSV structure, keys, lineage, and geography coverage."""
    digest, _ = _file_digest(path)
    issues: list[dict[str, object]] = []
    if digest != layer.sha256:
        issues.append({"code": "checksum-mismatch"})
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        required = [*layer.key_columns, *layer.variables]
        missing = [column for column in required if column not in columns]
        if missing:
            issues.append({"code": "missing-columns", "columns": missing})
        rows = list(reader)
    if len(rows) != layer.row_count:
        issues.append(
            {
                "code": "row-count-mismatch",
                "expected": layer.row_count,
                "observed": len(rows),
            }
        )
    keys: set[tuple[str, ...]] = set()
    duplicate_keys: list[list[str]] = []
    for row in rows:
        key = tuple(row.get(column, "") for column in layer.key_columns)
        if any(not value for value in key):
            issues.append({"code": "missing-key", "key": list(key)})
        elif key in keys:
            duplicate_keys.append(list(key))
        keys.add(key)
    if duplicate_keys:
        issues.append({"code": "duplicate-keys", "keys": duplicate_keys})

    unmatched_layer: list[str] = []
    unmatched_base: list[str] = []
    if base_geography is not None:
        if layer.geography is None:
            issues.append({"code": "missing-geography-context"})
        elif layer.geography.canonical_key != base_geography.canonical_key:
            issues.append(
                {
                    "code": "incompatible-geography-universe",
                    "base": list(base_geography.canonical_key),
                    "layer": list(layer.geography.canonical_key),
                }
            )
        elif layer.geography.identifier_column in columns:
            source_ids = {
                row[layer.geography.identifier_column]
                for row in rows
                if row.get(layer.geography.identifier_column)
            }
            base_ids = set(base_identifiers)
            unmatched_layer = sorted(source_ids - base_ids)
            unmatched_base = sorted(base_ids - source_ids)
    return {
        "schema_version": "synthpopcan-enrichment-validation-v1",
        "passed": not issues,
        "layer_id": layer.layer_id,
        "rows": len(rows),
        "duplicate_key_count": len(duplicate_keys),
        "unmatched_layer_identifiers": unmatched_layer,
        "unmatched_base_identifiers": unmatched_base,
        "issues": issues,
    }


def build_enrichment_layer(
    path: Path,
    *,
    layer_id: str,
    layer_class: str,
    key_columns: Sequence[str],
    variables: Sequence[str],
    source: SourceProfile,
    resource: ResourceRecord,
    observed_status: str,
    geography: GeographyUniverse | None = None,
    table_name: str | None = None,
) -> EnrichmentLayer:
    """Describe one normalized CSV sidecar using observed bytes and row count."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        columns = next(reader, [])
        row_count = sum(1 for _ in reader)
    if not columns:
        raise ValueError("normalized enrichment layer is empty")
    required = [*key_columns, *variables]
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(
            "normalized enrichment layer is missing columns: " + ", ".join(missing)
        )
    if resource.source_id != source.source_id:
        raise ValueError("resource and source profile do not share source_id")
    sha256, _ = _file_digest(path)
    return EnrichmentLayer(
        layer_id=layer_id,
        layer_class=layer_class,
        table_path=table_name or path.name,
        sha256=sha256,
        row_count=row_count,
        key_columns=tuple(key_columns),
        variables=tuple(variables),
        source_id=source.source_id,
        resource_id=resource.resource_id,
        observed_status=observed_status,
        geography=geography,
    )


def import_normalized_layer(
    population_directory: Path,
    layer_path: Path,
    output_directory: Path,
    *,
    source: SourceProfile,
    resource: ResourceRecord,
    layer_id: str,
    layer_class: str,
    key_columns: Sequence[str],
    variables: Sequence[str],
    base_geography: GeographyUniverse | None = None,
    observed_status: str = "observed",
    reproduction_request: Mapping[str, object] | None = None,
    limitations: Sequence[str] = (),
) -> tuple[EnrichmentManifest, dict[str, object]]:
    """Validate and atomically publish a normalized sidecar and its manifest."""
    households_path = population_directory / "households.csv"
    persons_path = population_directory / "persons.csv"
    linked_manifest_path = population_directory / "manifest.json"
    base_before = {
        path: _file_digest(path)
        for path in (households_path, persons_path, linked_manifest_path)
    }
    linked_manifest = _read_json_object(
        linked_manifest_path,
        "linked population manifest",
    )
    linked_geography = linked_manifest.get("geography")
    if source.geography is not None and base_geography is None:
        raise ValueError(
            "base_geography is required for a geography-bearing enrichment layer"
        )
    if base_geography is not None:
        if not isinstance(linked_geography, Mapping):
            raise ValueError("base population does not declare a geography column")
        if linked_geography.get("household_column") != base_geography.identifier_column:
            raise ValueError(
                "base geography identifier column does not match the linked "
                "population manifest"
            )
    layer = build_enrichment_layer(
        layer_path,
        layer_id=layer_id,
        layer_class=layer_class,
        key_columns=key_columns,
        variables=variables,
        source=source,
        resource=resource,
        observed_status=observed_status,
        geography=source.geography,
    )
    base_ids = (
        _csv_values(households_path, base_geography.identifier_column)
        if base_geography is not None
        else ()
    )
    validation = validate_normalized_layer(
        layer_path,
        layer,
        base_geography=base_geography,
        base_identifiers=base_ids,
    )
    if not validation["passed"]:
        validation_issues = validation.get("issues", [])
        if not isinstance(validation_issues, list):
            validation_issues = []
        issue_codes = ", ".join(
            str(issue.get("code"))
            for issue in validation_issues
            if isinstance(issue, Mapping)
        )
        raise ValueError(
            f"normalized enrichment layer failed validation: {issue_codes}"
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    destination = output_directory / layer.table_path
    _copy_atomic(layer_path, destination)
    manifest = build_enrichment_manifest(
        households_path,
        persons_path,
        linked_population_manifest_path=linked_manifest_path,
        sources=(source,),
        resources=(resource,),
        layers=(layer,),
        reproduction_request=reproduction_request
        or {
            "workflow": "enrichment",
            "operation": "import-normalized-layer",
            "population": str(population_directory),
            "layer": str(layer_path),
        },
        limitations=limitations,
    )
    write_enrichment_manifest(output_directory / "manifest.json", manifest)
    base_after = {path: _file_digest(path) for path in base_before}
    if base_after != base_before:
        raise RuntimeError("base population changed while publishing enrichment")
    return manifest, validation


def build_enrichment_manifest(
    households_path: Path,
    persons_path: Path,
    *,
    linked_population_manifest_path: Path,
    sources: Sequence[SourceProfile],
    resources: Sequence[ResourceRecord],
    layers: Sequence[EnrichmentLayer],
    reproduction_request: Mapping[str, object],
    limitations: Sequence[str] = (),
) -> EnrichmentManifest:
    """Compose base-table hashes with source, resource, and sidecar records."""
    households_sha256, households_size = _file_digest(households_path)
    persons_sha256, persons_size = _file_digest(persons_path)
    manifest_sha256, manifest_size = _file_digest(linked_population_manifest_path)
    base_population = {
        "linked_population_schema": "synthpopcan-linked-population-v1",
        "linked_population_manifest": _file_record(
            linked_population_manifest_path,
            manifest_sha256,
            manifest_size,
        ),
        "households": _file_record(
            households_path,
            households_sha256,
            households_size,
        ),
        "persons": _file_record(persons_path, persons_sha256, persons_size),
    }
    return EnrichmentManifest(
        base_population=base_population,
        sources=tuple(sources),
        resources=tuple(resources),
        layers=tuple(layers),
        reproduction_request=reproduction_request,
        limitations=tuple(limitations),
    )


def write_enrichment_manifest(path: Path, manifest: EnrichmentManifest) -> None:
    """Atomically write a validated enrichment manifest."""
    payload = manifest.as_dict()
    EnrichmentManifest.from_dict(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def verify_enrichment_manifest(
    manifest: EnrichmentManifest,
    directory: Path,
    *,
    base_directory: Path | None = None,
) -> dict[str, object]:
    """Verify that base tables and sidecars still match the manifest bytes."""
    issues: list[str] = []
    base = manifest.base_population
    base_root = base_directory or directory
    for label in ("linked_population_manifest", "households", "persons"):
        record = _mapping(base.get(label), label)
        _verify_file_record(base_root, record, label, issues)
    for layer in manifest.layers:
        path = directory / layer.table_path
        try:
            digest, _ = _file_digest(path)
        except OSError as exc:
            issues.append(f"cannot read layer {layer.layer_id}: {exc}")
            continue
        if digest != layer.sha256:
            issues.append(f"layer {layer.layer_id} checksum does not match")
    return {
        "schema_version": "synthpopcan-enrichment-verification-v1",
        "passed": not issues,
        "base_population_unchanged": not any(
            issue.startswith("base ") for issue in issues
        ),
        "issues": issues,
    }


def read_source_profile(path: Path) -> SourceProfile:
    """Read and validate a source-profile JSON document."""
    return SourceProfile.from_dict(_read_json_object(path, "source profile"))


def read_resource_record(path: Path) -> ResourceRecord:
    """Read and validate a resource-record JSON document."""
    return ResourceRecord.from_dict(_read_json_object(path, "resource record"))


def read_enrichment_manifest(path: Path) -> EnrichmentManifest:
    """Read and validate an enrichment-manifest JSON document."""
    return EnrichmentManifest.from_dict(_read_json_object(path, "enrichment manifest"))


def _verify_file_record(
    directory: Path,
    record: Mapping[str, object],
    label: str,
    issues: list[str],
) -> None:
    filename = record.get("path")
    if not isinstance(filename, str) or Path(filename).name != filename:
        issues.append(f"base {label} path is invalid")
        return
    try:
        digest, byte_size = _file_digest(directory / filename)
    except OSError as exc:
        issues.append(f"base {label} cannot be read: {exc}")
        return
    if digest != record.get("sha256"):
        issues.append(f"base {label} checksum does not match")
    if byte_size != record.get("byte_size"):
        issues.append(f"base {label} byte size does not match")


def _validate_base_population(payload: Mapping[str, object]) -> None:
    if payload.get("linked_population_schema") != "synthpopcan-linked-population-v1":
        raise ValueError("enrichment requires linked-population v1")
    for label in ("linked_population_manifest", "households", "persons"):
        record = _mapping(payload.get(label), label)
        filename = record.get("path")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"base {label} path must be a filename")
        _validate_sha256(record.get("sha256"), f"base {label} sha256")
        byte_size = record.get("byte_size")
        if (
            not isinstance(byte_size, int)
            or isinstance(byte_size, bool)
            or byte_size < 0
        ):
            raise ValueError(f"base {label} byte_size must be non-negative")


def _file_record(path: Path, sha256: str, byte_size: int) -> dict[str, object]:
    return {"path": path.name, "sha256": sha256, "byte_size": byte_size}


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_size += len(chunk)
    return digest.hexdigest(), byte_size


def _csv_values(path: Path, column: str) -> tuple[str, ...]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if column not in (reader.fieldnames or []):
            raise ValueError(
                f"base population household table is missing geography column {column}"
            )
        return tuple(
            value for row in reader if (value := str(row.get(column, "")).strip())
        )


def _copy_atomic(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with source.open("rb") as input_handle, temporary.open("xb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json_object(path: Path, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _validate_language_map(value: Mapping[str, str], label: str) -> None:
    _validate_string_mapping(value, label)
    if not value or any(language not in {"en", "fr"} for language in value):
        raise ValueError(f"{label} must contain English and/or French metadata")


def _validate_string_mapping(value: Mapping[str, str], label: str) -> None:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str)
        and isinstance(item, str)
        and key
        and item
        and item == item.strip()
        for key, item in value.items()
    ):
        raise ValueError(f"{label} must be a string-to-string object")


def _validate_columns(
    values: tuple[str, ...],
    label: str,
    *,
    allow_empty: bool = False,
) -> None:
    if (not values and not allow_empty) or any(
        not isinstance(value, str) or not value or value != value.strip()
        for value in values
    ):
        raise ValueError(f"{label} must contain non-empty column names")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_stable_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase stable identifier")


def _validate_sha256(value: object, label: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _validate_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty trimmed string")


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_text(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _string_mapping(
    payload: Mapping[str, object],
    key: str,
) -> Mapping[str, str]:
    value = _mapping(payload.get(key), key)
    if not all(
        isinstance(name, str) and isinstance(item, str) for name, item in value.items()
    ):
        raise ValueError(f"{key} must be a string-to-string object")
    return value  # type: ignore[return-value]


def _string_tuple(payload: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return tuple(value)


def _mapping_sequence(
    payload: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return tuple(_mapping(item, f"{key} item") for item in value)
