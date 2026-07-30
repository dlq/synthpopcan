"""Efficient candidate reuse and aggregation for national small-area runs."""

from __future__ import annotations

__all__ = [
    "NationalBatchRunConfiguration",
    "build_national_geography_summary",
    "find_cached_national_candidate_pools",
    "prepare_national_candidate_pools",
    "reset_nonconverged_national_batches",
    "run_national_cached_batch",
]

import csv
import json
import os
import shutil
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.geography import statcan_geography_universe
from synthpopcan.small_area_controls import write_recoded_candidates
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs
from synthpopcan.statcan import file_integrity
from synthpopcan.tree import (
    generate_linked_population_to_csv,
    validate_linked_population_files,
)

_POOL_SCHEMA = "synthpopcan-national-candidate-pool-v1"
_SUMMARY_SCHEMA = "synthpopcan-national-small-area-summary-v1"
_EXCLUDED_CANDIDATE_VALUES = {"TENUR": ["8"]}


@dataclass(frozen=True)
class NationalBatchRunConfiguration:
    """Serializable settings shared by cached-pool batch workers."""

    pool_manifests: dict[str, str]
    geography_level: str
    identifier_column: str
    identifier_namespace: str
    fit_workers: int
    max_iterations: int = 100
    tolerance: float = 1e-6


def prepare_national_candidate_pools(
    plan_path: Path,
    *,
    household_model: Any,
    person_model: Any,
    household_size_column: str,
    model_evidence: Mapping[str, object],
    requested_pool_size: int,
    base_seed: int,
    condition_by_jurisdiction: bool = True,
    pumf_pr_values: set[str] | None = None,
    force: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, dict[str, object]]:
    """Create or reuse one linked candidate pool per PUMF condition value."""

    if requested_pool_size < 1:
        raise ValueError("requested_pool_size must be at least 1")
    plan = _read_json(plan_path)
    targets_by_condition = _targets_by_condition(
        plan_path,
        plan,
        condition_by_jurisdiction=condition_by_jurisdiction,
        pumf_pr_values=pumf_pr_values,
    )

    pools_root = plan_path.parent / "candidate-pools"
    pools_root.mkdir(parents=True, exist_ok=True)
    pool_reports: dict[str, dict[str, object]] = {}
    for condition_key in sorted(
        targets_by_condition,
        key=lambda value: int(value) if value.isdigit() else -1,
    ):
        target_households = targets_by_condition[condition_key]
        pool_size = min(requested_pool_size, target_households)
        seed = base_seed + (int(condition_key) if condition_key.isdigit() else 0)
        final_directory = pools_root / (
            f"pr-{condition_key}" if condition_key.isdigit() else condition_key
        )
        condition = {"PR": condition_key} if condition_by_jurisdiction else {}
        configuration = {
            "model": dict(model_evidence),
            "condition": condition,
            "household_size_column": household_size_column,
            "pool_size": pool_size,
            "random_seed": seed,
            "excluded_candidate_values": _EXCLUDED_CANDIDATE_VALUES,
        }
        cached = _validated_cached_pool(final_directory, configuration)
        if cached is not None and not force:
            if progress is not None:
                progress(f"Using cached {condition or 'unconditioned'} candidate pool")
            pool_reports[condition_key] = cached
            continue

        if progress is not None:
            progress(
                f"Generating {condition or 'unconditioned'} candidate pool "
                f"({pool_size:,} households)"
            )
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(
            dir=pools_root,
            prefix=f".pool-{condition_key}-",
        ) as temporary_value:
            temporary = Path(temporary_value)
            raw_households = temporary / "households-raw.csv"
            filtered_households = temporary / "households-filtered.csv"
            households = temporary / "households.csv"
            raw_persons = temporary / "persons-raw.csv"
            persons = temporary / "persons.csv"

            phase_started = time.perf_counter()
            generated_households, generated_persons = generate_linked_population_to_csv(
                household_model,
                person_model,
                households=pool_size,
                households_path=raw_households,
                persons_path=raw_persons,
                household_conditions=condition,
                household_size_column=household_size_column,
                random_seed=seed,
            )
            generation_seconds = time.perf_counter() - phase_started

            phase_started = time.perf_counter()
            retained = _exclude_unusable_linked_candidates(
                raw_households,
                raw_persons,
                filtered_households,
                persons,
            )
            write_recoded_candidates(
                filtered_households,
                households,
                hhsize_col=household_size_column,
                group_col="household_size_group",
                cap=5,
            )
            recode_seconds = time.perf_counter() - phase_started
            raw_households.unlink()
            raw_persons.unlink()
            filtered_households.unlink()

            phase_started = time.perf_counter()
            validation = validate_linked_population_files(households, persons)
            if not validation["passed"]:
                raise ValueError(
                    f"{condition or 'unconditioned'} candidate-pool "
                    "linked validation failed"
                )
            support = _candidate_support(households)
            integrity = {
                "households": {
                    "path": "households.csv",
                    **file_integrity(households),
                },
                "persons": {
                    "path": "persons.csv",
                    **file_integrity(persons),
                },
            }
            validation_seconds = time.perf_counter() - phase_started

            manifest: dict[str, object] = {
                "schema_version": _POOL_SCHEMA,
                "configuration": configuration,
                "rows": {
                    "households": retained["households"],
                    "persons": retained["persons"],
                },
                "generated_rows": {
                    "households": generated_households,
                    "persons": generated_persons,
                },
                "excluded_rows": retained["excluded"],
                "support": support,
                "linked_validation": validation,
                "artifacts": integrity,
                "timing_seconds": {
                    "generation": generation_seconds,
                    "household_size_recode": recode_seconds,
                    "validation_and_hashing": validation_seconds,
                    "total": time.perf_counter() - started,
                },
            }
            _write_json(temporary / "manifest.json", manifest)
            if final_directory.exists():
                shutil.rmtree(final_directory)
            Path(temporary_value).replace(final_directory)

        pool_reports[condition_key] = _read_json(final_directory / "manifest.json")

    existing_pools = plan.get("candidate_pools")
    existing_conditions = (
        existing_pools.get("conditions")
        if isinstance(existing_pools, Mapping)
        and existing_pools.get("model") == dict(model_evidence)
        and existing_pools.get("base_seed") == base_seed
        and existing_pools.get("condition_by_jurisdiction") == condition_by_jurisdiction
        else None
    )
    merged_conditions = (
        dict(existing_conditions) if isinstance(existing_conditions, Mapping) else {}
    )
    merged_conditions.update(
        {
            condition_key: {
                "manifest": str(
                    (
                        pools_root
                        / (
                            f"pr-{condition_key}"
                            if condition_key.isdigit()
                            else condition_key
                        )
                        / "manifest.json"
                    ).relative_to(plan_path.parent)
                ),
                "target_households": targets_by_condition[condition_key],
                "candidate_households": _pool_row_count(report, "households"),
                "requested_pool_size": requested_pool_size,
            }
            for condition_key, report in pool_reports.items()
        }
    )
    plan["candidate_pools"] = {
        "schema_version": _POOL_SCHEMA,
        "requested_pool_size": requested_pool_size,
        "base_seed": base_seed,
        "condition_by_jurisdiction": condition_by_jurisdiction,
        "model": dict(model_evidence),
        "conditions": merged_conditions,
    }
    _write_json(plan_path, plan)
    return pool_reports


