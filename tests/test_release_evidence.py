from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_release_evidence.py"
_SPEC = importlib.util.spec_from_file_location("build_release_evidence", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_manifest = _MODULE.build_manifest
missing_release_assets = _MODULE.missing_release_assets
validate_source_version = _MODULE.validate_source_version

_SMOKE_MARKERS = (
    "Installed wheel smoke command completed.",
    "Installed sdist smoke command completed.",
    "Installed model-build smoke command completed.",
    "Installed-wheel fictional case-study interface smoke command completed.",
)
_COMMIT = "a" * 40


def _write_wheel(
    path: Path, *, version: str, runtime_version: str | None = None
) -> None:
    runtime_version = runtime_version or version
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "synthpopcan/__init__.py", f'__version__ = "{runtime_version}"\n'
        )
        archive.writestr(
            f"synthpopcan-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.5\nName: synthpopcan\nVersion: {version}\n",
        )


def _write_sdist(
    path: Path, *, version: str, runtime_version: str | None = None
) -> None:
    runtime_version = runtime_version or version
    root = f"synthpopcan-{version}"
    files = {
        f"{root}/pyproject.toml": (
            f'[project]\nname = "synthpopcan"\nversion = "{version}"\n'
        ).encode(),
        f"{root}/src/synthpopcan/__init__.py": (
            f'__version__ = "{runtime_version}"\n'
        ).encode(),
        f"{root}/PKG-INFO": (
            f"Metadata-Version: 2.5\nName: synthpopcan\nVersion: {version}\n"
        ).encode(),
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))


def _ci_run(*, commit: str = _COMMIT) -> dict[str, object]:
    return {
        "id": 101,
        "workflow_id": 202,
        "name": "CI",
        "path": ".github/workflows/ci.yml",
        "head_branch": "main",
        "head_sha": commit,
        "run_number": 303,
        "run_attempt": 1,
        "event": "push",
        "status": "completed",
        "conclusion": "success",
    }


def _release_files(tmp_path: Path, *, version: str = "0.6.3") -> dict[str, Path]:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / f"synthpopcan-{version}-py3-none-any.whl"
    _write_wheel(wheel, version=version)
    sdist = dist / f"synthpopcan-{version}.tar.gz"
    _write_sdist(sdist, version=version)
    smoke = tmp_path / "release-distribution-smoke.log"
    smoke.write_text("\n".join(_SMOKE_MARKERS) + "\n")
    ci_run = tmp_path / "release-ci-run.json"
    ci_run.write_text(json.dumps(_ci_run()))
    return {"wheel": wheel, "sdist": sdist, "smoke": smoke, "ci": ci_run}


def _manifest(
    files: list[Path],
    *,
    tag: str = "v0.6.3",
    commit: str = _COMMIT,
    version: str = "0.6.3",
    workflow_sha: str = _COMMIT,
    dispatch_sha: str = _COMMIT,
    dispatch_ref: str = "refs/tags/v0.6.3",
) -> dict[str, object]:
    return build_manifest(
        tag=tag,
        commit=commit,
        version=version,
        workflow_sha=workflow_sha,
        dispatch_sha=dispatch_sha,
        dispatch_ref=dispatch_ref,
        files=files,
    )


def test_release_evidence_names_exact_release_and_hashes_files(
    tmp_path: Path,
) -> None:
    evidence = _release_files(tmp_path)
    report = tmp_path / "correctness.xml"
    report.write_text("<testsuites/>")
    manifest = _manifest([*evidence.values(), report])

    assert manifest["schema_version"] == "synthpopcan-release-evidence-v2"
    assert manifest["release"] == {
        "tag": "v0.6.3",
        "commit": _COMMIT,
        "version": "0.6.3",
        "workflow_sha": _COMMIT,
        "dispatch_sha": _COMMIT,
        "dispatch_ref": "refs/tags/v0.6.3",
    }
    wheel_evidence = next(
        item for item in manifest["files"] if item["filename"].endswith(".whl")
    )
    assert (
        wheel_evidence["sha256"]
        == hashlib.sha256(evidence["wheel"].read_bytes()).hexdigest()
    )
    assert manifest["waived_checks"] == []
    assert "installed-sdist smoke test in an isolated environment" in manifest["checks"]
    assert (
        "installed-wheel model-build-extra smoke test in an isolated environment"
        in manifest["checks"]
    )
    assert (
        "installed-wheel fictional case-study interface smoke test in an "
        "isolated environment" in manifest["checks"]
    )


