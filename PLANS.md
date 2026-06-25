# SynthPopCan Plan

Status: working roadmap\
Last updated: 2026-06-25

## Goal

Build SynthPopCan as a Python library, CLI, and local web app for Canadian synthetic population generation.

This file is the live roadmap: it should say what is next, what is deferred,
and which design decisions remain open. Detailed completed implementation
status and benchmark notes belong in the Sphinx documentation, especially
`docs/status.md`; research background and source synthesis belong in `NOTES.md`.

The near-term scope is deliberately narrower than the full proposal:

1. Build synthetic populations through iterative proportional fitting from StatCan margin/control tables.
1. Build household- and person-level synthetic populations with a tree-based synthetic population generator using pluggable census microdata sources. The Canadian 2016 Census material staged locally is the first available microdata source, not the tool boundary.
1. Keep environmental, school, healthcare, food, and broader enrichment data as later extensions unless they are needed for validation or demos.

Current high-priority implementation step: build the small-area linked
synthesis bridge. The project already has broad-geography linked
household/person model generation and Census Profile tooling; the next major
workflow must fetch or reuse small-area Census Profile controls, assign
generated linked households to target geographies, calibrate household rows
against those controls, preserve person links, and validate both the small-area
margins and household/person structure.

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

1. `synthpopcan` CLI

   - Inspect local source files.
   - Normalize margins.
   - Run IPF synthesis.
   - Train or apply the tree-based synthetic population generator.
   - Validate and export generated populations.

1. Local data workspace

   - Ignored `data/raw` and `data/private` folders.
   - Tracked manifests only when they are public-safe and useful.
   - Small test fixtures under `tests/fixtures` when needed.

1. Web app

   - Run configuration UI.
   - Source and geography selection.
   - Progress and diagnostics.
   - Validation reports and export downloads.

## Milestones

### 0. Repository Baseline

Status: complete.

Current state:

- Git repository initialized.
- README, research notes, license, package scaffold, CLI, web app, and tests are in place.
- Large data and private source material are ignored.
- `NOTES.md` captures the local proposal/materials plus research and source
  synthesis for population synthesis.

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
- Keep CSV as the beginner-facing data exchange format. If Arrow/Parquet-style
  structures become useful later, treat them as internal or advanced
  performance/export options rather than required concepts for humanities users.

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

IPF and attribute coverage:

- IPF cannot add a column that is absent from the seed/generated population.
  Every control dimension must already map to a seed column before it can be
  used directly in fitting.
- StatCan tables with useful dimensions that are missing from the seed should
  be treated as enrichment or modelling candidates, not direct IPF controls.
  A separate model, lookup, public cross-tab, or recoding step must add the
  column first; IPF can then calibrate the enriched rows.
- `ipf check-inputs` keeps making this distinction explicit for users: usable
  controls, missing-column controls, category mismatches, and enrichment/modeling
  next steps for absent attributes. This is especially important for humanities
  users exploring unfamiliar StatCan tables.
- Output metadata should eventually track column provenance: source microdata,
  recoded source column, model-generated column, enriched public-data column,
  IPF weight/calibration output, and synthetic identifier.

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
1. Keep expanded output explicit through a separate `ipf expand` command. Status: complete.
1. Precompute record membership indexes for each margin cell. Status: complete in the pure-Python fitter.
1. Stream expanded rows directly to CSV instead of building the full expanded population in memory. Status: complete.
1. Add benchmarks or performance tests for easy, moderate, and high-cardinality fixtures. Status: complete for developer-facing `scripts/benchmark_ipf.py`; not exposed as a user CLI workflow.
1. Improve non-convergence diagnostics and CLI reporting. Status: partially complete; the CLI now fails closed on non-convergence, can write JSON fit diagnostics, can print a human-readable report table, and reports the largest residual with a plain-language tip. Richer validation reports that explain whole-run inconsistency patterns are still pending.
1. Consider NumPy, Polars, and possibly sparse arrays after the pure-Python indexed version establishes the right data contracts. Status: first benchmark characterization tests added; cases now report average records per margin cell plus a dependency hint, and an opt-in timing test runs with `SYNTHPOPCAN_PERF_TESTS=1 uv run pytest tests/test_benchmarks.py -m performance`. Experimental backend benchmarks show current pure Python remains fastest for one-iteration dense cases, while NumPy `bincount` and SciPy CSR are much faster for repeated high-cardinality updates; Polars appears better suited to table ingestion/prep than the iterative IPF update kernel.
1. Later, prototype an optional SciPy CSR IPF backend for large or sparse StatCan controls. Candidate trigger conditions: many geography-crossed cells, low average seed records per margin cell, or repeated non-converged/high-iteration updates. Keep the current pure-Python indexed backend as the default until the sparse backend has production tests, clear dependency implications, and web-app/Pyodide feasibility notes.

