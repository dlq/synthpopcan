# CART Methodology Review

Status: conditional research\
Last updated: 2026-08-20\
Target: held-out validation and multiple realizations before any tree-method change\
Current next action: build one reproducible held-out scorecard for a reviewed
profile

## Purpose And Boundary

Retain CART and conditional-frequency generation as SynthPopCan's production
model families while strengthening how tree models are trained, selected,
composed, and evaluated. The tree representation remains a deliberate product
and research advantage: a reviewer can inspect its splits, paths, leaf support,
outcome probabilities, and generation decisions in a portable JSON artifact.

This plan does not commit the project to Gaussian copulas, neural generators,
SDV, or another runtime model dependency. Alternative generators may be used
in isolated benchmarks only when a demonstrated CART limitation justifies the
comparison. They do not replace linked-population validation, Census controls,
small-area calibration, provenance, or disclosure review.

The immediate work is intentionally limited to two questions:

1. Do fitted CART models reproduce important distributions and linked
   household relationships in records that were not used for fitting?
1. How sensitive are generated and calibrated results to declared sources of
   randomness?

Complete those before expanding the implementation scope below.

## Phase 1 — Held-Out Model Selection

Add a reproducible train/validation split for one bounded, reviewed model
profile. Compare candidate tree settings with a scorecard rather than choosing
on training fit or one accuracy value.

The scorecard should include:

- held-out marginal distributions for generated fields;
- a short reviewed list of substantively important joint distributions;
- linked household-composition signatures;
- rare-category recall, false generation, and tail error;
- candidate diversity and duplicate or reuse concentration;
- downstream small-area feasibility, residuals, and fitted-weight
  concentration; and
- existing leaf support, purity, provenance, and disclosure warnings.

Model selection must not optimize every possible cross-tabulation. The reviewed
relationship list should be small, domain-motivated, versioned, and appropriate
to the model profile. A predictive improvement does not justify a model that
creates support holes, extreme calibration weights, unstable rare categories,
or materially worse disclosure findings.

Acceptance:

- fixed split specifications reproduce the same partitions and scorecard;
- no held-out record contributes to fitting the model being evaluated;
- the report distinguishes predictive fidelity, linked validity, calibration
  behavior, and disclosure warnings;
- at least one existing model profile is evaluated without changing its public
  package bytes or the frozen `1.x` interface; and
- the result records whether current defaults are retained or a separately
  reviewed future profile should use different tree settings.

## Phase 2 — Multiple Realizations

Build the first bounded ensemble around the retained model. Generate multiple
members under one versioned specification while varying only declared sources
of randomness. Keep these components distinguishable where applicable:

- source sampling or survey replicate weights;
- CART fitting randomness;
- candidate-pool generation;
- calibration subsampling;
- integerization; and
- final random realization.

Summarize stability for controlled totals, important untargeted relationships,
rare categories, linked household signatures, calibration weights, candidate
reuse, and geography aggregates. Failed or infeasible members remain visible.

The ensemble is a sensitivity analysis unless a separately justified method
supports a stronger interpretation. Do not label its spread as a confidence
interval merely because multiple populations were generated.

Acceptance:

- fixed ensemble specifications reproduce member artifacts and summaries;
- reports identify which randomness component changed for each member;
- stable and unstable quantities can be distinguished;
- generation, calibration, and integerization variation are not collapsed into
  one unexplained range; and
- one bounded example documents the operational meaning and limitations of the
  ensemble.

Phase 2 shares its ensemble contract and statistical-claims boundary with the
[methodological validation and uncertainty plan](2026-08-02-methodological-validation-and-uncertainty.md).
This plan owns the CART-specific model-selection and interpretation questions;
the broader plan owns reusable uncertainty and disclosure methodology.

## Deferred CART Extensions

Do not begin these merely because they are listed. Promote one into active work
only when held-out or ensemble evidence reveals a concrete need.

### Explicit field order and chained blocks

Treat generation order as part of the model specification. If richer profiles
need it, define coherent, versioned blocks with explicit dependencies, for
example household structure, housing, person demographics, education, labour,
and income. Evaluate support and fitness per block. Avoid an unrestricted
dependency graph or one monolithic tree.

The expanded hierarchical-tree plan owns the package contract for chained
blocks. This plan supplies the evidence required to decide whether a chain is
methodologically preferable.

### Structural, universe, and derivation rules

Distinguish:

- deterministic fields that should be calculated rather than generated;
- structural-zero combinations that must never be emitted;
- fields that apply only within a declared population universe; and
- unusual but permitted combinations that should be reported rather than
  silently removed.

Linked invariants such as household size and person count should hold by
construction. If a rule layer is needed, keep it declarative, versioned,
portable, and separately testable from tree fitting.

### End-to-end rare-category review

Extend leaf support and purity evidence only when necessary to assess complete
linked signatures. Review whether a rare category is reproduced in supported
contexts, whether calibration repeatedly selects the same candidate, and
whether coarsening improves the utility-risk balance. Acceptable support in
each individual leaf does not by itself prove that a full household signature
is sufficiently supported.

### Conditional numeric fields

For a justified numeric field, prefer an interpretable local extension:

```text
CART path -> supported leaf -> explicit bounded numeric distribution
```

Record support, bounds, quantiles, distribution choice, rounding, and tail
policy. Fall back to a parent group or published band when local support is
inadequate. Do not introduce a dense global dependence model merely to add one
numeric field.

### Whole-household validation

If field-level held-out metrics miss material problems, add a short reviewed
set of linked signatures such as household size by age composition, tenure by
dwelling and household size, or age by education and labour status. Avoid an
exhaustive quadratic catalogue of pairwise relationships.

### Empirical disclosure attacks

Before publishing substantially richer profiles, extend current support,
purity, uniqueness, and source-row leakage screening with attack-oriented
evidence appropriate to the release class. An empirical result is evidence,
not a legal disclosure-safety certification.

## Sequencing

1. Implement and review one held-out CART scorecard.
1. Retain or revise model settings based on that evidence.
1. Implement one bounded multiple-realization study.
1. Stop and reassess.
1. Activate at most one deferred extension when the first two phases identify
   a concrete deficiency that it addresses.

Completion does not require every deferred extension. The immediate plan is
complete when the held-out and multiple-realization evidence is reproducible,
documented, and sufficient to decide whether the current CART methodology
should remain unchanged.
