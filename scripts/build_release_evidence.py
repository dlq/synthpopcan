"""Build a machine-readable release evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path


def file_evidence(path: Path) -> dict[str, object]:
    """Return checksum and size evidence for one release file."""
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_size += len(chunk)
    return {
        "filename": path.name,
        "sha256": digest.hexdigest(),
        "byte_size": byte_size,
    }


def build_manifest(
    *,
    tag: str,
    commit: str,
    version: str,
    files: list[Path],
) -> dict[str, object]:
    """Validate release identity and assemble permanent evidence metadata."""
    if tag != f"v{version}":
        raise ValueError(f"tag {tag!r} does not match version {version!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("commit must be a full 40-character lowercase Git SHA")
    filenames = [path.name for path in files]
    if len(filenames) != len(set(filenames)):
        raise ValueError("release evidence filenames must be unique")
    distributions = [
        path
        for path in files
        if path.name.startswith("synthpopcan-")
        and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    ]
    if not distributions:
        raise ValueError("at least one distribution file is required")
    normalized_version = version.replace("-", "_")
    if any(normalized_version not in path.name for path in distributions):
        raise ValueError("a distribution filename does not contain the package version")
    return {
        "schema_version": "synthpopcan-release-evidence-v1",
        "release": {"tag": tag, "commit": commit, "version": version},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "files": [file_evidence(path) for path in sorted(files)],
        "checks": [
            "full Python test suite with branch coverage threshold",
            "extended numerical correctness and reference suite",
            "installed-wheel smoke test in an isolated environment",
            "release tag, commit, and package-version identity checks",
        ],
        "limitations": [
            "Passing checks supports implementation and numerical correctness but "
            "does not establish fitness for every substantive research use.",
            "External source-data validity remains bounded by the cited providers "
            "and documented transformations.",
        ],
        "waived_checks": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    missing = [path for path in args.files if not path.is_file()]
    if missing:
        raise SystemExit(f"missing evidence file: {missing[0]}")
    manifest = build_manifest(
        tag=args.tag,
        commit=args.commit,
        version=args.version,
        files=args.files,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