Detailed IPF timing and backend comparison notes now live in `docs/status.md`.

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
- Document assumptions in `NOTES.md` or a future data-access note when source interpretation matters.
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
- `synthpopcan tree package-linked-models` packages household and person models together only after both audits pass without warnings. It validates household/person model levels and the household-size linkage column, requires linked training-manifest provenance, reviewed source provenance, and a human review note, checks manifest model paths against the packaged models or verifies release manifests connecting private source models to publishable release copies, embeds both model artifacts and both audit reports, and marks the package as a publishable candidate only when both model audits say so.
- `synthpopcan tree inspect-package` provides a compact reader-facing package summary as a Rich table or JSON, including source provenance, geography/profile, privacy flags, model sizes, audit summaries, release manifests, and review note without dumping the embedded full model payloads.
- `synthpopcan tree generate-from-package` generates linked household/person CSVs directly from a publishable linked package, refusing packages that are not marked `publishable_candidate`. Its generation manifest points back to a compact package inspection summary, source provenance, generation conditions, outputs, and random seed.
- Linked conditional-frequency generation now caches repeated condition
  selections and uses precomputed cumulative weights with binary-search
  sampling, fixed-schema CSV writing, and a shared linked-run RNG instead of
  constructing one random generator per household. A local Montréal package
  smoke test generated 100,000 household rows and 231,637 person rows to CSV in
  about 2.78 seconds after these changes, compared with about 34.7 seconds
  before the optimization pass. CSV remains the user-facing output.
- Initial audit on the local 2016-derived models with `min_support=50,max_purity=0.95`: conditional-frequency had 157 groups, minimum support about 503.7, no low-support groups, and 2 pure groups; CART had 58 leaves, minimum support 81, no low-support or high-purity leaves. Both remained `private_working` and `publishable_candidate: false`.
- `synthpopcan tree generate-linked` performs the first household-then-person generation pass from separate household and person models, writing linked `synthetic_household_id` and `synthetic_person_id` CSV outputs.
- `synthpopcan tree generate` and `synthpopcan tree generate-linked` accept `--manifest-out` for a lightweight JSON provenance sidecar with model path, model type, release class, output paths, conditions, requested random seed, and effective random seed.
- `synthpopcan tree train-linked` trains household and person models directly from a mixed `statcan-2016-hierarchical` microdata file using named suggestion-profile blocks. The first user-facing path requires `--suggested-blocks`, defaults to `household_core` plus `person_demographics`, writes both model JSON files, and writes a training manifest with source, selected blocks, training summaries, model paths, method, and random seed.
- `synthpopcan tree train-linked` now makes geography advisor recommendations directly actionable with `--geography-column`, `--geography-value`, and `--target-profile full|reduced|minimal`. This lets a user train a likely PR/CMA with the full suggested blocks, a borderline geography with reduced targets, or a small province/territory with a minimal local-experiment target set without hand-authoring training CSVs.
- Local linked-model benchmark and release-workflow evidence now lives in
  `docs/status.md`.
- `scripts/benchmark_tree_linked.py` remains the developer-facing linked
  household/person benchmark harness. It should stay optional because it depends
  on ignored local/private data.
- `synthpopcan microdata suggest-tree-columns` and `microdata tree-geography-feasibility` provide source-specific column and geography
  advice. Keep future adapter profiles explicit by source year/product instead
  of assuming all Canadian census microdata uses the 2016 hierarchical layout.

