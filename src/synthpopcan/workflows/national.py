"""File-backed national execution, independent of CLI parsing and map presentation."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from synthpopcan.national_small_area import CANADA_SMALL_AREA_JURISDICTIONS


class NationalRunInputError(ValueError):
    """A national command's plan identity or resource precondition is invalid."""


@dataclass(frozen=True)
class NationalRunRequest:
    package_path: str
    plan_path: Path
    limit: int | None
    jurisdiction_values: tuple[str, ...]
    random_seed: int
    condition_by_jurisdiction: bool
    continue_on_error: bool
    candidate_pool_size: int
    workers: int
    fit_workers: int
    force_candidate_pools: bool
    allow_low_disk: bool
    expected_geography_level: str


@dataclass(frozen=True)
class NationalRunResult:
    plan: dict[str, Any]
    summary: dict[str, Any]
    jurisdiction_pruids: set[str] | None
    identifier_column: str


def _jurisdictions(request: NationalRunRequest) -> set[str] | None:
    selector_lookup = {
        selector.casefold(): item.pruid
        for item in CANADA_SMALL_AREA_JURISDICTIONS
        for selector in (item.pruid, item.abbreviation)
    }
    jurisdiction_pruids = (
        {selector_lookup[value.casefold()] for value in request.jurisdiction_values}
        if request.jurisdiction_values
        else None
    )
    return jurisdiction_pruids


def _plan_identity(request: NationalRunRequest) -> tuple[str, str]:
    plan_payload = json.loads(request.plan_path.read_text())
    storage = (
        plan_payload.get("storage_estimate") if isinstance(plan_payload, dict) else None
    )
    geography = (
        plan_payload.get("geography") if isinstance(plan_payload, dict) else None
    )
    if not isinstance(geography, Mapping):
        raise NationalRunInputError("The national plan has no geography identity.")
    geography_level = geography.get("geography_level")
    identifier_column = geography.get("identifier_column")
    identifier_namespace = geography.get("identifier_namespace")
    if geography_level != request.expected_geography_level:
        raise NationalRunInputError(
            f"This command requires a {request.expected_geography_level.upper()} plan, "
            f"not {geography_level!r}."
        )
    if not isinstance(identifier_column, str) or not isinstance(
        identifier_namespace, str
    ):
        raise NationalRunInputError(
            "The national plan geography identity is incomplete."
        )
    if isinstance(storage, dict):
        required = storage.get("recommended_free_space_bytes")
        if isinstance(required, int):
            free = shutil.disk_usage(request.plan_path.parent).free
            if free < required and (not request.allow_low_disk):
                raise NationalRunInputError(
                    "The national plan conservatively recommends "
                    f"{required / 1024**3:.1f} GiB free, but only "
                    f"{free / 1024**3:.1f} GiB is available. Free space, reduce "
                    "the plan, or pass --allow-low-disk after reviewing the risk."
                )
    return identifier_column, identifier_namespace


