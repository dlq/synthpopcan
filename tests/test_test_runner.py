"""Safety of the lightweight local and CI test selector."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/test_runner.py"
SPEC = importlib.util.spec_from_file_location("test_selection_runner", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_only_reviewed_test_files_are_selected(tmp_path, monkeypatch):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_first.py").touch()
    (tests / "test_second.py").touch()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    selected, reason = runner.select_affected(
        ["tests/test_second.py", "tests/test_first.py"]
    )
    assert selected == ("tests/test_first.py", "tests/test_second.py")
    assert "reviewed" in reason


@pytest.mark.parametrize(
    "paths",
    [
        [],
        ["src/synthpopcan/ipf.py"],
        ["tests/conftest.py"],
        ["tests/test_coverage_gate.py"],
        ["tests/test_deleted.py"],
        ["README.md"],
    ],
)
def test_unknown_shared_empty_or_deleted_changes_run_all(paths):
    selected, reason = runner.select_affected(paths)
    assert selected == ("tests",)
    assert "full suite" in reason


def test_unmapped_change_overrides_focused_test():
    selected, _ = runner.select_affected(["tests/test_cli.py", "pyproject.toml"])
    assert selected == ("tests",)


def test_reviewed_source_mapping_runs_its_tests_and_missing_targets_fall_back(
    tmp_path, monkeypatch
):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_leaf.py").touch()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        runner, "MODULE_TESTS", {"src/leaf.py": ("tests/test_leaf.py",)}
    )
    assert runner.select_affected(["src/leaf.py"])[0] == ("tests/test_leaf.py",)
    (tests / "test_leaf.py").unlink()
    assert runner.select_affected(["src/leaf.py"])[0] == ("tests",)


def test_dry_run_explains_named_selection():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "localization", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "named selection localization" in result.stdout
    assert "tests/test_localization_inventory.py" in result.stdout


def test_failed_git_comparison_runs_full_suite(monkeypatch, capsys):
    def fail(_base):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(runner, "changed_paths", fail)
    assert runner.main(["affected", "--dry-run"]) == 0
    assert "Git comparison failed; using full suite" in capsys.readouterr().out


def test_affected_selection_includes_committed_staged_and_untracked_changes(
    tmp_path, monkeypatch
):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "fictional@example.invalid")
    git("config", "user.name", "Fictional Contributor")
    tests = tmp_path / "tests"
    tests.mkdir()
    for name in ("first", "second"):
        (tests / f"test_{name}.py").write_text("# fixture\n")
    git("add", "tests")
    git("commit", "-qm", "initial")
    base = git("rev-parse", "HEAD")
    (tests / "test_first.py").write_text("# committed change\n")
    git("commit", "-qam", "change")
    (tests / "test_second.py").write_text("# staged change\n")
    git("add", "tests/test_second.py")
    (tests / "test_third.py").write_text("# untracked change\n")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    assert runner.changed_paths(base) == [
        "tests/test_first.py",
        "tests/test_second.py",
        "tests/test_third.py",
    ]


def test_runner_propagates_pytest_exit_status(monkeypatch):
    def run(command, **kwargs):
        assert command[1:3] == ["-m", "pytest"]
        assert command[-1] == "-q"
        return subprocess.CompletedProcess(command, 5)

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["localization", "--", "-q"]) == 5
