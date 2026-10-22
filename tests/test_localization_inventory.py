"""Inventory completeness checked against independent repository interfaces."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from support.readiness import audit

from synthpopcan._interface import load_public_interface_contract
from synthpopcan.webapi import create_web_app
from synthpopcan.webapp import get_webapp_root

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def inventory():
    return audit.localization_inventory()


def repository_files() -> set[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "src/synthpopcan",
            "docs",
            "adr",
            "plans",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return set(result.stdout.rstrip("\0").split("\0"))


def test_cli_inventory_contains_every_contract_path_once(inventory):
    expected = {
        item["path"] for item in load_public_interface_contract()["cli"]["commands"]
    }
    actual = [item["path"] for item in inventory["commands"]]
    assert set(actual) == expected
    assert len(actual) == len(expected), (
        "aliases must have distinct paths, without duplicates"
    )


def test_route_inventory_matches_the_registered_application(inventory, tmp_path):
    app = create_web_app(static_root=get_webapp_root(), workspace=tmp_path)
    try:
        expected = {
            (route.path, method)
            for route in app.routes
            for method in (getattr(route, "methods", None) or ())
        }
    finally:
        app.state.job_manager.shutdown()
    actual = [
        (route["path"], method)
        for route in inventory["routes"]
        for method in route["method"].split(",")
    ]
    assert set(actual) == expected
    assert len(actual) == len(expected)


def test_every_repository_owned_localization_file_is_classified(inventory):
    extensions = {".py", ".js", ".mjs", ".html", ".css", ".md", ".rst", ".json"}
    expected = {path for path in repository_files() if Path(path).suffix in extensions}
    assert set(inventory["files"]) == expected


@pytest.mark.parametrize(
    "path,classification",
    [
        pytest.param(
            "src/synthpopcan/cli_errors.py", "mixed-presentation", id="cli-errors"
        ),
        pytest.param(
            "docs/records/zenodo-2026-10-07.md",
            "historical-or-maintainer",
            id="historical-evidence",
        ),
        pytest.param(
            "src/synthpopcan/contracts/public-interface-v1.json",
            "machine-contract-or-source",
            id="machine-contract",
        ),
        pytest.param("docs/command-line.md", "user-documentation", id="user-guide"),
        pytest.param(
            "src/synthpopcan/controls.py", "domain-or-workflow", id="domain-messages"
        ),
    ],
)
def test_file_classification_respects_translation_boundaries(
    inventory, path, classification
):
    assert inventory["files"][path].split(":", 1)[0] == classification


def test_python_literal_inventory_covers_all_package_sources_with_valid_hashes(
    inventory,
):
    expected = {
        path
        for path in repository_files()
        if path.startswith("src/synthpopcan/") and path.endswith(".py")
    }
    assert set(inventory["python_literals"]) == expected
    for filename, entry in inventory["python_literals"].items():
        source = (ROOT / filename).read_bytes()
        assert entry["source_sha256"] == hashlib.sha256(source).hexdigest(), filename
        line_count = len(source.splitlines())
        for locations in entry["roles"].values():
            assert locations == sorted(set(locations)), filename
            assert all(1 <= line <= line_count for line in locations), filename


def test_literal_roles_and_hashes_follow_a_known_source_fixture(tmp_path, monkeypatch):
    package = tmp_path / "src/synthpopcan"
    package.mkdir(parents=True)
    path = package / "sample.py"
    source = (
        '"""Maintainer documentation."""\n'
        'VALUES = {"schema_key": "Human prose."}\n'
        "def example(name):\n"
        '    """Command help."""\n'
        '    raise ValueError(f"Missing {name}.")\n'
    )
    path.write_text(source)
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    result = audit._python_literal_inventory()["src/synthpopcan/sample.py"]
    assert result == {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "roles": {
            "docstring-review-cli-help-or-maintainer": [1, 4],
            "machine-key-retain": [2],
            "human-or-source-review": [2, 5],
        },
    }
    updated = source + '\nMESSAGE = "New human message."\n'
    path.write_text(updated)
    result = audit._python_literal_inventory()["src/synthpopcan/sample.py"]
    assert result["source_sha256"] == hashlib.sha256(updated.encode()).hexdigest()
    assert result["roles"]["human-or-source-review"] == [2, 5, 7]


def test_inventory_declares_canonical_locales_without_claiming_translation(inventory):
    assert inventory["canonical_locales"] == ["en-CA", "fr-CA"]
    assert inventory["default_locale"] == "en-CA"
    assert "inventory only" in inventory["translation_status"]
