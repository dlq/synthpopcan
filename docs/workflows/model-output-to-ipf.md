# Model Output to IPF Workflow

This workflow connects the linked tree generator to IPF calibration. Use it
when you have a reviewed linked household/person model package and want the
generated rows to match selected StatCan controls.

The important rule is simple: **IPF cannot create missing variables**. IPF can
only calibrate columns already present on the seed or generated rows. If a
StatCan table includes a useful dimension that is not in the generated output,
add that column first with a model, recoding step, lookup, or future enrichment
workflow. Then run IPF.

This workflow is useful when generated model output has the right columns but
the totals need to be nudged toward a public aggregate table. It is not a
shortcut for adding attributes the model did not generate.

## 1. Generate Candidate Rows

Start from a reviewed linked model package:

```bash
synthpopcan tree generate-from-package linked-model-package.json \
  --households 1000 \
  --condition PR=24 \
  --households-out candidate-households.csv \
  --persons-out candidate-persons.csv \
  --manifest-out candidate-linked.manifest.json \
  --random-seed 13
```

The household output becomes the first IPF seed table. It keeps the generated
household attributes from the model package, such as geography, household size,
tenure, or other fields included in the model.

Validate the household/person linkage before calibration:

```bash
synthpopcan validate linked-output \
  --households candidate-households.csv \
  --persons candidate-persons.csv
```

## 2. Get Calibration-Control Suggestions

Ask SynthPopCan which generated columns look like useful calibration controls:

```bash
synthpopcan ipf suggest-controls \
  --seed candidate-households.csv \
  --unit household
```

This is an advisory helper. It does not choose a StatCan table for you. It
reports generated columns that are plausible household controls, common useful
controls that are missing and would require enrichment first, geography columns
to check against the model scope, and next commands for StatCan WDS discovery.

Treat the suggestions as a reading aid. They help you see what the generated
file can support, but you still choose controls based on the research question,
geography, source reliability, and interpretability.

For a generated household file with `geo`, `household_size`, and `tenure`, the
useful part of the output is shaped like this:

| Column | Status | What it means |
| --- | --- | --- |
| `household_size` | usable if categories match | Look for a household-size margin and check that categories can be mapped. |
| `tenure` | usable if categories match | Look for a tenure or housing-tenure margin. |
| `dwelling_type` | needs enrichment/modeling | Do not use dwelling-type controls until generated rows include that column. |

The next commands point you toward StatCan table discovery and a compatibility
check:

```bash
synthpopcan statcan wds search household size
synthpopcan statcan wds explain PRODUCT_ID
synthpopcan ipf check-inputs --seed candidate-households.csv --controls controls.csv
```

## 3. Check Control Compatibility

Normalize or prepare the StatCan controls you want to use, then check whether
the generated rows contain matching columns and categories:

```bash
synthpopcan ipf check-inputs \
  --seed candidate-households.csv \
  --controls household-controls.csv
```

Use this command before fitting. It tells you whether controls are usable as-is
or whether a control dimension is missing from the generated rows.

If the report says a control column is missing, do not try to force that table
through IPF. `check-inputs` will label that path as needing enrichment/modeling
because IPF cannot create the absent variable. Add the missing attribute first,
or choose controls that match the generated columns.

If the report says categories differ, keep the source meaning in view. Some
differences are harmless label differences, such as `Female` and `F`. Others
may indicate different universes, age bands, geographies, or household
definitions.

## 4. Fit Household Weights

Fit the generated household rows to compatible controls:

```bash
synthpopcan ipf fit \
  --seed candidate-households.csv \
  --controls household-controls.csv \
  --out calibrated-household-weights.csv \
  --report household-fit-report.json
```

Weights are the default output because they are compact and preserve the model
output rows. Inspect the report if fitting fails or if the controls appear
inconsistent.

## 5. Expand When Needed

Expand only when you need a full household CSV:

```bash
synthpopcan ipf expand \
  --weights calibrated-household-weights.csv \
  --out calibrated-households.csv
```

Expanded output has one row per synthetic household after integerization. Large
controls can produce large files, so keep the weighted output when possible.

## 6. Validate Against Controls

Validate the calibrated output:

```bash
synthpopcan validate controls \
  --population calibrated-households.csv \
  --controls household-controls.csv \
  --kind expanded
```

For compact weights instead of expanded rows, use:

```bash
synthpopcan validate controls \
  --population calibrated-household-weights.csv \
  --controls household-controls.csv \
  --kind weights
```

## Person Rows and Linkage

The first safe version of this workflow calibrates households. Person rows are
generated from household context and should be validated against linkage checks.
Person-level or joint household/person calibration is a later workflow because
independent person weighting can break household membership.

For now, treat person controls as validation targets unless the person output
already has the controlled columns and the calibration strategy preserves
household links.

When writing up results, be explicit about this distinction. A calibrated
household file and a linked person file are not the same thing as an independently
calibrated person population.
