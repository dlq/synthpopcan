"""Durable local workspace, upload, run-manifest, and artifact storage."""

from __future__ import annotations

__all__ = [
    "RUN_SCHEMA_VERSION",
    "RunStore",
    "UploadWriter",
    "publish_artifact",
]

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from synthpopcan import __version__
from synthpopcan._runtime_schemas import RunEvent, RunManifest, UploadMetadata
from synthpopcan.assurance import build_run_assurance, verify_run_assurance

RUN_SCHEMA_VERSION = "synthpopcan-run-v1"
_OPAQUE_ID = re.compile(r"^[a-f0-9]{32}$")
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$")
_TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class UploadWriter:
    """Bounded incremental upload writer that hashes bytes while writing."""

    def __init__(
        self,
        store: RunStore,
        *,
        upload_id: str,
        display_name: str,
        media_type: str,
        max_bytes: int,
    ) -> None:
        self._store = store
        self.upload_id = upload_id
        self.display_name = display_name
        self.media_type = media_type
        self.max_bytes = max_bytes
        self.byte_size: int = 0
        self._digest = hashlib.sha256()
        self._temporary_path = store.uploads_dir / f".{upload_id}.part"
        self._final_path = store.uploads_dir / f"{upload_id}.bin"
        self._handle: BinaryIO | None = self._temporary_path.open("xb")
        self._finished = False

    def write(self, chunk: bytes) -> None:
        """Write one chunk, rejecting uploads beyond the declared bound."""
        if self._handle is None:
            raise RuntimeError("upload writer is closed")
        next_size = self.byte_size + len(chunk)
        if next_size > self.max_bytes:
            raise ValueError(f"upload exceeds the {self.max_bytes}-byte size limit")
        self._handle.write(chunk)
        self._digest.update(chunk)
        self.byte_size = next_size

    def finish(self) -> dict[str, Any]:
        """Atomically publish the completed upload and return its metadata."""
        if self._handle is None or self._finished:
            raise RuntimeError("upload writer is already closed")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self._handle = None
        if self.byte_size == 0:
            self.abort()
            raise ValueError("upload is empty")
        os.replace(self._temporary_path, self._final_path)
        metadata = UploadMetadata(
            upload_id=self.upload_id,
            display_name=self.display_name,
            media_type=self.media_type,
            byte_size=self.byte_size,
            sha256=self._digest.hexdigest(),
            created_at=_utc_now(),
            claimed_by=None,
            path=str(self._final_path.relative_to(self._store.root)),
        ).model_dump()
        self._store._write_json_atomic(  # noqa: SLF001
            self._store.uploads_dir / f"{self.upload_id}.json", metadata
        )
        self._finished = True
        return metadata

    def abort(self) -> None:
        """Close and remove an incomplete upload."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        self._temporary_path.unlink(missing_ok=True)


class RunStore:
    """Own all files under one controlled local SynthPopCan workspace."""

    def __init__(self, root: Path) -> None:
        self.root: Path = root.resolve()
        self._lock = threading.RLock()
        uploads_dir = self.root / "uploads"
        runs_dir = self.root / "runs"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir = uploads_dir.resolve()
        self.runs_dir = runs_dir.resolve()
        if not self.uploads_dir.is_relative_to(self.root):
            raise ValueError("uploads directory escapes the workspace")
        if not self.runs_dir.is_relative_to(self.root):
            raise ValueError("runs directory escapes the workspace")
        self.recover_interrupted_runs()

    def begin_upload(
        self,
        display_name: str,
        *,
        media_type: str = "text/csv",
        max_bytes: int,
    ) -> UploadWriter:
        """Allocate an opaque upload and return its incremental writer."""
        if max_bytes <= 0:
            raise ValueError("upload size limit must be positive")
        upload_id = secrets.token_hex(16)
        return UploadWriter(
            self,
            upload_id=upload_id,
            display_name=_safe_display_name(display_name),
            media_type=media_type,
            max_bytes=max_bytes,
        )

    def get_upload(
        self,
        upload_id: str,
        *,
        require_unclaimed: bool = False,
    ) -> dict[str, Any]:
        """Return validated upload metadata without exposing arbitrary paths."""
        _validate_opaque_id(upload_id, "upload")
        metadata_path = self.uploads_dir / f"{upload_id}.json"
        try:
            metadata = UploadMetadata.model_validate(
                json.loads(metadata_path.read_text())
            ).model_dump()
        except FileNotFoundError as exc:
            raise KeyError(f"unknown upload {upload_id}") from exc
        if require_unclaimed and metadata.get("claimed_by") is not None:
            raise ValueError(f"upload {upload_id} has already been claimed")
        self.resolve_managed_path(str(metadata["path"]))
        return metadata

    def upload_path(self, upload_id: str, *, require_unclaimed: bool = False) -> Path:
        """Resolve an upload through its trusted metadata."""
        metadata = self.get_upload(upload_id, require_unclaimed=require_unclaimed)
        return self.resolve_managed_path(str(metadata["path"]))

    def create_ipf_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create an IPF run and atomically claim its two input uploads."""
        with self._lock:
            inputs = request.get("inputs")
            if not isinstance(inputs, dict):
                raise ValueError("IPF run inputs must be an object")
            seed_id = str(inputs.get("seed_upload_id", ""))
            controls_id = str(inputs.get("controls_upload_id", ""))
            if seed_id == controls_id:
                raise ValueError("seed and controls uploads must differ")
            seed = self.get_upload(seed_id, require_unclaimed=True)
            controls = self.get_upload(controls_id, require_unclaimed=True)
            run_id = _new_run_id()
            run_dir = self.run_dir(run_id)
            inputs_dir = run_dir / "inputs"
            for directory in (
                inputs_dir,
                run_dir / "artifacts",
                run_dir / "work",
            ):
                directory.mkdir(parents=True, exist_ok=False)
            claimed_metadata: list[dict[str, Any]] = []
            try:
                claimed_inputs = []
                for metadata, logical_name, filename in (
                    (seed, "seed", "seed.csv"),
                    (controls, "controls", "controls.csv"),
                ):
                    claimed_inputs.append(
                        self._claim_upload(
                            metadata,
                            run_id,
                            inputs_dir,
                            logical_name,
                            filename,
                        )
                    )
                    claimed_metadata.append(metadata)
                now = _utc_now()
                manifest: dict[str, Any] = {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "run_id": run_id,
                    "workflow": "ipf",
                    "status": "queued",
                    "created_at": now,
                    "started_at": None,
                    "finished_at": None,
                    "synthpopcan_version": __version__,
                    "request": request,
                    "random_seed": None,
                    "inputs": claimed_inputs,
                    "artifacts": [],
                    "summary": {},
                    "error": None,
                    "reproduction": None,
                    "assurance": None,
                }
                self._write_json_atomic(run_dir / "run.json", manifest)
                (run_dir / "events.ndjson").touch(exist_ok=False)
                self.append_event(run_id, "queued", "Run queued")
                return self.load_run(run_id)
            except Exception:
                for metadata in reversed(claimed_metadata):
                    self._release_upload_claim(metadata)
                shutil.rmtree(run_dir, ignore_errors=True)
                raise

    def create_model_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create a prepared-model run from a catalogue ID or package upload."""
        with self._lock:
            inputs = request.get("inputs")
            if not isinstance(inputs, dict):
                raise ValueError("model run inputs must be an object")
            model_id = inputs.get("model_id")
            package_upload_id = inputs.get("package_upload_id")
            if bool(model_id) == bool(package_upload_id):
                raise ValueError(
                    "model run requires exactly one model_id or package_upload_id"
                )
            upload = (
                self.get_upload(str(package_upload_id), require_unclaimed=True)
                if package_upload_id
                else None
            )
            run_id = _new_run_id()
            run_dir = self.run_dir(run_id)
            inputs_dir = run_dir / "inputs"
            for directory in (inputs_dir, run_dir / "artifacts", run_dir / "work"):
                directory.mkdir(parents=True, exist_ok=False)
            try:
                claimed_inputs = []
                if upload is not None:
                    claimed_inputs.append(
                        self._claim_upload(
                            upload,
                            run_id,
                            inputs_dir,
                            "package",
                            "package.json",
                        )
                    )
                now = _utc_now()
                manifest: dict[str, Any] = {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "run_id": run_id,
                    "workflow": "model",
                    "status": "queued",
                    "created_at": now,
                    "started_at": None,
                    "finished_at": None,
                    "synthpopcan_version": __version__,
                    "request": request,
                    "random_seed": request.get("options", {}).get("random_seed"),
                    "inputs": claimed_inputs,
                    "artifacts": [],
                    "summary": {},
                    "error": None,
                    "reproduction": None,
                    "assurance": None,
                }
                self._write_json_atomic(run_dir / "run.json", manifest)
                (run_dir / "events.ndjson").touch(exist_ok=False)
                self.append_event(run_id, "queued", "Run queued")
                return self.load_run(run_id)
            except Exception:
                if upload is not None and upload.get("claimed_by") == run_id:
                    self._release_upload_claim(upload)
                shutil.rmtree(run_dir, ignore_errors=True)
                raise

    def create_small_area_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create a small-area run and claim its package/control uploads."""
        with self._lock:
            inputs = request.get("inputs")
            if not isinstance(inputs, dict):
                raise ValueError("small-area run inputs must be an object")
            model_id = inputs.get("model_id")
            package_id = inputs.get("package_upload_id")
            candidate_households_id = inputs.get("candidate_households_upload_id")
            candidate_persons_id = inputs.get("candidate_persons_upload_id")
            has_model_source = bool(model_id) ^ bool(package_id)
            has_candidate_source = bool(candidate_households_id) and bool(
                candidate_persons_id
            )
            if bool(candidate_households_id) != bool(candidate_persons_id):
                raise ValueError(
                    "small-area candidate household and person uploads are both "
                    "required"
                )
            if has_model_source == has_candidate_source:
                raise ValueError(
                    "small-area run requires one model/package or one linked "
                    "candidate pair"
                )
            controls_id = str(inputs.get("controls_upload_id", ""))
            person_controls_id = inputs.get("person_controls_upload_id")
            upload_specs: list[tuple[dict[str, Any], str, str]] = []
            if package_id:
                upload_specs.append(
                    (
                        self.get_upload(str(package_id), require_unclaimed=True),
                        "package",
                        "package.json",
                    )
                )
            if candidate_households_id and candidate_persons_id:
                upload_specs.extend(
                    (
                        (
                            self.get_upload(
                                str(candidate_households_id), require_unclaimed=True
                            ),
                            "candidate_households",
                            "households.csv",
                        ),
                        (
                            self.get_upload(
                                str(candidate_persons_id), require_unclaimed=True
                            ),
                            "candidate_persons",
                            "persons.csv",
                        ),
                    )
                )
            upload_specs.append(
                (
                    self.get_upload(controls_id, require_unclaimed=True),
                    "controls",
                    "controls.csv",
                )
            )
            if person_controls_id:
                upload_specs.append(
                    (
                        self.get_upload(
                            str(person_controls_id), require_unclaimed=True
                        ),
                        "person_controls",
                        "person-controls.csv",
                    )
                )
            boundaries_id = inputs.get("boundaries_upload_id")
            if boundaries_id:
                upload_specs.append(
                    (
                        self.get_upload(str(boundaries_id), require_unclaimed=True),
                        "boundaries",
                        "boundaries.geojson",
                    )
                )
            upload_ids = [str(metadata["upload_id"]) for metadata, _, _ in upload_specs]
            if len(upload_ids) != len(set(upload_ids)):
                raise ValueError("small-area input uploads must differ")

            run_id = _new_run_id()
            run_dir = self.run_dir(run_id)
            inputs_dir = run_dir / "inputs"
            for directory in (inputs_dir, run_dir / "artifacts", run_dir / "work"):
                directory.mkdir(parents=True, exist_ok=False)
            claimed: list[dict[str, Any]] = []
            try:
                claimed_inputs = []
                for metadata, logical_name, filename in upload_specs:
                    claimed_inputs.append(
                        self._claim_upload(
                            metadata,
                            run_id,
                            inputs_dir,
                            logical_name,
                            filename,
                        )
                    )
                    claimed.append(metadata)
                now = _utc_now()
                manifest: dict[str, Any] = {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "run_id": run_id,
                    "workflow": "small_area",
                    "status": "queued",
                    "created_at": now,
                    "started_at": None,
                    "finished_at": None,
                    "synthpopcan_version": __version__,
                    "request": request,
                    "random_seed": request.get("options", {}).get("random_seed"),
                    "inputs": claimed_inputs,
                    "artifacts": [],
                    "summary": {},
                    "error": None,
                    "reproduction": None,
                    "assurance": None,
                }
                self._write_json_atomic(run_dir / "run.json", manifest)
                (run_dir / "events.ndjson").touch(exist_ok=False)
                self.append_event(run_id, "queued", "Run queued")
                return self.load_run(run_id)
            except Exception:
                for metadata in reversed(claimed):
                    self._release_upload_claim(metadata)
                shutil.rmtree(run_dir, ignore_errors=True)
                raise

    def list_runs(self) -> list[dict[str, Any]]:
        """Return newest runs first."""
        runs = [
            self.load_run(path.name)
            for path in self.runs_dir.iterdir()
            if path.is_dir()
        ]
        return sorted(runs, key=lambda item: str(item["created_at"]), reverse=True)

    def load_run(self, run_id: str) -> dict[str, Any]:
        """Load one validated run manifest."""
        run_dir = self.run_dir(run_id)
        try:
            manifest = RunManifest.model_validate(
                json.loads((run_dir / "run.json").read_text())
            ).model_dump()
        except FileNotFoundError as exc:
            raise KeyError(f"unknown run {run_id}") from exc
        return manifest

    def update_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        """Atomically update trusted manifest fields."""
        with self._lock:
            manifest = self.load_run(run_id)
            manifest.update(changes)
            manifest = RunManifest.model_validate(manifest).model_dump()
            self._write_json_atomic(self.run_dir(run_id) / "run.json", manifest)
            return manifest

    def transition_run(
        self,
        run_id: str,
        status: str,
        **changes: Any,
    ) -> dict[str, Any]:
        """Apply a valid lifecycle transition and its timestamps."""
        with self._lock:
            manifest = self.load_run(run_id)
            current = str(manifest["status"])
            allowed = {
                "queued": {"running", "cancelled", "failed", "interrupted"},
                "running": {"succeeded", "failed", "cancelling", "interrupted"},
                "cancelling": {"cancelled", "failed", "interrupted"},
            }
            if status not in allowed.get(current, set()):
                raise ValueError(f"invalid run transition {current} -> {status}")
            now = _utc_now()
            if status == "running":
                manifest["started_at"] = now
            if status in _TERMINAL_STATES:
                manifest["finished_at"] = now
            manifest["status"] = status
            manifest.update(changes)
            if status in _TERMINAL_STATES:
                manifest["assurance"] = build_run_assurance(
                    manifest,
                    self.resolve_managed_path,
                )
            manifest = RunManifest.model_validate(manifest).model_dump()
            self._write_json_atomic(self.run_dir(run_id) / "run.json", manifest)
            return manifest

    def verify_assurance(self, run_id: str) -> dict[str, Any]:
        """Independently recompute and compare one terminal run's evidence."""
        return verify_run_assurance(
            self.load_run(run_id),
            self.resolve_managed_path,
        )

    def append_event(
        self,
        run_id: str,
        stage: str,
        message: str,
        *,
        completed: int | None = None,
        total: int | None = None,
    ) -> dict[str, Any]:
        """Persist one numbered progress event with flush and fsync."""
        with self._lock:
            events = self.read_events(run_id)
            event = RunEvent(
                id=len(events) + 1,
                timestamp=_utc_now(),
                stage=stage,
                message=message,
                completed=completed,
                total=total,
            ).model_dump()
            events_path = self.run_dir(run_id) / "events.ndjson"
            with events_path.open("a") as handle:
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return event

    def read_events(self, run_id: str, *, after_id: int = 0) -> list[dict[str, Any]]:
        """Read persisted events after an optional replay cursor."""
        events_path = self.run_dir(run_id) / "events.ndjson"
        try:
            lines = events_path.read_text().splitlines()
        except FileNotFoundError:
            self.load_run(run_id)
            return []
        events = [
            RunEvent.model_validate(json.loads(line)).model_dump()
            for line in lines
            if line
        ]
        return [event for event in events if event["id"] > after_id]

    def artifact_path(
        self,
        run_id: str,
        artifact_id: str,
    ) -> tuple[Path, dict[str, Any]]:
        """Resolve an artifact only through its owning manifest entry."""
        _validate_opaque_id(artifact_id, "artifact")
        manifest = self.load_run(run_id)
        for artifact in manifest["artifacts"]:
            if artifact.get("artifact_id") == artifact_id:
                path = self.resolve_managed_path(str(artifact["path"]))
                if not path.is_file():
                    raise KeyError(f"artifact file is missing: {artifact_id}")
                return path, artifact
        raise KeyError(f"unknown artifact {artifact_id}")

    def run_dir(self, run_id: str) -> Path:
        """Return a validated run directory contained by the workspace."""
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run ID")
        candidate = (self.runs_dir / run_id).resolve()
        if candidate.parent != self.runs_dir:
            raise ValueError("run path escapes the workspace")
        return candidate

    def resolve_managed_path(self, relative_path: str) -> Path:
        """Resolve a manifest-owned path and reject traversal or symlink escape."""
        untrusted_path = Path(relative_path)
        if untrusted_path.is_absolute():
            raise ValueError("managed path must be relative to the workspace")
        candidate = (self.root / untrusted_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("managed path escapes the workspace")
        return candidate

    def recover_interrupted_runs(self) -> None:
        """Mark unfinished manifests interrupted on application startup."""
        for path in self.runs_dir.iterdir():
            if not path.is_dir() or not _RUN_ID.fullmatch(path.name):
                continue
            manifest_path = path / "run.json"
            if not manifest_path.is_file():
                continue
            manifest = RunManifest.model_validate(
                json.loads(manifest_path.read_text())
            ).model_dump()
            if manifest.get("status") in {"queued", "running", "cancelling"}:
                manifest["status"] = "interrupted"
                manifest["finished_at"] = _utc_now()
                manifest["error"] = {
                    "kind": "interrupted",
                    "message": "Run was interrupted before the local app restarted.",
                }
                manifest["assurance"] = build_run_assurance(
                    manifest,
                    self.resolve_managed_path,
                )
                manifest = RunManifest.model_validate(manifest).model_dump()
                self._write_json_atomic(manifest_path, manifest)
                events_path = path / "events.ndjson"
                events_path.touch(exist_ok=True)
                self.append_event(
                    path.name,
                    "interrupted",
                    "Run interrupted by application restart",
                )

    def _claim_upload(
        self,
        metadata: dict[str, Any],
        run_id: str,
        inputs_dir: Path,
        logical_name: str,
        filename: str,
    ) -> dict[str, Any]:
        upload_id = str(metadata["upload_id"])
        source = self.resolve_managed_path(str(metadata["path"]))
        destination = inputs_dir / filename
        original_metadata = dict(metadata)
        os.replace(source, destination)
        try:
            metadata["claimed_by"] = run_id
            metadata["path"] = str(destination.relative_to(self.root))
            self._write_json_atomic(self.uploads_dir / f"{upload_id}.json", metadata)
        except Exception:
            if destination.exists():
                os.replace(destination, source)
            metadata.clear()
            metadata.update(original_metadata)
            raise
        return {
            "logical_name": logical_name,
            "upload_id": upload_id,
            "display_name": metadata["display_name"],
            "path": metadata["path"],
            "media_type": metadata["media_type"],
            "byte_size": metadata["byte_size"],
            "sha256": metadata["sha256"],
        }

    def _release_upload_claim(self, metadata: dict[str, Any]) -> None:
        upload_id = str(metadata["upload_id"])
        _validate_opaque_id(upload_id, "upload")
        claimed_path = self.resolve_managed_path(str(metadata["path"]))
        upload_path = (self.uploads_dir / f"{upload_id}.bin").resolve()
        if upload_path.parent != self.uploads_dir:
            raise ValueError("upload path escapes the workspace")
        if claimed_path.exists():
            os.replace(claimed_path, upload_path)
        metadata["claimed_by"] = None
        metadata["path"] = str(upload_path.relative_to(self.root))
        self._write_json_atomic(self.uploads_dir / f"{upload_id}.json", metadata)

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("JSON path escapes the workspace")
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
        try:
            with temporary.open("x") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _safe_display_name(name: str) -> str:
    cleaned = Path(name.replace("\\", "/")).name.strip()
    if not cleaned:
        return "upload.csv"
    return cleaned[:255]


def _validate_opaque_id(value: str, label: str) -> None:
    if not _OPAQUE_ID.fullmatch(value):
        raise ValueError(f"invalid {label} ID")


def _new_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(6)}"


def publish_artifact(
    root: Path,
    source: Path,
    destination: Path,
    *,
    logical_name: str,
    media_type: str,
    row_count: int | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Copy, hash, fsync, and atomically publish one completed artifact."""
    root = root.resolve()
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_relative_to(root):
        raise ValueError("artifact source escapes the workspace")
    if not destination.is_relative_to(root):
        raise ValueError("artifact destination escapes the workspace")
    digest = hashlib.sha256()
    byte_size = 0
    temporary = source.with_name(f".{source.name}.publish-{secrets.token_hex(6)}")
    try:
        with source.open("rb") as input_handle, temporary.open("xb") as output_handle:
            while True:
                if cancel_check is not None:
                    cancel_check()
                chunk = input_handle.read(1024 * 1024)
                if not chunk:
                    break
                output_handle.write(chunk)
                digest.update(chunk)
                byte_size += len(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        if cancel_check is not None:
            cancel_check()
        os.replace(temporary, destination)
        source.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "artifact_id": secrets.token_hex(16),
        "logical_name": logical_name,
        "filename": destination.name,
        "path": str(destination.relative_to(root)),
        "media_type": media_type,
        "byte_size": byte_size,
        "sha256": digest.hexdigest(),
        "row_count": row_count,
    }
