"""Restartable province and territory batching for Canadian small areas."""

from __future__ import annotations

__all__ = [
    "CANADA_SMALL_AREA_JURISDICTIONS",
    "CANADA_DA_JURISDICTIONS",
    "NationalSmallAreaJurisdiction",
    "NationalDAJurisdiction",
    "NationalSmallAreaSpecification",
    "execute_canada_small_area_plan",
    "execute_canada_da_plan",
    "estimate_national_small_area_storage",
    "estimate_national_da_storage",
    "load_2021_small_area_jurisdictions",
    "load_2021_da_jurisdictions",
    "national_2021_profile_paths",
    "prepare_canada_small_area_plan",
    "prepare_canada_da_plan",
    "regional_2021_da_profile_paths",
    "required_2021_profile_keys",
    "required_2021_da_profile_keys",
    "small_area_specification",
]

import csv
import json
import multiprocessing
import queue
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthpopcan.geography import statcan_geography_universe
from synthpopcan.map_render import partition_boundaries_geojson
from synthpopcan.small_area_controls import (
    extract_controls_from_profile,
    scale_and_validate_controls,
    write_controls_csv,
)
from synthpopcan.statcan import file_integrity

_PLAN_SCHEMA = "synthpopcan-canada-small-area-plan-v1"
_BATCH_SCHEMA = "synthpopcan-canada-small-area-batch-v1"
_ESTIMATED_PERSISTENT_BYTES_PER_HOUSEHOLD = 500
_ESTIMATED_WORKING_BYTES_PER_HOUSEHOLD = 1_500
_RECOMMENDED_FREE_SPACE_RESERVE_BYTES = 5 * 1024**3


@dataclass(frozen=True)
class NationalSmallAreaJurisdiction:
    """One province or territory in national small-area orchestration.

    The record connects the jurisdiction's PRUID, PUMF conditioning value,
    English and French names, abbreviation, and regional DA Census Profile
    product. Yukon, Northwest Territories, and Nunavut intentionally share the
    hierarchical PUMF's combined northern conditioning value.
    """

    pruid: str
    pumf_pr: str
    abbreviation: str
    name_en: str
    name_fr: str
    da_profile_key: str


@dataclass(frozen=True)
class NationalSmallAreaSpecification:
    """Source and identifier contract for a national geography level.

    A specification names the short identifier column, authoritative DGRF
    relationship column, and required Census Profile products for DA or ADA.
    It lets both levels share planning and execution without pretending their
    source layouts are identical.
    """

    geography_level: str
    identifier_column: str
    dgrf_column: str
    profile_keys: tuple[str, ...]

    def profile_key_for(
        self,
        jurisdiction: NationalSmallAreaJurisdiction,
    ) -> str:
        """Return the official profile product containing a jurisdiction."""

        return (
            jurisdiction.da_profile_key
            if self.geography_level == "da"
            else self.profile_keys[0]
        )