def test_release_evidence_rejects_identity_mismatch(tmp_path: Path) -> None:
    evidence = _release_files(tmp_path)
    with pytest.raises(ValueError, match="does not match"):
        _manifest(
            list(evidence.values()),
            tag="v0.6.2",
            commit="b" * 40,
            workflow_sha="b" * 40,
            dispatch_sha="b" * 40,
            dispatch_ref="refs/tags/v0.6.2",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("workflow_sha", "b" * 40, "workflow definition SHA"),
        ("dispatch_sha", "b" * 40, "workflow dispatch SHA"),
        ("dispatch_ref", "refs/heads/main", "workflow dispatch ref"),
    ),
)
def test_release_evidence_binds_dispatch_and_workflow_identity(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    evidence = _release_files(tmp_path)
    with pytest.raises(ValueError, match=message):
        _manifest(list(evidence.values()), **{field: value})


@pytest.mark.parametrize(
    ("missing", "message"),
    (("wheel", "exactly one wheel"), ("sdist", "exactly one sdist")),
)
def test_release_evidence_requires_wheel_and_sdist(
    tmp_path: Path, missing: str, message: str
) -> None:
    evidence = _release_files(tmp_path)
    evidence.pop(missing)
    with pytest.raises(ValueError, match=message):
        _manifest(list(evidence.values()))


@pytest.mark.parametrize("distribution", ("wheel", "sdist"))
def test_release_evidence_checks_distribution_internal_versions(
    tmp_path: Path, distribution: str
) -> None:
    evidence = _release_files(tmp_path)
    path = evidence[distribution]
    path.unlink()
    writer = _write_wheel if distribution == "wheel" else _write_sdist
    writer(path, version="0.6.3", runtime_version="0.6.2")
    with pytest.raises(ValueError, match="metadata and runtime versions"):
        _manifest(list(evidence.values()))


def test_release_evidence_requires_all_distribution_smoke_markers(
    tmp_path: Path,
) -> None:
    evidence = _release_files(tmp_path)
    evidence["smoke"].write_text("\n".join(_SMOKE_MARKERS[:-1]) + "\n")
    with pytest.raises(ValueError, match="missing marker"):
        _manifest(list(evidence.values()))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("head_sha", "b" * 40),
        ("head_branch", "release"),
        ("event", "pull_request"),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("name", "Another workflow"),
        ("path", ".github/workflows/other.yml"),
        ("workflow_id", 0),
        ("run_attempt", None),
    ),
)
def test_release_evidence_requires_exact_successful_ci_identity(
    tmp_path: Path, field: str, value: object
) -> None:
    evidence = _release_files(tmp_path)
    payload = _ci_run()
    payload[field] = value
    evidence["ci"].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=f"invalid {field}"):
        _manifest(list(evidence.values()))


def test_release_source_version_gate_matches_current_tree() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    validate_source_version(version=project["project"]["version"])


def _release_asset(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "name": path.name,
        "size": len(payload),
        "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
        "state": "uploaded",
    }


