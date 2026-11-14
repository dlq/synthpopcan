"""Validated national batch references and worker-result messages."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, TypeAlias, TypedDict, cast

WorkerResult: TypeAlias = (
    tuple[Literal["ok"], str, dict[str, object]]
    | tuple[Literal["error"], str, str, str, str]
)
BATCH_SCHEMA = "synthpopcan-canada-small-area-batch-v1"
_INVALID_WORKER_RESULT = (
    "national worker returned a malformed result; rerun the command to resume"
)


class BatchIdentity(TypedDict):
    """Validated fields required to safely resume a persisted batch."""

    batch_id: str
    status: Literal["planned", "running", "failed", "completed"]
    attempts: int


def batch_manifest_path(root: Path, record: object) -> Path:
    """Resolve a relative batch manifest without leaving the plan directory."""
    if not isinstance(record, Mapping):
        raise ValueError("national small-area plan batch record is invalid")
    fields = cast(Mapping[object, object], record)
    relative = fields.get("manifest")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("national small-area plan batch record is invalid")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("national batch manifest must be inside the plan directory")
    return resolved


def validate_batch_identity(batch: Mapping[str, object]) -> BatchIdentity:
    """Validate persisted lifecycle fields before scheduling a batch."""
    if batch.get("schema_version") != BATCH_SCHEMA:
        raise ValueError("unsupported batch schema")
    identifier = batch.get("batch_id")
    status = batch.get("status")
    attempts = batch.get("attempts", 0)
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("national batch identifier is invalid")
    if status not in ("planned", "running", "failed", "completed"):
        raise ValueError("national batch status is invalid")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
        raise ValueError("national batch attempts are invalid")
    return {"batch_id": identifier, "status": status, "attempts": attempts}


def decode_worker_result(message: object) -> WorkerResult:
    """Validate worker messages before changing any durable batch state."""
    if not isinstance(message, tuple):
        raise ValueError(_INVALID_WORKER_RESULT)
    values = cast(tuple[object, ...], message)
    if len(values) == 3 and values[0] == "ok" and isinstance(values[1], str):
        if isinstance(values[2], dict):
            payload = cast(dict[object, object], values[2])
            if all(isinstance(key, str) for key in payload):
                return (
                    "ok",
                    values[1],
                    {str(key): value for key, value in payload.items()},
                )
    if (
        len(values) == 5
        and values[0] == "error"
        and all(isinstance(value, str) for value in values[1:])
    ):
        return (
            "error",
            str(values[1]),
            str(cast(object, values[2])),
            str(values[3]),
            str(values[4]),
        )
    raise ValueError(_INVALID_WORKER_RESULT)
