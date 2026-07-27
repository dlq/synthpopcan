"""Single-process local job runner for durable SynthPopCan runs."""

from __future__ import annotations

__all__ = ["JobManager"]

import json
import multiprocessing
import queue
import threading
import time
from pathlib import Path
from typing import Any

from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore, publish_artifact
from synthpopcan.workflows.ipf import fit_ipf_files
from synthpopcan.workflows.models import (
    LOCAL_RUN_MAX_HOUSEHOLDS,
    LOCAL_RUN_MAX_PERSONS,
    PreparedModelRequest,
    generate_prepared_model_files,
)
from synthpopcan.workflows.small_area import (
    SmallAreaRequest,
    synthesize_small_area_files,
)
from synthpopcan.workflows.types import IPFFitRequest, WorkflowProgress


class _WorkerCancelled(RuntimeError):
    pass


def _workflow_worker(workspace, run_id, manifest, messages, cancel_event) -> None:
    """Dispatch a durable manifest to its file-backed workflow."""
    if manifest.get("workflow") == "ipf":
        _ipf_worker(workspace, run_id, manifest, messages, cancel_event)
        return
    if manifest.get("workflow") == "model":
        _model_worker(workspace, run_id, manifest, messages, cancel_event)
        return
    if manifest.get("workflow") == "small_area":
        _small_area_worker(workspace, run_id, manifest, messages, cancel_event)
        return
    messages.put(
        {
            "type": "failed",
            "error": {
                "kind": "ValueError",
                "message": f"unsupported workflow {manifest.get('workflow')!r}",
            },
        }
    )


def _ipf_worker(
    workspace: str,
    run_id: str,
    manifest: dict[str, Any],
    messages,
    cancel_event,
) -> None:
    """Execute one IPF workflow in an isolated spawned process."""
    root = Path(workspace)
    run_dir = root / "runs" / run_id
    input_paths = {
        str(item["logical_name"]): root / str(item["path"])
        for item in manifest["inputs"]
    }
    work_dir = run_dir / "work"
    artifact_dir = run_dir / "artifacts"
    work_weights = work_dir / "weights.csv"
    work_report = work_dir / "fit-report.json"
    options = manifest["request"].get("options", {})

    def progress(event: WorkflowProgress) -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled
        messages.put({"type": "progress", "event": event.as_dict()})

    def check_cancelled() -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled

    try:
        result = fit_ipf_files(
            IPFFitRequest(
                seed_path=input_paths["seed"],
                controls_path=input_paths["controls"],
                output_path=work_weights,
                weight_column=options.get("weight_column"),
                max_iterations=int(options.get("max_iterations", 100)),
                tolerance=float(options.get("tolerance", 1e-6)),
                allow_nonconverged=bool(options.get("allow_nonconverged", False)),
                report_path=work_report,
                seed_reference="inputs/seed.csv",
                controls_reference="inputs/controls.csv",
                output_reference="reproduced-weights.csv",
                report_reference="reproduced-fit-report.json",
            ),
            progress=progress,
        )
        if cancel_event.is_set():
            raise _WorkerCancelled
        final_weights = artifact_dir / "weights.csv"
        final_report = artifact_dir / "fit-report.json"
        artifacts = [
            publish_artifact(
                root,
                work_weights,
                final_weights,
                logical_name="weights",
                media_type="text/csv",
                row_count=int(result.report["seed_records"]),
                cancel_check=check_cancelled,
            ),
            publish_artifact(
                root,
                work_report,
                final_report,
                logical_name="fit_report",
                media_type="application/json",
                cancel_check=check_cancelled,
            ),
        ]
        messages.put(
            {
                "type": "succeeded",
                "artifacts": artifacts,
                "summary": {
                    "converged": result.report["converged"],
                    "iterations": result.report["iterations"],
                    "max_abs_error": result.report["max_abs_error"],
                    "seed_records": result.report["seed_records"],
                },
                "reproduction": result.reproduction.as_dict(),
            }
        )
    except _WorkerCancelled:
        messages.put({"type": "cancelled"})
    except Exception as exc:  # noqa: BLE001
        messages.put(
            {
                "type": "failed",
                "error": {"kind": type(exc).__name__, "message": str(exc)},
            }
        )


