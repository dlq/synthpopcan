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
from collections.abc import Callable
from pathlib import Path
from typing import Any

from synthpopcan.models import model_payload
from synthpopcan.tree import validate_linked_population_files

ASSURANCE_SCHEMA_VERSION = "synthpopcan-assurance-v1"
_TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


def build_run_assurance(
    manifest: dict[str, Any],
    resolve_path: Callable[[str], Path],
) -> dict[str, Any]:
    """Build terminal-run evidence without embedding source data."""
    status = str(manifest["status"])
    if status not in _TERMINAL_STATES:
        raise ValueError("assurance evidence requires a terminal run")
    inputs = [
        _file_evidence(item, resolve_path(str(item["path"])))
        for item in manifest.get("inputs", [])
    ]
    artifacts = [
        _file_evidence(item, resolve_path(str(item["path"])))
        for item in manifest.get("artifacts", [])
    ]
    request = manifest.get("request", {})
    options = request.get("options", {}) if isinstance(request, dict) else {}
    report_summary = _report_summary(artifacts, resolve_path)
    linkage = _linked_validation(artifacts, resolve_path)
    warnings = _collect_warnings(manifest.get("summary", {}), report_summary)
    return {
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
        "limitations": [
            "Evidence verifies recorded bytes and implemented numerical checks; "
            "it does not establish substantive fitness for every research use.",
            "Input hashes provide provenance without redistributing input contents.",
        ],
    }


def verify_run_assurance(
    manifest: dict[str, Any],
    resolve_path: Callable[[str], Path],
) -> dict[str, Any]:
    """Recompute stored evidence and report any mismatch or lifecycle problem."""
    assurance = manifest.get("assurance")
    issues: list[str] = []
    if not isinstance(assurance, dict):
        return {"passed": False, "issues": ["run has no assurance evidence"]}
    if assurance.get("schema_version") != ASSURANCE_SCHEMA_VERSION:
        issues.append("unsupported assurance schema")
    if assurance.get("run_schema_version") != manifest.get("schema_version"):
        issues.append("run schema version does not match the run manifest")
    if assurance.get("synthpopcan_version") != manifest.get("synthpopcan_version"):
        issues.append("SynthPopCan version does not match the run manifest")
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
    options = request.get("options", {}) if isinstance(request, dict) else {}
    if assurance.get("settings") != options:
        issues.append("settings do not match the normalized request")
    expected_seeds = {
        str(key): value for key, value in options.items() if "seed" in str(key).lower()
    }
    if assurance.get("random_seeds") != expected_seeds:
        issues.append("random seeds do not match the normalized request")

    observed_inputs: list[dict[str, Any]] = []
    for collection in ("inputs", "artifacts"):
        claimed = assurance.get(collection)
        manifest_items = manifest.get(collection)
        if not isinstance(claimed, list) or not isinstance(manifest_items, list):
            issues.append(f"{collection} evidence is malformed")
            continue
        claimed_by_name = {
            str(item.get("logical_name")): item
            for item in claimed
            if isinstance(item, dict)
        }
        for item in manifest_items:
            logical_name = str(item.get("logical_name"))
            evidence = claimed_by_name.get(logical_name)
            if evidence is None:
                issues.append(f"missing {collection} evidence for {logical_name}")
                continue
            try:
                observed = _file_evidence(
                    item,
                    resolve_path(str(item["path"])),
                )
            except OSError as exc:
                issues.append(f"cannot read {collection} file {logical_name}: {exc}")
                continue
            if collection == "inputs":
                observed_inputs.append(observed)
            for field in ("sha256", "byte_size", "row_count"):
                if evidence.get(field) != observed.get(field):
                    issues.append(f"{collection} {logical_name} {field} does not match")
    try:
        if assurance.get("model") != _model_identity(request, observed_inputs):
            issues.append("model identity or checksum does not match")
    except (KeyError, ValueError) as exc:
        issues.append(f"cannot recompute model evidence: {exc}")

    artifacts = assurance.get("artifacts", [])
    if isinstance(artifacts, list):
        try:
            report_summary = _report_summary(artifacts, resolve_path)
            if report_summary != assurance.get("diagnostics", {}).get("report_summary"):
                issues.append("report diagnostics do not match the report artifact")
            linkage = _linked_validation(artifacts, resolve_path)
            if linkage != assurance.get("diagnostics", {}).get("linked_population"):
                issues.append("linked-population findings do not match the artifacts")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            issues.append(f"cannot recompute artifact diagnostics: {exc}")
    return {"passed": not issues, "issues": issues}


def _file_evidence(metadata: dict[str, Any], path: Path) -> dict[str, Any]:
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


def _is_csv(metadata: dict[str, Any], path: Path) -> bool:
    return metadata.get("media_type") == "text/csv" or path.suffix.lower() == ".csv"


def _csv_row_count(path: Path) -> int:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _report_summary(
    artifacts: list[dict[str, Any]],
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
    payload = json.loads(resolve_path(str(report["path"])).read_text())
    if isinstance(payload, dict):
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
        return {key: payload[key] for key in diagnostic_keys if key in payload}
    return payload


def _linked_validation(
    artifacts: list[dict[str, Any]],
    resolve_path: Callable[[str], Path],
) -> dict[str, Any] | None:
    by_name = {
        str(item.get("logical_name")): item
        for item in artifacts
        if isinstance(item, dict)
    }
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
    inputs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(request, dict) or not isinstance(request.get("inputs"), dict):
        return None
    request_inputs = request["inputs"]
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
        if not isinstance(candidate, dict):
            continue
        candidates = [candidate]
        nested_summary = candidate.get("summary")
        if isinstance(nested_summary, dict):
            candidates.append(nested_summary)
        for diagnostics in candidates:
            if int(diagnostics.get("non_converged_count", 0) or 0):
                warnings.append("one or more geography fits did not converge")
            if diagnostics.get("converged") is False:
                warnings.append("the fit did not converge")
    return sorted(set(warnings))
