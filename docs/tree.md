# Tree Models

Tree commands train and use tree-based synthetic population models. They are
most useful when you need generated rows with multivariate structure, or when
households and people need to remain linked.

## Concept

An IPF workflow reweights existing seed rows. A tree workflow learns patterns
from training rows and generates new rows. In SynthPopCan, tree models can be:

- flat person or household models from a training CSV;
- linked household/person models from hierarchical microdata;
- private working artifacts;
- reviewed publishable-candidate artifacts after audit and release checks.

Treat models trained from restricted microdata as private unless they have been
audited, reviewed, and packaged with provenance.

SynthPopCan currently uses transparent frequency-based and CART-style tree
models. CART models are useful here because they expose conditional splits that
can be audited more easily than many opaque generative models, but the audit
step is still necessary.

### What a Tree Model Is

A decision tree is a model made from branching questions. Each question splits
the training rows into smaller groups. In a classification tree, the end of a
branch is called a leaf, and the leaf contains the observed outcomes for records
that reached that point.

For synthetic population work, a simplified person model might behave like this:

```text
Is tenure owner?
├─ yes: use the age/sex distribution observed among owner households
└─ no:  use the age/sex distribution observed among non-owner households
```

A deeper tree might also split by province, household size, or age group. That
extra detail can preserve useful structure, but it also reduces the number of
training rows behind each branch. A model that splits too finely may look
sophisticated while relying on only a handful of examples.

SynthPopCan has two tree-family model types:

- `conditional-frequency`: groups rows by the conditioning columns and samples
  from the observed target outcomes in each group. This is transparent and easy
  to audit, but sparse groups can be fragile.
- `cart`: trains a CART-style decision tree using scikit-learn. This can merge
  or split patterns more flexibly than exact frequency groups, but it still
  needs support, purity, and validation checks.

The scikit-learn decision-tree guide explains CART-style decision trees as
models that split records by feature values to predict a target class. In
SynthPopCan, the point is not prediction for its own sake. The point is to
generate plausible categorical rows while preserving enough structure to support
interpretation and audit.

### What a Forest Model Is

A forest model, usually called a random forest, combines many decision trees.
Each tree is trained on a different sample of rows or a different subset of
columns, and the forest combines their results. In predictive modelling this can
reduce the instability of one tree.

SynthPopCan does not currently train forest models. That is deliberate. A forest
can be useful, but it is harder to explain to a humanities or digital-humanities
reader because there is no single branch or leaf to inspect. For this project,
the first priority is a model artifact that can be audited, packaged with
provenance, and discussed plainly: what columns conditioned generation, how much
support each group or leaf had, and whether any group looked too revealing.

If forest-style models are added later, they should come with stronger
diagnostics, clear variable-importance reporting, and release checks that do not
depend on reading one tree by eye.

### What Makes a Tree Model Bad

A bad tree model is not just a model that fails to run. It is a model that
generates rows that are misleading, unstable, or unsafe to share. Common
problems include:

- **Too little support:** a group or leaf is based on too few training records.
  Generated rows then depend on accidents of the sample rather than a stable
  pattern.
- **Overly pure groups:** one outcome dominates a small group. This can signal
  memorization, especially when the conditioning columns are detailed.
- **Overfitting:** the model follows the training rows too closely and loses the
  broader structure the synthetic population is supposed to represent.
- **Underfitting:** the model is too coarse and washes out important
  relationships, such as household size by tenure or age structure by geography.
- **Target leakage:** identifier-like columns, geography codes at too fine a
  level, or derived columns that already encode the answer make generation look
  accurate for the wrong reason.
- **Wrong population universe:** training rows and intended output describe
  different populations, years, geographies, or inclusion rules.
- **Bad column roles:** a target column is accidentally also used as a
  conditioning column, or a household-level attribute is treated as if it varied
  by person.
- **Sparse geography:** splitting by a small region can produce weak support
  even if the national training file is large.
- **Broken linkage:** a person model may generate people whose attributes do not
  match the household rows they are linked to, or household sizes may not match
  the generated number of people.
- **Missing provenance:** without source notes, commands, random seeds, and
  validation reports, readers cannot tell what choices shaped the output.

These are methodological issues, not just software errors. Gargiulo and
co-authors emphasize the importance of household structure in synthetic
population generation, and privacy-preserving data-publishing surveys describe
the recurring tradeoff between utility and disclosure risk. SynthPopCan's audit
commands are meant to make those issues visible before a model is treated as
usable.

### Reading Support and Purity

