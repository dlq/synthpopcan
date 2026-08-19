# Expanded Hierarchical Tree Models Plan

Status: conditional research; pre-1.0 inventory completed\
Created: 2026-08-01\
Last updated: 2026-08-19\
Target: pre-`1.0` inventory and extension-contract proof only; richer profiles
and family hierarchy after `1.0.0`\
Next action: when a concrete research use justifies it, select one coherent
additive field family and design a separately versioned profile\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Outcome

Let researchers generate more of the information legitimately available in the
2016 and 2021 Census hierarchical Public Use Microdata Files (PUMFs) without
turning every source column into one sparse target class, weakening household
linkage, or implying unsupported small-area accuracy.

The end state should support:

- more reviewed household and person attributes in generated linked output;
- chained, interpretable model blocks with explicit dependencies;
- economic-family and census-family structure when the artifact contract can
  represent it honestly;
- derived fields that remain logically consistent with their inputs;
- appropriate treatment of grouped numeric measures;
- field-level fitness, privacy, provenance, and small-area-control metadata;
- deterministic generation and durable validation evidence; and
- explicit version boundaries and practical migration guidance when a new
  design supersedes an existing model or population artifact.

This plan expands what the model can represent. It does not establish that
every PUMF field is statistically fit for every geography, safe to publish in a
model artifact, or locally representative after small-area assignment.
The [expanded small-area controls plan](2026-08-01-expanded-small-area-controls.md)
owns control discovery, compatibility, calibration, and local-representativeness
evidence for current and future tree profiles. The
[methodological validation and uncertainty plan](2026-08-02-methodological-validation-and-uncertainty.md)
owns shared held-out metrics, ensemble and replicate-weight evaluation,
external benchmarks, and empirical disclosure-risk attack methods.

## Current Baseline

The 2016 hierarchical PUMF CSV has 116 columns and the 2021 CSV has 122. The
current all-fields profiles model 35 source columns and add derived
`household_size`, producing 36 substantive output fields. After accounting for
four source identifiers, the main survey weight plus 16 replicate weights, and
two geography/context columns, 58 source-role columns in 2016 and 64 in 2021
remain outside the current target profiles.

The two geography/context columns are:

- `PR`: province or territory of current residence; and
- `CMA`: census metropolitan area or census agglomeration of current residence,
  including the PUMF's residual/non-CMA grouping where applicable.

`PR` and `CMA` describe the coarse geography exposed by the PUMF. They may
scope training data or condition a model, but they are not ordinary generated
attributes and must not be presented as precise locations.

The current linked generator has one household model and one person model. For
each model, the complete target tuple is represented as one outcome class. This
preserves observed combinations for the selected fields, but extending that
tuple to dozens more columns would create sparse or nearly unique classes,
inflate artifacts, increase disclosure risk, and make rare combinations
unreliable.

The current output represents households and people. Although the source rows
contain economic-family and census-family identifiers and roles, generated
output does not represent those intermediate entities.

The pre-1.0 inventory is now published as
[`synthpopcan-hierarchical-pumf-field-eligibility-v1`](../docs/field-eligibility.md).
It covers all 116 and 122 source columns exactly once, reconciles the current 35
source targets per vintage, and records explicit structural, conditioning,
validation-only, or deferred roles for every other field. Its source-bound
aggregate evidence makes applicability and family-membership ambiguities
visible without adding a new model profile or publishing source rows.

## Scope And Non-Goals

In scope:

- the Statistics Canada 2016 and 2021 hierarchical Census PUMFs;
- field classification, model structure, training, generation, validation,
  packaging, documentation, and migration;
- household/person fields that can reuse the current linked-population contract
  or justify a clearly versioned replacement; and
- a separately versioned family hierarchy if evidence justifies it.

Out of scope without a separate approved design:

- generating source identifiers, survey weights, or replicate weights as
  synthetic attributes; source replicate weights may still be used for
  methodological stability and uncertainty evaluation;
- treating `PR` or `CMA` as synthetic small-area locations;
- fusing the individual PUMF into households as if its people were observed
  household members;
