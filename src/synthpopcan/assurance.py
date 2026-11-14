"""Versioned, independently verifiable evidence for durable local runs."""

from __future__ import annotations

__all__ = [
    "ASSURANCE_SCHEMA_VERSION",
    "build_run_assurance",
    "verify_run_assurance",
]

import csv
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from synthpopcan.models import model_payload
from synthpopcan.tree import validate_linked_population_files

ASSURANCE_SCHEMA_VERSION = "synthpopcan-assurance-v1"


class FileEvidence(TypedDict):
    logical_name: object
    path: object
    media_type: object
    sha256: str
    byte_size: int
    row_count: int | None


class AssuranceVerification(TypedDict):
    passed: bool
    issues: list[str]


class AssuranceDiagnostics(TypedDict):
    run_summary: object
    report_summary: object
    linked_population: object


class _RestartFragment(TypedDict):
    restarted_from: NotRequired[object]


class AssuranceReport(TypedDict):
    schema_version: str
    run_schema_version: object
    synthpopcan_version: object
    run_id: object
    workflow: object
    terminal_status: str
    successful: bool
    normalized_request: object
    model: dict[str, object] | None
    random_seeds: dict[str, object]
    settings: dict[str, object]
    inputs: list[FileEvidence]
    artifacts: list[FileEvidence]
    diagnostics: AssuranceDiagnostics
    warnings: list[str]
    limitations: list[str]
    restarted_from: NotRequired[object]


def _object_map(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    raw = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw):
        return None
    return {key: item for key, item in raw.items() if isinstance(key, str)}


def _object_list(value: object) -> list[object] | None:
    return cast(list[object], value) if isinstance(value, list) else None


def _required_file_metadata(value: object) -> list[dict[str, object]]:
    items = _object_list(value)
    if items is None:
        raise ValueError("run file metadata must be a list")
    result: list[dict[str, object]] = []
    for item in items:
        entry = _object_map(item)
        if entry is None:
            raise ValueError("run file metadata must contain objects")
        result.append(entry)
    return result


def _restart_fragment(manifest: dict[str, object]) -> _RestartFragment:
    if manifest.get("restarted_from") is not None:
        return {"restarted_from": manifest["restarted_from"]}
    return {}


_TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


def build_run_assurance(
    manifest: dict[str, object],
    resolve_path: Callable[[str], Path],
) -> AssuranceReport:
    """Build terminal-run evidence without embedding source data."""
    status = str(manifest["status"])
    if status not in _TERMINAL_STATES:
        raise ValueError("assurance evidence requires a terminal run")
    inputs = [
        _file_evidence(item, resolve_path(str(item["path"])))
        for item in _required_file_metadata(manifest.get("inputs", []))
    ]
    artifacts = [
        _file_evidence(item, resolve_path(str(item["path"])))
        for item in _required_file_metadata(manifest.get("artifacts", []))
    ]
    request = manifest.get("request", {})
    options = _object_map((_object_map(request) or {}).get("options")) or {}
    report_summary = _report_summary(artifacts, resolve_path)
    linkage = _linked_validation(artifacts, resolve_path)
    warnings = _collect_warnings(manifest.get("summary", {}), report_summary)
    result: AssuranceReport = {
        "schema_version": ASSURANCE_SCHEMA_VERSION,
        "run_schema_version": manifest.get("schema_version"),
        "synthpopcan_version": manifest.get("synthpopcan_version"),
        "run_id": manifest.get("run_id"),
        "workflow": manifest.get("workflow"),
        "terminal_status": status,
        "successful": status == "succeeded",
        "normalized_request": request,
        "model": _model_identity(request, inputs),
        "random_seeds": {
            str(key): value
            for key, value in options.items()
            if "seed" in str(key).lower()
        },
        "settings": options,
        "inputs": inputs,
        "artifacts": artifacts,
        "diagnostics": {
            "run_summary": manifest.get("summary", {}),
            "report_summary": report_summary,
            "linked_population": linkage,
        },
        "warnings": warnings,
        **_restart_fragment(manifest),
        "limitations": [
            "Evidence verifies recorded bytes and implemented numerical checks; "
            "it does not establish substantive fitness for every research use.",
            "Input hashes provide provenance without redistributing input contents.",
        ],
    }
    return result


