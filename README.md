# SynthPopCan

[![CI](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml/badge.svg)](https://github.com/dlq/synthpopcan/actions/workflows/ci.yml)
[![Extended correctness](https://github.com/dlq/synthpopcan/actions/workflows/correctness.yml/badge.svg)](https://github.com/dlq/synthpopcan/actions/workflows/correctness.yml)
[![Documentation Status](https://readthedocs.org/projects/synthpopcan/badge/?version=latest)](https://synthpopcan.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/synthpopcan.svg)](https://pypi.org/project/synthpopcan/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21461463.svg)](https://doi.org/10.5281/zenodo.21461463)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/dlq/synthpopcan/blob/main/LICENSE)

<p align="center">
  <img src="https://raw.githubusercontent.com/dlq/synthpopcan/main/assets/branding/logo/synthpopcan-logo-512.png" alt="SynthPopCan logo" width="220">
</p>

SynthPopCan helps researchers create, inspect, and validate modelled Canadian
households and people from Census-derived data. It supports reproducible work
without requiring researchers to expose private source data or become software
developers first.

SynthPopCan is an independent research-software project. It is not affiliated
with, endorsed by, or sponsored by Statistics Canada or the Government of
Canada.

Core workflows:

1. Provide a Python library and CLI that can create synthetic populations through IPF from Statistics Canada margin/control tables.
1. Maintain explicit 2016 and 2021 Census microdata workflows for household-
   and person-level synthetic populations using tree-based generation plus
   calibration, while keeping source adapters and metadata appropriately
   census-vintage-specific.
1. Maintain a local web app for configuring runs, inspecting controls, generating from prepared models, validating outputs, and downloading results.

Version `1.0.0` establishes a stable, explicitly bounded interface for
research scripts and artifacts. Its packaged
[1.x compatibility contract](https://synthpopcan.readthedocs.io/en/latest/compatibility.html)
freezes the documented CLI, curated Python API, callable signatures, and
supported persisted schemas while keeping later additive extension possible.
It carries forward the bounded calibration and small-area evidence from
`0.9.0` without turning that evidence into a universal representativeness,
privacy, or fitness claim.

It also includes a complete
[2016/2021 field-eligibility inventory](https://synthpopcan.readthedocs.io/en/latest/field-eligibility.html), a
[bilingual Quebec 2021 case study](https://synthpopcan.readthedocs.io/en/latest/case-study-quebec-2021.html),
dated preservation and software-management records, and an accepted
open-by-default prepared-model policy. All 32 public Census-derived model
concepts now point to verified, non-overwriting versions with embedded scoped
licensing and preserved source provenance. The release boundary and post-1.0
research tracks are recorded in
[PLANS.md](https://github.com/dlq/synthpopcan/blob/main/PLANS.md).

Detailed documentation is published at
<https://synthpopcan.readthedocs.io/>. The source files live under
[`docs/`](https://github.com/dlq/synthpopcan/tree/main/docs); start with
[`docs/index.rst`](https://synthpopcan.readthedocs.io/en/latest/) for task-based
navigation to the web app, IPF from StatCan margin tables,
generated-from-model workflows, the beginner Python API, and advanced
microdata/model-training material.

The development branch and the
[`latest` documentation](https://synthpopcan.readthedocs.io/en/latest/) may
describe the next release before it reaches PyPI. The PyPI badge above identifies
what `pip install synthpopcan` currently installs; use the
[`stable` documentation](https://synthpopcan.readthedocs.io/en/stable/) for that
published version. Maintained Can-FED and ODEF adapters are included in `0.7.2`
and later.

Project records have distinct jobs:

| Record | Use it for |
| --- | --- |
| [`PLANS.md`](https://github.com/dlq/synthpopcan/blob/main/PLANS.md) | Current maintenance priorities, conditional research tracks, deferred scope, and open decisions |
| [`plans/`](https://github.com/dlq/synthpopcan/tree/main/plans) | Detailed active scopes and archived implementation evidence |
| [`CHANGELOG.md`](https://github.com/dlq/synthpopcan/blob/main/CHANGELOG.md) | Observable changes grouped by public release |
| [`adr/`](https://github.com/dlq/synthpopcan/tree/main/adr) | Durable architecture decisions, alternatives, and consequences |
| [`CORRECTNESS.md`](https://github.com/dlq/synthpopcan/blob/main/CORRECTNESS.md) | Current tested correctness claims, evidence, limitations, and reproduction commands |
| [`NOTES.md`](https://github.com/dlq/synthpopcan/blob/main/NOTES.md) | Index of dated historical research and design syntheses, not current project status |
| [`docs/stewardship.md`](https://synthpopcan.readthedocs.io/en/latest/stewardship.html) | Supported environments, maintenance expectations, licensing, preservation identifiers, and dated records |

## Quick Start

These commands use a Unix-style shell. Windows readers should first complete
the [WSL setup in the Installation guide](https://synthpopcan.readthedocs.io/en/latest/installation.html),
then run the same commands inside the Ubuntu terminal.

Install the published package from PyPI:

**Network required for installation.**

```bash
python3 -m pip install synthpopcan
```

The base installation is enough to generate from portable frequency or CART
models. Starting with `0.7.0`, only researchers training new CART models need
`python3 -m pip install "synthpopcan[model-build]"`.

For a guided first look, start the local browser workbench:

```bash
synthpopcan serve
```

It opens forms, previews, run history, and downloads on this computer only. The
[local web app guide](https://synthpopcan.readthedocs.io/en/latest/web-app.html)
includes fictional teaching data and
explains what stays on disk. Use the command line below when the work needs to
be scripted or repeated exactly.

Then inspect the command line:

```bash
synthpopcan --help
```

Run a small offline smoke test with the bundled fictional model:

**Runnable teaching example.** Enter both commands in order.

```bash
synthpopcan models generate demo-linked-household-person \
  --households 10 \
  --condition "geo=Demo North" \
  --out synthpopcan-quickstart \
  --random-seed 42
synthpopcan validate linked synthpopcan-quickstart
```

This verifies linked household/person generation, but it does not create a
representative Canadian population. The documentation explains how to choose
research sources, controls, and model packages.

For a one-off command without installing the tool into the current environment,
use `uvx`:

**Network and `uv` required.** See the Installation guide before using this
route if `uvx --version` is not already available.

```bash
uvx synthpopcan --help
uvx synthpopcan guide ipf
uvx synthpopcan guide model
uvx synthpopcan guide small-area
```

From a source checkout for development:

**Source checkout, network, Git, and `uv` required.**

```bash
git clone https://github.com/dlq/synthpopcan.git
cd synthpopcan
uv sync
uv run synthpopcan --help
```

For installation details, see
[`docs/installation.md`](https://synthpopcan.readthedocs.io/en/latest/installation.html).

## Where To Start

Most readers should start in the Sphinx documentation rather than in this
README:

| Task | Documentation |
| --- | --- |
| Choose a first workflow | [`docs/getting-started.md`](https://synthpopcan.readthedocs.io/en/latest/getting-started.html) |
| Start a reproducible command-line workflow | [`docs/command-line.md`](https://synthpopcan.readthedocs.io/en/latest/command-line.html) |
| Use the local browser app | [`docs/web-app.md`](https://synthpopcan.readthedocs.io/en/latest/web-app.html) |
| Generate with IPF from margin/control tables | [`docs/ipf.md`](https://synthpopcan.readthedocs.io/en/latest/ipf.html), [`docs/controls.md`](https://synthpopcan.readthedocs.io/en/latest/controls.html), [`docs/statcan.md`](https://synthpopcan.readthedocs.io/en/latest/statcan.html) |
| Assign linked households and people to small areas | [`docs/small-area.md`](https://synthpopcan.readthedocs.io/en/latest/small-area.html) |
| Fetch verified display-only map boundaries | [`docs/geodata.md`](https://synthpopcan.readthedocs.io/en/latest/geodata.html) |
| Attach governed external context as a sidecar layer | [`docs/enrichment.md`](https://synthpopcan.readthedocs.io/en/latest/enrichment.html) |
| Hand a validated linked population to another tool | [`docs/exchange.md`](https://synthpopcan.readthedocs.io/en/latest/exchange.html) |
| Use the beginner Python API | [`docs/library-getting-started.md`](https://synthpopcan.readthedocs.io/en/latest/library-getting-started.html) |
| Work with local data layout and `data doctor` | [`docs/data.md`](https://synthpopcan.readthedocs.io/en/latest/data.html) |
| Inspect source files safely | [`docs/data.md`](https://synthpopcan.readthedocs.io/en/latest/data.html), [`docs/statcan.md`](https://synthpopcan.readthedocs.io/en/latest/statcan.html), [`docs/microdata.md`](https://synthpopcan.readthedocs.io/en/latest/microdata.html) |
| Work with census microdata adapters | [`docs/microdata.md`](https://synthpopcan.readthedocs.io/en/latest/microdata.html) |
| Train, audit, package, or use tree models | [`docs/tree.md`](https://synthpopcan.readthedocs.io/en/latest/tree.html) |
| Validate generated outputs | [`docs/validate.md`](https://synthpopcan.readthedocs.io/en/latest/validate.html) |
| Understand correctness evidence and limitations | [`CORRECTNESS.md`](https://github.com/dlq/synthpopcan/blob/main/CORRECTNESS.md) |
| Check current priorities and conditional research | [`PLANS.md`](https://github.com/dlq/synthpopcan/blob/main/PLANS.md), [`plans/README.md`](https://github.com/dlq/synthpopcan/blob/main/plans/README.md) |
| Review completed release history | [`CHANGELOG.md`](https://github.com/dlq/synthpopcan/blob/main/CHANGELOG.md) |

Build the documentation locally with:

**Source checkout required.** Contributor setup is documented in
[`CONTRIBUTING.md`](https://github.com/dlq/synthpopcan/blob/main/CONTRIBUTING.md).

```bash
uv run sphinx-build -W -b html docs docs/_build/html
```

## Data Policy

Large, raw, private, or access-controlled data are not tracked in git. Local
source caches, derived artifacts, and scratch work have separate roles and must
retain their provenance and access classification. See the maintained
[`Data and Local Workspace`](https://synthpopcan.readthedocs.io/en/latest/data.html)
chapter for the directory contract, licensing boundary, and safe handling
rules.

## Model Packages

Only the tiny fictional demo model is bundled. Larger reviewed models are
downloaded on demand. List the current catalogue and generate from a selected
package with:

```bash
synthpopcan models fetch quebec-2021-all-fields
synthpopcan models generate quebec-2021-all-fields \
  --households 1000 --out quebec-2021-population/
```

Prepared packages are derived research artifacts, not raw Census microdata or
claims of official approval, privacy certification, or universal fitness. See
[Generate From a Model Package](https://synthpopcan.readthedocs.io/en/latest/tree-generate.html)
for ordinary use and [Tree Models](https://synthpopcan.readthedocs.io/en/latest/tree.html)
for training, audit, packaging, licensing, and release guidance.

## How To Cite

Releases and prepared model packages are archived on Zenodo, so cite whichever
matches what your work actually depended on.

| You used | Cite | DOI |
| --- | --- | --- |
| SynthPopCan generally | The concept DOI, which always resolves to the newest release | [10.5281/zenodo.21461463](https://doi.org/10.5281/zenodo.21461463) |
| SynthPopCan 1.0.0 | The archived 1.0.0 version DOI | [10.5281/zenodo.21961301](https://doi.org/10.5281/zenodo.21961301) |
| SynthPopCan 0.9.0 | The archived 0.9.0 version DOI | [10.5281/zenodo.21876960](https://doi.org/10.5281/zenodo.21876960) |
| SynthPopCan 0.7.0 | The archived 0.7.0 version DOI | [10.5281/zenodo.21743129](https://doi.org/10.5281/zenodo.21743129) |
| A prepared model package | That package's own DOI, listed on its Zenodo record | one per package |

For reproducibility, prefer the **version** DOI for the release and the model
package DOI for each package you generated from: together they pin the exact
code and the exact artifact, and every model record publishes the checksums
needed to verify the file you downloaded.

Citation metadata lives in
[`CITATION.cff`](https://github.com/dlq/synthpopcan/blob/main/CITATION.cff),
which GitHub renders as a ready-made citation from the sidebar.

The source history through `v1.0.0` is also independently preserved in
[Software Heritage](https://archive.softwareheritage.org/swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845;origin=https://github.com/dlq/synthpopcan).
Use its SWHIDs to identify source objects; continue to use the release DOI and
artifact checksums to identify the software and model bytes used in research.
The earlier capture through `v0.9.0` remains available in the dated
[preservation record](https://synthpopcan.readthedocs.io/en/latest/records/software-heritage-2026-08-15.html).

Prepared model packages are derived from Statistics Canada public use microdata
files under the
[Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence).
The catalogue, archive records, and current registered package bytes carry the
required attribution and machine-readable rights contract. Historical package
versions remain available under their original identifiers and checksums for
reproducibility; the registry now selects the verified non-overwriting
`v1.0.0-rights.1` versions. See
[`docs/data.md`](https://synthpopcan.readthedocs.io/en/latest/data.html) for the
full attribution and licensing terms.
The accepted open-by-default policy in
[`ADR-0014`](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md)
offers CC BY 4.0 only for original prepared-model rights the package author
owns or controls. That scoped grant is cumulative with the continuing
Statistics Canada conditions; it does not cover source Information, facts, or
unprotectable results, and it does not relax privacy or provenance safeguards.
The fail-closed existing-record correction implementation passed independent
review, and all 32 metadata corrections, 32 non-overwriting versions, remote
byte checks, and 32 registry updates completed on 2026-08-16. The
[durable correction record](https://synthpopcan.readthedocs.io/en/latest/records/prepared-model-archive-correction-2026-08-16.html)
preserves sanitized evidence. External review remains welcome but is not a
`1.0.0` gate.

## Development Acknowledgement

Development of SynthPopCan has been supplemented by the use of large language
models for tasks including code generation, review, testing, documentation, and
research assistance. All resulting contributions remain subject to human review
and the project's automated correctness and quality checks. Responsibility for
the project and its releases rests with its maintainer.
