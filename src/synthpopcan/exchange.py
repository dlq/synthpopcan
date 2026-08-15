"""Simulator-neutral exchange bundles for linked synthetic populations."""

from __future__ import annotations

__all__ = [
    "EXCHANGE_SCHEMA_VERSION",
    "ExchangeBundle",
    "create_exchange_bundle",
    "read_exchange_manifest",
    "validate_exchange_bundle",
]

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from synthpopcan._runtime_schemas import RunManifest
from synthpopcan.geography import GeographyUniverse
from synthpopcan.linked_schema import (
    LINKED_POPULATION_SCHEMA_VERSION,
    build_linked_population_contract,
    validate_linked_population_contract,
)
from synthpopcan.tree import validate_linked_population_files

EXCHANGE_SCHEMA_VERSION = "synthpopcan-exchange-v1"
_PROVENANCE_SCHEMA_VERSION = "synthpopcan-exchange-provenance-v1"
_DICTIONARY_SCHEMA_VERSION = "synthpopcan-data-dictionary-v1"
_VALIDATION_SCHEMA_VERSION = "synthpopcan-exchange-validation-v1"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ACCESS_CLASSES = frozenset({"public", "local", "licensed", "restricted"})
_REDISTRIBUTION_STATUSES = frozenset({"permitted", "not-permitted", "not-assessed"})
_REQUIRED_FILES = {
    "households": ("households.csv", "text/csv"),
    "persons": ("persons.csv", "text/csv"),
    "linked_population": ("linked-population.json", "application/json"),
    "data_dictionary": ("data-dictionary.json", "application/json"),
    "provenance": ("provenance.json", "application/json"),
    "validation": ("validation.json", "application/json"),
}
_KNOWN_SIMULATION_INPUTS = (
    "behavioural rules and intervention logic",
    "activities, schedules, and locations",
    "transport or contact networks",
    "target-specific settings and coefficients",
)


class _BoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _FileRecord(_BoundaryModel):
    logical_name: str
    path: str
    media_type: Literal["text/csv", "application/json"]
    byte_size: int = Field(ge=0)
    sha256: str
    row_count: int | None = Field(default=None, ge=0)
    access_classification: Literal["public", "local", "licensed", "restricted"]
    redistribution_status: Literal["permitted", "not-permitted", "not-assessed"]


class _ExchangeManifest(_BoundaryModel):
    schema_version: Literal["synthpopcan-exchange-v1"]
    synthpopcan_version: str
    bundle_kind: Literal["population-contribution"]
    files: list[_FileRecord]
    relationships: list[dict[str, Any]]
    geography: dict[str, Any] | None
    temporal_coverage: dict[str, str] | None
    missing_simulation_inputs: list[str]
    limitations: list[str]


class _DictionaryColumn(_BoundaryModel):
    name: str
    storage_type: Literal["string"]
    role: Literal[
        "attribute",
        "primary-key",
        "foreign-key",
        "geography-identifier",
        "weight",
    ]
    unit: str | None
    code_list: str | None
    missing_value: Literal["empty-string"] | None
    value_status: Literal["modeled"]


class _DictionaryTable(_BoundaryModel):
    name: Literal["households", "persons"]
    columns: list[_DictionaryColumn]


class _DataDictionary(_BoundaryModel):
    schema_version: Literal["synthpopcan-data-dictionary-v1"]
    format: Literal["csv"]
    encoding: Literal["utf-8"]
    tables: list[_DictionaryTable]
    notes: list[str]


class _Provenance(_BoundaryModel):
    schema_version: Literal["synthpopcan-exchange-provenance-v1"]
    origin: dict[str, Any]
    reproduction: dict[str, Any]


class _StoredValidation(_BoundaryModel):
    schema_version: Literal["synthpopcan-exchange-validation-v1"]
    passed: Literal[True]
    checks: dict[str, bool]
    linked_population: dict[str, Any]
    reproduction: dict[str, Any]
    limitations: list[str]


@dataclass(frozen=True)
class ExchangeBundle:
    """Paths and validation for one simulator-neutral population bundle."""

    directory: Path
    manifest: Path
    households: Path
    persons: Path
    linked_population: Path
    data_dictionary: Path
    provenance: Path
    validation: Path
    report: Mapping[str, Any]


