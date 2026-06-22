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
- `SeedSample` is implemented in `synthpopcan.microdata` as the stable seed/training record contract for IPF and future tree-based synthetic population generator adapters.

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
- `controls from-csv`, `controls from-wds`, and `controls from-census-profile` adapters. Status: `from-csv` complete for normalized long CSVs; `from-wds` complete for local WDS ZIPs with explicit dimensions/count/category mapping; `from-census-profile` complete for local CSVs with explicit row mapping, row inspection, and starter mapping templates.
- Category mapping layer for converting source labels/codes into stable internal categories. Status: complete for WDS normalization and Census Profile row mapping.
- Validation for totals, missing categories, duplicated cells, and geography coverage.
- CLI command:

```bash
synthpopcan controls from-csv SOURCE --out controls.csv
synthpopcan controls from-wds SOURCE.zip --dimensions "GEO,Age group,Sex" --count-column VALUE --mapping categories.json --out controls.csv
synthpopcan controls from-census-profile PROFILE.csv --mapping census-profile-mapping.json --out controls.csv
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
synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv
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
- `synthpopcan ipf fit --report` writes JSON diagnostics with convergence status, iterations, max absolute error, per-margin summaries, and per-cell residuals.
- `synthpopcan ipf report fit-report.json` prints a human-readable fit summary and margin table for non-programmatic review.
- `synthpopcan ipf check-inputs` previews whether seed columns and categories cover the normalized controls before fitting.
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
5. Add benchmarks or performance tests for easy, moderate, and high-cardinality fixtures. Status: complete for developer-facing `scripts/benchmark_ipf.py`; not exposed as a user CLI workflow.
6. Improve non-convergence diagnostics and CLI reporting. Status: partially complete; the CLI now fails closed on non-convergence, can write JSON fit diagnostics, can print a human-readable report table, and reports the largest residual with a plain-language tip. Richer validation reports that explain whole-run inconsistency patterns are still pending.
7. Consider NumPy, Polars, and possibly sparse arrays after the pure-Python indexed version establishes the right data contracts. Status: pending.

Local timing evidence after indexing:

- Easy balanced fixture, 50,000 seed records to 500,000 expanded rows: fitting about 0.03 seconds, expansion about 0.14 seconds.
- High-cardinality inconsistent fixture, 50,000 seed records, 72 target cells, 100 iterations: fitting about 1.0 second, down from about 54.5 seconds in the naive repeated-scan version.
- The high-cardinality fixture still does not converge because its controls are deliberately inconsistent, so diagnostics are still required.

### 5. Census Household/Person Microdata Ingestion

Turn staged census microdata into usable seed and training inputs. The currently available 2016 microdata is the first adapter target; the design should support later 2021 or other census-year microdata where access is available.

Deliverables:

- Support the 2016 hierarchical PUMF as the first real microdata adapter.
- Create loading adapters that are explicit about census year and source format.
- Derive household, person, and link views from one hierarchical file when a format carries `HH_ID`/`PP_ID`-style identifiers.
- Normalize key variables needed for the first household/person synthesis prototype.
- Export selected person-level microdata columns to IPF seed CSVs.
- Export conservative household-level seed rows from hierarchical microdata when selected household columns are constant within each `HH_ID`.
- Check selected household seed columns before export so users can see constant columns, conflicts, the weight check, and derived `household_size`.
- Document assumptions in `research.md` or a future data-access note when source interpretation matters.
- CLI commands:

```bash
synthpopcan microdata inspect sample.csv --input-format fixture-v1 --level person --format json
synthpopcan microdata inspect hierarchical.csv --input-format statcan-2016-hierarchical --format table
synthpopcan microdata check-seed hierarchical.csv --input-format statcan-2016-hierarchical --level household --columns TENUR,ROOMS
synthpopcan microdata export-seed hierarchical.csv --input-format statcan-2016-hierarchical --columns AGEGRP,SEX --out seed.csv
synthpopcan microdata export-seed hierarchical.csv --input-format statcan-2016-hierarchical --level household --columns TENUR --out household-seed.csv
synthpopcan microdata export-training hierarchical.csv --input-format statcan-2016-hierarchical --level person --target-columns AGEGRP,SEX --conditioning-columns TENUR,household_size --out person-training.csv
```

Acceptance criteria:

- A small fixture can represent a person-row hierarchical file with household/person identifiers.
- Full-data paths remain configurable and ignored.
- The loader exposes useful diagnostics for row counts, household counts, weights, geography, duplicate IDs, and missing values.

Current implementation notes:

- `fixture-v1` is the first tiny adapter used only for tests and demos.
- `statcan-2016-hierarchical` inspects a single hierarchical PUMF-style CSV with `HH_ID`, `EF_ID`, `CF_ID`, `PP_ID`, and `WEIGHT`.
- `microdata export-seed` exports selected person-level columns from fixture and `statcan-2016-hierarchical` inputs for use by `ipf fit`.
- `microdata export-training` derives household/person training views from `statcan-2016-hierarchical` inputs for use by `tree train`, including derived `household_size` and selected household context on person rows.
- `microdata check-seed` previews whether selected `statcan-2016-hierarchical` household columns are safe to export before writing a seed file.
- Household-level seed export from `statcan-2016-hierarchical` is intentionally conservative: one row per `HH_ID`, selected household columns must be constant within the household, `WEIGHT` must be constant within the household, `household_size` is derived, and conflicts fail rather than being imputed.
- Real Pritchard-era, individual-only 2016 PUMF, and later census microdata formats should be added as separate adapters that emit `SeedSample` or derived household/person views.

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

Current implementation notes:

- The `synthpopcan.tree` module defines the first tree-generator contract objects: `TreeTrainingSample`, `TreeModelSpec`, `TreeGenerationRequest`, and a CSV training-sample reader with validation for target, conditioning, geography, and weight columns.
- `synthpopcan tree train` and `synthpopcan tree generate` run transparent conditional-frequency and sklearn CART models on fixture-style CSV training samples. Conditional-frequency remains the default; CART is selected with `--method cart`.
- The current tree CLI does not assume the real 2016 hierarchical PUMF is a clean people CSV. Real 2016 usage should flow through microdata adapters that derive household/person training views from the mixed hierarchical file, then pass those views into the tree training contract.
- The first model artifact records privacy-oriented metadata including source format, trained record count, minimum support, groups below support threshold, release class, and explicit `contains_raw_rows: false` / `contains_source_identifiers: false` flags. It is still marked `private_working`, not publishable.
- Initial benchmark on the local 2016 hierarchical PUMF person file (343,330 rows, 116 source columns) with target `AGEGRP,SEX` and conditioning `PR,TENUR,household_size`: read hierarchical sample 3.7s, derive person training rows 1.0s, write 15.7 MB training CSV 0.5s, read training CSV 1.3s, train conditional-frequency 0.3s, train CART with `min_samples_leaf=50,max_depth=8` 1.5s. Peak process memory was about 2.4 GiB because the current adapter reads the full source CSV into Python dictionaries; streaming/narrow-column loading should be planned before web-app use.
- `synthpopcan tree audit-model` performs the first artifact-level disclosure-risk check for private working models, including raw-row/source-id flags, minimum support, high-purity groups/leaves with dominant outcomes, release class, and publishable-candidate status. It is an advisory gate, not a claim of privacy safety.
- `synthpopcan tree package-model` is a strict first packaging gate: it refuses to write a package if the audit has any warnings or errors. Current `private_working` models therefore cannot be packaged until a later reviewed publishable-candidate workflow exists.
- `synthpopcan tree prepare-model-release` writes a publishable-candidate copy of a model only when the release audit has no blocking issues beyond the expected `private_working` release-class warning. It can write a release manifest with thresholds, audit output, source/output model paths, and a human review note.
- `synthpopcan tree package-linked-models` packages household and person models together only after both audits pass without warnings. It validates household/person model levels and the household-size linkage column, embeds both model artifacts and both audit reports, and marks the package as a publishable candidate only when both model audits say so.
- Initial audit on the local 2016-derived models with `min_support=50,max_purity=0.95`: conditional-frequency had 157 groups, minimum support about 503.7, no low-support groups, and 2 pure groups; CART had 58 leaves, minimum support 81, no low-support or high-purity leaves. Both remained `private_working` and `publishable_candidate: false`.
- `synthpopcan tree generate-linked` performs the first household-then-person generation pass from separate household and person models, writing linked `synthetic_household_id` and `synthetic_person_id` CSV outputs.
- `synthpopcan tree generate` and `synthpopcan tree generate-linked` accept `--manifest-out` for a lightweight JSON provenance sidecar with model path, model type, release class, output paths, conditions, requested random seed, and effective random seed.
- `synthpopcan tree train-linked` trains household and person models directly from a mixed `statcan-2016-hierarchical` microdata file using named suggestion-profile blocks. The first user-facing path requires `--suggested-blocks`, defaults to `household_core` plus `person_demographics`, writes both model JSON files, and writes a training manifest with source, selected blocks, training summaries, model paths, method, and random seed.
- `synthpopcan tree train-linked` now makes geography advisor recommendations directly actionable with `--geography-column`, `--geography-value`, and `--target-profile full|reduced|minimal`. This lets a user train a likely PR/CMA with the full suggested blocks, a borderline geography with reduced targets, or a small province/territory with a minimal local-experiment target set without hand-authoring training CSVs.
- Full local 2016 run using `tree train-linked --suggested-blocks` on the ignored project-local hierarchical PUMF source trained household/person conditional-frequency models from 343,330 person rows and 140,720 derived household rows in about 12 seconds wall-clock. The default `household_core` model was about 95.5 MB and the `person_demographics` model about 3.5 MB. Generating 1,000 QC households with `PR=24` produced 2,300 people; `validate linked-output` passed with no unknown households and no household-size mismatches. The household model size suggests broad household target blocks need pruning, coarsening, or staged modeling before distribution or browser use.
- Local smoke run for PEI-style small-geography training with `--geography-column PR --geography-value 11 --target-profile minimal` trained on 1,401 person rows and 597 households, producing a 4.8 KB household model and 42 KB person model. This demonstrates the ergonomic path works, but the advisor still recommends aggregate or minimal models for small geographies before any distribution workflow.
- `scripts/benchmark_tree_linked.py` runs the first developer-facing linked household/person benchmark workflow from a `statcan-2016-hierarchical` CSV: derive household/person training views, train both models, generate linked outputs, validate linkage, compare household/person distributions, write JSON reports, and print timing/RSS summary metrics.
- Initial linked benchmark on the local 2016 hierarchical PUMF with `PR=24`, 1,000 generated households, household targets `household_size,TENUR`, household conditioning `PR`, person targets `AGEGRP,SEX`, and person conditioning `PR,household_size,TENUR`: source 343,330 person rows and 140,720 households; QC validation subset 35,306 household rows and 79,498 person rows; generated 1,000 households and 2,271 persons; generated average household size 2.271 versus 2.2517 in the QC training subset; linkage passed with no issues; household and person distribution checks passed at 5 percentage-point tolerance after comparing against the conditioned QC training subset, with max deltas about 2.02 and 2.08 percentage points and no warnings. Timings: read source 3.5s, derive training 3.1s, train models 1.8s, generate 0.1s, validate 0.3s; peak RSS about 2.2 GiB. Output artifacts under ignored `data/private/benchmarks/tree-linked-2016-qc/`: household model 28 KB, person model 590 KB, household training CSV 4.2 MB, person training CSV 15 MB.
- `synthpopcan microdata suggest-tree-columns` advises broad staged column blocks through a source-specific suggestion profile. The first profile, `statcan-2016-hierarchical`, covers household core, person demographics, person identity/language, and person education/work/income. It excludes identifiers, weights, and replicate weights, reports geography context columns, and only includes target columns present in the inspected file. The profile registry is the first step toward supporting other census years or microdata layouts without rewriting the command.
- `synthpopcan microdata tree-geography-feasibility` estimates which PR or CMA geographies are plausible candidates for publishable linked tree models before training many artifacts. It reports person rows, derived household rows, weighted totals, conditioning support, outcome purity risk, a likely/borderline/unlikely tier, and a model-design recommendation with scope, reduced/minimal target sets, columns to review first, Canadian aggregation hints, and next steps. On the local 2016 hierarchical PUMF with default `household_core` plus `person_demographics`, PR 35/24/59/48/46/47 are likely, PR 12/13/10 are borderline, and PR 11/70 are unlikely under the current thresholds. The exposed CMA buckets 999/535/462/933/825/835 are likely under the same first-pass criteria.
- `scripts/benchmark_tree_linked.py --suggested-blocks` can now run the linked benchmark from named suggestion-profile blocks, defaulting to `household_core` plus `person_demographics`. This keeps the fuller benchmark path aligned with `synthpopcan microdata suggest-tree-columns` and avoids long manual column lists while preserving the explicit-column mode for experiments.

Household/person linkage design:

- Treat tree-based generation as a hierarchical workflow, not as independent household and person generators.
- Generate synthetic households first. Each household record receives household-level attributes such as geography, household size, tenure, dwelling type, income band if available, and family or household structure.
- Generate people second, conditional on each generated household. The person generator should receive household context such as geography, household size, tenure, household or family type, and any other household attributes used during training.
- Preserve linkage through generated identifiers: `synthetic_household_id` on household rows and both `synthetic_person_id` and `synthetic_household_id` on person rows.
- Validate both levels: household outputs against household margins, person outputs against person margins, and linked outputs against structural checks such as household size matching the number of generated people. Status: `synthpopcan validate linked-output` checks that person rows reference known households and that `household_size` matches the number of linked people.

Model distribution and privacy-release design:

- Support two model artifact modes:
  - Private working models: trained locally from restricted microdata, useful for experimentation, and not marked as publishable.
  - Publishable models: packaged only after passing SynthPopCan disclosure-risk checks, with no raw source records and clear provenance metadata.
- Add release-oriented commands such as `synthpopcan tree audit-model ...` and `synthpopcan tree package-model ... --require-privacy-pass` before encouraging public model sharing.
- A trained model from restricted microdata is not automatically safe to publish just because it is a model. The tool should make accidental publication of a leaky model difficult.
- Privacy checks for publishable model artifacts should include:
  - No raw rows, source identifiers, household identifiers, bootstrap sample indices, cached training data, or debug example records stored in the package.
  - Minimum support thresholds for terminal leaves or model-equivalent subgroups.
  - Rare-combination checks so generated rows do not reproduce rare exact combinations from the source microdata, especially for linked household/person records.
  - Category coarsening recommendations or requirements when fields create overly specific combinations.
  - Geography thresholding, with Canada and province-level models treated as the likely first distributable targets and smaller geographies requiring stronger checks.
  - Person-household linkage checks, because rare household structures plus person compositions can become identifying even when individual rows look ordinary.
  - Provenance metadata covering source description, columns used, geography level, training parameters, random seed, package date, privacy-audit result, and warnings.
  - Model simplification constraints such as minimum leaf size, pruning, maximum depth, or equivalent constraints depending on the chosen estimator.
- Avoid claiming that these checks make a model absolutely privacy safe. The intended claim is narrower: publishable model artifacts have passed SynthPopCan disclosure-risk checks and still require appropriate review before public distribution when trained from restricted sources.

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
- Tests cover command parsing and one tiny end-to-end IPF run from exported microdata seed rows through validation.

Usability helper principle:

- For every workflow that requires source-specific knowledge, add companion helper commands before expecting users to hand-author configuration. Prefer discoverable helpers such as `inspect`, `search`, `template`, `doctor`, `explain`, `preview`, and dry-run/JSON output modes. This is especially important for digital humanities users who may understand the research question well but not the StatCan file formats or package internals.
- Each complex normalization workflow should answer three questions from the CLI: what is in this source file, what starter configuration can I use, and what will be produced before I run the full synthesis step?

Current implementation notes:

- A fixture integration test covers `microdata export-seed -> ipf fit --report -> validate controls` for a tiny `statcan-2016-hierarchical` person-level workflow.
- CLI refactoring has gone far enough for the current pass; revisit command-module boundaries after the first tree-based generator pass is complete.

### 8. Validation Reports

Add repeatable validation before building a web UI around the workflow.

Deliverables:

- Marginal fit tables. Status: complete for validating IPF weights and expanded rows against normalized controls.
- Distribution comparisons.
- Geography-level diagnostics.
- Tree output distribution checks. Status: complete for comparing generated tree rows to training-view distributions with target, joint-target, conditioning, and unknown-category checks.
- Household/person consistency checks. Status: complete for linked tree outputs with `synthpopcan validate linked-output`.
- Machine-readable JSON plus human-readable Markdown or HTML report output. Status: JSON and Rich table output complete for control validation; Markdown/HTML reports pending.

Acceptance criteria:

- Every synthesis run can produce a validation report. Status: complete for `synthpopcan validate controls`.
- Failed validation thresholds can return a non-zero CLI exit code for automation. Status: complete for `synthpopcan validate controls`.
- Tree-generated flat outputs can be checked with `synthpopcan validate tree-output --generated ... --training ... --target-columns ...`.
- Linked household/person outputs can be checked with `synthpopcan validate linked-output --households ... --persons ...`.

### 9. Web App

Start the web app only after the library and CLI contracts are stable enough.

Likely first version:

- Local-only app.
- Select source roots and normalized controls.
- Configure an IPF run.
- Choose prepared tree model artifacts for tree-based generation.
- Show run progress and validation summaries.
- Download generated population and report artifacts.

Model training boundary:

- Do not expose model training in the first web app.
- Treat `microdata export-training`, `tree train`, future `tree audit-model`, and future `tree package-model` as maintainer/developer CLI and Python-library workflows.
- The web app should consume prepared model artifacts, not restricted microdata. Users should be able to choose a prepared model, select geography/scope, generate synthetic household/person rows, inspect validation summaries, and export outputs.
- Prepared models used by the web app should include provenance, release class, privacy/disclosure-risk metadata, version information, and warnings.
- If training is ever exposed in a UI, make it a separate advanced local-only mode with strong warnings and no publish/distribute action by default.
- This boundary supports the browser-first/Pyodide direction: loading JSON model artifacts and generating rows in-browser is much more plausible than training from restricted microdata in-browser.

Performance and runtime concerns:

- Prefer a browser-first web app that does as much work as possible in-browser and avoids a backend unless a workflow clearly needs one.
- Define practical time guarantees for web-app workflows before exposing long-running synthesis operations to users.
- Use the developer IPF benchmarks as early regression checks, then add user-facing estimates or previews for large/sparse runs.
- Evaluate browser-side Pyodide/WebAssembly as the preferred runtime for demos and small-to-moderate local workflows. Compare it against a local Python backend or server-side job process only where data size, memory pressure, or run time breaks the browser-first model.
- Keep heavy full-data runs out of the browser unless benchmarks show predictable memory and runtime behavior.

Deferred until needed:

- User accounts.
- Remote job execution.
- Large-data upload management.
- Hosted public deployment.

### 10. Documentation Site

Build a documentation site once the CLI and library surfaces have enough stable shape to document.

Deliverables:

- Sphinx documentation scaffold under `docs/`. Status: initial scaffold added with MyST Markdown support, workflow pages, autodoc, and the Read the Docs theme.
- Read the Docs configuration for hosted documentation builds. Status: initial `.readthedocs.yaml` and `docs/requirements.txt` added.
- User-oriented CLI guides for IPF, StatCan source discovery, local data setup, and microdata inspection.
- API reference generated from library docstrings for stable public modules.
- Data access notes that explain which sources are public fetches, which require local/private files, and how ignored data roots should be organized.
- Keep README examples short; move reproducible workflow guides into `docs/workflows/` so they can be adopted by the Sphinx site later.

Acceptance criteria:

- Documentation builds locally without warnings for tracked pages.
- Read the Docs can build the docs from a clean checkout without private data.
- README links to the hosted docs once the public site is available.

## Near-Term Slice

Current active slice: StatCan/IPF usability.

The original near-term computational core is complete: typed controls and seed
samples, local source inspection, `controls from-csv`, and the first IPF engine
are all in place. The next work should make the public-data-to-IPF path easier
for non-specialist users:

1. Add helper commands that inspect downloaded StatCan WDS tables and suggest
   starter `controls from-wds` settings. Status: first `controls wds inspect`
   helper added for local WDS ZIPs.
2. Improve the WDS metadata/search path so users can choose plausible product
   IDs and understand whether a table has useful dimensions before downloading.
3. Add starter mapping/template helpers for common StatCan dimensions such as
   age, sex, geography, and household structure where stable labels exist.
4. Make `ipf check-inputs` the expected next step after control normalization,
   with clearer category-mismatch guidance for humanities users.
5. Keep README examples short and move reproducible walkthroughs into
   `docs/workflows/`.

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
- Sphinx and Read the Docs setup once the core CLI workflows are stable enough to document.
- Project icon and lightweight visual identity for the eventual docs site and web app.
- Packaging and publishing.

## Testing Policy

Every new feature should include tests at the smallest practical scale:

- Unit tests for pure transformations and algorithms.
- CLI tests for command behavior and output files.
- Fixture-based integration tests for one complete workflow.
- Coverage measurement with `pytest-cov` or an equivalent tool once the core workflow surface stabilizes.
- No tests should require full private or raw data caches.

Full-data smoke tests can be added later as optional local commands, documented separately from the default test suite. A modest coverage gate should wait until the public API and CLI command families stop shifting rapidly; until then, use coverage reports to find blind spots rather than as a hard release criterion.

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
- First derived household/person output schema from the single-file 2016 hierarchical PUMF.
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