def _model_worker(
    workspace: str,
    run_id: str,
    manifest: dict[str, Any],
    messages,
    cancel_event,
) -> None:
    """Execute prepared-model generation in the spawned worker."""
    root = Path(workspace)
    run_dir = root / "runs" / run_id
    work_dir = run_dir / "work"
    artifact_dir = run_dir / "artifacts"
    inputs = manifest["request"]["inputs"]
    options = manifest["request"].get("options", {})
    package_reference: str
    if inputs.get("model_id"):
        package_reference = str(inputs["model_id"])
        package_path = work_dir / "package.json"
        package_path.write_text(json.dumps(model_payload(package_reference)))
    else:
        package_reference = "inputs/package.json"
        package_path = run_dir / "inputs" / "package.json"

    def progress(event: WorkflowProgress) -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled
        messages.put({"type": "progress", "event": event.as_dict()})

    def check_cancelled() -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled

    try:
        result = generate_prepared_model_files(
            PreparedModelRequest(
                package_path=package_path,
                households_path=work_dir / "households.csv",
                persons_path=work_dir / "persons.csv",
                report_path=work_dir / "generation-report.json",
                households=int(options.get("households", 10)),
                conditions=dict(options.get("conditions", {})),
                random_seed=options.get("random_seed"),
                household_size_column=options.get("household_size_column"),
                package_reference=package_reference,
                chunk_size=int(options.get("chunk_size", 1000)),
                max_households=LOCAL_RUN_MAX_HOUSEHOLDS,
                max_persons=LOCAL_RUN_MAX_PERSONS,
                output_dir_reference="reproduced",
            ),
            progress=progress,
        )
        if cancel_event.is_set():
            raise _WorkerCancelled
        artifacts = [
            publish_artifact(
                root,
                result.households_path,
                artifact_dir / "households.csv",
                logical_name="households",
                media_type="text/csv",
                row_count=result.household_count,
                cancel_check=check_cancelled,
            ),
            publish_artifact(
                root,
                result.persons_path,
                artifact_dir / "persons.csv",
                logical_name="persons",
                media_type="text/csv",
                row_count=result.person_count,
                cancel_check=check_cancelled,
            ),
            publish_artifact(
                root,
                result.report_path,
                artifact_dir / "generation-report.json",
                logical_name="generation_report",
                media_type="application/json",
                cancel_check=check_cancelled,
            ),
        ]
        messages.put(
            {
                "type": "succeeded",
                "artifacts": artifacts,
                "summary": {
                    "generated_households": result.household_count,
                    "generated_persons": result.person_count,
                    "linked_validation_passed": result.report["validation"]["passed"],
                    "package": result.report["package"],
                },
                "reproduction": result.reproduction.as_dict(),
            }
        )
    except _WorkerCancelled:
        messages.put({"type": "cancelled"})
    except Exception as exc:  # noqa: BLE001
        messages.put(
            {
                "type": "failed",
                "error": {"kind": type(exc).__name__, "message": str(exc)},
            }
        )


