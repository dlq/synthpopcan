"""Calibrate a prepared Census control directory as one user-facing stage."""

from __future__ import annotations

import csv
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any

from synthpopcan._candidate_preparation import prepare_candidates
from synthpopcan._population_preparation import (
    _combine_population_files,
    audit_population,
)
from synthpopcan._profile_preparation import PROFILE, write_json
from synthpopcan.controls import read_control_table
from synthpopcan.geography import GeographyUniverse
from synthpopcan.linked_schema import read_linked_population_contract
from synthpopcan.small_area_synthesis import controls_by_geography
from synthpopcan.tree import validate_linked_population_files
from synthpopcan.workflows.preparation import file_fingerprint
from synthpopcan.workflows.small_area import (
    SmallAreaCalibrationRequest,
    SmallAreaCalibrationResult,
    calibrate_small_area_files,
)
from synthpopcan.workflows.types import ProgressReporter, WorkflowProgress


def _emit(progress, message):
    if progress is not None:
        progress(WorkflowProgress("prepared-calibration", message))


def _read_plan(request: SmallAreaCalibrationRequest):
    if (
        request.person_controls_path
        or request.control_pack
        or request.control_pack_evidence
    ):
        raise ValueError(
            "Prepared control directories already define all batches; omit "
            "--person-controls, --control-pack and --control-pack-evidence."
        )
    if request.augment_support and request.pool_size is None:
        raise ValueError("--augment-support requires --pool-size.")
    plan = json.loads((request.controls_path / "plan.json").read_text())
    if not isinstance(plan, dict) or plan.get("source_profile") != PROFILE:
        raise ValueError(
            "Use the directory written by geo prepare-controls for the "
            "hierarchical 2021 source profile."
        )
    dimension = plan.get("geography_dimension", "ct")
    if (
        dimension not in {"ct", "ada"}
        or plan.get("geography_level", dimension) != dimension
    ):
        raise ValueError("Prepared controls require a Census 2021 CT or ADA identity.")
    if request.geography_dimension != dimension:
        if dimension == "ct":
            raise ValueError(
                "Prepared CMA controls currently require --geo-dimension ct."
            )
        raise ValueError("Prepared provincial controls require --geo-dimension ada.")
    batches = plan.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError(
            "Prepared control plan has no batches; prepare the controls again."
        )
    names, geos = set(), set()
    for batch in batches:
        _validate_batch(request.controls_path, batch, names, geos, dimension)
    if set(_selected_geographies(plan)) != geos:
        raise ValueError(
            "Prepared batches do not cover the plan's geography selection."
        )
    return plan


def _selected_geographies(record):
    return record.get("geographies", record.get("tracts", []))


def _validate_batch(directory, batch, names, geos, dimension="ct"):
    if not isinstance(batch, dict):
        raise ValueError("Invalid prepared batch record.")
    name = batch.get("name")
    if name not in {"private-households", "zero-collective"} or name in names:
        raise ValueError(
            "Prepared control plan has an unknown or duplicate batch name."
        )
    names.add(name)
    if batch.get("include_age_gender") is not (name == "zero-collective"):
        raise ValueError(
            "Prepared batch age/gender policy conflicts with its universe."
        )
    selected = set(_selected_geographies(batch))
    if not selected or selected & geos:
        raise ValueError(
            "Prepared batches must contain nonempty, disjoint geographies."
        )
    for entity in ("household", "person"):
        table = read_control_table(directory / name / f"{entity}-controls.csv")
        if set(controls_by_geography(table, geography_dimension=dimension)) != selected:
            raise ValueError(
                f"{name} {entity} controls do not match the plan's geographies."
            )
    geos.update(selected)


def _universe(request):
    dimension = request.geography_dimension
    inferred = GeographyUniverse(
        2021, dimension, f"statcan:census:2021:{dimension}", request.geography_column
    )
    if request.geography_universe is not None:
        if request.geography_universe.canonical_key != inferred.canonical_key:
            raise ValueError(
                "Prepared controls require the matching Census 2021 geography identity."
            )
        return request.geography_universe
    return inferred


