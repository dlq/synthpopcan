"""Build review-only Zenodo metadata for the prepared model catalogue.

Emits one deposition-metadata JSON per downloadable model package, plus an
``index.json`` summarising the set. The registry in ``synthpopcan.models`` is the
single source of truth: geography, census vintage, the Statistics Canada
attribution notice, the source licence, review status, limitations, file sizes,
and both checksums are copied straight out of it.

Zenodo and DataCite have no native "subordinate DOI". The hierarchy is expressed
through ``related_identifiers``:

* each model record declares ``isPartOf`` the software concept DOI and
  ``isDerivedFrom`` the Statistics Canada PUMF catalogue entry it was trained on;
* the software record declares ``hasPart`` for each model concept DOI.

The current registered assets are the verified non-overwriting correction
versions and embed the licensing contract. Generated records remain review-only:
they describe already-published objects but are not upload manifests. The
separate correction-candidate mode is retained for tests and future audited
transactions; it cannot treat a corrected registered asset as legacy input.

Usage::

    uv run python scripts/build_zenodo_depositions.py
    uv run python scripts/build_zenodo_depositions.py --year 2021
    uv run python scripts/build_zenodo_depositions.py --concept-doi 10.5281/zenodo.1234567
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

import click

from synthpopcan.model_licensing import (
    PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
    validate_prepared_model_licensing,
)
from synthpopcan.models import model_catalogue, model_registry_entry

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "derived" / "zenodo" / "depositions"
CORRECTION_PLAN_PATH = (
    ROOT / "data" / "derived" / "zenodo" / "prepared-model-rights-correction.json"
)

# Upstream product each vintage was trained from, for the isDerivedFrom link.
_PUMF_SOURCES = {
    "2016 Census": {
        "catalogue": "98M0002X2016001",
        "url": "https://www150.statcan.gc.ca/n1/en/catalogue/98M0002X2016001",
        "title": "2016 Census Hierarchical Public Use Microdata File",
    },
    "2021 Census": {
        "catalogue": "98M0001X2021002",
        "url": "https://www150.statcan.gc.ca/n1/en/catalogue/98M0001X2021002",
        "title": "2021 Census Hierarchical Public Use Microdata File, version 2",
    },
}

# Zenodo's legacy deposition API accepts one controlled license identifier even
# when layer-specific terms apply cumulatively. ``other-open`` is Zenodo's
# controlled compatibility value for that composite situation; the exact terms
# and their scopes live in the authoritative SynthPopCan licensing object.
_LICENSE = "other-open"
_ARCHIVE_CORRECTION_COMPLETED = "- **Archive correction implementation:** Completed"
_NEWVERSION_AUTHORITY_PREFIX = "<!-- synthpopcan-zenodo-newversion-authority:"

_SOFTWARE_REPOSITORY = "https://github.com/dlq/synthpopcan"

# Authorship for the archived model records, kept in step with CITATION.cff.
# ORCIDs are only ever added when supplied by their owner, never inferred.
_CREATORS = [{"name": "Quesnel, Darcy"}]


def _archive_filename(metadata: dict[str, Any]) -> str:
    """Return the immutable compressed basename, not the local cache filename."""

    filename = str(metadata.get("archive_filename", ""))
    if not filename:
        filename = Path(urllib.parse.urlparse(str(metadata["url"])).path).name
    if not filename.endswith(".json.gz"):
        raise ValueError("prepared-model release URL must name a .json.gz asset")
    if Path(filename).name != filename:
        raise ValueError("prepared-model release asset must be a safe basename")
    return filename


def _correction_operation_descriptor(manifest: dict[str, Any]) -> dict[str, Any]:
    """Bind an executable manifest to its operation, bytes, and metadata."""

    synthpopcan = manifest["synthpopcan"]
    metadata = manifest["metadata"]
    operation = str(synthpopcan["deposit_operation"])
    model_id = str(synthpopcan["model_id"])
    if operation == "correct-existing-metadata":
        version = str(synthpopcan["existing_package_version"])
        asset_sha256 = str(synthpopcan["historical_asset"]["sha256"]).lower()
    else:
        version = str(metadata["version"])
        asset_sha256 = str(synthpopcan["sha256"]).lower()
    canonical_metadata = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    metadata_sha256 = hashlib.sha256(canonical_metadata).hexdigest()
    operation_id = f"{operation}:{model_id}:{version}:{asset_sha256}:{metadata_sha256}"
    descriptor: dict[str, Any] = {
        "operation_id": operation_id,
        "deposit_operation": operation,
        "model_id": model_id,
        "package_version": version,
        "asset_sha256": asset_sha256,
        "metadata_sha256": metadata_sha256,
        "existing_record_id": synthpopcan["existing_record_id"],
        "existing_version_doi": synthpopcan["existing_version_doi"],
        "existing_concept_doi": synthpopcan["existing_concept_doi"],
    }
    if operation == "create-new-version":
        for field in (
            "filename",
            "size_bytes",
            "sha256",
            "uncompressed_size_bytes",
            "uncompressed_sha256",
        ):
            descriptor[field] = synthpopcan[field]
    return descriptor


def _description(
    entry: dict[str, Any], metadata: dict[str, Any], licensing: dict[str, Any]
) -> str:
    """Build the human-readable record description carrying full provenance."""

    source = _PUMF_SOURCES[str(entry["census_vintage"])]
    conditions = ", ".join(str(value) for value in entry["conditions"])
    presentation = licensing["presentation"]
    authored = licensing["authored_material"]
    authored_scope = authored["grant_scope"]
    authored_licence = authored["licence"]
    authored_materials = ", ".join(authored_scope["materials"])
    excluded_material = ", ".join(authored["excluded_material"])
    embedded_licensing = metadata.get("contains_embedded_licensing") is True
    integrity_heading = (
        "Published package integrity."
        if embedded_licensing
        else "Historical file integrity (review context only)."
    )
    return "\n".join(
        [
            f"<p>{entry['description']}</p>",
            "<p><strong>Geography:</strong> "
            f"{entry['geography']}<br>"
            f"<strong>Census vintage:</strong> {entry['census_vintage']}<br>"
            f"<strong>Conditioning columns:</strong> {conditions}<br>"
            f"<strong>Package version:</strong> {entry['release_version']}</p>",
            f"<p><strong>Source attribution.</strong> {entry['provenance']}</p>",
            "<p><strong>Layer-specific rights.</strong> Zenodo's compatibility "
            "label is Other (Open). The machine-readable contract is "
            f"<code>{licensing['schema_version']}</code>. "
            f"{presentation['statement']} {authored_scope['statement']} The "
            f'<a href="{authored_licence["url"]}">'
            f"{authored_licence['name']}</a> is the authored-layer licence. Named "
            f"original materials: {authored_materials}. Excluded material: "
            f"{excluded_material}. The "
            f'<a href="{source["url"]}">source file</a> is released under the '
            f'<a href="{entry["source_licence"]}">Statistics Canada Open '
            "Licence</a>; retain its required attribution above and comply with "
            "its accuracy, non-identification, non-misrepresentation, and "
            "no-endorsement conditions. Project rights-policy status: "
            f"<strong>{licensing['policy_decision']['status']}</strong>. External "
            "legal review: "
            f"<strong>{licensing['policy_decision']['external_legal_review']}</strong>."
            "</p>",
            "<p><strong>Disclosure review.</strong> "
            f"{entry['privacy']} Review status: "
            f"{entry['privacy_review_status']}. Passing SynthPopCan's "
            "disclosure-risk checks is a project-level screen, not legal "
            "anonymization or Statistics Canada endorsement.</p>",
            f"<p><strong>Known limitations.</strong> {entry['known_limitations']}</p>",
            "<p><strong>Generation guidance.</strong> "
            f"{entry['generation_limits']}</p>",
            f"<p><strong>{integrity_heading}</strong> "
            f"Compressed {metadata['size_bytes']:,} bytes, "
            f"SHA-256 <code>{metadata['sha256']}</code>. "
            f"Uncompressed {metadata['uncompressed_size_bytes']:,} bytes, "
            f"SHA-256 <code>{metadata['uncompressed_sha256']}</code>.</p>",
            "<p>Generated populations are synthetic artifacts. They are not "
            "real Census records and must not be presented as confidential "
            "Statistics Canada information.</p>",
        ]
    )


def _related_identifiers(
    entry: dict[str, Any], *, concept_doi: str | None
) -> list[dict[str, str]]:
    """Link the model record upward to the software and back to its source."""

    source = _PUMF_SOURCES[str(entry["census_vintage"])]
    related: list[dict[str, str]] = [
        {
            "relation": "isDerivedFrom",
            "identifier": source["url"],
            "resource_type": "dataset",
        },
        {
            "relation": "isCompiledBy",
            "identifier": _SOFTWARE_REPOSITORY,
            "resource_type": "software",
        },
    ]
    if concept_doi:
        related.insert(
            0,
            {
                "relation": "isPartOf",
                "identifier": concept_doi,
                "resource_type": "software",
            },
        )
    return related


def build_deposition(model_id: str, *, concept_doi: str | None) -> dict[str, Any]:
    """Build the Zenodo deposition metadata for one model package."""

    entry = next(item for item in model_catalogue() if item["id"] == model_id)
    metadata = model_registry_entry(model_id)
    source = _PUMF_SOURCES[str(entry["census_vintage"])]
    licensing = validate_prepared_model_licensing(entry["licensing"])
    embedded_licensing = metadata.get("contains_embedded_licensing") is True
    notes = (
        f"Package identifier: {model_id}. Fetch with "
        f"`synthpopcan models fetch {model_id}`. Trained from "
        f"{source['title']} ({source['catalogue']}). Rights are "
        "layer-specific and cumulative, not alternatives. "
    )
    if embedded_licensing:
        notes += (
            "This verified non-overwriting archive version embeds the exact "
            f"{PREPARED_MODEL_LICENSING_SCHEMA_VERSION} object at top-level "
            "`licensing`."
        )
    else:
        notes += (
            "This historical asset predates the embedded contract and is review "
            "context only. A corrected non-overwriting version must embed the "
            f"{PREPARED_MODEL_LICENSING_SCHEMA_VERSION} object at top-level "
            "`licensing` before upload."
        )

    return {
        "metadata": {
            "upload_type": "dataset",
            "title": f"SynthPopCan prepared model: {entry['name']}",
            "creators": _CREATORS,
            "version": str(entry["release_version"]),
            "description": _description(entry, metadata, licensing),
            "license": _LICENSE,
            "access_right": "open",
            "language": "eng",
            "keywords": [
                "synthetic population",
                "census",
                "Statistics Canada",
                "microdata",
                str(entry["census_vintage"]),
                str(entry["geography"]),
            ],
            "related_identifiers": _related_identifiers(entry, concept_doi=concept_doi),
            "notes": notes,
        },
        "synthpopcan": {
            "model_id": model_id,
            "deposit_operation": "review-metadata-only",
            "asset_ready": False,
            "historical_asset": {
                "url": str(metadata["url"]),
                "filename": _archive_filename(metadata),
                "compression": str(metadata["compression"]),
                "size_bytes": metadata["size_bytes"],
                "sha256": metadata["sha256"],
                "uncompressed_size_bytes": metadata["uncompressed_size_bytes"],
                "uncompressed_sha256": metadata["uncompressed_sha256"],
                "contains_embedded_licensing": embedded_licensing,
            },
            "licensing": licensing,
        },
    }


def build_rights_correction_plan() -> dict[str, Any]:
    """Plan non-destructive versions only for still-legacy registered assets."""

    registered = sorted(
        (entry for entry in model_catalogue() if entry["distribution"] == "download"),
        key=lambda entry: str(entry["id"]),
    )
    entries = [
        entry
        for entry in registered
        if model_registry_entry(str(entry["id"])).get("contains_embedded_licensing")
        is not True
    ]
    actions = []
    for entry in entries:
        licensing = validate_prepared_model_licensing(entry["licensing"])
        actions.append(
            {
                "model_id": str(entry["id"]),
                "existing_concept_doi": str(entry["doi"]),
                "existing_package_version": str(entry["release_version"]),
                "action": "prepare-new-version",
                "ready_for_production": False,
                "blocking_reason": (
                    "Build and independently review the checksum-bound corrected "
                    "asset and deposition bundle before any archive write. Production "
                    "also requires accepted ADR-0014 and the completed existing-record "
                    "correction implementation gate."
                ),
                "preserve_all_existing_versions": True,
                "new_package_version": "assign-before-candidate-build",
                "required_top_level_field": "licensing",
                "review_candidate_top_level_licensing": licensing,
                "target_zenodo_metadata": {
                    "license": _LICENSE,
                    "composite_scope_location": "metadata.description",
                },
                "required_package_licensing_location": "licensing",
                "local_manifest_licensing_location": "synthpopcan.licensing",
            }
        )
    return {
        "schema_version": "synthpopcan-zenodo-rights-correction-plan-v1",
        "network_writes": False,
        "current_policy_decision": validate_prepared_model_licensing(
            registered[0]["licensing"]
        )["policy_decision"]["status"],
        "corrected_record_count": len(registered) - len(actions),
        "existing_record_count": len(actions),
        "policy": {
            "legacy_license": "cc-by-4.0",
            "target_license": _LICENSE,
            "preserve_existing_versions": True,
            "production_gates": [
                "- **Status:** Accepted",
                _ARCHIVE_CORRECTION_COMPLETED,
            ],
            "reason": (
                "Published files are immutable research objects; corrected "
                "packages require new versions under the existing concept DOIs. "
                "The maintained package-rights policy is the project default. "
                "Archive writes still require accepted ADR-0014, an independently "
                "reviewed implementation, and an exact checksum-bound execution "
                "bundle."
            ),
        },
        "actions": actions,
    }


def _candidate_value(candidate: dict[str, Any], key: str, expected: type) -> Any:
    value = candidate.get(key)
    if not isinstance(value, expected) or isinstance(value, bool):
        raise click.UsageError(f"correction candidate must declare {key}")
    if expected is str and not value:
        raise click.UsageError(f"correction candidate must declare non-empty {key}")
    return value


def _validate_candidate_envelope(
    document: dict[str, Any], *, known: set[str]
) -> tuple[dict[str, Any], bool, str, str]:
    """Validate complete/test candidate readiness before emitting any manifest."""

    if document.get("schema_version") != (
        "synthpopcan-zenodo-correction-candidates-v1"
    ):
        raise click.UsageError("unsupported correction-candidates schema")
    if document.get("network_writes") is not False:
        raise click.UsageError("candidate envelope must record network_writes false")
    if document.get("model_retrained") is not False:
        raise click.UsageError("candidate envelope must record model_retrained false")
    build_scope = document.get("build_scope")
    if build_scope not in {"complete-catalogue", "test-subset"}:
        raise click.UsageError("candidate envelope has an invalid build_scope")
    production_ready = document.get("production_ready")
    coverage_complete = document.get("production_coverage_complete")
    if not isinstance(production_ready, bool) or not isinstance(
        coverage_complete, bool
    ):
        raise click.UsageError("candidate readiness fields must be booleans")
    non_production_reason = document.get("non_production_reason")
    if production_ready:
        if non_production_reason is not None:
            raise click.UsageError(
                "production-ready candidates cannot carry a non-production reason"
            )
    elif not isinstance(non_production_reason, str) or not non_production_reason:
        raise click.UsageError(
            "non-production candidates must explain why they are not executable"
        )
    candidates = document.get("candidates")
    if not isinstance(candidates, dict) or not candidates:
        raise click.UsageError("correction candidates must be a non-empty mapping")
    candidate_ids = document.get("candidate_model_ids")
    if not isinstance(candidate_ids, list) or candidate_ids != sorted(candidates):
        raise click.UsageError("candidate_model_ids must exactly match candidates")
    if document.get("candidate_count") != len(candidates):
        raise click.UsageError("candidate_count must exactly match candidates")
    if set(candidates) - known:
        raise click.UsageError(
            f"unknown correction model IDs: {sorted(set(candidates) - known)}"
        )
    if build_scope == "test-subset":
        if production_ready or coverage_complete:
            raise click.UsageError(
                "test-subset candidates can never be production-ready"
            )
    elif coverage_complete is not True or set(candidates) != known:
        raise click.UsageError(
            "complete-catalogue candidates must cover the exact 32-model catalogue"
        )
    if production_ready and (
        build_scope != "complete-catalogue"
        or coverage_complete is not True
        or set(candidates) != known
    ):
        raise click.UsageError("production-ready candidates require complete coverage")
    new_version = document.get("new_package_version")
    if not isinstance(new_version, str) or not new_version:
        raise click.UsageError("candidate envelope must declare new_package_version")
    return candidates, production_ready, str(build_scope), new_version


def build_correction_depositions(
    model_id: str,
    candidate: dict[str, Any],
    *,
    concept_doi: str,
    production_ready: bool,
    build_scope: str,
    envelope_new_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build executable metadata-edit and corrected-version manifests."""

    review = build_deposition(model_id, concept_doi=concept_doi)
    entry = next(item for item in model_catalogue() if item["id"] == model_id)
    historical = model_registry_entry(model_id)
    if historical.get("contains_embedded_licensing") is True:
        raise click.UsageError(
            f"{model_id}: installed registry already points to a verified package "
            "with embedded licensing; this legacy rights-insertion correction no "
            "longer applies"
        )
    if candidate.get("model_id") != model_id:
        raise click.UsageError(f"{model_id}: candidate model_id does not match its key")
    if candidate.get("census_vintage") != str(entry["census_vintage"]):
        raise click.UsageError(f"{model_id}: candidate Census vintage does not match")
    if candidate.get("package_schema_version") != (
        "synthpopcan-linked-tree-package-v1"
    ):
        raise click.UsageError(f"{model_id}: unsupported package schema")
    if candidate.get("package_type") != "linked_household_person":
        raise click.UsageError(f"{model_id}: unsupported package type")
    if candidate.get("existing_package_version") != str(entry["release_version"]):
        raise click.UsageError(f"{model_id}: existing package version does not match")
    candidate_licensing_value = candidate.get("licensing")
    try:
        candidate_licensing = validate_prepared_model_licensing(
            candidate_licensing_value
        )
    except ValueError as exc:
        raise click.UsageError(
            f"{model_id}: candidate must carry the exact licensing contract"
        ) from exc
    catalogue_licensing = validate_prepared_model_licensing(entry["licensing"])
    if candidate.get("licensing_schema_version") != candidate_licensing.get(
        "schema_version"
    ):
        raise click.UsageError(f"{model_id}: licensing schema binding does not match")
    for field in (
        "schema_version",
        "package_basis",
        "source_information",
        "authored_material",
        "presentation",
        "policy_decision",
    ):
        if candidate_licensing.get(field) != catalogue_licensing.get(field):
            raise click.UsageError(
                f"{model_id}: candidate licensing {field} does not match the model"
            )
    if production_ready and candidate_licensing["policy_decision"]["status"] != (
        "accepted"
    ):
        raise click.UsageError(
            f"{model_id}: production-ready candidate rights policy is not accepted"
        )
    existing_record_id = _candidate_value(candidate, "existing_record_id", int)
    existing_concept_doi = _candidate_value(candidate, "existing_concept_doi", str)
    existing_version_doi = _candidate_value(candidate, "existing_version_doi", str)
    if existing_concept_doi != entry["doi"]:
        raise click.UsageError(
            f"{model_id}: existing_concept_doi does not match the installed registry"
        )
    if existing_version_doi == existing_concept_doi:
        raise click.UsageError(
            f"{model_id}: latest version DOI must be distinct from the concept DOI"
        )
    new_version = _candidate_value(candidate, "new_package_version", str)
    if new_version != envelope_new_version:
        raise click.UsageError(f"{model_id}: package version differs from envelope")
    if new_version == entry["release_version"]:
        raise click.UsageError(f"{model_id}: corrected package needs a new version")
    filename = _candidate_value(candidate, "filename", str)
    if new_version not in filename:
        raise click.UsageError(
            f"{model_id}: candidate filename must contain new_package_version"
        )

    if candidate.get("transformation") != (
        "rights-metadata-only-top-level-field-insertion"
    ):
        raise click.UsageError(f"{model_id}: unsupported correction transformation")
    if candidate.get("model_retrained") is not False:
        raise click.UsageError(f"{model_id}: correction must not retrain the model")
    if candidate.get("historical_json_preserved_except_inserted_licensing") is not True:
        raise click.UsageError(f"{model_id}: historical preservation is not proven")

    nested_historical = candidate.get("historical_asset")
    nested_candidate = candidate.get("candidate_asset")
    if not isinstance(nested_historical, dict) or not isinstance(
        nested_candidate, dict
    ):
        raise click.UsageError(f"{model_id}: nested asset evidence is required")
    expected_historical = {
        "filename": _archive_filename(historical),
        "size_bytes": historical["size_bytes"],
        "sha256": historical["sha256"],
        "uncompressed_size_bytes": historical["uncompressed_size_bytes"],
        "uncompressed_sha256": historical["uncompressed_sha256"],
        "contains_embedded_licensing": False,
    }
    if nested_historical != expected_historical:
        raise click.UsageError(f"{model_id}: historical asset binding does not match")

    asset_fields: dict[str, Any] = {}
    for key, expected in (
        ("asset_url", str),
        ("size_bytes", int),
        ("sha256", str),
        ("uncompressed_size_bytes", int),
        ("uncompressed_sha256", str),
    ):
        asset_fields[key] = _candidate_value(candidate, key, expected)
        if nested_candidate.get(key) != asset_fields[key]:
            raise click.UsageError(f"{model_id}: nested/flat candidate {key} differs")
    if nested_candidate.get("filename") != filename:
        raise click.UsageError(f"{model_id}: nested/flat candidate filename differs")
    if nested_candidate.get("contains_embedded_licensing") is not True:
        raise click.UsageError(f"{model_id}: candidate licensing insertion is unproven")
    asset_uri = urllib.parse.urlparse(str(asset_fields["asset_url"]))
    if asset_uri.scheme != "file":
        raise click.UsageError(f"{model_id}: candidate asset must use a local file URI")
    for key in ("sha256", "uncompressed_sha256"):
        if len(asset_fields[key]) != 64:
            raise click.UsageError(f"{model_id}: {key} must be a SHA-256 checksum")

    historical_asset = {
        "url": str(historical["url"]),
        **expected_historical,
        "compression": str(historical["compression"]),
    }
    identity = {
        "existing_record_id": existing_record_id,
        "existing_concept_doi": existing_concept_doi,
        "existing_version_doi": existing_version_doi,
        "existing_package_version": str(entry["release_version"]),
        "historical_asset": historical_asset,
    }
    correction_notice = (
        "<p><strong>Rights-metadata correction.</strong> Earlier metadata could "
        "be read as applying one licence to the entire mixed-rights object. This "
        "record now states the cumulative, layer-specific scope. The historical "
        "file is unchanged and remains available at its existing identifier; it "
        "is retained but superseded for licensing clarity by the corrected "
        "version under the same concept DOI.</p>"
    )

    metadata_correction = json.loads(json.dumps(review))
    metadata_correction["metadata"]["description"] = (
        _description(entry, historical, candidate_licensing) + correction_notice
    )
    metadata_correction["synthpopcan"] = {
        "model_id": model_id,
        "deposit_operation": "correct-existing-metadata",
        "metadata_ready": production_ready,
        "production_ready": production_ready,
        "build_scope": build_scope,
        "candidate_envelope_schema": "synthpopcan-zenodo-correction-candidates-v1",
        "transformation": candidate["transformation"],
        "model_retrained": False,
        "historical_json_preserved_except_inserted_licensing": True,
        "package_schema_version": candidate["package_schema_version"],
        "package_type": candidate["package_type"],
        "census_vintage": candidate["census_vintage"],
        "licensing_schema_version": candidate["licensing_schema_version"],
        **identity,
        "licensing": candidate_licensing,
    }

    new_version_deposition = json.loads(json.dumps(review))
    new_metadata = new_version_deposition["metadata"]
    new_metadata["version"] = new_version
    corrected_entry = {**entry, "release_version": new_version}
    new_metadata["description"] = _description(
        corrected_entry,
        {
            "size_bytes": asset_fields["size_bytes"],
            "sha256": asset_fields["sha256"],
            "uncompressed_size_bytes": asset_fields["uncompressed_size_bytes"],
            "uncompressed_sha256": asset_fields["uncompressed_sha256"],
        },
        candidate_licensing,
    ).replace(
        "Historical file integrity (review context only).",
        "Corrected package integrity.",
    )
    new_metadata["description"] += (
        "<p><strong>Corrected package.</strong> These candidate bytes embed the "
        f"validated <code>{PREPARED_MODEL_LICENSING_SCHEMA_VERSION}</code> "
        "contract at top-level <code>licensing</code>.</p>"
    )
    related_identifiers = list(new_metadata.get("related_identifiers", []))
    related_identifiers.append(
        {
            "relation": "isNewVersionOf",
            "identifier": existing_version_doi,
            "resource_type": "dataset",
        }
    )
    new_metadata["related_identifiers"] = related_identifiers
    new_metadata["notes"] = (
        f"Corrected non-overwriting package version {new_version}; supersedes "
        f"{existing_version_doi} for licensing clarity while retaining that "
        "historical version. The package embeds the exact top-level licensing "
        "contract."
    )
    new_version_deposition["synthpopcan"] = {
        "model_id": model_id,
        "deposit_operation": "create-new-version",
        "asset_ready": production_ready,
        "production_ready": production_ready,
        "build_scope": build_scope,
        "candidate_envelope_schema": "synthpopcan-zenodo-correction-candidates-v1",
        "transformation": candidate["transformation"],
        "model_retrained": False,
        "historical_json_preserved_except_inserted_licensing": True,
        "package_schema_version": candidate["package_schema_version"],
        "package_type": candidate["package_type"],
        "census_vintage": candidate["census_vintage"],
        "licensing_schema_version": candidate["licensing_schema_version"],
        "candidate_asset": nested_candidate,
        "filename": filename,
        **asset_fields,
        **identity,
        "supersession": {
            "preserve_existing_version": True,
            "record_id": existing_record_id,
            "version_doi": existing_version_doi,
        },
        "licensing": candidate_licensing,
    }
    for manifest in (metadata_correction, new_version_deposition):
        is_part_of = [
            relation
            for relation in manifest["metadata"].get("related_identifiers", [])
            if relation.get("relation") == "isPartOf"
        ]
        if is_part_of != [
            {
                "relation": "isPartOf",
                "identifier": concept_doi,
                "resource_type": "software",
            }
        ]:
            raise click.UsageError(f"{model_id}: software concept DOI binding failed")
    new_version_operation_id = _correction_operation_descriptor(new_version_deposition)[
        "operation_id"
    ]
    authority_marker = f"{_NEWVERSION_AUTHORITY_PREFIX}{new_version_operation_id} -->"
    correction_notes = metadata_correction["metadata"].get("notes")
    if correction_notes is not None and not isinstance(correction_notes, str):
        raise click.UsageError(f"{model_id}: correction notes must be text")
    metadata_correction["metadata"]["notes"] = (
        f"{correction_notes.rstrip()}\n\n{authority_marker}"
        if correction_notes
        else authority_marker
    )
    return metadata_correction, new_version_deposition


