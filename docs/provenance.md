# Provenance and Research Notes

SynthPopCan workflows produce data, but they also produce decisions. A useful
run should be understandable months later by someone who was not present when
the commands were run.

## What to Keep

For each serious run, keep a small folder like this:

```text
run-2026-06-22-age-sex-ipf/
  README.md
  commands.sh
  seed.csv
  controls.csv
  category-mapping.json
  weights.csv
  fit-report.json
  validation-report.json
```

The exact names do not matter. The habit matters.

## What to Write in `README.md`

Record the research context:

```markdown
# Age/Sex IPF Run

Purpose: Fit a tiny seed population to age-group and sex controls.

Source rows:
- `hierarchical.csv`, fixture standing in for StatCan 2016 hierarchical PUMF.

Controls:
- normalized control table with `AGEGRP` and `SEX` margins.

Choices:
- used `AGEGRP` and `SEX` as seed columns;
- kept source `WEIGHT`;
- did not include tenure in the first fit;
- validated fitted weights rather than expanded rows.

Known limits:
- tiny fixture only;
- not a real geography;
- no household/person linkage check in this IPF-only run.
```

## Command Logs

One simple option is to keep a shell script:

```bash
uv run synthpopcan microdata export-seed \
  tests/fixtures/workflows/microdata_ipf/hierarchical.csv \
  --input-format statcan-2016-hierarchical \
  --columns AGEGRP,SEX \
  --out seed.csv

uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv

uv run synthpopcan ipf fit \
  --seed seed.csv \
  --controls controls.csv \
  --weight-field WEIGHT \
  --out weights.csv \
  --report fit-report.json

uv run synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights \
  --format json
```

This makes a run easier to repeat and review.

## Validation Reports

Keep validation outputs even when they pass. A passing report is evidence that a
specific generated artifact was checked against a specific control table.

Use JSON when the report should be archived or consumed by another tool:

```bash
uv run synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights \
  --format json
```

## Notes for Interpretation

Write down choices that may look obvious now:

- why a table was chosen;
- why a geography was included or excluded;
- why categories were merged or renamed;
- why a column was treated as household-level or person-level;
- whether outputs are fitted weights, expanded rows, generated households, or
  linked generated persons;
- whether a model is private working material or a reviewed publishable
  candidate.

These notes make the output more useful for teaching, peer review, project
handoff, and publication appendices.
