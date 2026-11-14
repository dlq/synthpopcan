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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from synthpopcan._runtime_schemas import RunEvent, RunManifest, UploadMetadata
from synthpopcan._version import __version__
from synthpopcan.assurance import build_run_assurance, verify_run_assurance

RUN_SCHEMA_VERSION = "synthpopcan-run-v1"
_OPAQUE_ID = re.compile(r"^[a-f0-9]{32}$")
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$")
_TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


class RestartError(ValueError):
    """A run cannot be safely restarted from its retained inputs."""


@dataclass(frozen=True)
class _UploadClaimSpec:
    metadata: dict[str, Any]
    logical_name: str
    filename: str


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
        self.uploads_dir: Path = uploads_dir.resolve()
        self.runs_dir: Path = runs_dir.resolve()
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

    def _create_run_transaction(
        self,
        *,
        workflow: str,
        request: dict[str, Any],
        upload_specs: list[_UploadClaimSpec],
        random_seed: int | None,
    ) -> dict[str, Any]:
        """Create one queued run, rolling back every claimed upload on failure."""
        run_id = _new_run_id()
        run_dir = self.run_dir(run_id)
        inputs_dir = run_dir / "inputs"
        # This atomic mkdir establishes ownership.  A random-ID collision must
        # fail before rollback is allowed to remove anything at that path.
        run_dir.mkdir(exist_ok=False)
        claimed_metadata: list[dict[str, Any]] = []
        try:
            for directory in (inputs_dir, run_dir / "artifacts", run_dir / "work"):
                directory.mkdir(exist_ok=False)
            claimed_inputs = []
            for spec in upload_specs:
                claimed_inputs.append(
                    self._claim_upload(
                        spec.metadata,
                        run_id,
                        inputs_dir,
                        spec.logical_name,
                        spec.filename,
                    )
                )
                claimed_metadata.append(spec.metadata)
            manifest: dict[str, Any] = {
                "schema_version": RUN_SCHEMA_VERSION,
                "run_id": run_id,
                "workflow": workflow,
                "status": "queued",
                "created_at": _utc_now(),
                "started_at": None,
                "finished_at": None,
                "synthpopcan_version": __version__,
                "request": request,
                "random_seed": random_seed,
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
            return self._create_run_transaction(
                workflow="ipf",
                request=request,
                upload_specs=[
                    _UploadClaimSpec(seed, "seed", "seed.csv"),
                    _UploadClaimSpec(controls, "controls", "controls.csv"),
                ],
                random_seed=None,
            )

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
            return self._create_run_transaction(
                workflow="model",
                request=request,
                upload_specs=(
                    [_UploadClaimSpec(upload, "package", "package.json")]
                    if upload is not None
                    else []
                ),
                random_seed=request.get("options", {}).get("random_seed"),
            )

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
            control_pack_id = inputs.get("control_pack_id")
            control_pack_evidence_id = inputs.get("control_pack_evidence_upload_id")
            if bool(control_pack_id) != bool(control_pack_evidence_id):
                raise ValueError(
                    "small-area control pack and evidence upload are both required"
                )
            if control_pack_id and not person_controls_id:
                raise ValueError("small-area control packs require person controls")
            upload_specs: list[_UploadClaimSpec] = []
            if package_id:
                upload_specs.append(
                    _UploadClaimSpec(
                        self.get_upload(str(package_id), require_unclaimed=True),
                        "package",
                        "package.json",
                    )
                )
            if candidate_households_id and candidate_persons_id:
                upload_specs.extend(
                    (
                        _UploadClaimSpec(
                            self.get_upload(
                                str(candidate_households_id), require_unclaimed=True
                            ),
                            "candidate_households",
                            "households.csv",
                        ),
                        _UploadClaimSpec(
                            self.get_upload(
                                str(candidate_persons_id), require_unclaimed=True
                            ),
                            "candidate_persons",
                            "persons.csv",
                        ),
                    )
                )
            upload_specs.append(
                _UploadClaimSpec(
                    self.get_upload(controls_id, require_unclaimed=True),
                    "controls",
                    "controls.csv",
                )
            )
            if person_controls_id:
                upload_specs.append(
                    _UploadClaimSpec(
                        self.get_upload(
                            str(person_controls_id), require_unclaimed=True
                        ),
                        "person_controls",
                        "person-controls.csv",
                    )
                )
            if control_pack_evidence_id:
                upload_specs.append(
                    _UploadClaimSpec(
                        self.get_upload(
                            str(control_pack_evidence_id), require_unclaimed=True
                        ),
                        "control_pack_evidence",
                        "control-pack-evidence.json",
                    )
                )
            upload_specs.extend(self._conditional_uploads(inputs))
            boundaries_id = inputs.get("boundaries_upload_id")
            if boundaries_id:
                upload_specs.append(
                    _UploadClaimSpec(
                        self.get_upload(str(boundaries_id), require_unclaimed=True),
                        "boundaries",
                        "boundaries.geojson",
                    )
                )
            upload_ids = [str(spec.metadata["upload_id"]) for spec in upload_specs]
            if len(upload_ids) != len(set(upload_ids)):
                raise ValueError("small-area input uploads must differ")
            return self._create_run_transaction(
                workflow="small_area",
                request=request,
                upload_specs=upload_specs,
                random_seed=request.get("options", {}).get("random_seed"),
            )

    def _conditional_uploads(self, inputs: dict[str, Any]) -> list[_UploadClaimSpec]:
        specs = []
        for family, source in (
            ("marital_status", "controls"),
            ("education", "profile"),
            ("labour_force", "profile"),
            ("work_activity", "profile"),
        ):
            pack = inputs.get(f"{family}_pack")
            upload_id = inputs.get(f"{family}_{source}_upload_id")
            if bool(pack) != bool(upload_id):
                raise ValueError(f"{family} pack and source upload are both required")
            if upload_id:
                metadata = self.get_upload(str(upload_id), require_unclaimed=True)
                extension = (
                    "zip" if metadata["media_type"] == "application/zip" else "csv"
                )
                specs.append(
                    _UploadClaimSpec(
                        metadata,
                        f"{family}_{source}",
                        f"{family.replace('_', '-')}-{source}.{extension}",
                    )
                )
        return specs

    def restart_interrupted_small_area(
        self,
        run_id: str,
        preflight: Callable[[Path, dict[str, Path], dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Create a fresh run from verified inputs without modifying the old run."""
        with self._lock:
            original = self.load_run(run_id)
            if (
                original["workflow"] != "small_area"
                or original["status"] != "interrupted"
            ):
                raise RestartError("Only interrupted small-area runs can be restarted.")
            if original["synthpopcan_version"] != __version__:
                raise RestartError(
                    "The run used a different SynthPopCan version; create a new run."
                )
            assurance = self.verify_assurance(run_id)
            if not assurance["passed"]:
                raise RestartError(
                    "Run evidence or inputs have changed; create a new run."
                )
            self._verify_restart_model(original)
            new_id = _new_run_id()
            destination = self.run_dir(new_id)
            if destination.exists():
                raise FileExistsError("Restart run identifier already exists")
            staging = self.root / f".restart-{secrets.token_hex(16)}"
            staging.mkdir(exist_ok=False)
            try:
                for name in ("inputs", "artifacts", "work"):
                    (staging / name).mkdir()
                copies, input_paths = self._copy_restart_inputs(
                    original, staging, new_id
                )
                preflight(self.root, input_paths, original["request"])
                for item in copies:
                    digest = hashlib.sha256()
                    size = 0
                    with input_paths[item["upload_id"]].open("rb") as handle:
                        while chunk := handle.read(1024 * 1024):
                            digest.update(chunk)
                            size += len(chunk)
                    if (
                        digest.hexdigest() != item["sha256"]
                        or size != item["byte_size"]
                    ):
                        raise RestartError(
                            "Restart inputs changed during preflight; create a new run."
                        )
                manifest = {
                    **original,
                    "run_id": new_id,
                    "status": "queued",
                    "created_at": _utc_now(),
                    "started_at": None,
                    "finished_at": None,
                    "inputs": copies,
                    "artifacts": [],
                    "summary": {},
                    "error": None,
                    "reproduction": None,
                    "assurance": None,
                    "restarted_from": run_id,
                }
                manifest = RunManifest.model_validate(manifest).model_dump()
                self._write_json_atomic(staging / "run.json", manifest)
                (staging / "events.ndjson").write_text(
                    json.dumps(
                        {
                            "id": 1,
                            "timestamp": _utc_now(),
                            "stage": "queued",
                            "message": f"Restarted from {run_id}",
                            "completed": None,
                            "total": None,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                self._publish_restart(staging, destination)
                return self.load_run(new_id)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise

    @staticmethod
    def _publish_restart(staging: Path, destination: Path) -> None:
        # Exclusive directory creation prevents collisions from replacing a run.
        # The manifest is published last, after all inputs and events are in place.
        destination.mkdir(exist_ok=False)
        try:
            for name in ("inputs", "artifacts", "work", "events.ndjson", "run.json"):
                os.rename(staging / name, destination / name)
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _verify_restart_model(self, original: dict[str, Any]) -> None:
        model_id = original["request"].get("inputs", {}).get("model_id")
        package_path = self.run_dir(str(original["run_id"])) / "work" / "package.json"
        if not model_id:
            return
        if (
            package_path.is_symlink()
            or package_path.resolve().parent != package_path.parent
        ):
            raise RestartError("The prior model path is invalid; create a new run.")
        if not package_path.exists():
            return
        from synthpopcan.models import model_payload

        try:
            previous = json.loads(package_path.read_text())
            current = model_payload(str(model_id))
        except (OSError, ValueError, KeyError) as exc:
            raise RestartError(
                "The prior model cannot be verified; create a new run."
            ) from exc
        if previous != current:
            raise RestartError(
                "The model has changed since the interrupted run; create a new run."
            )

    def _copy_restart_inputs(self, original, staging: Path, new_id: str):
        copied = []
        paths = {}
        old_inputs = self.run_dir(str(original["run_id"])) / "inputs"
        if old_inputs.is_symlink() or old_inputs.resolve().parent != old_inputs.parent:
            raise RestartError("The run input directory is invalid; create a new run.")
        for item in original["inputs"]:
            source = self.resolve_managed_path(str(item["path"]))
            if source.parent != old_inputs.resolve() or source.is_symlink():
                raise RestartError("Run input path is invalid; create a new run.")
            upload_id = str(item["upload_id"])
            _validate_opaque_id(upload_id, "upload")
            if upload_id in paths:
                raise RestartError("Run has duplicate input identifiers.")
            target = staging / "inputs" / source.name
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as src, target.open("xb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            if digest.hexdigest() != item["sha256"] or size != item["byte_size"]:
                raise RestartError("Run inputs have changed; create a new run.")
            copied.append({**item, "path": f"runs/{new_id}/inputs/{source.name}"})
            paths[upload_id] = target
        return copied, paths

    def list_runs(self) -> list[dict[str, Any]]:
        """Return newest runs first."""
        runs = [
            self.load_run(path.name)
            for path in self.runs_dir.iterdir()
            if path.is_dir() and (path / "run.json").is_file()
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
