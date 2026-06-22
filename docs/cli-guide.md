# CLI Guide

This guide lists the main command groups and when to use them. For complete
options, run any command with `--help`.

```bash
uv run synthpopcan --help
uv run synthpopcan ipf fit --help
```

## Command Groups

| Command group | Use it when you want to |
| --- | --- |
| `data` | Check whether your local data folders and metadata are in the expected place. |
| `sources` | Inspect local files safely before choosing an adapter. |
| `statcan` | Search, explain, or fetch supported Statistics Canada WDS resources. |
| `controls` | Validate or normalize control totals. |
| `microdata` | Inspect census microdata and export seed or training tables. |
| `ipf` | Check inputs, fit weights, expand rows, and read fit reports. |
| `tree` | Train, generate, audit, and package tree-based population models. |
| `validate` | Check generated outputs against controls or household/person linkage rules. |
| `serve` | Start the local browser app. |

## Human-Readable and JSON Output

Most commands default to readable table output. That is the right choice when a
person is inspecting a file or deciding what to do next.

When a command offers `--format json`, use it for scripts, notebooks, and
repeatable pipelines:

```bash
uv run synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv \
  --format json
```

The two modes are meant to work together: readable defaults for exploration,
machine-readable output for automation.

## A Typical IPF Session

```bash
uv run synthpopcan microdata export-seed hierarchical.csv \
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

uv run synthpopcan ipf report fit-report.json

uv run synthpopcan validate controls \
  --population weights.csv \
  --controls controls.csv \
  --kind weights
```

## A Typical Source-Inspection Session

```bash
uv run synthpopcan sources inspect data/raw
uv run synthpopcan sources schema data/raw/example.csv
uv run synthpopcan sources sample data/raw/example.csv --rows 10
```

This is the safest place to start with unfamiliar files. The goal is to learn
the headers, row shape, delimiter, and likely adapter before using the file in a
workflow.

## A Typical StatCan WDS Session

```bash
uv run synthpopcan statcan wds search "age sex population"
uv run synthpopcan statcan wds explain 98100001
uv run synthpopcan statcan wds fetch 98100001 --out-dir data/raw/statcan/wds
uv run synthpopcan controls wds inspect data/raw/statcan/wds/98100001-eng.zip
```

After inspection, normalize only the dimensions you actually need:

```bash
uv run synthpopcan controls from-wds data/raw/statcan/wds/98100001-eng.zip \
  --dimensions "GEO,Age group,Sex" \
  --count-column VALUE \
  --margin-name age_sex \
  --out controls.csv
```

Then run `ipf check-inputs` before fitting.

## Reading Errors

SynthPopCan tries to fail before writing misleading outputs. Common failures are
usually fixable:

- missing seed column: export or add the column before fitting;
- category mismatch: create a mapping or recode one file;
- non-converged fit: inspect the fit report and check for conflicting controls;
- private path refusal: decide whether `--allow-private` is appropriate.