def find_cached_national_candidate_pools(
    plan_path: Path,
    *,
    model_evidence: Mapping[str, object],
    requested_pool_size: int,
    base_seed: int,
    condition_by_jurisdiction: bool = True,
    pumf_pr_values: set[str] | None = None,
) -> dict[str, dict[str, object]] | None:
    """Return matching verified pools without loading the model package."""

    plan = _read_json(plan_path)
    targets = _targets_by_condition(
        plan_path,
        plan,
        condition_by_jurisdiction=condition_by_jurisdiction,
        pumf_pr_values=pumf_pr_values,
    )
    pools_root = plan_path.parent / "candidate-pools"
    reports: dict[str, dict[str, object]] = {}
    for condition_key, target in targets.items():
        directory = pools_root / (
            f"pr-{condition_key}" if condition_key.isdigit() else condition_key
        )
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            return None
        manifest = _read_json(manifest_path)
        configuration = manifest.get("configuration")
        if not isinstance(configuration, Mapping):
            return None
        expected_condition = {"PR": condition_key} if condition_by_jurisdiction else {}
        if configuration.get("model") != dict(model_evidence):
            return None
        if configuration.get("condition") != expected_condition:
            return None
        if configuration.get("excluded_candidate_values") != _EXCLUDED_CANDIDATE_VALUES:
            return None
        if configuration.get("pool_size") != min(requested_pool_size, target):
            return None
        expected_seed = base_seed + (
            int(condition_key) if condition_key.isdigit() else 0
        )
        if configuration.get("random_seed") != expected_seed:
            return None
        verified = _validated_cached_pool(directory, configuration)
        if verified is None:
            return None
        reports[condition_key] = verified
    return reports


