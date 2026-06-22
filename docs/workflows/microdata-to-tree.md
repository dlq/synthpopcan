# Microdata to Linked Tree Workflow

This workflow trains and uses linked household/person tree models from a mixed
StatCan hierarchical microdata file. The 2016 hierarchical PUMF is the first
supported layout, but the command shape is meant to generalize through explicit
input formats and source-specific column suggestion profiles.

The tracked fixture under `tests/fixtures/workflows/linked_tree/hierarchical.csv`
is deliberately tiny. It is useful for learning the command flow without touching
private or full-size data.

## 1. Inspect Suggested Column Blocks

Start by asking SynthPopCan what it can safely use from the source file:

```bash
synthpopcan microdata suggest-tree-columns \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical
```

For the 2016 hierarchical profile, the first blocks are:

| Block | Level | Role |
| --- | --- | --- |
| `household_core` | household | Household size, tenure, dwelling, rooms, shelter cost, repair, and built-period fields that are present in the inspected file. |
| `person_demographics` | person | Age group, sex, marital status, and immigration status when present. |

The helper excludes identifiers, weights, and replicate weights. It also drops
profile columns that are not present in the inspected file, so the same block
names can work on a tiny fixture and on a fuller local file.

## 2. Train Linked Models

Use `tree train-linked` when you have the mixed hierarchical microdata file and
want compatible household and person models:

```bash
synthpopcan tree train-linked \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --suggested-blocks \
  --household-model-out household-model.json \
  --person-model-out person-model.json \
  --manifest-out linked-training.manifest.json \
  --random-seed 7 \
  --min-support 5
```

The command reads the source once, derives a household training view and a person
training view, trains both models, and writes a manifest. The default blocks are
`household_core` and `person_demographics`.

For full-size local 2016 data, a recent benchmark with those default blocks used
343,330 source person rows and 140,720 derived household rows. Training completed
in about 12 seconds on this development machine. The household model was about
95.5 MB and the person model about 3.5 MB. That model size is a signal that
broader household target blocks may need pruning or coarsening before packaging
for distribution.

## 3. Generate Linked Synthetic Rows

Generate households first, then people conditioned on each generated household:

```bash
synthpopcan tree generate-linked \
  --household-model household-model.json \
  --person-model person-model.json \
  --households 100 \
  --condition PR=24 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --manifest-out synthetic-linked.manifest.json \
  --random-seed 13
```

The household output has one row per generated household with
`synthetic_household_id`. The person output has one row per generated person with
`synthetic_person_id` and the household's `synthetic_household_id`.

## 4. Validate Linkage

Always validate the linked files before using them downstream:

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

The validator checks that every generated person references a generated household
and that each household's `household_size` equals the number of generated people
linked to it.

In the same full-size 2016 QC run noted above, generating 1,000 households with
`PR=24` produced 2,300 people. Linked validation passed with no unknown
households and no household-size mismatches.

## 5. Release Review and Packaging

Models trained from restricted microdata are private working artifacts by
default. Do not distribute them directly.

Audit a model artifact first:

```bash
synthpopcan tree audit-model household-model.json \
  --min-support 50 \
  --max-purity 0.95
```

If the only issue is the expected `private_working` release-class warning, a
reviewed copy can be prepared as a publishable candidate:

```bash
synthpopcan tree prepare-model-release household-model.json \
  --out household-model-publishable.json \
  --manifest-out household-model-release.manifest.json \
  --min-support 50 \
  --max-purity 0.95 \
  --review-note "Reviewed for minimum support, purity, and raw-row metadata."
```

Repeat that review for the person model, then package the pair:

```bash
synthpopcan tree package-linked-models \
  --household-model household-model-publishable.json \
  --person-model person-model-publishable.json \
  --out linked-model-package.json \
  --min-support 50 \
  --max-purity 0.95
```

Packaging is intentionally strict. It refuses models that still have warnings or
errors, validates that the household model is a household model, validates that
the person model is a person model, checks the household-size linkage column, and
embeds both audit reports in the package.

These checks do not prove that a model is absolutely privacy safe. They are a
guardrail so a prepared package carries model provenance, release metadata, and a
review trail before it is considered for sharing or web-app use.

## Advanced Manual Training Views

For experiments, you can still derive training views yourself and train one model
at a time:

```bash
synthpopcan microdata export-training hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --out person-training.csv

synthpopcan tree train person-training.csv \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --weight-column WEIGHT \
  --out person-model.json
```

Use this lower-level route when testing new target sets, conditioning columns, or
model backends. For ordinary linked household/person generation, prefer
`tree train-linked` so the household and person models are derived consistently.
