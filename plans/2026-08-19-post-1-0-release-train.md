# Post-1.0 Release Train

Status: active maintenance; `1.2.0` released\
Created: 2026-08-19\
Last updated: 2026-11-21\
Target: bounded `1.x` feature releases with patch releases as needed\
Next action: implement the core IPF localization and select one statistical family for source review; run Python 3.15 and dependency reviews independently\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Planning Horizon

Plan forward at four different confidence levels:

1. **Committed next release:** specify exact scope, exclusions, acceptance
   evidence, and release gate. Only one feature release may be in this state.
1. **Scoped following release:** name the control families and required method,
   but permit splitting or deferral when source or universe evidence fails.
1. **Forecast release:** reserve a coherent problem boundary without promising
   every candidate family or a fixed date.
1. **Provisional follow-on:** name a cross-cutting outcome and earliest useful
   window, but require the earlier releases to prove its implementation and
   maintenance prerequisites before it becomes scoped.

The later `1.5.0` and `1.6.0` entries below are tentative planning scenarios,
not scoped releases or dates. Review their order and contents after each release;
work beyond them remains conditional research. The
English/French localization work crosses this train and is owned by the
[bilingual localization plan](2026-08-19-bilingual-localization.md). Patch
releases are cut whenever a correctness, security, packaging, or documentation
fix should not wait for the next feature release.

## PR-Sized Work

