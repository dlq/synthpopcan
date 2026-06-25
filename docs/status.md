# Implementation Status

This page summarizes what the current codebase can do. `PLANS.md` remains the
active roadmap; this page holds completed implementation notes that are useful
for users, contributors, and reviewers.

## Current First-Pass Capabilities

SynthPopCan currently has working first-pass surfaces for:

- a Python library with a beginner API exposed through `import synthpopcan as spc`;
- a Click command-line interface for data inspection, control normalization,
  IPF, microdata adapters, tree-model workflows, validation, and local serving;
- a local browser app started with `synthpopcan serve`;
- Sphinx documentation with a task-first entry point and selective autodoc API
  reference;
- fixture-based tests that do not require private or full raw data caches.

The two beginner generation paths are:

1. **IPF from margin tables:** prepare or load seed rows, normalize control
   totals, fit weights, optionally expand rows, and validate the result.
1. **Generate from existing model:** load a prepared household/person model
   package, generate linked household and person rows, preview output, and
   validate household/person linkage.

## Completed StatCan/IPF Slice

The StatCan/IPF usability slice is mostly complete for a first pass. The
project now has a coherent public-data-to-IPF path:

```bash
synthpopcan statcan wds search ...
synthpopcan statcan wds explain PRODUCT_ID
synthpopcan statcan wds fetch PRODUCT_ID --out-dir data/raw/statcan/wds
synthpopcan controls wds inspect TABLE.zip
synthpopcan controls wds mapping-template TABLE.zip --dimensions ... --out categories.json
synthpopcan controls from-wds TABLE.zip --mapping categories.json --out controls.csv
synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv
synthpopcan ipf fit --seed seed.csv --controls controls.csv --out weights.csv --report fit-report.json
synthpopcan validate controls --population weights.csv --controls controls.csv --kind weights
```

Completed StatCan/IPF usability work:

- `controls wds inspect` inspects downloaded WDS ZIPs and suggests starter
  `controls from-wds` settings.
- `statcan wds explain` summarizes a product ID, reports available dimensions,
  gives an IPF suitability hint, and prints next commands.
- `statcan wds fetch` and `controls from-wds` show Rich status indicators while
  downloading, reading, normalizing, and writing WDS artifacts.
- `controls wds mapping-template` writes a starter category mapping JSON from
  observed WDS labels in selected dimensions.
- `ipf check-inputs` includes suggested next steps for missing seed columns and
  category mismatches, including WDS mapping-template hints.
- `docs/ipf.md`, `docs/controls.md`, and `docs/statcan.md` document the
  WDS-to-IPF path.
- `ipf suggest-controls --seed ...` inspects generated columns, reports usable
  controls, flags missing/enrichment candidates, separates likely household
  controls from person controls, and prints next StatCan/IPF commands while
  keeping final table choice reviewable.

Remaining StatCan/IPF follow-up work belongs in `PLANS.md`, especially richer
non-convergence reports, broader mapping presets, optional sparse backends, and
future enrichment workflows for useful StatCan dimensions that are not already
present on generated rows.

## IPF Performance Notes

The pure-Python indexed IPF implementation is the default. It precomputes
seed-record membership for margin cells and streams expanded output.

Local timing evidence after indexing:

- Easy balanced fixture, 50,000 seed records to 500,000 expanded rows: fitting
  about 0.03 seconds, expansion about 0.14 seconds.
- High-cardinality inconsistent fixture, 50,000 seed records, 72 target cells,
  100 iterations: fitting about 1.0 second, down from about 54.5 seconds in the
  naive repeated-scan version.
- The high-cardinality fixture still does not converge because its controls are
  deliberately inconsistent, so diagnostics remain important.

Experimental backend comparison results:

| Seed rows | Case | Iterations | Current Python | NumPy `bincount` | SciPy CSR | Polars `group_by` |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 50,000 | easy balanced | 1 | ~0.023s | ~0.032s | ~0.037s | ~0.046s |
| 50,000 | moderate three-margin | 1 | ~0.037s | ~0.047s | ~0.056-0.064s | ~0.035-0.049s |
| 50,000 | high-cardinality inconsistent | 100 | ~0.62-0.67s | ~0.11s | ~0.09-0.12s | ~0.69-0.73s |
| 200,000 | high-cardinality inconsistent | 100 | ~2.8s | ~0.44s | ~0.36s | not rerun |

