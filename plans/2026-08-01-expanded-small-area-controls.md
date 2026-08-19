# Expanded Small-Area Controls Plan

Status: `1.1.0` release candidate complete; later tranches scoped or forecast\
Created: 2026-08-01\
Last updated: 2026-08-19\
Target: `1.1.0` broad compatible packs; conditional person controls in `1.2.0`\
Next action: preserve the completed 24-pack/14-family gate through exact-commit
`1.1.0` publication, then review the age-15+ marital, education, labour-force,
and work-activity crosswalks for `1.2.0`\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

Release sequencing and confidence are defined in the
[post-1.0 release train](2026-08-19-post-1-0-release-train.md). This plan owns
the control-specific method and evidence; the release-train plan owns which
accepted tranche is targeted to which minor release.

## Outcome

Allow a researcher to calibrate a generated hierarchical population to as many
defensible 2016 or 2021 Census small-area controls as its model profile can
support, while preserving whole households and any future economic-family and
census-family relationships.

The workflow should:

- discover and classify compatible public controls for CSD, CT, ADA, and DA;
- match controls to both the current 36-field all-fields output and future
  expanded hierarchical profiles;
- combine compatible low-dimensional household, family, and person margins in
  one reviewed control pack;
- reconcile universes, suppression, rounding, categories, geography, and
  census vintage before fitting;
- plan and reject infeasible work before an expensive calibration;
- fit selected margins against whole-household weights;
- report fractional and realized residuals for every field and geography; and
- distinguish locally controlled fields from broad-model, derived,
  validation-only, or unavailable fields in every artifact and interface.

This plan owns expanded small-area control implementation. The
[correctness-assurance plan](2026-07-12-correctness-assurance.md) owns the
general evidence standards, and the
[expanded hierarchical tree-model plan](2026-08-01-expanded-hierarchical-tree-models.md)
owns which PUMF fields and entity relationships a generated population can
represent. The
[methodological validation and uncertainty plan](2026-08-02-methodological-validation-and-uncertainty.md)
owns shared solver oracles, backend and integerization comparisons,
uncertainty ensembles, statistical metrics, external benchmarks, and empirical
disclosure-risk methods.

## Current Baseline

The compatible default control preparer builds household-size and tenure
margins. Expanded packs now build nine reviewed household margins: size,
tenure, dwelling type, condominium status, bedrooms, rooms, housing
suitability, construction period, and repair condition. The
linked calibration engine can already:

- consume multiple normalized household margins;
- consume a separate set of person margins;
- fit household controls first and then refine the same household weights
  jointly against household indicators and linked-person contributions;
- preserve household/person linkage during integerization; and
- report preflight issues and per-margin fitted and realized residuals.

The completed
[source-coverage inventory](../docs/small-area-control-coverage.md) screens the
current all-fields output across both census vintages and four geography
levels. It identifies:

- 23 count-based control families covering 29 of 36 modeled fields;
- two lower-confidence fields derivable from rounded percentages; and
- five fields without a matching Census Profile count distribution.

That inventory is a ceiling, not an implementation list. Fourteen families
covering 15 modeled fields are now implemented in core or expanded packs. The
remaining nine count-based families still need reviewed child-category
crosswalks, universe alignment, suppression handling, fixtures, and calibration
evidence.

Those nine families are assigned provisionally rather than left in an
unbounded queue:

- `1.2.0`: marital status, education, labour-force status, and work activity;
- `1.3.0`: mother tongue, home language, place of birth, employment income,
  and total income; and
- `1.3.0` opt-in only: the percentage-derived mortgage and subsidy candidates,
  if their approximation gate passes.

Assignment is not acceptance. A family that cannot satisfy its universe,
crosswalk, suppression, support, and residual evidence remains uncontrolled
and returns to conditional research.

## `1.1.0` Runtime Invariants

The expanded control surface must enforce its scientific and structural
assumptions while a plan or calibration is running. Tests demonstrate the
behavior, but tests are not a substitute for validating each user's actual
inputs. The runtime must fail closed before fitting when any of these invariants
is false:

