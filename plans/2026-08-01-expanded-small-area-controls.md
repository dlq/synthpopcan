# Expanded Small-Area Controls Plan

Status: active feature implementation; `1.1.0` released and `1.2.0` committed\
Created: 2026-08-01\
Last updated: 2026-11-14\
Target: `1.1.0` broad compatible packs; conditional person controls in `1.2.0`\
Next action: complete installed-distribution and release evidence for the accepted scope\
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
| `SA12-05` | `in progress` | `SA12-01`, accepted `SA12-04`, `SA12-10` | Education preparer, registry entry, and pack component | Normalized controls validate and round-trip; not-applicable and unmapped categories remain explicit |
| `SA12-06` | `done` | Pinned 2016 and 2021 Profile definitions | Labour-force-status source decision and crosswalk | Categories, age denominator, vintage differences, suppression rules, and fixture totals reproduce independently |
| `SA12-07` | `in progress` | `SA12-01`, accepted `SA12-06`, `SA12-10` | Labour-force preparer, registry entry, and pack component | Normalized controls validate and round-trip; support, zero, and universe failures stop before fitting |
| `SA12-08` | `done` | Pinned 2016 and 2021 Profile definitions | Work-activity source decision and crosswalk | Full/part-year and full/part-time categories, applicability, suppression, and fixture totals reproduce independently |
| `SA12-09` | `in progress` | `SA12-01`, accepted `SA12-08`, `SA12-10` | Work-activity preparer, registry entry, and pack component | Normalized controls validate and round-trip; mutually exclusive states and denominators are enforced |
| `SA12-10` | `done` | `SA12-01` | Shared conditional-person reconciliation and preflight path | The common implementation represents not-applicable states or explicit conditional constraints without silently manufacturing totals; adversarial cases fail closed |
| `SA12-11` | `done` | `SA12-10` and at least one accepted family runtime slice | Separately versioned conditional-person pack tier | Manifests have stable identifiers, semantic checksums, inspectable contents, and fail-closed compatibility with the retained broad packs |
| `SA12-12` | `done` | `SA12-11` | Joint bounded feasibility and calibration evidence | Reviewed 2016/2021 CT and CSD cases have direct-source joint evidence; non-tract proxy cases and missing 2016 ADA evidence are explicitly qualified or deferred below. Fractional and realized residuals are independently recomputed for the recorded fits |
| `SA12-13` | `done` | `SA12-12` | Python and CLI adoption through the shared workflow | Equivalent library and command requests normalize identically; public-interface and machine-output fixtures remain additive |
| `SA12-14` | `done` | `SA12-12` | Local-web and durable-run adoption through the shared workflow | HTTP normalization, progress events, run evidence, interruption restart, and browser scenarios match the accepted pack semantics |
| `SA12-15` | `ready` | `SA12-13`, `SA12-14` | Installed-distribution evidence and public documentation | Wheel and sdist smokes pass; documentation names admitted, deferred, approximate, validation-only, and uncontrolled families |

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
whole-household realization. Subsequent joint acceptance and its bounded
non-tract decisions are recorded below.

#### Whole-household integerization experiment

Systematic midpoint rounding preserves the rounded household weight total.
It selects households by cumulative weight in candidate order and does not
use their contributions to the individual control cells. In 20 fixed-seed
permutations per tract, the median maximum marital-status residual ranged
from 28 to 53.5 people. Changing candidate order alone left substantial error.

A prototype started from the same midpoint allocations and swapped one
household at a time among candidates with positive fractional weights. Each
swap reduced the unweighted sum of squared residuals across all control
cells. The search stopped at 100 swaps or when its shortlist offered no
improvement. It retained the starting household count in every tract.

| Census | Tract | Max marital residual before → after | Max residual across all cells before → after |
| --- | --- | --- | --- |
| 2016 | 4620221.00 | 33 → 1 | 47 → 4 |
| 2016 | 4620470.03 | 37 → 1 | 48 → 2 |
| 2016 | 4620625.02 | 31 → 1 | 79 → 5 |
| 2021 | 4620252.00 | 50 → 1 | 50 → 2 |
| 2021 | 4620419.00 | 29 → 1 | 54 → 22 |
| 2021 | 4620626.00 | 71 → 2 | 71 → 7 |

Both realized populations passed linkage validation. The prototype reused
the exported fractional weights, so the previously nonconverged 2021 fit
retains its original convergence status. The local experiment and outputs
are under `runs/marital-integerization-2026-11-13/`. The CLI exposes the swap method through `geo calibrate --integerization swap`
for linked normalized CSV controls. Midpoint remains the default.

Rerunning both workflows through the CLI reproduced the prototype's
marital-status residuals. The CLI's maximum across all cells for 2021 tract
4620419.00 was 21 rather than 22 in the prototype. Both CLI outputs passed
linkage validation. The 2016 run realized 6,830 households and 18,679 people
(six below the person target), and the 2021 run realized 6,756 households and
17,606 people (one above the person target). Fractional convergence stayed
at three of three and two of three, respectively. The CLI invocations and
validation reports are in the same local run directory.

#### Toronto joint-fit diagnosis and rerun

The 2021 Toronto run combined all 17 broad and conditional margins.
A nonnegative linear feasibility check with structural zeros found an
exact fit for the housing margins alone in every tract. The original
complete-case pool had one six-person household and no seven-person
households, down from 4,954 households of those sizes before filtering.
When the person controls were added, the minimum sum of absolute cell
residuals was 70, 216.5, and 127.5, respectively. The available household
sizes could not supply the target person totals at the published
household-size distribution.

