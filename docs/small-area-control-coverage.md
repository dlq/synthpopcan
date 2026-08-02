# Small-Area Control Coverage Inventory

Status: source-availability screen, 2026-08-01\
Census vintages: 2016 and 2021\
Geographies: census subdivision (CSD), census tract (CT), aggregate
dissemination area (ADA), and dissemination area (DA)

This inventory asks which public Census Profile families could constrain the
fields emitted by the corresponding all-fields linked model. It is deliberately
broader than the current `geo controls` implementation, which builds only
household-size and tenure margins.

## Answer At A Glance

The all-fields linked output has **36 substantive modeled fields** after
excluding identifiers, province (the model condition), repeated linkage
context, and the derived `household_size_group` helper.

- **29 of 36 fields** have a candidate control based on published Profile
  counts. Some are exact; most require coarsening, banding, component
  derivation, or an explicit universe restriction.
- **2 more fields** (`PRESMORTG` and `SUBSIDY`) could be approximated from a
  published denominator and rounded percentage. They are not count-quality
  controls and should remain a separate, lower-confidence tier.
- **5 fields** have no matching count distribution in the Profile: `VALUE`,
  `SHELCO`, `FCOND`, `HRSWRK`, and `WKSWRK`.

Thus, the defensible source ceiling is **29/36 fields (80.6%)** using
count-based candidates, or **31/36 fields (86.1%)** only if the two
percentage-derived approximations are accepted. This is a ceiling, not the
number implemented today and not evidence that all 29 crosswalks are ready.

## Geography Coverage

The audit counts a geography when the family root has a numeric, positive
denominator. It does not treat an empty, zero, missing, or suppressed universe
as usable. “Family range” shows the least and greatest geography coverage among
the 23 count-based control families. Percentage-derived mortgage and subsidy
are reported separately because their published percentages are rounded.

| Vintage | Level | Profile geographies | Positive population | Count-based family range | Mortgage | Subsidy |
|---|---:|---:|---:|---:|---:|---:|
| 2016 | CSD | 5,162 | 4,869 | 3,027–4,585 | 3,903 | 3,112 |
| 2016 | CT | 5,721 | 5,686 | 5,571–5,645 | 5,554 | 5,540 |
| 2016 | ADA | 5,386 | 5,121 | 4,231–4,920 | 4,274 | 4,265 |
| 2016 | DA | 56,590 | 55,548 | 49,834–55,003 | 53,156 | 41,959 |
| 2021 | CSD | 4,173 | 3,869 | 2,240–3,608 | 2,945 | 2,270 |
| 2021 | CT | 6,247 | 6,211 | 6,100–6,165 | 6,074 | 6,059 |
| 2021 | ADA | 5,433 | 5,158 | 4,443–4,963 | 4,321 | 4,315 |
| 2021 | DA | 57,936 | 56,686 | 50,085–56,158 | 54,304 | 44,194 |

The lower end is usually the immigrant-only place-of-birth universe; in 2021
CTs it is instead the published employment- and total-income universe. The
upper end is generally the broad age/sex-or-gender or marital-status universe.
The table reports geographies present in each Profile product, not the number
of boundary features in the geographic framework.

The 2016 DA Profile contains 56,590 unique level-4 identifiers, while the
official boundary file used by this workspace contains 56,589. Identifier
`35510090` is the sole Profile-only record. A boundary-linked workflow must
treat it as unavailable unless that source discrepancy is resolved; the
maximum immediately mappable 2016 DA universe is therefore 56,589.

CSD, ADA, and DA are national geography systems. CT is not: it covers tracted
census metropolitan areas and census agglomerations. A high percentage within
the CT product therefore does not imply wall-to-wall Canadian coverage.

## Candidate Control Families

Profile characteristic IDs are stable only within a census vintage. A root ID
identifies the family whose child rows must be mapped and reconciled before the
control is implemented.

