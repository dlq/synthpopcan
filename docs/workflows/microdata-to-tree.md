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

## 2. Check Geography Feasibility

Before training one model per province, territory, or agglomeration, run a
feasibility report:

```bash
synthpopcan microdata tree-geography-feasibility \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --geography-column PR
```

Use `--geography-column CMA` for the agglomeration codes exposed by the local
PUMF. The report classifies each geography as `likely`, `borderline`, or
`unlikely` for a publishable-candidate model under the current first-pass
support and purity thresholds.

The report is a planning helper, not a privacy decision. It uses source row
counts, derived household counts, weighted totals, conditioning-cell support, and
target-outcome purity risk for the selected household/person blocks. It also
returns a model-design recommendation for each geography:

- whether to train a separate model, use a reduced target set, or aggregate the
  geography;
- household and person target columns to start with;
- columns to review or coarsen first;
- Canadian census-specific aggregation hints, such as Atlantic or territories
  aggregation for small provinces and territories.

A `likely` geography is a candidate for training and audit; it still needs the
normal model audit and release workflow.

The recommendations are directly actionable with `tree train-linked`. For a
likely geography, train the requested blocks:

```bash
synthpopcan tree train-linked hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --suggested-blocks \
  --geography-column PR \
  --geography-value 24 \
  --target-profile full \
  --household-model-out household-pr24.json \
  --person-model-out person-pr24.json \
  --manifest-out linked-training-pr24.manifest.json
```

For a borderline geography, start with a reduced target profile:

```bash
synthpopcan tree train-linked hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --suggested-blocks \
  --geography-column PR \
  --geography-value 10 \
  --target-profile reduced \
  --household-model-out household-pr10-reduced.json \
  --person-model-out person-pr10-reduced.json \
  --manifest-out linked-training-pr10-reduced.manifest.json
```

For a small province or territory that the advisor marks unlikely, use a minimal
profile only as a cautious local experiment, and prefer an aggregate model for
distribution:

```bash
synthpopcan tree train-linked hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --suggested-blocks \
  --geography-column PR \
  --geography-value 11 \
  --target-profile minimal \
  --household-model-out household-pr11-minimal.json \
  --person-model-out person-pr11-minimal.json \
  --manifest-out linked-training-pr11-minimal.manifest.json
```

## 3. Train Linked Models

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

## 4. Generate Linked Synthetic Rows

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

## 5. Validate Linkage

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

## 6. Release Review and Packaging

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
synthpopcan tree release-readiness \
  --household-model household-model-publishable.json \
  --person-model person-model-publishable.json \
  --training-manifest linked-training.manifest.json \
  --min-support 50 \
  --max-purity 0.95
```

The readiness report distinguishes private working models, likely publishable
candidates, and candidates that need pruning, coarsening, aggregation, or
review before packaging. When a linked training manifest is provided, it also
includes the source summary, column source, target profile, geography filter,
method, random seed, and household/person training summaries.

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
