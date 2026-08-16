# Contributing

SynthPopCan is early-stage research software. Keep changes small, reviewable,
and grounded in the existing code and documentation structure.

Contributions do not have to be code. Reports about unclear terminology,
documentation gaps, inaccessible workflows, research-method concerns, and
small public teaching examples are especially useful. Open a question or
feature issue if you want to discuss an idea before preparing a change. Never
post private data, raw Census microdata rows, credentials, or controlled files.

## Development Setup

Install Python 3.11 or newer, `uv`, and Node.js 24. Then install the Python and
documentation dependencies:

```bash
uv sync --group dev --group docs
```

Install web tooling:

```bash
npm ci
```

Run the normal checks before opening a pull request:

```bash
./scripts/check.sh
```

This runs Python linting, formatting, type checks, tests, a warning-clean docs
build, web formatting/linting, JavaScript unit tests, and the Playwright browser
scenarios. Install the Playwright browser once with `npx playwright install chromium` if it is not already available.

For a small documentation or Python-only change, use the relevant faster checks
while iterating:

```bash
uv run ruff check src tests scripts
uv run pyright src
uv run pytest path/to/relevant_test.py
uv run --group docs mdformat --check README.md CONTRIBUTING.md docs
```

Run `./scripts/check.sh` before requesting final review when practical. If a
local check cannot run on your machine, say which check and why in the pull
request instead of leaving reviewers to infer it.

## Pull Requests

Before opening a pull request, search existing issues and pull requests, keep
the change focused, and add or update tests and user documentation where the
observable behavior changes. Draft pull requests are welcome for early
feedback.

In the pull request description, explain the user or research problem, the
chosen change, the checks you ran, and any data, correctness, compatibility, or
privacy implications. A maintainer may ask for revisions; keep follow-up
commits reviewable. Once checks and review are complete, a maintainer will merge
the change. Contributors do not need release permissions or access to private
research data.

Changes to numerical kernels, model generation, linked records, small-area
artifacts, or validation must update the relevant claim and evidence in
[`CORRECTNESS.md`](CORRECTNESS.md). A regression test should demonstrate the
failure before or alongside its fix and should use an independent oracle or
invariant where practical.

## Module Boundaries

Keep dependency direction easy to reason about:

- `synthpopcan.__init__` re-exports the small beginner API from
  `synthpopcan.api`;
- `synthpopcan.api` is the stable notebook and short-script surface for
  beginner workflows;
- `cli.py`, `cli_*.py`, `cli_output.py`, and `console.py` are CLI and terminal
  adapters;
- core workflow modules such as `ipf`, `controls`, `tree`, `microdata`,
  `validation`, `diagnostics`, `small_area_synthesis`, `small_area_controls`,
  `calibration`, `statcan`, `geodata`, `sources`, `localdata`, `map_render`, and
  `benchmarks` should stay independent of CLI and UI code;
- `webapp.py`, `web_wds.py`, and `src/synthpopcan/web/*.mjs` are local web app
  and browser-side adapters.

Adapters may depend on core modules, but core modules should not import Click,
Rich, `synthpopcan.cli*`, `synthpopcan.console`, `synthpopcan.web`, or
`synthpopcan.webapp`. The architecture checks in `tests/test_architecture.py`
enforce these boundaries as part of the normal `uv run pytest` gate.

## Architecture Decisions

Repository-wide decisions and their rationale live in
[`adr/`](adr/README.md). Read the relevant records before changing a public
schema, dependency direction, execution model, data boundary, or publication
authority.

Add an ADR when a proposed choice will constrain several interfaces or future
implementations, would be costly to reverse, or establishes an important
compatibility, data, privacy, or distribution boundary. Use
[`adr/template.md`](adr/template.md), and supersede an accepted decision with a
new record rather than rewriting its original rationale.

## Data And Model Safety

Do not commit raw Census microdata, downloaded bulk data caches, generated CSV
outputs, private research datasets, or local reference corpora. Keep those files
under ignored paths such as `data/raw`, `data/private`, `references`, `runs`, or
`outputs`.

Reviewed model packages may be published only when they are explicitly intended
for distribution and carry provenance, disclosure-risk metadata, and the
validated embedded prepared-model licensing contract. Publication remains
fail-closed unless the accepted policy, completed implementation, completed
execution, tracked evidence, and installed registry gates in
[`ADR-0014`](adr/0014-separate-prepared-model-and-source-licensing.md) agree.
Large packages should be uploaded as GitHub Release assets and listed in the
model registry, not bundled into the normal Python package.

Before contributing a model artifact:

- verify it contains no raw source rows or source identifiers;
- inspect its provenance and redistribution notes;
- validate its embedded licensing object and preserve that object in every
  derived manifest;