`tree audit-model` reports support and purity because they are practical warning
signals.

Support is the number or weighted count of training rows behind a group or leaf.
Low support means the model has little evidence for that branch. A support value
of 3 may be acceptable in a private experiment, but it is a poor basis for a
shareable model.

Purity is the share of the dominant outcome in a group or leaf. A leaf where 98%
of records have the same outcome is not automatically wrong. But if that leaf is
also small, the model may be close to revealing a rare pattern from the training
data.

Use these measures together:

- low support and high purity is the strongest warning;
- low support and mixed outcomes is unstable;
- high support and high purity may describe a real common pattern;
- high support and mixed outcomes is usually safer but may generate noisy rows.

The default audit thresholds are conservative starting points, not universal
rules. Choose stricter thresholds for public sharing, sensitive columns, or
small geographies.

### When a Tree Model Is Methodologically Weak

A tree model can pass basic software checks and still be weak for research. The
most common problem is confusing a model that can generate rows with a model
that supports the intended interpretation.

Watch for these patterns:

- **Predictive-looking output without a prediction question.** Tree models can
  sound like predictive models, but SynthPopCan usually uses them to preserve
  categorical structure for synthetic generation. Do not interpret a split as a
  causal claim.
- **Too many conditioning columns.** Every extra conditioning column can make
  groups smaller. A model conditioned on province, tenure, household size, age,
  sex, language, and income may be less stable than a simpler model.
- **Important relationships left out.** A model that omits household size,
  tenure, or geography may generate rows that look plausible one column at a
  time but fail as households or communities.
- **Rare categories treated as ordinary categories.** Sparse identity,
  language, migration, or geography categories may need aggregation or private
  handling rather than direct modelling.
- **Training data treated as neutral.** The model learns from the training
  sample. If the source data has exclusions, survey design effects, coding
  choices, or historical bias, those choices shape the generated rows.
- **Release checks treated as ethics review.** `tree audit-model` can flag
  support, purity, raw-row metadata, and source identifiers. It cannot decide
  whether a generated population should be used for a sensitive interpretive
  claim.
- **Model artifacts treated as harmless.** A trained model is not automatically
  safe just because it is JSON rather than a CSV of source records. Splits,
  leaf counts, class summaries, encoders, and package metadata can still reveal
  rare paths or small subgroups.
- **Validation against the training view only.** A tree-output validation report
  can compare generated rows to the training distribution. It does not prove the
  model matches an external population unless external controls are also used.
- **Linked rows validated only mechanically.** Household/person linkage can be
  internally consistent while still sociologically implausible if the household
  and person models were trained with poor column choices.

Additional issues to consider before trusting a tree model:

- **Instability:** a single decision tree can change a lot when the training
  rows, random seed, or selected columns change. Forests reduce some instability
  by averaging many trees, but they also make the model harder to inspect.
- **High-cardinality columns:** postal codes, small geographies, detailed
  occupations, or many-category identity variables can create tiny branches and
  disclosure risk.
- **Class imbalance:** rare outcomes may be ignored, exaggerated, or copied too
  directly, depending on the model and thresholds.
- **Out-of-domain conditions:** asking a model to generate for a condition it
  barely saw, or never saw, can force fallback behaviour that looks valid in a
  CSV but has weak evidence.
- **Missing values are information:** blank, unknown, not applicable, and
  refused responses are not interchangeable. Treating them all as ordinary
  categories can distort the generated population.
- **Survey weights shape training:** if training rows have weights, the model is
  learning a weighted view of the source. If weights are ignored, common and rare
  groups may be misrepresented.
- **Unpruned trees memorize too much:** default tree settings can grow many
  small leaves. Use deliberate leaf-size, depth, category-coarsening, and pruning
  choices for any model that might later be packaged.
- **Donor-style generation can leak:** methods that draw directly from observed
  records inside a terminal node need special caution. If a leaf contains only a
  few donors, synthetic rows may be too close to source rows.
- **Column encoding changes meaning:** collapsed categories, derived variables,
  and text labels are modelling decisions. A generated value is only as clear as
  the category system behind it.
- **Transfer is not automatic:** a model trained on one geography, period, or
  population may not transfer to another. This is especially important when
  using one region to generate another because local structure matters.
- **Randomness affects interpretation:** generated rows depend on random seeds.
  If a conclusion changes when the seed changes, the model is too unstable for
  that claim.
- **External validity is separate:** matching the training distribution does not
  prove the generated population matches public controls or the historical world
  being studied.

