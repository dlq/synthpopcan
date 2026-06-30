# Statistics Canada Sources

SynthPopCan can fetch two kinds of public Statistics Canada sources: tables
from the **Web Data Service (WDS)**, which is the API behind the CANSIM table
inventory, and the **Census Profile**, a bulk download that gives hundreds of
demographic characteristics for each census geography. Both sources are fetched
over the network directly from Statistics Canada's public servers. If a server
is unavailable or a URL changes, the command fails — treat downloaded files as
worth keeping locally so you do not need to re-fetch them.

Downloading a file is only the first step. The fetched files are raw — wide
format, Statistics Canada labels, characteristic codes — and cannot be used as
controls directly. After downloading, use {doc}`controls` to inspect, map
categories, and normalize before fitting.

## Concept

**WDS tables** are the general-purpose source. The CANSIM inventory contains
thousands of tables covering demographics, income, housing, labour, and more.
Each table has a stable product ID (e.g. `98100001`) that you use to fetch,
explain, and download it. WDS tables come as CSV ZIPs in a wide format; the
columns and category labels vary by table.

**Census Profile** is a specific bulk product from the decennial census. It
gives several hundred demographic characteristics for every geographic unit at
a chosen level — census tract, dissemination area, province, and others. It
is the primary source for small-area controls because it reports counts at the
census tract level that are not available from WDS. The download is large and
the file uses Statistics Canada's characteristic-row format, which requires
inspection and mapping before normalization.

A note on categories: Statistics Canada tables use their own category
definitions for age groups, household types, dwelling types, income bands, and
geography levels. These definitions are not universal — they reflect specific
administrative and methodological choices, and they change between census years.
When you map a Statistics Canada category to a control dimension, you are
adopting that definition. If your research question uses a different conception
of the same variable, the mismatch should be documented, not papered over.

The workflow is the same for both sources:

1. Find the source (search WDS or choose a Census Profile geography level).
1. Inspect it to confirm it has the dimensions and categories you need.
1. Normalize only the dimensions relevant to your research question.
1. Check compatibility with the seed before fitting.

Step 3 and 4 are covered in {doc}`controls`.

Statistics Canada tables are official aggregate sources, but the work of
choosing dimensions, geographies, and category mappings belongs to the
researcher. A table that is appropriate for one geography or population
universe may be misleading for another.

## Getting Started

The WDS workflow starts with a keyword search to find a product ID, then a
quick metadata check before committing to a full download:

```bash
synthpopcan statcan wds search "population dwelling" --limit 10
```

```bash
synthpopcan statcan wds explain 98100001
```

```bash
synthpopcan statcan wds fetch 98100001 \
  --lang en \
  --out-dir data/raw/statcan/wds
```

After download, inspect the ZIP to see what columns and category labels it
contains before normalizing:

```bash
synthpopcan controls wds inspect data/raw/statcan/wds/98100001-eng.zip
```

The Census Profile workflow is simpler — there is no search step, just choose
the geography level and year:

```bash
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ct \
  --out-dir data/raw/statcan/census-profile/2016
```

Normalization for both source types is covered in {doc}`controls`.

## Subcommands

### `statcan wds search`

Searches the WDS table inventory by keyword against table titles and
descriptions. Returns a list of matching tables with their product IDs and
titles. The inventory is large; use specific terms (a characteristic name, a
census year, a geography keyword) and cap results with `--limit` until you find
a plausible candidate. Take the product ID to `statcan wds explain` before
downloading.

```bash
synthpopcan statcan wds search "age sex population"
synthpopcan statcan wds search "age sex population" --limit 20 --format json
```

Options:

- `--limit INTEGER`: maximum number of results to return.
- `--format table|tsv|json`: output format; `json` is useful for scripting.

### `statcan wds explain`

Summarizes the metadata for a product ID in human-readable form: the table
title, geographic coverage, available dimensions (e.g. Age group, Sex, Tenure
type), category labels within each dimension, and the approximate row count.
Run this before `statcan wds fetch` to confirm the table has the variables you
need, covers the right geography, and is not impractically large. A table with
millions of rows may be better accessed through a more targeted WDS query or
a Census Profile instead.

```bash
synthpopcan statcan wds explain 98100001
synthpopcan statcan wds explain 98100001 --format json
```

### `statcan wds fetch`

Downloads the full table as a CSV ZIP to the specified output directory. The
ZIP filename follows Statistics Canada's convention: `PRODUCT_ID-eng.zip` for
English or `PRODUCT_ID-fra.zip` for French. Large tables can be several hundred
megabytes — check the row count in `explain` first. Keep the downloaded ZIP;
Statistics Canada URLs can change, and re-downloading is not always possible.
After downloading, pass the ZIP to `controls wds inspect` to see its columns
and category labels before normalizing.

```bash
synthpopcan statcan wds fetch 98100001 \
  --lang en \
  --out-dir data/raw/statcan/wds
```

Options:

- `--lang en|fr`: language of the downloaded CSV (affects column headers and category labels).
- `--out-dir PATH`: directory to write the ZIP into.

### `statcan wds metadata`

Fetches the raw API metadata JSON for a product ID. Unlike `explain`, which
summarizes for human reading, `metadata` returns the full structure including
internal member IDs, coordinate codes, and dimension identifiers. This is
useful for debugging category mapping issues — when a label in a WDS table
does not match what the mapping template expects, the raw metadata shows the
exact strings Statistics Canada uses.

```bash
synthpopcan statcan wds metadata 98100001
synthpopcan statcan wds metadata 98100001 --out metadata.json
```

### `statcan census-profile fetch`

Downloads a Census Profile bulk CSV for a specific geography level and census
year. The Census Profile contains several hundred demographic characteristics
(age, sex, income, household size, housing tenure, languages, and more) for
every geographic unit at the chosen level. It is the primary source for
census-tract-level controls in small-area synthesis.

Geography levels (`--geo-level`):

- `pt` — province/territory
- `cd` — census division
- `csd` — census subdivision
- `ct` — census tract (most common for small-area controls)
- `da` — dissemination area

The downloaded file is large and uses Statistics Canada's characteristic-row
format, where each row is a named demographic characteristic rather than a
column. Use `controls census-profile inspect` to search it by keyword before
writing a mapping template.

```bash
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ct \
  --out-dir data/raw/statcan/census-profile/2016
```

Currently only the 2016 census year is supported.

## Troubleshooting

**Search finds a table but controls do not fit:** the table may describe a
different population universe (all persons vs. persons in private households),
a different geography, or use category labels that do not match the seed. Use
`controls wds inspect` and review the mapping before normalizing.

**Download fails:** public Statistics Canada URLs can change. Record the
product ID, the date, the exact command, and the error message. Check whether
the product ID still appears in `statcan wds search` results.

**A table has many columns:** normalize only the dimensions needed for the
first fit. Add more dimensions after a simpler fit validates.

## Further Reading

- [Web Data Service (WDS)](https://www.statcan.gc.ca/en/developers/wds) —
  Statistics Canada's developer hub for the WDS, including rate limits,
  available methods, and JSON vs SDMX output options.
- [WDS User Guide](https://www.statcan.gc.ca/en/developers/wds/user-guide) —
  full reference for every WDS API call, response formats, and error codes.
- [Census Profile bulk downloads](https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X) —
  Statistics Canada catalogue page listing all Census Profile CSV downloads
  by geography level and census year.
