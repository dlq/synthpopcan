# ADR-0016: Keep Evidence And Claim Classes Separate

- **Status:** Accepted
- **Date:** 2026-08-20
- **Decision owners:** Maintainers

## Context

Synthetic-population workflows combine several questions that are related but
not interchangeable. Code can reproduce an algorithm correctly while the
inputs are statistically unsuitable. A calibration can converge while
uncontrolled attributes remain locally inaccurate. An artifact can reproduce
exactly while being sensitive to another random seed. A privacy metric can
identify one risk without establishing legal disclosure safety. An open licence
can permit reuse without granting access to confidential source data or proving
that publication is responsible.

SynthPopCan already states these limits throughout its correctness evidence,
model audits, calibration reports, exchange bundles, documentation, and release
process. Without an explicit architecture decision, a future feature could
collapse them into one pass/fail status or use evidence from one class to imply
a stronger claim in another.

## Decision

SynthPopCan records and communicates the following evidence and claim classes
separately:

1. **Computational correctness:** the implementation performs its declared
   operation and preserves tested invariants.
1. **Numerical feasibility and convergence:** the represented constraints have
   support, the numerical method reaches its declared criterion, and fractional
   and realized results are distinguished.
1. **Statistical utility and fitness:** generated data preserve reviewed
   distributions or relationships sufficiently for a named use and population
   universe.
1. **Uncertainty and stability:** results are sensitive or robust to explicitly
   varied sources such as training samples, replicate weights, model fitting,
   candidate generation, calibration, integerization, and random realization.
1. **Disclosure-risk evidence:** model or artifact checks evaluate named attack,
   support, purity, uniqueness, leakage, or distance risks within a declared
   scope.
1. **Substantive research validity:** the population and method are appropriate
   for the domain question and support the interpretation made by the
   researcher.
1. **Licensing, access, and redistribution authority:** the relevant rights and
   conditions permit the proposed access, use, publication, or handoff.

Schemas, reports, user interfaces, documentation, and release evidence must
name the class of finding they contain when confusion is plausible. A passing
finding in one class must not silently satisfy, suppress, or be presented as a
finding in another. In particular:

- test passage or reproducibility does not establish statistical fitness;
- convergence or low controlled residuals do not establish local
  representativeness;
- integer realization does not erase fractional or realized residuals;
- one fixed-seed result does not establish stability;
- model support, purity, anonymization, or a privacy metric does not certify
  anonymity or legal disclosure safety;
- licensing metadata does not establish privacy, accuracy, endorsement, or
  substantive validity; and
- a valid population exchange bundle is not a runnable simulation or proof of
  compatibility with an unnamed consumer.

Combined summaries may present several classes together, but they must preserve
their individual findings, scopes, limitations, and evidence references. A
feature may omit a class that is genuinely outside its scope; it must not imply
that the omitted question passed.

## Alternatives Considered

- **Use one overall quality or readiness score:** rejected because aggregation
  hides materially different failure modes and encourages unsupported claims.
- **Treat correctness tests as sufficient release evidence:** rejected because
  correct software can produce statistically unsuitable or disclosure-sensitive
  artifacts from unsuitable inputs.
- **Treat calibration fit as representativeness:** rejected because controlled
  margins do not validate uncontrolled fields, linked compositions, geography,
  or the research interpretation.
- **Treat privacy and licensing as one publication gate:** rejected because
  permission to reuse, empirical disclosure risk, ethical authority, and legal
  determinations are distinct questions.
- **Leave the distinctions only in prose caveats:** rejected because persisted
  evidence, interfaces, and future workflows also need to preserve the
  boundaries.

## Consequences

- Reports may be more verbose, but their conclusions and limitations remain
  auditable.
- Release and model-review workflows must identify which claims their evidence
  supports and which remain outside scope.
- New aggregate scores or readiness labels require mappings back to the
  underlying evidence classes and cannot erase a failed or missing class.
- Tests should protect claim language and schema separation where accidental
  overstatement would create material research, privacy, or governance risk.
- Users retain responsibility for substantive validity, ethics, permissions,
  and artifact-specific disclosure decisions that the software cannot certify.
- The taxonomy can be extended through a later ADR, but existing classes must
  not be silently redefined.

## Evidence And Related Records

- [Correctness claims and evidence](../CORRECTNESS.md)
- [Correctness assurance plan](../plans/2026-07-12-correctness-assurance.md)
- [Methodological validation and uncertainty plan](../plans/2026-08-02-methodological-validation-and-uncertainty.md)
- [CART methodology review](../plans/2026-08-20-cart-methodology-review.md)
- [Prepared-model and source licensing](0014-separate-prepared-model-and-source-licensing.md)
- [Simulator-neutral population exchange](0011-simulator-neutral-population-exchange.md)
- [Release process](../RELEASING.md)
- [`src/synthpopcan/assurance.py`](../src/synthpopcan/assurance.py)