### Model Release And Disclosure Risk

SynthPopCan separates private working models from publishable-candidate models
because trained models can carry disclosure risk. A safe-looking artifact can
still contain or imply sensitive information through very small leaves,
geography-specific paths, rare target values, source identifiers, bootstrap
indices, donor lists, or raw-row fragments.

For linked household/person models, the risk is higher than for a flat person
table. A household composition can be distinctive even when each field is
ordinary on its own. Audit linked models as household signatures: household
attributes plus the ordered or summarized composition of generated people.

Practical release rules:

- keep restricted-source models private by default;
- inspect the actual serialized artifact, not only the training options;
- require non-trivial support in every group or leaf;
- reject source rows, row IDs, household IDs, bootstrap indices, and donor lists
  in publishable artifacts;
- use model cards or release manifests to state intended use, out-of-scope use,
  source description, parameters, validation results, limitations, and caveats;
- do not claim anonymity or legal privacy safety merely because
  `prepare-model-release` succeeded.

Good tree modelling is usually iterative. Start with fewer columns, inspect the
training view, generate a small sample, validate distributions and linkage, then
add detail only when the support remains adequate and the extra detail matters
for the research question.

### Practical Signs to Step Back

Pause and reconsider the model design when:

- the audit report shows many low-support groups or leaves;
- generated rows repeat the same combinations too often;
- generated rows contain combinations that subject-matter readers find
  implausible;
- small changes to the random seed noticeably change the story;
- a small geography needs much stricter thresholds than the model can satisfy;
- the model has to include sensitive or identifier-like columns to produce
  plausible output;
- the model behaves differently after a harmless-looking change to the seed,
  training sample, or random seed;
- the model depends on a very detailed category system that readers will not be
  able to interpret;
- the generated output passes internal validation but fails against an external
  table or domain expectation;
- the release narrative depends on "the tool passed" rather than on source,
  modelling, and validation evidence.

In those cases, the next step is usually not a bigger model. It is often a
clearer research question, broader categories, a larger geography, fewer target
columns, or a decision to keep the artifact private.

## Getting Started: Linked Household and Person Models

Inspect suggested columns:

```bash
synthpopcan microdata suggest-tree-columns \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical
```

Train linked models:

```bash
synthpopcan tree train-linked \
  tests/fixtures/workflows/linked_tree/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --suggested-blocks \
  --household-model-out household-model.json \
  --person-model-out person-model.json \
  --manifest-out linked-training.manifest.json \
  --random-seed 7
```

Generate linked rows:

```bash
synthpopcan tree generate-linked \
  --household-model household-model.json \
  --person-model person-model.json \
  --households 100 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --manifest-out synthetic-linked.manifest.json \
  --random-seed 13
```

Validate linkage:

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

Audit the models before thinking about release or reuse:

```bash
synthpopcan tree audit-model household-model.json \
  --min-support 50 \
  --max-purity 0.95

synthpopcan tree audit-model person-model.json \
  --min-support 50 \
  --max-purity 0.95
```

If the audit reports low support, high purity, or private release status, treat
the model as a working artifact. Reduce the column profile, aggregate geography,
or keep the model private.

## Subcommands

### `tree train`

Trains one flat model from a CSV training sample.

```bash
synthpopcan tree train person-training.csv \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --weight-column WEIGHT \
  --out person-model.json
```

Options include `--method conditional-frequency|cart`, `--random-seed`,
`--min-support`, `--min-samples-leaf`, and `--max-depth`.

Use `conditional-frequency` when you want a direct, inspectable relationship
between conditioning columns and generated target outcomes. Use `cart` when exact
conditioning groups are too sparse and a decision tree can pool similar cases.
Neither method removes the need for validation.

### `tree train-linked`

Trains household and person models from mixed hierarchical microdata.

```bash
synthpopcan tree train-linked hierarchical.csv \
  --suggested-blocks \
  --geography-column PR \
  --geography-value 24 \
  --target-profile reduced \
  --household-model-out household-pr24.json \
  --person-model-out person-pr24.json \
  --manifest-out linked-training-pr24.manifest.json
```

The linked workflow is useful when household and person rows need to agree with
each other. The household model generates household attributes first. The person
model then generates the people inside each household using shared conditioning
columns, such as household size or tenure.

Bad linked models often come from mixing levels. For example, a person-level
attribute should not be used as if it were constant for the household unless the
training export has explicitly derived a household-level summary.

### `tree generate`

Generates flat rows from one model.

