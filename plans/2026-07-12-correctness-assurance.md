# Correctness Assurance Plan

Status: active\
Created: 2026-07-12\
Last updated: 2026-08-01\
Target: ongoing correctness and release evidence\
Next action: review and fixture the highest-priority vintage-specific category
crosswalks identified by the 2016/2021 CSD/CT/ADA/DA source-coverage inventory
before implementing expanded controls or making a new small-area
representativeness claim; maintain the released assurance and reproduction
gates in parallel\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose And Boundaries

Maintain an auditable assurance case for SynthPopCan's numerical results,
generated distributions, linked records, and emitted artifacts. The released
baseline is summarized in [CORRECTNESS.md](../CORRECTNESS.md); completed
`0.5.1` implementation history belongs in the changelog rather than this active
plan.

The assurance case combines independent reference calculations, mathematical
and structural invariants, differential and metamorphic tests, statistical
acceptance tests, and artifact read-back reconciliation. Production report
builders must not be the sole validators of production output.

Passing the project gate establishes behavior only under the tested conditions.
It does not certify source-data accuracy, statistical fitness for a particular
study, disclosure safety, causal validity, or substantive interpretation.

## Released In `0.6.3`: Exact Reproduction And Durable Evidence

`0.6.3` is a maintenance release. It must not change the linked-population v1
contract.

Implementation is complete and passes the local full release gate.
Reproduction recipes now support tested ordered command sequences; terminal durable runs embed
`synthpopcan-assurance-v1`; and the release workflow builds, attests, checksums,
retains, and attaches evidence to the matching GitHub Release. The assurance
schema is additive within `run.json`: readers must ignore unknown fields.
A future incompatible assurance change requires a new schema identifier and an
explicit migration reader; existing evidence is never rewritten in place.

### 1. Reproduction and adapter parity

IPF and prepared-model durable runs have executable CLI checks. Small-area
recipes now preserve model conditions and optional map creation, and parity
tests execute both generated and uploaded-candidate forms.

Implement an executable reproduction recipe that can contain an ordered command
sequence when one command cannot recreate every artifact. The recipe must:

- preserve the normalized workflow request and every result-affecting option;
- represent catalogue models and uploaded model packages without substituting an
  unverified input;
- include model conditions, random and subsampling seeds, household-size
  grouping, person controls, fitted-weight output, geography fields, and optional
  map creation;
- use managed relative input references or documented user-supplied replacements
  rather than workspace-internal opaque upload IDs; and
- remain shell-safe while retaining a structured, machine-readable form.

Consolidate model and small-area orchestration where practical. Where two
adapters still call shared domain functions separately, require explicit parity
tests so defaults and option translation cannot drift silently.

Acceptance:

- execute generated IPF, prepared-model, small-area calibration, and small-area
  generation recipes against public fixtures;
- compare fixed-seed rows, identifiers, reports, validation summaries, and
  requested optional artifacts, excluding only documented path or timestamp
  fields;
- cover catalogue and uploaded packages plus generated and uploaded linked
  candidates;
- fail a test when a result-affecting request field is not represented; and
- remove the documented small-area reproduction limitation only after these
  tests pass.

### 2. Versioned per-run assurance

Extend the existing workflow reports and durable `run.json` record rather than
creating a parallel provenance system. Define one versioned assurance object
whose fields have a single documented owner and can be embedded in or referenced
by those existing records.

The assurance object must cover, where applicable:

- SynthPopCan and assurance-schema versions;
- normalized request, model identity and checksum, random seeds, and settings;
- input and artifact SHA-256 digests, media types, byte sizes, and row counts;
- convergence, iteration count, tolerances, and fitted and realized residuals;
- unsupported or structurally impossible cells and deliberate support repairs;
- linked household/person integrity findings;
- validation status, warnings, and explicit limitations; and
- terminal run state without presenting failed, cancelled, or interrupted work
  as successful output.

Acceptance:

- validate complete, failed, cancelled, and interrupted fixture records against
  the versioned contract;
- independently recompute a representative subset of digests, row counts,
  residuals, and linkage findings from emitted artifacts;
- reject or clearly report missing required evidence and tampered artifacts;
- keep restricted inputs and raw training records out of the assurance payload;
  and
- document additive compatibility and the migration rule for any future schema
  version.

### 3. Permanent release evidence

Actions artifacts are useful commit evidence but are not a permanent archive.
For every release, preserve:

- the tested tag and commit;
- distribution and evidence-file checksums;
- correctness and coverage reports;
- dependency/build provenance and available attestations;
- installed-wheel smoke results; and
- a concise statement of tests run, known limitations, and any waived checks.

Acceptance:

- a release workflow verifies that evidence names the exact tag commit and built
  distributions;
- evidence remains downloadable from the GitHub Release, Zenodo record, or
  another documented permanent record after Actions retention expires; and
- a clean verifier can match the published distributions and evidence manifest
  by checksum.

## Evidence Hardening After `0.6.3`

### Generated and mutation evidence

- Add Hypothesis strategies that construct feasible IPF tables, record
  permutations, category renamings, target scaling, and finite weight vectors
  directly, with deterministic CI profiles and useful shrinking.
- Add targeted mutation testing for IPF, integerization, calibration, model
  traversal, artifact reconciliation, and report construction.
- Record a reviewed baseline and triage every surviving mutation; do not adopt an
  arbitrary project-wide mutation percentage.

Acceptance: minimized failures are reproducible from recorded seeds, the normal
profile remains suitable for pull requests, a larger profile runs on schedule,
and surviving critical-kernel mutations are fixed or explicitly justified.

### Cross-version and platform evidence

