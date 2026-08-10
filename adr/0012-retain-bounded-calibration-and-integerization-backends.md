# ADR-0012: Retain the Bounded Calibration and Integerization Backends

- **Status:** Accepted
- **Date:** 2026-08-10
- **Decision owners:** Maintainers

## Context

SynthPopCan fits linked household and person controls with non-negative
household weights, then realizes those fractional weights as whole-household
copies. The production calibration updater and deterministic systematic
integerizer are transparent and dependency-light, but until `0.9.0` they did
not have a solver-independent bounded oracle or a reproducible comparison with
another integerization rule.

Changing either backend would affect household selection, realized residuals,
candidate reuse, reproducibility, and every surface that reports or reproduces
small-area results. A backend change therefore needs evidence of a material
benefit rather than a preference for a more elaborate solver.

## Decision

Retain the existing `linked-multiplicative-updater-v1` production
linked-calibration updater and the
`deterministic-systematic-midpoint-v1` integerizer for the bounded
private-household workflow.

Add two evidence-only independent implementations:

- `bounded-relative-entropy-dual-newton-v1` independently classifies and solves
  generated feasible calibration cases with no more than 14 households and 20
  constraints; and
- `deterministic-largest-remainder-v1` provides a second deterministic
  integerization result on the same fitted weights.

The oracle and comparator are methodological evidence, not selectable
production backends. They must remain independently formulated, run from
generated or public-safe fixtures, and emit a versioned reproducible evidence
artifact. Production reports continue to retain both fractional and realized
residuals. Production preflight rejects directly unsupported positive targets
and support removed by structural zeros; the independent evidence layer also
classifies bounded general infeasibility. A conflicting dependent-constraint
case may still appear as an iteration limit in production and must not be
presented as proof that the problem was feasible.

A later backend may replace or supplement the retained methods only after a
reviewed comparison demonstrates a material improvement for a supported use
case. The comparison must use the same control pack, population universe,
candidate pool, targets, and seeds, and must report dependency, failure,
runtime, memory, traceability, and household/person consistency costs.

## Alternatives Considered

- **Adopt the bounded relative-entropy oracle in production:** rejected because
  its exhaustive feasibility classification is deliberately size-bounded and
  exists to provide independent evidence, not a general runtime path.
- **Replace systematic realization with largest remainder:** rejected because
  the bounded comparison did not establish a material overall improvement
  sufficient to justify changing established deterministic selections.
- **Add a mixed-integer solver dependency:** deferred because the current
  tranche does not establish a production benefit that outweighs dependency,
  platform, runtime, and failure-semantics costs.
- **Treat convergence or an iteration limit as a complete feasibility test:**
  rejected because direct support failures, bounded general infeasibility, and
  numerical non-convergence are different findings. The present production
  path detects the first and the evidence oracle distinguishes the latter two
  only within its declared bounds.

## Consequences

- Existing fixed-seed workflows keep their deterministic realization rule.
- Maintainers gain an independent bounded check without shipping a new solver
  dependency or exposing an unstable backend selector before `1.0.0`.
- The bounded oracle is evidence for declared cases, not proof for arbitrary
  production inputs or statistical fitness.
- Users must still review realized residuals, rare categories, structural
  zeros, candidate reuse, and weight concentration even when the fractional
  fit converges.
- Future hierarchy-aware or exact controlled-rounding work remains possible
  through a new versioned backend and decision record.

## Evidence And Related Records

- [Methodological validation and uncertainty plan](../plans/2026-08-02-methodological-validation-and-uncertainty.md)
- [Correctness assurance plan](../plans/2026-07-12-correctness-assurance.md)
- [Correctness claims and evidence](../CORRECTNESS.md)
- `docs/_static/methodology-evidence-v1.json`
- `scripts/build_methodology_evidence.py`
