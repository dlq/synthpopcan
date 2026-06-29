# Changelog

All notable public changes to SynthPopCan are tracked here.

## Unreleased

- Added the Canada 2016 all-fields linked model package to the downloadable
  model registry as `canada-2016-all-fields`.
- Switched downloadable model release assets to gzip-compressed JSON while
  keeping the local model cache as normal JSON files.
- Added Census Profile household-size recoding that preserves exact
  `household_size` values and fits grouped controls through
  `household_size_group`.
- Added largest-residual and suggested-next-step diagnostics to small-area
  calibration reports and CLI summaries.
- Added small-area calibration preflight checks for missing candidate columns
  and categories before IPF fitting starts.
- Added `geo estimate-run` to preview small-area run scale and recommend
  whether the web app, CLI, or Python API is the right surface before launching
  a large calibration.

## 0.2.1 - 2026-06-28

Polish and CI hardening.

- Added a clean-install smoke-test CI job that builds the wheel, installs it in
  an isolated environment, and exercises key CLI entry points including bundled
  demo generation.
- Added an end-to-end doc-example test that runs the five-command IPF workflow
  from `docs/installation.md` against the repo's fixture files.
- Fixed "Miss" column heading to "Missing" in the IPF input check table.
- Replaced `(s)` plural shorthand with proper plurals in the calibrate-linked
  summary message.
- Replaced vague "process" action verb with "read or write" in the
  calibrate-linked file-access error message.

## 0.2.0 - 2026-06-28

Small-area linked synthesis MVP.

- Added `small-area calibrate-linked` command and `calibrate_small_area_linked`
  API entry point to assign linked household/person candidates to target
  geographies using Census Profile controls.
- Added `geo` command group: `build-controls`, `map`, `prepare-boundaries`, and
  `synthesize-from-package` subcommands covering the end-to-end small-area
  workflow in a single command.
- Added StatCan Census Profile 2016 fetch and preparation helpers for census
  tracts and aggregate dissemination areas.
- Added geography-level residual summaries to calibration reports.
- Expanded the prepared model catalogue to include all provinces, territories,
  and major CMAs.
- Vectorized IPF and population expansion using NumPy (~2.3× speedup); added
  threaded IPF loop and pool-size subsampling for large candidate sets.
- Renamed `--geography-*` CLI flags to `--geo-*` for consistency.
- Declared pandas as an explicit dependency.
- Enforced public/private distinction across library modules with `__all__`.
- Added pre-commit hooks for ruff, pyright, and pytest.
- Raised test coverage from 95% to 99.5% (552 tests).

## 0.1.1 - 2026-06-26

Public repository polish release.

- Added README badges for CI, documentation, PyPI, and license status.
- Added `CITATION.cff` for research software citation metadata.
- Added GitHub issue templates for bugs, feature requests, and model release
  reviews.
- Added `docs/release-checklist.md` for package and model asset releases.
- Added a CI Python formatting check with `ruff format --check`.
- Normalized documentation links to `synthpopcan.readthedocs.io`.
- Added repository topics for discovery on GitHub.

## 0.1.0 - 2026-06-25

Initial public release.

- Added the `synthpopcan` Python package and CLI.
- Added IPF workflows for seed rows and normalized margin/control tables.
- Added Statistics Canada WDS search, inspection, fetch, and IPF-preparation
  helpers.
- Added census microdata adapters, validation helpers, and data layout checks.
- Added tree-based household/person synthetic population generation workflows.
- Added local web app support for beginner IPF and generated-from-model paths.
- Added downloadable model package registry with GitHub Release assets.
- Added Sphinx documentation, CI, PyPI publishing workflow, and Read the Docs
  configuration.
