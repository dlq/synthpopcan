# SynthPopCan Plan

Status: working roadmap  
Last updated: 2026-06-21

## Goal

Build SynthPopCan as a Python library, CLI, and eventually web app for Canadian synthetic population generation.

The near-term scope is deliberately narrower than the full proposal:

1. Build synthetic populations through iterative proportional fitting from StatCan margin/control tables.
2. Build household- and person-level synthetic populations with a tree-based synthetic population generator using pluggable census microdata sources. The Canadian 2016 Census material staged locally is the first available microdata source, not the tool boundary.
3. Keep environmental, school, healthcare, food, and broader enrichment data as later extensions unless they are needed for validation or demos.

## Principles

- Keep source data out of git. Track only code, documentation, tiny fixtures, and reproducible metadata.
- Prefer public fetches for public geography and service layers rather than storing copies in the project.
- Make the library usable without the web app. The CLI should expose the same core workflows as the Python API.
- Treat geography, variables, margins, seed samples, weights, and generated populations as explicit typed concepts.
- Build from small, inspectable test fixtures before operating on full census files.
- Preserve provenance for every generated output: source tables, geography, variables, filters, model version, random seed, and validation metrics.

## Architecture Target

SynthPopCan should eventually have four layers:

1. `synthpopcan` Python library
   - Data schemas and validation.
   - StatCan table normalization.
   - IPF and integerization.
   - Tree-based household/person synthesis.
   - Validation and reporting primitives.

2. `synthpopcan` CLI
   - Inspect local source files.
   - Normalize margins.
   - Run IPF synthesis.
   - Train or apply the tree-based synthetic population generator.
   - Validate and export generated populations.

3. Local data workspace
   - Ignored `data/raw` and `data/private` folders.
   - Tracked manifests only when they are public-safe and useful.
   - Small test fixtures under `tests/fixtures` when needed.

4. Web app
   - Run configuration UI.
   - Source and geography selection.
   - Progress and diagnostics.
   - Validation reports and export downloads.

## Milestones

### 0. Repository Baseline

Status: complete.

Current state:

- Git repository initialized.
- README, research notes, license, package scaffold, CLI stub, and smoke test are in place.
- Large data and private source material are ignored.
- `research.md` captures the local proposal/materials plus recent implementation work in population synthesis.

### 1. Core Data Model

Define the internal contracts before implementing algorithms.

Deliverables:

- `VariableSpec`: variable name, categories, source column names, category mapping, missing-value handling.
- `GeographySpec`: geographic level, identifiers, parent/child relationships where available.
- `ControlTable`: normalized margin table with geography, variable dimensions, category values, and counts.
- `SeedSample`: microdata sample with person/household rows, weights, geography hints, and source metadata.
- `SyntheticPopulation`: generated rows plus provenance and validation metadata.

Notes:

- Use plain dataclasses or lightweight typed models first. Avoid a heavy dependency until the shape stabilizes.
- Include serialization helpers for CSV/Parquet-friendly structures once dependencies are chosen.

Current implementation notes:

- `ControlTable`, `ControlMargin`, and `ControlCell` are implemented in `synthpopcan.controls` for normalized controls.
- `ControlTable` can convert to the IPF engine's `IPFMargin` objects, keeping the IPF algorithm decoupled from CSV parsing.
- `SeedSample` is implemented in `synthpopcan.census_microdata` as the stable seed/training record contract for IPF and future tree-based synthetic population generator adapters.

### 2. Local Source Inspection

Build tools that can inspect staged census microdata and public aggregate source caches without loading everything into memory.

Deliverables:

- CLI command to list known local source roots and file counts.
- Header/schema inspection for common CSV/TXT source files.
- Sampling command for tiny previews with encoding and delimiter detection.
- Public-safe source inventory output suitable for debugging.

Acceptance criteria:

- Works against ignored local census microdata caches, starting with the available 2016 material.
- Produces no private-data output by default.
- Has tests using tiny fixtures only.

Current implementation notes:

- `sources inspect`, `sources schema`, and `sources sample` provide structural inspection for local files.
- `sources sample` refuses paths under `data/private` unless `--allow-private` is provided.
- Census microdata formats should be handled with explicit source adapters by year/product/format. Pritchard-era inputs, the available 2016 files, and later 2021-style files should route through separate adapters that produce the same internal `SeedSample` contract.

### 3. Control Table Normalization

Implement the path from StatCan-style margin/control tables, Census Profile downloads, and user-provided CSVs to normalized controls.

Deliverables:

- Parser for local StatCan table exports.
- Generic `controls` CLI namespace for normalized control-table workflows.
- `controls validate` for checking the normalized long control CSV format. Status: complete for normalized long CSVs.
- `controls from-csv`, `controls from-wds`, and `controls from-census-profile` adapters. Status: `from-csv` complete for normalized long CSVs; `from-wds` complete for local WDS ZIPs with explicit dimensions/count/category mapping; Census Profile adapter pending.
- Category mapping layer for converting source labels/codes into stable internal categories. Status: complete for WDS normalization.
- Validation for totals, missing categories, duplicated cells, and geography coverage.
- CLI command:

