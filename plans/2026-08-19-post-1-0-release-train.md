# Post-1.0 Release Train

Status: active maintenance; `1.1.0` released and `1.2.0` committed next\
Created: 2026-08-19\
Last updated: 2026-08-28\
Target: bounded `1.x` feature releases with patch releases as needed\
Next action: complete `SA12-01`, `I18N12-01`, and `RB12-02` before expanding the
`1.2.0` public surface\
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

Anything beyond that horizon remains a conditional research track. The
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
| `REL12-01` | `blocked` | Terminal `done` or `deferred` status for [`SA12-01`–`SA12-15`](2026-08-01-expanded-small-area-controls.md#pr-sized-work) | Admit the individually accepted conditional-person control families to `1.2.0` | Every admitted family has accepted source, universe, runtime, residual, and interface evidence; a failed family is explicitly deferred |
| `REL12-02` | `blocked` | Completed [`I18N12-01`–`I18N12-05`](2026-08-19-bilingual-localization.md#pr-sized-work) | Ship the locale-safe message-catalogue foundation | The packaged catalogue, locale rules, compatibility fixtures, and static guard pass without a full-localization claim |
| `REL12-03` | `blocked` | Terminal status for [`RB12-01`–`RB12-09`](2026-08-26-responsibility-boundaries.md#pr-sized-work) and completed applicable [`TYPE12-01`–`TYPE12-08`](2026-08-01-strict-typing.md#pr-sized-work) slices | Complete the bounded maintainability ratchet | Each required boundary and documentation slice meets its local acceptance; deferred archive extraction does not enlarge the executor |
| `REL12-04` | `blocked` | `REL12-01`, `REL12-02`, `REL12-03` | Prepare and verify the `1.2.0` release candidate | The release acceptance gate below and the exact-commit procedure in `RELEASING.md` pass |

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
Confidence: committed next release

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
- route newly localized human-facing CLI and web text through the catalogue
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
- joint use with the `1.1.0` broad pack is feasible on bounded 2016 and 2021
  CSD, CT, ADA, and DA cases;
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

Also target reviewed Canadian English/French localization for the core CLI and
local-web workflows. This interface tranche is independent of whether every
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

## `1.4.0` — Complete English/French Supported Surface

Target window: second half of 2027\
Confidence: provisional follow-on

Complete reviewed English/French localization for every supported CLI and
local-web path and for maintained public user documentation. Preserve
language-neutral commands, options, identifiers, schemas, JSON, CSV, evidence,
and reproducibility contracts. This release becomes scoped only after the
`1.2.0` catalogue/packaging foundation and `1.3.0` core localization prove
maintainable.

The detailed surface, translation-quality rules, machine-contract boundaries,
and acceptance evidence live in the
[bilingual localization plan](2026-08-19-bilingual-localization.md).

## Beyond `1.4.0`

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
