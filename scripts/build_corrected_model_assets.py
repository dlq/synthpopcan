"""Build checksum-bound, non-overwriting ADR-0014 correction candidates.

This tool performs a local byte transformation only.  It verifies the immutable
historical ``.json.gz`` packages against the installed model registry, validates
their JSON incrementally, inserts the exact top-level ``licensing`` contract,
and emits deterministic corrected archives plus the candidate index consumed by
``build_zenodo_depositions.py --correction-candidates``.  It makes no network or
archive calls and does not claim that any model was retrained.
"""

from __future__ import annotations

import codecs
import gzip
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

import click

from synthpopcan.model_licensing import validate_prepared_model_licensing
from synthpopcan.models import model_catalogue, model_registry_entry

_CHUNK_BYTES = 1024 * 1024
_MAX_JSON_DEPTH = 1024
_MAX_ROOT_KEY_CAPTURE = 256
_MAX_TEST_SUBSET_MODELS = 8
_CANDIDATE_SCHEMA = "synthpopcan-zenodo-correction-candidates-v1"
_RECORD_INDEX_SCHEMA = "synthpopcan-zenodo-record-index-v1"
_DOI_PATTERN = re.compile(r"10\.5281/zenodo\.[1-9][0-9]*\Z")
_VERSION_PATTERN = re.compile(r"v?[0-9][0-9A-Za-z.-]*\Z")


class CorrectionAssetError(ValueError):
    """Raised when correction inputs cannot produce trustworthy candidates."""


class _Frame(NamedTuple):
    kind: Literal["object", "array"]
    state: str
    is_root: bool = False


class _JsonInspection(NamedTuple):
    size_bytes: int
    sha256: str
    root_open_offset: int
    root_close_offset: int
    root_member_count: int
    licensing_key_count: int
    package_schema_version: str
    package_type: str


class _AssetInspection(NamedTuple):
    compressed_size_bytes: int
    compressed_sha256: str
    uncompressed: _JsonInspection


class _PreparedModel(NamedTuple):
    model_id: str
    census_year: int
    historical_path: Path
    historical: Mapping[str, object]
    record: Mapping[str, object]
    licensing: dict[str, Any]
    filename: str
    destination: Path
    inspection: _AssetInspection