- the pack identifier, definition hash, registry revision, Census vintage,
  geography level, namespace, and linked-population schema agree;
- every required margin has exactly one complete, non-duplicated category
  vector for every admitted geography;
- household and person controls use the same explicit geography set;
- each household margin reconciles to the declared private-household total;
- each person margin independently reconciles to persons in private households
  rather than being summed across margins;
- every count and tolerance is finite and nonnegative, and suppressed, missing,
  zero, rounded, and not-applicable states remain distinguishable;
- every positive target category has candidate support, every declared
  structural zero is respected, and uncontrolled candidate categories remain
  visible;
- every person has one valid household link and person contributions alter only
  whole-household weights; and
- control tables, universe evidence, pack definitions, and admitted geography
  sets match their recorded checksums and identities.

A successful calibration must also enforce and record these postconditions:

- solver convergence satisfies the requested tolerance or the run fails;
- weights and realized multiplicities are finite and nonnegative;
- household/person linkage and geography inheritance remain intact;
- fractional fitted residuals and integerized realized residuals are recomputed
  for every selected margin and geography; and
- the run manifest records exact inputs, hashes, pack identity, derivations,
  exclusions, tolerances, residuals, and permitted claim boundary.

Acceptance: public CLI, Python, and local-web paths execute the same invariant
checks; malformed and near-valid adversarial fixtures fail before producing a
successful artifact; installed-distribution smoke tests exercise the invariant
path; and no interface can silently downgrade, remove, or reinterpret a
required margin.

Future tree profiles may add fields from the 58 currently unmodeled 2016
source-role columns and 64 corresponding 2021 columns. Presence in a generated
file does not make a field controllable. Every extended field must pass the
source and compatibility process below.

## Principles And Boundaries

- Fit multiple interpretable margins, not one enormous all-field cross-tab.
- Use one census vintage, target geography namespace, and model population
  universe per calibration run.
- Keep household, economic-family, census-family, and person quantities
  distinct even when the source publishes them in one Profile product.
- Preserve whole households. Person and future family controls may change a
  household's weight but may not detach or independently place its members.
- Treat zero, suppressed, missing, rounded, and not-applicable values as
  different states.
- Never convert a conditional percentage into an exact count without recording
  the approximation and tolerance.
- Never call an uncontrolled model field locally representative.
- Do not silently discard a geography or margin to make a fit pass.
- Preserve the frozen `1.x` household-size/tenure inputs and core pack
  identifiers. Add new pack identifiers and additive inputs for expanded
  behavior; reserve an incompatible replacement for a future major release.

## Completed Pre-`1.0` Baseline

Completed in `0.9.0` on 2026-08-10. Strict generic registry, pack, and bound
evidence contracts now support reviewed 2016/2021 private-household
household-size, tenure, and broad age-by-sex/gender definitions at CSD, CT,
ADA, and DA levels. Their shared API, CLI, and local-web extension points fail
closed on incompatible counts, candidates, geography, or universe evidence.
The compatible household and private-household-person tranches below were
added after 1.0; conditional person and economic families remain research work.

The `0.9.0` tranche implemented only:

- the versioned compatibility-registry and control-pack contracts;
- reviewed 2016 and 2021 household-size and tenure controls;
- one reviewed private-household age-by-sex/gender person-control family;
- the feasibility and combined whole-household contribution path needed by
  those packs;
- bounded evidence at explicitly named supported CSD/CT/ADA/DA cases rather
  than an all-geography promise; and
- the generic CLI/API/web extension points needed to add later packs without
  redesigning the frozen surface.

