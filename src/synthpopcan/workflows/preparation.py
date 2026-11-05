"""Atomic publication and input fingerprints for CLI preparation steps."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from synthpopcan._profile_preparation import write_json


def file_fingerprint(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": digest,
    }


def publish_preparation(
    output: Path,
    inputs: tuple[Path, ...],
    action: Callable[[Path], dict[str, Any]],
    invocation: Mapping[str, Any],
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Leave failed steps unpublished and never overwrite an existing result."""
    if output.exists():
        raise ValueError(
            f"Output already exists: {output}. "
            "Choose a new --out directory to preserve completed results."
        )
    fingerprints = [file_fingerprint(path) for path in inputs]
    if (
        expected_sha256 is not None
        and fingerprints[0]["sha256"] != expected_sha256.lower()
    ):
        raise ValueError(
            "Profile SHA-256 does not match --profile-sha256. "
            "Verify the source file before preparing controls."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".synthpopcan-prepare-", dir=output.parent
    ) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        result = action(stage)
        artifacts = [
            {**file_fingerprint(path), "path": str(path.relative_to(stage))}
            for path in sorted(stage.rglob("*"))
            if path.is_file()
        ]
        write_json(
            stage / "preparation.json",
            {
                "operation": invocation["operation"],
                "invocation": dict(invocation),
                "cwd": os.getcwd(),
                "inputs": fingerprints,
                "artifacts": artifacts,
            },
        )
        stage.rename(output)
    return result
