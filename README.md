# SynthPopCan

SynthPopCan is an early-stage project for building Canadian synthetic population tooling.

Near-term goals:

1. Provide a Python library and CLI that can create synthetic populations through IPF from Statistics Canada margin/control tables.
2. Build census microdata workflows for household- and person-level synthetic populations using a tree-based synthetic population generator plus calibration. The local 2016 Census material is the first available microdata source, but the tooling should be census-year agnostic.
3. Add a web app for configuring runs, inspecting controls, validating outputs, and downloading results.

Broader SynthEco-style enrichment with cohort, environmental, school, healthcare, and food-access layers is intentionally deferred until the base population synthesis workflow is stable.

## Developer Benchmarks

IPF benchmark fixtures are available as developer tooling, not as a normal user workflow:

```bash
uv run python scripts/benchmark_ipf.py
```

Use `--seed-records` for smaller or larger local runs while checking performance changes.

## Local Data Setup

SynthPopCan expects local data and metadata under `data/` by default. Raw and private data are ignored by git.

```text
data/
  raw/
    statscan/
      2016-census/
        metadata/
          statcan-2016-hierarchical-pumf/
            variable-labels.json
          statcan-2016-individual-pumf/
            variable-labels.json
  private/
```

Check whether the expected files are in place with:

```bash
synthpopcan data doctor
```

Use `--data-root PATH` when your local data directory lives somewhere else:

```bash
synthpopcan data doctor --data-root /path/to/data
```

For repeated work, set `SYNTHPOPCAN_DATA_ROOT`:

```bash
export SYNTHPOPCAN_DATA_ROOT=/path/to/data
synthpopcan data doctor
```

Command-line options take priority over `SYNTHPOPCAN_DATA_ROOT`; if neither is set, SynthPopCan uses `data/`.

## Source Inspection

Use source inspection before writing adapters for new StatCan, Census Profile, or microdata formats:

```bash
synthpopcan sources inspect data/raw --format json
synthpopcan sources schema data/raw/example.csv --format json
synthpopcan sources sample data/raw/example.csv --rows 5 --format json
```

Sampling paths under `data/private` requires `--allow-private`. Census microdata formats vary by source year and access product, so SynthPopCan should inspect structure first and then route files through explicit source adapters rather than relying on one generic census parser.

## Microdata CLI

Inspect a StatCan 2016 hierarchical PUMF file without printing private rows:

```bash
synthpopcan microdata inspect hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --format table
```

The 2016 hierarchical PUMF is a single person-row file with household and family identifiers such as `HH_ID`, `EF_ID`, `CF_ID`, and `PP_ID`. SynthPopCan treats separate household/person CSVs as a derived or fixture shape, not the expected StatCan input shape.

Export selected person-level columns as an IPF seed CSV:

```bash
synthpopcan microdata export-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv
```

The export includes stable ID and weight columns from the adapter, plus the selected seed attributes. Household-level export from hierarchical microdata is deferred until household aggregation rules are defined.

## IPF CLI

The first implemented workflow fits seed records to one-way or multi-way margin tables stored as CSV.

Seed records are ordinary CSV rows:

```csv
id,age,sex
1,young,F
2,young,M
3,old,F
4,old,M
```

Controls use a long format. The `dimensions` column names the seed columns that define each margin, and `count` is the target total:

```csv
margin,dimensions,age,sex,count
age,age,young,,60
age,age,old,,40
sex,sex,,F,50
sex,sex,,M,50
```

Validate a normalized controls file with:

```bash
synthpopcan controls validate controls.csv
```

Normalize a local long controls CSV into SynthPopCan's canonical long format with:

```bash
synthpopcan controls from-csv source-controls.csv --out controls.csv
```

Run IPF with:

```bash
synthpopcan ipf fit \
  --seed seed.csv \
  --controls controls.csv \
  --out weights.csv \
  --report fit-report.json
```