def create_exchange_bundle(
    population: str | Path,
    output_dir: str | Path,
    *,
    geography_universe: GeographyUniverse | Mapping[str, object] | None = None,
    run_manifest: str | Path | None = None,
    reproduction: Mapping[str, object] | None = None,
    temporal_coverage: Mapping[str, str] | None = None,
    access_classification: str = "local",
    redistribution_status: str = "not-assessed",
    limitations: Sequence[str] = (),
) -> ExchangeBundle:
    """Create an atomic, self-describing CSV/JSON population contribution.

    The source directory must contain ``households.csv`` and ``persons.csv``.
    A linked-population descriptor may be the top-level ``manifest.json`` or a
    ``linked_population`` object inside a generation manifest. The source bytes
    are copied unchanged, then independently hashed and validated.
    """

    source = Path(population).resolve()
    destination = Path(output_dir).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"linked population directory not found: {source}")
    if destination == source or destination.is_relative_to(source):
        raise ValueError("exchange output must not be the source population directory")
    if destination.exists():
        raise FileExistsError(f"exchange output already exists: {destination}")
    if access_classification not in _ACCESS_CLASSES:
        raise ValueError("unsupported access classification")
    if redistribution_status not in _REDISTRIBUTION_STATUSES:
        raise ValueError("unsupported redistribution status")
    normalized_limitations = _string_list(limitations, "limitations")
    normalized_temporal = _optional_string_mapping(
        temporal_coverage, "temporal coverage"
    )
    normalized_geography = _geography_universe(geography_universe)

    households_source = source / "households.csv"
    persons_source = source / "persons.csv"
    for label, path in (("household", households_source), ("person", persons_source)):
        if not path.is_file():
            raise FileNotFoundError(f"linked population {label} CSV not found: {path}")
    source_contract = _source_linked_contract(source, households_source, persons_source)
    _validate_geography(source_contract, normalized_geography)
    if normalized_geography is not None:
        _validate_geography_values(households_source, normalized_geography)
    linkage = validate_linked_population_files(
        households_source,
        persons_source,
        household_size_column=None,
    )
    if linkage.get("passed") is not True:
        raise ValueError(_linkage_error(linkage))

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        households = temporary / "households.csv"
        persons = temporary / "persons.csv"
        shutil.copyfile(households_source, households)
        shutil.copyfile(persons_source, persons)
        if _sha256(households) != _sha256(households_source):
            raise RuntimeError("household bytes changed while creating the exchange")
        if _sha256(persons) != _sha256(persons_source):
            raise RuntimeError("person bytes changed while creating the exchange")

        linked_contract = build_linked_population_contract(
            households,
            persons,
            geography_column=_household_geography_column(source_contract),
            licensing=_linked_population_licensing(source_contract),
        )
        linked_path = temporary / "linked-population.json"
        _write_json(linked_path, linked_contract)

        dictionary = _build_data_dictionary(households, persons, linked_contract)
        dictionary_path = temporary / "data-dictionary.json"
        _write_json(dictionary_path, dictionary)

        provenance_payload = _build_provenance(
            source=source,
            source_manifest=source / "manifest.json",
            run_manifest=Path(run_manifest) if run_manifest is not None else None,
            reproduction=reproduction,
            output_dir=destination,
        )
        provenance_path = temporary / "provenance.json"
        _write_json(provenance_path, provenance_payload)

        validation_payload = {
            "schema_version": _VALIDATION_SCHEMA_VERSION,
            "passed": True,
            "checks": {
                "source_linked_contract": True,
                "household_person_linkage": True,
                "source_bytes_preserved": True,
                "data_dictionary_complete": True,
                "geography_context_explicit": normalized_geography is not None,
            },
            "linked_population": linkage,
            "reproduction": provenance_payload["reproduction"],
            "limitations": [
                "Validation establishes bundle integrity and implemented linkage "
                "rules; it does not establish fitness for every simulation or "
                "substantive research use.",
                *normalized_limitations,
            ],
        }
        validation_path = temporary / "validation.json"
        _write_json(validation_path, validation_payload)

        files = [
            _file_record(
                logical_name,
                temporary / filename,
                media_type,
                access_classification=access_classification,
                redistribution_status=redistribution_status,
            )
            for logical_name, (filename, media_type) in _REQUIRED_FILES.items()
        ]
        manifest_payload = {
            "schema_version": EXCHANGE_SCHEMA_VERSION,
            "synthpopcan_version": _synthpopcan_version(),
            "bundle_kind": "population-contribution",
            "files": files,
            "relationships": linked_contract["relationships"],
            "geography": (
                normalized_geography.as_dict()
                if normalized_geography is not None
                else None
            ),
            "temporal_coverage": normalized_temporal,
            "missing_simulation_inputs": list(_KNOWN_SIMULATION_INPUTS),
            "limitations": [
                "This bundle contributes a synthetic population; it is not a "
                "runnable simulation and contains no observed residence claims.",
                *normalized_limitations,
            ],
        }
        _validate_manifest_payload(manifest_payload)
        _write_json(temporary / "manifest.json", manifest_payload)
        report = validate_exchange_bundle(temporary)
        if report["passed"] is not True:
            raise RuntimeError(
                "new exchange bundle failed validation: " + "; ".join(report["issues"])
            )
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return _bundle_result(destination, report)


