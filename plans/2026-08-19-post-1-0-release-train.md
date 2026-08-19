# Post-1.0 Release Train

Status: `1.1.0` release candidate complete; later releases remain planned\
Created: 2026-08-19\
Last updated: 2026-08-19\
Target: bounded `1.x` feature releases with patch releases as needed\
Next action: publish the exact green `1.1.0` candidate, then begin the bounded
`1.2.0` evidence tranche without expanding its public surface prematurely\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Planning Horizon

Plan forward at three different confidence levels:

1. **Committed next release:** specify exact scope, exclusions, acceptance
   evidence, and release gate. Only one feature release may be in this state.
1. **Scoped following release:** name the control families and required method,
   but permit splitting or deferral when source or universe evidence fails.
1. **Forecast release:** reserve a coherent problem boundary without promising
   every candidate family or a fixed date.

Anything beyond that horizon remains a conditional research track. Patch
releases are cut whenever a correctness, security, packaging, or documentation
fix should not wait for the next feature release.

## `1.1.0` — Broad Compatible Small-Area Controls

Target window: August 2026\
Confidence: release candidate complete

Ship the additive control expansion already under implementation:

- retain the eight stable core packs;
- add eight expanded-housing packs and eight concise broad packs for the 2016
  and 2021 Census at CSD, CT, ADA, and DA levels;
- support 14 reviewed control families covering 15 of the 36 modeled fields;
- prepare all nine compatible household margins directly from a Profile bulk
  file when an expanded or broad pack is selected;
- retain separate, explicit person-control and universe-evidence inputs;
- validate all selected margins together while preserving whole households;
- enforce the declared control, universe, linkage, numerical, and provenance
  invariants at runtime rather than relying only on tests or documentation;
  and
- document controlled, coarsened, derived, and uncontrolled fields without a
  local-representativeness claim.

Acceptance gate:

- every one of the 24 manifests validates and has a stable public identifier;
- real 2016 and 2021 Profile fixtures reproduce all nine household margins;
- broad packs plan and calibrate nine household plus five person margins in one
  run;
- planning and calibration fail closed at runtime when pack identity, Census
  vintage, geography namespace, complete margin vectors, common geography,
  universe reconciliation, finite nonnegative counts, candidate support,
  structural-zero rules, household/person linkage, evidence checksums, or
  convergence requirements are violated;
- successful runs preserve whole-household linkage and record fractional and
  realized residuals, input identities, checksums, and claim limitations in
  their output evidence;
- CLI, Python, local-web, installed-wheel, documentation, compatibility, and
  schema-contract tests pass;
- the full locked test, coverage, correctness, type, lint, documentation,
  browser, distribution-smoke, and release-evidence gates remain green; and
- the changelog states the exact families and limitations.

Candidate evidence recorded 2026-08-19:

- all 24 manifests, 14 control families, and the frozen eight-pack `1.0.0`
  compatibility baseline pass their contract tests;
- public aggregate 2016 CT and 2021 ADA fixtures reproduce and reconcile all
  nine household margins, including the corrected non-subtotal dwelling-type
  mapping;
- the locked Python gate passes 1,700 tests with 6 documented skips and 95.01%
  combined branch coverage; the extended correctness suite passes 339 tests;
- Ruff, Pyright, CFF, public-interface, Sphinx, Markdown, JavaScript, and all 12
  browser scenarios pass; and
- fresh wheel, sdist, optional model-build, and fictional case-study installed
  smokes pass, including the 24-pack and 14-margin broad-pack contract.

Explicitly deferred from `1.1.0`: conditional age-15+ controls,
multiple-response language controls, immigrant-only place of birth, income
bands, percentage-derived controls, family entities, and collective
populations.

## `1.2.0` — Conditional Person Controls

Target window: November–December 2026\
Confidence: scoped following release

Implement a separately versioned conditional-person tier for:

- marital status;
- highest certificate, diploma, or degree;
- labour-force status; and
- full-/part-year and full-/part-time work activity.

These families share an age-15+ boundary but not necessarily identical source
denominators. Each must include an explicit, reproducible under-15 or other
not-applicable representation, or use a reviewed conditional-constraint
method. The release may contain fewer than all four families if any crosswalk
or universe cannot pass the gate; it must not weaken the gate to preserve the
target window.

Acceptance gate:

- vintage-specific Profile child rows and PUMF categories are independently
  reviewed;
- each denominator, not-applicable category, suppression rule, and rounding
  decision is explicit in the compatibility registry;
- joint use with the `1.1.0` broad pack is feasible on bounded 2016 and 2021
  CSD, CT, ADA, and DA cases;
- rare and structural-zero cases fail closed before calibration;
- fractional and realized residual evidence covers every added family; and
- Python 3.15 support is reassessed separately in November 2026 and is not a
  prerequisite for this feature release.

## `1.3.0` — Language, Migration Detail, And Income

Target window: first half of 2027\
Confidence: forecast, not a commitment

Evaluate the remaining count-based candidates from the current all-fields
profile:

- mother-tongue components;
- home-language components;
- immigrant place of birth completed through immigration status;
- employment-income bands; and
- total-income bands.

Multiple responses, immigrant-only detail, numeric banding, zero and negative
income, and vintage-specific classifications make this a distinct method and
evidence tranche. Families that do not pass remain validation-only rather than
delaying unrelated accepted families.

Mortgage and subsidy may appear only as an explicitly opt-in approximate tier.
Their rounded percentages must retain approximation provenance, denominator
reconciliation, and a tolerance distinct from count-quality controls.

## Beyond `1.3.0`

Do not assign a release number or date until its prerequisite contract exists:

- census-family and economic-family controls require represented family
  entities and roles;
- collective populations require a separate seed, entity, linkage, and output
  contract;
- richer hierarchical profiles require a separately versioned model profile;
- a breaking public-interface or persisted-schema change belongs to a future
  major release; and
- additional sources require a concrete research use, authority, provenance,
  privacy review, and maintenance owner.

## Release Movement Rules

- Freeze the committed release before implementation begins on the following
  release's public surface.
- Move an accepted family forward independently; do not bundle unrelated
  research merely to fill a version number.
- Move a failed or weakly supported family back to conditional research and
  record why.
- Record observable release outcomes in `CHANGELOG.md`; keep this file about
  future scope and gates.
- Revisit this train after every minor release. At most the next release is a
  commitment, the following release is scoped, and the third is a forecast.
