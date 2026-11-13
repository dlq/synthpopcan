# Expanded Small-Area Controls Plan

Status: active feature implementation; `1.1.0` released and `1.2.0` committed\
Created: 2026-08-01\
Last updated: 2026-11-13\
Target: `1.1.0` broad compatible packs; conditional person controls in `1.2.0`\
Next action: investigate the realized tract residuals and apply the
education source contract in `SA12-05` when its prerequisites are complete\
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

## PR-Sized Work

These rows are the executable `1.2.0` tranche. Source decisions may proceed in
parallel. A family whose evidence slice does not pass becomes `deferred`; its
runtime slice does not begin and the other families continue independently.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `SA12-01` | `done` | Released `1.1.0` registry and runtime invariants | Versioned age-15+ universe and not-applicable/conditional-semantics contract | The contract distinguishes all-private-household persons, age-15+ denominators, under-15 states, suppression, and rounding; mismatch fixtures fail before fitting |
| `SA12-02` | `done` | Pinned 2016 and 2021 Profile definitions | Marital-status source decision and crosswalk | Child rows, categories, denominators, suppression rules, vintage differences, and fixture totals reproduce independently |
| `SA12-03` | `in progress` | `SA12-01`, accepted `SA12-02`, `SA12-10` | Marital-status preparer, registry entry, and pack component ([#53](https://github.com/dlq/synthpopcan/issues/53)) | Normalized controls validate and round-trip; unsupported categories and universe mismatches fail closed |
| `SA12-04` | `done` | Pinned 2016 and 2021 Profile definitions | Education source decision and crosswalk ([#55](https://github.com/dlq/synthpopcan/issues/55)) | Degree categories, age universe, vintage classifications, suppression rules, and fixture totals reproduce independently |
| `SA12-05` | `blocked` | `SA12-01`, accepted `SA12-04`, `SA12-10` | Education preparer, registry entry, and pack component | Normalized controls validate and round-trip; not-applicable and unmapped categories remain explicit |
| `SA12-06` | `ready` | Pinned 2016 and 2021 Profile definitions | Labour-force-status source decision and crosswalk | Categories, age denominator, vintage differences, suppression rules, and fixture totals reproduce independently |
| `SA12-07` | `blocked` | `SA12-01`, accepted `SA12-06`, `SA12-10` | Labour-force preparer, registry entry, and pack component | Normalized controls validate and round-trip; support, zero, and universe failures stop before fitting |
| `SA12-08` | `ready` | Pinned 2016 and 2021 Profile definitions | Work-activity source decision and crosswalk | Full/part-year and full/part-time categories, applicability, suppression, and fixture totals reproduce independently |
| `SA12-09` | `blocked` | `SA12-01`, accepted `SA12-08`, `SA12-10` | Work-activity preparer, registry entry, and pack component | Normalized controls validate and round-trip; mutually exclusive states and denominators are enforced |
| `SA12-10` | `in progress` | `SA12-01` | Shared conditional-person reconciliation and preflight path | The common implementation represents not-applicable states or explicit conditional constraints without silently manufacturing totals; adversarial cases fail closed |
| `SA12-11` | `blocked` | `SA12-10` and at least one accepted family runtime slice | Separately versioned conditional-person pack tier | Manifests have stable identifiers, semantic checksums, inspectable contents, and fail-closed compatibility with the retained broad packs |
| `SA12-12` | `blocked` | `SA12-11` | Joint bounded feasibility and calibration evidence | Accepted families run jointly with broad packs on reviewed 2016/2021 CSD, CT, ADA, and DA cases; fractional and realized residuals are independently recomputed |
| `SA12-13` | `blocked` | `SA12-12` | Python and CLI adoption through the shared workflow | Equivalent library and command requests normalize identically; public-interface and machine-output fixtures remain additive |
| `SA12-14` | `blocked` | `SA12-12` | Local-web and durable-run adoption through the shared workflow | HTTP normalization, progress events, run evidence, resume behavior, and browser scenarios match the accepted pack semantics |
| `SA12-15` | `blocked` | `SA12-13`, `SA12-14` | Installed-distribution evidence and public documentation | Wheel and sdist smokes pass; documentation names admitted, deferred, approximate, validation-only, and uncontrolled families |

The internal universe contract and rejection fixtures are recorded in the
[2026-10-22 preparation record](../docs/records/readiness-2026-10-22.md).
No conditional family or pack is admitted by that contract alone.

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

The first conditional calibration path accepts reviewed marital-status
vectors and separate private-household age denominators through normalized
CSV calibration. Fictional 2016 and 2021 inputs exercise the CLI from
preflight through realized residuals. The built-in packs use the verified CT sources and crosswalk below.
The published all-resident marital-status rows alone do not meet the
private-household universe requirement.

### Marital-status source review (2026-11-13)

Statistics Canada produced two private-household custom tabulations
distributed under its Open Licence by the University of Toronto. They cover
Canada, CMAs, tracted CAs and CTs using 25% Census sample data.

| Census | Deposit | File and revision | SHA-256 |
| --- | --- | --- | --- |
| 2016 | [Borealis CDKEOF](https://doi.org/10.5683/SP3/CDKEOF) | `EO3559_2016_Table2_Final.ivt`, 1.0, file 428828 | `2d4df7fcf4b77ba97f2c31c1438f02a07b7537f488651ef07c3aca798291b215` |
| 2021 | [Borealis UHEPKL](https://doi.org/10.5683/SP3/UHEPKL) | `EO3559_2021_Table1_Final.ivt`, 1.1, file 428826 | `01c2b85e3cd9dfb75dc41294fa5d31ba850fc4ae0956ca3933e6e08784e3331b` |

Both files matched the deposit MD5s. Inspection with `pyivt==0.0.8`
confirmed the same marital-status member codes in both. The official
[hierarchical PUMF archives](https://www150.statcan.gc.ca/n1/pub/98m0001x/)
supply the SAS formats for `MarStH` (2016) and `MARSTH` (2021).

| PUMF code | Category | IVT marital-status member codes |
| --- | --- | --- |
| 1 | Never married, not living common law | 6 |
| 2 | Married | 3 |
| 3 | Living common law | 4 |
| 4 | Separated, divorced or widowed, not living common law | 7 + 8 + 9 |

Use total household type, disability and sex or gender (member 1 on each).
Use the non-overlapping adult age members 3 and 6–15. Age member 2 gives
under-15 and member 1 gives all ages. Marital member 1 provides the independent
age totals. For PUMF age eligibility, `AGEGRP` 1–2 are under 15 and 3–13
are eligible. Age code 88 and eligible marital code 8 are unavailable.

For CT 4620053.00, the 2021 extract gives all ages 1,320, under-15 60,
and adult age totals 1,260. Its four adult marital categories are 595,
220, 250 and 160, summing to 1,225. The 2016 extract gives 1,095, 20
and 1,070 respectively, with categories 530, 160, 175 and 170 summing
to 1,035. These are unreconciled published counts. The CT packs preserve the source totals and record proportional
largest-remainder adjustments within base-five rounding bounds. Missing or
suppressed required cells stop the run before fitting. Resolve 2016 tract IDs through the IVT UID and
2021 tract IDs through the CT label, then verify each against the matching
Census geography. The built-in pack scope is CT. The deposits
provide no CSD, ADA or DA target vectors.

### Marital-status release acceptance

The bounded `1.2.0` scope is the 2016 and 2021 built-in census tract packs in
normalized CSV calibration. `geo calibrate` can combine either with the matching
broad CT pack. The broad evidence remains bound to its original 14 margins,
and the report records the conditional targets and their separate source
fingerprint. Prepared-control directories, the local web app, and other
geographies remain outside this acceptance. The joint CLI path also uses the
advanced file calibration API. Broader Python/CLI adoption and installed
distribution evidence remain open.

The [acceptance test](../tests/test_marital_status_controls.py) uses published
marital-status cells from Montréal tracts 4620053.00, 4620054.00 and 4620056.00
in both vintages. The linked candidate profiles, broad targets and companion
counts are fictional and constructed to agree with the reconciled conditional
totals. All nine household and five person margins pass broad-pack preflight
before the marital-status margin is added. The test recomputes each margin
from the exported weights and linked candidate profiles, then recounts it
from the output household and person CSVs. It checks household sizes and
person-to-household geography inheritance.

| Census | Tracts converged | Maximum fractional residual | Maximum realized residual |
| --- | --- | --- | --- |
| 2016 | 3 of 3 | < 0.000001 | 0 |
| 2021 | 3 of 3 | < 0.000001 | 0 |

For each vintage, suppression in a selected tract, an incompatible pack
vintage, a conflicting private-household person total, and a conflicting
under-15 target each fail before fit output is written. The test also exercises
the hierarchical age codes at the 15 and 65 boundaries while preserving the
frozen broad-pack crosswalk for existing callers.

A separate real-source screen compared the 2021 Montréal Profile age root
(ID 8) and private-household count (ID 56) to the marital extract all-ages
count. Of 316 tracts with equal Profile companion counts, 43 also matched
the marital count. Of those 43, eight had an identical reconciled under-15
target. The others fail joint preflight because the broad and marital
margins would require different child counts.

An empirical 2021 run selected three of those eight tracts from the
Montréal CLI-only workflow's normalized zero-collective controls and used
86,461 complete linked candidates from its 100,000-household model pool.
Whole households with unavailable required codes were excluded. The default
IPU solver at 100 iterations converged on zero of three tracts. A second run
used `--joint-solver hybrid --max-iterations 1000 --tolerance 0.01 --include-weights`. Its results were independently recomputed for each
margin from the weight file and the realized population files.

| 2021 tract | Hybrid fractional fit converged | Maximum fractional residual | Maximum realized residual |
| --- | --- | --- | --- |
| 4620252.00 | Yes | 0.000142 | 50 |
| 4620419.00 | No | 39.746812 | 54 |
| 4620626.00 | Yes | 0.002212 | 71 |

The 2016 run screened 970 Montréal tracts in the recovered Profile.
Of 205 with matching Profile total and private-household counts and
positive household counts, 33 also matched the marital all-ages count
and had complete broad and marital source cells. Three also matched the
under-15 target. All three ran with nine household, five person, and one
conditional marital-status margin. The preparation applied the reviewed
2016 registry crosswalk and proportional largest-remainder normalization
to the Profile household-size and private-household population anchors.
It preserved raw and normalized vectors and mapped the published male
and female counts to hierarchical PUMF SEX codes 2 and 1.

The candidate pool used `montreal-cma-2016-all-fields`, package
`v1.0.0-rights.1`, with 100,000 households and seed 20161113. Filtering
unavailable required fields by whole household left 89,176 candidates
with 181,542 people. IPU at 100 iterations and tolerance 0.01 converged
on zero of three tracts. The hybrid solver with up to 1,000 iterations
and the same tolerance converged on all three.

| 2016 tract | Hybrid max fractional residual, all margins | Max realized residual, all margins | Max realized marital residual |
| --- | --- | --- | --- |
| 4620221.00 | 0.000344 | 47 | 33 |
| 4620470.03 | 0.000135 | 48 | 37 |
| 4620625.02 | 0.001202 | 79 | 31 |

An independent tally reproduced all margin maxima from the exported weights
(to within 0.00001 of the report, allowing for CSV precision) and from the
realized CSVs (exactly). Linkage validation passed for 6,830 households and
18,743 people. The person target was 18,685. The run directory
`runs/marital-2016-acceptance-2026-11-13/` holds the source screen,
normalization evidence, CLI invocations, reports, and audit.

The empirical CT pass now covers both vintages. The exact denominator
checks govern admission, while the residuals show the separate limits of
whole-household realization. The wider `SA12-12` acceptance remains open
for its additional geographies and control families.

### Education source review (2026-11-13)

Accept the 2016 and 2021 Census Profile tract products as source candidates
for `SA12-05`, subject to the tract-level rules below. Both education panels
cover the population aged 15 and over in private households, using estimates
from the 25% sample. Use total sex or gender counts and the age-15+ panel.
[2016 Education Reference Guide](https://www12.statcan.gc.ca/census-recensement/2016/ref/guides/013/98-500-x2016013-eng.pdf) ·
[2021 Census Dictionary](https://www12.statcan.gc.ca/census-recensement/2021/ref/dict/98-301-x2021001-eng.pdf)

| Vintage | Tract Profile input | SHA-256 |
| --- | --- | --- |
| 2016 | `98-401-X2016043_eng_CSV.zip`, [Zenodo mirror](https://zenodo.org/records/15343658) | `c0113c58902368a77218fe7ae96ca477311cd8a6379a8eb9a257739839a9e8d6` |
| 2021 | `98-401-X2021007_eng_CSV.zip`, [Statistics Canada downloads](https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger.cfm?Lang=E) | `5d29811e5c3171cb16c9564bfbce0a08da45d1584810be2bd74764cbd2329ffc` |

The 2016 mirror matched its deposited MD5
`b7945a00205e2e251a175d3a3999d832`. For 2016 select `GEO_LEVEL=2` and use
the dotted tract identifier in `GEO_CODE (POR)`. For 2021 select
`GEO_LEVEL=Census tract` and use `ALT_GEO_CODE`, with the matching vintage
DGUID. Read the 2016 Total–Sex count or 2021 `C1_COUNT_TOTAL` and its
adjacent `SYMBOL`. Retain the product revision and tract vintage.

#### Education category crosswalk

The mapping uses disjoint Profile rows from the age-15+ panel and the
vintage-specific hierarchical PUMF `HDGREE` codes. Code 88 is unavailable,
and code 99 is not applicable. Classify children from age eligibility and
require one of codes 1–8 for eligible candidates. The trades categories have
different published definitions by vintage. Preserve those definitions in
reports. [Statistics Canada hierarchical PUMF](https://www150.statcan.gc.ca/n1/pub/98m0001x/)

| HDGREE | Category | 2016 Profile row | 2021 Profile row |
| --- | --- | --- | --- |
| 1 | No certificate, diploma or degree | 1684 | 1999 |
| 2 | Secondary diploma or equivalency | 1685 | 2000 |
| 3 | Other trades certificate or diploma | 1688, excluding apprenticeship or qualification certificates | 2004, non-apprenticeship trades |
| 4 | Apprenticeship or qualification certificate | 1689, apprenticeship or qualification | 2005, apprenticeship |
| 5 | College, CEGEP or other non-university credential | 1690 | 2006 |
| 6 | University certificate or diploma below bachelor level | 1691 | 2007 |
| 7 | Bachelor's degree | 1693 | 2009 |
| 8 | University credential above bachelor level | Sum of 1694–1697 | Sum of 2010–2013 |

#### Denominator and rounding rules

1. Anchor the adult vector to the education root (2016 row 1683, 2021 row
   1998). Cross-check it against the same-universe 25% income-statistics
   root (672 or 126). Require both counts and a difference of at most
   five. Every complete tract in the two archives met that bound. Require
   all three denominator rows to be observed nonnegative base-five integers.
1. Anchor the all-ages denominator to the same Profile's 25% private-household
   citizenship root (1135 or 1522). Require a positive all-ages count and
   `0 < education total <= all-ages total`. Derive the under-15 target by
   subtraction. Record that it is a derived calibration target. The 100%
   private-household counts (57 or 56) can differ materially from the 25%
   roots. Other independently sourced age targets, including the marital
   IVTs, must agree before any joint fit. Never clamp a negative child
   target or silently rescale between the short- and long-form universes.
1. Require the education root and all 11 disjoint leaves to be observed,
   nonnegative base-five integers. Their sum differed from the root by
   −30 to +25 in both vintages. Admit an absolute gap of at most 48
   (four people per published cell across 11 leaves and the root) as a
   conservative policy for these files. This is a calibration admission
   bound, not a guarantee about weighted-count error. Reject an all-zero
   vector with a positive root. Group the 11 leaves into eight categories
   before applying deterministic proportional largest remainder, with ties
   in code order. Preserve observed zeros and retain the raw leaves,
   published roots, derived counts, adjustments, and source hash in evidence.
1. Treat any unavailable required value as a tract exclusion during
   preparation and a preflight error if the tract was explicitly selected.
   Handle blank, absent, `x`, `..`, `...`, and `F` as unavailable, preserving
   the reason. For 2021 also inspect the count symbol. Reject malformed or
   duplicate cells. A numeric zero with a usable symbol is an observed
   rounded value. Do not reconstruct an unavailable cell from parent totals,
   other sex/gender columns, or another vintage.
   [2016 Census Guide](https://publications.gc.ca/collections/collection_2017/statcan/98-304-x/98-304-x2016001-eng.pdf) ·
   [2021 Profile rounding notes](https://www12.statcan.gc.ca/census-recensement/2021/as-sa/fogs-spg/Page.cfm?Dguid=2021A00034708&Lang=E&topic=9)

#### Tract evidence

| Vintage | Tracts scanned | Unavailable required counts | Complete tracts with adult total above all-ages total | Pass numeric source screen |
| --- | --- | --- | --- | --- |
| 2016 | 5,721 | 80 (73 `x`, 5 `..`, 2 `F`) | 56 | 5,585 |
| 2021 | 6,247 | 89 (blank counts with `x` symbols) | 1 | 6,157 |

These counts screen the source only. Candidate support, joint control
compatibility, and calibration residuals belong to the runtime acceptance.

| Vintage | Montréal CT | 25% all ages | Education 15+ | Companion 15+ | Derived under 15 | Raw eight-category vector in HDGREE order | Raw sum |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | 4620053.00 | 1,095 | 1,070 | 1,075 | 25 | 120, 145, 50, 10, 180, 80, 220, 265 | 1,070 |
| 2016 | 4620054.00 | 1,085 | 1,045 | 1,045 | 40 | 25, 145, 45, 30, 185, 55, 290, 275 | 1,050 |
| 2021 | 4620053.00 | 1,320 | 1,260 | 1,260 | 60 | 125, 175, 55, 20, 150, 90, 320, 320 | 1,255 |
| 2021 | 4620054.00 | 1,125 | 1,085 | 1,085 | 40 | 35, 155, 25, 20, 175, 60, 345, 260 | 1,075 |

Negative fixtures include 2016 CT 2050130.05 (`x`), 4620732.03 (`..`),
and 8600002.00 (`F`), and 2021 CT 9320010.00 (blank). Denominator
reversals include 2016 CT 3050015.01 (adult 40, all ages 0) and 2021 CT
5350376.06 (adult 280, all ages 275). In 55 of the 56 rejected 2016 tracts,
the citizenship root is zero even though the education root is positive.
The separate 25% private-household language root (872 in 2016, 1078 in
2021\) is at least as large as the education root in all complete tracts.
Keep the citizenship-based policy for compatibility with the existing broad
control. Admitting those tracts under the language root would require a
separate source decision. The recovered 2016 archive also supports the
separate marital-status broad-control acceptance work.

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

A completed calibration must enforce and record these postconditions:

- fractional convergence records whether the solver met the requested tolerance.
  A structurally valid output can be published with non-convergence and residuals
  explicitly reported against the retained targets;
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

The general phases below describe the reusable capability horizon, not an
alternative `1.2.0` task list. Their released portions are identified in the
baseline above; future collective, family, richer-profile, and national work
remains conditional until a later plan activates it.

## Phase 1 — Field/Control Compatibility Registry (Implemented, Extensible)

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

## Phase 2 — Source Screening For Extended Fields (Ongoing Research)

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

## Phase 3 — Universe Reconciliation (Baseline Implemented, Extension Active)

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

## Phase 4 — Versioned Control Packs (Baseline Implemented, Extension Active)

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

## Phase 5 — Feasibility Planner (Implemented, Extensible)

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

## Phase 6 — Household, Person, And Family Contributions (Family Deferred)

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

## Phase 7 — Validation And Claims (Implemented, Extensible)

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

## Phase 8 — Interfaces And Researcher Workflow (Implemented, Extensible)

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

## Phase 9 — Scale, Evidence, And Publication (Broader Work Conditional)

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
