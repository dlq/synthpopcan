# Validate

Validation commands check **generated artifacts**. They do **not** prove a synthetic
population is substantively good, but they catch important mechanical and
calibration errors.

## Concept

Use validation as a **normal step in every workflow**:

- after IPF fitting;
- after expanding rows;
- after linked household/person generation;
- before interpreting or sharing outputs.

Keep **validation reports** with the run notes.

Validation is both a **technical check** and a **provenance practice**. It records what
was checked, against which target, and with what tolerance.

For IPF-specific fit reports and residuals, see {doc}`ipf`. For generating
from a model package, see {doc}`tree-generate`. For model training, auditing,
and release, see {doc}`tree`.

## What Validation Does Not Prove

A passing validation report is **not a certificate** that the synthetic population is
substantively correct. It proves only that the checks we asked for passed.

Validation can miss:

- uncontrolled relationships, such as income by household type or language by
  age, when those relationships were not part of the check;
- source-universe problems, such as mixing years, geographies, or household and
  person units;
- biased or sparse seed data that still matches simple controls;
- tree models that match their training view but fail against external public
  totals;
- disclosure or interpretive risks that require human review.

Treat validation as **evidence in a research note**. Pair it with the source
provenance, category mappings, modelling choices, random seeds, and a short
statement of what the output should not be used to claim.

## What a Serious Validation Note Should Include

For exploratory examples, a short pass/fail report may be enough. For a
**serious run**, keep enough evidence for another reader to understand both the
success and the weak spots:

- total population and household counts by geography;
- absolute and relative error for each controlled margin;
- worst controls and worst geographies, not only overall averages;
- household-size distribution;
- person count per household and orphaned-person checks;
- family/person role consistency where those fields are generated;
- structural-zero and zero-cell diagnostics;
- seed coverage and unused-category notes;
- suppression, rounding, or source-quality notes for public controls;
- random seed, command, package version, and input provenance.

The goal is not to make validation longer for its own sake. The goal is to stop
a neat pass/fail summary from hiding **where the model is weakest**.

## Getting Started

The typical validation sequence follows the generation steps. After IPF
fitting, validate the fitted weights against the controls that were used to fit
them — this confirms the optimizer converged and the weights reproduce the
target totals within tolerance:

```bash
synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```

The report shows the absolute and relative error for each controlled margin and
flags any that exceed the tolerance threshold. A clean run should show near-zero
residuals for every margin. Large residuals on a specific margin usually mean
that margin is structurally in tension with another one, or that the seed has
zero-coverage cells for that combination.

After expanding weights to integer rows, validate the expanded population — this
checks that the row counts match the target totals after rounding:

```bash
synthpopcan validate controls \
  --population synthetic.csv \
  --controls controls.csv \
  --kind expanded
```

Expansion introduces small rounding errors that `--kind weights` would not show,
so run both. Differences between the two reports isolate rounding from fit error.

After linked household/person generation, validate the linkage structure — this
is a mechanical check, not a distributional one:

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

The report flags orphaned persons (person rows referencing a household that does
not exist in the households file) and household size mismatches (the size column
on the household row disagrees with how many person rows reference it). Both are
structural errors that would produce wrong counts in any downstream aggregation.

For flat (non-linked) tree output, use `validate tree-output` instead to compare
generated marginal distributions against a training sample:

```bash
synthpopcan validate tree-output \
  --generated synthetic-persons.csv \
  --training person-training.csv \
  --target-columns AGEGRP,SEX
```

## Subcommands

### `validate controls`

Compares a fitted or expanded population file against the normalized control
table that was used to produce it. For each margin in the controls file, it
computes the absolute and relative difference between what the output contains
and what the control specifies, then reports which margins pass and which exceed
tolerance.

Use `--kind weights` immediately after `ipf fit` to confirm convergence. Use
`--kind expanded` after `ipf expand` to confirm the integer rounding did not
introduce large deviations. Running both is the standard practice because
expansion can amplify small rounding differences that are invisible in the
weight-stage report.

```bash
synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights

synthpopcan validate controls \
  --population synthetic.csv \
  --controls controls.csv \
  --kind expanded \
  --format json
```

Options:

- `--population PATH`: the weights CSV (from `ipf fit`) or expanded rows CSV
  (from `ipf expand`).
- `--controls PATH`: normalized control CSV — the same file passed to `ipf fit`.
- `--kind weights|expanded`: tells the command how to interpret the population
  file. `weights` reads a weight column; `expanded` counts rows.
- `--weight-field NAME`: the weight column name when using `--kind weights`.
  Defaults to the standard output column name from `ipf fit`.
- `--tolerance FLOAT`: maximum allowed absolute difference before a margin is
  flagged as failing. Defaults are appropriate for most runs; tighten for
  publication-quality output.
- `--format table|json`: `table` for human review; `json` for logging or
  feeding into another script.

### `validate linked-output`

Checks the structural integrity of linked household and person output — the two
files that `tree generate-linked` or `small-area` produces together. It does
not check distributional fit against controls; it checks that the two files are
internally consistent.

Specifically, it verifies:

- every person row references a household ID that exists in the households file
  (no orphaned persons);
- the household size field on each household row matches the count of person
  rows that reference it;
- no household IDs are duplicated.

A failure here is a hard structural error. Downstream aggregations that join
households to persons on these IDs would produce wrong counts or silently drop
rows.

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv

synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv \
  --household-id-column HHID \
  --person-household-id-column HHID \
  --household-size-column HHSIZE \
  --format json
```

Options:

- `--households PATH`: the generated households CSV.
- `--persons PATH`: the generated persons CSV.
- `--household-id-column NAME`: the household identifier column in the
  households file. Defaults to the standard name from `tree generate-linked`.
- `--person-household-id-column NAME`: the column in the persons file that
  references the household identifier.
- `--household-size-column NAME`: the column in the households file that records
  how many persons belong to each household.
- `--format table|json`: output format.

### `validate tree-output`

Checks flat (non-linked) tree-generated output by comparing the marginal
distributions of selected columns in the generated file against the same columns
in a training sample. Use this after `tree generate` when we have not used
linked generation and therefore cannot use `validate linked-output`.

The comparison is column-by-column: for each column named in `--target-columns`,
it computes the category distribution in the generated rows and in the training
sample and reports the difference. This tells us whether the tree model is
reproducing the rough shape of the training distribution, but it does not
validate against public control totals — for that, use `validate controls`.

```bash
synthpopcan validate tree-output \
  --generated synthetic-persons.csv \
  --training person-training.csv \
  --target-columns AGEGRP,SEX

synthpopcan validate tree-output \
  --generated synthetic-persons.csv \
  --training person-training.csv \
  --target-columns AGEGRP,SEX \
  --format json
```

Options:

- `--generated PATH`: the flat tree-generated output CSV.
- `--training PATH`: a training sample CSV with the same columns. This is
  typically the person-level file used to train the model.
- `--target-columns COLS`: comma-separated list of column names to compare.
  Choose the columns that the tree model was trained to predict.
- `--format table|json`: output format.

## Troubleshooting

**Validation fails after IPF:** inspect the fit report first. The fit may not
have converged, or the wrong weight column may have been used.

**Validation fails after expansion:** confirm `ipf expand` used the intended
`--weight-field`.

**Linked validation fails:** check generated household IDs, person household
IDs, and household size fields.

## Further Reading

- Robin Lovelace and Dimitris Ballas,
  [Truncate, replicate, sample](https://arxiv.org/abs/1303.5228),
  for the distinction between continuous IPF weights and expanded integer rows.
- Statistical disclosure context:
  [Statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control).