@click.command()
@click.option(
    "--year",
    type=click.Choice(["2016", "2021", "all"]),
    default="all",
    show_default=True,
    help="Census vintage to emit depositions for.",
)
@click.option(
    "--concept-doi",
    default=None,
    metavar="DOI",
    help="Software concept DOI to link each model record to with isPartOf.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Output directory (default: {OUTPUT_DIR.relative_to(ROOT)}).",
)
@click.option(
    "--correction-plan",
    is_flag=True,
    help=(
        "Write only the deterministic, no-network rights-correction plan for "
        "existing model records."
    ),
)
@click.option(
    "--correction-candidates",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help=(
        "Build executable correction manifests from a fail-closed candidate-asset "
        "mapping. This performs no network writes."
    ),
)
def main(
    year: str,
    concept_doi: str | None,
    out_dir: Path | None,
    correction_plan: bool,
    correction_candidates: Path | None,
) -> None:
    """Emit Zenodo deposition metadata for the prepared model catalogue."""

    if correction_plan:
        plan_path = (
            out_dir / CORRECTION_PLAN_PATH.name
            if out_dir is not None
            else CORRECTION_PLAN_PATH
        )
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(build_rights_correction_plan(), indent=2, sort_keys=True) + "\n"
        )
        click.echo(f"Wrote {plan_path}")
        click.echo(
            "Plan only: no Zenodo request was made, every existing version is "
            "retained, and the correction implementation remains blocked."
        )
        return

    if correction_candidates is not None:
        if not concept_doi:
            raise click.UsageError(
                "--concept-doi is required when building correction candidates"
            )
        document = json.loads(correction_candidates.read_text())
        known = {
            str(entry["id"])
            for entry in model_catalogue()
            if entry["distribution"] == "download"
        }
        candidates, production_ready, build_scope, envelope_new_version = (
            _validate_candidate_envelope(document, known=known)
        )
        destination = out_dir or (OUTPUT_DIR / "corrections")
        if destination.exists():
            raise click.UsageError(
                f"refusing to overwrite correction bundle: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        execution_operations: list[dict[str, Any]] = []
        manifests: list[tuple[str, dict[str, Any]]] = []
        for model_id in sorted(candidates):
            candidate = candidates[model_id]
            if not isinstance(candidate, dict):
                raise click.UsageError(f"{model_id}: candidate must be an object")
            metadata_edit, new_version = build_correction_depositions(
                model_id,
                candidate,
                concept_doi=concept_doi,
                production_ready=production_ready,
                build_scope=build_scope,
                envelope_new_version=envelope_new_version,
            )
            for suffix, manifest in (
                ("metadata-correction", metadata_edit),
                ("new-version", new_version),
            ):
                descriptor = _correction_operation_descriptor(manifest)
                execution_operations.append(descriptor)
                manifests.append((f"{model_id}.{suffix}.json", manifest))
        candidate_envelope_sha256 = hashlib.sha256(
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        execution_document = {
            "schema_version": "synthpopcan-zenodo-correction-execution-index-v1",
            "build_scope": build_scope,
            "production_ready": production_ready,
            "candidate_count": len(candidates),
            "candidate_model_ids": sorted(candidates),
            "candidate_envelope_sha256": candidate_envelope_sha256,
            "new_package_version": envelope_new_version,
            "operations": sorted(
                execution_operations, key=lambda item: item["operation_id"]
            ),
        }
        execution_index_sha256 = hashlib.sha256(
            json.dumps(
                execution_document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        operation_ids = {
            (descriptor["model_id"], descriptor["deposit_operation"]): descriptor[
                "operation_id"
            ]
            for descriptor in execution_operations
        }
        for _, manifest in manifests:
            synthpopcan = manifest["synthpopcan"]
            synthpopcan["candidate_envelope_sha256"] = candidate_envelope_sha256
            synthpopcan["execution_index_schema"] = execution_document["schema_version"]
            synthpopcan["execution_index_sha256"] = execution_index_sha256
            synthpopcan["execution_operation_id"] = operation_ids[
                (synthpopcan["model_id"], synthpopcan["deposit_operation"])
            ]

        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.staging-", dir=destination.parent
            )
        )
        try:
            for filename, manifest in manifests:
                (staging / filename).write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
                )
            (staging / "execution-index.json").write_text(
                json.dumps(execution_document, indent=2, sort_keys=True) + "\n"
            )
            if destination.exists():
                raise click.UsageError(
                    f"refusing to overwrite correction bundle: {destination}"
                )
            staging.replace(destination)
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        for filename, _ in manifests:
            click.echo(f"Wrote {destination / filename}")
        click.echo(f"Wrote {destination / 'execution-index.json'}")
        if production_ready:
            click.echo(
                "Production-ready manifests built locally; no Zenodo request was "
                "made. The depositor still enforces every ADR-0014 production gate."
            )
        else:
            click.echo(
                "Non-production review manifests built locally; no Zenodo request "
                "was made, and the depositor will refuse to execute them."
            )
        return

    destination = out_dir or OUTPUT_DIR
    destination.mkdir(parents=True, exist_ok=True)

    wanted = [
        entry
        for entry in model_catalogue()
        if entry["distribution"] == "download"
        and (year == "all" or str(entry["census_vintage"]).startswith(year))
    ]
    if not wanted:
        raise click.UsageError(f"No downloadable models for year {year}")

    if not concept_doi:
        click.echo(
            "No --concept-doi supplied; records will omit the isPartOf link to "
            "the software record. Re-run with it once the software DOI exists.",
            err=True,
        )

    index: list[dict[str, Any]] = []
    for entry in wanted:
        model_id = str(entry["id"])
        deposition = build_deposition(model_id, concept_doi=concept_doi)
        path = destination / f"{model_id}.json"
        path.write_text(json.dumps(deposition, indent=2, sort_keys=True) + "\n")
        index.append(
            {
                "model_id": model_id,
                "title": deposition["metadata"]["title"],
                "version": deposition["metadata"]["version"],
                "census_vintage": str(entry["census_vintage"]),
                "deposit_operation": "review-metadata-only",
                "asset_ready": False,
                "deposition_metadata": path.name,
            }
        )
        click.echo(f"Wrote {path.relative_to(ROOT)}")

    index_path = destination / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-deposition-index-v1",
                "software_concept_doi": concept_doi,
                "license": _LICENSE,
                "licensing_schema_version": PREPARED_MODEL_LICENSING_SCHEMA_VERSION,
                "policy_decision": wanted[0]["licensing"]["policy_decision"]["status"],
                "depositions": index,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    click.echo(
        f"\n{len(index)} deposition(s) written to {destination.relative_to(ROOT)}"
    )
    click.echo(
        "Review-only metadata for already-published registered assets; no Zenodo "
        "write is authorized by these files."
    )


if __name__ == "__main__":
    main()
