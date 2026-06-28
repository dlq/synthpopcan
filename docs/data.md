# Data

The `data` command group checks local data setup and inspects source files
before they enter a workflow.

## Concept

SynthPopCan expects real source data to stay local. Raw and private files should
not be committed to git. The default local layout is:

```text
data/
  raw/
    statcan/
  private/
```

Use `data/raw` for public or redistributable files in your project context. Use
`data/private` for restricted files.

`data doctor` checks whether the expected directories exist. `data inspect`,
`data schema`, and `data sample` inspect the actual files within that layout —
what files are present, what their columns are, and what a few rows look like.
Use {doc}`statcan` to find and fetch public Statistics Canada sources to
populate the layout. If a file is ready to become a control table, move to
{doc}`controls`.

## Public Repository Policy

The public repository should not contain raw or access-controlled source data.
This includes Census microdata files, local Downloads snapshots, private
research datasets, and generated full-population CSV outputs.

Reviewed model packages are handled separately from raw data. A package may be
distributed when it is intentionally prepared for public use, contains
provenance and review metadata, and passes the current model-release checks.
Large published packages should be attached as GitHub Release assets and fetched
on demand with `synthpopcan models fetch MODEL_ID`, not bundled into the default
Python install.

Model packages are still derived research artifacts. Before publishing one:

- check that it contains no raw rows, source identifiers, or private paths;
- confirm the source citation and redistribution note are clear;
- run the relevant tree-model audit and release workflow;
- inspect package metadata with `synthpopcan tree inspect-package`;
- verify large package files are outside the installed package and listed in
  the model registry with a checksum.

SynthPopCan is independent research software. It is not affiliated with or
endorsed by Statistics Canada or the Government of Canada.

## Getting Started

`data doctor` checks whether the expected subdirectories exist under the data
root. Run it at the start of a new project to confirm the layout is correct, or
after moving files to confirm nothing is missing:

```bash
synthpopcan data doctor
```

Once the layout is confirmed, inspect what files are present under a directory
without opening any of them:

```bash
synthpopcan data inspect data/raw
```

Check the column headers, delimiter, and encoding of a specific file before
writing `--dimensions` or `--columns` flags for other commands:

```bash
synthpopcan data schema data/raw/example.csv
```

Sample a small number of rows to see the actual data shape:

```bash
synthpopcan data sample data/raw/example.csv --rows 5
```

The default data root is `data/` relative to the current directory. If your
data lives elsewhere, pass `--data-root` or set the environment variable so you
do not have to repeat it:

```bash
export SYNTHPOPCAN_DATA_ROOT=/path/to/data
synthpopcan data doctor
```

## Subcommands

### `data doctor`

Checks the local data directory layout and reports which expected paths are
present and which are missing. The expected subdirectories under the data root
are:

- `raw/statcan/` — Statistics Canada source files fetched with `statcan` commands
- `private/` — restricted files that should not be committed to git

Each path is reported as present or missing. A missing path is not an error in
itself — it just means that part of the layout has not been created yet. The
report is a quick way to confirm your working directory is set up before
starting a workflow that depends on those paths.

```bash
synthpopcan data doctor
synthpopcan data doctor --data-root /path/to/data
synthpopcan data doctor --format json
```

Options:

- `--data-root PATH`: override the data root (default: `data/` relative to
  current directory, or `SYNTHPOPCAN_DATA_ROOT` if set).
- `--format table|json`: `table` gives a human-readable report; `json` is
  useful for scripting or logging.

### `data inspect`

Lists the files found under a given path, organized by subdirectory. Reports
file counts and detected file types (CSV, ZIP, JSON, etc.) and flags any files
located under `data/private`. Use this to get an overview of what you have
before deciding which files to inspect more closely. Does not open or read any
file contents.

```bash
synthpopcan data inspect data/raw
synthpopcan data inspect data/raw --format json
```

### `data schema`

Inspects a single file and reports its column headers, detected delimiter
(comma, tab, pipe, etc.), detected encoding, and approximate row count. Does
not print any data rows. Use this before passing a file to any normalization
or export command to confirm it has the columns you expect and is not
mis-encoded or using an unexpected delimiter.

```bash
synthpopcan data schema data/raw/example.csv
synthpopcan data schema data/raw/example.csv --format json
```

### `data sample`

Prints a small number of rows from a file so you can see its actual structure.
Because sample outputs real source data, files under `data/private` require
`--allow-private` — this is a deliberate friction to prevent accidentally
printing restricted content to a shared terminal, log, or screen-share session.

```bash
synthpopcan data sample data/raw/example.csv --rows 10
```

```bash
synthpopcan data sample data/private/example.csv \
  --rows 5 \
  --allow-private
```

## Troubleshooting

**The data root is wrong:** pass `--data-root` for one command or set
`SYNTHPOPCAN_DATA_ROOT`.

**Private path refused by `data sample`:** this is intentional. Add
`--allow-private` only for local inspection and only when you are certain the
output will not be shared or logged.

**Columns are unexpected:** do not try to force a file into an adapter using
guessed column names. Use `data schema` to read the exact headers, then write
the appropriate `--dimensions` or `--columns` flags explicitly.

**Private files appear in source paths:** keep them under `data/private` and do
not paste private rows into docs, issues, or shared reports.

## Further Reading

- Background concept:
  [Statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control).
- Tania Carvalho, Nuno Moniz, Pedro Faria, and Luis Antunes,
  [Survey on Privacy-Preserving Techniques for Data Publishing](https://arxiv.org/abs/2201.08120).