CANADA_SMALL_AREA_JURISDICTIONS = (
    NationalSmallAreaJurisdiction(
        "10",
        "10",
        "NL",
        "Newfoundland and Labrador",
        "Terre-Neuve-et-Labrador",
        "da-atlantic",
    ),
    NationalSmallAreaJurisdiction(
        "11",
        "11",
        "PE",
        "Prince Edward Island",
        "Île-du-Prince-Édouard",
        "da-atlantic",
    ),
    NationalSmallAreaJurisdiction(
        "12", "12", "NS", "Nova Scotia", "Nouvelle-Écosse", "da-atlantic"
    ),
    NationalSmallAreaJurisdiction(
        "13", "13", "NB", "New Brunswick", "Nouveau-Brunswick", "da-atlantic"
    ),
    NationalSmallAreaJurisdiction("24", "24", "QC", "Quebec", "Québec", "da-quebec"),
    NationalSmallAreaJurisdiction("35", "35", "ON", "Ontario", "Ontario", "da-ontario"),
    NationalSmallAreaJurisdiction(
        "46", "46", "MB", "Manitoba", "Manitoba", "da-prairies"
    ),
    NationalSmallAreaJurisdiction(
        "47", "47", "SK", "Saskatchewan", "Saskatchewan", "da-prairies"
    ),
    NationalSmallAreaJurisdiction(
        "48", "48", "AB", "Alberta", "Alberta", "da-prairies"
    ),
    NationalSmallAreaJurisdiction(
        "59",
        "59",
        "BC",
        "British Columbia",
        "Colombie-Britannique",
        "da-british-columbia",
    ),
    NationalSmallAreaJurisdiction("60", "70", "YT", "Yukon", "Yukon", "da-territories"),
    NationalSmallAreaJurisdiction(
        "61",
        "70",
        "NT",
        "Northwest Territories",
        "Territoires du Nord-Ouest",
        "da-territories",
    ),
    NationalSmallAreaJurisdiction(
        "62", "70", "NU", "Nunavut", "Nunavut", "da-territories"
    ),
)

# Compatibility names retained for the pre-generalization public imports.
NationalDAJurisdiction = NationalSmallAreaJurisdiction
CANADA_DA_JURISDICTIONS = CANADA_SMALL_AREA_JURISDICTIONS

_SMALL_AREA_SPECIFICATIONS = {
    "da": NationalSmallAreaSpecification(
        geography_level="da",
        identifier_column="DAUID",
        dgrf_column="DADGUID_ADIDUGD",
        profile_keys=tuple(
            dict.fromkeys(
                jurisdiction.da_profile_key
                for jurisdiction in CANADA_SMALL_AREA_JURISDICTIONS
            )
        ),
    ),
    "ada": NationalSmallAreaSpecification(
        geography_level="ada",
        identifier_column="ADAUID",
        dgrf_column="ADADGUID_ADAIDUGD",
        profile_keys=("ada",),
    ),
}


def small_area_specification(
    geography_level: str,
) -> NationalSmallAreaSpecification:
    """Return the registered national source contract for DA or ADA.

    Geography-level matching is case-insensitive. Unsupported levels raise
    :class:`ValueError`; national orchestration is not inferred for every
    geography supported by smaller local workflows.
    """

    try:
        return _SMALL_AREA_SPECIFICATIONS[geography_level.lower()]
    except KeyError as exc:
        raise ValueError("national geography level must be da or ada") from exc


def required_2021_profile_keys(geography_level: str) -> tuple[str, ...]:
    """Return registered 2021 Census Profile keys for national DA or ADA work.

    DA returns the six regional products covering Canada; ADA returns its one
    national product. Keys are suitable for
    :func:`synthpopcan.statcan.fetch_census_profile`.
    """

    return small_area_specification(geography_level).profile_keys


def required_2021_da_profile_keys() -> tuple[str, ...]:
    """Return the six regional profile keys covering every jurisdiction."""

    return required_2021_profile_keys("da")


def national_2021_profile_paths(
    root: Path,
    geography_level: str,
) -> dict[str, Path]:
    """Resolve conventional local paths for all required profile products.

    The resolver accepts the current nested cache layout and the earlier flat
    layout. It returns expected paths whether or not every file exists, so
    callers can report missing products explicitly before planning.
    """

    resolved: dict[str, Path] = {}
    for key in required_2021_profile_keys(geography_level):
        filename = f"2021-census-profile-{key}.csv"
        flat = root / filename
        nested_name = key.removeprefix("da-") if geography_level == "da" else key
        nested = root / nested_name / filename
        resolved[key] = flat if flat.is_file() else nested
    return resolved


def regional_2021_da_profile_paths(root: Path) -> dict[str, Path]:
    """Resolve the conventional nested or legacy flat regional profile paths."""

    return national_2021_profile_paths(root, "da")


