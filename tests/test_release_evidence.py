from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_release_evidence.py"
_SPEC = importlib.util.spec_from_file_location("build_release_evidence", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_manifest = _MODULE.build_manifest


def test_release_evidence_names_exact_release_and_hashes_files(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "synthpopcan-0.6.3-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    report = tmp_path / "correctness.xml"
    report.write_text("<testsuites/>")

    manifest = build_manifest(
        tag="v0.6.3",
        commit="a" * 40,
        version="0.6.3",
        files=[wheel, report],
    )

    assert manifest["schema_version"] == "synthpopcan-release-evidence-v1"
    assert manifest["release"] == {
        "tag": "v0.6.3",
        "commit": "a" * 40,
        "version": "0.6.3",
    }
    wheel_evidence = next(
        item for item in manifest["files"] if item["filename"].endswith(".whl")
    )
    assert wheel_evidence["sha256"] == hashlib.sha256(b"wheel").hexdigest()
    assert manifest["waived_checks"] == []


def test_release_evidence_rejects_identity_mismatch(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "synthpopcan-0.6.3-py3-none-any.whl"
    wheel.write_bytes(b"wheel")

    with pytest.raises(ValueError, match="does not match"):
        build_manifest(
            tag="v0.6.2",
            commit="b" * 40,
            version="0.6.3",
            files=[wheel],
        )
