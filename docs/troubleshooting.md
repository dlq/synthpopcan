# Troubleshooting

This page lists common problems and the first checks to run.

## `uv run synthpopcan --help` Fails

First install the project dependencies from the repository root:

```bash
uv sync
```

Then try:

```bash
uv run synthpopcan --help
```

If you are working in a restricted environment and `uv` cannot write to its
default cache, set a cache directory you can write to:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run synthpopcan --help
```

## A Control Column Is Missing from the Seed

Run:

```bash
uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv
```

If the report says a control dimension is missing, IPF cannot use that control
yet. Export the column into the seed, recode a source column, add it through a
model or lookup, or choose a different control table.

## Categories Do Not Match

Examples:

- `Female` in a StatCan table but `F` in the seed;
- `0 to 4 years` in a source table but `age_000_004` in the seed;
- geography codes with different padding or labels.

Create a mapping or recode one side before fitting. For WDS ZIPs, start with:

```bash
uv run synthpopcan controls wds mapping-template table.zip \
  --dimensions "Age group,Sex" \
  --out categories-template.json
```

Fill the blank values, then pass the mapping to `controls from-wds`.

## IPF Does Not Converge

Write and inspect a report:

```bash
uv run synthpopcan ipf fit \
  --seed seed.csv \
  --controls controls.csv \
  --out weights.csv \
  --report fit-report.json

uv run synthpopcan ipf report fit-report.json
```

Common causes:

- inconsistent control totals;
- sparse seed coverage;
- categories present in controls but barely present in the seed;
- using a control table that belongs to a different geography or universe.

By default, SynthPopCan does not write weights for a non-converged fit. Use
`--allow-nonconverged` only when you intentionally want to inspect a failed fit.

## Expanded Output Is Huge

Use weights unless another tool requires expanded rows:

```bash
uv run synthpopcan ipf fit \
  --seed seed.csv \
  --controls controls.csv \
  --out weights.csv
```

Expand later:

```bash
uv run synthpopcan ipf expand \
  --weights weights.csv \
  --out synthetic.csv
```

## Private Data Appears in a Path

Commands that sample local files refuse `data/private` unless you explicitly
allow it:

```bash
uv run synthpopcan sources sample data/private/example.csv \
  --rows 5 \
  --allow-private
```

Use this only for local inspection. Do not paste private rows into issues,
documentation, commits, or shared reports.
