"""Opt-in profiler launcher at the CLI worker boundary, not in numerical code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def profile_cli_worker(arguments: list[str], name: str, directory: Path) -> None:
    """Give a spawned fitting worker its own complete sampling profile.

    Sampling a multiprocessing supervisor alone misses its worker threads on
    some platforms. Run the same conventional CSV calibration CLI under Scalene
    and retain its report files as usual. No parameters or numerical functions
    change. This path is used only by the explicit profiling harness.
    """
    python = Path(sys.prefix) / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    directory.mkdir(parents=True, exist_ok=True)
    profile = directory / f"{name}.json"
    log = directory / f"{name}.log"
    command = [
        str(python),
        "-m",
        "scalene",
        "run",
        "--cpu-only",
        "--profile-all",
        "--profile-only",
        str(Path(__file__).resolve().parents[1]),
        "--no-stacks",
        "--profile-interval",
        "60",
        "--outfile",
        str(profile),
        "-m",
        "synthpopcan.cli",
        "---",
        *arguments,
    ]
    (directory / f"{name}-command.json").write_text(
        json.dumps(command, indent=2) + "\n"
    )
    with log.open("w") as handle:
        result = subprocess.run(
            command, stdout=handle, stderr=subprocess.STDOUT, check=False
        )
    if result.returncode:
        raise ValueError(f"Profiled calibration worker {name} failed. See {log}.")
    if not profile.is_file():
        raise ValueError(
            f"Worker {name} did not produce a sampling profile; see {log}."
        )