def verify_run_assurance(
    manifest: dict[str, object],
    resolve_path: Callable[[str], Path],
) -> AssuranceVerification:
    """Recompute stored evidence and report any mismatch or lifecycle problem."""
    assurance = _object_map(manifest.get("assurance"))
    issues: list[str] = []
    if assurance is None:
        return {"passed": False, "issues": ["run has no assurance evidence"]}
    if assurance.get("schema_version") != ASSURANCE_SCHEMA_VERSION:
        issues.append("unsupported assurance schema")
    if assurance.get("run_schema_version") != manifest.get("schema_version"):
        issues.append("run schema version does not match the run manifest")
    if assurance.get("synthpopcan_version") != manifest.get("synthpopcan_version"):
        issues.append("SynthPopCan version does not match the run manifest")
    issues.extend(_check_restart_provenance(assurance, manifest))
    status = str(manifest.get("status"))
    if status not in _TERMINAL_STATES:
        issues.append("run is not terminal")
    if assurance.get("terminal_status") != status:
        issues.append("terminal status does not match the run manifest")
    if assurance.get("successful") is not (status == "succeeded"):
        issues.append("successful flag does not match the terminal status")
    if assurance.get("normalized_request") != manifest.get("request"):
        issues.append("normalized request does not match the run manifest")
    request = manifest.get("request")
    options = _object_map((_object_map(request) or {}).get("options")) or {}
    if assurance.get("settings") != options:
        issues.append("settings do not match the normalized request")
    expected_seeds = {
        str(key): value for key, value in options.items() if "seed" in str(key).lower()
    }
    if assurance.get("random_seeds") != expected_seeds:
        issues.append("random seeds do not match the normalized request")

    observed_inputs: list[FileEvidence] = []
    for collection in ("inputs", "artifacts"):
        observed = _verify_file_collection(
            collection,
            assurance.get(collection),
            manifest.get(collection),
            resolve_path,
            issues,
        )
        if collection == "inputs":
            observed_inputs.extend(observed)
    try:
        if assurance.get("model") != _model_identity(request, observed_inputs):
            issues.append("model identity or checksum does not match")
    except (KeyError, ValueError) as exc:
        issues.append(f"cannot recompute model evidence: {exc}")

    artifacts_value = assurance.get("artifacts", [])
    if isinstance(artifacts_value, list):
        diagnostics = _object_map(assurance.get("diagnostics"))
        if diagnostics is None:
            issues.append("assurance diagnostics are malformed")
            diagnostics = {}
        try:
            artifacts = _required_file_metadata(cast(list[object], artifacts_value))
            report_summary = _report_summary(artifacts, resolve_path)
            if report_summary != diagnostics.get("report_summary"):
                issues.append("report diagnostics do not match the report artifact")
            linkage = _linked_validation(artifacts, resolve_path)
            if linkage != diagnostics.get("linked_population"):
                issues.append("linked-population findings do not match the artifacts")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            issues.append(f"cannot recompute artifact diagnostics: {exc}")
    return {"passed": not issues, "issues": issues}


def _claimed_files(
    collection: str, claimed: list[object], issues: list[str]
) -> dict[str, dict[str, object]]:
    by_name: dict[str, dict[str, object]] = {}
    for raw_entry in claimed:
        entry = _object_map(raw_entry)
        if entry is None or not isinstance(entry.get("logical_name"), str):
            issues.append(f"{collection} evidence entry is malformed")
            continue
        name = str(entry["logical_name"])
        if name in by_name:
            issues.append(f"duplicate {collection} evidence for {name}")
        by_name[name] = entry
    return by_name


def _verify_file_collection(
    collection: str,
    claimed: object,
    manifest_items: object,
    resolve_path: Callable[[str], Path],
    issues: list[str],
) -> list[FileEvidence]:
    if not isinstance(claimed, list) or not isinstance(manifest_items, list):
        issues.append(f"{collection} evidence is malformed")
        return []
    by_name = _claimed_files(collection, cast(list[object], claimed), issues)
    observed_files: list[FileEvidence] = []
    manifest_names: set[str] = set()
    for raw_item in cast(list[object], manifest_items):
        item = _object_map(raw_item)
        if item is None or "path" not in item:
            issues.append(f"{collection} manifest entry is malformed")
            continue
        name = str(item.get("logical_name"))
        manifest_names.add(name)
        evidence = by_name.get(name)
        if evidence is None:
            issues.append(f"missing {collection} evidence for {name}")
            continue
        try:
            observed = _file_evidence(item, resolve_path(str(item["path"])))
        except OSError as exc:
            issues.append(f"cannot read {collection} file {name}: {exc}")
            continue
        observed_files.append(observed)
        for field in ("sha256", "byte_size", "row_count"):
            if evidence.get(field) != observed.get(field):
                issues.append(f"{collection} {name} {field} does not match")
    _reject_extra_evidence(collection, set(by_name) - manifest_names, issues)
    return observed_files