def load_2021_small_area_jurisdictions(
    relationship_path: Path,
    geography_level: str,
) -> dict[str, str]:
    """Read authoritative DA- or ADA-to-PRUID relationships from the 2021 DGRF.

    Short identifiers are derived from the product's DGUID columns. Missing
    required columns, conflicting assignments, and unsupported PRUIDs raise
    :class:`ValueError`; no prefix-based jurisdiction inference is used.
    """

    specification = small_area_specification(geography_level)
    relationships: dict[str, str] = {}
    conflicts: set[str] = set()
    with relationship_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"PRDGUID_PRIDUGD", specification.dgrf_column}
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ValueError("DGRF is missing required columns: " + ", ".join(missing))
        for row in reader:
            province_dguid = row["PRDGUID_PRIDUGD"].strip()
            geography_dguid = row[specification.dgrf_column].strip()
            if not province_dguid or not geography_dguid:
                continue
            pruid = _short_numeric_identifier(province_dguid, 2, "province")
            identifier = _short_numeric_identifier(
                geography_dguid,
                8,
                specification.geography_level.upper(),
            )
            previous = relationships.setdefault(identifier, pruid)
            if previous != pruid:
                conflicts.add(identifier)
    if conflicts:
        raise ValueError(
            f"DGRF assigns {specification.geography_level.upper()}s to "
            "conflicting jurisdictions: " + ", ".join(sorted(conflicts)[:10])
        )
    known_pruids = {item.pruid for item in CANADA_SMALL_AREA_JURISDICTIONS}
    unknown = sorted(set(relationships.values()) - known_pruids)
    if unknown:
        raise ValueError(
            "DGRF contains unsupported PRUID values: " + ", ".join(unknown)
        )
    return relationships


def load_2021_da_jurisdictions(relationship_path: Path) -> dict[str, str]:
    """Compatibility wrapper for authoritative DA-to-PRUID relationships."""

    return load_2021_small_area_jurisdictions(relationship_path, "da")


