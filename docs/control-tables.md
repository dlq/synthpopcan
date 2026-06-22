# Control Tables

Control tables tell SynthPopCan what totals the generated or weighted population
should match. In many projects these totals come from Statistics Canada, but
they can also come from a local CSV prepared by a researcher.

This page explains the normalized long format used by the IPF workflow.

## The Minimal Shape

A normalized control CSV has:

- `margin`: a name for the control margin;
- `dimensions`: the seed column or columns used by that margin;
- one column for each possible dimension;
- `count`: the target total.

Example:

```text
margin,dimensions,AGEGRP,SEX,count
age,AGEGRP,adult,,100
age,AGEGRP,child,,100
sex,SEX,,F,100
sex,SEX,,M,100
```

This table contains two one-way margins:

- the `age` margin uses the `AGEGRP` column;
- the `sex` margin uses the `SEX` column.

Blank cells mean that column is not part of that margin row.

## A Two-Dimension Margin

A joint margin can use more than one dimension:

```text
margin,dimensions,AGEGRP,SEX,count
age_sex,"AGEGRP,SEX",adult,F,55
age_sex,"AGEGRP,SEX",adult,M,45
age_sex,"AGEGRP,SEX",child,F,45
age_sex,"AGEGRP,SEX",child,M,55
```

Use joint margins when the relationship between categories matters. They are
more specific, but they also require enough seed coverage for each combination.

## Validate a Control File

Before fitting:

```bash
uv run synthpopcan controls validate controls.csv
```

Validation checks the file shape and catches problems such as missing required
columns, duplicated cells, and invalid counts.

## Normalize a Local Long CSV

If a local CSV is already close to SynthPopCan's long format, normalize it:

```bash
uv run synthpopcan controls from-csv source-controls.csv \
  --out controls.csv
```

Then validate:

```bash
uv run synthpopcan controls validate controls.csv
```

## Normalize a StatCan WDS ZIP

Inspect the ZIP first:

```bash
uv run synthpopcan controls wds inspect data/raw/statcan/wds/98100001-eng.zip
```

Then select the dimensions and count column:

```bash
uv run synthpopcan controls from-wds data/raw/statcan/wds/98100001-eng.zip \
  --dimensions "GEO,Age group,Sex" \
  --count-column VALUE \
  --margin-name age_sex \
  --out controls.csv
```

Run `ipf check-inputs` after normalization. A valid control table can still be
incompatible with a particular seed file.

## Category Mapping

Source tables often use labels that differ from seed labels:

| Source label | Seed label |
| --- | --- |
| `Female` | `F` |
| `Male` | `M` |
| `0 to 4 years` | `age_000_004` |

Create a mapping file:

```json
{
  "Sex": {
    "Female": "F",
    "Male": "M"
  }
}
```

Use it during normalization:

```bash
uv run synthpopcan controls from-wds table.zip \
  --dimensions Sex \
  --count-column VALUE \
  --mapping categories.json \
  --out controls.csv
```

Keep mapping files with the run outputs. They document how source categories
were interpreted.

## Choosing Controls Carefully

More controls are not always better. Start with controls that are:

- relevant to the research question;
- available for the same geography and population universe;
- represented in the seed or generated rows;
- understandable enough to explain later;
- not so detailed that every cell becomes sparse.

Add more detailed controls after the first fit and validation pass works.
