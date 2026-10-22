"""Independent fixtures for function identity and the complexity review gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from support.readiness import audit

FUNCTION = "src/synthpopcan/example.py:Example.run"


@pytest.fixture
def complexity_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "src/synthpopcan").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    path = tmp_path / "src/synthpopcan/example.py"
    path.write_text("class Example:\n    def run(self, value):\n        return value\n")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"functions": {FUNCTION: 1}}))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["audit", "complexity", "--baseline", str(baseline)]
    )
    return path, baseline


def test_complexity_inventory_qualifies_methods(complexity_workspace):
    assert audit.complexity_inventory()["functions"] == {FUNCTION: 1}


def test_line_shifts_do_not_change_function_identity(complexity_workspace):
    source, _ = complexity_workspace
    source.write_text("# line numbers are not identity\n\n" + source.read_text())
    assert audit.main() == 0


def test_existing_function_growth_requires_review(complexity_workspace, capsys):
    source, _ = complexity_workspace
    source.write_text(
        "class Example:\n    def run(self, value):\n"
        "        if value:\n            return 1\n        return 0\n"
    )
    assert audit.main() == 1
    assert f"{FUNCTION}: 2 > 1" in capsys.readouterr().err


def test_reviewed_complexity_limit_is_accepted(complexity_workspace):
    source, baseline = complexity_workspace
    source.write_text(
        "class Example:\n    def run(self, value):\n"
        "        if value:\n            return 1\n        return 0\n"
    )
    baseline.write_text(json.dumps({"functions": {FUNCTION: 2}}))
    assert audit.main() == 0


def test_noqa_does_not_hide_an_overcomplex_new_function(complexity_workspace, capsys):
    source, _ = complexity_workspace
    source.write_text(
        source.read_text()
        + "\ndef new_function(value):  # noqa: C901\n"
        + "".join(f"    if value == {i}:\n        return {i}\n" for i in range(11))
    )
    assert audit.main() == 1
    assert "new_function: 12 > 10" in capsys.readouterr().err
