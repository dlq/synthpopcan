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

## Choose and Inspect a StatCan WDS Table

Once a search result gives you a product ID, explain the table before
downloading it:

```bash
synthpopcan statcan wds explain 98100001
```

The explanation summarizes the table title, date range, available dimensions,
whether it looks plausible as an IPF control source, and the next commands to
run.

When you have downloaded a full StatCan WDS table ZIP, inspect it before
normalizing controls:

```bash
synthpopcan controls wds inspect 98100001-eng.zip
```

The inspection reports the CSV member, columns, row count, likely count column,
likely dimension columns, and a starter command:

```bash
synthpopcan controls from-wds 98100001-eng.zip \
  --dimensions 'GEO,Age group,Sex' \
  --count-column VALUE \
  --margin-name wds \
  --out controls.csv
```

Treat the suggested dimensions as a starting point. Drop columns that are not
part of the margin you want to fit.

If source labels need to be converted to seed categories, write a starter
mapping template:

```bash
synthpopcan controls wds mapping-template 98100001-eng.zip \
  --dimensions 'Age group,Sex' \
  --out categories.json
```

The template lists observed source labels with blank target values for you to
fill in:

```json
{
  "Age group": {
    "0 to 4 years": ""
  },
  "Sex": {
    "Female": "",
    "Male": ""
  }
}
```

After normalization, run `ipf check-inputs` to confirm that the seed file has
matching columns and category values.

When columns or categories do not line up, the report includes next steps. For
example, it may suggest exporting a seed column with the same name as a control
dimension, or using `controls wds mapping-template` when WDS labels such as
`Female` need to be mapped to seed labels such as `F`.
