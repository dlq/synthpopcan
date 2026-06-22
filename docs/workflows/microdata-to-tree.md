# Microdata to Tree Workflow

This fixture workflow shows how the tree generator consumes a derived training view rather than the raw mixed hierarchical microdata file directly.

The tracked files under `tests/fixtures/workflows/microdata_tree/` are deliberately tiny:

- `hierarchical.csv`: a three-person `statcan-2016-hierarchical`-style microdata file with two households.
- `expected-person-training.csv`: the person-level training view produced by `microdata export-training`.

Run the workflow:

```bash
synthpopcan microdata export-training tests/fixtures/workflows/microdata_tree/hierarchical.csv \
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

synthpopcan tree audit-model person-model.json \
  --min-support 50 \
  --max-purity 0.95

synthpopcan tree package-model person-model.json \
  --out person-model-package.json \
  --min-support 50 \
  --max-purity 0.95

synthpopcan tree generate person-model.json \
  --rows 10 \
  --condition TENUR=owner \
  --condition household_size=2 \
  --out synthetic-people.csv

synthpopcan validate tree-output \
  --generated synthetic-people.csv \
  --training person-training.csv \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --weight-field WEIGHT \
  --tolerance 0.5
```

The important boundary is the first command. The 2016 hierarchical PUMF-style source is one mixed person-row file with household identifiers and household context. `microdata export-training` derives the training view that `tree train` expects, including `household_size`.

For linked household/person generation, train a household model and a person model from compatible training views. The person model's conditioning columns must be present on the generated household rows.

```bash
synthpopcan tree generate-linked \
  --household-model household-model.json \
  --person-model person-model.json \
  --households 100 \
  --condition PR=24 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv

synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

The household output has one row per generated household with `synthetic_household_id`. The person output has one row per generated person with `synthetic_person_id` and the household's `synthetic_household_id`. The linked validator checks that each person's household exists and that each household's `household_size` equals the number of generated people linked to it.

`tree train` defaults to the transparent conditional-frequency backend. To train the first sklearn CART backend instead:

```bash
synthpopcan tree train person-training.csv \
  --method cart \
  --level person \
  --target-columns AGEGRP,SEX \
  --conditioning-columns TENUR,household_size \
  --weight-column WEIGHT \
  --min-samples-leaf 50 \
  --max-depth 8 \
  --out person-cart-model.json
```

CART model artifacts are JSON, not pickle files. They store tree structure, category metadata, class distributions, and disclosure-risk metadata, but not raw training rows.

The validation step compares generated-row distributions against the derived training view. It reports target-column distributions, the joint target distribution, optional conditioning-column distributions, and generated category combinations that were not present in the training view. This tiny example generates only one conditioned subset, so it uses a loose tolerance; larger unfiltered runs should use a tighter tolerance.

The audit step is a release-oriented check on the model artifact itself. It does not make the model publishable; it reports support, purity, dominant outcomes for high-purity groups/leaves, raw-row/source-id flags, release class, and issues that should be reviewed before any packaging or distribution workflow.

The package step is intentionally strict. It refuses to write a package while the audit has any warnings or errors, including the default `private_working` release class warning. Later packaging work should define how a reviewed model becomes a publishable candidate.