The output is compact fitted seed weights: one row per seed record with a fitted `weight`.
If the seed already has a `weight` column, fitted weights are written as `fitted_weight`.
The optional JSON report records convergence status, iterations, max error, and per-margin fitted residuals.

Read the fit report as a lightweight table:

```bash
synthpopcan ipf report fit-report.json
```

Example report output:

| Section | What it tells you |
| --- | --- |
| Fit summary | Whether IPF converged, how many iterations ran, how many seed records were fitted, and the largest absolute error. |
| Margin table | For each margin, the dimensions fitted, number of cells, target total, fitted total, largest absolute error, and largest relative error. |

For non-converged fits, the report includes a `Fit Issues` table that points to the largest residual and suggests whether to check conflicting controls, sparse seed coverage, or category mappings.

```csv
id,age,sex,weight
1,young,F,30
2,young,M,30
3,old,F,20
4,old,M,20
```

Expand fitted weights explicitly when you want a full synthetic CSV to inspect or pass to a downstream model:

```bash
synthpopcan ipf expand --weights weights.csv --out synthetic.csv
```

`ipf expand` uses `fitted_weight` when present, otherwise `weight`. Use `--weight-field` to choose a different column. By default, `ipf fit` fails without writing an output file if the fit does not converge; pass `--allow-nonconverged` only when you intentionally want to inspect a failed fit.
Expansion streams rows directly to the output CSV instead of holding the full synthetic population in memory.

Expanded output has one row per generated synthetic record:

```csv
synthetic_id,seed_id,age,sex
1,1,young,F
2,1,young,F
...
30,1,young,F
31,2,young,M
...
100,4,old,M
```

The expanded shape is:

- `synthetic_id`: new row ID for the generated synthetic record.
- `seed_id`: seed row ID copied from the seed `id` column, or the seed row number when no `id` column exists.
- all remaining seed attributes, such as `age` and `sex`.

For this toy example the expanded output has 100 rows. Its marginal counts match the controls: 60 young, 40 old, 50 female, and 50 male.

Validate a generated artifact against the controls after fitting, expansion, copying, or filtering:

```bash
synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```

Use `--kind expanded` for a full synthetic CSV from `ipf expand`. Validation recomputes marginal totals and reports pass/fail status, worst errors, and per-margin summaries.

## StatCan Source Fetching

SynthPopCan has two initial source-fetch paths.

### WDS table ZIPs

Search for candidate Statistics Canada WDS product/table IDs:

```bash
synthpopcan statcan wds search "population dwelling" --limit 10
```

Inspect a candidate table before downloading it:

```bash
synthpopcan statcan wds metadata 14100287 --out 14100287-metadata.json
```

Download the table CSV ZIP:

```bash
synthpopcan statcan wds fetch 14100287 --lang en --out-dir data/raw/statscan/wds
```

This calls the Statistics Canada Web Data Service endpoint:

```text
https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{product_id}/{lang}
```

The WDS response returns the actual CSV ZIP URL. SynthPopCan downloads that ZIP and writes a small JSON manifest beside it.

Normalize a downloaded WDS ZIP into SynthPopCan controls with explicit table mapping:

```bash
synthpopcan controls from-wds data/raw/statscan/wds/14100287-eng.zip \
  --dimensions "GEO,Age group,Sex" \
  --count-column VALUE \
  --margin-name population \
  --mapping categories.json \
  --out controls.csv
```

The first `from-wds` implementation intentionally requires the dimensions and count column. StatCan WDS tables differ in universe, measures, notes, and category layout, so arbitrary tables should not be guessed into controls without an explicit mapping.

The optional category mapping file is a JSON object keyed by source dimension:

```json
{
  "Age group": {
    "0 to 4 years": "age_000_004",
    "5 to 9 years": "age_005_009"
  },
  "Sex": {
    "Female": "female",
    "Male": "male"
  }
}
```

When a mapping is provided for a dimension, unmapped values in that dimension fail the normalization run.