def prepare_canada_small_area_plan(
    profile_paths: Mapping[str, Path],
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    *,
    geography_level: str,
    max_households_per_batch: int = 100_000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Prepare a restartable national DA or ADA plan from official inputs.

    The planner scans registered profiles, reconciles identifiers through the
    final DGRF, partitions a national boundary file once, excludes and reports
    incomplete controls, writes bounded batch controls and manifests, and
    records source hashes and conservative storage estimates. It performs no
    population generation.
    """

    specification = small_area_specification(geography_level)
    if max_households_per_batch < 1:
        raise ValueError("max_households_per_batch must be at least 1")
    required_profiles = set(specification.profile_keys)
    missing_profiles = sorted(required_profiles - set(profile_paths))
    if missing_profiles:
        raise ValueError(
            f"missing 2021 {geography_level.upper()} profiles: "
            + ", ".join(missing_profiles)
        )
    relationships = load_2021_small_area_jurisdictions(
        relationship_path,
        geography_level,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    boundaries_directory = output_directory / "boundaries"
    batch_directory = output_directory / "batches"

    identifiers_by_pruid = {
        jurisdiction.pruid: {
            identifier
            for identifier, pruid in relationships.items()
            if pruid == jurisdiction.pruid
        }
        for jurisdiction in CANADA_SMALL_AREA_JURISDICTIONS
    }
    controls_by_pruid: dict[str, dict[str, dict[str, dict[str, float]]]] = {
        jurisdiction.pruid: {} for jurisdiction in CANADA_SMALL_AREA_JURISDICTIONS
    }
    profile_evidence: dict[str, dict[str, object]] = {}
    for profile_key in specification.profile_keys:
        if progress is not None:
            progress(f"Scanning and hashing {profile_key}")
        profile_path = profile_paths[profile_key]
        jurisdictions = [
            item
            for item in CANADA_SMALL_AREA_JURISDICTIONS
            if specification.profile_key_for(item) == profile_key
        ]
        selected_ids = set().union(
            *(identifiers_by_pruid[item.pruid] for item in jurisdictions)
        )
        extracted = extract_controls_from_profile(
            profile_path,
            specification.geography_level,
            geo_ids=selected_ids,
        )
        for jurisdiction in jurisdictions:
            controls_by_pruid[jurisdiction.pruid] = {
                identifier: extracted[identifier]
                for identifier in identifiers_by_pruid[jurisdiction.pruid]
                if identifier in extracted
            }
        profile_evidence[profile_key] = {
            "path": str(profile_path),
            **file_integrity(profile_path),
        }

    boundary_outputs = {
        jurisdiction.pruid: (
            boundaries_directory
            / (
                f"2021-boundary-{specification.geography_level}-"
                f"{jurisdiction.abbreviation.lower()}.geojson"
            )
        )
        for jurisdiction in CANADA_SMALL_AREA_JURISDICTIONS
    }
    if progress is not None:
        progress(
            "Partitioning national "
            f"{specification.geography_level.upper()} boundaries by province "
            "and territory"
        )
    boundary_report = partition_boundaries_geojson(
        boundary_path,
        boundary_outputs,
        relationships,
    )

    batches: list[dict[str, object]] = []
    jurisdiction_reports: list[dict[str, object]] = []
    total_usable_geographies = 0
    total_excluded_geographies = 0
    for jurisdiction in CANADA_SMALL_AREA_JURISDICTIONS:
        if progress is not None:
            progress(
                f"Writing {jurisdiction.abbreviation} controls and batch manifests"
            )
        expected = identifiers_by_pruid[jurisdiction.pruid]
        raw = controls_by_pruid[jurisdiction.pruid]
        missing_controls = sorted(expected - set(raw))
        source_total = round(
            sum(
                sum(margins.get("hhsize", {}).values())
                for margins in raw.values()
                if margins.get("hhsize") and margins.get("tenure")
            )
        )
        if source_total:
            scaled, incomplete = scale_and_validate_controls(raw, source_total)
        else:
            scaled, incomplete = {}, sorted(raw)
        usable = set(scaled)
        partition_report = boundary_report["partitions"][jurisdiction.pruid]
        missing_boundaries = set(partition_report["missing_identifiers"])
        usable_without_boundaries = sorted(usable & missing_boundaries)
        if usable_without_boundaries:
            raise ValueError(
                f"{jurisdiction.abbreviation} has usable "
                f"{specification.geography_level.upper()} controls without "
                "matching boundaries: " + ", ".join(usable_without_boundaries[:10])
            )
        total_usable_geographies += len(usable)
        total_excluded_geographies += len(expected - usable)
        batch_groups = _partition_controls(scaled, max_households_per_batch)
        for index, identifiers in enumerate(batch_groups, start=1):
            batch_id = f"{jurisdiction.pruid}-{index:04d}"
            directory = batch_directory / jurisdiction.pruid / f"{index:04d}"
            controls_path = directory / "controls.csv"
            selected_controls = {
                identifier: scaled[identifier] for identifier in identifiers
            }
            write_controls_csv(
                selected_controls,
                controls_path,
                specification.geography_level,
                household_size_column="household_size_group",
            )
            household_total = sum(
                sum(margins["hhsize"].values())
                for margins in selected_controls.values()
            )
            batch_manifest: dict[str, object] = {
                "schema_version": _BATCH_SCHEMA,
                "batch_id": batch_id,
                "status": "planned",
                "jurisdiction": _jurisdiction_payload(jurisdiction, specification),
                "geography": statcan_geography_universe(
                    2021,
                    specification.geography_level,
                    specification.identifier_column,
                    dguid_column="DGUID",
                ).as_dict(),
                "identifiers": identifiers,
                "small_areas": len(identifiers),
                "target_households": household_total,
                "controls": {
                    "path": str(controls_path.relative_to(output_directory)),
                    **file_integrity(controls_path),
                },
                "boundaries": str(
                    boundary_outputs[jurisdiction.pruid].relative_to(output_directory)
                ),
                "output_directory": str(
                    (directory / "population").relative_to(output_directory)
                ),
            }
            batch_manifest_path = directory / "batch.json"
            _write_json(batch_manifest_path, batch_manifest)
            batch_record = {
                "batch_id": batch_id,
                "manifest": str(batch_manifest_path.relative_to(output_directory)),
                "jurisdiction_pruid": jurisdiction.pruid,
                "small_areas": len(identifiers),
                "target_households": household_total,
            }
            batches.append(batch_record)
        jurisdiction_reports.append(
            {
                **_jurisdiction_payload(jurisdiction, specification),
                "expected_geographies": len(expected),
                "usable_geographies": len(usable),
                "missing_profile_controls": missing_controls,
                "incomplete_profile_controls": sorted(incomplete),
                "excluded_geographies": len(expected - usable),
                "target_households": sum(
                    sum(margins["hhsize"].values()) for margins in scaled.values()
                ),
                "batches": len(batch_groups),
                "missing_boundaries_for_excluded_geographies": sorted(
                    missing_boundaries - usable
                ),
                "boundary_report": partition_report,
            }
        )

    storage_estimate = estimate_national_small_area_storage(batches)
    manifest: dict[str, object] = {
        "schema_version": _PLAN_SCHEMA,
        "status": "planned",
        "census_vintage": 2021,
        "geography": statcan_geography_universe(
            2021,
            specification.geography_level,
            specification.identifier_column,
            dguid_column="DGUID",
        ).as_dict(),
        "batch_policy": {
            "unit": "province-or-territory",
            "max_households_per_batch": max_households_per_batch,
            "restartable": True,
        },
        "storage_estimate": storage_estimate,
        "inputs": {
            "profiles": profile_evidence,
            "boundaries": {
                "path": str(boundary_path),
                **file_integrity(boundary_path),
            },
            "relationships": {
                "path": str(relationship_path),
                **file_integrity(relationship_path),
            },
        },
        "coverage": {
            "jurisdictions": len(CANADA_SMALL_AREA_JURISDICTIONS),
            "expected_geographies": len(relationships),
            "usable_geographies": total_usable_geographies,
            "excluded_geographies": total_excluded_geographies,
        },
        "jurisdictions": jurisdiction_reports,
        "boundary_partition": boundary_report,
        "batches": batches,
        "limitations": [
            "Planning does not imply that every batch has been synthesized.",
            f"{specification.geography_level.upper()}s with absent, zero, or "
            "incomplete household-size or tenure controls are excluded and "
            "reported rather than imputed.",
            "Integer realization residuals and linked-person validation must be "
            "reviewed independently for every completed batch.",
            "The plan uses household controls only unless a separately validated "
            "person-control resource is supplied.",
        ],
    }
    _write_json(output_directory / "plan.json", manifest)
    return manifest


def estimate_national_small_area_storage(
    batches: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    """Estimate persistent output and peak working storage for planned batches.

    Estimates use documented per-household planning constants, the total target
    household count, and the largest batch. The recommended free-space value
    adds a reserve; it is a conservative execution guard rather than a measured
    final file size.
    """

    household_counts: list[int] = []
    for batch in batches:
        value = batch.get("target_households")
        if not isinstance(value, int) or value < 0:
            raise ValueError("batch target_households must be a non-negative integer")
        household_counts.append(value)
    total = sum(household_counts)
    largest = max(household_counts, default=0)
    persistent = total * _ESTIMATED_PERSISTENT_BYTES_PER_HOUSEHOLD
    peak_working = largest * _ESTIMATED_WORKING_BYTES_PER_HOUSEHOLD
    return {
        "total_households": total,
        "largest_batch_households": largest,
        "estimated_persistent_output_bytes": persistent,
        "estimated_peak_batch_working_bytes": peak_working,
        "recommended_free_space_bytes": (
            persistent + peak_working + _RECOMMENDED_FREE_SPACE_RESERVE_BYTES
        ),
    }


def estimate_national_da_storage(
    batches: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    """Compatibility wrapper for national storage estimation."""

    return estimate_national_small_area_storage(batches)


def execute_canada_small_area_plan(
    plan_path: Path,
    run_batch: Callable[[Mapping[str, object], Path], Mapping[str, object]],
    *,
    limit: int | None = None,
    continue_on_error: bool = False,
    jurisdiction_pruids: set[str] | None = None,
    workers: int = 1,
) -> dict[str, object]:
    """Execute or resume national batches through a caller-supplied callback.

    Completed batches are skipped, each attempted transition is persisted, and
    failures can stop execution or be recorded while later batches continue.
    ``limit`` and ``jurisdiction_pruids`` bound the selected work; ``workers``
    controls independent batch processes. The callback owns batch-specific
    synthesis and must return serializable result evidence.
    """

    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    if workers < 1:
        raise ValueError("workers must be at least 1")
    root = plan_path.parent
    plan = _read_json(plan_path)
    if plan.get("schema_version") != _PLAN_SCHEMA:
        raise ValueError("unsupported national small-area plan schema")
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    if workers > 1:
        return _execute_canada_small_area_plan_parallel(
            plan_path,
            plan,
            records,
            run_batch,
            limit=limit,
            continue_on_error=continue_on_error,
            jurisdiction_pruids=jurisdiction_pruids,
            workers=workers,
        )
    attempted = 0
    failures: list[str] = []
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("manifest"), str
        ):
            raise ValueError("national small-area plan batch record is invalid")
        record_pruid = record.get("jurisdiction_pruid")
        if jurisdiction_pruids is not None and record_pruid not in jurisdiction_pruids:
            continue
        batch_path = root / record["manifest"]
        batch = _read_json(batch_path)
        if batch.get("schema_version") != _BATCH_SCHEMA:
            raise ValueError(f"unsupported batch schema in {batch_path}")
        if batch.get("status") == "completed":
            continue
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        attempts = batch.get("attempts", 0)
        if not isinstance(attempts, int):
            raise ValueError(f"batch attempts must be an integer in {batch_path}")
        batch["status"] = "running"
        batch["attempts"] = attempts + 1
        batch.pop("error", None)
        _write_json(batch_path, batch)
        try:
            result = dict(run_batch(batch, root))
        except KeyboardInterrupt:
            batch["status"] = "planned"
            batch["interrupted_attempt"] = batch["attempts"]
            _write_json(batch_path, batch)
            _refresh_plan_status(plan, root)
            _write_json(plan_path, plan)
            raise
        except Exception as exc:
            batch["status"] = "failed"
            batch["error"] = f"{type(exc).__name__}: {exc}"
            _write_json(batch_path, batch)
            batch_id = str(batch.get("batch_id", batch_path))
            failures.append(batch_id)
            if not continue_on_error:
                _refresh_plan_status(plan, root)
                _write_json(plan_path, plan)
                raise
        else:
            batch["status"] = "completed"
            batch["result"] = result
            _write_json(batch_path, batch)
            _refresh_plan_status(plan, root)
            _write_json(plan_path, plan)

    status_counts = _refresh_plan_status(plan, root)
    plan["last_execution"] = {
        "attempted_batches": attempted,
        "failed_batches": failures,
        "status_counts": status_counts,
    }
    _write_json(plan_path, plan)
    return plan


def _execute_canada_small_area_plan_parallel(
    plan_path: Path,
    plan: dict[str, object],
    records: list[object],
    run_batch: Callable[[Mapping[str, object], Path], Mapping[str, object]],
    *,
    limit: int | None,
    continue_on_error: bool,
    jurisdiction_pruids: set[str] | None,
    workers: int,
) -> dict[str, object]:
    """Execute independent batches in killable, bounded worker processes."""

    root = plan_path.parent
    candidates: list[tuple[Path, dict[str, object]]] = []
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("manifest"),
            str,
        ):
            raise ValueError("national small-area plan batch record is invalid")
        if (
            jurisdiction_pruids is not None
            and record.get("jurisdiction_pruid") not in jurisdiction_pruids
        ):
            continue
        batch_path = root / str(record["manifest"])
        batch = _read_json(batch_path)
        if batch.get("schema_version") != _BATCH_SCHEMA:
            raise ValueError(f"unsupported batch schema in {batch_path}")
        if batch.get("status") == "completed":
            continue
        candidates.append((batch_path, batch))
        if limit is not None and len(candidates) >= limit:
            break

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    active: dict[str, tuple[Any, Path, dict[str, object]]] = {}
    pending = iter(candidates)
    attempted = 0
    failures: list[str] = []
    failure_messages: list[str] = []
    stop_scheduling = False

    def start_next() -> bool:
        nonlocal attempted, stop_scheduling
        if stop_scheduling:
            return False
        try:
            batch_path, batch = next(pending)
        except StopIteration:
            return False
        batch_id = str(batch.get("batch_id", batch_path))
        attempts = batch.get("attempts", 0)
        if not isinstance(attempts, int):
            raise ValueError(f"batch attempts must be an integer in {batch_path}")
        batch["status"] = "running"
        batch["attempts"] = attempts + 1
        batch.pop("error", None)
        _write_json(batch_path, batch)
        process = context.Process(
            target=_parallel_batch_entry,
            args=(run_batch, batch, root, batch_id, result_queue),
            name=f"synthpopcan-{batch_id}",
        )
        try:
            process.start()
        except BaseException:
            batch["status"] = "planned"
            _write_json(batch_path, batch)
            raise
        active[batch_id] = (process, batch_path, batch)
        attempted += 1
        return True

    try:
        while len(active) < workers and start_next():
            pass
        while active:
            try:
                message = result_queue.get(timeout=0.25)
            except queue.Empty:
                message = None
            if message is None:
                crashed = [
                    batch_id
                    for batch_id, (process, _, _) in active.items()
                    if not process.is_alive() and process.exitcode not in (None, 0)
                ]
                for batch_id in crashed:
                    result_queue.put(
                        (
                            "error",
                            batch_id,
                            "WorkerProcessError",
                            f"worker exited with code {active[batch_id][0].exitcode}",
                            "",
                        )
                    )
                continue

            status, batch_id, *payload = message
            active_entry = active.pop(str(batch_id), None)
            if active_entry is None:
                continue
            process, batch_path, batch = active_entry
            process.join()
            if status == "ok":
                batch["status"] = "completed"
                batch["result"] = dict(payload[0])
            else:
                error_type, error_message, worker_traceback = payload
                batch["status"] = "failed"
                batch["error"] = f"{error_type}: {error_message}"
                batch["worker_traceback"] = worker_traceback
                failures.append(str(batch_id))
                failure_messages.append(batch["error"])
                if not continue_on_error:
                    stop_scheduling = True
            _write_json(batch_path, batch)
            _refresh_plan_status(plan, root)
            _write_json(plan_path, plan)
            while len(active) < workers and start_next():
                pass
    except KeyboardInterrupt:
        for process, _, _ in active.values():
            if process.is_alive():
                process.terminate()
        for process, batch_path, batch in active.values():
            process.join()
            batch["status"] = "planned"
            batch["interrupted_attempt"] = batch["attempts"]
            _write_json(batch_path, batch)
        _refresh_plan_status(plan, root)
        _write_json(plan_path, plan)
        raise
    finally:
        result_queue.close()
        result_queue.join_thread()

    status_counts = _refresh_plan_status(plan, root)
    plan["last_execution"] = {
        "attempted_batches": attempted,
        "failed_batches": failures,
        "status_counts": status_counts,
        "workers": workers,
    }
    _write_json(plan_path, plan)
    if failures and not continue_on_error:
        raise RuntimeError(failure_messages[0])
    return plan


def _parallel_batch_entry(
    run_batch: Callable[[Mapping[str, object], Path], Mapping[str, object]],
    batch: Mapping[str, object],
    root: Path,
    batch_id: str,
    result_queue: Any,
) -> None:
    """Run one picklable callback and return only serializable evidence."""

    try:
        result = dict(run_batch(batch, root))
    except Exception as exc:
        result_queue.put(
            (
                "error",
                batch_id,
                type(exc).__name__,
                str(exc),
                traceback.format_exc(),
            )
        )
    else:
        result_queue.put(("ok", batch_id, result))


def prepare_canada_da_plan(
    profile_paths: Mapping[str, Path],
    boundary_path: Path,
    relationship_path: Path,
    output_directory: Path,
    *,
    max_households_per_batch: int = 100_000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Compatibility wrapper for the national DA adapter."""

    return prepare_canada_small_area_plan(
        profile_paths,
        boundary_path,
        relationship_path,
        output_directory,
        geography_level="da",
        max_households_per_batch=max_households_per_batch,
        progress=progress,
    )


def execute_canada_da_plan(
    plan_path: Path,
    run_batch: Callable[[Mapping[str, object], Path], Mapping[str, object]],
    *,
    limit: int | None = None,
    continue_on_error: bool = False,
    jurisdiction_pruids: set[str] | None = None,
    workers: int = 1,
) -> dict[str, object]:
    """Compatibility wrapper for national DA plan execution."""

    return execute_canada_small_area_plan(
        plan_path,
        run_batch,
        limit=limit,
        continue_on_error=continue_on_error,
        jurisdiction_pruids=jurisdiction_pruids,
        workers=workers,
    )


def _partition_controls(
    controls: Mapping[str, Mapping[str, Mapping[str, int]]],
    maximum: int,
) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    current_total = 0
    for identifier in sorted(controls):
        total = sum(controls[identifier]["hhsize"].values())
        if current and current_total + total > maximum:
            groups.append(current)
            current = []
            current_total = 0
        current.append(identifier)
        current_total += total
    if current:
        groups.append(current)
    return groups


def _short_numeric_identifier(dguid: str, length: int, label: str) -> str:
    identifier = dguid[-length:]
    if len(identifier) != length or not identifier.isdigit():
        raise ValueError(f"invalid {label} DGUID: {dguid!r}")
    return identifier


def _jurisdiction_payload(
    jurisdiction: NationalSmallAreaJurisdiction,
    specification: NationalSmallAreaSpecification,
) -> dict[str, str]:
    return {
        "pruid": jurisdiction.pruid,
        "pumf_pr": jurisdiction.pumf_pr,
        "abbreviation": jurisdiction.abbreviation,
        "name_en": jurisdiction.name_en,
        "name_fr": jurisdiction.name_fr,
        "profile_key": specification.profile_key_for(jurisdiction),
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _refresh_plan_status(
    plan: dict[str, object],
    root: Path,
) -> dict[str, int]:
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("manifest"), str
        ):
            raise ValueError("national small-area plan batch record is invalid")
        status = _read_json(root / record["manifest"]).get("status")
        label = status if isinstance(status, str) else "unknown"
        counts[label] = counts.get(label, 0) + 1
    if counts.get("completed") == len(records):
        plan["status"] = "completed"
    elif counts.get("failed"):
        plan["status"] = "failed"
    elif counts.get("completed"):
        plan["status"] = "partial"
    else:
        plan["status"] = "planned"
    return counts