def read_exchange_manifest(path: str | Path) -> dict[str, Any]:
    """Read and strictly validate an exchange v1 manifest JSON document."""

    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{manifest_path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("exchange manifest must be a JSON object")
    return _validate_manifest_payload(payload)


def validate_exchange_bundle(bundle: str | Path) -> dict[str, Any]:
    """Recompute hashes, shapes, linkage, and metadata for an exchange bundle."""

    directory = Path(bundle)
    issues: list[str] = []
    try:
        manifest = read_exchange_manifest(directory / "manifest.json")
    except (OSError, ValueError) as exc:
        return {
            "schema_version": _VALIDATION_SCHEMA_VERSION,
            "passed": False,
            "issues": [str(exc)],
            "checks": {},
        }

    records = {str(item["logical_name"]): item for item in manifest["files"]}
    if set(records) != set(_REQUIRED_FILES):
        issues.append("manifest must name exactly the required exchange files")
    expected_paths = {
        "manifest.json",
        *(value[0] for value in _REQUIRED_FILES.values()),
    }
    try:
        actual_paths = {path.name for path in directory.iterdir()}
    except OSError as exc:
        return {
            "schema_version": _VALIDATION_SCHEMA_VERSION,
            "passed": False,
            "issues": [str(exc)],
            "checks": {},
        }
    unexpected = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    if unexpected:
        issues.append("unexpected bundle files: " + ", ".join(unexpected))
    if missing:
        issues.append("missing bundle files: " + ", ".join(missing))

    for logical_name, (filename, media_type) in _REQUIRED_FILES.items():
        record = records.get(logical_name)
        if record is None:
            continue
        if record.get("path") != filename:
            issues.append(f"{logical_name} path must be {filename}")
            continue
        if record.get("media_type") != media_type:
            issues.append(f"{logical_name} media type is invalid")
        path = directory / filename
        if not path.is_file():
            continue
        if record.get("byte_size") != path.stat().st_size:
            issues.append(f"{logical_name} byte size does not match")
        if record.get("sha256") != _sha256(path):
            issues.append(f"{logical_name} SHA-256 does not match")
        expected_rows = _csv_row_count(path) if media_type == "text/csv" else None
        if record.get("row_count") != expected_rows:
            issues.append(f"{logical_name} row count does not match")

    linked_payload: dict[str, Any] | None = None
    try:
        linked_raw = json.loads((directory / "linked-population.json").read_text())
        if not isinstance(linked_raw, dict):
            raise ValueError("linked-population.json must contain an object")
        validate_linked_population_contract(linked_raw)
        linked_payload = linked_raw
        rebuilt = build_linked_population_contract(
            directory / "households.csv",
            directory / "persons.csv",
            geography_column=_household_geography_column(linked_raw),
            licensing=_linked_population_licensing(linked_raw),
        )
        if rebuilt != linked_raw:
            issues.append("linked-population descriptor does not match the CSV files")
        if manifest.get("relationships") != linked_raw.get("relationships"):
            issues.append(
                "exchange relationships do not match the linked-population descriptor"
            )
        linkage = validate_linked_population_files(
            directory / "households.csv",
            directory / "persons.csv",
            household_size_column=None,
        )
        if linkage.get("passed") is not True:
            issues.append(_linkage_error(linkage))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"linked population is invalid: {exc}")

    try:
        dictionary = _json_object(directory / "data-dictionary.json")
        _validate_dictionary(dictionary, linked_payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"data dictionary is invalid: {exc}")
    try:
        provenance = _json_object(directory / "provenance.json")
        _validate_provenance(provenance)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"provenance is invalid: {exc}")
    try:
        validation = _json_object(directory / "validation.json")
        _validate_stored_validation(validation)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"stored validation is invalid: {exc}")

    geography_payload = manifest.get("geography")
    if geography_payload is not None:
        try:
            universe = GeographyUniverse.from_dict(geography_payload)
            if linked_payload is not None:
                _validate_geography(linked_payload, universe)
            _validate_geography_values(directory / "households.csv", universe)
        except (OSError, ValueError) as exc:
            issues.append(f"geography is invalid: {exc}")
    return {
        "schema_version": _VALIDATION_SCHEMA_VERSION,
        "passed": not issues,
        "issues": issues,
        "checks": {
            "required_files": not unexpected and not missing,
            "hashes_and_sizes": not any(
                "SHA-256" in issue or "byte size" in issue for issue in issues
            ),
            "linked_population": not any(
                issue.startswith("linked population") for issue in issues
            ),
            "metadata": not any(
                issue.startswith(
                    ("data dictionary", "provenance", "stored validation", "geography")
                )
                for issue in issues
            ),
        },
    }


