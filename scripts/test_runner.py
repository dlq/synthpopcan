"""Run named test selections or conservatively select tests for changed files."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Only modules whose direct and downstream tests have been reviewed belong here.
# Everything else, including shared test helpers and configuration, runs all tests.
MODULE_TESTS: dict[str, tuple[str, ...]] = {}
SELECTIONS = {
    "full": ("tests",),
    "correctness": (
        "tests/test_ipf_correctness.py",
        "tests/test_model_correctness.py",
        "tests/test_small_area_correctness.py",
        "tests/test_reference_correctness.py",
    ),
    "localization": ("tests/test_localization_inventory.py",),
    "control-packs": (
        "tests/test_control_packs.py",
        "tests/test_conditional_pack_registry.py",
        "tests/test_conditional_control_failures.py",
        "tests/test_marital_status_controls.py",
        "tests/test_education_controls.py",
        "tests/test_labour_force_controls.py",
    ),
}


def select_affected(paths: list[str]) -> tuple[tuple[str, ...], str]:
    """Choose reviewed test paths; ambiguous, deleted, or empty changes run all."""
    if not paths:
        return SELECTIONS["full"], "no changed files; using full suite"
    selected: set[str] = set()
    for path in paths:
        if path in MODULE_TESTS:
            selected.update(MODULE_TESTS[path])
        elif (
            path.startswith("tests/test_")
            and path.endswith(".py")
            and path != "tests/test_coverage_gate.py"
            and "/" not in path.removeprefix("tests/")
            and (ROOT / path).is_file()
        ):
            selected.add(path)
        else:
            return SELECTIONS[
                "full"
            ], f"shared or unmapped change {path}; using full suite"
    if any(not (ROOT / path).is_file() for path in selected):
        return SELECTIONS["full"], "mapped test missing; using full suite"
    return tuple(sorted(selected)), "reviewed changed-file mapping"


def _git_paths(*arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, check=True
    )
    return [
        part.decode("utf-8", "surrogateescape")
        for part in result.stdout.split(b"\0")
        if part
    ]


def changed_paths(base: str) -> list[str]:
    """Include committed, staged, unstaged, and untracked changes."""
    paths = _git_paths("diff", "--no-renames", "--name-only", "-z", f"{base}...HEAD")
    paths += _git_paths("diff", "--no-renames", "--name-only", "-z", "HEAD")
    paths += _git_paths("ls-files", "--others", "--exclude-standard", "-z")
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "selection", choices=(*SELECTIONS, "affected"), nargs="?", default="full"
    )
    parser.add_argument(
        "--base", default="origin/main", help="Git base for affected selection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Explain selection without running tests"
    )
    args, pytest_args = parser.parse_known_args(argv)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    if args.selection == "affected":
        try:
            paths = changed_paths(args.base)
            selected, reason = select_affected(paths)
        except subprocess.CalledProcessError:
            selected, reason = (
                SELECTIONS["full"],
                "Git comparison failed; using full suite",
            )
    else:
        selected, reason = (
            SELECTIONS[args.selection],
            f"named selection {args.selection}",
        )
    command = [sys.executable, "-m", "pytest", *selected, *pytest_args]
    print(f"Selection: {reason}", flush=True)
    print("Tests:", *selected, flush=True)
    if args.dry_run:
        return 0
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
