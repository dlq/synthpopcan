# Microdata to IPF Workflow

This workflow turns microdata into a seed table, fits that seed table to control
totals, and validates the result. It is the most direct SynthPopCan path when
you already know which source columns and control totals you want to use.

The key idea is alignment. The seed columns and the control dimensions must
name the same concepts, and their category labels must match or be mapped.

The tracked files under `tests/fixtures/workflows/microdata_ipf/` are deliberately tiny:

- `hierarchical.csv`: a two-person `statcan-2016-hierarchical`-style microdata file.
- `controls.csv`: normalized controls whose dimensions match the exported seed columns.
- `expected-seed.csv`: the seed file produced by `microdata export-seed`.

## 1. Start with a Small Fixture

The fixture microdata is small enough to read:

```text
HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR
1,11,111,11101,1,adult,F,owner
1,11,111,11102,1,child,M,owner
```

The fixture controls request totals by age group and sex:

```text
margin,dimensions,AGEGRP,SEX,count
age,AGEGRP,adult,,100
age,AGEGRP,child,,100
sex,SEX,,F,100
sex,SEX,,M,100
```

The controls use `AGEGRP` and `SEX` because those are the exported seed columns.
The category values also match: `adult`, `child`, `F`, and `M`. If either the
column names or category labels differ, IPF cannot fit the controls without a
mapping or recoding step.

## 2. Export the Seed

```bash
synthpopcan microdata export-seed tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv
```

The exported seed keeps a stable source identifier, selected attributes, and the
source `WEIGHT`. For a real research run, choose columns that describe the
attributes you intend to fit or validate. Do not add every available source
column by habit; keep the first pass understandable.

Check the expected output shape:

```text
PP_ID,AGEGRP,SEX,WEIGHT
11101,adult,F,1
11102,child,M,1
```

## 3. Check Compatibility Before Fitting

```bash
synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv
```

This is the best place to catch mistakes. If the report says a control dimension
is missing, return to the seed export or choose a different control table. If
the report says category values differ, add a mapping or recode the source.

For scripts and notebooks, use JSON:

```bash
synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --format json
```

## 4. Fit Weights

```bash
synthpopcan ipf fit \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json

synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights
```

Weights are the default output because they are compact. A two-row seed stays a
two-row weights file even if the target population total is 200. This makes it
easier to inspect the fitted result before creating a large expanded file.

Read the report:

```bash
synthpopcan ipf report fit-report.json
```

## 5. Validate and Decide Whether to Expand

Validation compares the fitted output back to the controls:

```bash
synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights
```

Expand only when you need one row per generated person:

```bash
synthpopcan ipf expand \
  --weights weights.csv \
  --out synthetic.csv
```

Keep `fit-report.json` and a short note about your source files, selected
columns, and mappings. Those details are part of the research result.

## Choose a StatCan WDS Table

Once a search result gives you a product ID, explain the table before
downloading it:

```bash
synthpopcan statcan wds explain 98100001
```

The explanation summarizes the table title, date range, available dimensions,
a short member preview, whether it looks plausible as an IPF control source,
and the next commands to run.

If the table looks useful, fetch it and normalize the dimensions you need:

```bash
synthpopcan statcan wds fetch 98100001 --out-dir data/raw/statcan/wds
synthpopcan controls from-wds data/raw/statcan/wds/98100001-eng.zip \
  --dimensions 'GEO,Age group,Sex' \
  --count-column VALUE \
  --margin-name wds \
  --out controls.csv
```

Then run `ipf check-inputs` to confirm that the seed file has matching columns
and category values.

Choose dimensions deliberately. A StatCan table can contain more columns than
you need for a first fit. Start with dimensions that answer the research
question and that are already present in the seed.

If you are unsure which columns to use, inspect the downloaded ZIP:

```bash
synthpopcan controls wds inspect data/raw/statcan/wds/98100001-eng.zip
```

The inspection reports the CSV member, columns, row count, likely count column,
likely dimension columns, and a starter command:

```bash
synthpopcan controls from-wds data/raw/statcan/wds/98100001-eng.zip \
  --dimensions 'GEO,Age group,Sex' \
  --count-column VALUE \
  --margin-name wds \
  --out controls.csv
```

Treat the suggested dimensions as a starting point. Drop columns that are not
part of the margin you want to fit.

If source labels need to be converted to seed categories, create a starter
mapping template:

```bash
synthpopcan controls wds mapping-template data/raw/statcan/wds/98100001-eng.zip \
  --dimensions 'Age group,Sex' \
  --preset canonical \
  --out categories.json
```

The `canonical` preset fills common StatCan labels that SynthPopCan already
recognizes and leaves anything else blank for review:

```json
{
  "Age group": {
    "0 to 4 years": "age_000_004"
  },
  "Sex": {
    "Female": "female",
    "Male": "male"
  }
}
```

When columns or categories do not line up, the report includes next steps. For
example, it may suggest exporting a seed column with the same name as a control
dimension, or using `controls wds mapping-template` when WDS labels such as
`Female` need to be mapped to seed labels such as `F`.

For humanities and digital-humanities projects, keep the category mapping file
with your run outputs. The mapping is an interpretive choice, not just a
technical file.

## Optional Live StatCan Check

The default test suite does not call StatCan. To check whether the current WDS
service still matches SynthPopCan's assumptions, run the opt-in live smoke
tests:

```bash
SYNTHPOPCAN_LIVE_STATCAN=1 uv run pytest tests/test_statcan_live.py
```

These tests search for a stable public population/dwelling table, fetch its WDS
metadata, build an `explain` summary, and confirm that the WDS download endpoint
still resolves to a CSV ZIP URL. They do not download the full table ZIP.

## Tiny WDS-to-IPF Fixture

The tracked files under `tests/fixtures/workflows/wds_ipf/` show the WDS label
mapping loop with a deliberately small sex margin:

- `wds-table.csv`: source-style WDS rows with `Female` and `Male`.
- `seed.csv`: seed rows with `F` and `M`.
- `categories-template.json`: blank template produced by
  `controls wds mapping-template`.
- `categories-filled.json`: completed mapping from WDS labels to seed labels.
- `expected-controls.csv`: normalized controls after `controls from-wds`.

Create the ZIP, generate the template, normalize controls, check inputs, fit,
and validate:

```bash
zip -j wds.zip tests/fixtures/workflows/wds_ipf/wds-table.csv

synthpopcan controls wds mapping-template wds.zip \
  --dimensions Sex \
  --out categories-template.json

synthpopcan controls from-wds wds.zip \
  --dimensions Sex \
  --count-column VALUE \
  --margin-name sex \
  --mapping tests/fixtures/workflows/wds_ipf/categories-filled.json \
  --out controls.csv

synthpopcan ipf check-inputs \
  --seed tests/fixtures/workflows/wds_ipf/seed.csv \
  --controls controls.csv

synthpopcan ipf fit \
  --seed tests/fixtures/workflows/wds_ipf/seed.csv \
  --controls controls.csv \
  --out weights.csv \
  --report fit-report.json

synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```