def _reject_extra_evidence(collection: str, names: set[str], issues: list[str]) -> None:
    for name in sorted(names):
        issues.append(f"unexpected {collection} evidence for {name}")


def _file_evidence(metadata: dict[str, object], path: Path) -> FileEvidence:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_size += len(chunk)
    row_count = _csv_row_count(path) if _is_csv(metadata, path) else None
    return {
        "logical_name": metadata.get("logical_name"),
        "path": metadata.get("path"),
        "media_type": metadata.get("media_type"),
        "sha256": digest.hexdigest(),
        "byte_size": byte_size,
        "row_count": row_count,
    }


def _check_restart_provenance(
    assurance: dict[str, object], manifest: dict[str, object]
) -> list[str]:
    if assurance.get("restarted_from") != manifest.get("restarted_from"):
        return ["restart provenance does not match the run manifest"]
    return []


def _is_csv(metadata: dict[str, object], path: Path) -> bool:
    return metadata.get("media_type") == "text/csv" or path.suffix.lower() == ".csv"


def _csv_row_count(path: Path) -> int:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _report_summary(
    artifacts: Sequence[Mapping[str, object]],
    resolve_path: Callable[[str], Path],
) -> object | None:
    report = next(
        (
            item
            for item in artifacts
            if item.get("logical_name")
            in {"report", "fit_report", "generation_report", "small_area_report"}
            and str(item.get("path", "")).endswith(".json")
        ),
        None,
    )
    if report is None:
        return None
    payload: object = json.loads(resolve_path(str(report["path"])).read_text())
    mapping = _object_map(payload)
    if mapping is not None:
        diagnostic_keys = (
            "converged",
            "iterations",
            "max_iterations",
            "tolerance",
            "max_abs_error",
            "max_rel_error",
            "summary",
            "input_checks",
            "linked_population",
            "unsupported_cells",
            "impossible_cells",
            "support_repairs",
        )
        return {key: mapping[key] for key in diagnostic_keys if key in mapping}
    return payload


def _linked_validation(
    artifacts: Sequence[Mapping[str, object]],
    resolve_path: Callable[[str], Path],
) -> dict[str, object] | None:
    by_name = {str(item.get("logical_name")): item for item in artifacts}
    households = by_name.get("households")
    persons = by_name.get("persons")
    if households is None or persons is None:
        return None
    return validate_linked_population_files(
        resolve_path(str(households["path"])),
        resolve_path(str(persons["path"])),
    )


def _model_identity(
    request: object,
    inputs: Sequence[Mapping[str, object]],
) -> dict[str, object] | None:
    request_inputs = _object_map((_object_map(request) or {}).get("inputs"))
    if request_inputs is None:
        return None
    model_id = request_inputs.get("model_id")
    if model_id:
        payload = json.dumps(
            model_payload(str(model_id)),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return {
            "identity": str(model_id),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "checksum_basis": "canonical bundled model package JSON",
        }
    package = next(
        (item for item in inputs if item.get("logical_name") == "package"),
        None,
    )
    if package is not None:
        return {
            "identity": "uploaded package",
            "sha256": package["sha256"],
            "checksum_basis": "uploaded package bytes",
        }
    return None


def _collect_warnings(run_summary: object, report_summary: object) -> list[str]:
    warnings: list[str] = []
    for candidate in (run_summary, report_summary):
        mapping = _object_map(candidate)
        if mapping is None:
            continue
        candidates = [mapping]
        nested_summary = _object_map(mapping.get("summary"))
        if nested_summary is not None:
            candidates.append(nested_summary)
        for diagnostics in candidates:
            if _non_converged(diagnostics):
                warnings.append("one or more geography fits did not converge")
            if diagnostics.get("converged") is False:
                warnings.append("the fit did not converge")
    return sorted(set(warnings))


def _non_converged(diagnostics: dict[str, object]) -> bool:
    count = diagnostics.get("non_converged_count", 0) or 0
    if not isinstance(count, (int, float, str, bytes, bytearray)):
        raise ValueError("invalid non-converged count")
    return bool(int(count))