```bash
synthpopcan controls from-csv SOURCE --out controls.csv
synthpopcan controls from-wds SOURCE.zip --dimensions "GEO,Age group,Sex" --count-column VALUE --mapping categories.json --out controls.csv
```

Acceptance criteria:

- A toy fixture can be normalized into a `ControlTable`.
- A normalized control CSV can be validated with `synthpopcan controls validate controls.csv`.
- Validation errors are actionable and include source rows/columns.
- The code is ready to add live StatCan fetch support later, but does not require network access.

### 4. IPF Engine

Create the first production-quality synthesis engine around IPF.

Deliverables:

- N-dimensional IPF over seed records and normalized controls.
- Convergence controls: max iterations, tolerance, structural zeros, and failed-fit diagnostics.
- Integerization strategy for converting fitted weights into output rows.
- Reproducible random seed handling.
- CLI command:

```bash
synthpopcan ipf fit --seed seed.csv --controls controls.csv --out weights.csv
synthpopcan ipf fit --seed seed.csv --controls controls.csv --out weights.csv --report fit-report.json
synthpopcan ipf expand --weights weights.csv --out population.csv
```

Acceptance criteria:

- Unit tests cover convergence on simple two- and three-margin fixtures.
- Outputs include fit metrics by geography and variable.
- Non-convergence is reported as a useful error or warning, not a silent failure.

Current implementation notes:

- `synthpopcan ipf fit` writes compact fitted seed weights because expanded synthetic rows can become very large quickly.
- `synthpopcan ipf fit --report` writes JSON diagnostics with convergence status, iterations, max absolute error, and per-cell residuals.
- `synthpopcan ipf expand` streams fitted weights into full synthetic rows for demos, exploratory work, and agent-based-model inputs.
- The CLI now rejects non-converged fits by default before writing weights; `--allow-nonconverged` is available for explicit inspection runs.
- Normalized control table parsing lives in `synthpopcan.controls`, not in the CLI, so StatCan normalizers and the future web app can reuse the same contract.
- The first implementation used a simple record-oriented IPF loop. That was useful for correctness tests, but it repeatedly scanned every seed record for each target category.
- The next implementation direction is indexed IPF: precompute the seed-record indexes belonging to each margin cell, then reuse those indexes during each fitting iteration.

Production-grade IPF means more than using a faster table library. It should include:

- Indexed or vectorized updates rather than repeated full-record scans per target category.
- Sparse/high-cardinality margin handling.
- Clear treatment of structural zeros and impossible controls.
- Convergence diagnostics that explain whether a run converged, stalled, or has inconsistent controls.
- Numerical stability for large populations, small cells, and large fitted weights.
- Streaming expanded output so full synthetic datasets do not need to be held in memory.
- Benchmark tests on realistic seed sizes, target counts, and population sizes.
- Validation reports comparing generated outputs back to controls.
- Deterministic reproducibility for fitted weights, integerization, and expanded rows.

Near-term IPF performance tasks:

1. Use fitted weights as the default CLI output. Status: complete.
2. Keep expanded output explicit through a separate `ipf expand` command. Status: complete.
3. Precompute record membership indexes for each margin cell. Status: complete in the pure-Python fitter.
4. Stream expanded rows directly to CSV instead of building the full expanded population in memory. Status: complete.
5. Add benchmarks or performance tests for easy, moderate, and high-cardinality fixtures. Status: pending.
6. Improve non-convergence diagnostics and CLI reporting. Status: partially complete; the CLI now fails closed on non-convergence and can write JSON fit diagnostics, but richer validation reports are still pending.
7. Consider NumPy, Polars, and possibly sparse arrays after the pure-Python indexed version establishes the right data contracts. Status: pending.

Local timing evidence after indexing:

- Easy balanced fixture, 50,000 seed records to 500,000 expanded rows: fitting about 0.03 seconds, expansion about 0.14 seconds.
- High-cardinality inconsistent fixture, 50,000 seed records, 72 target cells, 100 iterations: fitting about 1.0 second, down from about 54.5 seconds in the naive repeated-scan version.
- The high-cardinality fixture still does not converge because its controls are deliberately inconsistent, so diagnostics are still required.

### 5. Census Household/Person Microdata Ingestion

Turn staged census microdata into usable seed and training inputs. The currently available 2016 microdata is the first adapter target; the design should support later 2021 or other census-year microdata where access is available.

Deliverables:

- Identify the exact household-level and person-level files to support first for 2016.
- Create loading adapters that are explicit about census year and source format.
- Normalize key variables needed for the first household/person synthesis prototype.
- Document assumptions in `research.md` or a future data-access note when source interpretation matters.
- CLI command:

```bash
synthpopcan microdata inspect sample.csv --input-format fixture-v1 --level person --format json
```

Acceptance criteria:

