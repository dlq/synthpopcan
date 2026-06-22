# SynthPopCan

SynthPopCan is an early-stage project for building Canadian synthetic population tooling.

Near-term goals:

1. Provide a Python library and CLI that can create synthetic populations through IPF from Statistics Canada margin/control tables.
2. Build census microdata workflows for household- and person-level synthetic populations using a tree-based synthetic population generator plus calibration. The local 2016 Census material is the first available microdata source, but the tooling should be census-year agnostic.
3. Add a web app for configuring runs, inspecting controls, validating outputs, and downloading results.

Broader SynthEco-style enrichment with cohort, environmental, school, healthcare, and food-access layers is intentionally deferred until the base population synthesis workflow is stable.

Workflow guides live under `docs/workflows/`. Start with
`docs/workflows/microdata-to-ipf.md` for IPF and
`docs/workflows/microdata-to-tree.md` for linked household/person tree models.

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

The export includes stable ID and weight columns from the adapter, plus the selected seed attributes.

Check household-level columns before exporting them:

```bash
synthpopcan microdata check-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR,ROOMS
```

This prints a column-by-column check showing whether selected columns and `WEIGHT` are constant within each `HH_ID`, plus the derived `household_size` field that will appear in the export.

Export household-level seed rows conservatively:

```bash
synthpopcan microdata export-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR \
  --out household-seed.csv
```

For `statcan-2016-hierarchical`, household export creates one row per `HH_ID`, includes `household_size`, and requires selected household columns and `WEIGHT` to be constant within each household. Conflicts fail clearly instead of guessing.

## Microdata to IPF Workflow

A minimal person-level workflow is:

```bash
synthpopcan microdata export-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

synthpopcan ipf fit \
  --seed seed.csv \
  --controls controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json

synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```

The seed file contains one row per source person with stable IDs, selected attributes, and the source `WEIGHT`. The fitted weights file keeps the seed attributes and adds the fitted `weight` column used for validation or later expansion.

A tracked tiny version of this workflow lives in `docs/workflows/microdata-to-ipf.md`.

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

For a downloaded StatCan WDS ZIP, inspect the table first so the CLI can suggest
the likely count and dimension columns:

```bash
synthpopcan controls wds inspect 98100001-eng.zip
```

Check that seed columns and categories cover the controls before fitting:

```bash
synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv
```

If columns or categories do not match, `check-inputs` prints next steps for
renaming/exporting seed columns or mapping WDS labels to seed categories.

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

`ipf expand` reads the `weight` column by default. Use `--weight-field fitted_weight` when fitting a seed file that already had a `weight` column, or use `--weight-field` to choose another fitted-weight column. By default, `ipf fit` fails without writing an output file if the fit does not converge; pass `--allow-nonconverged` only when you intentionally want to inspect a failed fit.
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

Explain a candidate table before downloading it:

```bash
synthpopcan statcan wds explain 14100287
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

Normalize a downloaded WDS ZIP into SynthPopCan controls:

```bash
synthpopcan controls from-wds data/raw/statscan/wds/14100287-eng.zip \
  --dimensions "GEO,Age group,Sex" \
  --count-column VALUE \
  --margin-name population \
  --mapping categories.json \
  --out controls.csv
```

The WDS workflow can also inspect downloaded ZIPs and create starter mapping
templates when source labels need to match seed categories. See
`docs/workflows/microdata-to-ipf.md` for the fuller walkthrough.

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

Short user story for finding a WDS table ID:

1. The user searches with plain topic words, for example `population dwelling`.
2. The CLI shows matching StatCan WDS tables and their product IDs.
3. The user explains one promising product ID before downloading it.
4. The explanation previews the dimensions, a few member labels, and whether
   the table looks useful as an IPF control source.
5. If it looks useful, the user fetches it and follows the printed next command.

If the downloaded table later needs column or label cleanup, SynthPopCan can
inspect the ZIP and create a starter mapping template.

The CLI-assisted search uses StatCan's `getAllCubesListLite` endpoint. Metadata inspection uses `getCubeMetadata`.

For detailed examples, optional metadata export, ZIP inspection, and label
mapping, use `docs/workflows/microdata-to-ipf.md`.

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