def _small_area_worker(
    workspace: str,
    run_id: str,
    manifest: dict[str, Any],
    messages,
    cancel_event,
) -> None:
    """Execute linked generation and small-area calibration in one worker."""
    root = Path(workspace)
    run_dir = root / "runs" / run_id
    work_dir = run_dir / "work"
    artifact_dir = run_dir / "artifacts"
    request_inputs = manifest["request"]["inputs"]
    options = manifest["request"].get("options", {})
    input_paths = {
        str(item["logical_name"]): root / str(item["path"])
        for item in manifest["inputs"]
    }
    package_reference: str | None
    package_path: Path | None
    if request_inputs.get("model_id"):
        package_reference = str(request_inputs["model_id"])
        package_path = work_dir / "package.json"
        package_path.write_text(json.dumps(model_payload(package_reference)))
    elif request_inputs.get("package_upload_id"):
        package_reference = "inputs/package.json"
        package_path = input_paths["package"]
    else:
        package_reference = None
        package_path = None

    def progress(event: WorkflowProgress) -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled
        messages.put({"type": "progress", "event": event.as_dict()})

    def check_cancelled() -> None:
        if cancel_event.is_set():
            raise _WorkerCancelled

    try:
        result = synthesize_small_area_files(
            SmallAreaRequest(
                package_path=package_path,
                controls_path=input_paths["controls"],
                person_controls_path=input_paths.get("person_controls"),
                candidates_dir=work_dir / "candidates",
                output_dir=work_dir / "output",
                candidate_households=int(options.get("candidate_households", 10_000)),
                geography_dimension=str(options["geography_dimension"]),
                geography_column=str(
                    options.get("geography_column") or options["geography_dimension"]
                ),
                conditions=dict(options.get("conditions", {})),
                package_reference=package_reference,
                candidate_households_path=input_paths.get("candidate_households"),
                candidate_persons_path=input_paths.get("candidate_persons"),
                random_seed=options.get("random_seed"),
                pool_size=options.get("pool_size"),
                subsample_seed=int(options.get("subsample_seed", 42)),
                max_household_size=options.get("max_household_size"),
                household_size_group_column=str(
                    options.get("household_size_group_column", "household_size_group")
                ),
                include_weights=bool(options.get("include_weights", False)),
                chunk_size=int(options.get("chunk_size", 1000)),
                boundaries_path=input_paths.get("boundaries"),
                map_path=(
                    work_dir / "output" / "map.html"
                    if "boundaries" in input_paths
                    else None
                ),
                geography_id_field=str(options.get("geography_id_field", "geo_id")),
                map_title=str(options.get("map_title", "Synthetic Population")),
                max_candidate_households=LOCAL_RUN_MAX_HOUSEHOLDS,
                max_candidate_persons=LOCAL_RUN_MAX_PERSONS,
                controls_reference="inputs/controls.csv",
                person_controls_reference=(
                    "inputs/person-controls.csv"
                    if "person_controls" in input_paths
                    else None
                ),
                candidate_households_reference=(
                    "inputs/households.csv"
                    if "candidate_households" in input_paths
                    else None
                ),
                candidate_persons_reference=(
                    "inputs/persons.csv" if "candidate_persons" in input_paths else None
                ),
                boundaries_reference=(
                    "inputs/boundaries.geojson" if "boundaries" in input_paths else None
                ),
                output_dir_reference="reproduced",
            ),
            progress=progress,
        )
        check_cancelled()
        artifacts = [
            publish_artifact(
                root,
                result.households_path,
                artifact_dir / "households.csv",
                logical_name="households",
                media_type="text/csv",
                row_count=int(result.details["assigned_households"]),
                cancel_check=check_cancelled,
            ),
            publish_artifact(
                root,
                result.persons_path,
                artifact_dir / "persons.csv",
                logical_name="persons",
                media_type="text/csv",
                row_count=int(result.details["assigned_persons"]),
                cancel_check=check_cancelled,
            ),
            publish_artifact(
                root,
                result.report_path,
                artifact_dir / "report.json",
                logical_name="small_area_report",
                media_type="application/json",
                cancel_check=check_cancelled,
            ),
        ]
        if result.weights_path is not None:
            artifacts.append(
                publish_artifact(
                    root,
                    result.weights_path,
                    artifact_dir / "weights.csv",
                    logical_name="weights",
                    media_type="text/csv",
                    cancel_check=check_cancelled,
                )
            )
        if result.map_path is not None:
            artifacts.append(
                publish_artifact(
                    root,
                    result.map_path,
                    artifact_dir / "map.html",
                    logical_name="map",
                    media_type="text/html",
                    cancel_check=check_cancelled,
                )
            )
        summary = result.details["summary"]
        messages.put(
            {
                "type": "succeeded",
                "artifacts": artifacts,
                "summary": {
                    "assigned_households": result.details["assigned_households"],
                    "assigned_persons": result.details["assigned_persons"],
                    "total_geographies": summary["total_geographies"],
                    "non_converged_count": summary["non_converged_count"],
                    "max_abs_error": summary["max_abs_error"],
                    "realized_max_abs_error": summary["realized_max_abs_error"],
                    "largest_residuals": summary["largest_residuals"],
                    "suggested_next_steps": result.details["suggested_next_steps"],
                    "calibration_mode": result.details["calibration_mode"],
                },
                "reproduction": result.reproduction.as_dict(),
            }
        )
    except _WorkerCancelled:
        messages.put({"type": "cancelled"})
    except Exception as exc:  # noqa: BLE001
        messages.put(
            {
                "type": "failed",
                "error": {"kind": type(exc).__name__, "message": str(exc)},
            }
        )


