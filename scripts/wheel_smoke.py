"""Smoke-test an installed wheel from outside the source checkout."""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

from click.testing import CliRunner

import synthpopcan
from synthpopcan.cli import cli
from synthpopcan.ipf import IPFMargin, fit_ipf

package_path = Path(synthpopcan.__file__).resolve()
source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
if source_root in package_path.parents:
    raise RuntimeError(f"wheel smoke imported from the checkout: {package_path}")
assert "site-packages" in package_path.parts

result = fit_ipf(
    [{"age": "young"}, {"age": "old"}],
    [IPFMargin(("age",), {("young",): 6.0, ("old",): 4.0})],
)
assert result.converged
assert result.weights == [6.0, 4.0]
assert files("synthpopcan").joinpath("web/index.html").is_file()

help_result = CliRunner().invoke(cli, ["--help"])
assert help_result.exit_code == 0
assert "SynthPopCan" in help_result.output

print(f"Installed wheel smoke passed: {package_path}")