The first post-1.0 tranche adds reviewed dwelling type, condominium, bedrooms,
rooms, housing suitability, construction period, and repair controls to eight
expanded packs without changing the core packs. A second eight-pack tier adds
citizenship, immigrant status, generation status, and visible-minority status
from direct private-household-person Profile universes. The remaining candidate
control families, conditional/economic packs,
family-aware controls, exhaustive geography coverage, collective/non-private
household implementation, and broad catalogue publication move after `1.0.0`.
The field/control inventory may continue as research, but incomplete inventory
rows do not block the interface freeze when the implemented core is explicit.

Out of scope without a separate method and evidence:

- fitting confidential or restricted control tables in a public package;
- inventing local controls by disaggregating broad PUMF weights;
- treating `PR` or `CMA` PUMF context as an assigned small area;
- calibrating incompatible 2016 and 2021 geography in one fit;
- assigning people independently of their households; and
- claiming record-level truth from aggregate calibration.

## Post-`1.0` Population Scope — Collective And Non-Private Households

Private households and their linked residents remain the first supported
calibration universe. Before claiming complete local or national population
coverage, design a separate path for collective dwellings, institutional
residents, and other people outside ordinary private households.

The design must determine, by Census vintage:

- which collective-dwelling and resident categories are publicly controllable
  at CSD, CT, ADA, or DA;
- whether the PUMF or another authorized public seed can represent those
  categories without pretending they are ordinary households;
- the required entity, linkage, identifier, and output-schema changes;
- which controls and geographies are suppressed or unavailable;
- whether separate generation and calibration should be combined only at the
  final population-manifest level; and
- how exclusions and denominators appear in national planning, validation,
  maps, and user-facing claims.

Acceptance: the project either implements a separately validated collective
population component or declares its exclusion in every complete-coverage
claim; collective residents are never forced into private-household structure;
and combined totals identify each component's universe and evidence.

## Phase 1 — Field/Control Compatibility Registry

Create a machine-readable registry joining the tree-model field eligibility
inventory to every reviewed small-area control candidate. Use stable concept
identifiers so vintage-specific names such as `SEX`/`GENDER`,
`MarStH`/`MARSTH`, `NOCS`/`NOC21`, and `CIP2011`/`CIP2021` remain explicit.

Each record must include:

- concept identifier and 2016/2021 generated field names;
- generated entity level and model-profile requirements;
- source product, characteristic IDs, labels, child rows, revision, and URL;
- source universe, reference period, estimate type, and unit;
- target geographies and geographic coverage counts;
- exact, coarsened, component, banded, conditional, percentage-derived, or
  unavailable classification;
- category crosswalk with unmapped and not-applicable categories;
- suppression, rounding, zero-cell, and missing-value policy;
- whether a complete mutually exclusive control vector can be constructed;
- compatible companion fields required to complete a conditional universe;
- privacy, interpretation, and terminology notes;
- implementation and fixture status; and
- provenance and reviewer/date fields.

The registry must be able to answer mechanically:

1. Does this generated model profile contain the required field and entity
   structure?
1. Is a compatible control available for this vintage and geography level?
1. Can it share a calibration universe with the other selected margins?
1. Is the crosswalk implemented and independently tested?
1. Is the field controlled, approximate, validation-only, or unavailable in
   this particular run?

Acceptance:

- every current and planned tree field has an explicit control status;
- every implemented control maps to one reviewed field concept and universe;
- the registry validates against a versioned schema;
- no runtime code relies on undocumented characteristic IDs; and
- source revisions or category changes produce a reviewable registry diff.

## Phase 2 — Source Screening For Extended Fields

Screen the 2016 and 2021 Census Profile—and another public source only when its
authority, licence, vintage, geography, and maintenance case are documented—for
the extended tree-field families.

Priority screens include:

| Extended field family | Candidate Profile material to assess | Main risk |
| --- | --- | --- |
| Indigenous identity and registration | identity, registered-status, and band-membership tables | sensitivity, terminology, sparse cells, sample universe |
| Education | attendance, diploma, and field-of-study tables | age universe and vintage classification |
| Language | official-language knowledge, first official language, and regular home/work language | multiple responses and work applicability |
| Labour | class of worker, industry, occupation, job status, and last-worked tables | age/work universe and sparse categories |
| Mobility | one- and five-year mobility status | prior-residence universe and changed geography |
| Commuting | mode, duration, vehicle occupancy, and place-of-work status | employed commuter universe and pandemic effects |
| Immigration timing | age/year/period of immigration | immigrant-only universe and coarsening |
| Income and low income | income bands, source components, and low-income status | person/family universe, numeric bands, rounding |
| Housing need and affordability | shelter-cost-to-income and core-need summaries | derived definitions and household eligibility |
| Family structure | household composition and census-family tables | entity mismatch with current household/person schema |
| Background fields | parental birthplace, ethnic/cultural origin, religion | sensitivity, interpretation, vintage availability |

Record `unavailable` when the public source lacks a defensible count vector.
Summary statistics, medians, averages, rates without reliable denominators, or
non-exclusive categories are not automatically suitable controls.

For each geography level, report:

- Profile records and authoritative boundary records;
- numeric, positive, suppressed, zero, and incomplete vectors;
- the exact intersection with the model profile and selected control pack;
- unmatched Profile/boundary identifiers; and
- coverage by province/territory and relevant urban/rural scope.

Acceptance: every screened field has a cited source decision; counts reproduce
from pinned inputs; all geography discrepancies are named; and the output does
not confuse source availability with an approved crosswalk.

## Phase 3 — Universe Reconciliation

Define explicit full-universe representations for margins that are currently
conditional. Examples include:

- mortgage status among owners, completed with renter/band/not-applicable
  categories when fitted with all private households;
- subsidy status among tenants, completed with owner/not-applicable categories;
- place of birth detail among immigrants, completed with non-immigrant and
  non-permanent-resident categories through immigration status;
- education and labour characteristics for the population aged 15+, completed
  with an under-15 not-applicable category when the person calibration universe
  is all people in private households; and
- commuting fields completed with did-not-work, worked-at-home, no-fixed-place,
  and other documented applicability states.

Do not add a synthetic not-applicable category merely to force equal totals.
The category must follow the source definition and be reproducible from
published companion counts. Where this is impossible, support conditional
constraints explicitly or keep the field validation-only.

The reconciler must:

- distinguish total population from people in private households;
- distinguish households, occupied private dwellings, census families,
  economic families, persons aged 15+, workers, commuters, immigrants, owners,
  and tenants;
- reconcile rounded child cells to authoritative totals under a documented
  method without hiding residuals;
- retain suppression and imputation decisions in provenance; and
- reject totals that cannot be made mutually consistent within the declared
  tolerance.

Acceptance: every pack margin names its universe; all margins fitted together
have a documented common representation or explicit conditional semantics;
the preflight detects deliberate universe-mismatch fixtures; and no rounded or
imputed count is presented as observed exact data.

## Phase 4 — Versioned Control Packs

Define a versioned control-pack manifest containing:

- pack identifier, version, label, census vintage, geography level, namespace,
  and source revisions;
- compatible linked-population and model-profile versions;
- required entity levels, fields, category mappings, and derivations;
- household, economic-family, census-family, and person margin files;
- universe and approximation policy for each margin;
- expected geography set and explicit exclusions;
- checksums, row/cell counts, and provenance;
- planner estimates and recommended calibration settings; and
- known limitations and permitted claims.

Initial packs should proceed in this order:

1. **Core household:** household size, tenure, structural dwelling type, rooms,
   bedrooms, condominium status, repair condition, construction period, and
   housing suitability.
1. **Core person:** reviewed age-by-sex/gender for people in private households.
1. **Demographic:** marital status, citizenship, immigration, generation,
   visible-minority group, mother tongue, and home language.
1. **Conditional/economic:** place of birth, education, labour-force status,
   work activity, employment-income bands, and total-income bands.
1. **Approximate opt-in:** mortgage and subsidy based on rounded percentages.
1. **Extended education/labour/mobility:** only fields admitted by the expanded
   tree eligibility inventory and the source screen.