def _candidate_pools(
    request: NationalRunRequest,
    jurisdiction_pruids: set[str] | None,
    progress: Callable[[str], None],
) -> dict[str, Any]:
    from synthpopcan.national_execution import (
        find_cached_national_candidate_pools,
        prepare_national_candidate_pools,
    )
    from synthpopcan.statcan import file_integrity
    from synthpopcan.workflows.models import (
        prepared_model_models,
        resolve_prepared_model_package,
        validate_prepared_model_publishable,
    )

    pumf_pr_values = (
        {
            item.pumf_pr
            for item in CANADA_SMALL_AREA_JURISDICTIONS
            if item.pruid in jurisdiction_pruids
        }
        if jurisdiction_pruids is not None
        else None
    )
    local_package_path = Path(request.package_path)
    model_evidence: dict[str, object] | None = None
    if local_package_path.is_file():
        model_evidence = {
            "label": request.package_path,
            "path": str(local_package_path),
            **file_integrity(local_package_path),
        }
    pool_reports = (
        find_cached_national_candidate_pools(
            request.plan_path,
            model_evidence=model_evidence,
            requested_pool_size=request.candidate_pool_size,
            base_seed=request.random_seed,
            condition_by_jurisdiction=request.condition_by_jurisdiction,
            pumf_pr_values=pumf_pr_values,
        )
        if model_evidence is not None and (not request.force_candidate_pools)
        else None
    )
    if pool_reports is not None:
        progress("Verified reusable candidate pools without loading the model")
    else:
        package_started = time.perf_counter()
        resolved_package = resolve_prepared_model_package(request.package_path)
        package = resolved_package.package
        validate_prepared_model_publishable(package)
        (household_model, person_model) = prepared_model_models(package)
        if resolved_package.source_path is not None:
            model_evidence = {
                "label": resolved_package.label,
                "path": str(resolved_package.source_path),
                **file_integrity(resolved_package.source_path),
            }
        else:
            canonical = json.dumps(
                package, sort_keys=True, separators=(",", ":")
            ).encode()
            model_evidence = {
                "label": resolved_package.label,
                "schema_version": package.get("schema_version"),
                "sha256": hashlib.sha256(canonical).hexdigest(),
                "byte_size": len(canonical),
            }
        package_seconds = time.perf_counter() - package_started
        progress(f"Loaded model package once in {package_seconds:.1f}s")
        pool_reports = prepare_national_candidate_pools(
            request.plan_path,
            household_model=household_model,
            person_model=person_model,
            household_size_column=str(
                package.get("household_size_column", "household_size")
            ),
            model_evidence=model_evidence,
            requested_pool_size=request.candidate_pool_size,
            base_seed=request.random_seed,
            condition_by_jurisdiction=request.condition_by_jurisdiction,
            pumf_pr_values=pumf_pr_values,
            force=request.force_candidate_pools,
            progress=progress,
        )
    assert pool_reports is not None
    return pool_reports


def run_national_small_area_files(
    request: NationalRunRequest,
    *,
    progress: Callable[[str], None],
    after_batches: Callable[[dict[str, Any], set[str] | None, str], None] | None = None,
) -> NationalRunResult:
    """Reuse or prepare pools, execute batches, and build the national summary."""
    from synthpopcan.national_execution import (
        NationalBatchRunConfiguration,
        build_national_geography_summary,
        run_national_cached_batch,
    )
    from synthpopcan.national_small_area import execute_canada_small_area_plan

    jurisdiction_pruids = _jurisdictions(request)
    identifier_column, identifier_namespace = _plan_identity(request)
    pool_reports = _candidate_pools(request, jurisdiction_pruids, progress)
    if request.condition_by_jurisdiction:
        pool_manifests = {
            pumf_pr: str(
                (
                    request.plan_path.parent
                    / "candidate-pools"
                    / f"pr-{pumf_pr}"
                    / "manifest.json"
                ).relative_to(request.plan_path.parent)
            )
            for pumf_pr in pool_reports
        }
    else:
        all_manifest = str(
            (
                request.plan_path.parent / "candidate-pools" / "all" / "manifest.json"
            ).relative_to(request.plan_path.parent)
        )
        pool_manifests = {
            item.pumf_pr: all_manifest for item in CANADA_SMALL_AREA_JURISDICTIONS
        }
    configuration = NationalBatchRunConfiguration(
        pool_manifests=pool_manifests,
        geography_level=request.expected_geography_level,
        identifier_column=identifier_column,
        identifier_namespace=identifier_namespace,
        fit_workers=request.fit_workers,
    )
    run_batch = partial(run_national_cached_batch, configuration=configuration)
    plan = execute_canada_small_area_plan(
        request.plan_path,
        run_batch,
        limit=request.limit,
        continue_on_error=request.continue_on_error,
        jurisdiction_pruids=jurisdiction_pruids,
        workers=request.workers,
    )
    if after_batches is not None:
        after_batches(plan, jurisdiction_pruids, identifier_column)
    national_summary = build_national_geography_summary(request.plan_path)
    return NationalRunResult(
        plan, national_summary, jurisdiction_pruids, identifier_column
    )