- confirm the accepted ADR-0014 policy and its archive-correction gates are
  complete before any archive write;
- preserve the Statistics Canada conditions, exact source attribution,
  provenance, no-endorsement statement, and anti-identification boundary; an
  open licence never relaxes those obligations;
- run the relevant SynthPopCan audit/release workflow;
- confirm large files are distributed as release assets with checksums and
  fetched on demand by `synthpopcan models fetch`.
- follow `RELEASING.md` before updating the public model registry.

## Building Model Release Assets

Training, reviewing, and bundling model packages from restricted microdata is a
maintainer workflow. It requires a source checkout and appropriately controlled
access to the source data; ordinary installs do not run it.

The repository includes `scripts/build_all_model_packages.py`, which builds the
province and PUMF-coded CMA targets currently declared in that script:

```bash
uv run python scripts/build_all_model_packages.py
uv run python scripts/build_all_model_packages.py --year 2021
```

Pass `--only` to build a subset:

```bash
uv run python scripts/build_all_model_packages.py --only ontario-2016 toronto-cma-2016
```

The script uses library modules directly to:

- read the selected 2016 or 2021 hierarchical PUMF once, then filter by
  geography;
- resolve all currently supported household and person column blocks;
- prefer linked conditional-frequency models and fall back to CART leaves with
  at least 50 contributing records when sparse condition cells would block
  release;
- audit private working models and stop on release-blocking issues;
- write publishable-candidate model copies and release manifests;
- write linked package JSON under `data/derived/models/release-assets/`, ready
  for review before upload as GitHub Release assets.

The script's target declarations are authoritative. The 2021 build creates the
complete parallel catalogue, including Canada, Quebec, and Montreal. The 2016
default retains its historical batch scope because its Canada, Quebec, and
Montreal assets were prepared separately.

Review every generated package under the **Data And Model Safety** policy above,
then complete the **Model Package Release** checklist in `RELEASING.md`.

## Building Prepared Geodata

Prepared geodata is display-only derived geometry published separately from the
Python wheel. Building it requires the canonical local Statistics Canada
boundary inputs documented by the scripts; those large inputs and generated
release files remain ignored.

Install the Node dependencies, then create topology-preserving display copies:

```bash
npm ci
npm run simplify:all-boundaries
```

For a bounded rebuild, use the level-specific scripts declared in
`package.json`. After reviewing the outputs, build compressed assets and the
versioned catalogue with an immutable release base URL:

```bash
SYNTHPOPCAN_GEODATA_RELEASE_BASE_URL="https://github.com/dlq/synthpopcan/releases/download/geodata-v1" \
  npm run build:geodata-release
```

The builder writes `data/derived/geodata/release-assets/v1/`. It records Census
year, geography level, optional PRUID, representation, byte sizes, and separate
compressed and unpacked SHA-256 values. Review the complete catalogue rather
than trusting filenames, then follow the **Prepared Geodata Release** checklist
in `RELEASING.md`.

Never use a prepared display file to replace the canonical analytical boundary.
See [ADR-0009](adr/0009-separate-display-and-analytical-geodata.md) for the
architectural boundary.

## Documentation

User-facing behavior should be documented where readers will look for it:

- `README.md` for project orientation and public-repo expectations;
- `docs/` for workflow and API documentation;
- `adr/` for durable architectural decisions and their rationale;
- `PLANS.md` for open roadmap items;
- `NOTES.md` for research notes.

Avoid putting long walkthroughs in the README when they belong in Sphinx docs.

Build the documentation with warnings treated as errors:

```bash
uv run sphinx-build -W -b html docs docs/_build/html
```

Check external links and source formatting separately:

```bash
uv run sphinx-build -b linkcheck docs docs/_build/linkcheck
uv run --group docs doc8 docs
uv run --group docs mdformat --check docs README.md CONTRIBUTING.md
```

Apply Markdown formatting with:

```bash
uv run --group docs mdformat docs README.md CONTRIBUTING.md
```

When changing examples, run the examples that are presented as runnable. Good
examples are part of the interface: check command names, fixture paths, column
names, output files, and whether the example still makes sense in its
surrounding explanation.

## Performance Benchmarks

Benchmarks are contributor tools, not normal user workflows. Exercise the
tracked small-area calibration profiles with:

```bash
uv run python scripts/benchmarks.py small-area
uv run python scripts/benchmarks.py small-area --province-scale
```

The province-scale profile records 10,000 retained candidates, 1,200 target
geographies, 4.5 million target households, a 180-second fit budget, and a
512 MiB retained-weight budget. Timing is opt-in because it depends on the
machine; fixture shape and memory estimates are checked by the default tests.