def reset_nonconverged_national_batches(
    plan_path: Path,
    *,
    jurisdiction_pruids: set[str] | None = None,
) -> list[str]:
    """Reset completed batches whose geography fits did not all converge."""

    plan = _read_json(plan_path)
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    reset: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        if (
            jurisdiction_pruids is not None
            and record.get("jurisdiction_pruid") not in jurisdiction_pruids
        ):
            continue
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            continue
        batch_path = plan_path.parent / manifest_value
        batch = _read_json(batch_path)
        if batch.get("status") != "completed":
            continue
        result = batch.get("result")
        if not isinstance(result, Mapping):
            continue
        artifacts = result.get("artifacts")
        report_artifact = (
            artifacts.get("report") if isinstance(artifacts, Mapping) else None
        )
        report_value = (
            report_artifact.get("path")
            if isinstance(report_artifact, Mapping)
            else None
        )
        if not isinstance(report_value, str):
            continue
        report = _read_json(plan_path.parent / report_value)
        geographies = report.get("geographies")
        if not isinstance(geographies, Mapping) or all(
            isinstance(evidence, Mapping) and evidence.get("converged") is True
            for evidence in geographies.values()
        ):
            continue
        prior_results = batch.setdefault("superseded_results", [])
        if not isinstance(prior_results, list):
            raise ValueError(f"{batch_path} superseded_results must be a list")
        prior_results.append(
            {
                "reason": "one or more geography fits did not converge",
                "result": result,
            }
        )
        batch["status"] = "planned"
        batch.pop("result", None)
        _write_json(batch_path, batch)
        reset.append(_required_text(batch, "batch_id"))
    if reset:
        plan["status"] = "partial"
        plan["last_correction"] = {
            "reason": "reset nonconverged geography fits",
            "batches": reset,
        }
        _write_json(plan_path, plan)
    return reset