def test_release_asset_inventory_is_idempotent_and_reports_missing(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    first = assets / "first.txt"
    first.write_text("first")
    second = assets / "second.txt"
    second.write_text("second")
    release = {
        "tag_name": "v0.6.3",
        "draft": False,
        "prerelease": False,
        "assets": [_release_asset(first)],
    }

    assert missing_release_assets(asset_dir=assets, release=release, tag="v0.6.3") == [
        "second.txt"
    ]
    release["assets"].append(_release_asset(second))
    assert missing_release_assets(asset_dir=assets, release=release, tag="v0.6.3") == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("digest", "different digest"),
        ("size", "different size"),
        ("extra", "extraneous asset"),
        ("draft", "invalid draft"),
        ("prerelease", "invalid prerelease"),
        ("tag", "invalid tag_name"),
    ),
)
def test_release_asset_inventory_fails_closed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    local = assets / "artifact.whl"
    local.write_bytes(b"wheel")
    release = {
        "tag_name": "v0.6.3",
        "draft": False,
        "prerelease": False,
        "assets": [_release_asset(local)],
    }
    if mutation == "digest":
        release["assets"][0]["digest"] = "sha256:" + "0" * 64
    elif mutation == "size":
        release["assets"][0]["size"] = 99
    elif mutation == "extra":
        release["assets"].append({"name": "extra.txt", "size": 1, "digest": "sha256:0"})
    elif mutation == "draft":
        release["draft"] = True
    elif mutation == "prerelease":
        release["prerelease"] = True
    else:
        release["tag_name"] = "v0.6.2"

    with pytest.raises(ValueError, match=message):
        missing_release_assets(asset_dir=assets, release=release, tag="v0.6.3")


def test_local_release_check_matches_locked_ci_and_web_gates() -> None:
    local_check = Path("scripts/check.sh").read_text()
    assert "uv lock --check" in local_check
    assert "uv run --locked --group docs mdformat --check docs README.md" in local_check
    assert "uv run --locked pytest" in local_check
    assert "npm run test:web:coverage" in local_check
    assert "\nnpm run test:web\n" not in local_check


def test_distribution_smoke_selects_one_exact_version_and_passes_it_through() -> None:
    smoke = Path("scripts/check-wheel.sh").read_text()
    wheel_smoke = Path("scripts/wheel_smoke.py").read_text()
    assert "dist/ must contain exactly one SynthPopCan wheel" in smoke
    assert "dist/ must contain exactly one SynthPopCan sdist" in smoke
    assert 'SYNTHPOPCAN_EXPECTED_VERSION="$version"' in smoke
    assert "SYNTHPOPCAN_EXPECTED_VERSION" in wheel_smoke
    assert 'distribution_version("synthpopcan") == expected_version' in wheel_smoke
    assert "synthpopcan.__version__ == expected_version" in wheel_smoke
    assert '"contracts/public-interface-v1-baseline.json"' in wheel_smoke


def test_publish_is_exact_locked_immutable_and_revalidates_before_pypi() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text()
    for requirement in (
        "concurrency:",
        "cancel-in-progress: false",
        "WORKFLOW_SHA: ${{ github.workflow_sha }}",
        "DISPATCH_SHA: ${{ github.sha }}",
        "DISPATCH_REF: ${{ github.ref }}",
        'test "$WORKFLOW_SHA" = "$RELEASE_COMMIT"',
        'test "$DISPATCH_REF" = "refs/tags/$RELEASE_TAG"',
        'git cat-file -t "$RELEASE_TAG"',
        "uv sync --locked --group dev",
        "uv run --locked pytest",
        "uv lock --check",
        "actions: read",
        'git merge-base --is-ancestor "$RELEASE_COMMIT" origin/main',
        '-f head_sha="$RELEASE_COMMIT"',
        '.head_branch == "main"',
        '.path == ".github/workflows/ci.yml"',
        "workflow_id,",
        "run_attempt,",
        "set -o pipefail",
        "release-distribution-smoke.log",
        "release-ci-run.json",
        "attest-distributions:",
        "--verify-release-assets",
        "missing-release-assets-after-upload.json",
        "git/ref/tags/$RELEASE_TAG",
        'test "$(jq -r .draft',
        'test "$(jq -r .prerelease',
    ):
        assert requirement in workflow
    assert "--clobber" not in workflow
    assert workflow.count("git/ref/tags/$RELEASE_TAG") >= 2