def _prepare_batches(request, plan, progress):
    source = request.candidate_households_path.parent
    if (
        request.candidate_households_path.name != "households.csv"
        or request.candidate_persons_path != source / "persons.csv"
    ):
        raise ValueError(
            "Prepared control calibration requires a linked population directory "
            "with households.csv and persons.csv."
        )
    work = request.output_dir / "work"
    base = work / "candidates-private"
    _emit(progress, "Screening the linked candidate pool for the full control set")
    prepare_candidates(source, base)
    requests = []
    universe = _universe(request)
    for batch in plan["batches"]:
        name = batch["name"]
        controls = request.controls_path / name
        candidates, augmented = _batch_candidates(
            request, batch, base, controls, work, progress
        )
        licensing = read_linked_population_contract(candidates / "manifest.json").get(
            "licensing"
        )
        requests.append(
            replace(
                request,
                candidate_households_path=candidates / "households.csv",
                candidate_persons_path=candidates / "persons.csv",
                controls_path=controls / "household-controls.csv",
                person_controls_path=controls / "person-controls.csv",
                output_dir=work / name,
                geography_universe=universe,
                licensing=licensing,
                pool_size=None if augmented else request.pool_size,
                augment_support=False,
            )
        )
    return requests


def _batch_candidates(request, batch, base, controls, work, progress):
    age = batch["include_age_gender"]
    observed = request.zero_target_policy == "observed"
    augmented = request.augment_support and (age or observed)
    if not age and not augmented:
        return base, False
    candidates = work / ("candidates-age" if age else "candidates-private-support")
    _emit(
        progress, "Preparing the linked candidate pool and requested category support"
    )
    prepare_candidates(
        base,
        candidates,
        require_gender=age,
        pool_size=request.pool_size if augmented else None,
        seed=request.subsample_seed,
        augment_support=augmented,
        controls_path=controls / "household-controls.csv",
        person_controls_path=controls / "person-controls.csv",
        geography_dimension=request.geography_dimension,
        support_strategy="witness" if observed and augmented else "linear",
    )
    return candidates, augmented


def _fit_batch(request: SmallAreaCalibrationRequest) -> SmallAreaCalibrationResult:
    profile_directory = os.environ.get("SYNTHPOPCAN_PROFILE_WORKERS")
    if not profile_directory:
        return calibrate_small_area_files(request)
    from synthpopcan.workflows.profiling import profile_cli_worker

    arguments = [
        "geo",
        "calibrate",
        str(request.candidate_households_path.parent),
        "--controls",
        str(request.controls_path),
        "--person-controls",
        str(request.person_controls_path),
        "--geo-dimension",
        request.geography_dimension,
        "--geo-column",
        request.geography_column,
        "--max-iterations",
        str(request.max_iterations),
        "--tolerance",
        str(request.tolerance),
        "--subsample-seed",
        str(request.subsample_seed),
        "--out",
        str(request.output_dir),
    ]
    if request.geography_universe is not None:
        geo = request.geography_universe
        arguments.extend(
            [
                "--census-vintage",
                str(geo.census_vintage),
                "--geo-level",
                geo.geography_level,
                "--geo-namespace",
                geo.identifier_namespace,
            ]
        )
    arguments.extend(["--joint-solver", request.joint_solver])
    if request.zero_target_policy != "structural":
        arguments.extend(["--zero-target-policy", request.zero_target_policy])
    if request.n_workers is not None:
        arguments.extend(["--workers", str(request.n_workers)])
    if request.pool_size is not None:
        arguments.extend(["--pool-size", str(request.pool_size)])
    if request.include_weights:
        arguments.append("--include-weights")
    profile_cli_worker(arguments, request.output_dir.name, Path(profile_directory))
    report = request.output_dir / "report.json"
    return SmallAreaCalibrationResult(
        request.output_dir / "households.csv",
        request.output_dir / "persons.csv",
        request.output_dir / "manifest.json",
        report,
        request.output_dir / "weights.csv" if request.include_weights else None,
        json.loads(report.read_text()),
    )


def _fit_batches(requests, progress):
    if len(requests) == 1:
        _emit(progress, "Calibrating the prepared geography batch")
        return [_fit_batch(requests[0])]
    results = {}
    _emit(
        progress, "Calibrating the two universe-specific geography batches concurrently"
    )
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        pending = {
            executor.submit(_fit_batch, request): i
            for i, request in enumerate(requests)
        }
        for future in as_completed(pending):
            index = pending[future]
            results[index] = future.result()
            _emit(progress, f"Finished batch {requests[index].output_dir.name}")
    return [results[i] for i in range(len(requests))]


def _combine_weights(results, output):
    with output.open("w", newline="") as handle:
        writer = None
        for result in results:
            if result.weights_path is None:
                raise ValueError("A batch did not write its requested weights file.")
            with result.weights_path.open(newline="") as source:
                reader = csv.DictReader(source)
                fields = list(reader.fieldnames or ())
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                if fields != writer.fieldnames:
                    raise ValueError("Batch weight columns do not match.")
                writer.writerows(reader)


