# Bounded Methodological Validation

The 0.9 validation profile keeps five questions separate from control
residuals. A calibration can reproduce every selected margin and still depend
on very few candidates, duplicate one candidate many times, lose a rare cell,
violate a declared structural zero, or leave most generated fields locally
uncontrolled.

`synthpopcan.methodological_validation` recomputes these diagnostics directly
from candidate rows plus fractional and integer weights. It does not read the
production fit report. This gives the correctness suite an independent
read-back path rather than asking a report builder to validate itself.

## Metric contract

The versioned `synthpopcan-validation-profile-v1` report includes:

- **Weight concentration:** total and positive weights, maximum and largest
  candidate share, Herfindahl concentration, and Kish effective sample size.
  The denominator is the total fractional household weight. High effective
  sample size is generally preferable, but it is not proof of a good fit.
- **Candidate reuse:** selected and unselected candidates, candidates copied
  more than once, additional copies, maximum expansion, copy-count histogram,
  and realized shares from unique and reused candidates. The report always
  says whether a denominator is candidate rows or realized rows.
- **Rare categories:** an explicit reference source and count define each
  category cell. The profile screens cells with positive reference counts no
  larger than the declared threshold and reports candidate support,
  fractional mass, realized count, retention, and tail error. An absent sample
  category is not silently reclassified as a structural zero.
- **Structural zeros:** every zero has a named source and exact category cell.
  Positive fractional or integer mass is an error. Candidate support may exist
  even when calibration correctly gives it zero weight.
- **Field declarations:** every reviewed field is classified as `controlled`,
  `approximate`, `validation-only`, `derived`, or `uncontrolled`. Only
  the intended tier is recorded. Every field remains `fit_evidence_status: not_assessed` in this standalone profile; no tier authorizes a local claim
  without independently verified source, universe, fit, and residual evidence.
  Disseminated Census estimates may also be rounded, suppressed, or otherwise
  unsuitable for an exact claim.

Warnings such as the loss of a supported rare category remain visible without
being confused with structural failure. Missing fitted fields and structural
zero violations fail the profile.

## Calibration oracle and integerization decision

The committed `_static/methodology-evidence-v1.json` artifact compares the
production `linked-multiplicative-updater-v1` with an independent bounded
`bounded-relative-entropy-dual-newton-v1` oracle. The oracle first exhaustively
classifies non-negative feasibility for tiny cases, then solves the relative-
entropy dual with NumPy. It is limited to 14 candidate households and 20
constraints, is not a production backend, and adds no runtime dependency.

The fixture set covers analytical, linked-person contributions greater than
one, sparse and rare, zero-target, non-uniform starting weight, redundant or
nearly dependent, and generated feasible cases, plus explicit infeasible and
unsupported-support cases. The comparison supports the retained updater in
that bounded domain. It does not prove that production preflight can classify
arbitrary infeasibility: one conflicting dependent case still reaches the
production iteration limit while the independent evidence layer classifies it
as infeasible.

The same artifact compares the production
`deterministic-systematic-midpoint-v1` integerizer with
`deterministic-largest-remainder-v1`. Both preserve the requested rounded
total in the tested cases; systematic midpoint has the better balanced-subunit
residual in the decision fixture and remains the backend. Neither guarantees
that every controlled cell survives integer realization, so reports retain
fractional and realized residuals separately.

Rebuild the artifact exactly with:

```bash
uv run python scripts/build_methodology_evidence.py \
  --out docs/_static/methodology-evidence-v1.json
```

[ADR-0012](https://github.com/dlq/synthpopcan/blob/main/adr/0012-retain-bounded-calibration-and-integerization-backends.md)
records the accepted decision and rejected alternatives.

## Bounded geography evidence

The committed multiscale fixture runs the real linked household/person fitter
at CSD, CT, ADA, and DA scales for the 2021 Census. Each scale has different
fictional targets. Person controls are computed from linked-person
contributions aggregated to candidate households before applying household
weights; person labels are never applied directly to household rows. The
independent profile then recomputes every target count from the emitted
fractional and integer weights.

Two bounded DA cases have additive fictional targets whose target, fitted, and
integerized cell totals reconcile to the bounded CSD case. Those two real DA
identities are only a tiny subset of the real Montréal CSD: this is an
additivity software test, not a claim that they exhaust the CSD. Each identity
carries its level, vintage, Statistics Canada namespace, short identifier,
DGUID, and correct resource column (`CSDUID`, `CTUID`, `ADAUID`, or `DAUID`).
All category values and targets remain project-authored.

The linked profile calls fields `targeted` or `uncontrolled`. Its independently
verified fractional residual status is reported by geography, separately from
the field tier and from any source-validity claim. A supplied zero is called a
declared zero-target constraint, not a structural impossibility unless separate
provenance establishes that stronger interpretation.

The official identifiers in the fixture are anchored to Statistics Canada's
[Montréal CSD profile](https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/moreinfo-plusinfo.cfm?DGUIDlist=2021A00052466023&Lang=E),
[Montréal CT map](https://www12.statcan.gc.ca/census-recensement/2021/geo/maps-cartes/thematicmaps-cartesthematiques/as/map-eng.cfm?dguid=2021S0503462&lang=E&mapid=5),
and
[Montréal ADA table](https://www12.statcan.gc.ca/census-recensement/2021/geo/maps-cartes/thematicmaps-cartesthematiques/low-ldt/map-eng.cfm?Dguid=2021S0503462&TYPE=1).

## External Canadian comparison boundary

The pinned external descriptor names Prédhumeau and Manley's
[version 2.1.0 Canadian synthetic population](https://doi.org/10.5281/zenodo.7572117),
the associated
[Scientific Data article](https://doi.org/10.1038/s41597-023-02030-4), the
9,573,036,764-byte Zenodo archive, its publisher-supplied MD5 checksum, licence,
schema, and bounded Nunavut territory comparison boundary.

The full archive is never fetched by default. Resolution requires both an
explicit `allow_download=True` and a caller-supplied downloader, and the result
must live in a cache outside git. Size and checksum are verified before the
cache entry becomes usable. The committed two-row CSV is project-authored and
contains no external records; it checks only schema and offline plumbing.

The separate committed JSON is aggregate-only empirical evidence generated by
an opt-in run. It records the exact FA archive member, its extracted SHA-256,
the two local output checksums, linked person and household totals, household
size distributions, linkage checks, and territory-level deltas. It contains no
source rows or direct identifiers. The FA scenario is not the LG scenario used
for validation in the associated article.

No DA join is attempted: the external projected 2021 population retains 2016
DA identities while the local population uses 2021 DAs. Raw sex/gender code
counts are retained only as non-crosswalked aggregates. Both outputs are
modelled artifacts, so neither is treated as observed truth or an oracle, and
the comparison cannot support scenario-superiority, DA-level, or national
quality claims.

Regenerate the software fixture with
`scripts/build_multiscale_validation_evidence.py`. Regenerating the empirical
artifact requires explicitly supplying the pinned extracted external member
and local Nunavut household/person outputs to
`scripts/build_external_canadian_comparison.py`; default tests stay offline and
validate the committed aggregate checksum.