def _validate_manifest_payload(payload: Mapping[str, object]) -> dict[str, Any]:
    try:
        manifest = _ExchangeManifest.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"invalid exchange manifest: {exc.errors()[0]['msg']}"
        ) from exc
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for record in manifest.files:
        if record.logical_name in seen_names:
            raise ValueError("exchange manifest logical names must be unique")
        if record.path in seen_paths:
            raise ValueError("exchange manifest paths must be unique")
        if Path(record.path).name != record.path:
            raise ValueError("exchange manifest paths must be filenames")
        if not _SHA256.fullmatch(record.sha256):
            raise ValueError("exchange manifest SHA-256 values are invalid")
        seen_names.add(record.logical_name)
        seen_paths.add(record.path)
    return manifest.model_dump()


def _source_linked_contract(
    directory: Path, households: Path, persons: Path
) -> dict[str, Any]:
    manifest_path = directory / "manifest.json"
    if manifest_path.is_file():
        payload = _json_object(manifest_path)
        if payload.get("schema_version") == LINKED_POPULATION_SCHEMA_VERSION:
            validate_linked_population_contract(payload)
            contract = payload
        else:
            nested = payload.get("linked_population")
            if not isinstance(nested, dict):
                raise ValueError(
                    "population manifest must be linked-population v1 or contain "
                    "a linked_population descriptor"
                )
            validate_linked_population_contract(nested)
            contract = nested
    else:
        contract = build_linked_population_contract(households, persons)
    rebuilt = build_linked_population_contract(
        households,
        persons,
        geography_column=_household_geography_column(contract),
        licensing=_linked_population_licensing(contract),
    )
    if rebuilt != contract:
        raise ValueError("source linked-population descriptor does not match its CSVs")
    return contract


def _linked_population_licensing(
    contract: Mapping[str, object],
) -> Mapping[str, object] | None:
    licensing = contract.get("licensing")
    if licensing is None:
        return None
    if not isinstance(licensing, Mapping):  # pragma: no cover - validated upstream
        raise ValueError("linked population licensing must be an object")
    return licensing


def _build_data_dictionary(
    households: Path, persons: Path, contract: Mapping[str, Any]
) -> dict[str, Any]:
    geography_column = _household_geography_column(contract)
    tables = []
    for table_name, path in (("households", households), ("persons", persons)):
        columns, missing = _csv_columns_and_missing(path)
        table_columns = []
        for column in columns:
            role = "attribute"
            if column == "synthetic_household_id":
                role = "primary-key" if table_name == "households" else "foreign-key"
            elif column == "synthetic_person_id":
                role = "primary-key"
            elif column == geography_column:
                role = "geography-identifier"
            elif "weight" in column.lower():
                role = "weight"
            table_columns.append(
                {
                    "name": column,
                    "storage_type": "string",
                    "role": role,
                    "unit": None,
                    "code_list": None,
                    "missing_value": "empty-string" if missing[column] else None,
                    "value_status": "modeled",
                }
            )
        tables.append({"name": table_name, "columns": table_columns})
    return {
        "schema_version": _DICTIONARY_SCHEMA_VERSION,
        "format": "csv",
        "encoding": "utf-8",
        "tables": tables,
        "notes": [
            "CSV values are stored as strings; identifiers and categorical codes "
            "must not be coerced to numbers without consulting source metadata.",
            "A modeled value is synthetic and must not be interpreted as an "
            "observed person, household, or residence.",
        ],
    }


