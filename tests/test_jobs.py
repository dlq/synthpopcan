from __future__ import annotations

import csv
import json
import queue
import threading
import time
from pathlib import Path

from synthpopcan.jobs import JobManager, _ipf_worker, _model_worker, _small_area_worker
from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore


def cooperative_slow_worker(workspace, run_id, manifest, messages, cancel_event):
    messages.put(
        {
            "type": "progress",
            "event": {
                "stage": "working",
                "message": "Working slowly",
                "completed": None,
                "total": None,
            },
        }
    )
    while not cancel_event.wait(0.01):
        pass
    messages.put({"type": "cancelled"})


def failing_after_progress_worker(workspace, run_id, manifest, messages, cancel_event):
    messages.put(
        {
            "type": "progress",
            "event": {
                "stage": "fitting",
                "message": "Fit started",
                "completed": None,
                "total": None,
            },
        }
    )
    messages.put(
        {
            "type": "failed",
            "error": {"kind": "TestFailure", "message": "failure during work"},
        }
    )


def test_job_manager_runs_ipf_and_publishes_only_completed_artifacts(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    manager = JobManager(store)
    try:
        manager.enqueue(run_id)
        manifest = wait_for_terminal(store, run_id)
    finally:
        manager.shutdown()

    assert manifest["status"] == "succeeded"
    assert manifest["summary"]["converged"] is True
    assert {item["logical_name"] for item in manifest["artifacts"]} == {
        "weights",
        "fit_report",
    }
    weights = next(
        item for item in manifest["artifacts"] if item["logical_name"] == "weights"
    )
    rows = list(csv.DictReader(store.resolve_managed_path(weights["path"]).open()))
    assert len(rows) == 4
    assert not any((store.run_dir(run_id) / "work").iterdir())
    assert store.read_events(run_id)[-1]["stage"] == "succeeded"


def test_job_manager_records_worker_failure_without_artifacts(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    seed = write_upload(store, "seed.csv", b"id,age\n1,young\n")
    controls = write_upload(store, "controls.csv", b"not,controls\n1,2\n")
    run_id = str(store.create_ipf_run(ipf_request(seed, controls))["run_id"])
    manager = JobManager(store)
    try:
        manager.enqueue(run_id)
        manifest = wait_for_terminal(store, run_id)
    finally:
        manager.shutdown()

    assert manifest["status"] == "failed"
    assert manifest["artifacts"] == []
    assert manifest["error"]["message"]


def test_job_manager_records_failure_after_work_starts(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    manager = JobManager(store, worker_target=failing_after_progress_worker)
    try:
        manager.enqueue(run_id)
        manifest = wait_for_terminal(store, run_id)
    finally:
        manager.shutdown()

    assert manifest["status"] == "failed"
    assert manifest["error"] == {
        "kind": "TestFailure",
        "message": "failure during work",
    }
    assert manifest["artifacts"] == []
    stages = [event["stage"] for event in store.read_events(run_id)]
    assert "fitting" in stages
    assert stages[-1] == "failed"


def test_job_manager_cancels_running_worker(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    manager = JobManager(
        store,
        worker_target=cooperative_slow_worker,
        cancel_grace_seconds=0.2,
    )
    try:
        manager.enqueue(run_id)
        wait_for_status(store, run_id, "running")
        manager.cancel(run_id)
        manifest = wait_for_terminal(store, run_id)
    finally:
        manager.shutdown()

    assert manifest["status"] == "cancelled"
    assert manifest["artifacts"] == []
    stages = [event["stage"] for event in store.read_events(run_id)]
    assert "cancelling" in stages
    assert stages[-1] == "cancelled"


def test_job_manager_terminates_worker_after_run_timeout(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    manager = JobManager(
        store,
        worker_target=cooperative_slow_worker,
        max_run_seconds=0.05,
    )

    try:
        manager.enqueue(run_id)
        manifest = wait_for_terminal(store, run_id)
    finally:
        manager.shutdown()

    assert manifest["status"] == "failed"
    assert manifest["error"]["kind"] == "WorkerTimeout"
    assert store.read_events(run_id)[-1]["message"] == "Worker timed out"


def test_job_manager_cancels_queued_run_without_starting_worker(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    manager = JobManager(store)

    manifest = manager.cancel(run_id)

    assert manifest["status"] == "cancelled"
    assert store.read_events(run_id)[-1]["stage"] == "cancelled"


def test_ipf_worker_contract_is_covered_in_process(tmp_path: Path) -> None:
    """Exercise the spawned target directly so coverage includes its contract."""
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    messages: queue.SimpleQueue = queue.SimpleQueue()

    _ipf_worker(
        str(store.root),
        run_id,
        store.load_run(run_id),
        messages,
        threading.Event(),
    )

    emitted = []
    while not messages.empty():
        emitted.append(messages.get())
    assert emitted[-1]["type"] == "succeeded"
    assert emitted[-1]["summary"] == {
        "converged": True,
        "iterations": 1,
        "max_abs_error": 0.0,
        "seed_records": 4,
    }
    assert {item["logical_name"] for item in emitted[-1]["artifacts"]} == {
        "weights",
        "fit_report",
    }


def test_ipf_worker_contract_reports_immediate_cancellation(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = create_valid_run(store)
    messages: queue.SimpleQueue = queue.SimpleQueue()
    cancelled = threading.Event()
    cancelled.set()

    _ipf_worker(
        str(store.root),
        run_id,
        store.load_run(run_id),
        messages,
        cancelled,
    )

    assert messages.get()["type"] == "cancelled"


def test_model_worker_medium_scale_uses_durable_artifact_path(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.create_model_run(
        {
            "workflow": "model",
            "inputs": {"model_id": "demo-linked-household-person"},
            "options": {
                "households": 5_000,
                "conditions": {"geo": "Demo North"},
                "random_seed": 13,
                "chunk_size": 257,
            },
        }
    )
    messages: queue.SimpleQueue = queue.SimpleQueue()

    _model_worker(
        str(store.root),
        str(run["run_id"]),
        run,
        messages,
        threading.Event(),
    )

    emitted = []
    while not messages.empty():
        emitted.append(messages.get())
    succeeded = emitted[-1]
    assert succeeded["type"] == "succeeded"
    assert succeeded["summary"]["generated_households"] == 5_000
    assert succeeded["summary"]["linked_validation_passed"] is True
    assert {artifact["logical_name"] for artifact in succeeded["artifacts"]} == {
        "households",
        "persons",
        "generation_report",
    }
    for artifact in succeeded["artifacts"]:
        assert store.resolve_managed_path(artifact["path"]).is_file()
        assert len(artifact["sha256"]) == 64


def test_small_area_worker_contract_is_covered_in_process(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    package = write_upload(
        store,
        "package.json",
        json.dumps(model_payload("demo-linked-household-person")).encode(),
    )
    controls = write_upload(
        store,
        "controls.csv",
        (
            b"margin,dimensions,tract,tenure,count\n"
            b'tenure,"tract,tenure",001,owner,2\n'
            b'tenure,"tract,tenure",001,renter,1\n'
            b'tenure,"tract,tenure",002,owner,2\n'
            b'tenure,"tract,tenure",002,renter,1\n'
        ),
    )
    boundaries = write_upload(
        store,
        "boundaries.geojson",
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": geography},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [offset, 0],
                                    [offset + 0.5, 0],
                                    [offset + 0.5, 0.5],
                                    [offset, 0.5],
                                    [offset, 0],
                                ]
                            ],
                        },
                    }
                    for geography, offset in (("001", 0), ("002", 1))
                ],
            }
        ).encode(),
    )
    run = store.create_small_area_run(
        {
            "workflow": "small_area",
            "inputs": {
                "package_upload_id": package,
                "controls_upload_id": controls,
                "boundaries_upload_id": boundaries,
            },
            "options": {
                "candidate_households": 20,
                "geography_dimension": "tract",
                "geography_column": "tract",
                "conditions": {"geo": "Demo North"},
                "random_seed": 13,
                "pool_size": 20,
                "subsample_seed": 7,
                "chunk_size": 3,
                "include_weights": True,
            },
        }
    )
    messages: queue.SimpleQueue = queue.SimpleQueue()

    _small_area_worker(
        str(store.root),
        str(run["run_id"]),
        run,
        messages,
        threading.Event(),
    )

    emitted = []
    while not messages.empty():
        emitted.append(messages.get())
    succeeded = emitted[-1]
    assert succeeded["type"] == "succeeded"
    assert succeeded["summary"]["assigned_households"] == 6
    assert succeeded["summary"]["total_geographies"] == 2
    assert succeeded["summary"]["non_converged_count"] == 0
    assert {artifact["logical_name"] for artifact in succeeded["artifacts"]} == {
        "households",
        "persons",
        "small_area_report",
        "weights",
        "map",
    }
    assert "geo synthesize" in succeeded["reproduction"]["shell"]


def test_small_area_worker_accepts_existing_linked_candidates(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    households = write_upload(
        store,
        "households.csv",
        (b"synthetic_household_id,household_size,tenure\nh1,1,owner\nh2,1,renter\n"),
    )
    persons = write_upload(
        store,
        "persons.csv",
        (b"synthetic_person_id,synthetic_household_id,sex\np1,h1,F\np2,h2,M\n"),
    )
    controls = write_upload(
        store,
        "controls.csv",
        (
            b"margin,dimensions,tract,tenure,count\n"
            b'tenure,"tract,tenure",001,owner,1\n'
            b'tenure,"tract,tenure",001,renter,1\n'
        ),
    )
    run = store.create_small_area_run(
        {
            "workflow": "small_area",
            "inputs": {
                "candidate_households_upload_id": households,
                "candidate_persons_upload_id": persons,
                "controls_upload_id": controls,
            },
            "options": {
                "candidate_households": 2,
                "geography_dimension": "tract",
                "geography_column": "tract",
                "subsample_seed": 7,
            },
        }
    )
    messages: queue.SimpleQueue = queue.SimpleQueue()

    _small_area_worker(
        str(store.root),
        str(run["run_id"]),
        run,
        messages,
        threading.Event(),
    )

    emitted = []
    while not messages.empty():
        emitted.append(messages.get())
    succeeded = emitted[-1]
    assert succeeded["type"] == "succeeded"
    assert succeeded["summary"]["assigned_households"] == 2
    assert succeeded["summary"]["assigned_persons"] == 2
    assert "geo calibrate" in succeeded["reproduction"]["shell"]
    assert "inputs" in succeeded["reproduction"]["shell"]


def create_valid_run(store: RunStore) -> str:
    seed = write_upload(
        store,
        "seed.csv",
        (b"id,age,sex\n1,young,F\n2,young,M\n3,old,F\n4,old,M\n"),
    )
    controls = write_upload(
        store,
        "controls.csv",
        (
            b"margin,dimensions,age,sex,count\n"
            b"age,age,young,,60\n"
            b"age,age,old,,40\n"
            b"sex,sex,,F,50\n"
            b"sex,sex,,M,50\n"
        ),
    )
    return str(store.create_ipf_run(ipf_request(seed, controls))["run_id"])


def wait_for_terminal(store: RunStore, run_id: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        manifest = store.load_run(run_id)
        if manifest["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return manifest
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def wait_for_status(
    store: RunStore, run_id: str, expected: str, timeout: float = 5
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if store.load_run(run_id)["status"] == expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"run {run_id} did not reach {expected}")


def write_upload(store: RunStore, name: str, body: bytes) -> str:
    writer = store.begin_upload(name, max_bytes=len(body))
    writer.write(body)
    return str(writer.finish()["upload_id"])


def ipf_request(seed_upload_id: str, controls_upload_id: str) -> dict:
    return {
        "workflow": "ipf",
        "inputs": {
            "seed_upload_id": seed_upload_id,
            "controls_upload_id": controls_upload_id,
        },
        "options": {},
    }
