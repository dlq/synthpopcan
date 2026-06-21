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

synthpopcan tree generate person-model.json \
  --rows 10 \
  --condition TENUR=owner \
  --condition household_size=2 \
  --out synthetic-people.csv
```

The important boundary is the first command. The 2016 hierarchical PUMF-style source is one mixed person-row file with household identifiers and household context. `microdata export-training` derives the training view that `tree train` expects, including `household_size`.

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
