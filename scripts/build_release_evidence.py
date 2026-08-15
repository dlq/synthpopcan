"""Build a machine-readable release evidence manifest."""

from __future__ import annotations

import argparse
import ast
import email
import hashlib
import json
import platform
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path

_DISTRIBUTION_SMOKE_LOG = "release-distribution-smoke.log"
_DISTRIBUTION_SMOKE_MARKERS = (
    "Installed wheel smoke command completed.",
    "Installed sdist smoke command completed.",
    "Installed model-build smoke command completed.",
    "Installed-wheel fictional case-study interface smoke command completed.",
)


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


def _filename_version(value: str) -> str:
    """Return the normalized version spelling used in distribution filenames."""
    return re.sub(r"[-_.]+", "_", value).lower()


def _declared_runtime_version(source: str, *, filename: str) -> str:
    """Read one literal ``__version__`` assignment without importing the package."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise ValueError(f"cannot parse runtime version from {filename}") from exc
    versions: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            versions.append(node.value.value)
    if len(versions) != 1:
        raise ValueError(f"{filename} must contain exactly one literal __version__")
    return versions[0]


def validate_source_version(*, version: str, project_root: Path = Path(".")) -> None:
    """Require every release-facing source version and date to agree."""
    project = tomllib.loads((project_root / "pyproject.toml").read_text())
    project_version = project.get("project", {}).get("version")
    if project_version != version:
        raise ValueError("pyproject.toml version does not match the release version")

    init_path = project_root / "src" / "synthpopcan" / "__init__.py"
    runtime_version = _declared_runtime_version(
        init_path.read_text(), filename=str(init_path)
    )
    if runtime_version != version:
        raise ValueError("synthpopcan.__version__ does not match the release version")

    citation = (project_root / "CITATION.cff").read_text()
    citation_versions = re.findall(
        r'^\s*version:\s*["\']?([^"\'\s]+)', citation, re.MULTILINE
    )
    if not citation_versions or any(item != version for item in citation_versions):
        raise ValueError("CITATION.cff versions do not match the release version")
    citation_dates = re.findall(
        r"^\s*date-released:\s*[\"']?([^\"'\s]+)", citation, re.MULTILINE
    )
    if not citation_dates or len(set(citation_dates)) != 1:
        raise ValueError("CITATION.cff must contain one consistent release date")

    changelog = (project_root / "CHANGELOG.md").read_text()
    entry = re.search(rf"^## {re.escape(version)} - (\S+)", changelog, re.MULTILINE)
    if entry is None:
        raise ValueError("CHANGELOG.md has no dated entry for the release version")
    if citation_dates[0] != entry.group(1):
        raise ValueError("CITATION.cff and CHANGELOG.md release dates do not match")


def _metadata_version(payload: bytes, *, filename: str) -> str:
    metadata = email.message_from_bytes(payload)
    version = metadata.get("Version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{filename} has no distribution Version metadata")
    return version


def _one_archive_name(names: list[str], *, suffix: str, archive: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"{archive} must contain exactly one {suffix}")
    return matches[0]


def _validate_wheel_contents(path: Path, *, version: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            metadata_name = _one_archive_name(
                names, suffix=".dist-info/METADATA", archive=path.name
            )
            init_name = _one_archive_name(
                names, suffix="synthpopcan/__init__.py", archive=path.name
            )
            metadata_version = _metadata_version(
                archive.read(metadata_name), filename=f"{path.name}:{metadata_name}"
            )
            runtime_version = _declared_runtime_version(
                archive.read(init_name).decode("utf-8"),
                filename=f"{path.name}:{init_name}",
            )
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"cannot inspect wheel distribution {path.name}") from exc
    if metadata_version != version or runtime_version != version:
        raise ValueError("wheel metadata and runtime versions must match the release")


def _validate_sdist_contents(path: Path, *, version: str) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            names = archive.getnames()
            pyproject_name = _one_archive_name(
                names, suffix="/pyproject.toml", archive=path.name
            )
            init_name = _one_archive_name(
                names, suffix="/src/synthpopcan/__init__.py", archive=path.name
            )
            metadata_name = _one_archive_name(
                names, suffix="/PKG-INFO", archive=path.name
            )
            pyproject_handle = archive.extractfile(pyproject_name)
            init_handle = archive.extractfile(init_name)
            metadata_handle = archive.extractfile(metadata_name)
            if None in (pyproject_handle, init_handle, metadata_handle):
                raise ValueError(f"cannot read version metadata from {path.name}")
            project = tomllib.loads(pyproject_handle.read().decode("utf-8"))
            runtime_version = _declared_runtime_version(
                init_handle.read().decode("utf-8"),
                filename=f"{path.name}:{init_name}",
            )
            metadata_version = _metadata_version(
                metadata_handle.read(), filename=f"{path.name}:{metadata_name}"
            )
    except (
        OSError,
        UnicodeDecodeError,
        tarfile.TarError,
        tomllib.TOMLDecodeError,
    ) as exc:
        raise ValueError(f"cannot inspect sdist distribution {path.name}") from exc
    project_version = project.get("project", {}).get("version")
    if {project_version, runtime_version, metadata_version} != {version}:
        raise ValueError("sdist metadata and runtime versions must match the release")


def _validate_distributions(*, version: str, files: list[Path]) -> None:
    """Require one wheel and one sdist for the exact release version."""
    wheels = [
        path
        for path in files
        if path.name.startswith("synthpopcan-") and path.suffix == ".whl"
    ]
    sdists = [
        path
        for path in files
        if path.name.startswith("synthpopcan-") and path.name.endswith(".tar.gz")
    ]
    if len(wheels) != 1:
        raise ValueError("exactly one wheel distribution is required")
    if len(sdists) != 1:
        raise ValueError("exactly one sdist distribution is required")

    wheel_parts = wheels[0].name.removesuffix(".whl").split("-")
    if len(wheel_parts) < 5:
        raise ValueError(f"invalid wheel filename: {wheels[0].name}")
    sdist_version = sdists[0].name.removeprefix("synthpopcan-").removesuffix(".tar.gz")
    expected = _filename_version(version)
    if _filename_version(wheel_parts[1]) != expected:
        raise ValueError("wheel filename does not contain the package version")
    if _filename_version(sdist_version) != expected:
        raise ValueError("sdist filename does not contain the package version")
    _validate_wheel_contents(wheels[0], version=version)
    _validate_sdist_contents(sdists[0], version=version)


def _one_named_file(files: list[Path], filename: str) -> Path:
    matches = [path for path in files if path.name == filename]
    if len(matches) != 1:
        raise ValueError(f"exactly one {filename} evidence file is required")
    return matches[0]


def _validate_distribution_smokes(files: list[Path]) -> None:
    """Require evidence that every isolated distribution smoke completed."""
    smoke_log = _one_named_file(files, _DISTRIBUTION_SMOKE_LOG)
    log_text = smoke_log.read_text(errors="replace")
    missing = [
        marker for marker in _DISTRIBUTION_SMOKE_MARKERS if marker not in log_text
    ]
    if missing:
        raise ValueError(f"distribution smoke log is missing marker: {missing[0]}")


def _validate_ci_run(*, commit: str, files: list[Path]) -> None:
    """Require a successful push CI record for the exact release commit."""
    ci_path = _one_named_file(files, "release-ci-run.json")
    try:
        ci_run = json.loads(ci_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("release CI evidence must be valid JSON") from exc
    expected = {
        "head_sha": commit,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "name": "CI",
        "path": ".github/workflows/ci.yml",
    }
    for key, value in expected.items():
        if ci_run.get(key) != value:
            raise ValueError(f"release CI evidence has invalid {key}")
    for key in ("id", "workflow_id", "run_number", "run_attempt"):
        value = ci_run.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"release CI evidence has invalid {key}")


def missing_release_assets(*, asset_dir: Path, release: object, tag: str) -> list[str]:
    """Validate existing immutable assets and return names still to upload."""
    if not isinstance(release, dict):
        raise ValueError("GitHub release metadata must be a JSON object")
    expected_release = {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
    }
    for key, value in expected_release.items():
        if release.get(key) != value:
            raise ValueError(f"GitHub release metadata has invalid {key}")

    entries = sorted(asset_dir.iterdir())
    if not entries or any(not entry.is_file() for entry in entries):
        raise ValueError("release evidence directory must contain files only")
    local = {entry.name: file_evidence(entry) for entry in entries}

    remote_value = release.get("assets")
    if not isinstance(remote_value, list):
        raise ValueError("GitHub release metadata assets must be a list")
    remote: dict[str, dict[str, object]] = {}
    for item in remote_value:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("GitHub release contains invalid asset metadata")
        name = item["name"]
        if name in remote:
            raise ValueError(f"GitHub release contains duplicate asset {name}")
        remote[name] = item

    extras = sorted(set(remote) - set(local))
    if extras:
        raise ValueError(f"GitHub release contains extraneous asset {extras[0]}")
    for name in sorted(set(local) & set(remote)):
        expected = local[name]
        actual = remote[name]
        if actual.get("state") not in (None, "uploaded"):
            raise ValueError(f"GitHub release asset {name} is not uploaded")
        if actual.get("size") != expected["byte_size"]:
            raise ValueError(f"GitHub release asset {name} has a different size")
        if actual.get("digest") != f"sha256:{expected['sha256']}":
            raise ValueError(f"GitHub release asset {name} has a different digest")
    return sorted(set(local) - set(remote))


def build_manifest(
    *,
    tag: str,
    commit: str,
    version: str,
    workflow_sha: str,
    dispatch_sha: str,
    dispatch_ref: str,
    files: list[Path],
) -> dict[str, object]:
    """Validate release identity and assemble permanent evidence metadata."""
    if tag != f"v{version}":
        raise ValueError(f"tag {tag!r} does not match version {version!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("commit must be a full 40-character lowercase Git SHA")
    if workflow_sha != commit:
        raise ValueError("workflow definition SHA must match the release commit")
    if dispatch_sha != commit:
        raise ValueError("workflow dispatch SHA must match the release commit")
    if dispatch_ref != f"refs/tags/{tag}":
        raise ValueError("workflow dispatch ref must be the exact release tag")
    filenames = [path.name for path in files]
    if len(filenames) != len(set(filenames)):
        raise ValueError("release evidence filenames must be unique")
    _validate_distributions(version=version, files=files)
    _validate_distribution_smokes(files)
    _validate_ci_run(commit=commit, files=files)
    return {
        "schema_version": "synthpopcan-release-evidence-v2",
        "release": {
            "tag": tag,
            "commit": commit,
            "version": version,
            "workflow_sha": workflow_sha,
            "dispatch_sha": dispatch_sha,
            "dispatch_ref": dispatch_ref,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "files": [file_evidence(path) for path in sorted(files)],
        "checks": [
            "successful full CI push workflow for the exact release commit",
            "rerun full Python test suite with branch coverage threshold",
            "extended numerical correctness and reference suite",
            "installed-wheel smoke test in an isolated environment",
            "installed-sdist smoke test in an isolated environment",
            "installed-wheel model-build-extra smoke test in an isolated environment",
            "installed-wheel fictional case-study interface smoke test in an isolated environment",
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
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--version")
    parser.add_argument("--workflow-sha")
    parser.add_argument("--dispatch-sha")
    parser.add_argument("--dispatch-ref")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-source-version", action="store_true")
    parser.add_argument("--verify-release-assets", type=Path)
    parser.add_argument("--asset-dir", type=Path)
    parser.add_argument("--missing-output", type=Path)
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    if args.check_source_version:
        if args.version is None:
            parser.error("--check-source-version requires --version")
        validate_source_version(version=args.version)
        print(f"Release source versions agree at {args.version}.")
        return
    if args.verify_release_assets is not None:
        if args.tag is None or args.asset_dir is None or args.missing_output is None:
            parser.error(
                "--verify-release-assets requires --tag, --asset-dir, and "
                "--missing-output"
            )
        try:
            release = json.loads(args.verify_release_assets.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit("invalid GitHub release metadata JSON") from exc
        missing_assets = missing_release_assets(
            asset_dir=args.asset_dir, release=release, tag=args.tag
        )
        args.missing_output.write_text(json.dumps(missing_assets, indent=2) + "\n")
        return
    required = {
        "--tag": args.tag,
        "--commit": args.commit,
        "--version": args.version,
        "--workflow-sha": args.workflow_sha,
        "--dispatch-sha": args.dispatch_sha,
        "--dispatch-ref": args.dispatch_ref,
        "--output": args.output,
    }
    missing_arguments = [name for name, value in required.items() if value is None]
    if missing_arguments or not args.files:
        parser.error("manifest mode requires files and " + ", ".join(missing_arguments))
    missing = [path for path in args.files if not path.is_file()]
    if missing:
        raise SystemExit(f"missing evidence file: {missing[0]}")
    manifest = build_manifest(
        tag=args.tag,
        commit=args.commit,
        version=args.version,
        workflow_sha=args.workflow_sha,
        dispatch_sha=args.dispatch_sha,
        dispatch_ref=args.dispatch_ref,
        files=args.files,
    )
    assert args.output is not None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
