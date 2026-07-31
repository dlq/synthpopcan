# Automated Workflow Scenario Inventory

This is a **maintainer-facing acceptance-test inventory**, not part of the
public user documentation. Reader-facing walkthroughs begin with [Getting
Started](../docs/getting-started.md), the [Local Web App](../docs/web-app.md),
[IPF](../docs/ipf.md), [Generate From a Model
Package](../docs/tree-generate.md), or [Small-Area Linked
Synthesis](../docs/small-area.md).

Tests, documentation, and release checks refer to the permanent IDs below
rather than copying complete command transcripts. A scenario can be expanded or
retired, but its ID is not reused.

## SCN-IPF-001

**Seed rows to validated IPF output.** A beginner or notebook user starts with
seed rows and public control totals, fits weights, keeps the fit report, and
validates the weighted or expanded artifact.

Acceptance evidence: seed and weight CSV headers and row counts, a converged
fit report, and a passing control-validation report. The tracked fixture lives
under `tests/fixtures/workflows/microdata_ipf/`.

## SCN-WDS-001

**StatCan WDS table to validated weights.** A command-line user creates a
category mapping template from a downloaded public WDS table, normalizes
controls, checks the seed/control match, fits weights, and validates the result.

Acceptance evidence: mapping template, normalized controls, passing input
check, converged fit report, and passing control validation. The tracked fixture
lives under `tests/fixtures/workflows/wds_ipf/`.

## SCN-TREE-001

**Hierarchical microdata to reviewed tree output.** A researcher derives a
training table, trains a model under explicit conditions, generates rows, and
validates generated target distributions against the training view.

Acceptance evidence: training CSV, model privacy metadata, generated CSV, and
a passing tree-output validation report. The tracked fixture lives under
`tests/fixtures/workflows/microdata_tree/`.

## SCN-MODEL-001

**Prepared linked model to calibrated household output.** A user packages
reviewed linked household/person models, generates candidates, validates links,
then calibrates generated household candidates to controls.

Acceptance evidence: package metadata and provenance, linked household/person
CSVs, passing link validation, converged weights, expanded households, and
passing control validation.

## SCN-SMALLAREA-001

**Linked candidates to small-area artifacts.** A user supplies linked
household/person candidates plus household controls and optional person
controls, assigns whole households to target geographies, and keeps the
calibration report beside both output CSVs.

Acceptance evidence: linked assigned CSVs, household and person margin
summaries, fractional and integerized residuals, convergence status, input
warnings, and preserved household/person links.

## SCN-WEB-001

**First durable browser IPF run.** A first-time user loads the bundled demo seed
and controls, streams both uploads to the local workspace, passes Python
preflight, starts a backend IPF job, and reopens its persisted result after a
page refresh.

Acceptance evidence: Runs workbench with one New run action, input diagnostics,
backend progress, fit summary, bounded weighted preview, artifact links,
reproduction command, refresh recovery, cancellation and blocked-preflight
coverage, and no browser console errors.

## SCN-WEB-002

**First browser prepared-model run.** A first-time user selects or uploads a
safe prepared linked model package, inspects its provenance and privacy summary,
generates linked household/person rows, reviews validation, and receives both
CSV downloads.

Acceptance evidence: package summary, generation result, validation summary,
household and person previews, two download links, and no browser console
errors.

## SCN-WEB-003

**Run a small-area linked synthesis.** A researcher chooses a published or
local linked model or uploads existing linked candidates, supplies normalized
geographic controls, configures the candidate and calibration pool sizes, and
passes Python-backed preflight before starting a durable synthesis.

Acceptance evidence: target geography and output-row estimates, workspace
capacity, durable progress, residual and convergence diagnostics, linked
artifacts, an optional map, and recorded `geo synthesize` or `geo calibrate`
reproduction metadata. Exact reproduction of model conditions and optional map
creation is tracked for `0.6.3`.

## SCN-GEO-001

**Prepare and finalize a bounded Québec 2021 DA proof.** A researcher selects
metropolitan and rural dissemination areas through authoritative 2021
relationships, prepares exact controls and matching boundaries, and finalizes
the proof only after calibration, linkage, geography, and map evidence agree.

Acceptance evidence: explicit 2021 DA identity, deduplicated relationship
selection, matched profile and boundary identifiers, resource hashes, bounded
household totals, converged fractional fits, reported integer residuals,
preserved household/person links, parent summaries, and cross-vintage or
missing-input rejection.

## SCN-NATIONAL-001

**Prepare and resume a bounded national DA/ADA plan.** A maintainer prepares
restartable province/territory batches from the appropriate official 2021
profile adapter, canonical boundaries, and DGRF relationships, then executes a
bounded batch from a verified reusable candidate pool.

Acceptance evidence: DA/ADA plan identity, complete jurisdiction coverage,
explicit exclusions and storage estimates, atomic batch output, candidate-pool
integrity, deterministic resume behavior, linked validation, artifact hashes,
and aggregate geography summaries.

## SCN-ENRICH-001

**Attach a researcher-supplied normalized sidecar without changing the base
population.** A researcher registers a source and immutable resource revision,
imports a normalized geography-keyed layer, reviews coverage, and later
revalidates every recorded hash.

Acceptance evidence: source/resource lineage, explicit geography compatibility,
unique linkage keys, unmatched-source and unmatched-base reporting, sidecar and
manifest publication, byte-for-byte preservation of the linked household,
person, and manifest files, and corruption detection.

## Test Ownership

Python scenarios live in the closest workflow or domain test module and carry
`@pytest.mark.scenario("SCN-...")`. Browser scenarios live in
`tests/web/scenarios.spec.mjs`. `tests/test_docs.py` fails if an inventory ID
does not have a test reference or if a test references an undocumented ID.

Private Census files, live StatCan requests, and province-scale timing runs are
not part of these deterministic scenarios. They remain documented opt-in smoke
tests and benchmarks.