def run_national_cached_batch(
    batch: Mapping[str, object],
    root: Path,
    *,
    configuration: NationalBatchRunConfiguration,
) -> Mapping[str, object]:
    """Calibrate one national batch from its reusable conditioned pool."""

    started = time.perf_counter()
    batch_id = _required_text(batch, "batch_id")
    controls = batch.get("controls")
    jurisdiction = batch.get("jurisdiction")
    target_households = batch.get("target_households")
    output_value = batch.get("output_directory")
    if not isinstance(controls, Mapping):
        raise ValueError(f"{batch_id} controls must be an object")
    if not isinstance(target_households, int):
        raise ValueError(f"{batch_id} target_households must be an integer")
    if not isinstance(jurisdiction, Mapping):
        raise ValueError(f"{batch_id} jurisdiction must be an object")
    if not isinstance(output_value, str):
        raise ValueError(f"{batch_id} output directory is invalid")
    controls_path = root / _required_text(controls, "path")
    pumf_pr = _required_text(jurisdiction, "pumf_pr")
    manifest_value = configuration.pool_manifests.get(pumf_pr)
    if manifest_value is None:
        raise ValueError(f"{batch_id} has no PR={pumf_pr} candidate pool")
    pool_manifest_path = root / manifest_value
    pool_manifest = _read_json(pool_manifest_path)
    artifacts = pool_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError(f"{batch_id} candidate-pool artifacts are invalid")
    households_artifact = artifacts.get("households")
    persons_artifact = artifacts.get("persons")
    if not isinstance(households_artifact, Mapping) or not isinstance(
        persons_artifact,
        Mapping,
    ):
        raise ValueError(f"{batch_id} candidate-pool files are invalid")
    pool_root = pool_manifest_path.parent
    households_path = pool_root / _required_text(households_artifact, "path")
    persons_path = pool_root / _required_text(persons_artifact, "path")

    output = root / output_value
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            dir=output.parent,
            prefix=f".{output.name}-{os.getpid()}-",
        )
    )
    try:
        calibration_started = time.perf_counter()
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            geography_dimension=configuration.geography_level,
            geography_column=configuration.identifier_column,
            geography_universe=statcan_geography_universe(
                2021,
                configuration.geography_level,
                configuration.identifier_column,
                dguid_column="DGUID",
            ),
            households_out=temporary / "households.csv",
            persons_out=temporary / "persons.csv",
            report_out=temporary / "report.json",
            max_iterations=configuration.max_iterations,
            tolerance=configuration.tolerance,
            n_workers=configuration.fit_workers,
            record_timing=True,
        )
        calibration_seconds = time.perf_counter() - calibration_started

        validation_started = time.perf_counter()
        validation = validate_linked_population_files(
            temporary / "households.csv",
            temporary / "persons.csv",
        )
        if not validation["passed"]:
            raise ValueError(f"{batch_id} linked-population validation failed")
        validation_seconds = time.perf_counter() - validation_started

        hashing_started = time.perf_counter()
        output_integrity = summary.get("output_integrity")
        result_artifacts: dict[str, object] = {}
        for name in ("households", "persons"):
            path = temporary / f"{name}.csv"
            recorded = (
                output_integrity.get(name)
                if isinstance(output_integrity, Mapping)
                else None
            )
            result_artifacts[name] = {
                "path": str((output / path.name).relative_to(root)),
                **(
                    dict(recorded)
                    if isinstance(recorded, Mapping)
                    else file_integrity(path)
                ),
            }
        report_path = temporary / "report.json"
        result_artifacts["report"] = {
            "path": str((output / report_path.name).relative_to(root)),
            **file_integrity(report_path),
        }
        hashing_seconds = time.perf_counter() - hashing_started

        if output.exists():
            shutil.rmtree(output)
        temporary.replace(output)
        return {
            "candidate_pool": {
                "condition": {"PR": pumf_pr},
                "manifest": str(pool_manifest_path.relative_to(root)),
                "households": pool_manifest["rows"]["households"],
                "persons": pool_manifest["rows"]["persons"],
            },
            "linked_validation": validation,
            "artifacts": result_artifacts,
            "summary": {
                "assigned_households": summary["assigned_households"],
                "assigned_persons": summary["assigned_persons"],
                "geographies": len(summary["geographies"]),
                "converged": summary["summary"]["converged_count"],
                "max_abs_error": summary["summary"]["max_abs_error"],
                "realized_max_abs_error": summary["summary"]["realized_max_abs_error"],
            },
            "timing_seconds": {
                "calibration_and_realization": calibration_seconds,
                "linked_validation": validation_seconds,
                "artifact_hashing": hashing_seconds,
                "total": time.perf_counter() - started,
            },
        }
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def build_national_geography_summary(plan_path: Path) -> dict[str, object]:
    """Write aggregate completed-batch and per-geography national evidence."""

    plan = _read_json(plan_path)
    geography = plan.get("geography")
    records = plan.get("batches")
    if not isinstance(geography, Mapping) or not isinstance(records, list):
        raise ValueError("national small-area plan is incomplete")
    identifier_column = geography.get("identifier_column")
    if not isinstance(identifier_column, str):
        raise ValueError("national plan identifier column is invalid")

    rows: list[dict[str, object]] = []
    completed_batches = 0
    assigned_households = 0
    assigned_persons = 0
    for record in records:
        if not isinstance(record, Mapping):
            continue
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            continue
        batch = _read_json(plan_path.parent / manifest_value)
        if batch.get("status") != "completed":
            continue
        result = batch.get("result")
        jurisdiction = batch.get("jurisdiction")
        if not isinstance(result, Mapping) or not isinstance(jurisdiction, Mapping):
            continue
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, Mapping):
            continue
        report_artifact = artifacts.get("report")
        if not isinstance(report_artifact, Mapping):
            continue
        report_path_value = report_artifact.get("path")
        if not isinstance(report_path_value, str):
            continue
        report = _read_json(plan_path.parent / report_path_value)
        completed_batches += 1
        assigned_households += int(report.get("assigned_households", 0))
        assigned_persons += int(report.get("assigned_persons", 0))
        geography_reports = report.get("geographies")
        if not isinstance(geography_reports, Mapping):
            continue
        for identifier, values in geography_reports.items():
            if not isinstance(values, Mapping):
                continue
            rows.append(
                {
                    identifier_column: str(identifier),
                    "pruid": str(jurisdiction.get("pruid", "")),
                    "jurisdiction": str(jurisdiction.get("abbreviation", "")),
                    "batch_id": str(batch.get("batch_id", "")),
                    "households": int(values.get("assigned_households", 0)),
                    "persons": int(values.get("assigned_persons", 0)),
                    "converged": bool(values.get("converged", False)),
                    "max_abs_error": float(values.get("max_abs_error", 0.0)),
                }
            )

    summary_csv = plan_path.parent / "national-geography-summary.csv"
    fieldnames = (
        identifier_column,
        "pruid",
        "jurisdiction",
        "batch_id",
        "households",
        "persons",
        "converged",
        "max_abs_error",
    )
    with summary_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: str(row[identifier_column])))

    payload: dict[str, object] = {
        "schema_version": _SUMMARY_SCHEMA,
        "plan_schema_version": plan.get("schema_version"),
        "plan_status": plan.get("status"),
        "geography": dict(geography),
        "batches": {
            "completed": completed_batches,
            "total": len(records),
        },
        "geographies": len(rows),
        "assigned_households": assigned_households,
        "assigned_persons": assigned_persons,
        "artifacts": {
            "geography_summary": {
                "path": summary_csv.name,
                **file_integrity(summary_csv),
            }
        },
    }
    _write_json(plan_path.parent / "national-summary.json", payload)
    return payload