| Model field(s) | Candidate treatment | 2016 root | 2021 root | Main qualification |
|---|---|---:|---:|---|
| `household_size` | direct/coarsened | 51 | 50 | Top-code generated size at 5+. |
| `TENUR` | coarsened | 1617 | 1414 | Combine renter with band/local-government/First Nation housing. |
| `DTYPE` | coarsened | 41 | 41 | Review vintage-specific dwelling categories. |
| `ROOM` | coarsened | 1630 | 1427 | Profile groups 1–4 rooms and top-codes 8+. |
| `BEDRM` | coarsened | 1624 | 1421 | Profile top-codes 4+. |
| `CONDO` | direct | 1621 | 1418 | Occupied-private-dwelling universe. |
| `REPAIR` | direct | 1651 | 1449 | Regular versus major repairs. |
| `BUILT` | coarsened | 1643 | 1440 | Review vintage construction-period bands. |
| `NOS` | direct | 1640 | 1437 | Suitable versus not suitable housing. |
| `AGEGRP` + sex/gender | joint/coarsened | 8 | 8 | Cross broad age rows with Profile sex/gender columns. |
| marital status | coarsened | 59 | 58 | Shared population aged 15+ universe. |
| `CITIZEN` | coarsened | 1135 | 1522 | Review multiple-citizenship categories. |
| `IMMSTAT` | coarsened | 1140 | 1527 | Keep status distinct from immigration period. |
| `GENSTAT` | direct | 1278 | 1665 | First, second, third-or-later generation. |
| `POB` | conditional/coarsened | 1157 | 1544 | Immigrant-only detail; combine with immigration status. |
| `VISMIN` | coarsened | 1323 | 1683 | Review vintage-specific categories and terminology. |
| three mother-tongue indicators | derived components | 112 | 393 | Preserve multiple responses. |
| three home-language indicators | derived components | 381 | 735 | Preserve multiple responses. |
| `HDGREE` | coarsened | 1683 | 1998 | Population aged 15+ universe. |
| labour-force status | coarsened | 1865 | 2223 | Population aged 15+ universe. |
| `EMPIN` | banded | 724 | 187 | Bin numeric generated income to Profile groups. |
| `FPTWK` + `WRKACT` | coarsened | 1873 | 2231 | Did not work, full-year/full-time, or other work. |
| `TOTINC` | banded | 691 | 155 | Bin numeric generated income to Profile groups. |
| `PRESMORTG` | rounded-percentage approximation | 1671 + 1672 | 1482 + 1483 | Derive approximate counts among owners. |
| `SUBSIDY` | rounded-percentage approximation | 1678 + 1679 | 1490 + 1491 | Derive approximate counts among tenants. |

The paired labels above account for census-vintage name changes, including
`SEX`/`GENDER`, `MarStH`/`MARSTH`, `LFTAG`/`LFACT`, and the language component
names. They represent one modeled concept per output vintage, not additional
fields.

## Fields Without A Matching Profile Distribution

| Field | Why it is not a current control candidate |
|---|---|
| `VALUE` | The Profile publishes median/average dwelling value, not a count distribution matching the generated field. |
| `SHELCO` | It publishes cost summaries and affordability ratios, not matching shelter-cost bands. |
| `FCOND` | It does not publish a condominium-fee count distribution. |
| `HRSWRK` | It does not publish a matching hours-worked count distribution. |
| `WKSWRK` | It publishes average weeks worked, not a matching distribution. |

These fields may still be useful model outputs. Without another reviewed
source, however, they remain candidate-pool estimates and must not be described
as locally calibrated.

## What This Audit Does And Does Not Establish

This is a **source-availability screen**. It establishes that a potentially
compatible Profile family is published and measures the number of geographies
with a positive root universe. It does not yet establish:

- an exact, reviewed mapping of every Profile child category to every PUMF
  category;
- internally complete child vectors after suppression and rounding;
- compatibility among multiple household and person margins;
- candidate support for rare categories at each target geography;
- convergence, integerized residuals, or the effect of controls on linked
  households; or
- that a broad provincial or national model is fit for a particular local
  research question.

Before implementation, each family needs a vintage-specific crosswalk,
universe and suppression policy, fixtures, independent reconciliation, and
coverage/residual reporting. Person controls must continue to change whole
household weights rather than detach people from households.

## Recommended Implementation Order

1. Add broad age-by-sex/gender person controls. They cover two important fields
   jointly and use the strongest population universe.
2. Expand household controls to dwelling type, bedrooms, rooms, repair,
   construction period, housing suitability, and condominium status.
3. Add reviewed immigration, citizenship, generation, visible-minority,
   language, education, labour-force, work-activity, and income-band
   crosswalks, with explicit universe handling.
4. Consider mortgage and subsidy only as an opt-in approximate tier with
   rounding provenance and a reconciliation tolerance.
5. Leave the five unsupported fields explicitly uncontrolled unless another
   authoritative, geography-compatible source is adopted.

## Sources And Reproduction

The input is Statistics Canada's English 2016 and 2021 Census Profile bulk CSV
products for CSD, CT, ADA, and DA. The audit used the source URLs recorded in
the local provenance manifests; the 2016 DA `GEONO=044` product was streamed
without retaining the multi-gigabyte raw file.

Run the local inventory with:

```bash
uv run python scripts/audit_small_area_control_coverage.py
```

The script emits JSON containing the field classifications, vintage-specific
root IDs, geography totals, positive-population totals, and positive-denominator
counts for every candidate family. It uses `rg` as an optional fast prefilter
for local multi-gigabyte CSVs and falls back to a Python streaming scan. Missing
conventional inputs are listed under `missing_profiles`; they are never silently
represented as zero coverage. The table above supplements the local run with a
streamed audit of the official 2016 DA product because that raw CSV is not kept
in the working data cache.