A local candidate-pool experiment retained the original complete households.
It added 11,889 large candidates using complete synthetic person draws from
the same Toronto model's province, household-size, and tenure groups. This
changes the candidate distribution and assumes exchangeability of complete
draws within those groups. The published targets and structural zeros
were retained. The augmented pool had an exact fractional feasibility
witness for every tract.

| 2021 CT | Max fractional residual before → after | Max realized residual before → after |
| --- | --- | --- |
| 5350403.09 | 36.907 → 0.000332 | 22 → 4 |
| 5350411.18 | 109.150 → 0.000315 | 57 → 3 |
| 5350412.26 | 64.746 → 0.000006 | 36 → 4 |

All three converged fractionally with the hybrid solver. The swap output
passed linkage validation for 6,180 households and 22,059 people against
a target of 22,060 people. The audit independently recounted the three
conditional margins and matched integer weights to realized households.
Scripts and results are in
`runs/joint-conditional-2026-11-13/toronto-diagnosis/`. This experiment
uses local candidate preparation. The model generator and CLI are unchanged.

#### Multi-region joint evidence and B.C. sensitivity runs

All 23 tracts from the two-vintage denominator screen ran with the 14 broad
and three conditional margins and whole-household swaps. The original pools
were jointly feasible in 10 tracts. Augmentation restored feasibility in 11
more. Selected fits converged in 9 of 9 tracts in 2016 and 12 of 14 in 2021.
All selected outputs passed linked validation.

The remaining B.C. cases had different size bounds. For CT 9350156.05,
the normalized size margin required at least 238 people against a target
of 230. For CT 9350180.05, the candidate model could accommodate at most
106 people against a target of 110. Targeted resampling improved joint
support for the latter, while its size bound still prevented an exact fit.
The linked CLI now rejects these two bound violations and identifies
whether to review targets or expand candidate support.

The sensitivity runs kept the published inputs separately. For 9350156.05,
two households moved from 5+ to size 1 in the normalized target. For
9350180.05, one household moved from size 1 to 5+, using the targeted
provincial pool. Both adjusted cases converged fractionally and passed
linkage validation. Their maximum realized cell residuals were two and
four, respectively. These fits establish feasibility for the adjusted
targets. The 23-tract original-target acceptance count remains 21 of 23.
The scripts, reports, and audits are in the local
`runs/joint-23-2026-11-13/` directory.

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

#### Education tract implementation and fit evidence

The built-in 2016 and 2021 packs read the matching tract Profile ZIP or CSV
through `geo calibrate --education-pack ... --education-profile ...`.
The joint path validates broad evidence before appending the conditional
margin and rejects disagreement on the all-ages or under-15 target.

The Montréal runs used published education rows and all nine household
and five person broad margins. Three eligible tracts per vintage ran with
the hybrid solver at tolerance 0.01. Both integerization methods were
checked against the same inputs.

| Census | Tracts | Fractional convergence | Max realized education residual, midpoint → swap | Max realized residual across all controls, midpoint → swap |
| --- | --- | --- | --- | --- |
| 2016 | 4620470.03, 4620625.02, 4620638.01 | 3 of 3 | 56 → 1 | 114 → 9 |
| 2021 | 4620221.00, 4620638.04, 4620643.03 | 2 of 3 | 40 → 2 | 53 → 25 |

All four outputs passed linkage validation. The audit matched the integer
weights to realized households and independently recounted education
residuals. The 2021 tract 4620221.00 remained fractionally nonconverged.
Local commands, outputs, and audit are under
`runs/education-acceptance-2026-11-13/`.

### Labour-force status source review (2026-11-13)