def _validated_cached_pool(
    directory: Path,
    configuration: Mapping[str, object],
) -> dict[str, object] | None:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = _read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        manifest.get("schema_version") != _POOL_SCHEMA
        or manifest.get("configuration") != configuration
    ):
        return None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return None
    for name in ("households", "persons"):
        artifact = artifacts.get(name)
        if not isinstance(artifact, Mapping):
            return None
        relative = artifact.get("path")
        if not isinstance(relative, str):
            return None
        path = directory / relative
        if not path.is_file():
            return None
        actual = file_integrity(path)
        if actual.get("sha256") != artifact.get("sha256"):
            return None
        if actual.get("byte_size") != artifact.get("byte_size"):
            return None
    return manifest


def _candidate_support(path: Path) -> dict[str, object]:
    counts: dict[str, Counter[str]] = {
        "PR": Counter(),
        "TENUR": Counter(),
        "household_size_group": Counter(),
    }
    rows = 0
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            for column, column_counts in counts.items():
                column_counts[str(row.get(column, ""))] += 1
    return {
        "households": rows,
        "categories": {
            column: dict(sorted(column_counts.items()))
            for column, column_counts in counts.items()
        },
    }


def _exclude_unusable_linked_candidates(
    households_path: Path,
    persons_path: Path,
    households_out: Path,
    persons_out: Path,
    *,
    household_id_column: str = "synthetic_household_id",
) -> dict[str, object]:
    """Drop missing-tenure households and their linked person rows."""

    retained_ids: set[str] = set()
    excluded_tenure: Counter[str] = Counter()
    retained_households = 0
    with (
        households_path.open(newline="") as source,
        households_out.open(
            "w",
            newline="",
        ) as destination,
    ):
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("generated candidate household CSV has no header")
        writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            tenure = str(row.get("TENUR", ""))
            if tenure in _EXCLUDED_CANDIDATE_VALUES["TENUR"]:
                excluded_tenure[tenure] += 1
                continue
            identifier = str(row.get(household_id_column, ""))
            if not identifier:
                raise ValueError("generated candidate household has no identifier")
            retained_ids.add(identifier)
            writer.writerow(row)
            retained_households += 1

    retained_persons = 0
    excluded_persons = 0
    with (
        persons_path.open(newline="") as source,
        persons_out.open(
            "w",
            newline="",
        ) as destination,
    ):
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("generated candidate person CSV has no header")
        writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if str(row.get(household_id_column, "")) not in retained_ids:
                excluded_persons += 1
                continue
            writer.writerow(row)
            retained_persons += 1
    return {
        "households": retained_households,
        "persons": retained_persons,
        "excluded": {
            "households": sum(excluded_tenure.values()),
            "persons": excluded_persons,
            "household_values": {
                "TENUR": dict(sorted(excluded_tenure.items())),
            },
            "reason": "PUMF TENUR=8 means not available and cannot be calibrated",
        },
    }


def _targets_by_condition(
    plan_path: Path,
    plan: Mapping[str, object],
    *,
    condition_by_jurisdiction: bool,
    pumf_pr_values: set[str] | None,
) -> Counter[str]:
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    targets: Counter[str] = Counter()
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("national small-area plan batch record is invalid")
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            raise ValueError("national small-area plan batch manifest is invalid")
        batch = _read_json(plan_path.parent / manifest_value)
        jurisdiction = batch.get("jurisdiction")
        target = batch.get("target_households")
        if not isinstance(jurisdiction, Mapping) or not isinstance(target, int):
            raise ValueError("national batch jurisdiction or target is invalid")
        pumf_pr = jurisdiction.get("pumf_pr")
        if not isinstance(pumf_pr, str):
            raise ValueError("national batch PUMF condition is invalid")
        if pumf_pr_values is not None and pumf_pr not in pumf_pr_values:
            continue
        condition_key = pumf_pr if condition_by_jurisdiction else "all"
        targets[condition_key] += target
    return targets


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _pool_row_count(payload: Mapping[str, object], key: str) -> int:
    rows = payload.get("rows")
    if not isinstance(rows, Mapping):
        raise ValueError("candidate-pool rows are invalid")
    value = rows.get(key)
    if not isinstance(value, int):
        raise ValueError(f"candidate-pool {key} count is invalid")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
