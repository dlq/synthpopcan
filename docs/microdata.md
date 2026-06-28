# Microdata

Microdata commands turn source-level census records into the smaller working
tables that SynthPopCan can fit, train, inspect, and validate. We use them when
we need to move from a local census file to either:

- an IPF seed CSV, where each row can receive a fitted weight; or
- a tree-training CSV, where selected columns become targets and conditioning
  variables for a model.

The command group is deliberately cautious. It inspects structure, checks
household-level assumptions, and writes derived CSVs without printing private
rows by default. That matters because census microdata can be restricted,
sensitive, or simply easy to misread. A derived file is not neutral: the chosen
columns, level, geography, and row weights all become part of the research
argument. If you export only age group and sex, the seed can only carry those
relationships forward — household income, language, immigration status, and
dwelling type will be absent from any generated output. That is a choice, and it
should be a deliberate one.

## Concept

Public aggregate tables tell us counts by category. Microdata gives us example
records with relationships among fields. Synthetic-population workflows often
need both: microdata gives row structure, while controls or model conditions
give the target population context.

For IPF, the microdata export creates seed rows. IPF can only reweight those
rows, so the seed has to contain the columns used in the controls. If a control
uses `AGEGRP` and `SEX`, the seed must contain `AGEGRP` and `SEX`.

For tree models, the microdata export creates training rows. Target columns are
the fields the model will generate; conditioning columns are the fields we use
to choose an appropriate distribution. The tree documentation explains the
model risks in more detail, especially low support, high purity, and overfit
geography-specific models.

SynthPopCan currently exposes two adapter formats in the CLI:

