# Methodological Validation And Uncertainty Plan

Status: planned cross-cutting assurance track\
Created: 2026-08-02\
Last updated: 2026-08-02\
Target: bounded oracle, integerization, validation, and Canadian comparison for
`0.9.0`; deeper ensembles and attack infrastructure after `1.0.0`\
Next action: add generated feasible linked-calibration cases and an independent
solver-backed oracle for bounded fixtures, then publish the first convergence
and residual comparison\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Outcome

Move SynthPopCan from a well-tested transparent implementation to an externally
benchmarked statistical system whose calibration limits, integer realization,
uncertainty, utility, and disclosure evidence are measured independently.

This track should let a researcher answer five different questions without
conflating them:

1. Did the software implement the selected algorithm correctly?
1. Did the fractional calibration problem have a feasible, stable solution?
1. How much did integer realization change the fitted controls?
1. How sensitive is the population to sample weights, controls, model choices,
   candidate pools, and random seeds?
1. What statistical utility and disclosure-risk evidence supports the intended
   use or release decision?

The plan owns shared methodological test infrastructure, algorithm comparisons,
uncertainty evidence, external benchmarks, and attack-oriented disclosure
evaluation. It does not own source-specific control crosswalks, the set of
fields a tree profile generates, or the substantive interpretation of a
particular research study.

Related ownership:

- [Correctness assurance](2026-07-12-correctness-assurance.md) owns the released
  claims-to-evidence baseline, routine gates, reproduction, and permanent
  evidence.
- [Expanded small-area controls](2026-08-01-expanded-small-area-controls.md)
  owns control packs, universes, feasibility planning, and whole-household
  calibration interfaces.
- [Expanded hierarchical tree models](2026-08-01-expanded-hierarchical-tree-models.md)
  owns model fields, model structure, family hierarchy, and profile-specific
  release decisions.

## Review Baseline

The 2026-08-02 software and literature review found that SynthPopCan is already
strong on source provenance, Census-vintage identity, linked artifacts,
fractional-versus-realized reporting, deterministic reproduction, interface
parity, and independent artifact reconciliation.

The principal comparison gaps are:

- the linked household/person fitter is a custom multiplicative IPU-style
  updater without an independent optimization oracle;
- deterministic systematic integerization preserves the rounded total but does
  not guarantee every selected margin;
- reports describe one fitted and realized result more fully than uncertainty
  across defensible inputs and realizations;
- validation is strongest for selected controls and structural integrity, with
  less shared infrastructure for held-out multivariate utility, household
  relationships, and empirical disclosure attacks; and
- the planned comparison with the Prédhumeau-Manley Canadian population has not
  yet produced a pinned external benchmark artifact.

The review's focused local evidence retained the released result: 102 IPF,
small-area, and model-correctness tests passed. A generated probe of 300
realistic categorical household/person calibration cases converged within the
tested tolerance. A broader set of feasible arbitrary contribution matrices
also exposed slower or incomplete convergence in some cases. That probe is a
reason to add an oracle and declared applicability domain, not evidence that a
released control pack is wrong.

Relevant external references include:

- PopulationSim's multi-geography relative-entropy balancing, bounds,
  constraint importance, and simultaneous integerization:
  <https://activitysim.github.io/populationsim/>;
- the Prédhumeau-Manley national Canadian population and QISI workflow:
  <https://doi.org/10.1038/s41597-023-02030-4>;
- the 2025 problem-based population-synthesis review:
  <https://doi.org/10.1080/01441647.2025.2469069>;
- one-step Gibbs household generation:
  <https://doi.org/10.1016/j.trc.2024.104770>;
- SynthEval's multi-axis utility and privacy metrics:
  <https://arxiv.org/abs/2404.15821>;
- Statistics Canada's work on fully synthetic complex-survey data and multiple
  releases: <https://www150.statcan.gc.ca/n1/pub/12-001-x/2024002/article/00008-eng.htm>;
  and
- Statistics Canada's 2024-2025 synthetic-data disclosure-risk work:
  <https://www150.statcan.gc.ca/n1/pub/12-206-x/2025001/04-eng.htm>.

## Principles And Boundaries

- Keep production behavior unchanged until an alternative has reproducible
  evidence of a material benefit.
- Use independent formulations and read-back calculations; production report
  builders must not validate themselves.
- Separate fractional feasibility, numerical convergence, integer realization,
  statistical fitness, and disclosure risk.
- Compare methods on the same pinned public fixtures, controls, tolerances,
  seeds, and hardware context.
- Report a vector of interpretable metrics rather than one synthetic-population
  quality score.
- Never perturb, repair, relax, or drop a control without recording the exact
  policy and its effect.
- Treat published Census cells as disseminated estimates subject to their
  documented rounding, suppression, sampling, and quality conditions, not as
  confidential exact truth.
- Use optional development dependencies for solver and attack benchmarks unless
  evidence justifies a production dependency.