- reconstructing confidential records or claiming disclosure-proof output;
- promising controls for a field merely because it is present in the PUMF; and
- replacing immutable published model packages or DOI records in place.

## Completed Pre-`1.0` Baseline

The `1.0.0` work completed the machine-readable 2016/2021 field-eligibility
inventory, reviewed the existing profiles, and established generic
profile-inspection and control-compatibility extension contracts without
adding a new public expanded profile.

Production chained blocks, the broad additive field catalogue,
numeric-generation extensions, economic- and census-family entities, and a
replacement linked-population schema remain conditional work. They require
additive public interfaces or separately versioned artifact contracts.

## Phase 1 — Field Eligibility Inventory

Create one machine-readable inventory with a record for every 2016 and 2021
hierarchical PUMF column. Generate its starting point from the checked-in SPSS
metadata and CSV headers, then review it rather than maintaining an unaudited
handwritten list.

Each field record must include:

- census vintage, source name, label, categories, and source universe;
- cross-vintage concept identifier and predecessor/successor where applicable;
- entity level: household, economic family, census family, person, geography,
  identifier, or weight;
- within-entity constancy and applicable/not-applicable/missing codes;
- cardinality, weighted support, rare-category counts, and missingness;
- permitted role: `target`, `condition`, `derive`, `structural_key`,
  `validation_only`, `defer`, or `exclude`;
- recommended representation: categorical, component indicators, ordered band,
  grouped numeric, conditional numeric, or deterministic derivation;
- dependencies and consistency invariants;
- candidate Census Profile control family and universe, or an explicit
  `uncontrolled` result;
- disclosure and interpretation concerns; and
- review status, rationale, reviewer, and date.

Initial field families to classify include:

| Family | Examples | Principal decision |
| --- | --- | --- |
| Family structure | `CFSTAT`, `CFSTRUCT`, `CF_RP`, `EF_RP` | Requires roles and intermediate family entities; do not flatten blindly. |
| Indigenous identity | `ABOID`, `BFNMEMB`, `REGIND` | Potentially useful but sensitive; require terminology, support, and privacy review. |
| Immigration | `AGEIMM`, `YRIMM`/`YRIM` | Preserve applicability and consistency with age and immigrant status. |
| Education | `ATTSCH`, `CIP2011`/`CIP2021`, `SSGRAD`, `LOCSTUD` | Condition on age and education; reconcile vintage classifications. |
| Language | `FOL`, `KOL`, regular home/work language components, `NOL` | Preserve multiple-response components and applicability. |
| Labour | `COW`, `NAICS`, `NOCS`/`NOC21`, `JOBPERM`, `LSTWRK` | Condition on age, labour-force status, and work activity; coarsen rare groups. |
| Mobility and commuting | `MOB1`, `MOB5`, `MODE`, `DIST`, `PWDUR`, `POWST` | Preserve work and mobility applicability; do not infer precise locations. |
| Income | `MRKINC`, `INCTAX`, `GTRFS`, `TOTINC_AT`, low-income measures | Choose numeric/banded/derived representations and family universe. |
| Housing | `HCORENEED_IND`, `STIR_GRP`, `HHMAINP`, `PRIHM` | Separate household measures from person roles and derived ratios. |
| Parent/background | parental birthplace, ethnic or cultural origin, religion | Review sensitivity, vintage availability, support, and intended use. |

Acceptance:

- every source column in both headers appears exactly once;
- identifiers, weights, `PR`, and `CMA` have explicit non-target roles;
- all current 35 source targets reconcile to the existing profiles;
- every omitted column has a documented decision rather than an accidental
  omission; and
- cross-vintage mappings never erase a real definition or classification
  change.

## Phase 2 — Additive Household And Person Fields

Add only fields that can be represented as extra columns in the existing
household/person outputs without changing entity meaning. Do this in coherent,
reviewed profiles rather than redefining `all-fields` to mean every source
column.

Candidate additive profiles should be organized by research concept:

1. education and school attendance;
1. language knowledge and additional home/work-language components;
1. labour, industry, occupation, and job characteristics;
1. mobility and commuting;
1. income components and reviewed low-income measures;
1. immigration timing; and
1. sensitive identity/background fields only after a separate release review.

For every added field:

- retain source not-applicable and unavailable states until a documented
  transformation is applied;
- record whether it is controlled, validation-only, or carried through from
  the broad PUMF model;
- add 2016 and 2021 adapter fixtures and weighted source-distribution checks;
- update the field primer, package metadata, output data dictionary, and
  claims-to-evidence records; and
- use a new model/profile identifier. Never mutate an archived package behind
  an existing checksum or DOI.

Acceptance: archived all-fields packages and their checksums are not rewritten;
new profiles round-trip through CLI, API, durable web runs, and package
inspection; any compatibility break has an explicit version, error, and
documented replacement path; output columns have labels and universes; and no
added column is described as small-area-local without an implemented compatible
control.

## Phase 3 — Chained Model Blocks

Replace the single ever-growing target tuple with an optional directed chain of
small models. A proposed person chain is:

1. demographics and household context;
1. identity, immigration, and language;
1. education;
1. labour, occupation, and workplace characteristics;
1. mobility and commuting; and
1. income and derived socioeconomic measures.

Each block may condition only on source conditions, household context, and
outputs from completed predecessor blocks. The package must store the ordered
dependency graph, model type, target fields, conditions, random-seed derivation,
fallback behavior, and field metadata for every block.

Implementation requirements:

- introduce a versioned chained-model package contract rather than changing
  `synthpopcan-linked-tree-package-v1` semantics;
- reject cycles, duplicate target ownership, missing dependencies, and a field
  used before it is generated;
- derive independent deterministic random streams for each entity and block so
  adding a later block does not change earlier generated values;
- support conditional-frequency and CART blocks without requiring scikit-learn
  for generation;
- preserve explicit missing/not-applicable states during conditioning;
- report fallback from an exact condition to a broader/global distribution;
- bound package size, target-class cardinality, peak memory, and runtime; and
- audit support and purity per block and leaf/group, not only for the package as
  a whole.

The CLI and API should expose named profiles for ordinary users and an explicit
block graph for advanced model builders. The web interface should present the
named profiles and their implications, not dozens of unstructured checkboxes.

Acceptance: fixed-seed generation is deterministic across streaming and
in-memory paths; adding a terminal block leaves predecessor output unchanged;
dependency and fallback reports are complete; and representative expanded
models materially improve held-out field distributions without failing privacy
or resource budgets.

## Phase 4 — Economic And Census Family Hierarchy

Do not model family identifiers as ordinary categorical targets. If family
structure is adopted, introduce a new linked artifact version with explicit:

- synthetic household identifiers;
- synthetic economic-family identifiers nested in households;
- synthetic census-family identifiers nested in economic families or
  households according to the source definition;
- person membership and family/household roles; and
- cardinality and referential-integrity rules.

Generation should proceed structurally: household composition, family units,
family roles/counts, then people and their attributes. It must enforce at least:

- every person belongs to exactly one generated household;
- family identifiers reference an existing generated family;
- reference-person and maintainer roles satisfy their documented cardinality;
- family structure agrees with member roles and household size; and
- age, marital status, and child/partner roles do not form prohibited
  combinations defined by reviewed rules.

This requires a new linked-population schema and a new model-package schema.
Because family hierarchy is now post-`1.0`, a `1.x` implementation must publish
the richer schema as a separately versioned addition while retaining the
declared `1.0` household/person contract. Dropping that frozen contract or
changing its meaning requires a new major release. A converter may expose a
richer artifact as a household/person-only view when it can preserve meaning,
but it must never invent missing family relationships.

Acceptance: synthetic fixtures exercise multiple economic and census families
within households; independent validation recomputes every membership and role
invariant; compatibility behavior and any migration path are tested; archived
artifacts remain unchanged; and small-area calibration continues to select
whole households.

## Phase 5 — Numeric And Derived Representations

Classify high-cardinality values before modeling them. Use one of:

