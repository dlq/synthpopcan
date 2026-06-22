# Examples

These examples are deliberately small. They are meant to show the workflow and
file shapes clearly before you move to larger local data.

## Example 1: A Two-Person IPF Fixture

The fixture microdata file is:

```text
HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR
1,11,111,11101,1,adult,F,owner
1,11,111,11102,1,child,M,owner
```

The controls ask for equal totals by age group and sex:

```text
margin,dimensions,AGEGRP,SEX,count
age,AGEGRP,adult,,100
age,AGEGRP,child,,100
sex,SEX,,F,100
sex,SEX,,M,100
```

Run the workflow:

```bash
uv run synthpopcan microdata export-seed \
  tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv

uv run synthpopcan ipf fit \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json
```

The fitted output is compact. It should contain the two seed records with fitted
weights that sum to the requested control totals.

## Example 2: Checking Category Labels Before Fitting

Suppose a StatCan table uses full labels:

```text
Sex,VALUE
Female,60
Male,40
```

But your seed uses short labels:

```text
id,SEX
1,F
2,M
```

Do not fit directly. First create or use a mapping:

```json
{
  "Sex": {
    "Female": "F",
    "Male": "M"
  }
}
```

Then normalize the controls:

```bash
zip -j wds.zip tests/fixtures/workflows/wds_ipf/wds-table.csv

uv run synthpopcan controls from-wds wds.zip \
  --dimensions Sex \
  --count-column VALUE \
  --margin-name sex \
  --mapping tests/fixtures/workflows/wds_ipf/categories-filled.json \
  --out controls.csv
```

Check before fitting:

```bash
uv run synthpopcan ipf check-inputs \
  --seed tests/fixtures/workflows/wds_ipf/seed.csv \
  --controls controls.csv
```

## Example 3: Use JSON for a Notebook or Script

Use table output while exploring:

```bash
uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv
```

Use JSON when another program needs the result:

```bash
uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv \
  --format json
```

This pattern is useful in digital-history or social-science notebooks where a
human reviews the first pass, then the workflow is repeated for multiple
geographies.

## Example 4: Validate Linked Household and Person Rows

After generating linked rows, validate that each generated person points to a
generated household and that household sizes agree:

```bash
uv run synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

If validation fails, inspect the household identifier columns first. A common
problem is writing or editing the household and person files separately so the
IDs no longer match.

## Example 5: Keep a Research Trail

For a serious run, keep these files together:

```text
project-run/
  command-log.txt
  seed.csv
  controls.csv
  weights.csv
  fit-report.json
  validation-report.json
  notes.md
```

In `notes.md`, record:

- source tables and microdata products;
- geography and filters;
- selected seed columns;
- category mappings;
- random seed, if used;
- validation result;
- known limitations.

This small habit makes the output easier to cite, rerun, and explain.