- A formal privacy mechanism or empirical attack result does not replace
  purpose-, source-, licence-, ethics-, and human-release review.

## Pre-`1.0` Cut Line

Only a bounded subset of this plan is a `0.9.0`/`1.0.0` gate:

- Phase 1's generated feasible linked-calibration cases, independent oracle,
  and declared applicability for the production updater;
- Phase 2's integerization comparison and published backend decision;
- the Phase 4 metrics needed for controlled residuals, structural zeros, rare
  categories, weight concentration, candidate reuse, household linkage, and
  parent-geography reconciliation; and
- one bounded Phase 5 comparison with the Prédhumeau-Manley Canadian artifact
  or an equivalently pinned public slice.

Full ensemble infrastructure in Phase 3, the broader metric catalogue in Phase
4, general software comparisons in Phase 5, and the comprehensive empirical
attack framework in Phase 6 are post-`1.0` work unless a specific public model
release needs one earlier. Before `1.0.0`, existing public models still require
their current support, purity, raw-content, rare-signature, provenance, and
human-review gates; this cut line does not weaken them.

Phase 7 contributes only the interfaces and durable evidence needed by the
bounded pre-`1.0` tranche. The frozen CLI/API should expose versioned extension
points rather than a separate public switch for every future solver, metric,
perturbation, or attack.

## Phase 1 — Calibration Oracles And Applicability

Build generated feasible linked-calibration fixtures whose targets come from
known non-negative household weights. Include:

- ordinary household indicator rows;
- linked-person count contributions greater than one;
- sparse and rare categories;
- redundant, linearly dependent, and nearly conflicting constraints;
- zero targets and deliberately unsupported positive targets;
- non-uniform initial survey or candidate weights; and
- bounded small cases with an analytically known answer.

Implement at least one independent solver-backed oracle for small and moderate
fixtures. Prefer a convex relative-entropy or generalized-raking formulation
that minimizes departure from initial weights subject to the contribution
matrix and target totals. Add a brute-force or mixed-integer oracle only for
tiny integer fixtures where it improves independence.

Compare the released multiplicative updater with the oracle on:

- feasibility classification;
- convergence and iteration counts;
- absolute and relative residuals;
- distance from initial weights;
- minimum, maximum, concentration, and effective sample size of weights;
- redundant-constraint handling; and
- deterministic behavior, runtime, and memory.

Define an applicability statement for the production updater. If it remains the
default, document the contribution structures for which evidence is strong and
the diagnostics that require review. If a solver becomes an optional or default
backend, define hard constraints, soft constraints, importance, slack, bounds,
failure semantics, and dependency cost explicitly.

Acceptance: analytical cases, the production updater, and the independent
oracle agree within declared tolerances on supported feasible fixtures;
infeasible cases are not presented as numerical non-convergence; generated
failures shrink to reproducible examples; and backend selection never changes
the represented universe or control pack silently.

## Phase 2 — Integerization And Controlled Realization

Benchmark the released deterministic systematic integerizer against reviewed
alternatives:

- QISI/QIWS;
- simultaneous linear or mixed-integer optimization similar in purpose to
  PopulationSim's integerizer;
- controlled rounding or minimum-error allocation; and
- information-theoretic floor/ceiling integerization after its assumptions and
  publication status are reviewed.

Measure:

- preservation of total households and people;
- per-cell and per-margin realized residuals;
- simultaneous household/person and parent-geography consistency;
- rare-category retention and structural-zero preservation;
- candidate reuse, maximum expansion, and diversity;
- reproducibility or distribution across repeated realizations;
- runtime, peak memory, and solver failure behavior; and
- traceability from realized rows to candidate households and people.

Support a hierarchy-aware test in which child-geography realizations reconcile
to authoritative parent controls. Do not imply that independently integerized
geographies are jointly optimal when they are not.

Acceptance: publish a reproducible comparison and backend decision; preserve
the current method unless another method supplies a material reviewed benefit;
and always retain fractional and realized reports even when an optimizer meets
every selected margin.

## Phase 3 — Uncertainty And Multiple Realizations

Represent at least four uncertainty sources separately:

1. **Source/sample:** PUMF sampling and source weights, evaluated where possible
   with supplied replicate weights or documented resampling.
1. **Control:** random rounding, suppression, sampling, category reconciliation,
   and other published quality conditions.
1. **Model/candidate:** training choices, candidate-pool construction,
   subsampling, fallback, and transferred geography support.
1. **Realization:** stochastic model generation and integer selection.

Add an ensemble request and report contract that can vary only declared
dimensions. It should record every seed, replicate-weight view, control
perturbation policy, model/package identity, and failed member. Summaries should
include intervals or quantiles for selected margins, uncontrolled validation
statistics, rare categories, household signatures, and geography aggregates.

Using PUMF replicate weights for evaluation does not mean generating them as
synthetic attributes. Control perturbations must follow documented dissemination
mechanisms or an explicitly labelled sensitivity scenario; arbitrary noise must
not be presented as statistical uncertainty.