Current decision: keep pure Python as the default for simple dense controls,
prototype SciPy CSR later for large, sparse, or repeated-update fits, and treat
Polars as a likely table-ingestion/prep tool rather than the IPF update kernel.

## Completed Tree Packaging And Distribution Slice

The first pass of model packaging and distribution is in place:

- `tree release-readiness` can evaluate linked household/person model pairs and
  classify whether they look like publishable candidates under current checks.
- `tree prepare-model-release` creates reviewed publishable-candidate copies
  when audits allow it.
- `tree package-linked-models` packages household and person models together
  only after both audits pass, source provenance is present, training/release
  manifests are consistent, and a human review note is provided.
- `models list` lists bundled demo packages and published downloadable model
  packages for both CLI and local web app use.
- `models fetch` downloads large published model packages into a local cache
  only when the user asks for them.
- `tree inspect-package` summarizes package provenance, privacy flags, model
  sizes, audit summaries, release manifests, and review notes without dumping
  embedded model payloads.
- `tree generate-from-package` consumes a reviewed linked package path or
  packaged model ID and generates linked household/person CSVs.
- Large linked package generation streams CSV and now caches repeated
  conditional-frequency selections with precomputed cumulative sampling weights,
  fixed-schema CSV writing, and a shared linked-run RNG. In a local Montréal
  package smoke test, 100,000 household rows plus 231,637 person rows wrote to
  CSV in about 2.78 seconds after these changes.
- A reviewed Quebec (`PR=24`) all-fields package is listed as the downloadable
  `quebec-2016-all-fields` model. The library workflow script
  `scripts/build_quebec_model_package.py` trained, audited, released, and
  packaged the 116 MiB model artifact in about 10 seconds of script-recorded
  build time. Its optional large-output run generated 3,750,000 household rows
  and 8,450,189 person rows in about 51.7 seconds, writing local CSV artifacts
  under `data/private/benchmarks/tree-release-2016-pr24-all-fields/`.
- The `tree generate-from-package` CLI command renders a Rich progress indicator
  with generated household and person counts for longer runs.
- The `tree train-linked` CLI command renders a step-based Rich progress
  indicator for reading source microdata, deriving household/person training
  rows, training both models, and writing model artifacts.
- The web app consumes prepared model artifacts and does not expose training
  from restricted microdata.

The workflow separates private working models from publishable candidates. This
is deliberate: a model trained from restricted microdata is not automatically
safe to distribute just because it is a model.

## 2016 Linked-Model Experiment Notes

Local full-data experiments are not part of the default test suite, but they
have been useful for shaping the workflow:

- A full local 2016 hierarchical PUMF run using `tree train-linked --suggested-blocks` trained household/person conditional-frequency models
  from 343,330 person rows and 140,720 derived household rows in about 12
  seconds wall-clock. The broad `household_core` model was about 95.5 MB and
  the `person_demographics` model about 3.5 MB. Generating 1,000 Quebec
  households with `PR=24` produced 2,300 people; `validate linked-output`
  passed. The household model size suggests broad household target blocks need
  pruning, coarsening, or staged modeling before distribution or browser use.
- A smaller PR=24 release-workflow experiment trained from 79,498 person rows
  and 35,306 households. After release preparation, readiness classified the
  pair as `likely_publishable` under current first-pass checks. The linked
  package was about 25 MB and generated linked output passed validation.
- A PR=11 minimal-profile smoke run trained from 1,401 person rows and 597
  households. It produced a small package and generated linked output passed
  validation. This is useful as a technical smoke test, but small geographies
  still require cautious review before distribution.

## Testing Policy

Every new feature should include tests at the smallest practical scale:

- unit tests for pure transformations and algorithms;
- CLI tests for command behavior and output files;
- fixture-based integration tests for one complete workflow;
- documentation-example checks for runnable getting-started or workflow
  examples;
- coverage measurement with `pytest-cov`.

No default tests should require full private or raw data caches.

The current coverage command is:

```bash
uv run pytest --cov=synthpopcan --cov-report=term-missing -q
```

The current documentation and web-asset checks are:

```bash
uv run sphinx-build -W -b html docs docs/_build/html
npm run check:web
```

Current measured baseline as of 2026-06-24: 100% line coverage for tracked
Python code, with 268 tests passing and 4 skipped.

Full-data smoke tests should remain optional local commands. They supplement,
but do not replace, the fixture-based default suite.