Household/person linkage design:

- Treat tree-based generation as a hierarchical workflow, not as independent household and person generators.
- Generate synthetic households first. Each household record receives household-level attributes such as geography, household size, tenure, dwelling type, income band if available, and family or household structure.
- Generate people second, conditional on each generated household. The person generator should receive household context such as geography, household size, tenure, household or family type, and any other household attributes used during training.
- Preserve linkage through generated identifiers: `synthetic_household_id` on household rows and both `synthetic_person_id` and `synthetic_household_id` on person rows.
- Validate both levels: household outputs against household margins, person outputs against person margins, and linked outputs against structural checks such as household size matching the number of generated people. Status: `synthpopcan validate linked-output` checks that person rows reference known households and that `household_size` matches the number of linked people.

Model output to IPF calibration:

- Treat the Pritchard-style bridge as a staged workflow: generate candidate
  household/person rows from a model package, check whether selected StatCan
  controls are compatible with those rows, fit IPF weights, integerize or expand
  the calibrated output, then validate both margins and household/person
  linkage.
- The model generator supplies plausible multivariate structure and extra
  columns. IPF supplies calibration to official controls for columns already
  present on the generated rows.
- Prefer household-level calibration first for linked populations: fit or
  integerize households, let persons inherit household context, then validate
  person margins. Add person-level or joint household/person calibration only
  after the simpler staged workflow is well understood.
- Keep missing controlled attributes out of IPF until an explicit enrichment
  step adds them to generated rows. Future commands may add an `enrich` or
  similarly named workflow, but it should be separate from `ipf fit` so users do
  not think IPF can invent absent variables.

High-priority small-area linked synthesis bridge:

- The next implementation slice should turn the staged bridge above into an
  explicit small-area workflow. The 2016 hierarchical PUMF does not provide
  census tract, aggregate dissemination area, or dissemination area identifiers
  for source households; Census Profile small-area tables provide aggregate
  controls rather than household rows. The software bridge is therefore:
  generate plausible linked household/person candidates from a prepared model
  package, fit household candidates separately to each target geography's
  household controls, assign selected households to small-area identifiers, copy
  linked persons into the assigned households, and validate small-area controls
  plus household/person links.
- Geography strategy: use Montreal census tracts only as the first prototype
  because those files are already staged and familiar. For province-wide or
  country-wide synthesis, use 2016 Census Profile `ada` controls first because
  aggregate dissemination areas cover the country and are less sparse than
  dissemination areas. Add `da-all` support next for finer, wall-to-wall
  synthesis after calibration and validation are stable.
- Source-fetch strategy: add explicit workflow tasks for
  `synthpopcan statcan census-profile fetch --year 2016 --geo-level ada` and
  `--geo-level da-all`, followed by reviewed `controls from-census-profile`
  mappings for household size, tenure, dwelling type, and any person controls
  chosen for validation.
- First-pass scope should be household-level small-area calibration. Person rows
  inherit the assigned small-area geography from households; person-level
  small-area margins should be validated and reported, then added as a later
  joint or staged calibration step once the household bridge is stable.
- Detailed implementation plan:
  `docs/superpowers/plans/2026-06-25-small-area-linked-synthesis.md`.

Model distribution and privacy-release design:

- Support two model artifact modes:
  - Private working models: trained locally from restricted microdata, useful for experimentation, and not marked as publishable.
  - Publishable models: packaged only after passing SynthPopCan disclosure-risk checks, with no raw source records and clear provenance metadata.