def _validate_dictionary(
    payload: Mapping[str, Any], linked: Mapping[str, Any] | None
) -> None:
    try:
        dictionary = _DataDictionary.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid data dictionary: {exc.errors()[0]['msg']}") from exc
    tables = dictionary.model_dump()["tables"]
    if linked is None:
        return
    linked_tables = linked.get("tables")
    if not isinstance(linked_tables, Mapping):
        raise ValueError("linked tables are missing")
    by_name = {
        table.get("name"): table
        for table in tables
        if isinstance(table, Mapping) and isinstance(table.get("name"), str)
    }
    if set(by_name) != {"households", "persons"}:
        raise ValueError("data dictionary must describe households and persons")
    for table_name in ("households", "persons"):
        table = by_name[table_name]
        columns = table.get("columns")
        if not isinstance(columns, list):
            raise ValueError(f"{table_name} dictionary columns must be a list")
        names = [item.get("name") for item in columns if isinstance(item, Mapping)]
        expected = linked_tables[table_name]["columns"]
        if names != expected:
            raise ValueError(f"{table_name} dictionary columns do not match")


def _validate_provenance(payload: Mapping[str, Any]) -> None:
    try:
        provenance = _Provenance.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid provenance: {exc.errors()[0]['msg']}") from exc
    origin = provenance.origin
    kind = origin.get("kind")
    if kind == "standalone-linked-population":
        digest = origin.get("linked_population_manifest_sha256")
        if digest is not None and (
            not isinstance(digest, str) or not _SHA256.fullmatch(digest)
        ):
            raise ValueError("standalone provenance manifest hash is invalid")
    elif kind == "durable-run":
        required = ("run_schema_version", "run_id", "workflow", "synthpopcan_version")
        if any(
            not isinstance(origin.get(name), str) or not origin[name]
            for name in required
        ):
            raise ValueError("durable-run provenance is incomplete")
        digest = origin.get("run_manifest_sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("durable-run provenance manifest hash is invalid")
    else:
        raise ValueError("unsupported provenance origin")
    _validate_reproduction(provenance.reproduction)


def _validate_stored_validation(payload: Mapping[str, Any]) -> None:
    try:
        validation = _StoredValidation.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"invalid stored validation: {exc.errors()[0]['msg']}"
        ) from exc
    _validate_reproduction(validation.reproduction)


def _validate_reproduction(payload: Mapping[str, Any]) -> None:
    if not payload:
        raise ValueError("reproduction request must not be empty")
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("reproduction request must be JSON serializable") from exc


def _build_provenance(
    *,
    source: Path,
    source_manifest: Path,
    run_manifest: Path | None,
    reproduction: Mapping[str, object] | None,
    output_dir: Path,
) -> dict[str, Any]:
    origin: dict[str, Any] = {
        "kind": "standalone-linked-population",
        "linked_population_manifest_sha256": (
            _sha256(source_manifest) if source_manifest.is_file() else None
        ),
    }
    run_reproduction: object | None = None
    if run_manifest is not None:
        run = _json_object(run_manifest)
        if run.get("schema_version") != "synthpopcan-run-v1":
            raise ValueError("run manifest must use synthpopcan-run-v1")
        if run.get("status") != "succeeded":
            raise ValueError("exchange requires a successful durable run")
        try:
            run = RunManifest.model_validate(run).model_dump()
        except ValidationError as exc:
            raise ValueError(
                f"invalid durable-run manifest: {exc.errors()[0]['msg']}"
            ) from exc
        origin = {
            "kind": "durable-run",
            "run_schema_version": run["schema_version"],
            "run_id": run.get("run_id"),
            "workflow": run.get("workflow"),
            "synthpopcan_version": run.get("synthpopcan_version"),
            "request": run.get("request"),
            "random_seed": run.get("random_seed"),
            "run_manifest_sha256": _sha256(run_manifest),
            "assurance_schema_version": (
                run.get("assurance", {}).get("schema_version")
                if isinstance(run.get("assurance"), Mapping)
                else None
            ),
        }
        run_reproduction = run.get("reproduction")
    exact_reproduction = (
        dict(reproduction)
        if reproduction is not None
        else run_reproduction
        if isinstance(run_reproduction, Mapping)
        else {
            "interface": "python",
            "operation": "synthpopcan.create_exchange_bundle",
            "parameters": {
                "population": str(source),
                "output_dir": str(output_dir),
            },
        }
    )
    _validate_reproduction(exact_reproduction)
    return {
        "schema_version": _PROVENANCE_SCHEMA_VERSION,
        "origin": origin,
        "reproduction": exact_reproduction,
    }