### Census Profile CSVs

Start by searching the characteristic labels in a local Census Profile CSV:

```bash
synthpopcan controls census-profile inspect profile.csv --search "years"
```

This prints a small table of matching Census Profile rows with example counts, which helps you decide which rows belong in an IPF control.

Write a starter mapping template:

```bash
synthpopcan controls census-profile template age5 --out census-profile-mapping.json
```

Available starter templates are `age5` and `sex`. The mapping file names the geography, characteristic, and count columns, then maps selected profile characteristic rows into control categories:

```json
{
  "geography": {"column": "GEO_CODE", "dimension": "geo"},
  "characteristic_column": "CHARACTERISTIC_NAME",
  "count_column": "C1_COUNT_TOTAL",
  "margins": [
    {
      "name": "age",
      "dimensions": ["geo", "age"],
      "categories": {
        "0 to 4 years": {"age": "age_000_004"},
        "5 to 9 years": {"age": "age_005_009"}
      }
    }
  ]
}
```

Edit the template if the Census Profile labels or output category names need to change, then normalize:

```bash
synthpopcan controls from-census-profile profile.csv \
  --mapping census-profile-mapping.json \
  --out controls.csv
```

This first adapter intentionally reads local downloaded CSVs and selected rows only. It helps inspect and template mappings, but it does not infer which Census Profile characteristics are suitable IPF controls.

User story for finding a WDS table ID:

1. The user starts with topic words, for example `population dwelling`, `age sex`, `household income`, or `labour force`.
2. The user runs `synthpopcan statcan wds search "TOPIC WORDS" --limit 10`.
3. The CLI prints matching WDS tables with product ID, CANSIM ID when available, date range, and English title.
4. The user runs `synthpopcan statcan wds metadata PRODUCT_ID --out metadata.json`.
5. The user inspects the metadata dimensions, geography members, measures, date range, and title to decide whether the table can be normalized into margin controls.
6. The user runs `synthpopcan statcan wds fetch PRODUCT_ID --out-dir ...`.
7. If the table is not suitable as a margin table, the later normalization step should fail with a clear explanation of which dimensions or measures are missing.

The CLI-assisted search uses StatCan's `getAllCubesListLite` endpoint. Metadata inspection uses `getCubeMetadata`.

#### Example: choosing a WDS table

Suppose the user wants a simple population/dwelling count source to begin testing control-table normalization.

Search WDS tables:

```bash
synthpopcan statcan wds search "population dwelling" --limit 5
```

Default shell output is a Rich table:

```text
                              StatCan WDS Tables
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Product ID ┃ CANSIM ID ┃ Date Range               ┃ Title                    ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 38100170   │ None      │ 2016-01-01 to 2021-01-01 │ Coastal population and   │
│            │           │                          │ dwellings by elevation   │
│            │           │                          │ and distance from        │
│            │           │                          │ coastline                │
│ 98100001   │ None      │ 2021-01-01               │ Population and dwelling  │
│            │           │                          │ counts: Canada,          │
│            │           │                          │ provinces and            │
│            │           │                          │ territories              │
│ 98100002   │ None      │ 2021-01-01               │ Population and dwelling  │
│            │           │                          │ counts: Canada and       │
│            │           │                          │ census subdivisions      │
│            │           │                          │ (municipalities)         │
└────────────┴───────────┴──────────────────────────┴──────────────────────────┘
```

The same search can use script-friendly output:

```bash
synthpopcan statcan wds search "population dwelling" --limit 5 --format tsv
synthpopcan statcan wds search "population dwelling" --limit 5 --format json
```

The same results as a lightweight documentation table:

| Product ID | CANSIM ID | Date Range | Title |
| --- | --- | --- | --- |
| `38100170` | None | 2016-01-01 to 2021-01-01 | Coastal population and dwellings by elevation and distance from coastline |
| `98100001` | None | 2021-01-01 | Population and dwelling counts: Canada, provinces and territories |
| `98100002` | None | 2021-01-01 | Population and dwelling counts: Canada and census subdivisions (municipalities) |
| `98100003` | None | 2021-01-01 | Population and dwelling counts: Census metropolitan areas, census agglomerations and census subdivisions (municipalities) |
| `98100004` | None | 2021-01-01 | Population and dwelling counts: Canada, provinces and territories, census divisions, census subdivisions (municipalities) and designated places |

The user picks `98100001` because the title says it contains population and dwelling counts for Canada, provinces, and territories.

Inspect the metadata:

```bash
synthpopcan statcan wds metadata 98100001 --out 98100001-metadata.json
```

Useful metadata excerpt:

```json
{
  "productId": "98100001",
  "cubeTitleEn": "Population and dwelling counts: Canada, provinces and territories",
  "cubeStartDate": "2021-01-01",
  "cubeEndDate": "2021-01-01",
  "dimensions": [
    {
      "name": "Geographic name",
      "members": [
        "Canada",
        "Newfoundland and Labrador",
        "Prince Edward Island",
        "Nova Scotia",
        "New Brunswick",
        "Quebec"
      ]
    },
    {
      "name": "Population and dwelling counts (11)",
      "members": [
        "Population, 2021",
        "Population, 2016",
        "Population percentage change, 2016 to 2021",
        "Total private dwellings, 2021",
        "Total private dwellings, 2016",
        "Total private dwellings percentage change, 2016 to 2021"
      ]
    }
  ]
}
```

This is useful because it tells the user what the table can and cannot do before downloading it. This table has geography and population/dwelling measures, so it is a plausible source for total population controls by province or territory. It is not enough for age-by-sex IPF because the metadata does not include age or sex dimensions.

Download the table:

```bash
synthpopcan statcan wds fetch 98100001 --lang en --out-dir data/raw/statscan/wds
```

The command is quiet on success and creates:

```text
data/raw/statscan/wds/98100001-eng.zip
data/raw/statscan/wds/98100001-eng.json
```

The manifest records the WDS API URL and the actual ZIP URL:

```json
{
  "download_url": "https://www150.statcan.gc.ca/n1/tbl/csv/98100001-eng.zip",
  "language": "en",
  "path": "data/raw/statscan/wds/98100001-eng.zip",
  "product_id": "98100001",
  "source": "Statistics Canada WDS",
  "source_url": "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/98100001/en"
}
```

The next step, not implemented yet, is a normalizer that reads the downloaded StatCan CSV package and turns selected dimensions and measures into SynthPopCan's long control format for `synthpopcan ipf fit`.

### Census Profile bulk CSVs

Use this for known public Census Profile bulk downloads by geography level. The current implementation starts with the 2016 registry; 2021 should be added as a year-aware registry rather than as a separate product path.

```bash
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level pt \
  --out-dir data/raw/statscan/census-profile/2016
```

Initial geography keys include:

```text
pt, cma-ca, cma-ca-csd, cd, csd-all, da-all, ct, er, popctr, fed, dpl, fsa, ada, hr
```

The Census Profile archive currently exposes these as listed CSV download links. If Statistics Canada moves an archived file, the command will fail at download time and preserve the source URL in the code registry for troubleshooting.

## Data Policy

Large, raw, private, or access-controlled data are not tracked in git.

- `data/raw/` is a local ignored cache for central raw inputs, including public Census Profile and WDS downloads.
- `data/private/` is a local ignored cache for access-controlled or sensitive later-use datasets.
- `references/` is a local ignored cache for copied papers, proposals, and legacy code references.

Public geography, school, healthcare, road, and environmental layers should generally be fetched from authoritative public sources such as Statistics Canada, open.canada.ca, donneesquebec.ca, and municipal/provincial open-data portals rather than stored in this repository.

Local-only manifests may exist inside ignored data directories to document what is present on a development machine.