Use the same checksum-pinned 2016 and 2021 Census Profile CT archives and
tract identifiers documented in the education source review. Labour-force
status covers private-household residents aged 15 and over in the 25% sample.
The reference weeks were May 1–7, 2016 and May 2–8, 2021. Annual work
activity has a separate reference period, documented in the
[work-activity source review](#work-activity-source-review-2026-11-13).
[2016 Labour Reference Guide](https://publications.gc.ca/collections/collection_2017/statcan/98-500-x/98-500-x2016012-eng.pdf) ·
[2021 Labour Reference Guide](https://www12.statcan.gc.ca/census-recensement/2021/ref/98-500/012/98-500-x2021012-eng.pdf)

| Category | 2016 Profile row | 2021 Profile row | 2016 `LFTAG` / 2021 `LFACT` |
| --- | --- | --- | --- |
| Employed | 1867 | 2225 | 1–2 |
| Unemployed | 1868 | 2226 | 3–10 |
| Not in the labour force | 1869 | 2227 | 11–14 |

The code ranges match across vintages. Codes 11–13 use vintage-specific
last-worked years, which the aggregate category combines. For hierarchical
PUMF candidates, `AGEGRP` codes 1–2 give the under-15 state. Codes 3–13
require a labour code 1–14. Reject unknown ages and unavailable or unmapped
adult labour codes, including 99 (not applicable). The in-labour-force
subtotal (1866/2224) overlaps employed and unemployed. Use the three disjoint
count rows in the table, omitting the subtotal and rate rows from the fit.
[Hierarchical PUMF codebooks](https://www150.statcan.gc.ca/n1/pub/98m0001x/)

1. Anchor the eligible vector to the labour-status root (1865/2223).
   Cross-check it against the 25% private-household age-15+ education
   root (1683/1998) and income-statistics root (672/126). Require each
   companion to be within five people of the labour root. Every complete
   tract met both bounds. Use the all-ages 25% citizenship root (1135/1522)
   as the private-household anchor. Require a positive labour root no larger
   than the all-ages anchor and derive the under-15 target by subtraction.
   The 100% Profile counts belong to a separate denominator.
1. Require exact agreement with the all-ages and under-15 targets of
   any other controls in a joint fit. For instance, 2016 CT 4620053.00
   gives an under-15 target of 20 from labour and 25 from education.
   Of the tracts passing the labour source screen, 3,743 in 2016 and
   6,008 in 2021 also had an exact match to the education age target.
1. Require all roots and leaves to be observed nonnegative base-five
   integers. Allow an absolute discrepancy up to 16 between the three
   leaves and the labour root, a conservative allowance of four per
   published cell. Reject a zero-sum vector against a positive root.
   Reconcile by proportional largest remainder in table order and retain
   observed zeros, published counts, derived targets, and the archive hash.
   The observed leaf-sum-minus-root range was −15 to +15 in 2016 and
   −15 to +10 in 2021.
1. Exclude a tract with an absent, blank, suppressed, unreliable, or
   malformed required cell and fail preflight if it was explicitly
   selected. Reject duplicate required rows. Read the 2016 total-sex
   count or the 2021 total count and adjacent symbol. Preserve the reason
   and distinguish numeric zero from unavailable data. Never reconstruct
   suppressed counts from the subtotal or companion roots.

| Census | Tracts scanned | Unavailable required counts | Impossible adult/all-ages counts | Passed source screen |
| --- | --- | --- | --- | --- |
| 2016 | 5,721 | 80 (73 `x`, 5 `..`, 2 `F`) | 57 | 5,584 |
| 2021 | 6,247 | 89 (blank with `x`) | 1 | 6,157 |

| Census | Montréal CT | All ages | Labour 15+ | Derived under 15 | Published employed / unemployed / outside labour force | Reconciled vector |
| --- | --- | --- | --- | --- | --- | --- |
| 2016 | 4620053.00 | 1,095 | 1,075 | 20 | 635 / 45 / 395 | 635 / 45 / 395 |
| 2016 | 4620056.00 | 1,500 | 1,410 | 90 | 645 / 65 / 705 | 643 / 65 / 702 |
| 2021 | 4620053.00 | 1,320 | 1,260 | 60 | 740 / 65 / 455 | 740 / 65 / 455 |
| 2021 | 4620056.00 | 1,920 | 1,805 | 115 | 960 / 90 / 755 | 960 / 90 / 755 |

Rejection fixtures include 2016 CT 2050130.05 (suppressed) and 3050015.01
(labour root 40, citizenship root 0), and 2021 CT 9320010.00 (suppressed)
and 5350376.06 (labour root 280, citizenship root 275). These are source
checks. Candidate support and fit evidence belong to `SA12-07` and the
subsequent joint acceptance.

#### Labour-force tract implementation and fit evidence

The built-in 2016 and 2021 labour-force status packs accept the matching
tract Profile ZIP or CSV via `geo calibrate --labour-force-pack ... --labour-force-profile ...`.
Both reuse the conditional Profile validation path and check exact
all-ages and under-15 agreement before joint calibration.

Three Montréal tracts per vintage used published labour-force and broad
controls with the hybrid solver at tolerance 0.01. The midpoint and swap
runs used the same controls and candidate pools.

| Census | Tracts | Fractional convergence | Max realized labour residual, midpoint → swap | Max realized residual across all controls, midpoint → swap |
| --- | --- | --- | --- | --- |
| 2016 | 4620470.03, 4620500.00, 4620625.02 | 2 of 3 | 61 → 2 | 93 → 9 |
| 2021 | 4620221.00, 4620638.04, 4620643.03 | 3 of 3 | 61 → 1 | 70 → 5 |

All four outputs passed linkage validation. The audit matched exported
integer weights to realized households and independently recounted the
labour-force residuals. The 2016 tract 4620500.00 remained fractionally
nonconverged. Commands and results are in the local directory
`runs/labour-acceptance-2026-11-13/`.

### Work-activity source review (2026-11-13)

Use the checksum-pinned 2016 and 2021 Census Profile CT archives and vintage
tract identifiers documented in the education source review. Both roots
cover residents aged 15 and over in private households (25% long-form
sample). The 2016 Census measures work for pay or in self-employment in
calendar year 2015. The 2021 Census measures calendar year 2020, which
includes pandemic disruptions. Full-year full-time means 49–52 weeks,
mostly at least 30 hours per week. Labour-force status measures a separate
May reference week.
[2016 work-activity definition](https://www23.statcan.gc.ca/imdb/p2SV.pl?DECId=244099&DFId=244177&Function=assembleDESurv&Id=152274&RepClass=591&db=IMDB) ·
[2021 Census Dictionary](https://www12.statcan.gc.ca/census-recensement/2021/ref/dict/98-301-x2021001-eng.pdf) ·
[2021 Labour Reference Guide](https://www12.statcan.gc.ca/census-recensement/2021/ref/98-500/012/98-500-x2021012-eng.pdf)

| Category | 2016 Profile row | 2021 Profile row | Hierarchical PUMF `WRKACT` (both vintages) |
| --- | --- | --- | --- |
| Did not work in the reference year | 1874 | 2232 | 1–2 |
| Worked full year, full time | 1876 | 2234 | 11 |
| Worked part year and/or part time | 1877 | 2235 | 3–10, 12 |

Code 1 covers those who worked before the reference year or never worked.
Code 2 covers those who worked in the Census year but did not work in the
reference year. Codes 3–10 cover 1–48 weeks and code 12 covers 49–52 weeks
mostly part time. Use `AGEGRP` 1–2 for the under-15 state and require a
mapped `WRKACT` code for `AGEGRP` 3–13. Reject unknown ages and unmapped
adult codes, including 99 (not applicable). `WRKACT` is sufficient for this
crosswalk. Omit the worked subtotal (1875/2233) and the average weeks row
(1878/2236) from the margin.
[Hierarchical PUMF codebooks](https://www150.statcan.gc.ca/n1/pub/98m0001x/)

1. Anchor the adult vector to the work-activity root (1873/2231). Require
   each companion 25% age-15+ root to be within five of it: education
   (1683/1998), labour-force status (1865/2223), and income statistics
   (672/126). Every complete tract met this check. Require a positive
   adult root no larger than the 25% all-ages citizenship root
   (1135/1522) and derive the under-15 target by subtraction. The 100%
   population counts use a separate denominator.
1. Require exact agreement on all-ages and under-15 targets when
   combining controls. Independent rounding can pass the source check
   and still fail joint preflight. In 2021 CT 4620053.00 the work-activity
   root is 1,265, while education and labour-force status both use 1,260.
1. Require observed nonnegative base-five integers for all roots and
   leaves. With independently rounded cells, allow an absolute gap of
   at most 16 between the leaf sum and its root (four per cell). Reject
   an all-zero vector against a positive root. Reconcile eligible
   vectors by proportional largest remainder in table order. Retain
   numeric zeros, raw counts, reconciled targets, and archive provenance.
1. Exclude tracts with a required count that is absent, blank,
   suppressed, unreliable, or malformed. Fail preflight for explicitly
   selected excluded tracts and report the missing or invalid row.
   Reject duplicate required rows. Read the 2016 total-sex count or the
   2021 total count and its adjacent symbol. Treat `x`, `..`, `...`,
   and `F` as unavailable when present. Preserve numeric zero and leave
   unavailable cells unresolved even when a subtotal could imply a value.

| Census | Tracts scanned | Unavailable required counts | Invalid adult/all-ages counts | Outside rounding envelope | Passed source screen |
| --- | --- | --- | --- | --- | --- |
| 2016 | 5,721 | 80 (73 `x`, 5 `..`, 2 `F`) | 56 | 0 | 5,585 |
| 2021 | 6,247 | 89 (blank with `x`) | 3 | 1 | 6,154 |

The published leaf sum minus the adult root ranged from −15 to +15 in
2016 and −20 to +15 in 2021. CT 8350018.00 in 2021 published an adult root
of 40 and leaves of 20 / 0 / 0. Its −20 gap exceeds the allowance and
the source screen excludes it. Suppression fixtures are 2016 CT
2050130.05 and 2021 CT 9320010.00. Invalid denominator fixtures include
2016 CT 3050015.01 (adult 40, all ages 0) and 2021 CT 5220015.00
(adult 55, all ages 50).

| Census | CT | All ages | Work activity 15+ | Derived under 15 | Published leaves in table order | Reconciled leaves |
| --- | --- | --- | --- | --- | --- | --- |
| 2016 | 4620053.00 | 1,095 | 1,070 | 25 | 395 / 345 / 335 | 393 / 343 / 334 |
| 2016 | 4620054.00 | 1,085 | 1,045 | 40 | 175 / 485 / 385 | 175 / 485 / 385 |
| 2021 | 4620053.00 | 1,320 | 1,265 | 55 | 520 / 425 / 315 | 522 / 427 / 316 |
| 2021 | 4620054.00 | 1,125 | 1,085 | 40 | 285 / 390 / 410 | 285 / 390 / 410 |

These counts establish source eligibility. Candidate support, normalized
pack validation, and fit evidence belong to `SA12-09` and joint acceptance.
The local archive scan is recorded in
`runs/work-activity-source-review-2026-11-13/`.

#### Work-activity tract implementation and fit evidence

Both built-in work-activity packs accept the matching tract Profile ZIP
or English CSV via `geo calibrate --work-activity-pack ... --work-activity-profile ...`.
The shared conditional Profile reader checks the work-activity denominator
against education, labour-force status, and income before enforcing exact
all-ages and under-15 agreement with other selected controls.

Both vintages used published broad controls, the same candidate pools for
each midpoint/swap comparison, and the hybrid solver at tolerance 0.01.

| Census | Montréal tracts | Fractional convergence | Max realized work-activity residual, midpoint → swap | Max realized residual across all controls, midpoint → swap |
| --- | --- | --- | --- | --- |
| 2016 | 4620470.03, 4620625.02 | 2 of 2 | 41 → 1 | 69 → 9 |
| 2021 | 4620221.00, 4620638.04 | 2 of 2 | 92 → 1 | 103 → 10 |

All four outputs passed linkage validation. The audit independently
classified exported people from `AGEGRP` and `WRKACT`, recomputed the
work-activity residuals, and matched exported weights to realized
household multiplicities. The 2016 tract 4620500.00 failed broad
preflight because its household-size counts require at least 925 people
and its person target is 920. The 2021 tract 4620643.03 was screened out
for a different work-activity under-15 target. Commands, screens, and
reports are in `runs/work-activity-acceptance-2026-11-13/`.

#### Five-family joint tract acceptance (2026-11-13)

At `3c0ce08`, the matching broad pack and the marital-status, education,
labour-force status, and work-activity add-ons ran together for 18 margins.
Six tracts from the earlier joint cohort were selected for compatible
published all-ages and under-15 targets. Montréal and Saskatchewan reused
the original candidate pools, and Toronto reused the previously augmented
pool. The fits used the pinned Profile ZIPs, the hybrid solver at tolerance
0.01 with a 1,000-iteration cap, and whole-household swaps.

All six tracts had zero joint feasibility slack and converged fractionally.
The largest fractional residual was 0.000189 or less in 2016 and 0.002281
or less in 2021. All three batches passed linkage validation. The audit
recounted the realized margins from exported records and verified that
integer weights matched realized household multiplicities.

| Census | Tract | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- | --- |
| 2016 | 4620470.03 | 5 | 1 | 1 | 1 | 1 |
| 2016 | 4620625.02 | 8 | 1 | 2 | 0 | 0 |
| 2021 | 7250105.00 | 5 | 0 | 0 | 0 | 0 |
| 2021 | 5350403.09 | 6 | 1 | 1 | 1 | 1 |
| 2021 | 5350411.18 | 8 | 1 | 1 | 1 | 1 |
| 2021 | 5350804.01 | 3 | 1 | 1 | 1 | 1 |

Each value is the largest absolute count error within that family after
swaps. This evidence covers the six selected tracts. Reproduction commands,
per-tract fractional residuals, and output audits are in the local run
directory `runs/joint-five-2026-11-13/`.

#### Five-family cohort extension (2026-11-13)

At `fc5bd33`, the remaining 17 tracts in the 23-tract cohort were
screened against the published work-activity targets and the existing
joint controls. Twelve had compatible denominators. The feasibility
screen reused each tract's previously selected pool and required zero
summed absolute residual across all 18 margins, within a numerical
tolerance of 1e-7. Ten passed, bringing the five-family acceptance
sample to 16 of 23 tracts.

The ten new fits used the same hybrid solver, tolerance, iteration cap,
and whole-household swap settings as the initial six. All converged.
The largest fractional residuals were 0.005133 or less in 2016 and
0.001479 or less in 2021. All five output batches passed linkage
validation. The audit recounted all 18 realized margins and checked
exported integer weights against household multiplicities.

| Census | Tract | Pool | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | 5350346.02 | augmented | 5 | 2 | 1 | 1 | 1 |
| 2016 | 5350484.03 | original | 5 | 1 | 1 | 2 | 1 |
| 2016 | 5350516.03 | original | 7 | 1 | 1 | 1 | 1 |
| 2016 | 5350516.09 | original | 4 | 1 | 1 | 1 | 1 |
| 2016 | 5350600.01 | original | 5 | 2 | 0 | 1 | 0 |
| 2021 | 5370066.00 | augmented | 7 | 1 | 1 | 1 | 1 |
| 2021 | 5590043.02 | original | 5 | 2 | 1 | 0 | 0 |
| 2021 | 9330147.07 | augmented | 5 | 2 | 1 | 1 | 1 |
| 2021 | 9330227.02 | augmented | 1 | 1 | 1 | 1 | 1 |
| 2021 | 9380014.00 | augmented | 7 | 1 | 1 | 1 | 1 |

Values are the largest absolute count errors after swaps in each family.

Five tracts shared the same all-ages target but differed by five in their
published age-15+ totals. The resulting under-15 targets are incompatible
in a joint fit. The source targets were preserved.

| Census | Tract | Age 15+ in other controls | Age 15+ in work activity |
| --- | --- | --- | --- |
| 2016 | 5350484.04 | 755 | 750 |
| 2016 | 5350516.47 | 3,960 | 3,965 |
| 2021 | 4080120.05 | 1,130 | 1,135 |
| 2021 | 5350412.26 | 4,805 | 4,810 |
| 2021 | 9330011.00 | 6,045 | 6,040 |

Two 2021 B.C. tracts passed the denominator check and failed joint
feasibility with the unchanged targets. For 9350156.05, the normalized
household-size targets require at least 238 people, while its person
target is 230. Its previously selected original pool had a minimum summed
absolute residual of 4.00. For 9350180.05, the previously selected
augmented pool had a minimum summed absolute residual of 31.34772946
across the 18 margins. The earlier B.C. diagnosis identified limited
candidate capacity in the largest household-size category. Both tracts
were excluded before fitting.

Reproduction commands, full residuals, and screening evidence are in
the local run directory `runs/joint-five-extension-2026-11-13/`.

#### Conditional pack verification and first ADA pilot (2026-11-14)

The eight built-in tract definitions have pinned semantic hashes. Tests
verify CLI display and export, canonical hash recomputation, and compatibility
with the matching broad CT definition for each vintage. All eight reject ADA
geography and the same-vintage core CT pack. The CLI preflight tests also
reject invalid targets before calling the fitter.

The first non-tract pilot screened 135 Québec ADAs with existing broad
private-household targets from the zero-collective cohort. Twenty-one
had observed education, labour-force status, and work-activity counts
with matching all-ages and under-15 targets. The pilot used the published
ADA Profile archive and applied the reviewed 2021 Profile category
mappings and rounding checks to its ADA rows.
[Statistics Canada ADA Profile](https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X2021012)

The first three compatible ADAs by identifier passed the zero-slack
feasibility screen with whole linked household candidates and structural
zeros. They were fit together using explicit normalized controls with
14 broad and three conditional margins, the hybrid solver at tolerance
0.01, and whole-household swaps. The audit independently recalculated
fractional and realized residuals and matched exported integer weights
to household multiplicities. The maximum fractional residual was
0.00002412 or less, all three fits converged, and linkage validation passed.

| 2021 Québec ADA | Broad | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- |
| 24100003 | 19 | 1 | 1 | 1 |
| 24230011 | 5 | 0 | 0 | 0 |
| 24250012 | 2 | 1 | 1 | 1 |

Each value is the largest absolute count error for that family after
swaps. The ADA pilot uses explicit normalized targets. The built-in
conditional pack definitions have CT geography. The reviewed marital-status
source covers CT, so the ADA pilot has no marital-status margin. The
subsequent acceptance work reviewed non-tract marital-status sources and
extended the cases to 2016 and to CSD and DA. The local
run directory `runs/nontract-acceptance-2026-11-14/` records the inputs,
screening, CLI invocation, and audit.

#### Non-tract marital-status source review (2026-11-14)

The 2021 table 98-10-0129-01 publishes marital status by age for CSDs
and DAs. Its universe is the 100% population aged 15 and over, including
residents of collective dwellings. The corresponding 2016 CSD and DA
marital-status table also uses the 100% population. The existing broad
conditional-person controls use 25% private-household denominators.
These published vectors require a documented universe and rounding
reconciliation before use in a joint fit.
[2021 table 98-10-0129-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?geocode=A000248&pid=9810012901) ·
[2021 family reference guide](https://www12.statcan.gc.ca/census-recensement/2021/ref/98-500/002/98-500-x2021002-eng.pdf)

The 2016 table 98-400-X2016029 covers people aged 15 and over in
private households at CSD level, but classifies family characteristics
rather than the complete four-category marital-status vector. Its
100% universe also needs an explicit comparison with the 25% Profile
controls. It is a source candidate for further review.
[2016 table 98-400-X2016029](https://www150.statcan.gc.ca/n1/en/catalogue/98-400-X2016029)

The 2016 and 2021 CSD/DA Profile archives were recovered from mirrors
and checked against their published MD5 checksums. The experimental
reconciliation and selected fits are recorded below.

#### Five-family ADA reconciliation experiment (2026-11-14)

The accessible [Zenodo 2016 Profile mirror](https://zenodo.org/records/15343658)
includes the CSD and DA archive. For a first reconciliation experiment,
the existing 2021 Québec ADA inputs were screened for equality of the
published 100% total-population and private-household counts and for
exact equality of the 100% marital-status adult root and the 25%
education adult root. These equalities are an observed screening
condition. Published counts are rounded and do not establish exact
underlying population equality. The two Census universes remain distinct.

The 100% marital-status leaves were mapped to never married and not
living common law, married, living common law, and separated/divorced/
widowed and not living common law. Complete observed base-five cells
and a conservative rounding envelope were required. Their 100% category
counts were proportionally reconciled to the common published adult
total by largest remainder, preserving source values and numeric zero.
These are experimental proxy targets for the 25% conditional controls.
The source does not directly establish the 25% marital distribution.

Three selected ADAs passed zero-slack feasibility with 18 margins.
Using the hybrid solver at tolerance 0.01, all three fractional fits
converged. Linked validation passed. Independent audit recomputed
fractional and realized errors and checked exported weights against
household multiplicities.

| 2021 Québec ADA | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- |
| 24230011 | 6 | 1 | 1 | 1 | 1 |
| 24250012 | 2 | 1 | 1 | 1 | 1 |
| 24580034 | 5 | 1 | 1 | 1 | 1 |

Values are maximum absolute count errors after whole-household swaps.
This proxy experiment does not admit a non-tract marital-status pack.
Inputs, source cells, preflight, CLI commands, and audit are in
`runs/nontract-five-2026-11-14/` and
`runs/nontract-acceptance-2026-11-14/`.

#### CSD and DA proxy fits (2026-11-14)

The 2016 `98-401-X2016044_eng_CSV.zip` archive has SHA-256
`0e1c72f4be0a97cdf72994181186479c2347f0d755465145ea91db095cc2a8ac`.
The 2021 `98-401-X2021006_eng_CSV.zip` archive has SHA-256
`f133d818d5078f3d4a6c68e3568653f4a1aab5e5e98b316723bd4b1ce0055c6d`.
Both match the published mirror MD5s.
[2016 archive](https://zenodo.org/records/15343658) ·
[2021 archive](https://zenodo.org/records/15333781)

The screening requires equal published 100% total-population and
private-household counts. It allows the 25% private-household all-ages
root and age-15+ root to differ from their corresponding 100% roots by
at most five. The conditional 25% families must agree on the adult
target and the normalized broad age margin must agree on children.
Suppressed required cells and vectors outside rounding bounds are
excluded. The published 100% marital-status categories are normalized
by proportional largest remainder to the 25% adult target. The
resulting marital-status targets are an approximate proxy, because
equal rounded counts do not establish exact universe equality or
the marital distribution of the 25% sample.

Selected cases were screened by linear programming with structural
zeros. Only zero-slack cases ran the hybrid solver with tolerance 0.01
and whole-household swaps. All six selected cases below converged and
passed linkage validation. An independent audit recalculated fractional
and realized errors and matched integer weights to realized household
multiplicities.

| Census | Geography | Identifier | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2016 | DA | 24180079 | 7 | 1 | 1 | 1 | 1 |
| 2016 | DA | 24370090 | 2 | 1 | 1 | 1 | 1 |
| 2021 | CSD | 2457030 | 9 | 1 | 1 | 1 | 1 |
| 2021 | CSD | 2467055 | 3 | 1 | 1 | 1 | 1 |
| 2021 | CSD | 2471075 | 4 | 1 | 1 | 1 | 1 |
| 2021 | DA | 24210077 | 2 | 0 | 0 | 1 | 0 |

Values are maximum absolute count errors after swaps by family.
Candidate pools were generated for Québec. The 2016 DA fits used an
augmented pool. The 2016 CSD 2434115 passed the source screen but its
household-size targets require at least 1,145 people against the
person target of 1,140. The original and augmented pools each produced
a minimum joint L1 residual of 2.5, so it was not fit. Other screened
cases with positive feasibility residuals were excluded.

The source review and proxy reconciliation advance `SA12-12`. A directly
sourced private-household distribution for DA and ADA remains outstanding. The
experimental source extracts, feasibility scripts, fit reports, and
audits are in `runs/nontract-2016-2026-11-14/` and
`runs/nontract-2021-2026-11-14/`.

#### 2016 CSD conflict and alternate fit (2026-11-14)

For CSD 2434115, the published 100% household-size cells are
135 / 215 / 70 / 55 / 30, totaling 505 households. Even at five people
per household in the last category, they require 1,145 people. The
published 100% private-household count is 1,145 and the 25%
private-household target is 1,140. These published and normalized
targets were preserved. The 2.5 minimum joint L1 residual applies to
the entire constraint system with the tested pool.

An expanded national scan examined 5,162 CSDs. Twenty-six passed the
source and denominator screen. Among two Ontario CSDs screened against
the existing augmented Toronto candidate pool, Cramahe (3514014) had
zero joint feasibility slack. The other had minimum L1 11. The Cramahe
fit used the same 18 margins, approximate 100% marital-status proxy,
hybrid tolerance 0.01, and whole-household swaps as the non-tract
experiment. It converged fractionally. The largest fractional error
reported was 0.000125 or less. Independent auditing verified the
realized residuals, linked output, and household weights.

| 2016 CSD | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- |
| 3514014 | 6 | 1 | 1 | 1 | 1 |

Values are maximum absolute count errors after swaps. The CSD output
contains 2,565 households and 6,356 people. Reproduction inputs,
feasibility evidence, reports, and the independent audit are retained
in `runs/nontract-2016-csd-expanded-2026-11-14/`.

#### Direct private-household CSD marital-status reruns (2026-11-14)

Two public 25% private-household sources provide the four marital
categories at CSD level. The 2016 source is the Québec English-Speaking
Communities Research Network (QUESCREN) portal's copy of Statistics
Canada table 98-400-X2016352. Its IVT SHA-256 is
`0384feb1b2e94e0f1aaa12ecc28333481f58e7db0af844f49f9d484ee629ebfd`.
The 2021 source is QUESCREN's copy of custom table CO-2613, table 1.
Its IVT SHA-256 is
`f7aab7fbc2cb8d994a0bbcfc965aafa98ed59f0e24ac4bf5b0b7953b8a43508d`.
[2016 table](https://www150.statcan.gc.ca/n1/en/catalogue/98-400-X2016352) ·
[2021 custom dataset](https://desq.quescren.ca/en/dataset/pch-2021-co-2613-table1)

Both extracts select total first official language spoken and total
sex or gender. The source categories map to never married and not
living common law, married, living common law, and separated/divorced/
widowed and not living common law. Published categories are preserved.
When independent rounding produces a total difference, proportional
largest remainder reconciles the vector to the existing 25% adult target.

| Census | CSD | Published adult total | Published leaves | Reconciled leaves |
| --- | --- | --- | --- | --- |
| 2016 | 3514014 | 5,435 | 1,160 / 2,810 / 730 / 735 | 1,160 / 2,810 / 730 / 735 |
| 2021 | 2457030 | 6,850 | 1,725 / 2,075 / 2,380 / 670 | 1,726 / 2,077 / 2,382 / 670 |
| 2021 | 2467055 | 1,995 | 475 / 705 / 585 / 240 | 473 / 701 / 582 / 239 |
| 2021 | 2471075 | 1,585 | 445 / 600 / 325 / 210 | 446 / 602 / 326 / 211 |

The 2021 adult target for 2457030 is 6,855, five above its published
root. The other targets equal their published roots. All four joint
18-margin systems had zero minimum L1 feasibility slack. All fractional
fits converged at tolerance 0.01 and all linked outputs passed
validation. An independent audit recounted fractional and realized
margins and checked integer weights against household multiplicities.

| Census | CSD | Broad | Marital status | Education | Labour-force status | Work activity |
| --- | --- | --- | --- | --- | --- | --- |
| 2016 | 3514014 | 4 | 2 | 1 | 1 | 2 |
| 2021 | 2457030 | 3 | 1 | 1 | 1 | 1 |
| 2021 | 2467055 | 8 | 1 | 1 | 1 | 1 |
| 2021 | 2471075 | 5 | 1 | 1 | 1 | 1 |

Values are maximum absolute count residuals after whole-household
swaps. The 2016 fit reused the augmented Toronto candidate pool and the
2021 fits reused the Québec pool. The source file, selected cells,
inputs, reports, and audits are retained in
`runs/private-marital-source-2026-11-14/`. The 2016 IVT exceeded
pyivt's default 2 GiB memory estimate. Its targeted extraction used
a locally built pyivt 0.0.10 with an 8 GiB estimate limit.

These CSD reruns supersede the earlier proxy fits for these four CSDs.
The sources reviewed here do not supply the earlier DA or ADA cases.
Those cases retain their approximate proxy evidence pending a directly
sourced private-household distribution at those geographies.

The project retains support for both 2016 and 2021. The unverified DA and
ADA marital-status distribution is a geography- and control-specific gap in
both vintages, not a reason to remove 2016 support. The 2016 DA cases
24180079 and 24370090, 2021 DA 24210077, and 2021 ADAs 24230011,
24250012, and 24580034 use the approximate all-resident proxy described
above. Their reported residuals are against those derived proxy targets;
they do not establish fit to directly observed private-household marital
counts. No 2016 ADA marital-status fit is claimed here. The directly
sourced CSD reruns above supersede their earlier proxy results; the built-in
marital-status packs remain tract-only.

#### DA and ADA private-household source search (2026-11-14)

The Community Data Program (CDP) lists a Statistics Canada
[2021 target-group profile of people in owner and renter households](https://communitydata.ca/data/target-group-profile-population-living-owner-and-renter-households-census-2021).
Its catalogue identifies marital status and both DA and ADA geography;
the profile uses the 25% sample. This is a promising direct source,
but the catalogue does not establish the actual category crosswalk,
coverage, suppression, or whether the owner and renter selections also
provide a private-household total. These must be checked in the file.
CDP says that [downloading requires an activated member account](https://communitydata.ca/content/welcome-community-data-program-0).
The file was not available for this review, so it was not used in a fit.

CDP also lists a [2016 age-group target profile](https://www.donneescommunautaires.ca/data/target-group-profile-population-age-groups-census-2016)
with an all-ages selection and ADA geography. It is a candidate for
investigation, not yet a verified marital-status source: its catalogue
does not identify the actual marital-status rows, DA coverage, or the
universe and suppression of the needed cells. The 2016 household and
family profile for owner and renter households is not evidence of
person-level marital-status counts.

Before rerunning either vintage, inspect the licensed files and their
terms, verify geography identifiers, the private-household adult universe,
marital categories and suppressed values, then reconcile independently
rounded totals and run feasibility checks. The existing DA and ADA
proxy results remain unchanged; no new direct-source fits are claimed.

#### SA12-12 bounded joint-evidence decision (2026-11-14)

SA12-12 is complete as a bounded evidence review. The original goal of
direct five-family evidence at every CT, CSD, DA, and ADA level in both
vintages is narrowed explicitly: unsupported geography/control combinations
are deferred, rather than being treated as accepted or preventing the
remaining interface work. Both Census vintages remain supported.

| Vintage and geography | Decision | Evidence and limit |
| --- | --- | --- |
| 2016 and 2021 CT | Accepted for the reviewed five-family cases | 16 of the 23-tract cohort passed the source and feasibility screens and converged with all 18 margins. Seven were excluded: five for incompatible adult denominators and two for joint infeasibility. The audited realized residuals and fractional errors are recorded above. |
| 2016 CSD | Accepted for the reviewed direct-source case | CSD 3514014 converged with all 18 margins and directly sourced, reconciled private-household marital categories; audit and residuals are recorded above. |
| 2021 CSD | Accepted for the reviewed direct-source cases | CSDs 2457030, 2467055, and 2471075 converged with all 18 margins and directly sourced, reconciled private-household marital categories. These reruns supersede their proxy fits. |
| 2016 and 2021 DA | Approximate research evidence only | DAs 24180079 and 24370090 in 2016 and 24210077 in 2021 converged against all 18 targets, but their marital targets are derived from all-resident rows. Residuals measure fit to those proxies. Direct private-household marital evidence is deferred. |
| 2021 ADA | Accepted for the reviewed three-conditional-family pilot; five-family evidence is approximate | ADAs 24100003, 24230011, and 24250012 used direct Profile controls for education, labour-force status, and work activity without marital status. ADAs 24230011, 24250012, and 24580034 additionally have five-family proxy fits, whose marital residuals are against approximate targets. |
| 2016 ADA | Deferred | No five-family ADA fit or directly verified DA/ADA private-household marital distribution is recorded for this vintage. |

The accepted entries cover only the named cases and methods, not every
geography or candidate pool. All selected fits recorded above passed the
stated feasibility screen, converged fractionally at the stated tolerance,
and had independently checked realized margins and linkage. Fractional
convergence and realized whole-household errors are separate claims. Raw
published cells, reconciliation, exclusions, pool choice, and residuals
remain part of each run's evidence. No targets are changed to make an
excluded case appear feasible.

This decision accepts statistical evidence, not a universal runtime or
release claim. The eight built-in conditional packs remain CT-only; the
non-tract studies used explicit normalized controls. `SA12-03`, `SA12-05`,
`SA12-07`, and `SA12-09` remain open for their individual implementation
acceptance, and `SA12-13` through `SA12-15` remain necessary before release.

#### Python, CLI, and local-web adoption in progress (2026-11-14)

The beginner `calibrate_small_area` API and `geo synthesize` accept the
conditional inputs already supported by `geo calibrate`. The local-web
preflight validates the selected tract packs and source CSVs, retains them
as checksummed durable inputs, and reports source and compatibility errors.
The worker forwards selections and realization options and records a CLI
reproduction command. Joint synthetic fixture tests exercise all four
conditional families together for both vintages, audit saved inputs, and
replay the command; source mismatches fail before fitting. The browser form
requires the reviewed broad pack, evidence, and person controls.

SA12-13 and SA12-14 use a fresh restart rather than resuming a partial fit.
The app marks unfinished runs interrupted, verifies retained inputs and model
identity, copies them into a new run, rechecks preflight, and publishes the
new queued run atomically. The original run and partial artifacts remain
unchanged. Failure and tampering tests cover rejection and cleanup; the new
manifest records its parent. An unseeded generation can differ after restart.
The web upload accepts marital-status CSVs and Profile CSVs or ZIPs within
its 256 MiB limit; the CLI remains available for larger sources. Installed
distribution and final release evidence remain in `SA12-15`.

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