def test_pypi_job_reuses_and_reverifies_exact_release_evidence_last() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text()
    publish_job = workflow.split("\n  publish-to-pypi:\n", maxsplit=1)[1]
    verification_step = (
        "      - name: Reverify exact evidence, remote tag, and final release assets\n"
    )
    publish_action = "      - uses: pypa/gh-action-pypi-publish@"
    evidence_download = "name: release-evidence-${{ inputs.tag }}"
    final_asset_assertion = (
        "          test \"$(jq 'length' "
        '"$RUNNER_TEMP/missing-release-assets-before-pypi.json")" = "0"\n'
    )
    distribution_binding = r"""
          mapfile -d '' -t PUBLISH_DISTRIBUTIONS \
            < <(find dist -mindepth 1 -maxdepth 1 -print0)
          mapfile -d '' -t EVIDENCE_DISTRIBUTIONS \
            < <(
              find release-evidence -mindepth 1 -maxdepth 1 \
                \( -name '*.whl' -o -name '*.tar.gz' \) -print0
            )
          test "${#PUBLISH_DISTRIBUTIONS[@]}" -eq 2
          test "${#EVIDENCE_DISTRIBUTIONS[@]}" -eq 2
          for DISTRIBUTION_PATH in "${PUBLISH_DISTRIBUTIONS[@]}"; do
            test -f "$DISTRIBUTION_PATH"
            DISTRIBUTION_NAME="${DISTRIBUTION_PATH##*/}"
            EVIDENCE_PATH="release-evidence/$DISTRIBUTION_NAME"
            test -f "$EVIDENCE_PATH"
            cmp -- "$DISTRIBUTION_PATH" "$EVIDENCE_PATH"
          done
"""

    for requirement in (
        evidence_download,
        "path: release-evidence/",
        'test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT"',
        'test "$WORKFLOW_SHA" = "$RELEASE_COMMIT"',
        'test "$DISPATCH_SHA" = "$RELEASE_COMMIT"',
        'test "$DISPATCH_REF" = "refs/tags/$RELEASE_TAG"',
        ".release.commit release-evidence/manifest.json",
        ".release.tag release-evidence/manifest.json",
        ".release.workflow_sha release-evidence/manifest.json",
        ".release.dispatch_sha release-evidence/manifest.json",
        ".release.dispatch_ref release-evidence/manifest.json",
        "sha256sum --check SHA256SUMS",
        '--verify-release-assets "$RUNNER_TEMP/github-release.json"',
        "--asset-dir release-evidence",
        "missing-release-assets-before-pypi.json",
    ):
        assert requirement in publish_job

    assert publish_job.count(verification_step) == 1
    assert publish_job.count(publish_action) == 1
    assert publish_job.index(evidence_download) < publish_job.index(verification_step)
    assert publish_job.index(verification_step) < publish_job.index(publish_action)
    assert final_asset_assertion + distribution_binding + publish_action in publish_job


def test_release_workflow_actions_are_pinned_to_full_commits() -> None:
    for workflow_path in (
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/correctness.yml"),
        Path(".github/workflows/publish.yml"),
    ):
        actions = re.findall(
            r"^[ \t]*(?:-[ \t]+)?uses:[ \t]*[^@\s]+@([^\s]+)",
            workflow_path.read_text(),
            re.MULTILINE,
        )
        assert actions
        assert all(re.fullmatch(r"[0-9a-f]{40}", action) for action in actions)


def test_scheduled_correctness_workflow_uses_the_committed_lock() -> None:
    workflow = Path(".github/workflows/correctness.yml").read_text()
    assert workflow.count("uv sync --locked --group dev") == 2
    assert 'UV_LOCKED: "1"' in workflow
    assert "uv run --locked pytest tests/test_statcan_live.py" in workflow
