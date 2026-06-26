# SynthPopCan

[![CI](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml/badge.svg)](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml)
[![Documentation Status](https://readthedocs.org/projects/synthpopcan/badge/?version=latest)](https://synthpopcan.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/synthpopcan.svg)](https://pypi.org/project/synthpopcan/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <img src="assets/branding/logo/synthpopcan-logo-512.png" alt="SynthPopCan logo" width="220">
</p>

SynthPopCan is an early-stage project for building Canadian synthetic population tooling.

SynthPopCan is an independent research-software project. It is not affiliated
with, endorsed by, or sponsored by Statistics Canada or the Government of
Canada.

Near-term goals:

1. Provide a Python library and CLI that can create synthetic populations through IPF from Statistics Canada margin/control tables.
1. Build census microdata workflows for household- and person-level synthetic populations using a tree-based synthetic population generator plus calibration. The local 2016 Census material is the first available microdata source, but the tooling should be census-year agnostic.
1. Maintain a local web app for configuring runs, inspecting controls, generating from prepared models, validating outputs, and downloading results.

Broader SynthEco-style enrichment with cohort, environmental, school, healthcare, and food-access layers is intentionally deferred until the base population synthesis workflow is stable.

Detailed documentation is published at
<https://synthpopcan.readthedocs.io/>. The source files live under `docs/`;
start with `docs/index.rst` for task-based navigation to the web app, IPF from
StatCan margin tables, generated-from-model workflows, the beginner Python API,
and advanced microdata/model-training material.

Project planning and research notes are tracked separately:

- `PLANS.md`: current roadmap, open work, sequencing, and design decisions.
- `NOTES.md`: research synthesis from local materials and external literature.
- `docs/status.md`: completed implementation status and benchmark notes.
- `CHANGELOG.md`: public release notes.

## Quick Start

Install the published package from PyPI:

```bash
python -m pip install synthpopcan
```

Then inspect the command line:

```bash
synthpopcan --help
```

For a one-off command without installing the tool into your current
environment, use `uvx`:

```bash
uvx synthpopcan --help
uvx synthpopcan guide ipf
```

From a source checkout for development:

```bash
git clone https://github.com/dlq/synthpopcan.git
cd synthpopcan
uv sync
uv run synthpopcan --help
```

For installation details, see `docs/installation.md`.

## Where To Start

Most users should start in the Sphinx documentation rather than in this README:

| Task | Documentation |
| --- | --- |
| Use the local browser app | `docs/web-app.md` |
| Generate with IPF from margin/control tables | `docs/ipf.md`, `docs/controls.md`, `docs/statcan.md` |
| Use the beginner Python API | `docs/library-getting-started.md` |
| Work with local data layout and `data doctor` | `docs/data.md` |
| Inspect source files safely | `docs/sources.md` |
| Work with census microdata adapters | `docs/microdata.md` |
| Train, audit, package, or use tree models | `docs/tree.md` |
| Validate generated outputs | `docs/validate.md` |
| Check current implementation status | `docs/status.md` |

Build the documentation locally with:

```bash
uv run sphinx-build -W -b html docs docs/_build/html
```

## Developer Benchmarks

IPF benchmark fixtures are available as developer tooling, not as a normal user
workflow:

```bash
uv run python scripts/benchmark_ipf.py
```

Use `--seed-records` for smaller or larger local runs while checking
performance changes. Optional full-data tree-model smoke tests are documented
as status and planning evidence rather than as default test-suite requirements.

## Data Policy

Large, raw, private, or access-controlled data are not tracked in git.

- `data/raw/` is a local ignored cache for central raw inputs, including public Census Profile and WDS downloads.
- `data/private/` is a local ignored cache for access-controlled or sensitive later-use datasets.
- `references/` is a local ignored cache for copied papers, proposals, and legacy code references.

Public geography, school, healthcare, road, and environmental layers should generally be fetched from authoritative public sources such as Statistics Canada, open.canada.ca, donneesquebec.ca, and municipal/provincial open-data portals rather than stored in this repository.

Local-only manifests may exist inside ignored data directories to document what is present on a development machine.

## Model Packages

Reviewed model packages may be distributed with the project when they are
explicitly intended as public research artifacts. The installed package should
stay small: only the tiny demo model is bundled. Larger published models are
downloaded on demand with `synthpopcan models fetch MODEL_ID`.

Bundled model packages are not raw Census microdata. They should still be
treated as derived research artifacts with provenance, disclosure-risk checks,
and limitations. A model package being marked as a publishable candidate means
it passed the project's current checks; it is not a claim of official approval,
legal privacy certification, or fitness for every research use.

Before publishing a new model package, review `docs/data.md`, `docs/tree.md`,
`docs/release-checklist.md`, and `CONTRIBUTING.md`.