- reviewed public bands when analysis and controls operate on bands;
- a conditional numeric distribution with documented bounds, rounding, and
  tails when numeric values are necessary; or
- a deterministic derivation from already generated inputs.

Candidate derivations include age-at-immigration consistency, shelter-cost-to-
income groups, and selected low-income or family-income measures, but only when
the published definition and required inputs can be reproduced. If not, retain
the published grouped field as its own target and record the limitation.

Never generate a base value and its purported deterministic derivative
independently without a reconciliation rule. Validation must flag impossible
or contradictory results, not merely compare marginal distributions.

Acceptance: numeric outputs obey domains and tail policy; deterministic fields
recompute exactly; grouped outputs reconcile to their underlying values where
claimed; and no approximate derivation is labelled exact.

## Phase 6 — Fitness, Privacy, And Correctness Gates

Evaluate each candidate profile and geography with:

- weighted marginal and selected joint comparisons to held-out PUMF rows;
- missing/not-applicable and universe reconciliation;
- household, economic-family, census-family, and person invariants;
- multi-seed stability and rare-category behavior;
- model fallback rates and unseen-condition coverage;
- support, purity, uniqueness, and source-row leakage screening;
- exact/near-copy, nearest-neighbour, linked-signature, and baseline empirical
  disclosure-risk checks appropriate to its release class;
- replicate-weight or documented resampling stability where the source design
  supports it;
- package size, generation throughput, and peak memory;
- compatible Census Profile controls where available; and
- post-calibration residuals without claiming accuracy for uncontrolled fields.

Define quantitative budgets from the current packages and representative
expanded prototypes before setting release thresholds. Do not select arbitrary
thresholds solely to make a candidate pass.

Sensitive fields require a documented purpose and human release review in
addition to automated checks. A technically generatable field may remain
private, validation-only, coarsened, or excluded.

Reuse the methodological-validation plan's metric and attack implementations,
but keep profile-specific field semantics, privacy thresholds, source
authority, intended use, and final human release decisions here. High utility
on held-out distributions must not override a material disclosure or rare
linked-household finding.

Acceptance: every published profile has a field eligibility manifest, audit
report, held-out comparison, privacy decision, reproducible build, checksums,
generation smoke test, and explicit known limitations.

## Phase 7 — Interfaces, Documentation, And Release

Add one shared domain workflow and expose it consistently through:

- a library API for inventory, training, audit, packaging, and generation;
- CLI commands for inspecting eligibility, selecting a named profile, and
  inspecting a package's block graph and field provenance; and
- the local web app for guided selection, estimates, progress, cancellation,
  artifact inspection, and exact CLI handoff.

Keep current beginner defaults. Expanded profiles must be opt-in until their
runtime, interpretation, and privacy implications are well understood.

Documentation must explain:

- the difference between source availability, modeled fields, controlled
  fields, derived fields, and validation-only fields;
- why `PR` and `CMA` are context rather than generated small-area geography;
- entity levels and family relationships;
- cross-vintage field differences;
- missing/not-applicable semantics;
- suitable and unsuitable research uses; and
- how to cite the PUMF, software, model package, and validation evidence.

Publish new models under new identifiers and immutable archival records. A
numbered release should adopt this track only after its exact included phases
and compatibility promises are named; this plan does not silently block
the released `0.7.2` Can-FED and ODEF adapters or the simulation-interoperability
sequence.

## Sequencing And Completion

Work proceeds in this order:

1. inventory and field decisions;
1. a small additive profile proving the evidence and interface path;
1. chained blocks for a bounded 2021 provincial model;
1. a parallel 2016 compatibility case;
1. family hierarchy only after the additive/chained evidence is satisfactory;
1. broader catalogue candidates after geography-specific fitness review; and
1. public release only after archival and documentation gates pass.

The plan is complete when every hierarchical PUMF field has a reviewed role;
supportable additive and chained fields are available through coherent named
profiles; any adopted family hierarchy has a versioned, validated artifact
contract; published packages pass correctness and privacy gates; breaking
changes have clear errors and practical migration guidance; and documentation
makes unsupported claims difficult to make accidentally.
