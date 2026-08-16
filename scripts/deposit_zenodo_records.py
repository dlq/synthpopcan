"""Apply prepared-model deposits and identifier-preserving Zenodo corrections.

Reads manifests emitted by ``build_zenodo_depositions.py``, applies their
explicit create/edit/new-version operation, and records the resulting record
IDs, DOIs, verified assets, and resumable state.

Safety model, because publishing to Zenodo is irreversible:

* the sandbox is the default target; ``--production`` is required to touch the
  real archive;
* nothing is published unless ``--publish`` is passed, and even then each
  publish is confirmed;
* ``--dry-run`` reports the planned calls without contacting Zenodo at all;
* existing records are checked before edits or new-version actions, and a
  corrected package is always uploaded to a new version draft;
* checkpoints are scoped to the operation, package version, and asset digest.

Authentication uses a personal access token from ``ZENODO_TOKEN`` (or
``ZENODO_SANDBOX_TOKEN`` when targeting the sandbox); tokens are never accepted
on the command line, so they stay out of shell history.

Usage::

    uv run python scripts/deposit_zenodo_records.py --dry-run
    uv run python scripts/deposit_zenodo_records.py --only ontario-2021-all-fields
    uv run python scripts/deposit_zenodo_records.py --manifests-dir PATH --dry-run
    uv run python scripts/deposit_zenodo_records.py --production --publish
"""

from __future__ import annotations

import codecs
import gzip
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from synthpopcan.model_licensing import validate_prepared_model_licensing

ROOT = Path(__file__).resolve().parents[1]
DEPOSITIONS_DIR = ROOT / "data" / "derived" / "zenodo" / "depositions"
RESULTS_PATH = DEPOSITIONS_DIR / "deposited.json"
REGISTRY_UPDATES_PATH = DEPOSITIONS_DIR / "verified-registry-updates.json"
CORRECTION_EXECUTION_INDEX_PATH = (
    DEPOSITIONS_DIR / "corrections" / "execution-index.json"
)
LICENSING_ADR = ROOT / "adr" / "0014-separate-prepared-model-and-source-licensing.md"
CORRECTION_PLAN_NAME = "prepared-model-rights-correction.json"
CORRECTION_PLAN_PATH = (
    ROOT / "data" / "derived" / "zenodo" / "prepared-model-rights-correction.json"
)
_ACCEPTED_STATUS = "- **Status:** Accepted"
_STATUS_PREFIX = "- **Status:** "
_ARCHIVE_CORRECTION_COMPLETED = "- **Archive correction implementation:** Completed"
_ARCHIVE_CORRECTION_PREFIX = "- **Archive correction implementation:** "
_ARCHIVE_EXECUTION_COMPLETED = "- **Archive correction execution:** Completed"
_ARCHIVE_EXECUTION_PREFIX = "- **Archive correction execution:** "
_STREAM_CHUNK_BYTES = 1024 * 1024
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")

PRODUCTION_API = "https://zenodo.org/api"
SANDBOX_API = "https://sandbox.zenodo.org/api"

_ASSET_OPERATIONS = {"create-new-record", "create-new-version"}
_SUPPORTED_OPERATIONS = _ASSET_OPERATIONS | {"correct-existing-metadata"}
_TERMINAL_STATE = "verified"
_HTTP_STATUS_KEY = "_synthpopcan_http_status"
# The HTML authority marker is part of the immutable, reviewed manifest and
# therefore part of every correction operation identity. Zenodo sanitizes
# HTML comments out of ``notes``, so API payloads use the visible plain-text
# forms below. Canonical comparison maps the durable authority form back to
# this logical manifest form; it never rewrites the manifest itself.
_OWNERSHIP_PREFIX = "<!-- synthpopcan-zenodo-executor:"
_NEWVERSION_AUTHORITY_PREFIX = "<!-- synthpopcan-zenodo-newversion-authority:"
_DURABLE_OWNERSHIP_PREFIX = "SYNTHPOPCAN-ZENODO-EXECUTOR: "
_DURABLE_NEWVERSION_AUTHORITY_PREFIX = "SYNTHPOPCAN-ZENODO-NEWVERSION-AUTHORITY: "
_OPERATION_MARKER = re.compile(
    r"(?:create-new-record|create-new-version|correct-existing-metadata):"
    r"[a-z0-9]+(?:-[a-z0-9]+)*:"
    r"v?[0-9][A-Za-z0-9._+-]*:"
    r"[0-9a-f]{64}:[0-9a-f]{64}\Z"
)
# One production edit was opened immediately before we learned that Zenodo
# strips HTML comments. This allow-list is deliberately a single immutable
# operation identity, not a general draft-adoption escape hatch.
_LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID = (
    "correct-existing-metadata:pei-2021-minimal:v0.6.0:"
    "d47857c9b27e8c2fb4a37e8469fe6f4afc44a7fbc5673663d8909718a6e44b85:"
    "c0ec9c938e71dca61c69fc1a5b3e2d86c4694855691695771147f6d1cee8f621"
)
_LEGACY_STRIPPED_MARKER_STAGED_PUBLICATION_DATE = "2026-08-16"
_LEGACY_STRIPPED_MARKER_RECOVERY_RECORD_ID = 21461527
_LEGACY_STRIPPED_MARKER_RECOVERY_VERSION_DOI = "10.5281/zenodo.21461527"
_LEGACY_STRIPPED_MARKER_RECOVERY_CONCEPT_DOI = "10.5281/zenodo.21461526"
_CENSUS_VINTAGE_YEAR = {
    "2016 Census": 2016,
    "2021 Census": 2021,
}


class ZenodoError(RuntimeError):
    """Raised when the Zenodo API rejects a request."""


def _model_licensing_review_is_accepted() -> bool:
    """Return whether the durable prepared-model licensing decision is accepted."""

    if not LICENSING_ADR.is_file():
        return False
    return _metadata_line_is_exact(
        LICENSING_ADR.read_text().splitlines(),
        _STATUS_PREFIX,
        _ACCEPTED_STATUS,
    )


def _metadata_line_is_exact(lines: list[str], prefix: str, expected: str) -> bool:
    matches = [line for line in lines if line.startswith(prefix)]
    return matches == [expected]


def _archive_correction_implementation_is_completed() -> bool:
    """Return whether existing-record/new-version support is implemented."""

    if not LICENSING_ADR.is_file():
        return False
    return _metadata_line_is_exact(
        LICENSING_ADR.read_text().splitlines(),
        _ARCHIVE_CORRECTION_PREFIX,
        _ARCHIVE_CORRECTION_COMPLETED,
    )


def _production_licensing_gates_are_complete() -> bool:
    """Require all durable rights and archive gates before production writes."""

    return (
        _model_licensing_review_is_accepted()
        and _archive_correction_implementation_is_completed()
    )


def _archive_correction_execution_is_completed() -> bool:
    """Require the durable marker and complete verified 32-record evidence."""

    if (
        not LICENSING_ADR.is_file()
        or not CORRECTION_PLAN_PATH.is_file()
        or not CORRECTION_EXECUTION_INDEX_PATH.is_file()
        or not REGISTRY_UPDATES_PATH.is_file()
    ):
        return False
    if not _metadata_line_is_exact(
        LICENSING_ADR.read_text().splitlines(),
        _ARCHIVE_EXECUTION_PREFIX,
        _ARCHIVE_EXECUTION_COMPLETED,
    ):
        return False
    plan = json.loads(CORRECTION_PLAN_PATH.read_text())
    actions = plan.get("actions")
    if not isinstance(actions, list) or len(actions) != 32:
        return False
    expected = {
        str(action.get("model_id"))
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("model_id"), str)
    }
    if len(expected) != 32:
        return False
    execution_index = json.loads(CORRECTION_EXECUTION_INDEX_PATH.read_text())
    if execution_index.get("schema_version") != (
        "synthpopcan-zenodo-correction-execution-index-v1"
    ):
        return False
    if (
        execution_index.get("production_ready") is not True
        or execution_index.get("build_scope") != "complete-catalogue"
        or execution_index.get("candidate_count") != 32
        or execution_index.get("candidate_model_ids") != sorted(expected)
    ):
        return False
    envelope_sha256 = execution_index.get("candidate_envelope_sha256")
    new_package_version = execution_index.get("new_package_version")
    if (
        not isinstance(envelope_sha256, str)
        or len(envelope_sha256) != 64
        or not isinstance(new_package_version, str)
        or not new_package_version
    ):
        return False
    indexed_operations = execution_index.get("operations")
    if not isinstance(indexed_operations, list) or len(indexed_operations) != 64:
        return False
    indexed_by_id = {
        str(operation.get("operation_id")): operation
        for operation in indexed_operations
        if isinstance(operation, dict)
        and isinstance(operation.get("operation_id"), str)
    }
    if len(indexed_by_id) != 64:
        return False
    for operation_id, operation in indexed_by_id.items():
        for digest_field in ("asset_sha256", "metadata_sha256"):
            digest = operation.get(digest_field)
            if not isinstance(digest, str) or len(digest) != 64:
                return False
        expected_operation_id = ":".join(
            str(operation.get(field))
            for field in (
                "deposit_operation",
                "model_id",
                "package_version",
                "asset_sha256",
                "metadata_sha256",
            )
        )
        if operation_id != expected_operation_id:
            return False
        if not isinstance(operation.get("existing_record_id"), int):
            return False
        if not all(
            isinstance(operation.get(field), str) and operation.get(field)
            for field in ("existing_version_doi", "existing_concept_doi")
        ):
            return False
        if operation.get("deposit_operation") == "create-new-version":
            if operation.get("package_version") != new_package_version:
                return False
            if operation.get("sha256") != operation.get("asset_sha256"):
                return False
            if not isinstance(operation.get("filename"), str):
                return False
            for field in ("size_bytes", "uncompressed_size_bytes"):
                value = operation.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return False
            digest = operation.get("uncompressed_sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                return False
    indexed_pairs = {
        (str(operation.get("model_id")), str(operation.get("deposit_operation")))
        for operation in indexed_by_id.values()
    }
    if indexed_pairs != {
        (model_id, operation)
        for model_id in expected
        for operation in ("correct-existing-metadata", "create-new-version")
    }:
        return False

    stored_production = _stored_targets().get("PRODUCTION")
    if (
        not isinstance(stored_production, dict)
        or str(stored_production.get("api", "")).rstrip("/") != PRODUCTION_API
    ):
        return False
    production_results = _existing_results("PRODUCTION")
    verified_by_id = {
        str(result.get("operation_id")): result
        for result in production_results.values()
        if result.get("state") == _TERMINAL_STATE
        and result.get("verified") is True
        and result.get("deposit_operation")
        in {"correct-existing-metadata", "create-new-version"}
    }
    if set(verified_by_id) != set(indexed_by_id):
        return False
    for operation_id, indexed in indexed_by_id.items():
        verified = verified_by_id[operation_id]
        for field in (
            "deposit_operation",
            "model_id",
            "package_version",
            "asset_sha256",
            "metadata_sha256",
            "source_record_id",
        ):
            indexed_value = (
                indexed.get("existing_record_id")
                if field == "source_record_id"
                else indexed.get(field)
            )
            if verified.get(field) != indexed_value:
                return False
        if verified.get("concept_doi") != indexed.get("existing_concept_doi"):
            return False
        if indexed.get("deposit_operation") == "correct-existing-metadata":
            if verified.get("deposition_id") != indexed.get(
                "existing_record_id"
            ) or verified.get("doi") != indexed.get("existing_version_doi"):
                return False
        elif verified.get("deposition_id") == indexed.get(
            "existing_record_id"
        ) or verified.get("doi") == indexed.get("existing_version_doi"):
            return False

    registry_document = json.loads(REGISTRY_UPDATES_PATH.read_text())
    if (
        registry_document.get("schema_version")
        != "synthpopcan-verified-registry-updates-v1"
        or registry_document.get("target") != "PRODUCTION"
        or str(registry_document.get("api", "")).rstrip("/") != PRODUCTION_API
    ):
        return False
    updates = registry_document.get("updates")
    if not isinstance(updates, list) or len(updates) != 32:
        return False
    updates_by_model = {
        str(update.get("model_id")): update
        for update in updates
        if isinstance(update, dict) and isinstance(update.get("model_id"), str)
    }
    if set(updates_by_model) != expected:
        return False
    for operation in indexed_by_id.values():
        if operation.get("deposit_operation") != "create-new-version":
            continue
        update = updates_by_model[str(operation["model_id"])]
        verified = verified_by_id[str(operation["operation_id"])]
        result_update = verified.get("registry_update")
        if not isinstance(result_update, dict) or update != result_update:
            return False
        expected_fields = {
            "model_id": operation["model_id"],
            "release_version": operation["package_version"],
            "record_id": verified.get("deposition_id"),
            "version_doi": verified.get("doi"),
            "concept_doi": operation["existing_concept_doi"],
            "url": update.get("url"),
            "filename": operation["filename"],
            "size_bytes": operation["size_bytes"],
            "sha256": operation["sha256"],
            "uncompressed_size_bytes": operation["uncompressed_size_bytes"],
            "uncompressed_sha256": operation["uncompressed_sha256"],
        }
        if update != expected_fields:
            return False
        if not isinstance(update["record_id"], int) or update["record_id"] <= 0:
            return False
        if not all(
            isinstance(update[field], str) and update[field]
            for field in ("version_doi", "concept_doi", "url", "filename")
        ):
            return False
    return True


def _request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
) -> dict[str, Any]:
    """Issue one authenticated Zenodo API call and return the parsed response."""

    headers = {"Authorization": f"Bearer {token}"}
    body: bytes | None = data
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        headers["Content-Type"] = "application/octet-stream"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:  # pragma: no cover - network failure
        detail = exc.read().decode(errors="replace")
        raise ZenodoError(f"{method} {url} failed: {exc.code} {detail}") from exc
    parsed = json.loads(raw) if raw else {}
    if isinstance(parsed, dict):
        parsed.setdefault(_HTTP_STATUS_KEY, status)
    return parsed


def _asset_bytes(deposition: dict[str, Any]) -> bytes:
    """Fetch the release asset this deposition describes."""

    url = str(deposition["synthpopcan"]["asset_url"])
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def _verify_remote_download(
    url: str, *, expected_size: int, expected_sha256: str
) -> None:
    """Stream and verify a preserved published asset without materializing it."""

    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=300) as response:
        while chunk := response.read(_STREAM_CHUNK_BYTES):
            size += len(chunk)
            if size > expected_size:
                raise ZenodoError("historical Zenodo asset exceeds its registered size")
            digest.update(chunk)
    if size != expected_size:
        raise ZenodoError("historical Zenodo asset size changed")
    if digest.hexdigest() != expected_sha256.lower():
        raise ZenodoError("historical Zenodo asset SHA-256 changed")


