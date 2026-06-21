# SynthPopCan

SynthPopCan is an early-stage project for building Canadian synthetic population tooling.

Near-term goals:

1. Provide a Python library and CLI that can create synthetic populations through IPF from Statistics Canada margin/control tables.
2. Build census microdata workflows for household- and person-level synthetic populations using tree-based models plus calibration. The local 2016 Census material is the first available microdata source, but the tooling should be census-year agnostic.
3. Add a web app for configuring runs, inspecting controls, validating outputs, and downloading results.

Broader SynthEco-style enrichment with cohort, environmental, school, healthcare, and food-access layers is intentionally deferred until the base population synthesis workflow is stable.

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

Run IPF with:

```bash
synthpopcan ipf fit --seed seed.csv --controls controls.csv --out weights.csv
```

The output is compact fitted seed weights: one row per seed record with a fitted `weight`.

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

Expanded output has one row per generated synthetic record:

```csv
synthetic_id,source_id,age,sex
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
- `source_id`: seed row ID copied from the seed `id` column, or the seed row number when no `id` column exists.
- all remaining seed attributes, such as `age` and `sex`.

For this toy example the expanded output has 100 rows. Its marginal counts match the controls: 60 young, 40 old, 50 female, and 50 male.

## StatsCan Source Fetching

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

User story for finding a WDS table ID:

1. The user starts with topic words, for example `population dwelling`, `age sex`, `household income`, or `labour force`.
2. The user runs `synthpopcan statcan wds search "TOPIC WORDS" --limit 10`.
3. The CLI prints matching WDS tables with product ID, CANSIM ID when available, date range, and English title.
4. The user runs `synthpopcan statcan wds metadata PRODUCT_ID --out metadata.json`.
5. The user inspects the metadata dimensions, geography members, measures, date range, and title to decide whether the table can be normalized into margin controls.
6. The user runs `synthpopcan statcan wds fetch PRODUCT_ID --out-dir ...`.
7. If the table is not suitable as a margin table, the later normalization step should fail with a clear explanation of which dimensions or measures are missing.

The CLI-assisted search uses StatsCan's `getAllCubesListLite` endpoint. Metadata inspection uses `getCubeMetadata`.

#### Example: choosing a WDS table

Suppose the user wants a simple population/dwelling count source to begin testing control-table normalization.

Search WDS tables:

```bash
synthpopcan statcan wds search "population dwelling" --limit 5
```

Default shell output is a Rich table:

```text
                              StatsCan WDS Tables
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

The next step, not implemented yet, is a normalizer that reads the downloaded StatsCan CSV package and turns selected dimensions and measures into SynthPopCan's long control format for `synthpopcan ipf fit`.

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
