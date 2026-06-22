# Getting Started

This page walks through a complete, tiny SynthPopCan workflow. It uses files
that are already in the repository, so you can learn the shape of the tool
without downloading Statistics Canada tables or touching private microdata.

SynthPopCan is meant for people doing population, place, policy, social,
historical, and digital-humanities work. You do not need to start by writing
Python. The command-line examples below are the main path.

## What You Are Building

The example starts with two source files:

- a tiny microdata file with two people;
- a tiny control table saying how many people should be in each age and sex
  category.

SynthPopCan turns the microdata rows into a seed table, checks whether the seed
can be fitted to the controls, fits weights with IPF, and validates the result.

In a real project, the rows and controls would be larger. The sequence stays the
same:

1. inspect or export source rows;
2. prepare control totals;
3. check compatibility;
4. fit weights;
5. validate the output;
6. record what you did.

## 1. Check That the CLI Runs

From the repository root:

```bash
uv run synthpopcan --help
```

You should see command groups such as `microdata`, `controls`, `ipf`, `tree`,
`sources`, `statcan`, and `validate`.

If that command fails, see [Troubleshooting](troubleshooting.md).

## 2. Export a Seed File

Export a small seed table from fixture microdata:

```bash
uv run synthpopcan microdata export-seed \
  tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv
```

This creates `seed.csv`. The seed is the set of records that IPF will reweight.
In this example, the seed keeps `AGEGRP`, `SEX`, and the source `WEIGHT`.

The selected columns matter. IPF can only fit controls for columns already
present in the seed. If you later want to fit against tenure, dwelling type, or
geography, those columns must be present before fitting.

## 3. Check Seed and Control Compatibility

Before fitting, ask SynthPopCan whether the seed can satisfy the controls:

```bash
uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv
```

This check is deliberately early. It catches the common problems before a
longer run:

- the control table names a column that is missing from the seed;
- a category label differs, such as `Female` in one file and `F` in another;
- the seed has no examples for a category that appears in the controls.

For automation, add `--format json` to get machine-readable output.

## 4. Fit Weights

```bash
uv run synthpopcan ipf fit \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json
```

The output `weights.csv` is compact: one row per seed record, plus a fitted
weight. This is usually more practical than expanding to one row per synthetic
person immediately.

The report `fit-report.json` records whether fitting converged, how many
iterations were used, and which margins had residual error.

Read the report as a table:

```bash
uv run synthpopcan ipf report fit-report.json
```

## 5. Validate the Result

```bash
uv run synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights
```

Validation compares the fitted output back to the requested controls. Treat this
as a normal part of the workflow, not as an optional final check.

For a script or notebook pipeline, use JSON:

```bash
uv run synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights \
  --format json
```

## 6. Expand Only When You Need Full Rows

Weights are easier to inspect and store. Expand only when another tool needs a
full synthetic CSV:

```bash
uv run synthpopcan ipf expand \
  --weights weights.csv \
  --out synthetic.csv
```

Expanded files can become large quickly. For exploratory work, keep the compact
weights file and the fit report.

## Choose the Next Workflow

- Use [Microdata to IPF Workflow](workflows/microdata-to-ipf.md) when you have a
  seed table and want fitted weights that match normalized controls.
- Use [Microdata to Linked Tree Workflow](workflows/microdata-to-tree.md) when
  you are training household and person models from hierarchical microdata.
- Use [Model Output to IPF Workflow](workflows/model-output-to-ipf.md) when you
  have generated rows and want to calibrate them against compatible controls.

## A Useful Rule

IPF can only calibrate columns that already exist in the seed or generated rows.
If a StatCan table contains a useful dimension that is missing from the seed,
add that attribute first through a model, recoding step, lookup, or later
enrichment workflow.

This rule is worth repeating because it prevents a lot of confusion. IPF adjusts
how much each existing row counts. It does not invent a new variable.
