"""Exercise the real pytest-cov gate, including its repository configuration."""

from __future__ import annotations

import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

pytestmark = pytest.mark.coverage_gate

CONFIG = Path(__file__).resolve().parents[1] / "pyproject.toml"


@pytest.mark.parametrize(
    "covered,threshold,expected_exit",
    [
        pytest.param(9450, 95, 1, id="94.50-fails"),
        pytest.param(9499, 95, 1, id="94.99-fails"),
        pytest.param(9500, 95, 0, id="95.00-passes"),
        pytest.param(9524, 95.25, 1, id="candidate-95.24-fails"),
        pytest.param(9525, 95.25, 0, id="candidate-95.25-passes"),
    ],
)
def test_pytest_cov_enforces_two_decimal_thresholds(
    tmp_path: Path, covered: int, threshold: float, expected_exit: int
) -> None:
    application = tmp_path / "application"
    application.mkdir()
    # Use the smallest exact ratio: 95% needs 20 statements, while 94.99%
    # really needs 10,000. This keeps the boundary proof without paying for
    # five large source fixtures on every test run.
    ratio = Fraction(covered, 10000)
    (application / "boundary.py").write_text(
        "value = 1\n" * (ratio.numerator - 1)
        + "def uncalled():\n"
        + "    value = 2\n" * (ratio.denominator - ratio.numerator)
    )
    (tmp_path / "test_boundary.py").write_text(
        "from application import boundary\n\n"
        "def test_imported_value():\n    assert boundary.value == 1\n"
    )
    # Nested pytest must not inherit the outer run's coverage startup settings,
    # data file or command-line options, nor auto-load unrelated user plugins.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("COV_CORE_")
        and key not in {"COVERAGE_FILE", "COVERAGE_PROCESS_START", "PYTEST_ADDOPTS"}
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "pytest_cov.plugin",
            "--cov",
            str(application),
            "--cov-branch",
            "--cov-config",
            str(CONFIG),
            "--cov-report=term-missing:skip-covered",
            f"--cov-fail-under={threshold}",
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
    )
    output = result.stdout + result.stderr
    assert result.returncode == expected_exit, output
    assert "1 passed" in output, output
    assert f"{covered / 100:.2f}%" in output, output
    assert (
        "FAIL Required test coverage" in output
        if expected_exit
        else "Required test coverage" in output
    )