- `statcan-2016-hierarchical` for the [Statistics Canada 2016 hierarchical PUMF](https://www150.statcan.gc.ca/n1/pub/98m0002x/98m0002x2016001-eng.htm)
  shape used by the current local workflow; and
- `fixture-v1` for small test and demonstration files.

The 2016 hierarchical PUMF is a person-row file with household and family
identifiers such as `HH_ID`, `EF_ID`, `CF_ID`, and `PP_ID`. Household-level
exports are derived from that person-row file and are only valid when selected
household columns are constant within each household.

## Getting Started

Always inspect the file first. The `inspect` command reports row and household
counts, detected identifier and weight columns, available geography columns,
and the full column list — without printing any source rows. Use this output
to confirm the file loaded correctly and to identify which columns are
available before choosing what to export.

```bash
synthpopcan microdata inspect \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical
```

**For an IPF seed (person level):** export the columns your controls use.
IPF can only reweight rows that exist in the seed, so the seed must contain
every column referenced in any control margin. The weight column is included
automatically.

```bash
synthpopcan microdata export-seed \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv
```

**For an IPF seed (household level):** household columns in a person-row file
should be constant within each household — tenure is the same for all people
in a household, but age is not. Run `check-seed` first to confirm this holds
for the columns you want. If any column varies within a household, a
household-level export would silently discard that variation.

```bash
synthpopcan microdata check-seed \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR
```

```bash
synthpopcan microdata export-seed \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR \
  --out household-seed.csv
```

**For a tree model (training export):** the column choices here are a
modelling decision, not just a technical step. `suggest-tree-columns` gives
you a starting point organized by block (household core, person demographics,
etc.) based on what the adapter considers safe and coherent at each level.
Review the suggestions before accepting them — a block that is sensible at the
provincial level may be too detailed for a small geography.

```bash
synthpopcan microdata suggest-tree-columns \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical
```

Export a training view only after deciding which fields belong in the model.
Target columns are what the model will generate; conditioning columns are what
it conditions generation on.

```bash
synthpopcan microdata export-training \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --out person-training.csv
```

## Subcommands

### `microdata inspect`

Inspects a microdata file without printing source rows. Reports row count,
household count, detected identifier columns (`HH_ID`, `PP_ID`, etc.), the
weight column, available geography columns, and the full column inventory.
Use this before any export to confirm the file is loaded correctly and to
identify which columns are available for seed or training export.

```bash
synthpopcan microdata inspect hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --format table
```

Important options:

- `--input-format`: source adapter, currently `statcan-2016-hierarchical` or
  `fixture-v1`.
- `--level`: required for `fixture-v1`, where the fixture must be declared as
  `household` or `person`.
- `--weight-column`, `--geo-columns`, and `--id-columns`: fixture-oriented
  options used when a small local file needs explicit metadata.
- `--format json|table`: choose machine-readable or reader-facing output.

### `microdata check-seed`

Checks whether selected household columns can be safely exported as seed rows
from a `statcan-2016-hierarchical` file.

```bash
synthpopcan microdata check-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR
```

Use this before household-level IPF. The check reports whether selected columns
and `WEIGHT` are constant within `HH_ID`. If they are not constant, a household
seed would collapse person-row differences into one household row and should not
be exported without another modelling decision.

### `microdata export-seed`

Exports selected microdata columns as an IPF seed CSV. The weight column is
always included. Only columns named in `--columns` appear in the output — any
column your controls reference must be listed here, or IPF will fail with a
missing-column error.

```bash
synthpopcan microdata export-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv
```

For `statcan-2016-hierarchical`, person-level export is the default. Use
`--level household` when you intentionally want one row per household. Run
`check-seed` first to confirm the selected columns are constant within each
household — if they are not, the export will collapse variation silently.

```bash
synthpopcan microdata export-seed hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --columns TENUR \
  --out household-seed.csv
```

For `fixture-v1`, `--level` is required because the fixture file does not carry
the same adapter assumptions as the StatCan hierarchical source.

### `microdata suggest-tree-columns`

Suggests broad household and person column blocks for tree modelling.

```bash
synthpopcan microdata suggest-tree-columns hierarchical.csv \
  --input-format statcan-2016-hierarchical
```

Treat this as a starting point, not as an automatic model design. A suggested
block can still be too detailed for a small geography or unsuitable for a
particular humanities question. See {doc}`tree` for the longer discussion of
support, purity, forests, and bad models.

For broad linked tree models, `tree train-linked` also accepts
`--household-block all` and `--person-block all`. These combine the source
adapter's currently supported household or person blocks. They do not mean
"every raw column": identifier, weight, replicate-weight, geography, and
person-varying columns are excluded from the household side unless a supported
source adapter derives a household-level version.

### `microdata tree-geography-feasibility`

Reports how many person and household rows each geography value has, and flags
which geographies are likely viable, borderline, or too sparse for the chosen
column blocks at publishable quality thresholds. Use this before committing to
a geography in `tree train-linked` — a geography with too few rows will produce
a model with low support and high purity that fails the audit step.

The output groups geographies into likely viable, borderline (may need a
reduced column profile or private-only use), and too sparse (should not be
trained at publishable thresholds with the chosen blocks). A borderline
geography is not automatically excluded; it may still work with a reduced
target profile or a broader category scheme.

```bash
synthpopcan microdata tree-geography-feasibility hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --geo-column PR \
  --household-block household_core \
  --person-block person_demographics
```

Important options:

- `--likely-person-rows` and `--likely-household-rows`: thresholds for
  geographies that look plausibly supported.
- `--borderline-person-rows` and `--borderline-household-rows`: thresholds for
  geographies that may need reduced targets or private-only use.
- `--min-support` and `--max-purity`: release-oriented model-risk thresholds
  aligned with the tree audit commands.

### `microdata export-training`

Exports selected microdata columns as tree-training rows.

```bash
synthpopcan microdata export-training hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level household \
  --target-columns household_size,TENUR \
  --conditioning-columns PR \
  --out household-training.csv
```

The `--target-columns` are generated by the model. The
`--conditioning-columns` shape which target distributions are used. If a
conditioning column is too detailed, the model may have very small groups; if it
is too broad, the generated rows may miss patterns that matter for the research
question.

## Troubleshooting

**The command says the input format is unsupported:** check the adapter name.
The current CLI accepts `statcan-2016-hierarchical` for the main census
microdata workflow and `fixture-v1` for small local fixtures.

**Household seed export fails:** run `microdata check-seed` and look for
columns that vary within `HH_ID`. We should either remove those columns, derive
a household-level summary explicitly, or stay with person-level seed rows.

**IPF later reports missing columns:** re-run `microdata export-seed` with the
columns used by the controls. IPF cannot fit a control dimension that is absent
from the seed CSV.

**Tree training looks sparse:** run `microdata tree-geography-feasibility`,
reduce the target profile, combine categories, or train for a larger geography.
The tree page discusses why low support and high purity are warning signs.

**The output should be used in automation:** pass `--format json` on inspection
and check commands. CSV exports remain ordinary CSV files.

## Further Reading

- See {doc}`ipf` for how exported seed rows are fitted to controls.
- See {doc}`tree` for how exported training rows become flat or linked tree
  models.
- See {doc}`field-primer` for the broader discussion of microdata,
  disclosure-risk framing, and synthetic-population methods.
