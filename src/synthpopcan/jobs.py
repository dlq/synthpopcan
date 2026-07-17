"""Single-process local job runner for durable SynthPopCan runs."""

from __future__ import annotations

__all__ = ["JobManager"]

import multiprocessing
import queue
import threading
from pathlib import Path
from typing import Any

from synthpopcan.runs import RunStore, publish_artifact
from synthpopcan.workflows.ipf import fit_ipf_files
from synthpopcan.workflows.types import IPFFitRequest, WorkflowProgress


class _WorkerCancelled(RuntimeError):
    pass


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
            ),
            publish_artifact(
                root,
                work_report,
                final_report,
                logical_name="fit_report",
                media_type="application/json",
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


class JobManager:
    """Run at most one spawned local synthesis process at a time."""

    def __init__(
        self,
        store: RunStore,
        *,
        worker_target=_ipf_worker,
        cancel_grace_seconds: float = 1.0,
    ) -> None:
        self.store = store
        self._worker_target = worker_target
        self._cancel_grace_seconds = cancel_grace_seconds
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
        while process.is_alive():
            terminal_message = (
                self._drain_messages(run_id, messages) or terminal_message
            )
            process.join(timeout=0.05)
        process.join()
        terminal_message = (
            self._drain_messages(run_id, messages, wait_seconds=0.2) or terminal_message
        )
        manifest = self.store.load_run(run_id)
        if not terminal_message:
            if manifest["status"] == "cancelling":
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