def _validated_licensing(
    deposition: dict[str, Any],
    *,
    require_accepted_policy: bool,
) -> dict[str, Any]:
    """Validate the authoritative package licensing object in a manifest."""

    metadata = deposition.get("synthpopcan")
    if not isinstance(metadata, dict):
        raise ZenodoError("deposition must carry SynthPopCan metadata")
    licensing = metadata.get("licensing")
    try:
        validated = validate_prepared_model_licensing(licensing)
    except ValueError as exc:
        raise ZenodoError(
            "deposition must carry the exact prepared-model licensing schema"
        ) from exc
    if validated.get("package_basis") != "census-derived":
        raise ZenodoError("Zenodo model depositions require Census-derived licensing")
    presentation = validated.get("presentation")
    if not isinstance(presentation, dict) or presentation.get("mode") != (
        "cumulative-layers-not-alternatives"
    ):
        raise ZenodoError("prepared-model licensing must use cumulative layers")
    policy_decision = validated.get("policy_decision")
    if not isinstance(policy_decision, dict):
        raise ZenodoError("prepared-model policy decision is missing")
    if require_accepted_policy and policy_decision.get("status") != "accepted":
        raise ZenodoError(
            "production packages require the accepted project rights policy"
        )
    if require_accepted_policy:
        decision = policy_decision.get("decision_record")
        if (
            not isinstance(decision, dict)
            or decision.get("id") != "ADR-0014"
            or decision.get("status") != "accepted"
        ):
            raise ZenodoError(
                "production licensing lacks its accepted ADR-0014 policy binding"
            )
        if policy_decision.get("external_legal_review") != "not-obtained":
            raise ZenodoError(
                "production licensing must state the actual external-review status"
            )
    return validated


def _verify_asset(
    payload: bytes,
    deposition: dict[str, Any],
    *,
    require_accepted_policy: bool = False,
) -> None:
    """Reject bytes that differ from metadata or lack exact package rights."""

    metadata = deposition["synthpopcan"]
    expected_size = metadata.get("size_bytes")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise ZenodoError("deposition metadata must declare a non-negative size_bytes")
    if len(payload) != expected_size:
        raise ZenodoError(
            f"asset size mismatch: expected {expected_size:,} bytes, "
            f"downloaded {len(payload):,}"
        )

    expected_sha256 = metadata.get("sha256")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ZenodoError("deposition metadata must declare a SHA-256 checksum")
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != expected_sha256.lower():
        raise ZenodoError(
            f"asset SHA-256 mismatch: expected {expected_sha256}, "
            f"downloaded {actual_sha256}"
        )

    expected_uncompressed_size = metadata.get("uncompressed_size_bytes")
    if (
        not isinstance(expected_uncompressed_size, int)
        or expected_uncompressed_size < 0
    ):
        raise ZenodoError("deposition metadata must declare uncompressed_size_bytes")
    expected_uncompressed_sha256 = metadata.get("uncompressed_sha256")
    if (
        not isinstance(expected_uncompressed_sha256, str)
        or len(expected_uncompressed_sha256) != 64
    ):
        raise ZenodoError(
            "deposition metadata must declare an uncompressed SHA-256 checksum"
        )
    package_licensing = _stream_uncompressed_licensing(
        payload,
        expected_size=expected_uncompressed_size,
        expected_sha256=expected_uncompressed_sha256,
        allow_verified_tail=(
            metadata.get("deposit_operation") == "create-new-version"
            and metadata.get("production_ready") is True
            and metadata.get("model_retrained") is False
            and metadata.get("historical_json_preserved_except_inserted_licensing")
            is True
            and metadata.get("transformation")
            == "rights-metadata-only-top-level-field-insertion"
        ),
    )

    licensing = _validated_licensing(
        deposition,
        require_accepted_policy=require_accepted_policy,
    )
    if package_licensing != licensing:
        raise ZenodoError(
            "prepared-model asset lacks the exact top-level licensing schema"
        )


class _JsonContext:
    def __init__(self, kind: str, *, capture: bool) -> None:
        self.kind = kind
        self.capture = capture
        self.state = "key-or-end" if kind == "object" else "value-or-end"
        self.pending_key: str | None = None
        self.value: dict[str, object] | list[object] = {} if kind == "object" else []


class _StreamingLicensingJsonParser:
    """Small validating SAX parser that materializes only top-level licensing."""

    def __init__(self) -> None:
        self.contexts: list[_JsonContext] = []
        self.root_state = "value"
        self.licensing: object | None = None
        self.licensing_count = 0
        self.licensing_complete = False
        self._capture_next = False
        self._lexer_state = "default"
        self._token = []
        self._string_buffered = False
        self._unicode_remaining = 0
        self._literal_expected = ""

    def _context_expects_value(self) -> bool:
        if not self.contexts:
            return self.root_state == "value"
        return self.contexts[-1].state in {"value", "value-or-end"}

    def _should_buffer_string(self) -> bool:
        if not self.contexts:
            return False
        context = self.contexts[-1]
        if context.kind == "object" and context.state in {"key", "key-or-end"}:
            return context.capture or len(self.contexts) == 1
        return self._next_value_is_captured()

    def _next_value_is_captured(self) -> bool:
        if self._capture_next:
            return True
        return bool(self.contexts and self.contexts[-1].capture)

    def _attach_value(self, value: object, *, captured: bool) -> None:
        if not self.contexts:
            if self.root_state != "value":
                raise ZenodoError("prepared-model JSON has multiple root values")
            self.root_state = "complete"
            return
        context = self.contexts[-1]
        if context.kind == "array":
            if context.state not in {"value", "value-or-end"}:
                raise ZenodoError("prepared-model JSON array is malformed")
            if context.capture:
                assert isinstance(context.value, list)
                context.value.append(value)
            context.state = "comma-or-end"
        else:
            if context.state != "value" or context.pending_key is None:
                raise ZenodoError("prepared-model JSON object is malformed")
            if context.capture:
                assert isinstance(context.value, dict)
                context.value[context.pending_key] = value
            context.pending_key = None
            context.state = "comma-or-end"
        if captured and not context.capture:
            self.licensing = value
            self._capture_next = False
            self.licensing_complete = True

    def _start_container(self, kind: str) -> None:
        if not self._context_expects_value():
            raise ZenodoError("prepared-model JSON contains an unexpected container")
        capture = self._next_value_is_captured()
        self.contexts.append(_JsonContext(kind, capture=capture))

    def _close_container(self, kind: str) -> None:
        if not self.contexts or self.contexts[-1].kind != kind:
            raise ZenodoError("prepared-model JSON containers are unbalanced")
        context = self.contexts[-1]
        valid = (
            context.state in {"key-or-end", "comma-or-end"}
            if kind == "object"
            else context.state in {"value-or-end", "comma-or-end"}
        )
        if not valid:
            raise ZenodoError("prepared-model JSON container closes mid-value")
        self.contexts.pop()
        captured_root = context.capture and not (
            self.contexts and self.contexts[-1].capture
        )
        self._attach_value(
            context.value if context.capture else None, captured=captured_root
        )

    def _scalar(self, value: object) -> None:
        if not self._context_expects_value():
            raise ZenodoError("prepared-model JSON contains an unexpected value")
        captured = self._next_value_is_captured()
        self._attach_value(value if captured else None, captured=captured)

    def _string(self, raw: str | None) -> None:
        if self.contexts:
            context = self.contexts[-1]
            if context.kind == "object" and context.state in {"key", "key-or-end"}:
                value = json.loads(f'"{raw}"') if raw is not None else ""
                if not isinstance(value, str):
                    raise ZenodoError("prepared-model JSON key must be text")
                context.pending_key = value
                context.state = "colon"
                if len(self.contexts) == 1 and value == "licensing":
                    self.licensing_count += 1
                    if self.licensing_count != 1:
                        raise ZenodoError(
                            "prepared-model asset contains duplicate top-level licensing"
                        )
                    self._capture_next = True
                return
        value = json.loads(f'"{raw}"') if raw is not None else None
        self._scalar(value)

    def _punctuation(self, character: str) -> None:
        if character == "{":
            self._start_container("object")
            return
        if character == "[":
            self._start_container("array")
            return
        if character == "}":
            self._close_container("object")
            return
        if character == "]":
            self._close_container("array")
            return
        if not self.contexts:
            raise ZenodoError("prepared-model JSON contains trailing punctuation")
        context = self.contexts[-1]
        if character == ":":
            if context.kind != "object" or context.state != "colon":
                raise ZenodoError("prepared-model JSON contains an unexpected colon")
            context.state = "value"
        elif character == ",":
            if context.state != "comma-or-end":
                raise ZenodoError("prepared-model JSON contains an unexpected comma")
            context.state = "key" if context.kind == "object" else "value"

    def _finish_number(self) -> None:
        raw = "".join(self._token)
        if not _JSON_NUMBER.fullmatch(raw):
            raise ZenodoError("prepared-model JSON contains an invalid number")
        self._scalar(json.loads(raw) if self._next_value_is_captured() else None)
        self._token = []
        self._lexer_state = "default"

    def feed(self, text: str) -> None:
        cursor = 0
        while cursor < len(text):
            character = text[cursor]
            if self._lexer_state == "string":
                if ord(character) < 0x20:
                    raise ZenodoError(
                        "prepared-model JSON string contains control text"
                    )
                if character == '"':
                    raw = "".join(self._token) if self._string_buffered else None
                    self._token = []
                    self._lexer_state = "default"
                    self._string(raw)
                elif character == "\\":
                    if self._string_buffered:
                        self._token.append(character)
                    self._lexer_state = "escape"
                elif self._string_buffered:
                    self._token.append(character)
                cursor += 1
                continue
            if self._lexer_state == "escape":
                if character not in '"\\/bfnrtu':
                    raise ZenodoError("prepared-model JSON string escape is invalid")
                if self._string_buffered:
                    self._token.append(character)
                if character == "u":
                    self._unicode_remaining = 4
                    self._lexer_state = "unicode"
                else:
                    self._lexer_state = "string"
                cursor += 1
                continue
            if self._lexer_state == "unicode":
                if character not in "0123456789abcdefABCDEF":
                    raise ZenodoError("prepared-model JSON unicode escape is invalid")
                if self._string_buffered:
                    self._token.append(character)
                self._unicode_remaining -= 1
                if self._unicode_remaining == 0:
                    self._lexer_state = "string"
                cursor += 1
                continue
            if self._lexer_state == "number":
                if character in "0123456789+-.eE":
                    self._token.append(character)
                    if len(self._token) > 1024:
                        raise ZenodoError(
                            "prepared-model JSON number is unreasonably long"
                        )
                    cursor += 1
                    continue
                self._finish_number()
                continue
            if self._lexer_state == "literal":
                self._token.append(character)
                current = "".join(self._token)
                if not self._literal_expected.startswith(current):
                    raise ZenodoError("prepared-model JSON literal is invalid")
                cursor += 1
                if current == self._literal_expected:
                    value = {"true": True, "false": False, "null": None}[current]
                    self._token = []
                    self._lexer_state = "default"
                    self._scalar(value if self._next_value_is_captured() else None)
                continue

            if character in " \t\r\n":
                cursor += 1
            elif character == '"':
                self._string_buffered = self._should_buffer_string()
                self._token = []
                self._lexer_state = "string"
                cursor += 1
            elif character in "{}[]:,":
                self._punctuation(character)
                cursor += 1
            elif character == "-" or character.isdigit():
                self._token = [character]
                self._lexer_state = "number"
                cursor += 1
            elif character in "tfn":
                self._literal_expected = {
                    "t": "true",
                    "f": "false",
                    "n": "null",
                }[character]
                self._token = [character]
                self._lexer_state = "literal"
                cursor += 1
            else:
                raise ZenodoError("prepared-model JSON contains an invalid token")

    def finish(self, *, allow_incomplete_after_licensing: bool = False) -> object:
        if allow_incomplete_after_licensing and self.licensing_complete:
            return self.licensing
        if self._lexer_state == "number":
            self._finish_number()
        elif self._lexer_state != "default":
            raise ZenodoError("prepared-model JSON ends inside a token")
        if self.contexts or self.root_state != "complete":
            raise ZenodoError(
                "prepared-model asset does not contain one complete JSON value"
            )
        if self.licensing_count != 1:
            raise ZenodoError(
                "prepared-model asset lacks the exact top-level licensing field"
            )
        return self.licensing


def _stream_uncompressed_licensing(
    payload: bytes,
    *,
    expected_size: int,
    expected_sha256: str,
    allow_verified_tail: bool = False,
) -> object:
    """Hash a bounded gzip stream and extract only its small licensing object.

    ``allow_verified_tail`` is reserved for correction assets whose envelope
    proves byte-for-byte historical preservation plus one top-level insertion.
    Once that inserted object is captured, UTF-8, size, and SHA verification
    continue to EOF while the Python semantic parser is no longer fed the
    potentially multi-gigabyte preserved tail.
    """

    digest = hashlib.sha256()
    decoded_size = 0
    parser = _StreamingLicensingJsonParser()
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as source:
            while chunk := source.read(_STREAM_CHUNK_BYTES):
                decoded_size += len(chunk)
                if decoded_size > expected_size:
                    raise ZenodoError(
                        "uncompressed asset size exceeds declared "
                        f"{expected_size:,} bytes"
                    )
                digest.update(chunk)
                decoded = decoder.decode(chunk)
                if not (allow_verified_tail and parser.licensing_complete):
                    parser.feed(decoded)
    except UnicodeDecodeError as exc:
        raise ZenodoError("prepared-model asset is not valid UTF-8 JSON") from exc
    except (EOFError, OSError) as exc:
        raise ZenodoError("prepared-model asset must be valid gzip data") from exc

    if decoded_size != expected_size:
        raise ZenodoError(
            "uncompressed asset size mismatch: expected "
            f"{expected_size:,} bytes, decoded {decoded_size:,}"
        )
    if digest.hexdigest() != expected_sha256.lower():
        raise ZenodoError("uncompressed asset SHA-256 mismatch")
    try:
        decoded_tail = decoder.decode(b"", final=True)
        if not (allow_verified_tail and parser.licensing_complete):
            parser.feed(decoded_tail)
    except UnicodeDecodeError as exc:
        raise ZenodoError("prepared-model asset is not valid UTF-8 JSON") from exc
    return parser.finish(allow_incomplete_after_licensing=allow_verified_tail)


def _verify_upload_response(uploaded: dict[str, Any], payload: bytes) -> None:
    """Check the file metadata returned by Zenodo when it is available."""

    uploaded_size = _reported_file_size(uploaded)
    if uploaded_size is not None and uploaded_size != len(payload):
        raise ZenodoError(
            f"Zenodo reports {uploaded_size:,} uploaded bytes; sent {len(payload):,}"
        )
    checksum = uploaded.get("checksum")
    if checksum is not None:
        if not isinstance(checksum, str):
            raise ZenodoError("Zenodo upload checksum is not text")
        if re.fullmatch(r"md5:[0-9a-f]{32}", checksum):
            reported_md5 = checksum.removeprefix("md5:")
        elif re.fullmatch(r"[0-9a-f]{32}", checksum):
            reported_md5 = checksum
        else:
            raise ZenodoError("Zenodo upload checksum is not an exact MD5")
        actual = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        if reported_md5 != actual:
            raise ZenodoError(
                f"Zenodo upload checksum mismatch: expected md5:{actual}, got {checksum}"
            )