def _file_record(
    logical_name: str,
    path: Path,
    media_type: str,
    *,
    access_classification: str,
    redistribution_status: str,
) -> dict[str, Any]:
    return {
        "logical_name": logical_name,
        "path": path.name,
        "media_type": media_type,
        "byte_size": path.stat().st_size,
        "sha256": _sha256(path),
        "row_count": _csv_row_count(path) if media_type == "text/csv" else None,
        "access_classification": access_classification,
        "redistribution_status": redistribution_status,
    }


def _bundle_result(directory: Path, report: Mapping[str, Any]) -> ExchangeBundle:
    return ExchangeBundle(
        directory=directory,
        manifest=directory / "manifest.json",
        households=directory / "households.csv",
        persons=directory / "persons.csv",
        linked_population=directory / "linked-population.json",
        data_dictionary=directory / "data-dictionary.json",
        provenance=directory / "provenance.json",
        validation=directory / "validation.json",
        report=report,
    )


def _validate_geography(
    contract: Mapping[str, Any], universe: GeographyUniverse | None
) -> None:
    column = _household_geography_column(contract)
    if universe is None:
        return
    if column is None:
        raise ValueError("geography universe requires a household geography column")
    if universe.identifier_column != column:
        raise ValueError(
            "geography universe identifier column does not match the linked population"
        )


def _geography_universe(
    value: GeographyUniverse | Mapping[str, object] | None,
) -> GeographyUniverse | None:
    if value is None or isinstance(value, GeographyUniverse):
        return value
    return GeographyUniverse.from_dict(value)


def _validate_geography_values(path: Path, universe: GeographyUniverse) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        required = [universe.identifier_column]
        if universe.dguid_column is not None:
            required.append(universe.dguid_column)
        missing = [column for column in required if column not in columns]
        if missing:
            raise ValueError(
                "geography columns are missing from households.csv: "
                + ", ".join(missing)
            )
        for row_number, row in enumerate(reader, start=2):
            if not row.get(universe.identifier_column, "").strip():
                raise ValueError(
                    f"household geography identifier is empty on row {row_number}"
                )
            if (
                universe.dguid_column is not None
                and not row.get(universe.dguid_column, "").strip()
            ):
                raise ValueError(f"household DGUID is empty on row {row_number}")


def _household_geography_column(contract: Mapping[str, Any]) -> str | None:
    geography = contract.get("geography")
    if isinstance(geography, Mapping):
        value = geography.get("household_column")
        return value if isinstance(value, str) else None
    return None


def _csv_columns_and_missing(path: Path) -> tuple[list[str], dict[str, bool]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"CSV is empty: {path}")
        columns = list(fieldnames)
        missing = dict.fromkeys(columns, False)
        for row in reader:
            for column in columns:
                if row.get(column, "") == "":
                    missing[column] = True
    return columns, missing


def _csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _synthpopcan_version() -> str:
    from synthpopcan import __version__

    return __version__


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _linkage_error(report: Mapping[str, Any]) -> str:
    issues = report.get("issues")
    if isinstance(issues, list) and issues:
        first = issues[0]
        if isinstance(first, Mapping) and first.get("message"):
            return "linked-population validation failed: " + str(first["message"])
    return "linked-population validation failed"


def _string_list(values: Sequence[str], label: str) -> list[str]:
    normalized = list(values)
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError(f"{label} must contain non-empty strings")
    return normalized


def _optional_string_mapping(
    value: Mapping[str, str] | None, label: str
) -> dict[str, str] | None:
    if value is None:
        return None
    normalized = dict(value)
    if any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(item, str)
        or not item.strip()
        for key, item in normalized.items()
    ):
        raise ValueError(f"{label} must contain non-empty string keys and values")
    return normalized