- Freeze semantic fixtures for stable public contracts, including
  multi-dimensional IPF, linked household/person generation, and small-area
  realization. Avoid snapshots of harmless formatting or timestamps.
- Declare the supported operating-system policy before promising compatibility.
  Add macOS and Windows wheel-install, filesystem, CLI, and spawned-job smoke
  checks, then expand only where failures justify a larger matrix.

Acceptance: the current release reads supported older artifacts or emits a
documented migration error, and each declared platform runs the named installed
workflows without relying on a source checkout.

### Full-field ADA/DA control coverage

This plan owns the follow-on work transferred from the completed small-area
geography implementation. Current national plans control household size and
tenure. Other linked household and person fields remain candidate-pool
attributes unless a compatible local margin is explicitly fitted.

Before presenting another field as ADA- or DA-local, audit every linked-schema
field against the 2021 Census Profile at both levels. Record the Profile
characteristic and universe, exact or coarsened category crosswalk,
suppression/availability conditions, geography and source revision, and an
explicit `unavailable` or `uncontrolled` result where no defensible margin
exists.

Use the audit to prioritize suitably supported household and person margins.
Linked person controls may change whole-household weights but must never detach
people from their households. Each fitted field needs coverage, residual,
support/structural-zero, suppression, and reconciliation evidence, plus updated
documentation and claims-to-evidence records.

This work runs in parallel with the `0.7.1` Can-FED and `0.7.2` ODEF sidecar
adapters because those releases do not claim to recalibrate base population
attributes. It blocks only new small-area representativeness claims and any
release that explicitly includes expanded ADA/DA controls.

Acceptance: every linked-schema field has an auditable classification; every
implemented crosswalk has independent fixtures; household-only runs remain
reproducible; and documentation distinguishes fitted local margins from
uncontrolled carried-through fields.

The initial source-availability screen now covers both census vintages and all
four supported calibration levels; see the
[small-area control coverage inventory](../docs/small-area-control-coverage.md).
It identifies 29 count-based candidate fields, two lower-confidence
percentage-derived candidates, and five fields without matching Profile count
distributions. Those candidates are not implemented controls until their
category crosswalks and statistical evidence meet the acceptance criteria
above.

### Multi-margin control packs

The dedicated
[expanded small-area controls plan](2026-08-01-expanded-small-area-controls.md)
owns the field/control registry, source screening, universe reconciliation,
versioned packs, feasibility planner, family-aware contributions, interfaces,
and implementation sequence. This assurance plan retains the cross-cutting
requirements for independent fixtures, structural-zero policy, residual and
aggregation evidence, reproducibility, privacy review, and restrained claims.

Expanded controls must remain low-dimensional reviewed margins fitted against
whole-household weights. Do not describe a field as locally controlled merely
because it exists in a generated hierarchical population or appears in a
source-availability inventory.

## Statistical And Model Quality

### Zero-cell and support policy

Define a policy that distinguishes structural zeros, sampling zeros, suppressed
values, missing categories, and genuine absence. Never repair support silently.

Acceptance: every repair or category coarsening is represented in provenance;
blocking and repairable cases have independent fixtures; reports distinguish
fitted feasibility from realized integer output.

### Multi-scale and rare-category validation

Validate emitted populations at target geography and, where authoritative
relationships exist, at CSD/CMA, province or territory, and national scales.
Report error distributions and rare-category behavior rather than only a single
maximum residual. The archived
[small-area geography plan](archive/2026-07-22-small-area-geography.md) records
the released relationship indexing and representative DA workflows.

Acceptance: aggregation uses version- and namespace-matched relationships,
reconciles independently from output rows, and reports unmatched geographies,
suppression, denominators, and tail errors.

### Integerization alternatives

Compare deterministic systematic integerization with QISI on public fixtures
before adding another production backend. Measure residuals, reproducibility,
runtime, memory, and sparse-candidate behavior.

Acceptance: publish the benchmark method and decision; retain the current
backend unless another method provides a material, reviewed benefit without
weakening determinism or traceability.

### Prepared-model assurance

- Derive raw-row and likely source-identifier findings from serialized model
  contents rather than trusting declarations alone. Treat detection as evidence,
  not proof of absence.
- Audit linked household and person models jointly for rare cross-level
  combinations and align thresholds with category-coarsening guidance.
- Define full, reduced, and minimal profile guidance by geography, sample
  support, size, model quality, and disclosure risk.
- Treat territory and broader-CMA packages as feasibility candidates. Publish
  only packages that pass support, rare-category, privacy, provenance,
  reproducible-build, checksum, generation, and archival gates.

Automated privacy findings remain subordinate to documented human review.

### External comparison and review

- Add an opt-in comparison with a small, checksum-pinned, schema-crosswalked
  slice of the Prédhumeau–Manley national Canadian synthetic population. Treat
  it as a comparison artifact, not observed truth.
- Invite an external methods/code review and publish its scope, findings,
  limitations, and project responses.

Acceptance: external data is not downloaded by the default test gate, source
version and licence are recorded, comparison metrics and denominators are
explicit, and review findings remain publicly traceable.

## Execution Tiers

- **Pull request and push:** deterministic unit, invariant, differential,
  reference, artifact-reconciliation, architecture, documentation, browser
  integration, and installed-wheel smoke checks on supported Python versions.
- **Scheduled:** larger generated and multi-seed suites plus live Statistics
  Canada interface-drift checks.
- **Release:** the complete extended suite against the release tag, exact
  reproduction fixtures, installed distributions, and permanent evidence
  publication.

Default tests must remain public and deterministic. Live external-service,
large-data, restricted-data, performance, and external-comparison checks remain
opt-in unless a bounded public fixture replaces them.
