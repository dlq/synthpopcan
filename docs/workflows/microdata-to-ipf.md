# Microdata to IPF Workflow

This fixture workflow shows how the seed columns and control dimensions must line up.

The tracked files under `tests/fixtures/workflows/microdata_ipf/` are deliberately tiny:

- `hierarchical.csv`: a two-person `statcan-2016-hierarchical`-style microdata file.
- `controls.csv`: normalized controls whose dimensions match the exported seed columns.
- `expected-seed.csv`: the seed file produced by `microdata export-seed`.

Run the workflow:

```bash
synthpopcan microdata export-seed tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

synthpopcan ipf fit \
  --seed seed.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json

synthpopcan validate controls \
  --population weights.csv \
  --controls tests/fixtures/workflows/microdata_ipf/controls.csv \
  --kind weights
```

The controls use `AGEGRP` and `SEX` because those are the exported seed columns. The category values also match: `adult`, `child`, `F`, and `M`. If either the column names or category labels differ, IPF cannot fit the controls without a mapping step.