Acceptance: fixed ensemble specifications reproduce member artifacts and
summaries; components of uncertainty remain distinguishable; failed members are
visible; a user can see whether a substantive conclusion changes across
defensible realizations; and documentation does not convert sensitivity ranges
into formal confidence intervals without a supporting method.

## Phase 4 — Multi-Axis Statistical Validation

Create a shared validation profile with separate axes for:

- controlled marginal and joint residuals;
- held-out one-, two-, and selected higher-order distributions;
- mixed-type association and mutual-information differences;
- missing, not-applicable, suppressed, and unavailable-state behavior;
- household, family, and inter-member relationship signatures;
- structural-zero violations and sampling-zero recovery;
- rare-category recall, precision, and tail errors;
- diversity, candidate reuse, effective sample size, and weight concentration;
- multi-seed and ensemble stability; and
- target- and parent-geography reconciliation.

Each metric must name its input unit, denominator, population universe,
weighting, direction, and important failure mode. Profiles may select metrics
appropriate to a use case, but no single score may hide a material failure on
another axis.

Acceptance: validation recomputes from emitted artifacts or pinned held-out
data; controlled and uncontrolled fields are labelled separately; linked
household metrics cannot be reduced to independent person rows; and reports
remain readable to a researcher who does not know the implementation.

## Phase 5 — External Canadian And Software Benchmarks

Create an opt-in, checksum-pinned, licence-recorded crosswalk to a bounded slice
of the Prédhumeau-Manley Canadian population. Compare schemas, represented
universes, DA and parent-geography distributions, household composition, rare
categories, unassigned or excluded populations, storage, and runtime. Treat
both outputs as modelled artifacts rather than observed truth.

Add small, reproducible algorithm comparisons with PopulationSim or an
independently equivalent formulation where licences and dependency costs allow.
The goal is not feature parity; it is to identify differences in calibration,
integerization, geographic hierarchy, expansion bounds, diagnostics, and
configuration semantics.

Acceptance: external downloads are opt-in and cached outside git; versions,
licences, checksums, crosswalk losses, metrics, and denominators are explicit;
no benchmark is selected only because it favors SynthPopCan; and published
claims name the exact slice and method tested.

## Phase 6 — Disclosure-Risk Evaluation

Extend support and purity screening with empirical tests appropriate to the
artifact and intended release class:

- exact and near source-row reproduction;
- nearest-neighbour and distance-to-closest-record comparisons;
- rare linked-household and family signatures;
- membership-inference and attribute-inference probes with simple baselines;
- model-content inspection for rows, identifiers, donor lists, bootstrap
  indices, encoders, and small leaves/groups; and
- comparison of utility and risk across model profiles, coarsening, support
  thresholds, and release classes.

Define the attacker's assumed knowledge and access for every test. Avoid
claiming anonymity from a failed attack or treating a successful attack metric
as a legal disclosure determination.

Acceptance: public model candidates have a versioned risk report, baseline
comparison, intended-use statement, source and licence review, known
limitations, and recorded human decision; sensitive or restricted-source
models fail closed when required evidence or authority is absent.

## Phase 7 — Interfaces, Evidence, And Publication

Expose ordinary results through shared library, CLI, and local-web workflows;
keep expensive solvers, ensembles, external downloads, and attacks opt-in.
Every methodological run should emit:

- normalized request and method identities;
- exact inputs, versions, hashes, seeds, and perturbation policies;
- per-member or per-backend status;
- machine-readable metrics and readable interpretation;
- environment and resource measurements where relevant;
- limitations and claims supported or not supported; and
- a reproduction recipe.

Add bounded pull-request fixtures, larger scheduled profiles, and release or
publication profiles. Preserve permanent evidence for any backend adoption,
national-quality claim, or public model release.

Acceptance: interfaces normalize equivalent requests identically; expensive
work has estimates, cancellation, and durable partial/failure records; reports
can be independently read and checked; and methodological evidence is archived
with the exact software and artifact version it supports.

## Sequencing And Completion

Work proceeds in this order:

1. generated feasible linked-calibration cases and an independent oracle;
1. declared applicability and convergence diagnostics for the current updater;
1. integerization benchmark and published backend decision;
1. weight concentration, effective sample size, and expanded validation;
1. bounded external Canadian and PopulationSim comparisons;
1. multiple-realization and uncertainty contracts;
1. empirical disclosure-risk evaluation; and
1. durable interface and publication evidence for adopted methods.

The track is complete when every production calibration and realization backend
has independent evidence and a declared applicability domain; fractional and
integer outcomes are distinguished; major uncertainty sources can be evaluated
without inventing precision; validation covers controls, held-out structure,
relationships, tails, and geography; external comparisons are reproducible;
public model decisions include empirical risk evidence and human review; and no
statistical or national-quality claim exceeds the exact evidence archived for
it.
