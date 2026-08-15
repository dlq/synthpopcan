"""Exercise the Quebec case-study interface from an installed wheel.

The released Quebec model is deliberately not downloaded in release CI. The
smoke checks its installed catalogue metadata, then runs the analogous fetch,
inspect, generate, and validate path with the bundled fictional demo under its
own identity. It never relabels synthetic bytes as a Census-derived package.
"""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

import synthpopcan
from synthpopcan.cli import cli

MODEL_ID = "quebec-2021-all-fields"
DEMO_MODEL_ID = "demo-linked-household-person"

# Keep the actual public sequence machine-readable so the documentation test
# catches command drift without downloading the 106 MB Quebec package in CI.
COMMANDS = (
    ("models", "fetch", MODEL_ID),
    ("models", "show", MODEL_ID, "--format", "json"),
    ("models", "build", "inspect", MODEL_ID, "--format", "json"),
    (
        "models",
        "generate",
        MODEL_ID,
        "--households",
        "1000",
        "--out",
        "quebec-2021-case-study/",
        "--random-seed",
        "20210921",
    ),
    ("validate", "linked", "quebec-2021-case-study/", "--format", "json"),
)

# The installed-wheel smoke uses the demo's honest synthetic identity. The one
# real-model command is catalogue-only and therefore remains offline.
SMOKE_COMMANDS = (
    ("models", "show", MODEL_ID, "--format", "json"),
    ("models", "fetch", DEMO_MODEL_ID),
    ("models", "show", DEMO_MODEL_ID, "--format", "json"),
    ("models", "build", "inspect", DEMO_MODEL_ID, "--format", "json"),
    (
        "models",
        "generate",
        DEMO_MODEL_ID,
        "--households",
        "1000",
        "--out",
        "fictional-case-study-smoke/",
        "--random-seed",
        "20210921",
    ),
    ("validate", "linked", "fictional-case-study-smoke/", "--format", "json"),
)
SMOKE_COMMAND_OUTPUTS = (
    "quebec-2021-model-metadata.json",
    None,
    "fictional-model-metadata.json",
    "fictional-model-inspection.json",
    None,
    "fictional-case-study-smoke/validation.json",
)


def _assert_installed_wheel() -> None:
    package_path = Path(synthpopcan.__file__).resolve()
    source_root = Path(os.environ["SYNTHPOPCAN_SOURCE_ROOT"]).resolve()
    if source_root in package_path.parents:
        raise RuntimeError(f"case-study smoke imported checkout: {package_path}")
    if "site-packages" not in package_path.parts:
        raise RuntimeError(f"case-study smoke did not import a wheel: {package_path}")


def main() -> None:
    _assert_installed_wheel()
    os.environ["SYNTHPOPCAN_MODEL_CACHE"] = str(Path("model-cache").resolve())

    runner = CliRunner()
    for command, output_path in zip(SMOKE_COMMANDS, SMOKE_COMMAND_OUTPUTS, strict=True):
        result = runner.invoke(cli, command, catch_exceptions=False)
        if result.exit_code != 0:
            raise RuntimeError(
                f"case-study smoke failed ({' '.join(command)}):\n{result.output}"
            )
        if output_path is not None:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result.output)

    output = Path("fictional-case-study-smoke")
    assert (output / "households.csv").is_file()
    assert (output / "persons.csv").is_file()
    assert (output / "manifest.json").is_file()
    assert (output / "validation.json").is_file()
    print(
        "Installed-wheel case-study interface smoke passed with the fictional "
        "demo; released Quebec model bytes were not tested."
    )


if __name__ == "__main__":
    main()
