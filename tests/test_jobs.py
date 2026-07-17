from __future__ import annotations

import csv
import queue
import threading
import time
from pathlib import Path

from synthpopcan.jobs import JobManager, _ipf_worker
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
