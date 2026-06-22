# Data and Privacy

SynthPopCan is designed around a simple rule: keep real source data under local
control, and commit only code, documentation, tiny fixtures, and public-safe
metadata.

## Local Data Layout

By default, SynthPopCan looks under `data/`:

```text
data/
  raw/
    statcan/
  private/
```

Use `data/raw/` for source material that is public or redistributable in your
own project context. Use `data/private/` for restricted, sensitive, or
non-redistributable files.

Check the expected layout:

```bash
uv run synthpopcan data doctor
```

Use a different data root for a shared lab machine or external disk:

```bash
uv run synthpopcan data doctor --data-root /path/to/project-data
```

Or set it for repeated work:

```bash
export SYNTHPOPCAN_DATA_ROOT=/path/to/project-data
uv run synthpopcan data doctor
```

## Inspect Before Parsing

Before writing an adapter or running a workflow on a new file, inspect the file
structure:

```bash
uv run synthpopcan sources inspect data/raw
uv run synthpopcan sources schema data/raw/example.csv
uv run synthpopcan sources sample data/raw/example.csv --rows 5
```

Sampling private data is blocked by default for paths under `data/private`.
Use `--allow-private` only when you intentionally want to inspect those rows on
your own machine:

```bash
uv run synthpopcan sources sample data/private/example.csv \
  --rows 5 \
  --allow-private
```

## What Not to Commit

Do not commit:

- raw census microdata;
- private extracts;
- full generated outputs derived from restricted files;
- model artifacts trained from restricted data unless they have been reviewed
  and prepared for release;
- local reports that include private row-level examples.

Small fixtures under `tests/fixtures/` are intentionally tiny and artificial.
Use them for documentation, tests, and examples.

## Model Release Review

Linked tree model artifacts can contain information about the data used to train
them. Treat models trained from restricted microdata as private working files by
default.

Use the tree audit and release commands before considering any model package for
sharing:

```bash
uv run synthpopcan tree audit-model household-model.json \
  --min-support 50 \
  --max-purity 0.95

uv run synthpopcan tree release-readiness \
  --household-model household-model-publishable.json \
  --person-model person-model-publishable.json \
  --training-manifest linked-training.manifest.json \
  --min-support 50 \
  --max-purity 0.95
```

These commands are guardrails, not a legal or ethical review by themselves.
Record the source, access conditions, and review note before packaging.