This is the coordination view. Detailed acceptance belongs to the named owning
plan; a family that fails its evidence gate becomes `deferred` rather than
weakening that gate.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `REL12-01` | `done` | Terminal `done` or `deferred` status for [`SA12-01`–`SA12-15`](2026-08-01-expanded-small-area-controls.md#pr-sized-work) | Admit the individually accepted conditional-person control families to `1.2.0` | All four families are accepted within the directly sourced and explicitly qualified scope in the `SA12-12` decision |
| `REL12-02` | `done` | Completed [`I18N12-01`–`I18N12-05`](2026-08-19-bilingual-localization.md#pr-sized-work) | Ship the locale-safe message-catalogue foundation | The draft catalogue, locale rules, compatibility fixtures and scoped literal guard pass without a full-localization claim |
| `REL12-03` | `done` | Terminal status for [`RB12-01`–`RB12-09`](2026-08-26-responsibility-boundaries.md#pr-sized-work), completed [`ASSURE12-01`–`ASSURE12-02`](2026-07-12-correctness-assurance.md#pr-sized-work), and completed applicable [`TYPE12-01`–`TYPE12-08`](2026-08-01-strict-typing.md#pr-sized-work) slices | Complete the bounded maintainability ratchet | The bounded slices and CI acceptance passed; the separately reviewed archive extraction is deferred |
| `REL12-04` | `done` | `REL12-01`, `REL12-02`, `REL12-03` | Prepare and verify the `1.2.0` release candidate | The release acceptance gate below and the exact-commit procedure in `RELEASING.md` pass |

## `1.1.0` — Broad Compatible Small-Area Controls

Target window: August 2026\
Confidence: released

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
- the locked Python gate passes 1,701 tests with 6 documented skips and 95.01%
  combined branch coverage; the extended correctness suite passes 339 tests;
- Ruff, Pyright, CFF, public-interface, Sphinx, Markdown, JavaScript, and all 13
  browser scenarios pass; and
- fresh wheel, sdist, optional model-build, and fictional case-study installed
  smokes pass, including the 24-pack and 14-margin broad-pack contract.

Explicitly deferred from `1.1.0`: conditional age-15+ controls,
multiple-response language controls, immigrant-only place of birth, income
bands, percentage-derived controls, family entities, and collective
populations.

## `1.2.0` — Conditional Person Controls

Target window: November–December 2026\
Confidence: released

In parallel, establish the locale and message-catalogue infrastructure defined
by the bilingual localization plan. This foundation must preserve
machine-readable output and does not yet constitute a fully translated
product.

Treat maintainability as a bounded release deliverable rather than waiting for
the statistical and presentation surfaces to grow further:

The detailed ownership model, extraction sequence, and architecture-test rules
live in the
[responsibility-boundaries plan](2026-08-26-responsibility-boundaries.md).

- make the `95%` combined branch-coverage gate compare at two-decimal
  precision, so a rounded `94.5%`–`94.99%` result cannot satisfy a stated
  `95.00%` requirement, and restore at least `0.25` percentage points of
  candidate headroom;
- preserve the small beginner API and frozen `1.x` contracts while extracting
  cohesive route registration, request validation, and orchestration services
  from the highest-complexity `webapi` functions;
- select at least one feature-adjacent `cli_geo` or `control_packs` hotspot and
  reduce its branching or responsibility count rather than adding another
  control-family path directly to the existing function;
- record a reproducible complexity baseline and prevent functions changed by
  this tranche from increasing beyond it without an explicit reviewed reason;
- document every beginner export, require docstrings for newly added or
  changed supported symbols, and ratchet down the existing undocumented
  supported-surface count;
- route newly localized web-client text through the catalogue
  boundary so localization does not become another cross-cutting concern in
  the large adapter modules; and
- begin separating the Zenodo depositor's protocol client, checkpoint/state
  machine, and evidence validation behind unchanged fail-closed behavior. This
  extraction may continue across later minor releases, but new archive
  operations must not enlarge the monolithic path.

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
- joint use with the `1.1.0` broad pack is feasible on the bounded, directly
  sourced 2016 and 2021 CT and CSD cases; non-tract proxy evidence and the
  deferred DA/ADA scope are explicitly qualified in the
  [SA12-12 decision](2026-08-01-expanded-small-area-controls.md#sa12-12-bounded-joint-evidence-decision-2026-11-14);
- rare and structural-zero cases fail closed before calibration;
- fractional and realized residual evidence covers every added family; and
- exact (not integer-rounded) combined branch coverage is at least `95.00%`,
  with the release candidate at or above `95.25%` before any documented
  platform-only exclusions;
- focused characterization and crash/resume tests protect every extracted web
  or archive boundary, while architecture tests continue to prohibit core,
  workflow, CLI, and web dependency reversals;
- the maintained public-interface contract is unchanged or evolves only
  additively, and the supported-surface documentation ratchet passes; and
- Python 3.15 support is reassessed separately in November 2026 and is not a
  prerequisite for this feature release.

## `1.3.0` — Language, Migration Detail, And Income

Target window: first half of 2027\
Confidence: forecast, not a commitment

Also target reviewed Canadian English/French localization for core web-client
workflows. CLI and documentation localization are deferred. This interface tranche is independent of whether every
statistical language, migration, or income family passes its evidence gate.

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

Acceptance gate for every statistical family admitted to `1.3.0`:

- the vintage-specific source rows, classifications, denominators, and
  crosswalks are independently reviewed;
- multiple-response, immigrant-only, banded, zero/negative-income, or rounded
  percentage semantics are represented explicitly rather than normalized away;
- joint use with the retained broad packs passes bounded feasibility, support,
  structural-zero, suppression, fractional-residual, and realized-residual
  evidence;
- approximate mortgage or subsidy controls remain opt-in, use a distinct
  tolerance, and retain derivation provenance in every artifact;
- interfaces, manifests, documentation, and claim limitations identify exactly
  which families passed; and
- a family that fails remains validation-only and does not delay unrelated
  accepted families.

## `1.4.0` — Complete English/French Web Client

Target window: second half of 2027\
Confidence: provisional follow-on

Complete reviewed English/French localization for supported local-web client
paths. CLI and documentation localization remain deferred. Preserve
language-neutral commands, options, identifiers, schemas, JSON, CSV, evidence,
and reproducibility contracts. This release becomes scoped only after the
`1.2.0` catalogue/packaging foundation and `1.3.0` core localization prove
maintainable.

The detailed surface, translation-quality rules, machine-contract boundaries,
and acceptance evidence live in the
[bilingual localization plan](2026-08-19-bilingual-localization.md).

## Cross-Release Priorities And Dependencies

This is a planning sequence, not an instruction to run every track at once.
The next feature release is not committed until its scope is explicitly frozen.
Patch releases continue independently when warranted.

| Priority | Work | Sequencing and dependency | Decision or acceptance |
| --- | --- | --- | --- |
| 1 | Core web localization (`1.3.0`) | `I18N13-01` baseline and `I18N13-02` shared shell complete; core workflows, dynamic-message work, review, and distribution acceptance follow | Ship only reviewed `en-CA`/`fr-CA` coverage; keep machine output and persisted evidence stable. Human French review is a release dependency. |
| 1 | Python 3.15 validation | `ASSURE315-01` review complete → `ASSURE315-01B` reviewed lock refresh → `ASSURE315-02` clean Linux full gate → `ASSURE315-03` support decision | Work independently of a minor release. Promote support only after the full gate and platform review pass; otherwise document the blocker. |
| 2 | French and English Profile inputs | `SOURCEFR-01` and `SOURCEFR-02` complete for the verified 2016 and 2021 tract formats; review additional geographies and revisions separately | Require equivalent controls, suppression and geography checks, and source-language provenance; do not guess when a source is unavailable. |
| 2 | Next control family | Select **one** `1.3.0` candidate for source and universe review; implementation depends on denominators, crosswalks, suppression and feasible joint fits | Admit only after the full evidence gate; defer without blocking localization if evidence is insufficient. Other candidates remain research until individually reviewed. |
| 2 | Remaining web localization (`1.4.0`) | Review `1.3.0` coverage and maintenance evidence; inventory remaining supported surfaces and define PR-sized slices | Complete the explicitly inventoried, human-reviewed web scope. Generated maps, reports, CLI, and public documentation are not included by implication. |
| 2 | Dependency rationalization | `DEP-01` inventories and measures dependencies, including SciPy with and without support augmentation; `DEP-02` applies separately reviewed changes | Work independently when capacity permits; retain current dependencies unless evidence supports a change. Do not block a release solely for this review. |
| 3 | Additional controls (`1.5.0` scenario) | Learn from the first reviewed family and completed web work; choose a bounded next family and prepare per-family slices | Prioritize useful, directly sourced controls and defer unsupported or approximate families rather than bundling all candidates. |
| 3 | Validation and uncertainty (`1.6.0` scenario) | A named use and reviewed model profile precede a held-out scorecard; a bounded multiple-realization study follows if useful | Choose a measurable question, reproducible inputs and decision thresholds before implementation; avoid broad statistical or privacy guarantees. |
| 4 | Family entities, placement, richer profiles, adapters and other research | Require their individual source, privacy, use-case, contract, or consumer triggers | Keep as separately activated work, not implicit requirements of `1.3.0`–`1.6.0`. |

Ongoing compatibility, security, exact-commit CI, correctness, documentation,
release provenance, and incremental typing remain normal maintenance. A
qualified human French reviewer is an explicit planning dependency. Calendar
dates are not commitments: capacity, translation review, source access, and
fitting evidence determine actual timing.

## `1.5.0` — Additional Evidence-Qualified Controls

Confidence: tentative planning scenario; no target date or committed scope.

After `1.3.0` and `1.4.0` establish the localization and control workload,
select at most one coherent next control family, or a closely related pair only
if source and universe review supports a bounded implementation. Select from
remaining language, migration-detail, or income candidates according to user
value and evidence; none is assumed to have passed review. A family accepted
earlier need not be repeated.

Proposed sequence: record the user need and vintage/geography scope; review the
public source, universe, crosswalk and suppression; assess model representation
and candidate support; implement versioned controls and preflight; run bounded
joint fits with existing packs and whole-household integerization; then document
fractional and realized residuals and limitations across supported interfaces.
Define independently reviewable slices and fixtures before implementation.

Release gate: source and compatibility evidence, representative joint-fit and
failure-case results, installed-distribution checks, reproducibility, and exact
control scope in documentation. If the chosen family fails, defer it or select
another; do not silently substitute approximate targets. Approximate mortgage
or subsidy controls require a separate opt-in and provenance decision.

## `1.6.0` — Bounded Model Evaluation And Uncertainty

Confidence: tentative planning scenario; no target date or committed scope.

Target one reproducible evaluation rather than a wholesale model replacement:
choose a named study and reviewed profile, specify held-out comparisons and
metrics, and produce a scorecard for the retained CART and conditional-frequency
methods. If the scorecard and study justify it, add one bounded multiple-seed
or multiple-realization comparison with documented interpretation. Choose a
limited geography and vintage supported by authorized data. Write PR-sized
slices after the study and baseline are selected.

Release gate: reproducible input and seed provenance, reviewed metrics and
baselines, documented uncertainty and limitations, and regression and packaging
checks for any shipped interface. Failure to show an advantage is a valid
research result and does not justify changing the production method. A separate
privacy study, broader representativeness claims, and a simulation adapter are
outside this provisional scope.

## Conditional Work Beyond The Proposed Horizon

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
  commitment, the following release is scoped, the third is a forecast, and a
  fourth may be retained only as a prerequisite-gated provisional follow-on.