class JobManager:
    """Run at most one spawned local synthesis process at a time."""

    def __init__(
        self,
        store: RunStore,
        *,
        worker_target=None,
        cancel_grace_seconds: float = 1.0,
        max_run_seconds: float | None = 6 * 60 * 60,
    ) -> None:
        self.store = store
        self._worker_target = worker_target or _workflow_worker
        self._cancel_grace_seconds = cancel_grace_seconds
        if max_run_seconds is not None and max_run_seconds <= 0:
            raise ValueError("maximum run seconds must be positive")
        self._max_run_seconds = max_run_seconds
        self._context = multiprocessing.get_context("spawn")
        self._pending: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._current_run_id: str | None = None
        self._current_process = None
        self._current_cancel = None

    def start(self) -> None:
        """Start the dispatcher thread once."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopping.clear()
            self._thread = threading.Thread(
                target=self._dispatch,
                name="synthpopcan-job-dispatcher",
                daemon=True,
            )
            self._thread.start()

    def enqueue(self, run_id: str) -> None:
        """Queue a previously created durable run."""
        manifest = self.store.load_run(run_id)
        if manifest["status"] != "queued":
            raise ValueError("only queued runs can be enqueued")
        self.start()
        self._pending.put(run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel a queued or running run, terminating after a short grace period."""
        with self._lock:
            manifest = self.store.load_run(run_id)
            status = str(manifest["status"])
            if status == "queued":
                self.store.transition_run(run_id, "cancelled")
                self.store.append_event(run_id, "cancelled", "Queued run cancelled")
                return self.store.load_run(run_id)
            if status != "running":
                raise ValueError(f"run in state {status} cannot be cancelled")
            self.store.transition_run(run_id, "cancelling")
            self.store.append_event(run_id, "cancelling", "Cancellation requested")
            if self._current_run_id == run_id and self._current_cancel is not None:
                self._current_cancel.set()
                timer = threading.Timer(
                    self._cancel_grace_seconds,
                    self._force_cancel,
                    args=(run_id,),
                )
                timer.daemon = True
                timer.start()
            return self.store.load_run(run_id)

    def shutdown(self) -> None:
        """Stop dispatching and terminate any active worker."""
        self._stopping.set()
        self._pending.put(None)
        with self._lock:
            process = self._current_process
            run_id = self._current_run_id
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if run_id is not None:
                manifest = self.store.load_run(run_id)
                if manifest["status"] in {"running", "cancelling"}:
                    self.store.transition_run(run_id, "interrupted")
                    self.store.append_event(
                        run_id, "interrupted", "Job manager shut down"
                    )
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _dispatch(self) -> None:
        while not self._stopping.is_set():
            run_id = self._pending.get()
            if run_id is None:
                return
            try:
                if self.store.load_run(run_id)["status"] != "queued":
                    continue
                self._run_one(run_id)
            except Exception as exc:  # noqa: BLE001
                manifest = self.store.load_run(run_id)
                if manifest["status"] == "queued":
                    self.store.transition_run(
                        run_id,
                        "failed",
                        error={"kind": type(exc).__name__, "message": str(exc)},
                    )
                    self.store.append_event(run_id, "failed", str(exc))

    def _run_one(self, run_id: str) -> None:
        manifest = self.store.transition_run(run_id, "running")
        self.store.append_event(run_id, "running", "Worker process started")
        messages = self._context.Queue()
        cancel_event = self._context.Event()
        process = self._context.Process(
            target=self._worker_target,
            args=(str(self.store.root), run_id, manifest, messages, cancel_event),
            name=f"synthpopcan-{run_id}",
        )
        with self._lock:
            self._current_run_id = run_id
            self._current_process = process
            self._current_cancel = cancel_event
        process.start()
        terminal_message = False
        timed_out = False
        deadline = (
            time.monotonic() + self._max_run_seconds
            if self._max_run_seconds is not None
            else None
        )
        while process.is_alive():
            terminal_message = (
                self._drain_messages(run_id, messages) or terminal_message
            )
            if (
                not terminal_message
                and deadline is not None
                and time.monotonic() >= deadline
            ):
                timed_out = True
                process.terminate()
                break
            process.join(timeout=0.05)
        process.join()
        terminal_message = (
            self._drain_messages(run_id, messages, wait_seconds=0.2) or terminal_message
        )
        manifest = self.store.load_run(run_id)
        if not terminal_message:
            if timed_out and manifest["status"] == "running":
                self.store.transition_run(
                    run_id,
                    "failed",
                    error={
                        "kind": "WorkerTimeout",
                        "message": (
                            "Worker exceeded the local run time limit of "
                            f"{self._max_run_seconds:g} seconds"
                        ),
                    },
                )
                self.store.append_event(run_id, "failed", "Worker timed out")
            elif manifest["status"] == "cancelling":
                self._finish_cancelled(run_id)
            elif manifest["status"] == "running":
                self.store.transition_run(
                    run_id,
                    "failed",
                    error={
                        "kind": "WorkerExit",
                        "message": f"Worker exited with code {process.exitcode}",
                    },
                )
                self.store.append_event(run_id, "failed", "Worker exited unexpectedly")
        with self._lock:
            self._current_run_id = None
            self._current_process = None
            self._current_cancel = None

    def _drain_messages(
        self, run_id: str, messages, *, wait_seconds: float = 0
    ) -> bool:
        terminal = False
        first_message = True
        while True:
            try:
                if first_message and wait_seconds > 0:
                    message = messages.get(timeout=wait_seconds)
                else:
                    message = messages.get_nowait()
            except queue.Empty:
                return terminal
            first_message = False
            message_type = message["type"]
            if message_type == "progress":
                event = message["event"]
                self.store.append_event(
                    run_id,
                    str(event["stage"]),
                    str(event["message"]),
                    completed=event.get("completed"),
                    total=event.get("total"),
                )
            elif message_type == "succeeded":
                self.store.transition_run(
                    run_id,
                    "succeeded",
                    artifacts=message["artifacts"],
                    summary=message["summary"],
                    reproduction=message["reproduction"],
                )
                self.store.append_event(run_id, "succeeded", "Run completed")
                terminal = True
            elif message_type == "failed":
                self.store.transition_run(run_id, "failed", error=message["error"])
                self.store.append_event(
                    run_id, "failed", str(message["error"]["message"])
                )
                terminal = True
            elif message_type == "cancelled":
                self._finish_cancelled(run_id)
                terminal = True

    def _finish_cancelled(self, run_id: str) -> None:
        manifest = self.store.load_run(run_id)
        if manifest["status"] == "running":
            self.store.transition_run(run_id, "cancelling")
        if self.store.load_run(run_id)["status"] == "cancelling":
            self.store.transition_run(run_id, "cancelled")
            self.store.append_event(run_id, "cancelled", "Run cancelled")

    def _force_cancel(self, run_id: str) -> None:
        with self._lock:
            if self._current_run_id != run_id:
                return
            process = self._current_process
            if process is not None and process.is_alive():
                process.terminate()