- Use release-oriented commands such as `synthpopcan tree audit-model ...`, `synthpopcan tree prepare-model-release ...`, `synthpopcan tree release-readiness ...`, and `synthpopcan tree package-linked-models ...` before encouraging public model sharing.
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
synthpopcan data doctor
synthpopcan sources inspect ROOT
synthpopcan controls validate controls.csv
synthpopcan controls from-csv SOURCE --out controls.csv
synthpopcan controls from-wds SOURCE.zip --dimensions "GEO,Age group,Sex" --count-column VALUE --out controls.csv
synthpopcan controls from-census-profile PROFILE.csv --mapping census-profile-mapping.json --out controls.csv
synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv
synthpopcan ipf fit --seed seed.csv --controls controls.csv --out weights.csv --report fit-report.json
synthpopcan ipf expand --weights weights.csv --out synthetic.csv
synthpopcan microdata inspect hierarchical.csv --input-format statcan-2016-hierarchical
synthpopcan tree train training.csv --level person --target-columns AGEGRP,SEX --conditioning-columns TENUR,household_size --out person-model.json
synthpopcan tree generate person-model.json --rows 100 --out synthetic-persons.csv
synthpopcan validate controls --population weights.csv --controls controls.csv --kind weights
synthpopcan validate linked-output --households synthetic-households.csv --persons synthetic-persons.csv
```

Acceptance criteria:

- Each command has help text and clear failure messages.
- Commands write explicit output files rather than hidden state.
- Tests cover command parsing and one tiny end-to-end IPF run from exported microdata seed rows through validation.

Usability helper principle:

- For every workflow that requires source-specific knowledge, add companion helper commands before expecting users to hand-author configuration. Prefer discoverable helpers such as `inspect`, `search`, `template`, `doctor`, `explain`, `preview`, and dry-run/JSON output modes. This is especially important for digital humanities users who may understand the research question well but not the StatCan file formats or package internals.
- Each complex normalization workflow should answer three questions from the CLI: what is in this source file, what starter configuration can I use, and what will be produced before I run the full synthesis step?

Beginner-lane CLI direction:

- The current CLI has useful building blocks, but the top-level surface is
  already busy for a new humanities user. Keep the structured expert command
  families, but add a small set of plain-language workflow commands or aliases
  that cover the most common paths without exposing every intermediate tool.
- Primary beginner workflows should be easy to recognize: launch the web app,
  find StatCan tables, make controls, run IPF, generate from a prepared model,
  and check the result.
- Candidate beginner-facing aliases, implemented as wrappers over the existing
  command families rather than replacements:

```bash
synthpopcan find-tables "population age sex"
synthpopcan make-controls --from-wds 98100001 --out controls.csv
synthpopcan run-ipf --seed seed.csv --controls controls.csv --out weights.csv
synthpopcan generate-from-model model-package.json --households 100 --out-dir output/
```

- Keep lower-level commands such as `controls from-wds`, `statcan wds fetch`,
  `tree train-linked`, `tree audit-model`, `tree package-linked-models`, and
  `release-readiness` available for power users and maintainers, but do not
  make them the first documented path for new users.
- Treat model training, auditing, packaging, and release readiness as advanced
  or maintainer workflows. The common user path should consume prepared,
  reviewed model packages rather than require users to understand the whole
  training and privacy-review pipeline.
- Revisit command naming before the first public documentation pass. Commands
  should read as user tasks where possible; expert implementation terms should
  remain available but be clearly labelled as advanced.

Library-surface direction:

- Add a small stable public Python API layer once the core workflows settle.
  Status: first pass complete through `synthpopcan.api` and top-level
  `synthpopcan` imports. Users no longer need to discover lower-level modules
  first for common notebook and teaching workflows.
- Current stable beginner imports:

```python
from synthpopcan import fit_ipf
from synthpopcan import expand_population
from synthpopcan import read_controls
from synthpopcan import generate_from_model
```

- Keep implementation modules importable for advanced use, but document the
  small stable API as the first stop for notebooks, teaching material, and
  humanities research scripts.
- Maintain the small API as a deliberately narrow facade: IPF file/path helpers,
  compact weight output, expanded rows when explicitly requested, prepared model
  package generation, and linked household/person CSV writing. Add new top-level
  functions only when they describe a common user workflow rather than an
  implementation detail.

Current implementation notes:

- A fixture integration test covers `microdata export-seed -> ipf fit --report -> validate controls` for a tiny `statcan-2016-hierarchical` person-level workflow.
- `synthpopcan.api` exposes `read_seed`, `read_controls`, `fit_ipf`,
  `write_weights`, `expand_population`, `read_model_package`,
  `generate_from_model`, and `write_population`, with autodoc-ready docstrings
  and tests covering the beginner IPF and linked-model paths.
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
- Initial app foundation: `synthpopcan serve` starts a packaged local app and opens the user's default browser with Python's cross-platform `webbrowser` support. Status: first pass complete.
- Treat `synthpopcan serve` as a convenience static-file launcher, not as the first step toward a required Python API backend.
- Keep the default architecture frontend-first: file selection, model loading, IPF setup, small-to-moderate generation, validation summaries, and exports should run in the browser when practical.
- First browser implementation uses pure modern JavaScript ES modules, no npm package, no build step, and a module Web Worker for IPF/model generation jobs. Status: first pass complete; Biome is wired in for HTML/CSS/JavaScript formatting and linting.
- Keep the first app simple: expose basic SynthPopCan functionality rather than the whole CLI.
- Support two generation workflows first: IPF from margin/control tables, and synthetic population generation from existing prepared model packages. Status: first pass complete.
- Select source roots, seed data, and normalized margin/control tables for IPF.
- For IPF users without files, provide browser starter helpers: runnable demo seed/control files, seed/control templates from chosen dimensions, and StatCan WDS search/metadata inspection where browser access allows it. Status: first pass complete with a local Python helper for WDS seed/control generation when browser cross-origin rules block direct ZIP access.
- Configure and run an IPF generation workflow. Status: first pass complete for browser weights and guarded expanded output.
- Choose existing prepared tree model artifacts for tree-based generation. Status: first pass complete with a safe demo package served by the local helper and file-upload fallback.
- Show run progress, generated-output previews, and validation summaries. Status: first pass complete for small browser runs; fuller validation reports remain pending.
- Download generated population and report artifacts. Status: first pass complete for IPF weights/expanded rows and linked household/person output.

Model training boundary:

- Do not expose model training in the first web app.
- Do not expose model generation, model training, model auditing, or model packaging in the first web app.
- Treat `microdata export-training`, `tree train`, future `tree audit-model`, and future `tree package-model` as maintainer/developer CLI and Python-library workflows.
- The web app should consume prepared model artifacts, not restricted microdata. Users should be able to choose a prepared model, select geography/scope, generate synthetic household/person rows, inspect validation summaries, and export outputs.
- Prepared models used by the web app should include provenance, release class, privacy/disclosure-risk metadata, version information, and warnings.
- If training is ever exposed in a UI, make it a separate advanced local-only mode with strong warnings and no publish/distribute action by default.
- This boundary supports the browser-first/Pyodide direction: loading JSON model artifacts and generating rows in-browser is much more plausible than training from restricted microdata in-browser.

Performance and runtime concerns:

- Prefer a browser-first web app that does as much work as possible in-browser and avoids a backend unless a workflow clearly needs one.
- Require an explicit reason before adding any server-side route beyond serving packaged static assets.
- Define practical time guarantees for web-app workflows before exposing long-running synthesis operations to users.
- Use the developer IPF benchmarks as early regression checks, then add user-facing estimates or previews for large/sparse runs.
- Evaluate browser-side Pyodide/WebAssembly as the preferred runtime for demos and small-to-moderate local workflows. Compare it against a local Python backend or server-side job process only where data size, memory pressure, or run time breaks the browser-first model.
- Keep heavy full-data runs out of the browser unless benchmarks show predictable memory and runtime behavior.
- Investigate browser streaming exports for larger web-app runs: use
  `ReadableStream`, `TextEncoderStream`, Web Workers, and the File System Access
  API where supported so CSV chunks can be written without building a giant
  in-memory Blob. Treat this as an optional advanced/browser-support-dependent
  path, keep hard memory guardrails, and show an exact CLI command when
  streaming file writing is unavailable. If full-population exports need to be
  reliable from the web UI, consider a narrow local-helper route that streams
  files server-side while the browser acts as the control panel.
- Direct WDS ZIP normalization in the browser is still a later step; it needs a browser ZIP parser or a preprocessed browser-friendly table source.
- The local Python helper is acceptable for workflows that need StatCan download
  support, premade model listing, or other local package assets. Keep its scope
  narrow and preserve browser-only fallbacks for static deployments.

Visual direction:

- Use GCWeb-inspired public data tool styling: accessible forms, sober typography, white page background, dark blue actions, red accenting, simple panels, and clear status text.
- Do not copy Government of Canada or StatCan branding, wordmarks, signatures, or page chrome. SynthPopCan should feel compatible with public-data workflows without implying official affiliation.

Deferred until needed:

- User accounts.
- Remote job execution.
- Large-data upload management.
- Hosted public deployment.

### 10. Documentation Site

Build a documentation site once the CLI and library surfaces have enough stable shape to document.

Deliverables:

- Sphinx documentation scaffold under `docs/`. Status: topic-oriented Sphinx
  site added with MyST Markdown support, a field primer, command sections,
  selective autodoc API reference, and the Read the Docs theme.
- Read the Docs configuration for hosted documentation builds. Status: initial `.readthedocs.yaml` and `docs/requirements.txt` added.
- User-oriented CLI guides for IPF, controls, StatCan source discovery, tree
  models, validation, local data setup, and source inspection. Status: first
  topic-pass complete under `docs/`.
- API reference generated from library docstrings for stable public modules.
  Status: selective `docs/api.rst` added and public API docstrings added for
  controls, IPF, microdata, StatCan, tree, and validation modules.
- Data access notes that explain which sources are public fetches, which require local/private files, and how ignored data roots should be organized. Status: first pass added in `docs/data.md` and `docs/sources.md`.
- Keep README examples short; keep reproducible workflows in topic pages such as
  `docs/ipf.md`, `docs/controls.md`, `docs/statcan.md`, and `docs/tree.md`.
- Treat documentation examples as tested interface surfaces, not decorative
  snippets. Good examples are hard to craft: every getting-started or workflow
  example should be checked for runnable commands, real fixture paths, existing
  column names, coherent file flow, and consistency with the surrounding
  narrative before it is treated as done.
- Documentation should distinguish beginner workflows from advanced/maintainer
  workflows. The first page should not expose every CLI command; it should route
  users to the web app, IPF from StatCan tables, generated-from-model workflows,
  and only then advanced microdata/model-training/release workflows.
- The field primer should remain part methods primer, part field introduction,
  part tool reference: explain interpretive risks, cite relevant methods, and
  map concepts to commands without hiding caveats behind CLI syntax.

Acceptance criteria:

- Documentation builds locally without warnings for tracked pages.
- Read the Docs can build the docs from a clean checkout without private data.
- README links to the hosted docs once the public site is available.

## Near-Term Slice

Current active slice: small-area linked household/person synthesis.

This slice should build the missing bridge between broad-geography PUMF-derived
linked household/person candidates and small-area Census Profile controls. It
is the next substantive modelling step because it turns the existing IPF,
control-table, Census Profile fetch/normalization, tree-package,
linked-generation, and validation pieces into the first workflow that can
produce small-area-assigned linked households.

Previous active slice: public usability polish across the beginner API, web app,
CLI, and documentation. That work should continue opportunistically, but it is
no longer the main implementation priority.

Near-term usability priorities:

1. Add a beginner CLI guide that rhymes with the web app's two workflow cards:
   `synthpopcan guide`, `synthpopcan guide ipf`, and
   `synthpopcan guide model`. The guide should use the same beginner-facing
   labels as the web app: "IPF from margin tables" and "Generate from existing
   model". It should be read-only guidance first, pointing to the existing
   expert commands instead of creating a second implementation path. Keep the
   expert commands visible for automation and advanced users. Status: complete
   for the first read-only guide.
1. Make the web app's prepared-model workflow more realistic: support a
   backend-served model index, show model provenance and warnings clearly, keep
   model training out of the UI, and add stronger output previews/validation
   summaries. Status: in progress; the safe demo model is now served through a
   publication-style catalogue with release status, provenance, privacy notes,
   output shape, default generation settings, generated-output previews, and a
   first-pass linked household/person validation summary.
1. Promote the beginner Python API in the documentation and keep its examples
   runnable. The API reference should remain autodoc-driven, but workflow docs
   should show the short `import synthpopcan as spc` path first. Status: first
   pass complete; the docs landing page and beginner API guide now route users
   through the same two workflow labels as the web app and CLI guide.
1. Do a docs navigation pass: route readers first to the web app, IPF from
   StatCan tables, generated-from-model workflows, and only then advanced
   microdata/model-training/release material. Status: first pass complete in
   the Sphinx index and web app guide.
1. Start documentation-example checks for the most visible beginner workflows.
   The project goal is 100% line coverage, but add the gate gradually: use
   coverage reports to close blind spots while the public surfaces are still
   settling, then ratchet thresholds upward by module or workflow.

Remaining user-facing surface audits:

- Generated artifacts as user documents: review default filenames, CSV column
  names, JSON manifest fields, provenance text, and validation/report outputs
  so a non-programmer can reopen them later and understand what was generated,
  from which sources, with which caveats.
- Install and package metadata: review PyPI-facing text, classifiers, project
  URLs, license display, changelog/release notes, console-script metadata, and
  a clean install/package smoke test before public distribution.
- Published model catalogue UX: when real models exist, present geography,
  census vintage, source, privacy review status, release version, model size,
  generation limits, and known limitations clearly in both the web app and CLI.
- Full first-run dry run: test both beginner paths from a clean checkout or
  installed wheel with no private local data, starting from `synthpopcan --help`,
  `synthpopcan guide`, and `synthpopcan serve`.
- Future browser/npm surface: if the browser-side IPF/model-generation modules
  become reusable outside the Python package, design the npm-facing API and
  examples so the terminology rhymes with the Python API, CLI, and web app
  instead of creating a parallel vocabulary.

Recently completed first-pass work:

- Beginner Python API: top-level imports, `synthpopcan.api`, focused tests, and
  autodoc-ready docstrings.
- Web app: `synthpopcan serve`, browser IPF, generated-output previews, WDS
  seed/control generation through the local helper, prepared demo model
  selection, linked household/person generation, and Biome formatting/linting
  for web assets.
- Documentation: Sphinx/Read the Docs scaffold, first topic pages, library API
  page, selective autodoc reference, and short README pointers.

### StatCan/IPF Follow-Up Backlog

Completed StatCan/IPF implementation notes now live in
`docs/status.md`. Keep this section focused on remaining work.

- Improve WDS dimension/member inspection from metadata so `statcan wds explain`
  can preview candidate dimensions and members before downloading a ZIP.
  Status: first pass complete; `statcan wds explain` now includes bounded
  dimension/member previews and an IPF suitability status from WDS metadata.
- Add common mapping presets for recurring StatCan categories such as age, sex,
  geography, household size, and tenure when stable labels are available.
  Status: first WDS `canonical` preset added for common age and sex labels;
  broader geography, household-size, and tenure presets still need source-label
  review before they should be exposed.
- Add optional live smoke tests against one or two public WDS tables when
  network access is explicitly enabled. Status: first opt-in smoke tests added
  behind `SYNTHPOPCAN_LIVE_STATCAN=1` for WDS search, metadata/explain summary,
  and download-URL resolution without downloading a full ZIP.
- Explore NumPy, Polars, PyArrow, or sparse-array implementations after the
  pure-Python indexed fitter remains stable under more realistic controls.
- Add richer reports for inconsistent controls and whole-run non-convergence
  patterns. Status: first pass added fit-report control-total checks,
  inconsistent-control-total issues, report-level next steps, and Rich
  `ipf report` next-step rendering.
- Add concise next-step hints where they remove friction without adding noise.
  Status: first `controls from-wds` error hints added for missing WDS columns
  and unmapped category labels; `ipf check-inputs` now labels absent control
  dimensions as needing enrichment/modeling before IPF and points users to
  `ipf suggest-controls`.
- Add an explicit generate-then-calibrate workflow that uses prepared tree model
  outputs as IPF seed rows: `tree generate-from-package`, `ipf check-inputs`,
  `ipf fit`, `ipf expand`, and `validate controls`. This should document that
  IPF calibrates columns already present on generated rows and does not create
  missing variables. Status: first tracked workflow test and docs page added for
  household-level calibration from a linked model package.
- Plan a later enrichment workflow for useful StatCan dimensions that are not
  present in the microdata/model output. The immediate goal is naming,
  provenance, and user guidance; implementation can wait until the core
  generate-then-calibrate path is stable.
- Add calibration-control guidance for model outputs. Users need help deciding
  which StatCan margin tables should calibrate generated household/person rows.
  Candidate controls should be recommended only when their dimensions exist on
  the generated rows, their geography matches the model scope, their universe
  matches the generated unit, categories can be mapped cleanly, totals are
  internally consistent, and the controls are worth fitting rather than merely
  validating. Status: first `ipf suggest-controls --seed ...` helper added. It
  inspects generated columns, reports usable controls, flags missing/enrichment
  candidates, separates likely household controls from person controls, and
  prints next StatCan/IPF commands while keeping final table choice reviewable by
  the user.

### Tree Packaging Follow-Up Backlog

Completed tree packaging and distribution implementation notes now live in
`docs/status.md`. Keep this section focused on remaining work.

- Broaden publishable package review from fixture and local smoke tests toward
  a repeatable Canada/province/territory/large-CMA model-candidate workflow.
- Add stronger rare-combination and disclosure-risk checks before treating
  models trained from restricted microdata as public distribution candidates.
- Add clearer model-size and browser-readiness guidance for prepared packages,
  especially broad household models.
- Keep the web app boundary intact: the first app consumes prepared model
  artifacts and does not expose training from restricted microdata.

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
- Documentation site expansion, API reference, and hosted Read the Docs polish.
- Project icon and lightweight visual identity for the eventual docs site and web app.
- Possible npm package once browser-side IPF/model-generation modules have a stable reusable API. Until then, keep JavaScript as packaged static ES modules inside the Python project.
- Packaging and publishing.

## Testing Policy

The stable testing policy and current coverage baseline now live in
`docs/status.md`.

Roadmap implications:

- Keep the default suite fixture-based and free of private/raw data
  requirements.
- Start documentation-example checks for visible beginner workflows.
- Add `--cov-fail-under` only after the suite and public surfaces settle enough
  that the gate encourages discipline without blocking ordinary design
  iteration.
- Keep full-data smoke tests optional and documented separately from the
  default test suite.

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

- Exact dependency stack for arrays/tables/models: current default is pure
  Python for the indexed IPF kernel, scikit-learn where CART models are used,
  and later optional NumPy/SciPy CSR/Polars/PyArrow experiments for larger
  sparse or table-ingestion-heavy workflows.
- Whether schemas should remain dataclasses or move to Pydantic once the API surface stabilizes.
- First supported StatCan table format and access path. Current first pass:
  StatCan WDS search/metadata/fetch plus local WDS ZIP normalization; broader
  Census Profile and other table paths need documentation and usability review.
- First derived household/person output schema from the single-file 2016 hierarchical PUMF. Current first pass: linked household/person CSVs with synthetic identifiers and household-size linkage; publishable schemas for distributed model outputs still need review.
- Integerization method for the first IPF engine. Current first pass:
  deterministic integerized expansion for `ipf expand`; alternative
  integerization strategies remain a later quality/research topic.
- How far the web app can go as static packaged frontend plus browser runtime before a backend is justified. Current first pass: static/browser-first with a narrow local helper for WDS/model assets; Pyodide/WebAssembly and stricter runtime guarantees remain open.

## Done Means

The first useful version is done when a user can:

1. Point the CLI at a small seed sample and normalized control table.
1. Generate a synthetic population through IPF.
1. Validate the output against controls.
1. Inspect and normalize a small census-style household/person fixture.
1. Run an initial tree-based household/person synthesis prototype.
1. Reproduce the run from tracked code and ignored local data caches.