def _merge_summary(results):
    summaries = [r.details["summary"] for r in results]
    non_converged = sorted(g for s in summaries for g in s["non_converged_geographies"])
    residuals = [r for s in summaries for r in s["largest_residuals"]]
    return {
        "total_geographies": sum(s["total_geographies"] for s in summaries),
        "converged_count": sum(s["converged_count"] for s in summaries),
        "non_converged_count": len(non_converged),
        "non_converged_geographies": non_converged,
        "max_abs_error": max(s["max_abs_error"] for s in summaries),
        "realized_max_abs_error": max(s["realized_max_abs_error"] for s in summaries),
        "largest_residuals": sorted(residuals, key=lambda r: -r["abs_error"])[:20],
    }


def _publish_population(request, plan, requests, results, progress):
    output = request.output_dir
    _emit(progress, "Combining assigned rows and validating household/person linkage")
    if len(results) == 1:
        # A single universe batch still gets a file-backed linkage check.
        from shutil import copyfile

        for name in ("households.csv", "persons.csv", "manifest.json"):
            copyfile(results[0].households_path.parent / name, output / name)
        report = dict(results[0].details)
        validation = validate_linked_population_files(
            output / "households.csv", output / "persons.csv"
        )
        if not validation["passed"]:
            raise ValueError(
                "Assigned rows failed household/person linkage validation."
            )
        report["validation"] = validation
    else:
        report = _combine_population_files(
            tuple(r.households_path.parent for r in results),
            output,
            request.geography_column,
        )
    _emit(progress, "Independently auditing every realized control cell")
    audit = audit_population(
        output,
        tuple(r.controls_path for r in requests),
        tuple(r.person_controls_path for r in requests),
        output,
        request.geography_column,
    )
    report.update(
        summary=_merge_summary(results),
        geographies={
            g: details
            for r in results
            for g, details in r.details["geographies"].items()
        },
        geography_universe=_universe(request).as_dict(),
        realized_control_audit=audit,
        prepared_control_plan=plan,
        source_reports=[file_fingerprint(r.report_path) for r in results],
    )
    _merge_zero_target_policy(report, request.zero_target_policy, results)
    write_json(output / "report.json", report)
    manifest = read_linked_population_contract(output / "manifest.json")
    manifest["source_profile"] = PROFILE
    manifest["prepared_control_plan"] = file_fingerprint(
        request.controls_path / "plan.json"
    )
    write_json(output / "manifest.json", manifest)
    weights = output / "weights.csv" if request.include_weights else None
    if weights is not None:
        _combine_weights(results, weights)
    return SmallAreaCalibrationResult(
        output / "households.csv",
        output / "persons.csv",
        output / "manifest.json",
        output / "report.json",
        weights,
        report,
    )


def _merge_zero_target_policy(report, requested, results):
    if requested != "observed":
        return
    counts = {"structural": 0, "observed": 0}
    for result in results:
        for policy, count in result.details["zero_target_policy"][
            "effective_counts"
        ].items():
            counts[policy] = counts.get(policy, 0) + count
    report["zero_target_policy"] = {"requested": requested, "effective_counts": counts}


def calibrate_prepared_controls(
    request: SmallAreaCalibrationRequest, *, progress: ProgressReporter | None = None
) -> SmallAreaCalibrationResult:
    """Screen, fit, combine, validate and audit the explicit source-plan batches."""
    plan = _read_plan(request)
    if request.output_dir.exists() and any(request.output_dir.iterdir()):
        raise ValueError(
            "Prepared calibration output is not empty. Choose a fresh --out "
            "directory; completed batches are retained for inspection."
        )
    request.output_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "status": "running",
        "source_profile": PROFILE,
        "controls": str(request.controls_path.resolve()),
        "options": {
            "workers": request.n_workers,
            "joint_solver": request.joint_solver,
            "pool_size": request.pool_size,
            "subsample_seed": request.subsample_seed,
            "augment_support": request.augment_support,
            "zero_target_policy": request.zero_target_policy,
            "max_iterations": request.max_iterations,
            "tolerance": request.tolerance,
        },
    }
    write_json(request.output_dir / "workflow.json", status)
    try:
        requests = _prepare_batches(request, plan, progress)
        results = _fit_batches(requests, progress)
        result = _publish_population(request, plan, requests, results, progress)
    except Exception as exc:
        write_json(
            request.output_dir / "workflow.json",
            {**status, "status": "failed", "error": str(exc)},
        )
        raise
    write_json(request.output_dir / "workflow.json", {**status, "status": "complete"})
    return result