class _StreamingJsonObjectValidator:
    """Validate one JSON object without retaining its values in memory."""

    def __init__(self) -> None:
        self._stack: list[_Frame] = []
        self._root_state = "value"
        self._token: Literal["string", "number", "literal"] | None = None
        self._string_is_key = False
        self._string_root_key = False
        self._string_escape = False
        self._unicode_remaining = 0
        self._string_capture: bytearray | None = None
        self._string_root_value_key: str | None = None
        self._utf8_decoder: codecs.IncrementalDecoder | None = None
        self._number_state = ""
        self._literal_remaining = b""
        self._offset = 0
        self.root_open_offset: int | None = None
        self.root_close_offset: int | None = None
        self.root_member_count = 0
        self.licensing_key_count = 0
        self.root_identity: dict[str, str] = {}
        self._current_root_key: str | None = None

    def feed(self, chunk: bytes) -> None:
        """Consume a decompressed JSON chunk."""

        for byte in chunk:
            while not self._consume(byte):
                pass
            self._offset += 1

    def finish(self) -> None:
        """Reject truncated, trailing, or otherwise incomplete JSON."""

        if self._token == "number":
            if self._number_state not in {"zero", "int", "frac", "exp_digits"}:
                raise CorrectionAssetError("model package ends in an invalid number")
            self._token = None
            self._complete_value()
        elif self._token is not None:
            raise CorrectionAssetError("model package contains truncated JSON")
        if self._stack or self._root_state != "done":
            raise CorrectionAssetError("model package contains truncated JSON")
        if self.root_close_offset is None:
            raise CorrectionAssetError("model package must be a top-level JSON object")

    def _consume(self, byte: int) -> bool:
        if self._token == "string":
            self._consume_string(byte)
            return True
        if self._token == "literal":
            self._consume_literal(byte)
            return True
        if self._token == "number":
            return self._consume_number(byte)
        self._consume_syntax(byte)
        return True

    def _consume_syntax(self, byte: int) -> None:
        if byte in b" \t\r\n":
            return
        if not self._stack:
            if self._root_state == "done":
                raise CorrectionAssetError("model package has trailing JSON data")
            if byte != ord("{"):
                raise CorrectionAssetError(
                    "model package must be a top-level JSON object"
                )
            self.root_open_offset = self._offset
            self._push("object", is_root=True)
            return

        frame = self._stack[-1]
        if frame.kind == "object":
            if frame.state == "key_or_end":
                if byte == ord("}"):
                    self._close_container("object")
                elif byte == ord('"'):
                    self._start_string(is_key=True, root_key=frame.is_root)
                else:
                    raise CorrectionAssetError("model package contains malformed JSON")
                return
            if frame.state == "key":
                if byte != ord('"'):
                    raise CorrectionAssetError("model package contains malformed JSON")
                self._start_string(is_key=True, root_key=frame.is_root)
                return
            if frame.state == "colon":
                if byte != ord(":"):
                    raise CorrectionAssetError("model package contains malformed JSON")
                self._set_top_state("value")
                return
            if frame.state == "value":
                self._start_value(byte)
                return
            if frame.state == "comma_or_end":
                if byte == ord(","):
                    self._set_top_state("key")
                elif byte == ord("}"):
                    self._close_container("object")
                else:
                    raise CorrectionAssetError("model package contains malformed JSON")
                return
        else:
            if frame.state == "value_or_end":
                if byte == ord("]"):
                    self._close_container("array")
                else:
                    self._start_value(byte)
                return
            if frame.state == "value":
                self._start_value(byte)
                return
            if frame.state == "comma_or_end":
                if byte == ord(","):
                    self._set_top_state("value")
                elif byte == ord("]"):
                    self._close_container("array")
                else:
                    raise CorrectionAssetError("model package contains malformed JSON")
                return
        raise CorrectionAssetError("model package contains malformed JSON")

    def _start_value(self, byte: int) -> None:
        if byte == ord("{"):
            self._push("object")
        elif byte == ord("["):
            self._push("array")
        elif byte == ord('"'):
            root_value_key = (
                self._current_root_key
                if self._stack[-1].is_root
                and self._current_root_key in {"schema_version", "package_type"}
                else None
            )
            self._start_string(
                is_key=False,
                root_key=False,
                root_value_key=root_value_key,
            )
        elif byte == ord("-"):
            self._token = "number"
            self._number_state = "minus"
        elif byte == ord("0"):
            self._token = "number"
            self._number_state = "zero"
        elif ord("1") <= byte <= ord("9"):
            self._token = "number"
            self._number_state = "int"
        elif byte == ord("t"):
            self._start_literal(b"rue")
        elif byte == ord("f"):
            self._start_literal(b"alse")
        elif byte == ord("n"):
            self._start_literal(b"ull")
        else:
            raise CorrectionAssetError("model package contains malformed JSON")

    def _push(self, kind: Literal["object", "array"], *, is_root: bool = False) -> None:
        if len(self._stack) >= _MAX_JSON_DEPTH:
            raise CorrectionAssetError("model package JSON nesting is too deep")
        initial = "key_or_end" if kind == "object" else "value_or_end"
        self._stack.append(_Frame(kind, initial, is_root))

    def _close_container(self, kind: Literal["object", "array"]) -> None:
        frame = self._stack[-1]
        if frame.kind != kind:
            raise CorrectionAssetError("model package contains malformed JSON")
        self._stack.pop()
        if frame.is_root:
            self.root_close_offset = self._offset
        self._complete_value()

    def _complete_value(self) -> None:
        if not self._stack:
            if self._root_state != "value":
                raise CorrectionAssetError("model package has trailing JSON data")
            self._root_state = "done"
            return
        frame = self._stack[-1]
        if frame.state not in {"value", "value_or_end"}:
            raise CorrectionAssetError("model package contains malformed JSON")
        self._set_top_state("comma_or_end")
        if frame.is_root:
            self._current_root_key = None

    def _set_top_state(self, state: str) -> None:
        frame = self._stack[-1]
        self._stack[-1] = _Frame(frame.kind, state, frame.is_root)

    def _start_string(
        self,
        *,
        is_key: bool,
        root_key: bool,
        root_value_key: str | None = None,
    ) -> None:
        self._token = "string"
        self._string_is_key = is_key
        self._string_root_key = root_key
        self._string_escape = False
        self._unicode_remaining = 0
        self._string_capture = (
            bytearray(b'"') if root_key or root_value_key is not None else None
        )
        self._string_root_value_key = root_value_key
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")("strict")

    def _consume_string(self, byte: int) -> None:
        capture = self._string_capture
        if capture is not None:
            if len(capture) < _MAX_ROOT_KEY_CAPTURE:
                capture.append(byte)
            else:
                self._string_capture = None

        if self._unicode_remaining:
            if byte not in b"0123456789abcdefABCDEF":
                raise CorrectionAssetError("model package contains an invalid escape")
            self._unicode_remaining -= 1
            if self._unicode_remaining == 0:
                self._string_escape = False
            return
        if self._string_escape:
            if byte == ord("u"):
                self._unicode_remaining = 4
            elif byte in b'"\\/bfnrt':
                self._string_escape = False
            else:
                raise CorrectionAssetError("model package contains an invalid escape")
            return
        if byte == ord('"'):
            self._finish_utf8_segment()
            self._token = None
            if self._string_is_key:
                if self._string_root_key:
                    self._finish_root_key()
                    self.root_member_count += 1
                self._set_top_state("colon")
            else:
                self._finish_root_value()
                self._complete_value()
            return
        if byte == ord("\\"):
            self._finish_utf8_segment()
            self._utf8_decoder = codecs.getincrementaldecoder("utf-8")("strict")
            self._string_escape = True
            return
        if byte < 0x20:
            raise CorrectionAssetError("model package contains a control character")
        assert self._utf8_decoder is not None
        try:
            self._utf8_decoder.decode(bytes((byte,)), final=False)
        except UnicodeDecodeError as exc:
            raise CorrectionAssetError("model package is not valid UTF-8 JSON") from exc

    def _finish_utf8_segment(self) -> None:
        assert self._utf8_decoder is not None
        try:
            self._utf8_decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise CorrectionAssetError("model package is not valid UTF-8 JSON") from exc

    def _finish_root_key(self) -> None:
        capture = self._string_capture
        if capture is None:
            return
        try:
            key = json.loads(bytes(capture).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorrectionAssetError(
                "model package contains a malformed key"
            ) from exc
        if key == "licensing":
            self.licensing_key_count += 1
        self._current_root_key = key if isinstance(key, str) else None

    def _finish_root_value(self) -> None:
        key = self._string_root_value_key
        if key is None:
            return
        capture = self._string_capture
        if capture is None:
            raise CorrectionAssetError(f"model package {key} is too long")
        try:
            value = json.loads(bytes(capture).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorrectionAssetError(
                f"model package contains malformed {key}"
            ) from exc
        if not isinstance(value, str):
            raise CorrectionAssetError(f"model package {key} must be a string")
        self.root_identity[key] = value

    def _start_literal(self, remaining: bytes) -> None:
        self._token = "literal"
        self._literal_remaining = remaining

    def _consume_literal(self, byte: int) -> None:
        if not self._literal_remaining or byte != self._literal_remaining[0]:
            raise CorrectionAssetError("model package contains malformed JSON")
        self._literal_remaining = self._literal_remaining[1:]
        if not self._literal_remaining:
            self._token = None
            self._complete_value()

    def _consume_number(self, byte: int) -> bool:
        state = self._number_state
        is_digit = ord("0") <= byte <= ord("9")
        if state == "minus":
            if byte == ord("0"):
                self._number_state = "zero"
            elif ord("1") <= byte <= ord("9"):
                self._number_state = "int"
            else:
                raise CorrectionAssetError("model package contains an invalid number")
            return True
        if state == "zero":
            if byte == ord("."):
                self._number_state = "dot"
                return True
            if byte in b"eE":
                self._number_state = "exp"
                return True
            if is_digit:
                raise CorrectionAssetError("model package contains an invalid number")
            return self._finish_number()
        if state == "int":
            if is_digit:
                return True
            if byte == ord("."):
                self._number_state = "dot"
                return True
            if byte in b"eE":
                self._number_state = "exp"
                return True
            return self._finish_number()
        if state == "dot":
            if not is_digit:
                raise CorrectionAssetError("model package contains an invalid number")
            self._number_state = "frac"
            return True
        if state == "frac":
            if is_digit:
                return True
            if byte in b"eE":
                self._number_state = "exp"
                return True
            return self._finish_number()
        if state == "exp":
            if byte in b"+-":
                self._number_state = "exp_sign"
            elif is_digit:
                self._number_state = "exp_digits"
            else:
                raise CorrectionAssetError("model package contains an invalid number")
            return True
        if state == "exp_sign":
            if not is_digit:
                raise CorrectionAssetError("model package contains an invalid number")
            self._number_state = "exp_digits"
            return True
        if state == "exp_digits":
            if is_digit:
                return True
            return self._finish_number()
        raise CorrectionAssetError("model package contains an invalid number")

    def _finish_number(self) -> bool:
        self._token = None
        self._complete_value()
        return False


def _file_integrity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _inspect_gzip_json(
    path: Path,
    *,
    expected: Mapping[str, object] | None = None,
    expected_licensing_keys: int,
) -> _AssetInspection:
    if not path.name.endswith(".json.gz"):
        raise CorrectionAssetError(f"historical asset must be .json.gz: {path}")
    compressed_size, compressed_sha256 = _file_integrity(path)
    if expected is not None:
        if compressed_size != expected.get("size_bytes"):
            raise CorrectionAssetError(f"compressed size mismatch for {path.name}")
        if compressed_sha256 != str(expected.get("sha256", "")).lower():
            raise CorrectionAssetError(f"compressed SHA-256 mismatch for {path.name}")

    validator = _StreamingJsonObjectValidator()
    digest = hashlib.sha256()
    uncompressed_size = 0
    try:
        with gzip.open(path, "rb") as source:
            while chunk := source.read(_CHUNK_BYTES):
                uncompressed_size += len(chunk)
                digest.update(chunk)
                validator.feed(chunk)
    except (EOFError, OSError) as exc:
        raise CorrectionAssetError(f"invalid gzip asset: {path.name}") from exc
    validator.finish()
    if validator.licensing_key_count != expected_licensing_keys:
        if expected_licensing_keys == 0:
            raise CorrectionAssetError(
                f"historical asset {path.name} already has an existing or duplicate "
                "top-level licensing key"
            )
        raise CorrectionAssetError(
            f"corrected asset {path.name} must contain exactly one top-level "
            "licensing key"
        )
    package_schema_version = validator.root_identity.get("schema_version")
    if package_schema_version != "synthpopcan-linked-tree-package-v1":
        raise CorrectionAssetError(
            f"unsupported model package schema in {path.name}: "
            f"{package_schema_version!r}"
        )
    package_type = validator.root_identity.get("package_type")
    if package_type != "linked_household_person":
        raise CorrectionAssetError(
            f"unsupported model package type in {path.name}: {package_type!r}"
        )
    uncompressed_sha256 = digest.hexdigest()
    if expected is not None:
        if uncompressed_size != expected.get("uncompressed_size_bytes"):
            raise CorrectionAssetError(f"uncompressed size mismatch for {path.name}")
        if uncompressed_sha256 != str(expected.get("uncompressed_sha256", "")).lower():
            raise CorrectionAssetError(f"uncompressed SHA-256 mismatch for {path.name}")
    assert validator.root_open_offset is not None
    assert validator.root_close_offset is not None
    return _AssetInspection(
        compressed_size,
        compressed_sha256,
        _JsonInspection(
            uncompressed_size,
            uncompressed_sha256,
            validator.root_open_offset,
            validator.root_close_offset,
            validator.root_member_count,
            validator.licensing_key_count,
            package_schema_version,
            package_type,
        ),
    )


def _verify_corrected_gzip(
    path: Path,
    *,
    expected_size: int,
    expected_sha256: str,
    historical: _JsonInspection,
    insertion_size: int,
) -> _AssetInspection:
    """Independently verify generated bytes without reparsing the known source."""

    compressed_size, compressed_sha256 = _file_integrity(path)
    digest = hashlib.sha256()
    size = 0
    try:
        with gzip.open(path, "rb") as source:
            while chunk := source.read(_CHUNK_BYTES):
                size += len(chunk)
                if size > expected_size:
                    raise CorrectionAssetError(
                        "corrected uncompressed size exceeds generated size"
                    )
                digest.update(chunk)
    except (EOFError, OSError) as exc:
        raise CorrectionAssetError("corrected asset is not valid gzip data") from exc
    if size != expected_size or digest.hexdigest() != expected_sha256:
        raise CorrectionAssetError("corrected asset verification changed its bytes")
    return _AssetInspection(
        compressed_size,
        compressed_sha256,
        _JsonInspection(
            size,
            expected_sha256,
            historical.root_open_offset,
            historical.root_close_offset + insertion_size,
            historical.root_member_count + 1,
            1,
            historical.package_schema_version,
            historical.package_type,
        ),
    )


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CorrectionAssetError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorrectionAssetError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CorrectionAssetError(f"{label} must be a JSON object")
    return value


def _downloadable_catalogue() -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for entry in model_catalogue():
        if entry.get("distribution") != "download":
            continue
        model_id = str(entry.get("id", ""))
        if not model_id or model_id in entries:
            raise CorrectionAssetError("installed registry has duplicate model IDs")
        entries[model_id] = entry
    if not entries:
        raise CorrectionAssetError("installed registry has no downloadable models")
    return entries


def _selection(
    known: Mapping[str, object], test_subset: Sequence[str]
) -> tuple[list[str], str]:
    if not test_subset:
        if len(known) != 32:
            raise CorrectionAssetError(
                "complete-catalogue mode requires exactly the 32 known downloadable "
                "models"
            )
        return sorted(known), "complete-catalogue"
    if len(test_subset) > _MAX_TEST_SUBSET_MODELS:
        raise CorrectionAssetError(
            f"test-subset mode is bounded to {_MAX_TEST_SUBSET_MODELS} models"
        )
    if len(test_subset) != len(set(test_subset)):
        raise CorrectionAssetError("test-subset contains duplicate model IDs")
    unknown = set(test_subset) - set(known)
    if unknown:
        raise CorrectionAssetError(f"unknown model IDs: {sorted(unknown)}")
    return sorted(test_subset), "test-subset"


def _record_mapping(
    path: Path, *, selected: Sequence[str], known: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    document = _load_json_object(path, label="record index")
    if document.get("schema_version") != _RECORD_INDEX_SCHEMA:
        raise CorrectionAssetError("unsupported record-index schema")
    records = document.get("records")
    if not isinstance(records, dict):
        raise CorrectionAssetError("record index must contain a records object")
    actual = set(records)
    expected = set(selected)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise CorrectionAssetError(
            f"record index model set mismatch; missing={missing}, unknown={unknown}"
        )

    validated: dict[str, dict[str, Any]] = {}
    record_ids: set[int] = set()
    doi_identities: set[str] = set()
    for model_id in selected:
        value = records[model_id]
        if not isinstance(value, dict):
            raise CorrectionAssetError(f"{model_id}: record identity must be an object")
        if set(value) != {
            "latest_record_id",
            "concept_doi",
            "version_doi",
        }:
            raise CorrectionAssetError(
                f"{model_id}: record identity fields are not exact"
            )
        record_id = value["latest_record_id"]
        concept_doi = value["concept_doi"]
        version_doi = value["version_doi"]
        if (
            not isinstance(record_id, int)
            or isinstance(record_id, bool)
            or record_id < 1
        ):
            raise CorrectionAssetError(f"{model_id}: latest_record_id must be positive")
        if not isinstance(concept_doi, str) or not _DOI_PATTERN.fullmatch(concept_doi):
            raise CorrectionAssetError(f"{model_id}: invalid concept DOI")
        if not isinstance(version_doi, str) or not _DOI_PATTERN.fullmatch(version_doi):
            raise CorrectionAssetError(f"{model_id}: invalid version DOI")
        if concept_doi != known[model_id].get("doi"):
            raise CorrectionAssetError(
                f"{model_id}: concept DOI conflicts with the installed registry"
            )
        if version_doi == concept_doi:
            raise CorrectionAssetError(
                f"{model_id}: version DOI must differ from its concept DOI"
            )
        if version_doi != f"10.5281/zenodo.{record_id}":
            raise CorrectionAssetError(
                f"{model_id}: version DOI must identify latest_record_id"
            )
        if (
            record_id in record_ids
            or concept_doi in doi_identities
            or version_doi in doi_identities
        ):
            raise CorrectionAssetError(
                "record index contains duplicate record identities"
            )
        record_ids.add(record_id)
        doi_identities.update((concept_doi, version_doi))
        validated[model_id] = value
    return validated


def _licensing_by_year(
    paths: Mapping[int, Path],
    *,
    selected: Sequence[str],
    known: Mapping[str, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    needed = {_model_census_year(known[model_id], model_id) for model_id in selected}
    if set(paths) != needed:
        raise CorrectionAssetError(
            "licensing inputs must exactly cover the selected Census vintages"
        )
    result: dict[int, dict[str, Any]] = {}
    for year in sorted(needed):
        raw = _load_json_object(paths[year], label=f"{year} licensing")
        try:
            licensing = validate_prepared_model_licensing(raw)
        except ValueError as exc:
            raise CorrectionAssetError(
                f"{year} licensing is not the exact validated contract"
            ) from exc
        representative = next(
            known[model_id]["licensing"]
            for model_id in selected
            if _model_census_year(known[model_id], model_id) == year
        )
        for field in (
            "schema_version",
            "package_basis",
            "presentation",
            "authored_material",
            "source_information",
        ):
            if licensing.get(field) != representative.get(field):
                raise CorrectionAssetError(
                    f"{year} licensing conflicts with the catalogue vintage"
                )
        result[year] = licensing
    return result


def _model_census_year(entry: Mapping[str, Any], model_id: str) -> int:
    vintage = entry.get("census_vintage")
    if vintage == "2016 Census":
        return 2016
    if vintage == "2021 Census":
        return 2021
    raise CorrectionAssetError(f"{model_id}: unsupported Census vintage {vintage!r}")


def _historical_filename(metadata: Mapping[str, object], model_id: str) -> str:
    if metadata.get("compression") != "gzip":
        raise CorrectionAssetError(f"{model_id}: historical asset is not gzip")
    url = metadata.get("url")
    if not isinstance(url, str):
        raise CorrectionAssetError(f"{model_id}: registry has no historical URL")
    filename = Path(urllib.parse.urlparse(url).path).name
    if not filename.endswith(".json.gz"):
        raise CorrectionAssetError(f"{model_id}: registry URL is not a .json.gz asset")
    return filename


def _new_filename(historical_filename: str, new_version: str) -> str:
    stem = historical_filename.removesuffix(".json.gz")
    return f"{stem}-{new_version}.json.gz"


def _validate_version(new_version: str, known: Mapping[str, Mapping[str, Any]]) -> None:
    if not _VERSION_PATTERN.fullmatch(new_version) or ".." in new_version:
        raise CorrectionAssetError("new package version is not filename-safe")
    old_versions = {str(entry.get("release_version")) for entry in known.values()}
    if new_version in old_versions:
        raise CorrectionAssetError("corrected package needs a new package version")


def _write_corrected_asset(prepared: _PreparedModel) -> _AssetInspection:
    licensing_bytes = json.dumps(
        prepared.licensing,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    separator = b"," if prepared.inspection.uncompressed.root_member_count else b""
    insertion = b'"licensing":' + licensing_bytes + separator
    destination = prepared.destination
    if destination.exists():
        raise CorrectionAssetError(f"refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".json.gz", dir=destination.parent
    )
    raw_target = os.fdopen(descriptor, "wb")
    temporary = Path(temporary_name)
    plain_digest = hashlib.sha256()
    plain_size = 0
    source_digest = hashlib.sha256()
    source_size = 0
    source_offset = 0
    inserted = False

    def write_plain(target: gzip.GzipFile, value: bytes) -> None:
        nonlocal plain_size
        target.write(value)
        plain_digest.update(value)
        plain_size += len(value)

    try:
        with prepared.historical_path.open("rb") as raw_source:
            with raw_target:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    compresslevel=9,
                    fileobj=raw_target,
                    mtime=0,
                ) as target:
                    source = gzip.GzipFile(fileobj=raw_source, mode="rb")
                    try:
                        while chunk := source.read(_CHUNK_BYTES):
                            source_digest.update(chunk)
                            source_size += len(chunk)
                            insertion_offset = (
                                prepared.inspection.uncompressed.root_open_offset + 1
                            )
                            end = source_offset + len(chunk)
                            if not inserted and source_offset <= insertion_offset < end:
                                split = insertion_offset - source_offset
                                write_plain(target, chunk[:split])
                                write_plain(target, insertion)
                                write_plain(target, chunk[split:])
                                inserted = True
                            else:
                                write_plain(target, chunk)
                            source_offset = end
                    except (EOFError, OSError) as exc:
                        raise CorrectionAssetError(
                            "historical source became invalid during transformation"
                        ) from exc
                    finally:
                        source.close()
            if (
                source_size != prepared.inspection.uncompressed.size_bytes
                or source_digest.hexdigest() != prepared.inspection.uncompressed.sha256
            ):
                raise CorrectionAssetError(
                    "historical source changed after preflight verification"
                )
            raw_source.seek(0)
            compressed_digest = hashlib.sha256()
            compressed_size = 0
            while chunk := raw_source.read(_CHUNK_BYTES):
                compressed_digest.update(chunk)
                compressed_size += len(chunk)
            if (
                compressed_size != prepared.inspection.compressed_size_bytes
                or compressed_digest.hexdigest()
                != prepared.inspection.compressed_sha256
            ):
                raise CorrectionAssetError(
                    "historical compressed source changed after preflight verification"
                )
        if not inserted:
            raise CorrectionAssetError(
                f"could not locate root object open in {prepared.historical_path.name}"
            )
        expected_size = prepared.inspection.uncompressed.size_bytes + len(insertion)
        if plain_size != expected_size:
            raise CorrectionAssetError("corrected uncompressed size is inconsistent")
        generated_sha = plain_digest.hexdigest()
        verified = _verify_corrected_gzip(
            temporary,
            expected_size=plain_size,
            expected_sha256=generated_sha,
            historical=prepared.inspection.uncompressed,
            insertion_size=len(insertion),
        )
        if (
            verified.uncompressed.size_bytes != plain_size
            or verified.uncompressed.sha256 != generated_sha
        ):
            raise CorrectionAssetError("corrected asset verification changed its bytes")
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise CorrectionAssetError(f"refusing to overwrite {destination}") from exc
        temporary.unlink()
        return verified
    finally:
        raw_target.close()
        temporary.unlink(missing_ok=True)


def build_correction_candidates(
    *,
    assets_dir: Path,
    record_index_path: Path,
    licensing_paths: Mapping[int, Path],
    new_package_version: str,
    output_dir: Path,
    test_subset: Sequence[str] = (),
) -> Path:
    """Build verified corrected archives and return their candidate-index path."""

    known = _downloadable_catalogue()
    selected, mode = _selection(known, test_subset)
    _validate_version(
        new_package_version, {model_id: known[model_id] for model_id in selected}
    )
    records = _record_mapping(record_index_path, selected=selected, known=known)
    licensing = _licensing_by_year(licensing_paths, selected=selected, known=known)
    index_path = output_dir / "correction-candidates.json"
    if output_dir.exists():
        raise CorrectionAssetError(
            f"refusing to overwrite correction bundle directory {output_dir}"
        )

    preflight: list[_PreparedModel] = []
    output_names: set[str] = set()
    for model_id in selected:
        entry = known[model_id]
        historical = model_registry_entry(model_id)
        if historical.get("contains_embedded_licensing") is True:
            raise CorrectionAssetError(
                f"{model_id}: installed registry already points to a corrected "
                "package with embedded licensing"
            )
        historical_filename = _historical_filename(historical, model_id)
        historical_path = assets_dir / historical_filename
        if not historical_path.is_file():
            raise CorrectionAssetError(
                f"missing historical asset for {model_id}: {historical_path}"
            )
        filename = _new_filename(historical_filename, new_package_version)
        if filename in output_names:
            raise CorrectionAssetError("corrected output filenames are not unique")
        output_names.add(filename)
        destination = output_dir / filename
        inspection = _inspect_gzip_json(
            historical_path,
            expected=historical,
            expected_licensing_keys=0,
        )
        year = _model_census_year(entry, model_id)
        preflight.append(
            _PreparedModel(
                model_id,
                year,
                historical_path,
                historical,
                records[model_id],
                licensing[year],
                filename,
                destination,
                inspection,
            )
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.", suffix=".staging", dir=output_dir.parent
        )
    )
    staged_paths: list[Path] = []
    published_paths: list[Path] = []
    bundle_created = False
    bundle_committed = False
    try:
        candidates: dict[str, dict[str, Any]] = {}
        for prepared in preflight:
            staged = prepared._replace(destination=staging / prepared.filename)
            corrected = _write_corrected_asset(staged)
            staged_paths.append(staged.destination)
            record = prepared.record
            catalogue_entry = known[prepared.model_id]
            historical_asset = {
                "filename": prepared.historical_path.name,
                "size_bytes": prepared.inspection.compressed_size_bytes,
                "sha256": prepared.inspection.compressed_sha256,
                "uncompressed_size_bytes": prepared.inspection.uncompressed.size_bytes,
                "uncompressed_sha256": prepared.inspection.uncompressed.sha256,
                "contains_embedded_licensing": False,
            }
            candidate_asset = {
                "filename": prepared.filename,
                "asset_url": (output_dir / prepared.filename).resolve().as_uri(),
                "size_bytes": corrected.compressed_size_bytes,
                "sha256": corrected.compressed_sha256,
                "uncompressed_size_bytes": corrected.uncompressed.size_bytes,
                "uncompressed_sha256": corrected.uncompressed.sha256,
                "contains_embedded_licensing": True,
            }
            candidates[prepared.model_id] = {
                "model_id": prepared.model_id,
                "census_vintage": str(catalogue_entry["census_vintage"]),
                "package_schema_version": (
                    prepared.inspection.uncompressed.package_schema_version
                ),
                "package_type": prepared.inspection.uncompressed.package_type,
                "existing_package_version": str(catalogue_entry["release_version"]),
                "existing_record_id": record["latest_record_id"],
                "existing_concept_doi": record["concept_doi"],
                "existing_version_doi": record["version_doi"],
                "new_package_version": new_package_version,
                "licensing_schema_version": prepared.licensing["schema_version"],
                "licensing": prepared.licensing,
                "historical_asset": historical_asset,
                "candidate_asset": candidate_asset,
                # Retain the v1 flat asset hand-off consumed by the deposition
                # builder; the nested objects bind both sides for the executor.
                "filename": candidate_asset["filename"],
                "asset_url": candidate_asset["asset_url"],
                "size_bytes": candidate_asset["size_bytes"],
                "sha256": candidate_asset["sha256"],
                "uncompressed_size_bytes": candidate_asset["uncompressed_size_bytes"],
                "uncompressed_sha256": candidate_asset["uncompressed_sha256"],
                "transformation": "rights-metadata-only-top-level-field-insertion",
                "model_retrained": False,
                "historical_json_preserved_except_inserted_licensing": True,
            }

        policy_accepted = all(
            candidate["licensing"]["policy_decision"]["status"] == "accepted"
            for candidate in candidates.values()
        )
        production_ready = mode == "complete-catalogue" and policy_accepted
        document = {
            "schema_version": _CANDIDATE_SCHEMA,
            "build_scope": mode,
            "production_coverage_complete": mode == "complete-catalogue",
            "production_ready": production_ready,
            "non_production_reason": (
                None
                if production_ready
                else (
                    "bounded test subset; never eligible for production"
                    if mode == "test-subset"
                    else "the maintained rights policy is not accepted"
                )
            ),
            "network_writes": False,
            "model_retrained": False,
            "new_package_version": new_package_version,
            "candidate_count": len(candidates),
            "candidate_model_ids": sorted(candidates),
            "candidates": candidates,
        }
        staged_index = staging / index_path.name
        try:
            with staged_index.open("x", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise CorrectionAssetError(
                "could not write the staged correction-candidate index"
            ) from exc
        staged_paths.append(staged_index)

        try:
            output_dir.mkdir()
        except FileExistsError as exc:
            raise CorrectionAssetError(
                f"refusing to overwrite correction bundle directory {output_dir}"
            ) from exc
        bundle_created = True
        for staged_path in staged_paths:
            published = output_dir / staged_path.name
            try:
                os.link(staged_path, published)
            except FileExistsError as exc:
                raise CorrectionAssetError(
                    f"refusing to overwrite {published}"
                ) from exc
            published_paths.append(published)
            staged_path.unlink()
        staging.rmdir()
        bundle_committed = True
        return index_path
    finally:
        if not bundle_committed:
            for published in published_paths:
                published.unlink(missing_ok=True)
        for staged_path in staged_paths:
            staged_path.unlink(missing_ok=True)
        if staging.exists():
            for unexpected in staging.iterdir():
                if unexpected.parent == staging and unexpected.is_file():
                    unexpected.unlink(missing_ok=True)
        try:
            staging.rmdir()
        except OSError:
            pass
        if bundle_created and not bundle_committed:
            try:
                output_dir.rmdir()
            except OSError:
                pass


@click.command()
@click.option(
    "--assets-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Directory containing the checksum-bound historical .json.gz assets.",
)
@click.option(
    "--record-index",
    "record_index_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
    help="Explicit model-to-latest-record identity index.",
)
@click.option(
    "--licensing-2016",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Exact validated 2016 prepared-model licensing JSON object.",
)
@click.option(
    "--licensing-2021",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Exact validated 2021 prepared-model licensing JSON object.",
)
@click.option("--new-package-version", required=True)
@click.option(
    "--out",
    "output_dir",
    type=click.Path(path_type=Path),
    required=True,
)
@click.option(
    "--test-subset",
    "test_subset",
    multiple=True,
    metavar="MODEL_ID",
    help=(
        "Build an explicitly non-production subset (repeat for at most eight IDs). "
        "Omit to require all 32 downloadable models."
    ),
)
def main(
    assets_dir: Path,
    record_index_path: Path,
    licensing_2016: Path | None,
    licensing_2021: Path | None,
    new_package_version: str,
    output_dir: Path,
    test_subset: tuple[str, ...],
) -> None:
    """Build local corrected package candidates without any network calls."""

    licensing_paths = {
        year: path
        for year, path in ((2016, licensing_2016), (2021, licensing_2021))
        if path is not None
    }
    try:
        index = build_correction_candidates(
            assets_dir=assets_dir,
            record_index_path=record_index_path,
            licensing_paths=licensing_paths,
            new_package_version=new_package_version,
            output_dir=output_dir,
            test_subset=test_subset,
        )
    except CorrectionAssetError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wrote {index}")
    click.echo(
        "Local candidates only: no model was retrained and no network or archive "
        "write was made. Review the index before building deposition manifests."
    )


if __name__ == "__main__":
    main()
