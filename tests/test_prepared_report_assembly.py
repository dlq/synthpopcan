"""Report ownership keeps prepared and standalone composition equivalent."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import synthpopcan._population_preparation as population
import synthpopcan.workflows.prepared_calibration as prepared
from synthpopcan._profile_preparation import PROFILE, write_json
from synthpopcan.linked_schema import build_linked_population_contract
from synthpopcan.workflows.small_area import (
    SmallAreaCalibrationRequest,
    SmallAreaCalibrationResult,
)


@pytest.fixture
def batches(tmp_path):
    controls = tmp_path / "controls"
    controls.mkdir()
    plan = {"source_profile": PROFILE, "tracts": ["4620001.00", "4620002.00"]}
    write_json(controls / "plan.json", plan)
    requests, results = [], []
    for index, geo in enumerate(plan["tracts"], 1):
        source = tmp_path / f"batch-{index}"
        source.mkdir()
        (source / "households.csv").write_text(
            f"synthetic_household_id,household_size,ct\nh{index},1,{geo}\n"
        )
        (source / "persons.csv").write_text(
            f"synthetic_person_id,synthetic_household_id,ct,group\np{index},h{index},{geo},all\n"
        )
        write_json(
            source / "manifest.json",
            build_linked_population_contract(
                source / "households.csv", source / "persons.csv", geography_column="ct"
            ),
        )
        batch_controls = controls / f"batch-{index}"
        batch_controls.mkdir()
        hh = batch_controls / "household-controls.csv"
        pp = batch_controls / "person-controls.csv"
        hh.write_text(
            f'margin,dimensions,ct,household_size,count\nsize,"ct,household_size",{geo},1,1\n'
        )
        pp.write_text(
            f'margin,dimensions,ct,group,count\nperson,"ct,group",{geo},all,1\n'
        )
        details = {
            "summary": {
                "total_geographies": 1,
                "converged_count": 1,
                "non_converged_geographies": [],
                "largest_residuals": [],
                "max_abs_error": 0.0,
                "realized_max_abs_error": 0.0,
            },
            "geographies": {
                geo: {"converged": True, "diagnostic": f"retained-{index}"}
            },
            "extra_source_details": ["must survive standalone combination"],
        }
        write_json(source / "report.json", details)
        requests.append(
            SmallAreaCalibrationRequest(
                source / "households.csv",
                source / "persons.csv",
                hh,
                source,
                "ct",
                "ct",
                person_controls_path=pp,
            )
        )
        results.append(
            SmallAreaCalibrationResult(
                source / "households.csv",
                source / "persons.csv",
                source / "manifest.json",
                source / "report.json",
                None,
                details,
            )
        )
    request = replace(
        requests[0],
        controls_path=controls,
        person_controls_path=None,
        output_dir=tmp_path / "assigned",
    )
    return request, plan, requests, results


def test_standalone_combine_retains_embedded_source_diagnostics(tmp_path, batches):
    _request, _plan, _requests, results = batches
    sources = tuple(r.households_path.parent for r in results)
    output = tmp_path / "standalone"
    report = population.combine_populations(sources, output, "ct")
    assert report["source_reports"] == [
        {"path": str(r.report_path.resolve()), "report": r.details} for r in results
    ]
    assert json.loads((output / "report.json").read_text()) == report
    assert report["validation"]["passed"]


def test_prepared_report_matches_previous_combiner_publication_exactly(
    tmp_path, batches, monkeypatch
):
    request, plan, requests, results = batches
    writes = []

    def record(path, value):
        if path.name == "report.json":
            writes.append(path)
        write_json(path, value)

    monkeypatch.setattr(population, "write_json", record)
    monkeypatch.setattr(prepared, "write_json", record)
    # The previous prepared path called the standalone combiner and discarded
    # its intermediate embedded-report tree after independently auditing rows.
    baseline = replace(request, output_dir=tmp_path / "baseline")
    with monkeypatch.context() as patch:
        patch.setattr(
            prepared, "_combine_population_files", population.combine_populations
        )
        prepared._publish_population(baseline, plan, requests, results, None)
    assert writes.count(baseline.output_dir / "report.json") == 2
    reads = []
    original_read = Path.read_text
    source_reports = {r.report_path for r in results}

    def read(path, *args, **kwargs):
        if path in source_reports:
            reads.append(path)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    optimized = replace(request, output_dir=tmp_path / "optimized")
    prepared._publish_population(optimized, plan, requests, results, None)
    assert reads == []
    assert writes.count(optimized.output_dir / "report.json") == 1
    for name in (
        "households.csv",
        "persons.csv",
        "manifest.json",
        "report.json",
        "realized-control-audit.json",
        "realized-control-residuals.csv",
    ):
        assert (optimized.output_dir / name).read_bytes() == (
            baseline.output_dir / name
        ).read_bytes()


def test_single_batch_does_not_copy_discarded_source_report(
    tmp_path, batches, monkeypatch
):
    import shutil

    request, plan, requests, results = batches
    source = results[0]
    copied = []
    original_copy = shutil.copyfile

    def copy(src, dst, *args, **kwargs):
        copied.append(Path(src).name)
        return original_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copyfile", copy)
    request.output_dir.mkdir()
    result = prepared._publish_population(
        request, plan, requests[:1], results[:1], None
    )
    assert copied == ["households.csv", "persons.csv", "manifest.json"]
    assert result.details["geographies"] == source.details["geographies"]
    assert result.details["validation"]["passed"]
    assert result.details["realized_control_audit"]["max_abs_error"] == 0
    assert (request.output_dir / "report.json").is_file()


@pytest.mark.parametrize("failure_stage", ["audit", "manifest-rename"])
def test_prepared_failure_leaves_final_artifacts_unpublished(
    batches, monkeypatch, failure_stage
):
    request, plan, requests, results = batches
    monkeypatch.setattr(prepared, "_read_plan", lambda _: plan)
    monkeypatch.setattr(prepared, "_prepare_batches", lambda *_: requests)
    monkeypatch.setattr(prepared, "_fit_batches", lambda *_: results)

    def fail_audit(*_):
        assert not (request.output_dir / "households.csv").exists()
        assert not (request.output_dir / "manifest.json").exists()
        raise ValueError("test audit failure")

    original_rename = Path.rename

    def fail_manifest_rename(path, destination):
        if destination == request.output_dir / "manifest.json":
            # Other artifacts have already been installed at this boundary.
            assert (request.output_dir / "households.csv").is_file()
            assert (request.output_dir / "persons.csv").is_file()
            raise OSError("test manifest rename failure")
        return original_rename(path, destination)

    if failure_stage == "audit":
        monkeypatch.setattr(prepared, "audit_population", fail_audit)
        error, message = ValueError, "test audit failure"
    else:
        monkeypatch.setattr(Path, "rename", fail_manifest_rename)
        error, message = OSError, "test manifest rename failure"

    with pytest.raises(error, match=message):
        prepared.calibrate_prepared_controls(request)

    assert {path.name for path in request.output_dir.iterdir()} == {"workflow.json"}
    status = json.loads((request.output_dir / "workflow.json").read_text())
    assert status["status"] == "failed"
