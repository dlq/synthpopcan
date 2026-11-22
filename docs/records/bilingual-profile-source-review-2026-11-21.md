# Bilingual Census Profile Source Review — 2026-11-21

**Status: complete for the reviewed 2016 and 2021 tract formats.** Internet Archive captures provide complete original
French Profile CSV ZIPs for 2016 and 2021 tracts, 2016 metropolitan areas,
and 2021 provinces and territories. Bilingual IVT extracts and
English tract archives are also available. The verified tract files are supported
by the Profile preparation workflows; other French geography products require
their own evidence.

## Source Inventory And Access

| Vintage | Accessible English bulk archive | Accessible bilingual extract containing French and English |
| --- | --- | --- |
| 2016 | [`98-401-X2016043_eng_CSV.zip`](https://zenodo.org/records/15343658), 168,561,819 bytes, mirror MD5 `b7945a00205e2e251a175d3a3999d832`, SHA-256 `c0113c58902368a77218fe7ae96ca477311cd8a6379a8eb9a257739839a9e8d6` | [Université Laval Québec CMA/tract extract](https://www.bibl.ulaval.ca/geostat/recensements/r2016/donnees/2016-RMR-Quebec.ivt), 3,932,750 bytes, SHA-256 `3683ae54ca64ae8c08dbdc8c8f98a4329fb88aadc17f5384291896df9b6a5969` |
| 2021 | [`98-401-X2021007_eng_CSV.zip`](https://zenodo.org/records/15333781), 249,720,408 bytes, mirror MD5 `624589f4489e4c9a788e5f1eccd94e2c`, SHA-256 `5d29811e5c3171cb16c9564bfbce0a08da45d1584810be2bd74764cbd2329ffc` | [Université Laval Québec CMA/tract extract](https://www.bibl.ulaval.ca/geostat/recensements/r2021/donnees/RMR-Quebec.ivt), 8,890,293 bytes, SHA-256 `e067ef3d1f0ef9683b7b8fdf24f23573e0a34f3e5df03310176c17c33e817a1a` |

The local English archives' MD5 hashes match the checksums in the two Zenodo
records. This establishes a match to those deposited files, not independent
cryptographic authentication by Statistics Canada. For 2021 there is
additional provenance: the recorded November 2, 2026 direct browser download
from Statistics Canada is byte-identical to the Zenodo archive (SHA-256
`5d29811e5c3171cb16c9564bfbce0a08da45d1584810be2bd74764cbd2329ffc`).
The similarly named local `official-...` file was that browser download; this
is not an independent official checksum or a guarantee about current revisions.
No equivalent direct-download comparison has been established for 2016.
Université Laval describes
its [2016](https://www.bibl.ulaval.ca/services/ressources-et-services-specialises/centre-geostat/statistiques/recensements-du-canada/recensement-de-2016)
and [2021](https://www.bibl.ulaval.ca/services/ressources-et-services-specialises/centre-geostat/statistiques/recensements-du-canada/recensement-de-2021)
Québec files as extracts from the respective StatCan tract Profile products.
They are regional derivatives, not original bulk CSV downloads. The 2016 IVT
reports product ID `98-401-X2016043`; the 2021 IVT title identifies the tract
Profile but its decoded `product_id` is empty, so the university's catalogue
attribution and the bounded data comparison support, but do not prove, its
full identity. Statistics Canada's [2016 catalogue](https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X2016043)
and [2021 catalogue](https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X2021007)
identify the respective products.

On 2026-11-21, all four official tract CSV URLs returned HTTP 403 HTML from
this environment: [2016 English](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?FILETYPE=CSV&GEONO=043&Lang=E),
[2016 French](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?FILETYPE=CSV&GEONO=043&Lang=F),
[2021 English](https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/getFile.cfm?LANG=E&GEONO=007&FILETYPE=CSV),
and [2021 French](https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/getFile.cfm?LANG=F&GEONO=007&FILETYPE=CSV).
These observations do not establish a permanent restriction. The discovered
Zenodo archive lists contain English files only; French CSV mirrors remain to
be checked against the later archived sources described below.

## Original French Profile Archives Recovered

The Internet Archive has captured the official download endpoints. The
following complete ZIPs were retrieved and passed CRC checks on all members:

| Vintage and geography | Capture | SHA-256 |
| --- | --- | --- |
| 2016 CMA/CA, product `98-401-X2016041` | [October 2, 2020](https://web.archive.org/web/20201002014143id_/https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=F&FILETYPE=CSV&GEONO=041) | `f824d281aa727d3edd3ad627ceaaba6da49c86d0d3aee6402ad9014aac711dbb` |
| 2016 tracts, product `98-401-X2016043` | [September 21, 2022](https://web.archive.org/web/20220921235722id_/https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=F&FILETYPE=CSV&GEONO=043) | `cb4897be4b767e9a6e7e8ef80080cad920fc799825533dece1b351a4581cb738` |
| 2021 Canada/provinces/territories, product `98-401-X2021001` | [February 6, 2023](https://web.archive.org/web/20230206201007id_/https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=F&FILETYPE=CSV&GEONO=001) | `a014687c44606eaf805327104bd9a8c8cb5d5093309aa2a91a18bea366f0a57b` |
| 2021 tracts, product `98-401-X2021007` | [November 11, 2025](https://web.archive.org/web/20251111123600id_/https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/getFile.cfm?LANG=F&GEONO=007&FILETYPE=CSV) | `27b3ee4ee070f92571fe51605219b29b521658ae3573eeba49484fc9a5be2f2b` |

Each ZIP contains a French data CSV, metadata, geography index and README.
The 2016 data header has a UTF-8 BOM and decodes as UTF-8; the 2021 French
data header uses a single-byte encoding and the complete data member decodes
as Windows-1252. Decodability alone does not prove the publisher's declared
encoding or establish all vintage and geography variants. French field names,
members and labels differ substantially from English, e.g. `CODE_GÉO (LDR)`
in 2016 and `ID_CARACTÉRISTIQUE`, `C1_CHIFFRE_TOTAL` and repeated `SYMBOLE`
columns in 2021. Full headers and members are in the
[archive comparison record](bilingual-profile-archive-comparison-2026-11-21.json).

For equivalent English and French historical downloads at the same geography
levels, every sequential `(geography, characteristic ID)` key matched:
359,520 rows and 1,078,560 count/symbol fields in 2016, and 36,834 rows and
442,008 count/rate/symbol fields in 2021. English captures were February 23,
2020 and January 7, 2023 respectively; French captures were later, so the
comparisons do not prove all source releases were identical. Labels were not
tested for translation accuracy. These files and the comparison scripts are
in the local run directory; the original source is the archived official URL,
not independently signed by Statistics Canada.

For tract `4210001.01`, all 2,247 rows in the 2016 French ZIP and all 2,631
rows in the 2021 French ZIP match the equivalent English ZIP by characteristic
ID and every count/rate/symbol field. The 2021 French archive includes all
eight characteristics that were absent from the earlier Laval IVT. This is a
one-tract test, not proof of equality for every geography or release.

### Encoding And Suppression Review

The complete 2016 French tract data member was read as UTF-8 with BOM; all
12,965,190 CSV records decoded successfully. Its three count columns contain
inline `...` (2,413,123 cells), `x` (467,755), `..` (31,611), and `F`
(21,612). The complete 2021 French tract data member decoded as Windows-1252
and has six positional `SYMBOLE` fields alongside counts and rates. Across
those fields the observed markers are `...` (6,288,453), `x` (1,382,757),
`r` (1,014, including leading whitespace), and `..` (54). These are cell
counts, not distinct geographies. Metadata members can use different
encodings; a presentation language does not establish an encoding.

Built-in Profile preparation treats an inline non-numeric count, or a nonempty
symbol adjacent to a required 2021 count, as unavailable. This includes `r`,
which indicates revision rather than suppression; the conservative policy
requires review instead of silently treating a flagged count as unqualified.
Counts are not replaced with zero. Selected 2021 rows preserve each positional
symbol in the saved CSV. Generic control mapping with user-specified columns
remains a separate, caller-configured workflow.

Paired original tract slices and their provenance are recorded in
`tests/fixtures/census/README.md`. Regression tests exercise both languages,
both vintages, CSV and ZIP input, the three conditional Profile families,
household extraction, suppression and mixed ZIP rejection. Marital-status
packs use a separate reviewed private-household source, not this Profile CSV.

### Linked Calibration Acceptance

The previously recorded three-tract broad-plus-education workflows were rerun
using the complete French tract ZIP for each vintage, with the same candidate
populations, broad controls, evidence, hybrid solver and whole-household swaps.
In each vintage the resulting household, person and weight CSVs have the same
SHA-256 hashes as the earlier English run. Linkage validation passed for both:
6,670 households / 18,203 people in 2016 and 8,421 households / 18,448 people
in 2021. All three 2016 fractional fits converged; two of three 2021 fits
converged, matching the existing English baseline. Completion of the run does
not mean the non-converged tract achieved exact calibration. Logs and output
are retained under `runs/bilingual-profile-acceptance-2026-11-21/` and
`runs/bilingual-profile-{2016,2021}-acceptance.log`.

A July 17, 2019 [2016 French tract capture](https://web.archive.org/web/20190717134250id_/https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=F&FILETYPE=CSV&GEONO=043)
is truncated to 1 MiB, but its first compressed member yields the original
tract CSV header and complete initial rows. The 170 recovered commuting rows
(510 values) match a separate 2020 Parquet copy. This is not a complete ZIP,
so its CRC and remainder cannot be validated. An interrupted October 2020
tract download yields all 2,247 rows for tract `4210001.01`: commuting total
1,470, male 740 and female 735. All 2,247 rows' three count/symbol fields
match the corresponding English tract CSV. The file lacks the ZIP footer, so this is
provisional and cannot establish that earlier capture's full-archive integrity.
An interrupted February 2023 2021 tract capture did not yield that test tract;
the complete later capture above was subsequently verified instead.

## Observed Layouts And Paired Values

The original English archives contain a data CSV, metadata text, a geography
starting-row index, and a README. The 2016 CSV member is
`98-401-X2016043_English_CSV_data.csv`; its header begins with a UTF-8 BOM and
includes `GEO_CODE (POR)`, `GEO_LEVEL`, `Member ID: Profile of Census Tracts (2247)` and `Dim: Sex (3): Member ID: [1]: Total - Sex`. The 2021 CSV member
is `98-401-X2021007_English_CSV_data.csv`, with `DGUID`, `ALT_GEO_CODE`,
`GEO_LEVEL`, `CHARACTERISTIC_ID`, `C1_COUNT_TOTAL` and an adjacent `SYMBOL`.
The complete source-archive READMEs and metadata remain with the source files.
The sampled 2016 header and selected rows decode as UTF-8 with BOM; a 2021
archive row encountered while scanning (row 8,819,766) did not decode as
UTF-8, so whole-file encoding must not be inferred from these selected rows. The existing preparer uses
Latin-1; the publisher's declared encoding for French archives remains unverified.

Both archives' bundled READMEs describe the observed data, metadata and
geography-index members, and list the corresponding English CSV headers. Their
packaging and identifiers are consistent with comprehensive Profile downloads,
not a locally reshaped table. This does not authenticate the 2016 mirror or
prove which revision it contains, and says nothing definitive about the French
CSV layout. A Profile CSV and a regional bilingual IVT extract are different
products and should not be expected to have identical packaging.

The IVT files are bilingual tables, not two French and English CSVs. Using an
isolated `pyivt 0.0.11` environment, decode the English and French member labels
and the single shared numeric table. In the Québec tract `4210001.01`, eight
count rows per year and their English labels matched the source CSV independently. The full
labels, native characteristic IDs, IVT member positions, and compared values
are recorded in [paired rows](bilingual-profile-paired-rows-2026-11-21.json).
Examples:

| Vintage | Profile row | English / French label | English CSV = IVT count |
| --- | --- | --- | --- |
| 2016 | 51 | Private households by household size / Ménages privés selon la taille du ménage | 2,840 |
| 2016 | 1683 | Highest certificate, diploma or degree, age 15+ / Plus haut certificat, diplôme ou grade, 15 ans et plus | 4,005 |
| 2021 | 50 | Private households by household size / Ménages privés selon la taille du ménage | 2,760 |
| 2021 | 1998 | Highest certificate, diploma or degree, age 15+ / Plus haut certificat, diplôme ou grade, 15 ans et plus | 4,025 |

The shorter labels in this table identify the concepts; the paired-row record
retains the full labels and their private-household and sample-universe wording.
The same tract code in different vintages does **not** prove unchanged
boundaries. The 2021 IVT metadata includes `2021S05074210001.01`, English
`Census tract` and French `Secteur de recensement`; the 2016 IVT has a dotted
`UID/IDU` of `4210001.01`. IVT member positions are one-based *table positions*,
not assumed to be source geographic or characteristic codes. Use the native
codes and vintage-specific definitions.

A subsequent comparison covered every characteristic in the tract, using the
total-sex or total-gender count and matching native characteristic IDs. The
[machine-readable comparison](bilingual-profile-tract-comparison-2026-11-21.json)
records the counts and exceptions:

- **2016:** all 2,247 characteristic IDs were present in both sources; 2,246
  numeric counts matched. Row 1925, the commuting-destination total, was
  **1,470** in the English CSV and **1,475** in the IVT. Both sources report
  740 male and 735 female. The IVT download has a 2017-11-30 HTTP
  last-modified date, while the English ZIP member has a 2018-02-09 archive
  timestamp. The commuting correction and expanded comparison discussed below
  suggest a possible source-revision difference; the exact cause remains unproven.
- **2021:** the English CSV contains 2,631 characteristic IDs; the IVT
  contains the first 2,623. Of those shared IDs, 2,620 numeric values matched
  and three were unavailable in both; each corresponding CSV symbol was
  `...`. IDs 2624–2631 appear in the CSV but not the IVT; 2624 concerns
  eligibility for minority-official-language instruction. Release timing
  supports an earlier-snapshot explanation, as discussed below, but the
  precise source revision remains unverified.

## Follow-Up: Release Timing And 2016 Commuting Differences

The initial single-tract comparison was expanded for 2016 Profile row 1925 and
11 other selected characteristics, across the Québec CMA and 181 tract
geographies in the Laval extract. Total, male and female values were compared
where numeric. For row 1925, **119 of 182 geographies** differ in at least one
of the three cells; 47 differ in the total. Across all 546 cells, 161 differ,
each by exactly five. The five commuting-destination rows 1925–1929 also show
many differences, including some larger than five, while the selected
neighbouring rows 1922–1924 and 1930, the education total 1683, and available
cells of rows 1 and 51 match across all 182 geographies. The
[comparison summary](bilingual-profile-2016-commute-comparison-2026-11-21.json)
records the counts and source checksums; the detailed geography-level results
and scripts remain in the local run directory.

Statistics Canada published a [December 6, 2017 correction notice](https://www150.statcan.gc.ca/n1/en/catalogue/98-400-X2016329)
for a **separate data-table product** concerning the same 2016 commuting
variable, explaining that some residence-to-workplace links had been computed
incorrectly. The Laval IVT's HTTP last-modified date is November 30, 2017,
and the English CSV ZIP member timestamp is February 9, 2018. The subject,
concentrated differences and chronology make a related source revision a
plausible hypothesis. The notice does not identify these Profile files, and
file timestamps do not establish their content revision.

The [2016 Census Profile catalogue correction record](https://www150.statcan.gc.ca/n1/en/catalogue/98-316-X2016001)
lists corrections for language data, immigrant birthplace sex labels,
forward-sortation-area geography and ethnic-origin labels; it does **not**
list a commuting correction. The specific [tract download catalogue record](https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X2016043)
also lists no correction. Those records do not establish that no unlisted
revision occurred, but they do not confirm the proposed connection. The IVT
has not been independently decoded. Neither the correction nor the available
timestamps establish which file's values are authoritative. Preserve the
separate source identities and seek an independently dated Profile revision or
confirmation from Statistics Canada before using the IVT as an oracle.

An independently hosted, transformed English tract Profile appears in a
[GitHub commit dated July 17, 2020](https://github.com/haleemur/ca_census_2016/commit/f9f48077e4973e840be4d32fd8fc17cba342b928).
The retrieved Parquet data's Git blob matches that commit, and its SHA-256 is
`57c29dda1696b060d41403dde5d4645a41fd822cab4db66de1977fde1b4e9770`.
For all 161 row-1925 sex/total cells where our English CSV and Laval IVT
disagree, this copy agrees with the English CSV. This establishes the English
values are consistent with that date, though Git commit dates alone are not
independent timestamps and do not authenticate or date the source revision.
The partial October 2020 Internet Archive capture independently supports their
availability by that capture date for the selected tract, with
the integrity limitation described above. The separate independent 2019
partial French tract capture agrees with the 2020 derivative for its first
170 commuting rows, but those rows cover other geographies, not this Québec
tract. None of these comparisons proves the cause of the earlier IVT
differences or demonstrates that the December 2017 correction applied to the
Profile.

For the **2021** eight-characteristic gap, the CSV labels for IDs 2624–2631
all concern eligibility for or instruction in the minority official language.
Statistics Canada stated on November 30, 2022 that [Profile results on this
topic would be available December 15](https://www150.statcan.gc.ca/n1/daily-quotidien/221130/dq221130d-eng.htm).
The Laval IVT has an HTTP last-modified date of December 9, 2022. The topic
and timing strongly support an earlier Profile snapshot as the explanation
for the missing rows, but the file timestamp is not proof of its source data
revision. The later English CSV contains all eight; neither a missing IVT row
nor its absence in this release establishes a zero or suppression.

These comparisons use a university derivative, an English CSV and a
third-party IVT decoder. The 2021 comparison covers one tract; the expanded
2016 comparison covers selected characteristics and geographies. Neither is a
cross-language CSV comparison or evidence that all releases are interchangeable.
Preserve the discrepancy and missing IDs in any proposed fixtures and source
selection.

For the population row, the English CSV has `...` for male/female counts and
the IVT decoder returns null for those cells. Both IVT missing-value legends
include `...` (not applicable), `x` (confidential), and `F` (too unreliable),
but a nullable IVT value alone does not distinguish their causes. Neither this
observation alone verifies the French CSV's symbol columns, numeric formatting,
or suppression handling. Never infer zeros or
replace symbols from the translated labels.

## Local Evidence And Next Steps

The downloaded extracts, original English row slices, comparison script and
machine-readable results (including `compare-all.py` and `all-characteristics-check.json`) are under `runs/bilingual-profile-source-review-2026-11-21/`.
The small English slices are aggregate-only excerpts preserving the original
CSV bytes and headers; their SHA-256 values are
`5dba624e0e150bc95b6f35f07a24ddc3e55d5c35dd9ad8dcdcb3a4e203e4de90`
(2016) and `826aa75c778c935a41accf8ece864cb803edad7c7c93ec83f3cdd0f38b37001c`
(2021). The derived bilingual record is not an original French CSV fixture.
The temporary IVT reader is a research tool, not a SynthPopCan dependency;
its decoding should be checked against another independent reader before using
it as the only correctness oracle.

Additional searches of GitHub, Zenodo and the public Borealis catalogue did
not find complete original French tract CSVs; the Internet Archive later provided
the captures above. One accessible Borealis 2016 Profile
archive contained an English CSV ZIP and a bilingual IVT, not a French CSV.
The [Open Government Portal's 2021 catalogue](https://open.canada.ca/data/dataset/750e6035-adf8-4426-966f-4c25b12a999e)
lists French Profile CSV resources, but that listing alone is not a locally
verified file. A normal in-app browser visit to the official 2021 French
download page on November 21 remained at the browser-validation page; no
French file was obtained in that attempt. Search-indexed copies and catalogues
are leads, not proof of an original file's bytes or contents.

Review additional French geography products and source revisions independently
before claiming them supported. Do not alter existing source files or silently
equate a presentation locale with a download language.