1. **Extended sensitive/background:** separately reviewed and never enabled by
   a broad default merely because source cells exist.
1. **Family-aware:** census-family and economic-family margins only after the
   expanded linked schema represents those entities and roles.

A pack may contain many low-dimensional margins. Do not build a Cartesian
cross-tab across every selected field. Joint margins should be added only when
they encode an important dependency, have adequate source and candidate
support, and materially improve validation.

Acceptance: manifests validate and round-trip; pack/model incompatibility is
detected before data loading; every artifact is checksummed; old two-margin
inputs either remain supported or fail with a version-specific migration path;
and pack contents can be inspected without running a fit.

## Phase 5 — Feasibility Planner

Plan every multi-margin run before calibration. The planner must:

- validate census vintage, geography level, namespace, model profile, linked
  schema, and control-pack compatibility;
- compute the exact common geography intersection for every selected margin
  and boundary/relationship artifact;
- report exclusions by reason rather than using only a total count;
- check candidate columns, categories, entities, and linkage;
- detect missing candidate categories, uncontrolled candidate categories,
  structural zeros, contradictory zero targets, and incompatible totals;
- measure support for every control cell in household-contribution space;
- identify duplicate or linearly redundant constraints;
- estimate constraints, candidate contributions, memory, runtime, output size,
  and parallelism;
- assess likely convergence and integerization pressure; and
- recommend a documented coarsening or lower-priority margin removal when a
  pack is infeasible.

Planner decisions must be explicit inputs to the run manifest. The executor may
not silently change the selected pack, geography set, categories, pool size, or
tolerance.

Acceptance: infeasible synthetic fixtures stop before fitting; estimates have
calibrated error bounds on representative CSD/CT/ADA/DA cases; repeated plans
are deterministic; and the CLI, API, and web app produce the same normalized
plan.

## Phase 6 — Household, Person, And Family Contributions

Retain the current household-first design:

1. fit household margins for each target geography;
1. build one contribution matrix whose columns are candidate households;
1. add household indicator rows and linked-person count rows;
1. when the expanded linked schema exists, add economic-family and
   census-family contribution rows aggregated within each household;
1. update one weight per household against all selected constraints; and
1. integerize household weights so every linked entity moves together.

Family controls must count generated family entities or roles inside a
household; they must not treat a family identifier as a categorical person
attribute. The contribution builder must independently verify family nesting
before fitting.

Evaluate whether the current multiplicative joint updater remains numerically
appropriate as packs grow. Compare any alternative—such as generalized raking,
entropy calibration, or bounded optimization—on convergence, residuals,
structural zeros, deterministic behavior, runtime, memory, and interpretability
before changing the backend. Preserve the current method unless evidence shows
a material improvement.

Phase 1 of the methodological-validation plan supplies the independent
solver-backed oracle, generated feasible contribution cases, weight bounds,
hard/soft-constraint semantics, and backend comparison method. This plan owns
how a selected backend consumes versioned control packs and reports
field-, unit-, and geography-specific outcomes.

Acceptance: every selected constraint appears in the contribution matrix and
report; whole-household linkage survives realization; family counts reconcile
independently; redundant and unsupported rows are reported; and backend changes
have differential fixtures against the released behavior.

## Phase 7 — Validation And Claims

Produce validation at four layers:

1. **Source:** crosswalk completeness, totals, suppression, rounding, and
   geography identifiers.
1. **Candidate:** field/entity availability, category support, linked
   household/family/person integrity, and broad-model distribution.
1. **Fractional fit:** convergence and absolute/relative residuals for every
   cell and margin.
1. **Realized output:** integer residuals, household/family/person counts,
   linkage, geography assignment, and aggregation to authoritative parent
   geographies.

Reports must summarize coverage and tail behavior, not only maximum error.
Include:

- controlled, approximate, validation-only, derived, and uncontrolled fields;
- geography exclusions and their population/household denominators;
- residual distributions by margin and geography;
- rare and structurally unsupported categories;
- effective household weight concentration and candidate reuse;
- sensitivity to candidate-pool and random/subsample seeds;
- aggregation reconciliation at CSD/CMA/province/national levels where
  relationships are authoritative; and
- field-specific interpretation and claim limitations.

Use the methodological-validation plan's shared definitions for effective
sample size, weight concentration, held-out multivariate comparisons,
relationship signatures, ensemble stability, and uncertainty components.
Control-pack reports retain responsibility for naming the exact source
universe, approximation, geography, field, and denominator behind each metric.

Acceptance: an independent validator recomputes representative source totals,
contributions, residuals, linkage, and aggregation from emitted artifacts;
failed/non-converged runs cannot appear successful; and documentation never
extends local representativeness from controlled margins to uncontrolled
fields.

## Phase 8 — Interfaces And Researcher Workflow

Provide one shared Python workflow used by the library, CLI, and local web app.
The researcher-facing sequence should be:

1. inspect a generated model/profile and available compatible packs;
1. select census vintage and geography level;
1. inspect fields, universes, approximations, coverage, and exclusions;
1. run the feasibility planner;
1. explicitly accept any approximate or coarsened margins;
1. execute or resume the calibration;
1. inspect per-margin fractional and realized validation; and
1. export linked output, control-pack manifest, plan, report, reproduction
   recipe, and checksums.

CLI/API contracts should support one household pack and one person/family pack,
or one combined manifest referencing their component files. Retain raw
normalized-control inputs when they remain useful to advanced workflows, not
solely as a pre-1.0 compatibility obligation.

The web app should use named packs and progressive disclosure. It should not
present dozens of field checkboxes without universe, support, and approximation
context. Every web action must have an exact CLI handoff and durable run record.

Acceptance: equivalent requests normalize identically across all surfaces;
fixed-seed outputs and reports match; errors name the field, margin, geography,
and remedy; and a humanities researcher can tell which results are locally
anchored without reading implementation code.

## Phase 9 — Scale, Evidence, And Publication

Exercise bounded cases before national execution:

- one urban and one non-urban CSD/ADA/DA case per vintage where sources permit;
- one CT case, explicitly limited to tracted areas;
- at least one sparse or suppressed geography case;
- one conditional-universe pack;
- one expanded-tree profile; and
- one future family-aware fixture before family controls are enabled.

Then benchmark province-scale and national planning/execution with restartable
batches, bounded memory, explicit concurrency, durable checkpoints, and
aggregate evidence. A national run is not required to prove every individual
crosswalk, but no national claim may exceed the geographies and fields actually
validated.

Published packs require immutable source revisions, manifests, checksums,
licensing/attribution, documentation, correctness evidence, and archival
records. Control packs and model packages must be versioned independently so a
source revision does not silently change a model and vice versa.

This track runs in parallel with the numbered enrichment and interoperability
sequence. A numbered release adopts it only when the release notes identify the
included packs, model profiles, geography levels, and claims.

## Sequencing And Completion

Work proceeds in this order:

1. compatibility-registry schema and generated baseline inventory;
1. reviewed core household crosswalks for 2016 and 2021;
1. private-household age-by-sex/gender person crosswalk;
1. first versioned household/person pack and feasibility planner;
1. bounded CT/ADA/DA evidence, calibration-oracle evidence, and interface parity;
1. collective/non-private-household source and entity-scope decision;
1. demographic and conditional/economic packs;
1. extended tree-field source screens as model fields are admitted;
1. family-aware controls only after the linked family schema exists; and
1. broader catalogue publication after fitness and privacy review.

The plan is complete when every supported generated field has an explicit
small-area control status; reviewed packs can combine compatible margins in one
whole-household fit; extended model profiles select only compatible controls;
conditional and family universes are represented honestly; planners reject
infeasible work before calibration; validation distinguishes every claim tier;
breaking changes have explicit schema versions and migration guidance; and
published packs have durable source and correctness evidence.