- A small fixture can represent household/person joins.
- Full-data paths remain configurable and ignored.
- The loader exposes useful diagnostics for row counts, weights, geography, and missing values.

Current implementation notes:

- `fixture-v1` is the first tiny adapter used only for tests and demos.
- Real Pritchard-era, 2016, and later census microdata formats should be added as separate adapters that emit `SeedSample`.

### 6. Tree-Based Synthetic Population Generator Prototype

Build the first tree-based synthetic population generator for household and person attributes.

Deliverables:

- Baseline model selection, likely random forest or gradient-boosted trees depending on dependency choices.
- Household model for household-level attributes.
- Person model conditioned on household and geography attributes.
- Geographic subregion support for training or applying models at different levels.
- Calibration hook so outputs can be aligned with known margins after model generation.

Acceptance criteria:

- The prototype runs on fixture data and a small sampled local extract.
- Metrics compare generated distributions against source controls.
- Model artifacts and generated outputs include provenance and random seed metadata.

### 7. CLI Workflow

Make the CLI useful for actual work before the web app starts.

Initial command families:

```bash
synthpopcan sources inspect ...
synthpopcan controls validate ...
synthpopcan controls from-csv ...
synthpopcan controls from-wds ...
synthpopcan controls from-census-profile ...
synthpopcan ipf fit ...
synthpopcan ipf expand ...
synthpopcan microdata inspect ...
synthpopcan tree train ...
synthpopcan tree generate ...
synthpopcan validate ...
```

Acceptance criteria:

- Each command has help text and clear failure messages.
- Commands write explicit output files rather than hidden state.
- Tests cover command parsing and one tiny end-to-end IPF run.

### 8. Validation Reports

Add repeatable validation before building a web UI around the workflow.

Deliverables:

- Marginal fit tables.
- Distribution comparisons.
- Geography-level diagnostics.
- Household/person consistency checks.
- Machine-readable JSON plus human-readable Markdown or HTML report output.

Acceptance criteria:

- Every synthesis run can produce a validation report.
- Failed validation thresholds can return a non-zero CLI exit code for automation.

### 9. Web App

Start the web app only after the library and CLI contracts are stable enough.

Likely first version:

- Local-only app.
- Select source roots and normalized controls.
- Configure an IPF run.
- Show run progress and validation summaries.
- Download generated population and report artifacts.

Deferred until needed:

- User accounts.
- Remote job execution.
- Large-data upload management.
- Hosted public deployment.

## Near-Term Slice

The next implementation slice should be small and testable:

1. Add initial typed data structures for variables, geography, controls, seed samples, and generated populations.
2. Add fixture-based tests for a tiny control table and seed sample.
3. Add a `sources inspect` or equivalent CLI command for local file/header inspection.
4. Add the first `controls from-csv` fixture workflow.
5. Add a minimal two-margin IPF implementation and test it end to end.

This gets the project from documentation scaffold to usable computational core without depending on the full Census data volume.

## Deferred Work

Data-source and data-access documentation needs a dedicated pass. It should cover:

- Which sources are fetched live or downloaded on demand.
- Which local caches are acceptable in `data/raw` and `data/private`.
- Which datasets require access controls or special handling.
- Stable URLs, APIs, and citation requirements for StatCan, open.canada.ca, donneesquebec.ca, and related portals.
- How the Google Drive source bundle maps to reproducible public sources.

Other deferred work:

- Environmental exposure integration.
- School, healthcare, and food-access enrichment.
- Scenario simulation.
- Privacy risk assessment for generated outputs.
- Packaging and publishing.

## Testing Policy

Every new feature should include tests at the smallest practical scale:

- Unit tests for pure transformations and algorithms.
- CLI tests for command behavior and output files.
- Fixture-based integration tests for one complete workflow.
- No tests should require full private or raw data caches.

Full-data smoke tests can be added later as optional local commands, documented separately from the default test suite.

## Data Policy

Tracked:

- Source code.
- Documentation.
- Public-safe manifests.
- Tiny synthetic fixtures.
- Generated examples only when they are small, reproducible, and safe.

Ignored:

- Raw Census files.
- Private research datasets.
- Large public data caches.
- Generated populations from real source data.
- Model artifacts trained from private or large raw sources.

## Open Decisions

- Exact dependency stack for arrays/tables/models: likely NumPy, pandas or Polars, scikit-learn, and optional PyArrow.
- Whether schemas should remain dataclasses or move to Pydantic once the API surface stabilizes.
- First supported StatCan table format and access path.
- First supported census microdata household/person files, starting with available 2016 files.
- Integerization method for the first IPF engine.
- Whether the web app should be Streamlit/FastAPI-first or built as a richer frontend once workflows settle.

## Done Means

The first useful version is done when a user can:

1. Point the CLI at a small seed sample and normalized control table.
2. Generate a synthetic population through IPF.
3. Validate the output against controls.
4. Inspect and normalize a small census-style household/person fixture.
5. Run an initial tree-based household/person synthesis prototype.
6. Reproduce the run from tracked code and ignored local data caches.
