# End-to-End Scenarios

This inventory is the stable source of truth for SynthPopCan's main user
stories. Tests, documentation, and release checks refer to the IDs below rather
than copying complete command transcripts. Scenario IDs are permanent; a
scenario can be expanded or retired, but its ID is not reused.

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

**First browser IPF run.** A first-time user loads the bundled demo seed and
controls, runs browser-local IPF, previews the result, and receives a weights
CSV download without a server-side synthesis job.

Acceptance evidence: meaningful first screen, demo-loaded status, successful
IPF result, CSV preview, download link, and no browser console errors.

## SCN-WEB-002

**First browser prepared-model run.** A first-time user selects or uploads a
safe prepared linked model package, inspects its provenance and privacy summary,
generates linked household/person rows, reviews validation, and receives both
CSV downloads.

Acceptance evidence: package summary, generation result, validation summary,
household and person previews, two download links, and no browser console
errors.

## Test Ownership

CLI scenarios live in `tests/test_workflows.py` and carry
`@pytest.mark.scenario("SCN-...")`. Browser scenarios live in
`tests/web/scenarios.spec.mjs`. `tests/test_docs.py` fails if an inventory ID
does not have a test reference or if a test references an undocumented ID.

Private Census files, live StatCan requests, and province-scale timing runs are
not part of these deterministic scenarios. They remain documented opt-in smoke
tests and benchmarks.