def _reported_file_size(file_metadata: dict[str, Any]) -> int | None:
    """Normalize the exact size fields used by public and deposition APIs."""

    size = file_metadata.get("size")
    legacy_size = file_metadata.get("filesize")
    for name, value in (("size", size), ("filesize", legacy_size)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise ZenodoError(f"Zenodo file {name} is not an exact byte count")
    if size is not None and legacy_size is not None and size != legacy_size:
        raise ZenodoError("Zenodo file size and filesize fields conflict")
    return size if size is not None else legacy_size


def _required_string(mapping: dict[str, Any], key: str) -> str:
    """Return a non-empty manifest string or fail with a useful diagnostic."""

    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ZenodoError(f"deposition must declare a non-empty {key}")
    return value.strip()


def _required_record_id(mapping: dict[str, Any], key: str) -> int:
    """Return a positive Zenodo record identifier from a correction manifest."""

    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ZenodoError(f"deposition must declare a positive {key}")
    return value


def _operation_identity(deposition: dict[str, Any]) -> str:
    """Return the durable operation/version/asset identity for a manifest."""

    synthpopcan = deposition.get("synthpopcan")
    metadata = deposition.get("metadata")
    if not isinstance(synthpopcan, dict) or not isinstance(metadata, dict):
        raise ZenodoError("deposition must carry metadata and SynthPopCan metadata")
    operation = _required_string(synthpopcan, "deposit_operation")
    if operation not in _SUPPORTED_OPERATIONS:
        raise ZenodoError(f"unsupported deposit operation: {operation}")
    model_id = _required_string(synthpopcan, "model_id")

    if operation == "correct-existing-metadata":
        version = _required_string(synthpopcan, "existing_package_version")
        historical = synthpopcan.get("historical_asset")
        if not isinstance(historical, dict):
            raise ZenodoError("metadata correction must identify the historical_asset")
        asset_sha256 = _required_string(historical, "sha256").lower()
    else:
        version = _required_string(metadata, "version")
        asset_sha256 = _required_string(synthpopcan, "sha256").lower()

    if len(asset_sha256) != 64:
        raise ZenodoError("operation identity requires a SHA-256 asset checksum")
    desired_metadata = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    metadata_sha256 = hashlib.sha256(desired_metadata).hexdigest()
    return f"{operation}:{model_id}:{version}:{asset_sha256}:{metadata_sha256}"


def _operation_asset_sha256(deposition: dict[str, Any]) -> str:
    """Return the candidate or historical digest bound into an operation."""

    synthpopcan = deposition["synthpopcan"]
    if synthpopcan["deposit_operation"] == "correct-existing-metadata":
        historical = synthpopcan["historical_asset"]
        return str(historical["sha256"]).lower()
    return str(synthpopcan["sha256"]).lower()


def _correction_operation_descriptor(
    deposition: dict[str, Any],
) -> dict[str, Any]:
    """Return the execution-index descriptor for one correction manifest."""

    synthpopcan = deposition["synthpopcan"]
    operation = str(synthpopcan["deposit_operation"])
    if operation not in {"correct-existing-metadata", "create-new-version"}:
        raise ZenodoError("execution authority accepts correction operations only")
    descriptor: dict[str, Any] = {
        "operation_id": _operation_identity(deposition),
        "deposit_operation": operation,
        "model_id": str(synthpopcan["model_id"]),
        "package_version": (
            str(synthpopcan["existing_package_version"])
            if operation == "correct-existing-metadata"
            else str(deposition["metadata"]["version"])
        ),
        "asset_sha256": _operation_asset_sha256(deposition),
        "metadata_sha256": _operation_identity(deposition).rsplit(":", 1)[-1],
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


def _canonical_document_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _read_correction_execution_index(source: Path) -> dict[str, Any]:
    path = source / "execution-index.json"
    if not path.is_file():
        raise click.UsageError(
            f"correction manifests require the execution index {path}"
        )
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise click.UsageError("correction execution index must be an object")
    return document


def _validate_correction_execution_authority(
    depositions: list[dict[str, Any]], *, source: Path
) -> dict[str, Any] | None:
    """Bind every correction manifest to one immutable pre-write authority."""

    corrections = [
        item
        for item in depositions
        if item.get("synthpopcan", {}).get("deposit_operation")
        in {"correct-existing-metadata", "create-new-version"}
    ]
    if not corrections:
        return None
    if len(corrections) != len(depositions):
        raise click.UsageError(
            "a correction bundle cannot mix correction and fresh-record manifests"
        )
    index = _read_correction_execution_index(source)
    if index.get("schema_version") != (
        "synthpopcan-zenodo-correction-execution-index-v1"
    ):
        raise click.UsageError("unsupported correction execution index schema")
    operations = index.get("operations")
    if not isinstance(operations, list):
        raise click.UsageError("correction execution index lacks operations")
    candidate_ids = index.get("candidate_model_ids")
    candidate_count = index.get("candidate_count")
    if (
        not isinstance(candidate_ids, list)
        or candidate_ids != sorted(set(candidate_ids))
        or candidate_count != len(candidate_ids)
        or len(operations) != 2 * len(candidate_ids)
    ):
        raise click.UsageError("correction execution index coverage is inconsistent")
    if index.get("production_ready") is True and (
        index.get("build_scope") != "complete-catalogue"
        or candidate_count != 32
        or len(operations) != 64
    ):
        raise click.UsageError(
            "production correction authority requires exactly 32 models/64 operations"
        )
    candidate_envelope_sha256 = index.get("candidate_envelope_sha256")
    if (
        not isinstance(candidate_envelope_sha256, str)
        or len(candidate_envelope_sha256) != 64
    ):
        raise click.UsageError("correction index lacks its candidate-envelope digest")
    index_sha256 = _canonical_document_sha256(index)
    descriptors = sorted(
        (_correction_operation_descriptor(item) for item in corrections),
        key=lambda item: str(item["operation_id"]),
    )
    indexed = sorted(operations, key=lambda item: str(item.get("operation_id")))
    if descriptors != indexed:
        raise click.UsageError(
            "correction manifests do not exactly match the execution index"
        )
    pairs = {(item["model_id"], item["deposit_operation"]) for item in descriptors}
    expected_pairs = {
        (model_id, operation)
        for model_id in candidate_ids
        for operation in ("correct-existing-metadata", "create-new-version")
    }
    if pairs != expected_pairs:
        raise click.UsageError("correction index lacks an exact operation pair")
    for deposition, descriptor in zip(
        sorted(
            corrections,
            key=lambda item: str(_operation_identity(item)),
        ),
        descriptors,
        strict=True,
    ):
        synthpopcan = deposition["synthpopcan"]
        if (
            synthpopcan.get("candidate_envelope_sha256") != candidate_envelope_sha256
            or synthpopcan.get("execution_index_schema") != index["schema_version"]
            or synthpopcan.get("execution_index_sha256") != index_sha256
            or synthpopcan.get("execution_operation_id") != descriptor["operation_id"]
        ):
            raise click.UsageError(
                "correction manifest lacks exact execution-authority bindings"
            )
    return index


def _require_production_correction_authority(
    deposition: dict[str, Any], execution_index: dict[str, Any] | None
) -> None:
    """Require the selected operation to belong to the exact full authority."""

    if execution_index is None:
        raise ZenodoError("production correction lacks its execution authority")
    if (
        execution_index.get("production_ready") is not True
        or execution_index.get("candidate_count") != 32
        or len(execution_index.get("operations", [])) != 64
    ):
        raise ZenodoError("production correction authority is not complete")
    descriptor = _correction_operation_descriptor(deposition)
    if descriptor not in execution_index["operations"]:
        raise ZenodoError("correction operation is not in the execution authority")
    synthpopcan = deposition["synthpopcan"]
    if (
        synthpopcan.get("candidate_envelope_sha256")
        != execution_index.get("candidate_envelope_sha256")
        or synthpopcan.get("execution_index_schema")
        != execution_index.get("schema_version")
        or synthpopcan.get("execution_index_sha256")
        != _canonical_document_sha256(execution_index)
        or synthpopcan.get("execution_operation_id") != descriptor["operation_id"]
    ):
        raise ZenodoError("correction manifest is not bound to this execution index")


def _validate_correction_manifest_readiness(deposition: dict[str, Any]) -> None:
    """Require a complete, checksum-bound candidate envelope for correction writes."""

    synthpopcan = deposition["synthpopcan"]
    operation = synthpopcan["deposit_operation"]
    if operation not in {"correct-existing-metadata", "create-new-version"}:
        return
    if synthpopcan.get("production_ready") is not True:
        raise ZenodoError("correction manifest is not production-ready")
    if synthpopcan.get("build_scope") != "complete-catalogue":
        raise ZenodoError("correction manifest does not come from complete coverage")
    if synthpopcan.get("candidate_envelope_schema") != (
        "synthpopcan-zenodo-correction-candidates-v1"
    ):
        raise ZenodoError("correction manifest lacks the candidate envelope binding")
    if synthpopcan.get("transformation") != (
        "rights-metadata-only-top-level-field-insertion"
    ):
        raise ZenodoError("correction manifest transformation is not supported")
    if synthpopcan.get("model_retrained") is not False:
        raise ZenodoError("correction manifest must prove the model was not retrained")
    if synthpopcan.get("historical_json_preserved_except_inserted_licensing") is not (
        True
    ):
        raise ZenodoError("correction manifest must prove historical JSON preservation")
    if synthpopcan.get("package_schema_version") != (
        "synthpopcan-linked-tree-package-v1"
    ):
        raise ZenodoError("correction manifest package schema is unsupported")
    if synthpopcan.get("package_type") != "linked_household_person":
        raise ZenodoError("correction manifest package type is unsupported")
    licensing = synthpopcan.get("licensing")
    if not isinstance(licensing, dict) or synthpopcan.get(
        "licensing_schema_version"
    ) != licensing.get("schema_version"):
        raise ZenodoError("correction manifest licensing schema binding does not match")
    source = licensing.get("source_information")
    product = source.get("product") if isinstance(source, dict) else None
    vintage = synthpopcan.get("census_vintage")
    census_year = (
        _CENSUS_VINTAGE_YEAR.get(vintage) if isinstance(vintage, str) else None
    )
    reference_year = (
        product.get("reference_year") if isinstance(product, dict) else None
    )
    if (
        census_year is None
        or not isinstance(reference_year, int)
        or isinstance(reference_year, bool)
        or reference_year != census_year
    ):
        raise ZenodoError("correction manifest Census vintage binding does not match")
    model_id = synthpopcan.get("model_id")
    if not isinstance(model_id, str) or f"-{census_year}-" not in model_id:
        raise ZenodoError(
            "correction manifest model identity does not match its vintage"
        )
    historical = synthpopcan.get("historical_asset")
    if (
        not isinstance(historical, dict)
        or historical.get("contains_embedded_licensing") is not False
    ):
        raise ZenodoError("correction manifest lacks exact historical evidence")
    for field in ("filename", "size_bytes", "sha256"):
        if historical.get(field) in {None, ""}:
            raise ZenodoError(f"correction historical asset lacks {field}")
    for field in ("sha256", "uncompressed_sha256"):
        value = historical.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise ZenodoError(f"correction historical asset lacks exact {field}")
    for field in ("size_bytes", "uncompressed_size_bytes"):
        value = historical.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ZenodoError(f"correction historical asset lacks exact {field}")
    if operation == "create-new-version":
        candidate = synthpopcan.get("candidate_asset")
        if (
            not isinstance(candidate, dict)
            or candidate.get("contains_embedded_licensing") is not True
        ):
            raise ZenodoError("new-version manifest lacks exact candidate evidence")
        for field in (
            "filename",
            "asset_url",
            "size_bytes",
            "sha256",
            "uncompressed_size_bytes",
            "uncompressed_sha256",
        ):
            if candidate.get(field) != synthpopcan.get(field):
                raise ZenodoError(
                    f"new-version nested/flat candidate {field} does not match"
                )


def _legacy_result_identity(result: dict[str, Any]) -> str:
    """Quarantine old model-only checkpoints so they never skip a new action."""

    model_id = str(result.get("model_id", "unknown"))
    deposition_id = str(result.get("deposition_id", "unknown"))
    state = str(result.get("state", "unknown"))
    return f"legacy:{model_id}:{state}:{deposition_id}"


def _candidate_filename(
    deposition: dict[str, Any], *, operation: str, model_id: str
) -> str:
    """Return a safe candidate filename, enforcing non-overwrite for versions."""

    synthpopcan = deposition["synthpopcan"]
    metadata = deposition["metadata"]
    filename_value = synthpopcan.get("filename")
    if filename_value is None and operation == "create-new-record":
        filename_value = f"{model_id}-package.json.gz"
    if not isinstance(filename_value, str) or not filename_value:
        raise ZenodoError("asset operation must declare a candidate filename")
    filename = Path(filename_value).name
    if filename != filename_value or filename in {".", ".."}:
        raise ZenodoError("candidate filename must be a plain file name")

    if operation == "create-new-version":
        version = _required_string(metadata, "version")
        historical = synthpopcan.get("historical_asset")
        if not isinstance(historical, dict):
            raise ZenodoError("new version must identify the historical_asset")
        historical_filename = _required_string(historical, "filename")
        if filename == historical_filename:
            raise ZenodoError(
                "corrected version filename must not overwrite the historical file"
            )
        if version not in filename:
            raise ZenodoError(
                "corrected version filename must include the new package version"
            )
    return filename


def _record_doi(record: dict[str, Any]) -> str | None:
    """Extract a version DOI from a legacy deposition or published record."""

    direct = record.get("doi")
    if isinstance(direct, str) and direct:
        return direct
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None
    metadata_doi = metadata.get("doi")
    if isinstance(metadata_doi, str) and metadata_doi:
        return metadata_doi
    reserved = metadata.get("prereserve_doi")
    if isinstance(reserved, dict):
        doi = reserved.get("doi")
        if isinstance(doi, str) and doi:
            return doi
    return None


def _concept_doi(record: dict[str, Any]) -> str | None:
    """Extract a concept DOI from a legacy deposition or published record."""

    direct = record.get("conceptdoi")
    if isinstance(direct, str) and direct:
        return direct
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("conceptdoi")
        if isinstance(value, str) and value:
            return value
    return None


def _operation_marker_value(
    line: str,
    *,
    prefix: str,
    suffix: str = "",
    label: str,
) -> str | None:
    """Parse one reserved marker line without accepting near-matches."""

    if not line.startswith(prefix):
        return None
    if suffix and not line.endswith(suffix):
        raise ZenodoError(f"malformed {label} marker")
    value_end = -len(suffix) if suffix else None
    value = line[len(prefix) : value_end]
    if _OPERATION_MARKER.fullmatch(value) is None:
        raise ZenodoError(f"malformed {label} marker")
    return value


def _marker_values(
    notes: str,
    *,
    prefix: str,
    suffix: str = "",
    label: str,
) -> list[str]:
    """Return all exact reserved marker values, rejecting malformed lines."""

    values: list[str] = []
    for line in notes.splitlines():
        value = _operation_marker_value(
            line,
            prefix=prefix,
            suffix=suffix,
            label=label,
        )
        if value is not None:
            values.append(value)
    return values


def _one_marker_value(
    notes: str,
    *,
    prefix: str,
    suffix: str = "",
    label: str,
) -> str | None:
    """Return at most one exact marker value."""

    values = _marker_values(notes, prefix=prefix, suffix=suffix, label=label)
    if len(values) > 1:
        raise ZenodoError(f"Zenodo metadata contains ambiguous {label} markers")
    return values[0] if values else None


def _logical_newversion_authority_marker(operation_id: str) -> str:
    """Return the manifest marker whose bytes are bound into operation IDs."""

    if _OPERATION_MARKER.fullmatch(operation_id) is None:
        raise ZenodoError("new-version authority has a malformed operation identity")
    return f"{_NEWVERSION_AUTHORITY_PREFIX}{operation_id} -->"


def _durable_newversion_authority_marker(operation_id: str) -> str:
    """Return the visible authority line sent to Zenodo."""

    if _OPERATION_MARKER.fullmatch(operation_id) is None:
        raise ZenodoError("new-version authority has a malformed operation identity")
    return f"{_DURABLE_NEWVERSION_AUTHORITY_PREFIX}{operation_id}"


def _metadata_for_transport(metadata: dict[str, Any]) -> dict[str, Any]:
    """Encode logical manifest authority as Zenodo-preserved plain text."""

    transported = json.loads(json.dumps(metadata))
    notes = transported.get("notes")
    if notes is None:
        return transported
    if not isinstance(notes, str):
        raise ZenodoError("Zenodo notes must be text")
    if any(
        line.startswith(
            (_DURABLE_OWNERSHIP_PREFIX, _DURABLE_NEWVERSION_AUTHORITY_PREFIX)
        )
        for line in notes.splitlines()
    ):
        raise ZenodoError("manifest notes must not contain transport markers")
    logical_authority = _one_marker_value(
        notes,
        prefix=_NEWVERSION_AUTHORITY_PREFIX,
        suffix=" -->",
        label="logical new-version authority",
    )
    lines = []
    for line in notes.splitlines():
        if (
            logical_authority is not None
            and line == _logical_newversion_authority_marker(logical_authority)
        ):
            lines.append(_durable_newversion_authority_marker(logical_authority))
        else:
            lines.append(line)
    transported["notes"] = "\n".join(lines)
    return transported


def _canonical_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize input/response shapes and marker transport representation."""

    canonical = json.loads(json.dumps(metadata))
    upload_type = canonical.pop("upload_type", None)
    resource_type = canonical.get("resource_type")
    if upload_type is not None:
        canonical["resource_type"] = upload_type
    elif isinstance(resource_type, dict):
        canonical["resource_type"] = resource_type.get("id", resource_type.get("type"))
    licence = canonical.get("license")
    if isinstance(licence, dict):
        canonical["license"] = licence.get("id")
    creators = canonical.get("creators")
    if isinstance(creators, list):
        canonical["creators"] = [
            {key: value for key, value in creator.items() if value is not None}
            if isinstance(creator, dict)
            else creator
            for creator in creators
        ]
    notes = canonical.get("notes")
    if isinstance(notes, str):
        ownership = _one_marker_value(
            notes,
            prefix=_DURABLE_OWNERSHIP_PREFIX,
            label="executor ownership",
        )
        durable_authority = _one_marker_value(
            notes,
            prefix=_DURABLE_NEWVERSION_AUTHORITY_PREFIX,
            label="durable new-version authority",
        )
        logical_authority = _one_marker_value(
            notes,
            prefix=_NEWVERSION_AUTHORITY_PREFIX,
            suffix=" -->",
            label="logical new-version authority",
        )
        if durable_authority is not None and logical_authority is not None:
            raise ZenodoError("Zenodo metadata contains duplicate authority forms")
        lines: list[str] = []
        for line in notes.splitlines():
            if ownership is not None and line == _ownership_marker(ownership):
                continue
            if (
                durable_authority is not None
                and line == _durable_newversion_authority_marker(durable_authority)
            ):
                lines.append(_logical_newversion_authority_marker(durable_authority))
            else:
                lines.append(line)
        normalized_notes = "\n".join(lines).rstrip()
        if normalized_notes:
            canonical["notes"] = normalized_notes
        else:
            canonical.pop("notes", None)
    return canonical


def _assert_metadata_subset(expected: object, actual: object, *, path: str) -> None:
    """Require all submitted metadata values to survive Zenodo normalization."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ZenodoError(f"Zenodo metadata mismatch at {path}")
        for key, value in expected.items():
            if key not in actual:
                raise ZenodoError(f"Zenodo metadata omitted {path}.{key}")
            _assert_metadata_subset(value, actual[key], path=f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise ZenodoError(f"Zenodo metadata mismatch at {path}")
        for index, value in enumerate(expected):
            _assert_metadata_subset(value, actual[index], path=f"{path}[{index}]")
        return
    if expected != actual:
        raise ZenodoError(f"Zenodo metadata mismatch at {path}")


def _ownership_marker(operation_id: str) -> str:
    """Return the exact visible executor-ownership line sent to Zenodo."""

    if _OPERATION_MARKER.fullmatch(operation_id) is None:
        raise ZenodoError("executor ownership has a malformed operation identity")
    return f"{_DURABLE_OWNERSHIP_PREFIX}{operation_id}"


def _metadata_with_ownership(
    metadata: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Return desired metadata carrying one durable executor ownership marker."""

    claimed = _metadata_for_transport(metadata)
    notes = claimed.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ZenodoError("Zenodo notes must be text before executor ownership")
    if isinstance(notes, str):
        if (
            _one_marker_value(
                notes,
                prefix=_DURABLE_OWNERSHIP_PREFIX,
                label="executor ownership",
            )
            is not None
        ):
            raise ZenodoError(
                "desired Zenodo notes must not contain an ownership marker"
            )
        if any(line.startswith(_OWNERSHIP_PREFIX) for line in notes.splitlines()):
            raise ZenodoError(
                "desired Zenodo notes must not contain a logical ownership marker"
            )
    marker = _ownership_marker(operation_id)
    claimed["notes"] = f"{notes.rstrip()}\n\n{marker}" if notes else marker
    return claimed


def _draft_ownership(draft: dict[str, Any]) -> str | None:
    """Extract one exact operation identity from draft notes."""

    metadata = draft.get("metadata")
    notes = metadata.get("notes") if isinstance(metadata, dict) else None
    if not isinstance(notes, str):
        return None
    if any(line.startswith(_OWNERSHIP_PREFIX) for line in notes.splitlines()):
        raise ZenodoError("Zenodo draft contains non-durable executor ownership")
    return _one_marker_value(
        notes,
        prefix=_DURABLE_OWNERSHIP_PREFIX,
        label="executor ownership",
    )


def _require_newversion_authority(existing: dict[str, Any], operation_id: str) -> None:
    """Require the predecessor metadata correction to authorize this version."""

    metadata = existing.get("metadata")
    notes = metadata.get("notes") if isinstance(metadata, dict) else None
    authority = (
        _one_marker_value(
            notes,
            prefix=_DURABLE_NEWVERSION_AUTHORITY_PREFIX,
            label="durable new-version authority",
        )
        if isinstance(notes, str)
        else None
    )
    if authority != operation_id:
        raise ZenodoError(
            "latest record metadata does not authorize this exact new-version operation"
        )


def _without_inherited_ownership(
    draft: dict[str, Any], inherited_owner: str
) -> dict[str, Any]:
    """Return an unowned local view after proving one inherited source marker."""

    if _draft_ownership(draft) != inherited_owner:
        raise ZenodoError("draft does not carry the expected inherited ownership")
    unowned = json.loads(json.dumps(draft))
    metadata = unowned.get("metadata")
    if not isinstance(metadata, dict):
        raise ZenodoError("inherited draft lacks metadata")
    notes = metadata.get("notes")
    if not isinstance(notes, str):
        raise ZenodoError("inherited draft lacks its ownership marker")
    marker = _ownership_marker(inherited_owner)
    lines = notes.splitlines()
    if lines.count(marker) != 1:
        raise ZenodoError("inherited draft lacks one exact ownership marker")
    metadata["notes"] = "\n".join(line for line in lines if line != marker).rstrip()
    if not metadata["notes"]:
        metadata.pop("notes")
    return unowned


def _doi_record_id(doi: str) -> str:
    suffix = doi.rsplit(".", 1)[-1]
    if not suffix.isdigit():
        raise ZenodoError("Zenodo DOI does not end in a record identifier")
    return suffix


def _assert_draft_binding(
    draft: dict[str, Any],
    deposition: dict[str, Any],
    *,
    operation_id: str,
    require_owned: bool,
) -> None:
    """Bind a mutable draft to the exact record, concept, operation, and DOI."""

    synthpopcan = deposition["synthpopcan"]
    operation = synthpopcan["deposit_operation"]
    draft_id = _required_record_id(draft, "id")
    owner = _draft_ownership(draft)
    if require_owned and owner != operation_id:
        raise ZenodoError("Zenodo draft is not owned by this exact operation")
    if owner is not None and owner != operation_id:
        raise ZenodoError("Zenodo draft is owned by a different operation")
    if operation == "correct-existing-metadata":
        if draft_id != synthpopcan["existing_record_id"]:
            raise ZenodoError("metadata edit draft changed the existing record ID")
        if _record_doi(draft) != synthpopcan["existing_version_doi"]:
            raise ZenodoError("metadata edit draft changed the version DOI")
        if _concept_doi(draft) != synthpopcan["existing_concept_doi"]:
            raise ZenodoError("metadata edit draft changed the concept DOI")
        return
    if operation == "create-new-version":
        if draft_id == synthpopcan["existing_record_id"]:
            raise ZenodoError("new-version draft reused the historical record ID")
        concept_doi = synthpopcan["existing_concept_doi"]
        if _concept_doi(draft) != concept_doi:
            raise ZenodoError("new-version draft belongs to another concept DOI")
        conceptrecid = draft.get("conceptrecid")
        if str(conceptrecid) != _doi_record_id(str(concept_doi)):
            raise ZenodoError("new-version draft parent concept does not match")
        reserved_doi = _record_doi(draft)
        if not reserved_doi or reserved_doi == synthpopcan["existing_version_doi"]:
            raise ZenodoError("new-version draft lacks a distinct reserved DOI")


def _canonical_owned_draft_metadata(
    draft: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Normalize only exact server-derived fields on an already-owned draft."""

    metadata = draft.get("metadata")
    if not isinstance(metadata, dict):
        raise ZenodoError("owned Zenodo draft lacks metadata")
    canonical = _canonical_metadata(metadata)
    expected = _canonical_metadata(transport_metadata)
    for field, envelope_value in (
        ("doi", _record_doi(draft)),
        ("conceptdoi", _concept_doi(draft)),
    ):
        if field not in expected and field in canonical:
            if not envelope_value or canonical[field] != envelope_value:
                raise ZenodoError(f"owned Zenodo draft has an unexpected {field}")
            canonical.pop(field)
    if "publication_date" not in expected and "publication_date" in canonical:
        value = canonical.pop("publication_date")
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None
        ):
            raise ZenodoError("owned Zenodo draft has a malformed publication date")
    publisher = canonical.pop("imprint_publisher", None)
    if publisher is not None and publisher != "Zenodo":
        raise ZenodoError("owned Zenodo draft has an unexpected publisher imprint")
    reserved = canonical.pop("prereserve_doi", None)
    if reserved is not None:
        record_id = draft.get("id")
        if (
            not isinstance(reserved, dict)
            or set(reserved) not in ({"doi"}, {"doi", "recid"})
            or reserved.get("doi") != _record_doi(draft)
            or ("recid" in reserved and str(reserved.get("recid")) != str(record_id))
        ):
            raise ZenodoError("owned Zenodo draft has malformed reserved DOI data")
    related = canonical.get("related_identifiers")
    if isinstance(related, list):
        normalized_related: list[object] = []
        for item in related:
            if not isinstance(item, dict):
                normalized_related.append(item)
                continue
            normalized = item.copy()
            scheme = normalized.pop("scheme", None)
            if scheme is not None and scheme != _expected_identifier_scheme(
                normalized.get("identifier")
            ):
                raise ZenodoError("owned Zenodo draft has an unexpected scheme")
            normalized_related.append(normalized)
        canonical["related_identifiers"] = normalized_related
    if draft.get("state") in {"done", "published"}:
        canonical.pop("relations", None)
    return canonical


def _assert_owned_draft_metadata(
    draft: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
) -> None:
    """Require exact intended metadata before trusting an owner-bearing draft."""

    actual = _canonical_owned_draft_metadata(
        draft,
        transport_metadata=transport_metadata,
    )
    expected = _canonical_metadata(transport_metadata)
    if actual != expected:
        raise ZenodoError("owned Zenodo draft metadata is not the intended payload")


def _claim_draft(
    draft: dict[str, Any],
    deposition: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
    operation_id: str,
    api: str,
    token: str,
) -> dict[str, Any]:
    """Persist and verify operation ownership before any destructive draft action."""

    owner = _draft_ownership(draft)
    if owner is not None:
        _assert_draft_binding(
            draft, deposition, operation_id=operation_id, require_owned=True
        )
        _assert_owned_draft_metadata(
            draft,
            transport_metadata=transport_metadata,
        )
        return draft
    _assert_draft_binding(
        draft, deposition, operation_id=operation_id, require_owned=False
    )
    claimed_metadata = _metadata_with_ownership(transport_metadata, operation_id)
    claimed = _request(
        "PUT",
        f"{api}/deposit/depositions/{draft['id']}",
        token=token,
        payload={"metadata": claimed_metadata},
    )
    _assert_draft_binding(
        claimed, deposition, operation_id=operation_id, require_owned=True
    )
    response_metadata = claimed.get("metadata")
    if not isinstance(response_metadata, dict):
        raise ZenodoError("Zenodo ownership claim returned no metadata")
    _assert_metadata_subset(
        _canonical_metadata(claimed_metadata),
        _canonical_metadata(response_metadata),
        path="metadata",
    )
    return claimed


def _normalized_source_files(record: dict[str, Any]) -> list[str]:
    """Return a representation shared by public and legacy draft file shapes."""

    values = record.get("files")
    if not isinstance(values, list):
        raise ZenodoError("unclaimed draft lacks comparable source files")
    normalized: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            raise ZenodoError("unclaimed draft contains malformed source files")
        checksum = item.get("checksum")
        if isinstance(checksum, str) and re.fullmatch(r"md5:[0-9a-f]{32}", checksum):
            checksum = checksum.removeprefix("md5:")
        normalized.append(
            json.dumps(
                {
                    "filename": item.get("filename", item.get("key")),
                    "size": _reported_file_size(item),
                    "checksum": checksum,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return sorted(normalized)


def _assert_same_source_files(draft: dict[str, Any], existing: dict[str, Any]) -> None:
    """Require the draft to contain exactly the bound historical source files."""

    if _normalized_source_files(draft) != _normalized_source_files(existing):
        raise ZenodoError("unclaimed draft is not an untouched source snapshot")


def _assert_unclaimed_draft_snapshot(
    draft: dict[str, Any], existing: dict[str, Any]
) -> None:
    """Allow intent recovery only for an untouched snapshot of the source record."""

    draft_metadata = draft.get("metadata")
    existing_metadata = existing.get("metadata")
    if not isinstance(draft_metadata, dict) or not isinstance(existing_metadata, dict):
        raise ZenodoError("unclaimed draft lacks comparable source metadata")
    canonical_existing = _canonical_metadata(existing_metadata)
    canonical_draft = _canonical_metadata(draft_metadata)
    for transient in ("doi", "conceptdoi"):
        canonical_existing.pop(transient, None)
        canonical_draft.pop(transient, None)
    # Zenodo's public-record and legacy-deposition serializers add different
    # derived fields to the same untouched record.  Keep this directional:
    # ``relations`` is public-only, while the DOI reservation and publisher
    # imprint are draft-only.  A field on the other side remains substantive.
    canonical_existing.pop("relations", None)
    for transient in ("imprint_publisher", "prereserve_doi"):
        canonical_draft.pop(transient, None)
    if canonical_draft != canonical_existing:
        raise ZenodoError("unclaimed draft metadata is not an untouched snapshot")
    _assert_same_source_files(draft, existing)


def _remove_exact_transport_markers(
    metadata: dict[str, Any],
    *,
    ownership_operation_id: str,
) -> dict[str, Any]:
    """Remove exactly one ownership and authority line for legacy comparison."""

    cleaned = json.loads(json.dumps(metadata))
    notes = cleaned.get("notes")
    if not isinstance(notes, str):
        raise ZenodoError("legacy recovery intended metadata lacks marker notes")
    owner = _one_marker_value(
        notes,
        prefix=_DURABLE_OWNERSHIP_PREFIX,
        label="executor ownership",
    )
    authority = _one_marker_value(
        notes,
        prefix=_DURABLE_NEWVERSION_AUTHORITY_PREFIX,
        label="durable new-version authority",
    )
    if owner != ownership_operation_id or authority is None:
        raise ZenodoError("legacy recovery intended metadata lacks exact markers")
    removed = {
        _ownership_marker(owner),
        _durable_newversion_authority_marker(authority),
    }
    lines = notes.splitlines()
    if sum(line in removed for line in lines) != 2:
        raise ZenodoError("legacy recovery intended metadata has ambiguous markers")
    normalized = "\n".join(line for line in lines if line not in removed).rstrip()
    if normalized:
        cleaned["notes"] = normalized
    else:
        cleaned.pop("notes", None)
    return cleaned


def _expected_identifier_scheme(identifier: object) -> str | None:
    """Return the only legacy-deposition scheme accepted as a derived extra."""

    if not isinstance(identifier, str):
        return None
    if re.fullmatch(r"10\.[0-9]{4,9}/\S+", identifier):
        return "doi"
    if identifier.startswith(("https://", "http://")):
        return "url"
    return None


def _canonical_legacy_recovery_draft_metadata(
    metadata: dict[str, Any],
    *,
    deposition: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    """Remove only the observed, validated server extras from the legacy draft."""

    canonical = _canonical_metadata(metadata)
    synthpopcan = deposition["synthpopcan"]
    draft_doi = canonical.pop("doi", None)
    if draft_doi != synthpopcan["existing_version_doi"]:
        raise ZenodoError("legacy recovery draft has an unexpected metadata DOI")
    publication_date = canonical.get("publication_date")
    existing_metadata = existing.get("metadata")
    existing_date = (
        existing_metadata.get("publication_date")
        if isinstance(existing_metadata, dict)
        else None
    )
    if publication_date not in {
        existing_date,
        _LEGACY_STRIPPED_MARKER_STAGED_PUBLICATION_DATE,
    }:
        raise ZenodoError("legacy recovery draft has an unexpected publication date")
    canonical["publication_date"] = existing_date
    publisher = canonical.pop("imprint_publisher", None)
    if publisher != "Zenodo":
        raise ZenodoError("legacy recovery draft has an unexpected publisher imprint")
    reserved = canonical.pop("prereserve_doi", None)
    if not isinstance(reserved, dict) or set(reserved) != {"doi", "recid"}:
        raise ZenodoError("legacy recovery draft has malformed reserved DOI data")
    if reserved.get("doi") != synthpopcan["existing_version_doi"]:
        raise ZenodoError("legacy recovery draft reserved a different DOI")
    if str(reserved.get("recid")) != str(synthpopcan["existing_record_id"]):
        raise ZenodoError("legacy recovery draft reserved a different record")
    related = canonical.get("related_identifiers")
    if not isinstance(related, list):
        raise ZenodoError("legacy recovery draft lacks related identifiers")
    normalized_related: list[object] = []
    for item in related:
        if not isinstance(item, dict):
            raise ZenodoError("legacy recovery draft has malformed related identifiers")
        normalized = item.copy()
        scheme = normalized.pop("scheme", None)
        if scheme != _expected_identifier_scheme(normalized.get("identifier")):
            raise ZenodoError(
                "legacy recovery draft has an unexpected identifier scheme"
            )
        normalized_related.append(normalized)
    canonical["related_identifiers"] = normalized_related
    return canonical


def _legacy_recovery_checkpoint(
    deposition: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Return the single action-intent checkpoint shape accepted for recovery."""

    synthpopcan = deposition["synthpopcan"]
    return {
        "operation_id": operation_id,
        "deposit_operation": "correct-existing-metadata",
        "model_id": synthpopcan["model_id"],
        "package_version": synthpopcan["existing_package_version"],
        "asset_sha256": synthpopcan["historical_asset"]["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": synthpopcan["existing_record_id"],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }


def _may_read_direct_legacy_recovery_draft(
    deposition: dict[str, Any],
    *,
    operation_id: str,
    resume: dict[str, Any] | None,
    api: str,
) -> bool:
    """Limit the direct draft probe to the exact interrupted production edit."""

    synthpopcan = deposition["synthpopcan"]
    return (
        api.rstrip("/") == PRODUCTION_API
        and operation_id == _LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID
        and resume == _legacy_recovery_checkpoint(deposition, operation_id)
        and synthpopcan.get("deposit_operation") == "correct-existing-metadata"
        and synthpopcan.get("existing_record_id")
        == _LEGACY_STRIPPED_MARKER_RECOVERY_RECORD_ID
        and synthpopcan.get("existing_version_doi")
        == _LEGACY_STRIPPED_MARKER_RECOVERY_VERSION_DOI
        and synthpopcan.get("existing_concept_doi")
        == _LEGACY_STRIPPED_MARKER_RECOVERY_CONCEPT_DOI
    )


def _assert_exact_legacy_stripped_marker_claim(
    draft: dict[str, Any],
    existing: dict[str, Any],
    deposition: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
    operation_id: str,
    resume: dict[str, Any],
) -> None:
    """Authorize only the one HTML-stripped production claim already in flight."""

    if operation_id != _LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID:
        raise ZenodoError("legacy stripped-marker recovery is not authorized")
    if resume != _legacy_recovery_checkpoint(deposition, operation_id):
        raise ZenodoError("legacy recovery checkpoint is not the exact action intent")
    if draft.get("state") != "inprogress" or draft.get("submitted") is not True:
        raise ZenodoError("legacy recovery draft is not the exact open edit state")
    _assert_draft_binding(
        draft,
        deposition,
        operation_id=operation_id,
        require_owned=False,
    )
    if _draft_ownership(draft) is not None:
        raise ZenodoError("legacy recovery draft unexpectedly has an owner")
    _assert_same_source_files(draft, existing)
    intended_transport = _metadata_with_ownership(transport_metadata, operation_id)
    expected_metadata = _canonical_metadata(
        _remove_exact_transport_markers(
            intended_transport,
            ownership_operation_id=operation_id,
        )
    )
    draft_metadata = draft.get("metadata")
    if not isinstance(draft_metadata, dict):
        raise ZenodoError("legacy recovery draft lacks metadata")
    actual_metadata = _canonical_legacy_recovery_draft_metadata(
        draft_metadata,
        deposition=deposition,
        existing=existing,
    )
    if actual_metadata != expected_metadata:
        raise ZenodoError("legacy recovery draft metadata is not the intended payload")


def _assert_exact_durable_owned_recovery_claim(
    draft: dict[str, Any],
    existing: dict[str, Any],
    deposition: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
    operation_id: str,
) -> None:
    """Verify the exact post-claim/pre-checkpoint state of the one live edit."""

    _assert_draft_binding(
        draft,
        deposition,
        operation_id=operation_id,
        require_owned=True,
    )
    _assert_same_source_files(draft, existing)
    draft_metadata = draft.get("metadata")
    if not isinstance(draft_metadata, dict):
        raise ZenodoError("owned legacy recovery draft lacks metadata")
    actual_metadata = _canonical_legacy_recovery_draft_metadata(
        draft_metadata,
        deposition=deposition,
        existing=existing,
    )
    expected_metadata = _canonical_metadata(transport_metadata)
    if actual_metadata != expected_metadata:
        raise ZenodoError("owned legacy recovery draft metadata is not exact")


def _preflight_metadata_edit_draft(
    deposition: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
    operation_id: str,
    api: str,
    token: str,
) -> dict[str, Any] | None:
    """Distinguish a closed record from an already-open, exactly owned edit."""

    record_id = _required_record_id(deposition["synthpopcan"], "existing_record_id")
    candidate = _request(
        "GET",
        f"{api}/deposit/depositions/{record_id}",
        token=token,
    )
    remote_state = candidate.get("state")
    if remote_state in {"done", "published"}:
        return None
    if remote_state != "inprogress":
        raise ZenodoError("metadata edit preflight returned an unexpected state")
    if _draft_ownership(candidate) != operation_id:
        raise ZenodoError("open metadata edit is not owned by this exact operation")
    _assert_draft_binding(
        candidate,
        deposition,
        operation_id=operation_id,
        require_owned=True,
    )
    _assert_owned_draft_metadata(
        candidate,
        transport_metadata=transport_metadata,
    )
    return candidate


def _preflight_newversion_draft(
    deposition: dict[str, Any],
    *,
    transport_metadata: dict[str, Any],
    operation_id: str,
    api: str,
    token: str,
) -> dict[str, Any] | None:
    """Prove there is no unowned draft in the concept before newversion."""

    synthpopcan = deposition["synthpopcan"]
    concept_doi = _required_string(synthpopcan, "existing_concept_doi")
    version_doi = _required_string(synthpopcan, "existing_version_doi")
    record_id = _required_record_id(synthpopcan, "existing_record_id")
    concept_id = _doi_record_id(concept_doi)
    response: object = _request(
        "GET",
        (
            f"{api}/deposit/depositions?status=draft&"
            f"q=conceptrecid:{concept_id}&size=100"
        ),
        token=token,
    )
    if not isinstance(response, list):
        raise ZenodoError("new-version draft preflight returned a malformed listing")
    matches: list[dict[str, Any]] = []
    ignored_predecessor = False
    for item in response:
        if not isinstance(item, dict):
            raise ZenodoError("new-version draft preflight returned malformed data")
        item_concept = _concept_doi(item)
        item_concept_id = item.get("conceptrecid")
        if item_concept != concept_doi and str(item_concept_id) != concept_id:
            raise ZenodoError("new-version draft preflight escaped the bound concept")
        if item.get("state") in {"done", "published"}:
            if not (
                item.get("state") == "done"
                and item.get("submitted") is True
                and item.get("id") == record_id
                and _record_doi(item) == version_doi
                and item_concept == concept_doi
                and str(item_concept_id) == concept_id
                and not ignored_predecessor
            ):
                raise ZenodoError(
                    "new-version draft preflight returned an unexpected terminal record"
                )
            # Zenodo's authenticated status=draft listing can include the
            # submitted predecessor itself. It is not an open mutable draft;
            # ignore only this exact, already-bound terminal envelope.
            ignored_predecessor = True
            continue
        matches.append(item)
    if not matches:
        return None
    if len(matches) != 1 or _draft_ownership(matches[0]) != operation_id:
        raise ZenodoError("new-version concept has an unowned or ambiguous open draft")
    _assert_draft_binding(
        matches[0],
        deposition,
        operation_id=operation_id,
        require_owned=True,
    )
    _assert_owned_draft_metadata(
        matches[0],
        transport_metadata=transport_metadata,
    )
    return matches[0]


def _assert_new_record_action_ownership_proof(
    action: dict[str, Any], draft: dict[str, Any]
) -> None:
    """Accept only the empty draft directly created by this POST response."""

    action_id = action.get("id")
    draft_id = draft.get("id")
    if not isinstance(action_id, int) or action_id != draft_id:
        raise ZenodoError("new-record action did not directly identify its draft")
    files = draft.get("files", [])
    if files not in (None, []):
        raise ZenodoError("new-record action returned a pre-populated unowned draft")
    metadata = draft.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ZenodoError("new-record action returned malformed draft metadata")
    metadata = _canonical_metadata(metadata)
    for transient in ("doi", "conceptdoi", "prereserve_doi"):
        metadata.pop(transient, None)
    if metadata:
        raise ZenodoError("new-record action returned a pre-populated unowned draft")


def _remote_file(record: dict[str, Any], filename: str) -> dict[str, Any]:
    """Find exactly one named asset in a Zenodo response."""

    files = record.get("files")
    if not isinstance(files, list):
        raise ZenodoError("Zenodo response does not expose uploaded files")
    matches = [
        item
        for item in files
        if isinstance(item, dict) and item.get("filename", item.get("key")) == filename
    ]
    if len(matches) != 1:
        raise ZenodoError(
            f"Zenodo response must contain exactly one candidate file {filename!r}"
        )
    return matches[0]


def _remote_file_url(file_metadata: dict[str, Any]) -> str:
    """Return the content URL exposed by either Zenodo API representation."""

    links = file_metadata.get("links")
    if isinstance(links, dict):
        for key in ("download", "self"):
            value = links.get(key)
            if isinstance(value, str) and value:
                return value
    raise ZenodoError("Zenodo file lacks a stable content URL")


def _verify_remote_asset(
    record: dict[str, Any], *, filename: str, payload: bytes
) -> dict[str, Any]:
    """Verify the strongest returned size/checksum evidence for one upload."""

    uploaded = _remote_file(record, filename)
    _verify_upload_response(uploaded, payload)
    if _reported_file_size(uploaded) != len(payload):
        raise ZenodoError("Zenodo file response lacks exact size evidence")
    if uploaded.get("checksum") is None:
        raise ZenodoError("Zenodo file response lacks exact MD5 evidence")
    return uploaded


def _assert_only_candidate_file(
    record: dict[str, Any], *, filename: str, payload: bytes
) -> None:
    """Require a version/create draft to contain exactly its candidate asset."""

    files = record.get("files")
    if not isinstance(files, list) or len(files) != 1:
        raise ZenodoError("Zenodo record must contain exactly one candidate file")
    _verify_remote_asset(record, filename=filename, payload=payload)


def _bound_draft_bucket(
    draft: dict[str, Any],
    result: dict[str, Any],
    *,
    api: str,
) -> str:
    """Bind uploads to the current owned draft's trusted Zenodo bucket URL."""

    links = draft.get("links")
    bucket = links.get("bucket") if isinstance(links, dict) else None
    if not isinstance(bucket, str) or not bucket:
        raise ZenodoError("Zenodo draft lacks an upload bucket")
    bucket_url = urllib.parse.urlsplit(bucket)
    api_url = urllib.parse.urlsplit(api)
    api_files_prefix = f"{api_url.path.rstrip('/')}/files/"
    if (
        bucket_url.scheme != "https"
        or bucket_url.netloc != api_url.netloc
        or not bucket_url.path.startswith(api_files_prefix)
        or bucket_url.query
        or bucket_url.fragment
    ):
        raise ZenodoError("Zenodo draft exposes an untrusted upload bucket")
    recorded = result.get("bucket_url")
    if recorded is not None and recorded != bucket:
        raise ZenodoError("checkpoint upload bucket does not match the bound draft")
    return bucket.rstrip("/")


def _assert_pre_publish_files(
    draft: dict[str, Any],
    *,
    operation: str,
    existing: dict[str, Any] | None,
    filename: str | None,
    payload: bytes | None,
) -> None:
    """Rebind the complete mutable file set immediately before publication."""

    if operation == "correct-existing-metadata":
        if existing is None:
            raise ZenodoError("metadata correction lost its source file binding")
        _assert_same_source_files(draft, existing)
        return
    if operation in _ASSET_OPERATIONS:
        if filename is None or payload is None:
            raise ZenodoError("asset operation lost its candidate file binding")
        _assert_only_candidate_file(draft, filename=filename, payload=payload)


def _existing_record_requirements(
    deposition: dict[str, Any],
    *,
    api: str,
    token: str,
    verify_asset_bytes: bool = True,
    require_latest: bool = True,
) -> tuple[dict[str, Any], int, str, str]:
    """Fetch and bind a correction to the intended record and concept."""

    synthpopcan = deposition["synthpopcan"]
    record_id = _required_record_id(synthpopcan, "existing_record_id")
    concept_doi = _required_string(synthpopcan, "existing_concept_doi")
    version_doi = _required_string(synthpopcan, "existing_version_doi")
    existing = _request("GET", f"{api}/records/{record_id}", token=token)
    if existing.get("id") != record_id:
        raise ZenodoError("existing Zenodo record ID does not match the manifest")
    if _concept_doi(existing) != concept_doi:
        raise ZenodoError("existing Zenodo record belongs to a different concept DOI")
    if _record_doi(existing) != version_doi:
        raise ZenodoError("existing Zenodo record version DOI does not match")
    if synthpopcan.get("deposit_operation") == "create-new-version" and require_latest:
        _require_existing_record_is_latest(
            existing,
            record_id=record_id,
            version_doi=version_doi,
            concept_doi=concept_doi,
            token=token,
        )
    historical = synthpopcan.get("historical_asset")
    if not isinstance(historical, dict):
        raise ZenodoError("correction must identify the historical asset")
    historical_filename = _required_string(historical, "filename")
    existing_files = existing.get("files")
    if not isinstance(existing_files, list) or len(existing_files) != 1:
        raise ZenodoError("existing Zenodo record must contain one historical asset")
    remote_historical = _remote_file(existing, historical_filename)
    expected_size = historical.get("size_bytes")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise ZenodoError("historical asset must declare its registered size")
    if _reported_file_size(remote_historical) != expected_size:
        raise ZenodoError("existing Zenodo historical asset size does not match")
    expected_sha256 = historical.get("sha256")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ZenodoError("historical asset must declare its registered SHA-256")
    if verify_asset_bytes:
        _verify_remote_download(
            _remote_file_url(remote_historical),
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
    return existing, record_id, concept_doi, version_doi


def _require_existing_record_is_latest(
    existing: dict[str, Any],
    *,
    record_id: int,
    version_doi: str,
    concept_doi: str,
    token: str,
) -> None:
    """Require the bound predecessor to remain the exact concept head."""

    links = existing.get("links")
    latest = links.get("latest") if isinstance(links, dict) else None
    if not isinstance(latest, str) or not latest:
        raise ZenodoError(
            "existing record does not identify the latest concept version"
        )
    latest_record = _request("GET", latest, token=token)
    if (
        latest_record.get("id") != record_id
        or _record_doi(latest_record) != version_doi
        or _concept_doi(latest_record) != concept_doi
    ):
        raise ZenodoError(
            "new-version action requires the latest record in the concept"
        )


def _operation_transport_metadata(
    deposition: dict[str, Any], existing: dict[str, Any] | None
) -> tuple[dict[str, Any], str | None]:
    """Carry the historical publication date on in-place metadata edits."""

    metadata = json.loads(json.dumps(deposition["metadata"]))
    operation = deposition["synthpopcan"]["deposit_operation"]
    if operation != "correct-existing-metadata":
        return metadata, None
    if existing is None:
        raise ZenodoError("metadata correction lacks its existing record")
    existing_metadata = existing.get("metadata")
    publication_date = (
        existing_metadata.get("publication_date")
        if isinstance(existing_metadata, dict)
        else None
    )
    if (
        not isinstance(publication_date, str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", publication_date) is None
    ):
        raise ZenodoError(
            "existing metadata correction record lacks an exact publication date"
        )
    declared = metadata.get("publication_date")
    if declared is not None and declared != publication_date:
        raise ZenodoError("metadata correction would change the publication date")
    metadata["publication_date"] = publication_date
    return metadata, publication_date


def _require_preserved_record_identity(
    existing: dict[str, Any],
    desired_metadata: dict[str, Any],
    *,
    fields: tuple[str, ...] = ("title", "creators", "resource_type", "version"),
) -> None:
    """Restrict an in-place correction to rights/provenance metadata deltas."""

    existing_metadata = existing.get("metadata")
    if not isinstance(existing_metadata, dict):
        raise ZenodoError("existing record does not expose metadata for comparison")
    canonical_existing = _canonical_metadata(existing_metadata)
    canonical_desired = _canonical_metadata(desired_metadata)
    for field in fields:
        if field not in canonical_existing:
            raise ZenodoError(
                f"existing record does not expose critical metadata field {field}"
            )
        if canonical_desired.get(field) != canonical_existing[field]:
            raise ZenodoError(
                f"metadata correction must preserve existing {field} exactly"
            )


def _require_supersession_metadata(
    deposition: dict[str, Any], *, existing_record_id: int, existing_version_doi: str
) -> None:
    """Require an explicit, machine-readable non-overwriting supersession claim."""

    synthpopcan = deposition["synthpopcan"]
    supersession = synthpopcan.get("supersession")
    if not isinstance(supersession, dict):
        raise ZenodoError("new version must declare supersession metadata")
    if supersession.get("preserve_existing_version") is not True:
        raise ZenodoError("new version must preserve the existing version")
    if supersession.get("record_id") != existing_record_id:
        raise ZenodoError("supersession record ID does not match")
    if supersession.get("version_doi") != existing_version_doi:
        raise ZenodoError("supersession version DOI does not match")

    metadata = deposition["metadata"]
    related = metadata.get("related_identifiers")
    if not isinstance(related, list) or not any(
        isinstance(identifier, dict)
        and identifier.get("relation") == "isNewVersionOf"
        and identifier.get("identifier") == existing_version_doi
        for identifier in related
    ):
        raise ZenodoError(
            "new-version metadata must relate isNewVersionOf the superseded DOI"
        )


def _draft_from_action(
    response: dict[str, Any], *, api: str, token: str
) -> dict[str, Any]:
    """Resolve an edit/new-version action response to its mutable draft."""

    links = response.get("links")
    if isinstance(links, dict):
        latest_draft = links.get("latest_draft")
        if isinstance(latest_draft, str) and latest_draft:
            return _request("GET", latest_draft, token=token)
    deposition_id = response.get("id")
    if isinstance(deposition_id, int):
        if isinstance(links, dict) and isinstance(links.get("bucket"), str):
            return response
        return _request(
            "GET", f"{api}/deposit/depositions/{deposition_id}", token=token
        )
    raise ZenodoError("Zenodo action did not identify its editable draft")


def _advertised_draft(
    existing: dict[str, Any] | None, *, api: str, token: str
) -> dict[str, Any] | None:
    """Resolve an already-open latest/edit draft advertised by a public record."""

    if existing is None:
        return None
    links = existing.get("links")
    draft_url = links.get("latest_draft") if isinstance(links, dict) else None
    if isinstance(draft_url, str) and draft_url:
        return _request("GET", draft_url, token=token)
    if existing.get("state") in {"inprogress", "editing"}:
        record_id = _required_record_id(existing, "id")
        return _request("GET", f"{api}/deposit/depositions/{record_id}", token=token)
    return None


def _require_created_action(action: dict[str, Any], operation: str) -> None:
    """Reject ambiguous action responses that do not prove draft creation."""

    if action.get(_HTTP_STATUS_KEY) != 201:
        raise ZenodoError(
            f"Zenodo {operation} action did not prove creation of a new owned draft"
        )


def _remove_inherited_draft_files(
    draft: dict[str, Any], *, api: str, token: str, preserve_filename: str | None = None
) -> None:
    """Remove snapshot-inherited files from only the mutable new-version draft."""

    deposition_id = _required_record_id(draft, "id")
    files = draft.get("files")
    if files is None:
        return
    if not isinstance(files, list):
        raise ZenodoError("new-version draft files must be a list")
    for file_metadata in files:
        if not isinstance(file_metadata, dict):
            raise ZenodoError("new-version draft contains malformed file metadata")
        file_id = file_metadata.get("id")
        filename = file_metadata.get("filename", file_metadata.get("key"))
        if preserve_filename is not None and filename == preserve_filename:
            continue
        if not isinstance(file_id, (str, int)) or isinstance(file_id, bool):
            raise ZenodoError(
                "inherited Zenodo file lacks an ID; refusing an ambiguous delete"
            )
        _request(
            "DELETE",
            f"{api}/deposit/depositions/{deposition_id}/files/{file_id}",
            token=token,
        )


def _assert_exact_inherited_draft_files(
    draft: dict[str, Any],
    existing: dict[str, Any],
    *,
    candidate_filename: str | None,
    allow_source_subset: bool,
) -> None:
    """Require only the source snapshot plus an optional verified candidate."""

    files = draft.get("files")
    if not isinstance(files, list):
        raise ZenodoError("new-version draft lacks an exact inherited file set")
    source_view = json.loads(json.dumps(draft))
    if candidate_filename is None:
        source_files = files
    else:
        candidates = [
            item
            for item in files
            if isinstance(item, dict)
            and item.get("filename", item.get("key")) == candidate_filename
        ]
        if len(candidates) != 1:
            raise ZenodoError("new-version draft lacks one exact candidate file")
        source_files = [item for item in files if item is not candidates[0]]
    source_view["files"] = source_files
    if not allow_source_subset:
        _assert_same_source_files(source_view, existing)
        return
    actual = _normalized_source_files(source_view)
    expected = _normalized_source_files(existing)
    if len(actual) != len(set(actual)) or not set(actual).issubset(expected):
        raise ZenodoError("new-version draft contains an unexpected inherited file")


def _verify_historical_version_unchanged(
    deposition: dict[str, Any],
    *,
    api: str,
    token: str,
    new_record_id: int,
    new_version_doi: str,
) -> None:
    """Confirm the published predecessor still resolves with its historical file."""

    synthpopcan = deposition["synthpopcan"]
    historical_record_id = _required_record_id(synthpopcan, "existing_record_id")
    historical = _request("GET", f"{api}/records/{historical_record_id}", token=token)
    if (
        historical.get("id") != historical_record_id
        or _record_doi(historical) != synthpopcan["existing_version_doi"]
        or _concept_doi(historical) != synthpopcan["existing_concept_doi"]
    ):
        raise ZenodoError("published predecessor identity changed")
    historical_asset = synthpopcan["historical_asset"]
    files = historical.get("files")
    if not isinstance(files, list) or len(files) != 1:
        raise ZenodoError("published predecessor file set changed")
    remote_asset = _remote_file(historical, str(historical_asset["filename"]))
    expected_size = historical_asset.get("size_bytes")
    expected_sha256 = historical_asset.get("sha256")
    if (
        not isinstance(expected_size, int)
        or _reported_file_size(remote_asset) != expected_size
    ):
        raise ZenodoError("published predecessor asset size changed")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ZenodoError("published predecessor lacks a registered SHA-256 checksum")
    _verify_remote_download(
        _remote_file_url(remote_asset),
        expected_size=expected_size,
        expected_sha256=expected_sha256,
    )
    links = historical.get("links")
    latest_url = links.get("latest") if isinstance(links, dict) else None
    if not isinstance(latest_url, str) or not latest_url:
        raise ZenodoError("published predecessor does not resolve the latest version")
    latest = _request("GET", latest_url, token=token)
    if (
        latest.get("id") != new_record_id
        or _record_doi(latest) != new_version_doi
        or _concept_doi(latest) != synthpopcan["existing_concept_doi"]
    ):
        raise ZenodoError("newly published correction is not the concept latest")
    # The post-publish SHA-256 stream closes the mutable-action TOCTOU window and
    # proves that publication did not alter the registered predecessor bytes.


def _verify_final_record(
    deposition: dict[str, Any],
    *,
    api: str,
    token: str,
    result: dict[str, Any],
    payload: bytes | None,
    filename: str | None,
) -> dict[str, Any]:
    """Verify published identity, metadata, and asset before declaring success."""

    record_id = _required_record_id(result, "deposition_id")
    record = _request("GET", f"{api}/records/{record_id}", token=token)
    if record.get("id") != record_id:
        raise ZenodoError("published Zenodo record ID changed during verification")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise ZenodoError("published Zenodo record does not expose metadata")
    _assert_metadata_subset(
        _canonical_metadata(deposition["metadata"]),
        _canonical_metadata(metadata),
        path="metadata",
    )
    operation_id = _operation_identity(deposition)
    if _draft_ownership(record) != operation_id:
        raise ZenodoError("published Zenodo record lost executor ownership")

    operation = str(deposition["synthpopcan"]["deposit_operation"])
    doi = _record_doi(record)
    concept_doi = _concept_doi(record)
    if not doi or not concept_doi:
        raise ZenodoError("published Zenodo record lacks version or concept DOI")
    if operation == "correct-existing-metadata":
        synthpopcan = deposition["synthpopcan"]
        if doi != synthpopcan["existing_version_doi"]:
            raise ZenodoError("metadata correction changed the version DOI")
        if concept_doi != synthpopcan["existing_concept_doi"]:
            raise ZenodoError("metadata correction changed the concept DOI")
        source_publication_date = result.get("source_publication_date")
        if (
            not isinstance(source_publication_date, str)
            or metadata.get("publication_date") != source_publication_date
        ):
            raise ZenodoError("metadata correction changed the publication date")
        historical_asset = synthpopcan["historical_asset"]
        files = record.get("files")
        if not isinstance(files, list) or len(files) != 1:
            raise ZenodoError("metadata correction changed the historical file set")
        remote_historical = _remote_file(record, str(historical_asset["filename"]))
        if _reported_file_size(remote_historical) != historical_asset["size_bytes"]:
            raise ZenodoError("metadata correction changed the historical file size")
        _verify_remote_download(
            _remote_file_url(remote_historical),
            expected_size=historical_asset["size_bytes"],
            expected_sha256=historical_asset["sha256"],
        )
    elif operation == "create-new-version":
        synthpopcan = deposition["synthpopcan"]
        if concept_doi != synthpopcan["existing_concept_doi"]:
            raise ZenodoError("new version escaped the existing concept DOI")
        if doi == synthpopcan["existing_version_doi"]:
            raise ZenodoError("new version reused the superseded version DOI")

    remote_asset: dict[str, Any] | None = None
    if payload is not None and filename is not None:
        _assert_only_candidate_file(record, filename=filename, payload=payload)
        remote_asset = _remote_file(record, filename)
        _verify_remote_download(
            _remote_file_url(remote_asset),
            expected_size=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    result.update(
        {
            "state": _TERMINAL_STATE,
            "verified": True,
            "doi": doi,
            "concept_doi": concept_doi,
            "html_url": record.get("links", {}).get("html", result.get("html_url")),
        }
    )
    if operation == "create-new-version":
        synthpopcan = deposition["synthpopcan"]
        result["supersedes"] = {
            "record_id": synthpopcan["existing_record_id"],
            "version_doi": synthpopcan["existing_version_doi"],
        }
        _verify_historical_version_unchanged(
            deposition,
            api=api,
            token=token,
            new_record_id=record_id,
            new_version_doi=doi,
        )
    if operation in _ASSET_OPERATIONS and remote_asset is not None:
        synthpopcan = deposition["synthpopcan"]
        download_url = _remote_file_url(remote_asset)
        result["registry_update"] = {
            "model_id": synthpopcan["model_id"],
            "release_version": deposition["metadata"]["version"],
            "record_id": record_id,
            "version_doi": doi,
            "concept_doi": concept_doi,
            "url": download_url,
            "filename": filename,
            "size_bytes": synthpopcan["size_bytes"],
            "sha256": synthpopcan["sha256"],
            "uncompressed_size_bytes": synthpopcan["uncompressed_size_bytes"],
            "uncompressed_sha256": synthpopcan["uncompressed_sha256"],
        }
    return record


def _checkpoint_result(
    checkpoint: Callable[[dict[str, Any]], None] | None,
    result: dict[str, Any],
) -> None:
    if checkpoint is not None:
        checkpoint(result.copy())


def deposit_one(
    deposition: dict[str, Any],
    *,
    api: str,
    token: str,
    publish: bool,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
    resume: dict[str, Any] | None = None,
    execution_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one deposit/correction operation, resuming a matching checkpoint."""

    synthpopcan = deposition.get("synthpopcan")
    if not isinstance(synthpopcan, dict):
        raise ZenodoError("deposition must carry SynthPopCan metadata")
    metadata = deposition.get("metadata")
    if not isinstance(metadata, dict):
        raise ZenodoError("deposition must carry Zenodo metadata")
    model_id = _required_string(synthpopcan, "model_id")
    operation = _required_string(synthpopcan, "deposit_operation")
    if operation == "review-metadata-only":
        raise ZenodoError(
            "deposition is review-only; no Zenodo write operation is authorized"
        )
    _validate_correction_manifest_readiness(deposition)
    operation_id = _operation_identity(deposition)
    if operation in _ASSET_OPERATIONS and synthpopcan.get("asset_ready") is not True:
        raise ZenodoError(
            "deposition is review-only; a verified corrected asset is required"
        )
    if operation == "correct-existing-metadata" and (
        synthpopcan.get("metadata_ready") is not True
    ):
        raise ZenodoError(
            "metadata correction is review-only until metadata_ready is true"
        )
    production = api.rstrip("/") == PRODUCTION_API
    if production and not _production_licensing_gates_are_complete():
        raise ZenodoError(
            "production deposition requires accepted ADR-0014 and the completed "
            "archive-correction implementation gate"
        )
    if production and operation in {
        "correct-existing-metadata",
        "create-new-version",
    }:
        _require_production_correction_authority(deposition, execution_index)
    _validated_licensing(
        deposition,
        require_accepted_policy=production,
    )
    if (
        production
        and operation == "create-new-record"
        and not _archive_correction_execution_is_completed()
    ):
        raise ZenodoError(
            "fresh production model records remain blocked until all 32 archive "
            "corrections are verified and Archive correction execution is Completed"
        )
    payload: bytes | None = None
    filename: str | None = None
    if operation in _ASSET_OPERATIONS:
        filename = _candidate_filename(
            deposition, operation=operation, model_id=model_id
        )
        payload = _asset_bytes(deposition)
        _verify_asset(
            payload,
            deposition,
            require_accepted_policy=production,
        )

    existing: dict[str, Any] | None = None
    existing_record_id: int | None = None
    existing_concept_doi: str | None = None
    existing_version_doi: str | None = None
    if operation in {"correct-existing-metadata", "create-new-version"}:
        (
            existing,
            existing_record_id,
            existing_concept_doi,
            existing_version_doi,
        ) = _existing_record_requirements(
            deposition,
            api=api,
            token=token,
            require_latest=(resume is None or resume.get("state") == "action-intent"),
        )
    if operation == "create-new-version":
        assert existing_record_id is not None and existing_version_doi is not None
        assert existing is not None
        _require_newversion_authority(existing, operation_id)
        _require_preserved_record_identity(
            existing,
            metadata,
            fields=("title", "creators", "resource_type"),
        )
        _require_supersession_metadata(
            deposition,
            existing_record_id=existing_record_id,
            existing_version_doi=existing_version_doi,
        )
        existing_package_version = _required_string(
            synthpopcan, "existing_package_version"
        )
        if metadata["version"] == existing_package_version:
            raise ZenodoError("corrected package must use a new package version")
    elif operation == "correct-existing-metadata":
        assert existing is not None
        _require_preserved_record_identity(existing, metadata)

    transport_metadata, source_publication_date = _operation_transport_metadata(
        deposition, existing
    )

    result = {
        "operation_id": operation_id,
        "deposit_operation": operation,
        "model_id": model_id,
        "package_version": (
            metadata.get("version")
            if operation in _ASSET_OPERATIONS
            else synthpopcan.get("existing_package_version")
        ),
        "asset_sha256": _operation_asset_sha256(deposition),
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }
    if existing_record_id is not None:
        result["source_record_id"] = existing_record_id
    if source_publication_date is not None:
        result["source_publication_date"] = source_publication_date

    if resume is not None:
        expected_static = result.copy()
        static_fields = (
            "operation_id",
            "deposit_operation",
            "model_id",
            "package_version",
            "asset_sha256",
            "metadata_sha256",
            "source_record_id",
        )
        missing = object()
        for field in static_fields:
            if resume.get(field, missing) != expected_static.get(field, missing):
                raise ZenodoError(f"checkpoint {field} does not match this operation")
        result = resume.copy()
        if (
            operation_id == _LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID
            and result.get("state") == "action-intent"
            and result != _legacy_recovery_checkpoint(deposition, operation_id)
        ):
            raise ZenodoError(
                "legacy recovery checkpoint is not the exact action intent"
            )
        if source_publication_date is not None:
            recorded_date = result.get("source_publication_date")
            legacy_action_intent = (
                operation_id == _LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID
                and result == _legacy_recovery_checkpoint(deposition, operation_id)
            )
            if recorded_date != source_publication_date and not legacy_action_intent:
                raise ZenodoError(
                    "metadata correction checkpoint changed the publication date"
                )
        if result.get("state") == _TERMINAL_STATE:
            if result.get("verified") is not True:
                raise ZenodoError("verified checkpoint lacks verified=true evidence")
            _verify_final_record(
                deposition,
                api=api,
                token=token,
                result=result,
                payload=payload,
                filename=filename,
            )
            _checkpoint_result(checkpoint, result)
            return result
        if result.get("state") == "published":
            _verify_final_record(
                deposition,
                api=api,
                token=token,
                result=result,
                payload=payload,
                filename=filename,
            )
            _checkpoint_result(checkpoint, result)
            return result
    else:
        _checkpoint_result(checkpoint, result)

    state = str(result.get("state"))
    draft: dict[str, Any] | None = None
    if state == "action-intent":
        advertised = _advertised_draft(existing, api=api, token=token)
        inherited_owner = _draft_ownership(existing) if existing is not None else None
        if advertised is not None:
            owner = _draft_ownership(advertised)
            if owner == operation_id:
                draft = advertised
            else:
                raise ZenodoError(
                    "existing Zenodo latest draft is not owned by this operation"
                )
        elif _may_read_direct_legacy_recovery_draft(
            deposition,
            operation_id=operation_id,
            resume=resume,
            api=api,
        ):
            assert existing is not None and existing_record_id is not None
            direct = _request(
                "GET",
                f"{api}/deposit/depositions/{existing_record_id}",
                token=token,
            )
            direct_owner = _draft_ownership(direct)
            if direct_owner == operation_id:
                _assert_exact_durable_owned_recovery_claim(
                    direct,
                    existing,
                    deposition,
                    transport_metadata=transport_metadata,
                    operation_id=operation_id,
                )
            elif direct_owner is None:
                _assert_exact_legacy_stripped_marker_claim(
                    direct,
                    existing,
                    deposition,
                    transport_metadata=transport_metadata,
                    operation_id=operation_id,
                    resume=resume,
                )
            else:
                raise ZenodoError(
                    "direct legacy recovery draft is owned by another operation"
                )
            draft = direct
        else:
            if operation == "correct-existing-metadata":
                draft = _preflight_metadata_edit_draft(
                    deposition,
                    transport_metadata=transport_metadata,
                    operation_id=operation_id,
                    api=api,
                    token=token,
                )
            elif operation == "create-new-version":
                draft = _preflight_newversion_draft(
                    deposition,
                    transport_metadata=transport_metadata,
                    operation_id=operation_id,
                    api=api,
                    token=token,
                )
            if draft is None:
                if operation == "create-new-record":
                    action = _request(
                        "POST", f"{api}/deposit/depositions", token=token, payload={}
                    )
                elif operation == "create-new-version":
                    assert existing_record_id is not None
                    action = _request(
                        "POST",
                        f"{api}/deposit/depositions/{existing_record_id}/actions/newversion",
                        token=token,
                    )
                else:
                    assert existing_record_id is not None
                    action = _request(
                        "POST",
                        f"{api}/deposit/depositions/{existing_record_id}/actions/edit",
                        token=token,
                    )
                _require_created_action(action, operation)
                draft = _draft_from_action(action, api=api, token=token)
                action_owner = _draft_ownership(draft)
                if action_owner != operation_id:
                    if existing is not None:
                        # The operation-specific preflight immediately above
                        # proved there was no open draft before this POST. The
                        # exact untouched action snapshot is therefore the new
                        # draft created for this invocation, including when an
                        # action-intent checkpoint is being resumed.
                        _assert_unclaimed_draft_snapshot(draft, existing)
                        if inherited_owner is not None:
                            if action_owner != inherited_owner:
                                raise ZenodoError(
                                    "action draft lacks the source ownership marker"
                                )
                            draft = _without_inherited_ownership(draft, inherited_owner)
                        elif action_owner is not None:
                            raise ZenodoError("action returned a draft owned elsewhere")
                    elif operation == "create-new-record":
                        if action_owner is not None:
                            raise ZenodoError("new-record draft is already owned")
                        _assert_new_record_action_ownership_proof(action, draft)
                    else:  # pragma: no cover - exhaustiveness guard
                        raise ZenodoError("action returned an unowned draft")
        assert draft is not None
        deposition_id = _required_record_id(draft, "id")
        terminal_action = draft.get("state") in {"done", "published"}
        if terminal_action:
            _assert_draft_binding(
                draft, deposition, operation_id=operation_id, require_owned=True
            )
            _assert_owned_draft_metadata(
                draft,
                transport_metadata=transport_metadata,
            )
        else:
            draft = _claim_draft(
                draft,
                deposition,
                transport_metadata=transport_metadata,
                operation_id=operation_id,
                api=api,
                token=token,
            )
            deposition_id = _required_record_id(draft, "id")
            if operation in {"correct-existing-metadata", "create-new-version"}:
                # Re-read an existing-concept draft after claiming it. This
                # closes the stale-response/race window before any inherited
                # file is removed or existing-record metadata is edited.
                draft = _request(
                    "GET", f"{api}/deposit/depositions/{deposition_id}", token=token
                )
                _assert_draft_binding(
                    draft,
                    deposition,
                    operation_id=operation_id,
                    require_owned=True,
                )
                _assert_owned_draft_metadata(
                    draft,
                    transport_metadata=transport_metadata,
                )
        links = draft.get("links")
        result.update(
            {
                "deposition_id": deposition_id,
                "state": (
                    "published"
                    if terminal_action
                    else (
                        "editing"
                        if operation == "correct-existing-metadata"
                        else "created"
                    )
                ),
                "doi": _record_doi(draft),
                "concept_doi": _concept_doi(draft) if terminal_action else None,
                "html_url": links.get("html") if isinstance(links, dict) else None,
            }
        )
        if not terminal_action:
            result.pop("concept_doi", None)
        if source_publication_date is not None:
            result["source_publication_date"] = source_publication_date
        if isinstance(links, dict) and isinstance(links.get("bucket"), str):
            result["bucket_url"] = links["bucket"]
        _checkpoint_result(checkpoint, result)
    else:
        deposition_id = _required_record_id(result, "deposition_id")
        draft = _request(
            "GET", f"{api}/deposit/depositions/{deposition_id}", token=token
        )
        if draft.get("id") != deposition_id:
            raise ZenodoError("checkpoint draft ID does not match Zenodo")
        if state in {"created", "editing", "uploaded"}:
            _assert_draft_binding(
                draft, deposition, operation_id=operation_id, require_owned=True
            )
            _assert_owned_draft_metadata(
                draft,
                transport_metadata=transport_metadata,
            )

    assert draft is not None
    state = str(result.get("state"))
    if state == "draft":
        _assert_draft_binding(
            draft, deposition, operation_id=operation_id, require_owned=True
        )
        _assert_owned_draft_metadata(
            draft,
            transport_metadata=transport_metadata,
        )
    remote_is_terminal = draft.get("state") in {"done", "published"}
    if operation == "create-new-version" and not remote_is_terminal:
        assert existing is not None
        assert existing_record_id is not None
        assert existing_version_doi is not None
        assert existing_concept_doi is not None
        _require_existing_record_is_latest(
            existing,
            record_id=existing_record_id,
            version_doi=existing_version_doi,
            concept_doi=existing_concept_doi,
            token=token,
        )
    remote_already_published = (
        state
        in {
            "created",
            "editing",
            "uploaded",
            "draft",
        }
        and remote_is_terminal
    )
    if remote_already_published:
        _assert_pre_publish_files(
            draft,
            operation=operation,
            existing=existing,
            filename=filename,
            payload=payload,
        )
        result["state"] = "published"
        result["doi"] = _record_doi(draft) or result.get("doi")
        result["concept_doi"] = _concept_doi(draft)
        _checkpoint_result(checkpoint, result)
        _verify_final_record(
            deposition,
            api=api,
            token=token,
            result=result,
            payload=payload,
            filename=filename,
        )
        _checkpoint_result(checkpoint, result)
        return result
    if operation in _ASSET_OPERATIONS:
        assert payload is not None and filename is not None
        upload_bucket: str | None = None
        if state in {"created", "editing"}:
            upload_bucket = _bound_draft_bucket(draft, result, api=api)
            result["bucket_url"] = upload_bucket
            existing_files = draft.get("files")
            candidate_files = (
                [
                    item
                    for item in existing_files
                    if isinstance(item, dict)
                    and item.get("filename", item.get("key")) == filename
                ]
                if isinstance(existing_files, list)
                else []
            )
            if len(candidate_files) > 1:
                raise ZenodoError("new draft contains duplicate candidate files")
            uploaded_before_checkpoint = (
                resume is not None and len(candidate_files) == 1
            )
            if uploaded_before_checkpoint:
                _verify_remote_asset(draft, filename=filename, payload=payload)
            if operation == "create-new-version":
                assert existing is not None
                _assert_exact_inherited_draft_files(
                    draft,
                    existing,
                    candidate_filename=(
                        filename if uploaded_before_checkpoint else None
                    ),
                    allow_source_subset=resume is not None,
                )
                _remove_inherited_draft_files(
                    draft,
                    api=api,
                    token=token,
                    preserve_filename=filename if uploaded_before_checkpoint else None,
                )
            elif candidate_files and not uploaded_before_checkpoint:
                raise ZenodoError(
                    "new draft already contains the candidate filename before upload"
                )
            if uploaded_before_checkpoint:
                result["state"] = "uploaded"
                result["uploaded_bytes"] = len(payload)
                _checkpoint_result(checkpoint, result)
                state = "uploaded"
                existing_files = []
            else:
                existing_files = []
        if state in {"created", "editing"}:
            if upload_bucket is None:  # pragma: no cover - state invariant
                raise ZenodoError("Zenodo draft upload bucket was not bound")
            uploaded = _request(
                "PUT", f"{upload_bucket}/{filename}", token=token, data=payload
            )
            _verify_upload_response(uploaded, payload)
            result["state"] = "uploaded"
            result["uploaded_bytes"] = len(payload)
            result["bucket_url"] = upload_bucket
            _checkpoint_result(checkpoint, result)
            state = "uploaded"
        elif state in {"uploaded", "draft", "published"}:
            _verify_remote_asset(draft, filename=filename, payload=payload)

    if state in {"created", "editing", "uploaded"}:
        owned_metadata = _metadata_with_ownership(transport_metadata, operation_id)
        updated = _request(
            "PUT",
            f"{api}/deposit/depositions/{result['deposition_id']}",
            token=token,
            payload={"metadata": owned_metadata},
        )
        updated_metadata = updated.get("metadata")
        if not isinstance(updated_metadata, dict):
            raise ZenodoError("Zenodo metadata update returned no metadata")
        _assert_draft_binding(
            updated,
            deposition,
            operation_id=operation_id,
            require_owned=True,
        )
        _assert_owned_draft_metadata(
            updated,
            transport_metadata=transport_metadata,
        )
        updated = _request(
            "GET",
            f"{api}/deposit/depositions/{result['deposition_id']}",
            token=token,
        )
        _assert_draft_binding(
            updated,
            deposition,
            operation_id=operation_id,
            require_owned=True,
        )
        _assert_owned_draft_metadata(
            updated,
            transport_metadata=transport_metadata,
        )
        _assert_pre_publish_files(
            updated,
            operation=operation,
            existing=existing,
            filename=filename,
            payload=payload,
        )
        draft = updated
        result["state"] = "draft"
        result["doi"] = _record_doi(updated) or result.get("doi")
        _checkpoint_result(checkpoint, result)
        state = "draft"
    elif state == "draft":
        _assert_draft_binding(
            draft,
            deposition,
            operation_id=operation_id,
            require_owned=True,
        )
        _assert_owned_draft_metadata(
            draft,
            transport_metadata=transport_metadata,
        )
        _assert_pre_publish_files(
            draft,
            operation=operation,
            existing=existing,
            filename=filename,
            payload=payload,
        )

    if not publish:
        return result

    if state == "draft":
        published = _request(
            "POST",
            f"{api}/deposit/depositions/{result['deposition_id']}/actions/publish",
            token=token,
        )
        result["state"] = "published"
        result["doi"] = _record_doi(published) or result.get("doi")
        result["concept_doi"] = _concept_doi(published)
        _checkpoint_result(checkpoint, result)
    elif state != "published":
        raise ZenodoError(f"cannot publish checkpoint in unexpected state {state!r}")

    _verify_final_record(
        deposition,
        api=api,
        token=token,
        result=result,
        payload=payload,
        filename=filename,
    )
    _checkpoint_result(checkpoint, result)
    return result


def _load_depositions(
    only: tuple[str, ...], directory: Path | None = None
) -> list[dict[str, Any]]:
    """Load generated deposition metadata, optionally filtered to some models."""

    source = directory or DEPOSITIONS_DIR
    if not source.exists():
        raise click.UsageError(
            f"No deposition metadata in {source}. "
            "Run scripts/build_zenodo_depositions.py first."
        )
    paths = sorted(
        path
        for path in source.glob("*.json")
        if path.name
        not in {
            "index.json",
            "execution-index.json",
            RESULTS_PATH.name,
            REGISTRY_UPDATES_PATH.name,
            CORRECTION_PLAN_NAME,
        }
    )
    depositions = [json.loads(path.read_text()) for path in paths]
    _validate_correction_execution_authority(depositions, source=source)
    if only:
        wanted = set(only)
        depositions = [
            item for item in depositions if item["synthpopcan"]["model_id"] in wanted
        ]
        missing = wanted - {item["synthpopcan"]["model_id"] for item in depositions}
        if missing:
            raise click.UsageError(f"Unknown model IDs: {sorted(missing)}")
    if not depositions:
        raise click.UsageError("No depositions selected")
    return depositions


def _stored_targets() -> dict[str, dict[str, Any]]:
    """Load all saved targets, migrating the original single-target format."""

    if not RESULTS_PATH.exists():
        return {}
    stored = json.loads(RESULTS_PATH.read_text())
    targets = stored.get("targets")
    if isinstance(targets, dict):
        return targets
    target = stored.get("target")
    if isinstance(target, str):
        return {
            target: {
                "api": stored.get("api"),
                "results": stored.get("results", []),
            }
        }
    return {}


def _existing_results(target: str) -> dict[str, dict[str, Any]]:
    """Load prior results keyed by operation/version/hash identity.

    Results from a different target are not returned: sandbox deposition IDs
    are meaningless against production. Legacy model-only checkpoints are kept
    under quarantined keys, so they remain auditable but cannot skip new work.
    """

    target_data = _stored_targets().get(target, {})
    results: dict[str, dict[str, Any]] = {}
    for item in target_data.get("results", []):
        if not isinstance(item, dict):
            continue
        operation_id = item.get("operation_id")
        key = (
            operation_id
            if isinstance(operation_id, str) and operation_id
            else _legacy_result_identity(item)
        )
        if key in results:
            raise ZenodoError(f"duplicate stored checkpoint identity: {key}")
        results[key] = item
    return results


def _write_results(target: str, api: str, results: dict[str, dict[str, Any]]) -> None:
    """Atomically checkpoint one target without discarding the other target."""

    targets = _stored_targets()
    targets[target] = {
        "api": api,
        "results": [results[key] for key in sorted(results)],
    }
    document = {
        "schema_version": "synthpopcan-zenodo-deposit-results-v3",
        "targets": targets,
    }
    temporary = RESULTS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(RESULTS_PATH)


def _write_registry_updates(
    target: str,
    api: str,
    results: dict[str, dict[str, Any]],
    *,
    execution_index: dict[str, Any] | None = None,
) -> bool:
    """Expose only unique, current-authority, verified correction versions."""

    if target != "PRODUCTION" or api.rstrip("/") != PRODUCTION_API:
        return False
    if not isinstance(execution_index, dict):
        return False
    operations = execution_index.get("operations")
    if not isinstance(operations, list):
        raise ZenodoError("registry output lacks a correction execution authority")
    indexed = {
        str(operation.get("operation_id")): operation
        for operation in operations
        if isinstance(operation, dict)
        and operation.get("deposit_operation")
        in {"correct-existing-metadata", "create-new-version"}
        and isinstance(operation.get("operation_id"), str)
    }
    if len(indexed) != len(operations):
        raise ZenodoError("correction execution authority has duplicate operations")
    for key, result in results.items():
        if result.get("deposit_operation") not in {
            "correct-existing-metadata",
            "create-new-version",
        }:
            continue
        operation_id = result.get("operation_id")
        if operation_id != key or operation_id not in indexed:
            raise ZenodoError(
                "stored correction result is stale or extraneous to the current index"
            )

    updates: list[dict[str, Any]] = []
    updated_models: set[str] = set()
    for operation_id, descriptor in indexed.items():
        if descriptor.get("deposit_operation") != "create-new-version":
            continue
        result = results.get(operation_id)
        if result is None or result.get("state") != _TERMINAL_STATE:
            continue
        if result.get("verified") is not True:
            raise ZenodoError("verified correction result lacks verified=true")
        for result_field, descriptor_field in (
            ("deposit_operation", "deposit_operation"),
            ("model_id", "model_id"),
            ("package_version", "package_version"),
            ("asset_sha256", "asset_sha256"),
            ("metadata_sha256", "metadata_sha256"),
            ("source_record_id", "existing_record_id"),
            ("concept_doi", "existing_concept_doi"),
        ):
            if result.get(result_field) != descriptor.get(descriptor_field):
                raise ZenodoError(
                    "verified correction result differs from the current index"
                )
        update = result.get("registry_update")
        if not isinstance(update, dict):
            raise ZenodoError("verified correction lacks a registry update")
        expected_update = {
            "model_id": descriptor["model_id"],
            "release_version": descriptor["package_version"],
            "record_id": result.get("deposition_id"),
            "version_doi": result.get("doi"),
            "concept_doi": descriptor["existing_concept_doi"],
            "url": update.get("url"),
            "filename": descriptor["filename"],
            "size_bytes": descriptor["size_bytes"],
            "sha256": descriptor["sha256"],
            "uncompressed_size_bytes": descriptor["uncompressed_size_bytes"],
            "uncompressed_sha256": descriptor["uncompressed_sha256"],
        }
        if update != expected_update:
            raise ZenodoError(
                "verified registry update differs from the current execution index"
            )
        model_id = str(update["model_id"])
        if model_id in updated_models:
            raise ZenodoError("registry output contains a duplicate model update")
        updated_models.add(model_id)
        updates.append(update)
    if not updates:
        return False
    document = {
        "schema_version": "synthpopcan-verified-registry-updates-v1",
        "target": target,
        "api": api,
        "updates": sorted(updates, key=lambda item: str(item["model_id"])),
    }
    temporary = REGISTRY_UPDATES_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(REGISTRY_UPDATES_PATH)
    return True


@click.command()
@click.option(
    "--production",
    is_flag=True,
    help="Target the real Zenodo archive instead of the sandbox.",
)
@click.option(
    "--publish",
    is_flag=True,
    help="Publish each deposition after upload. Irreversible; confirmed per record.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report the planned depositions without contacting Zenodo.",
)
@click.option(
    "--only",
    multiple=True,
    metavar="MODEL_ID",
    help="Deposit only these model IDs. Repeat as needed.",
)
@click.option(
    "--manifests-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=None,
    help="Read manifests from this directory instead of the review-only default.",
)
def main(
    production: bool,
    publish: bool,
    dry_run: bool,
    only: tuple[str, ...],
    manifests_dir: Path | None,
) -> None:
    """Deposit prepared model packages to Zenodo as reviewable drafts."""

    source = manifests_dir or DEPOSITIONS_DIR
    depositions = _load_depositions(only, source)
    has_corrections = any(
        item["synthpopcan"].get("deposit_operation")
        in {"correct-existing-metadata", "create-new-version"}
        for item in depositions
    )
    execution_index = (
        _read_correction_execution_index(source) if has_corrections else None
    )
    api = PRODUCTION_API if production else SANDBOX_API
    target = "PRODUCTION" if production else "sandbox"

    # Validate the complete local authority before token lookup, confirmation,
    # or any possible request.  Production dry-runs are the final 64-operation
    # canary, so they must exercise the same fail-closed manifest readiness
    # checks as a write rather than merely render descriptive output.  An
    # explicitly non-production test subset remains eligible for a sandbox
    # dry-run review, but the write-authority gate below keeps it unwritable.
    for item in depositions:
        synthpopcan = item.get("synthpopcan")
        operation = (
            synthpopcan.get("deposit_operation")
            if isinstance(synthpopcan, dict)
            else None
        )
        if operation not in {"correct-existing-metadata", "create-new-version"}:
            continue
        if not production and synthpopcan.get("production_ready") is not True:
            continue
        try:
            _validate_correction_manifest_readiness(item)
        except ZenodoError as exc:
            model_id = synthpopcan.get("model_id", "unknown")
            raise click.UsageError(
                f"{model_id}: correction manifest preflight failed: {exc}"
            ) from exc

    if production and not dry_run and not _production_licensing_gates_are_complete():
        raise click.UsageError(
            "Production model deposition is blocked until ADR-0014 records "
            "exactly '- **Status:** Accepted' and the archive-correction "
            "implementation marker is Completed. Dry-run review remains available."
        )
    if (
        has_corrections
        and not dry_run
        and (
            execution_index is None
            or execution_index.get("production_ready") is not True
            or execution_index.get("candidate_count") != 32
            or len(execution_index.get("operations", [])) != 64
        )
    ):
        raise click.UsageError(
            "correction writes require the production-ready 32-model/64-operation "
            "execution authority; bounded bundles are dry-run only"
        )

    if dry_run:
        click.echo(f"Dry run against {target} ({api}); no requests will be sent.\n")
        for item in depositions:
            spc = item["synthpopcan"]
            operation = spc.get("deposit_operation", "unknown")
            if operation == "correct-existing-metadata" and (
                spc.get("metadata_ready") is True
            ):
                action = "would correct the existing record metadata in place"
            elif spc.get("asset_ready") is True:
                action = (
                    f"would {operation} and upload {spc['size_bytes']:,} verified bytes"
                )
            else:
                action = "review-only metadata; no asset is eligible for upload"
            click.echo(
                f"  {spc['model_id']}: {action} as {item['metadata']['title']!r}"
            )
        click.echo(f"\n{len(depositions)} deposition(s) planned.")
        return

    token_var = "ZENODO_TOKEN" if production else "ZENODO_SANDBOX_TOKEN"
    token = os.environ.get(token_var)
    if not token:
        raise click.UsageError(
            f"Set {token_var} to a Zenodo personal access token with the "
            "deposit:write scope. Tokens are not accepted as arguments."
        )

    if production and not click.confirm(
        f"Deposit {len(depositions)} record(s) to PRODUCTION Zenodo?"
    ):
        raise click.Abort

    # Draft identifiers and operation identities are both required for safe
    # resume: a changed version or hash must never inherit an older checkpoint.
    results = _existing_results(target)
    for item in depositions:
        model_id = str(item["synthpopcan"]["model_id"])
        operation_id = _operation_identity(item)
        existing = results.get(operation_id)
        verb = (
            "Revalidating"
            if existing is not None and existing.get("state") == _TERMINAL_STATE
            else "Resuming"
            if existing is not None
            else "Applying"
        )
        click.echo(
            f"{verb} {item['synthpopcan']['deposit_operation']} for {model_id} …"
        )
        should_publish = publish and click.confirm(
            f"  Publish {model_id}? This cannot be undone", default=False
        )

        def checkpoint(result: dict[str, Any], key: str = operation_id) -> None:
            results[key] = result
            _write_results(target, api, results)

        result = deposit_one(
            item,
            api=api,
            token=token,
            publish=should_publish,
            checkpoint=checkpoint,
            resume=existing,
            execution_index=execution_index,
        )
        results[operation_id] = result
        click.echo(f"  {result['state']} id={result['deposition_id']}")

    _write_results(target, api, results)
    click.echo(f"\nWrote {RESULTS_PATH.relative_to(ROOT)}")
    if _write_registry_updates(target, api, results, execution_index=execution_index):
        click.echo(
            f"Wrote verified registry candidates to "
            f"{REGISTRY_UPDATES_PATH.relative_to(ROOT)}"
        )
    else:
        click.echo("No registry update was emitted: no new asset is verified.")


if __name__ == "__main__":
    main()
