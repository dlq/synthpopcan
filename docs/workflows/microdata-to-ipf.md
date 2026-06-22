# Microdata to IPF Workflow

This fixture workflow shows how the seed columns and control dimensions must line up.

The tracked files under `tests/fixtures/workflows/microdata_ipf/` are deliberately tiny:

- `hierarchical.csv`: a two-person `statcan-2016-hierarchical`-style microdata file.
- `controls.csv`: normalized controls whose dimensions match the exported seed columns.
- `expected-seed.csv`: the seed file produced by `microdata export-seed`.

Run the workflow:

```bash
synthpopcan microdata export-seed tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv

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

The controls use `AGEGRP` and `SEX` because those are the exported seed columns. The category values also match: `adult`, `child`, `F`, and `M`. If either the column names or category labels differ, IPF cannot fit the controls without a mapping step.

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