```bash
synthpopcan tree generate person-model.json \
  --rows 100 \
  --condition PR=24 \
  --out synthetic-persons.csv \
  --manifest-out synthetic-persons.manifest.json
```

### `tree generate-linked`

Generates households first and people second from separate linked models.

```bash
synthpopcan tree generate-linked \
  --household-model household-model.json \
  --person-model person-model.json \
  --households 1000 \
  --condition PR=24 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv
```

### `tree audit-model`

Audits a model artifact for release-oriented risk checks.

```bash
synthpopcan tree audit-model household-model.json \
  --min-support 50 \
  --max-purity 0.95
```

Important options:

- `--min-support`: minimum acceptable support for each group or leaf.
- `--max-purity`: warning threshold for dominant-outcome purity.

The audit also checks whether model metadata says raw rows or source identifiers
may be present. A model with those flags should not be treated as a release
candidate.

### `tree package-model`

Packages a single flat tree model only after `audit-model` passes without
warnings.

```bash
synthpopcan tree package-model household-model.json \
  --out household-model-package.json \
  --min-support 50 \
  --max-purity 0.95
```

This command is intentionally stricter than `audit-model`: an audit report can
be useful even when it contains warnings, but `package-model` refuses to write a
package until the audit is clean. For linked household/person work, use
`prepare-model-release`, `release-readiness`, and `package-linked-models`
instead.

### `tree prepare-model-release`

Writes a publishable-candidate copy after release checks.

```bash
synthpopcan tree prepare-model-release household-model.json \
  --out household-model-publishable.json \
  --manifest-out household-model-release.manifest.json \
  --review-note "Reviewed for minimum support, purity, and raw-row metadata."
```

### `tree release-readiness`

Reports whether linked models are ready for linked packaging.

```bash
synthpopcan tree release-readiness \
  --household-model household-model-publishable.json \
  --person-model person-model-publishable.json \
  --training-manifest linked-training.manifest.json
```

### `tree package-linked-models`

Packages reviewed household/person models with provenance and audit reports.

```bash
synthpopcan tree package-linked-models \
  --household-model household-model-publishable.json \
  --person-model person-model-publishable.json \
  --training-manifest linked-training.manifest.json \
  --source-provenance source-provenance.json \
  --review-note "Reviewed for release after readiness report." \
  --out linked-model-package.json
```

### `tree generate-from-package`

Generates linked rows directly from a reviewed package.

```bash
synthpopcan tree generate-from-package linked-model-package.json \
  --households 1000 \
  --condition PR=24 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv
```

### `tree inspect-package`

Prints a package summary without dumping embedded model payloads.

```bash
synthpopcan tree inspect-package linked-model-package.json
synthpopcan tree inspect-package linked-model-package.json --format json
```

## Troubleshooting

**Audit reports low support:** reduce the number of conditioning columns, use a
larger geography, combine categories, or switch from an exact
`conditional-frequency` model to a CART model with sensible leaf-size settings.

**Audit reports high purity:** inspect the conditioning columns. Remove
identifier-like columns, overly detailed geography, or columns that effectively
encode the target.

**Generated rows look too repetitive:** the model may be underfit, or the
conditioning values may route generation into one narrow group. Add appropriate
conditioning columns only if the training data has enough support.

**Generated rows look too detailed or too realistic:** the model may be
overfit. Increase `--min-support`, increase `--min-samples-leaf`, reduce
`--max-depth`, combine categories, or keep the model private.

**Model is very large:** review target columns and consider reduced or minimal
profiles. Large models can signal overly detailed categories.

**Linked validation fails:** check household ID columns and household-size
fields before interpreting the generated data.

**Package refuses to write:** inspect audit warnings, source provenance, release
manifests, and review notes.

## Further Reading

- scikit-learn,
  [Decision Trees user guide](https://scikit-learn.org/stable/modules/tree.html),
  for background on CART-style models.
- Floriana Gargiulo and co-authors,
  [An iterative approach for generating statistically realistic populations of households](https://arxiv.org/abs/0912.2826),
  for why household structure matters.
- Stanislav Borysov, Jeppe Rich, and Francisco Pereira,
  [Scalable Population Synthesis with Deep Generative Modeling](https://arxiv.org/abs/1808.06910),
  for a contrasting generative-model approach.
- Tania Carvalho, Nuno Moniz, Pedro Faria, and Luis Antunes,
  [Survey on Privacy-Preserving Techniques for Data Publishing](https://arxiv.org/abs/2201.08120),
  for the disclosure-control tradeoff between privacy protection and utility.
