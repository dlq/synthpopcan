# Data

The `data` command group checks **local data setup** and inspects **source
files** before they enter a workflow.

## Concept

SynthPopCan expects real source data to **stay local**. Raw and private files
should **not be committed to git**. The default local layout is:

```text
data/
  raw/                  # authoritative public source downloads
    statcan/census/
  derived/
    statcan/census/      # prepared public-data artifacts
    models/              # durable release candidates
  work/                  # disposable builds and experiments
  private/
    sources/             # restricted or access-controlled inputs only
```

Use `data/raw` for **public or redistributable files** in the project context.
Use `data/derived` for **reusable subsets, conversions, and durable model
artifacts**; keep their source and transformation provenance and do not present
them as raw official data. Use `data/work` for **disposable or restartable
intermediates**, including model-build workspaces and development experiments.
Use `data/private/sources` only for
**restricted or access-controlled source files**. Privacy and derivation are
separate properties: a generated artifact belongs under `derived`, even when it
must remain local and uncommitted.

The local Statistics Canada cache uses the same product-oriented layout for
each census vintage, but the local inventories are not assumed to be complete
or symmetrical:

```text
data/
  raw/statcan/census/
    2016/
      pumf/{hierarchical,individual}/
      metadata/pumf/{hierarchical,individual}/
      profiles/{ct,ada,csd/national}/
    2021/
      pumf/{hierarchical,individual}/
      metadata/pumf/{hierarchical,individual}/
      profiles/{ct,ada,csd/national}/
      geography/relationships/
  derived/statcan/census/
    2016/
      boundaries/
      profiles/
      pumf/individual/subsets/
    2021/
      boundaries/
  derived/models/release-assets/
  work/models/builds/
  work/small-area/experiments/
  private/sources/{canue,cptp,mavan,monnet,topo}/
```

Each vintage root has a `manifest.json` inventory of the products actually
present. At present, both vintages contain the national hierarchical and
individual PUMFs plus CT, ADA, and national CSD Census Profiles. The 2021 cache
additionally contains the national Dissemination Geographies Relationship
File. Matching product coverage does not imply column-identical schemas:
adapters must still account for the identifiers, characteristic codes, and
count/rate columns used by each vintage.

The national PUMFs, canonical Census Profile downloads, and official
relationship files stay under `raw`. Regional extracts, flattened tables,
notebook-produced reusable intermediates and prepared GeoJSON stay under
`derived`. Disposable model builds and exploratory synthesis outputs stay under
`work`. Each provider and product family is organized by census vintage before
product type.

`data doctor` checks whether the expected directories exist. `data inspect`,
`data schema`, and `data sample` inspect the actual files within that layout —
**what files are present**, **what their columns are**, and **what a few rows
look like**. `data example` writes tiny fictional files for a documented
teaching workflow; these files are not source data.
Use {doc}`statcan` to find and fetch public Statistics Canada sources to
populate the layout. If a file is ready to become a control table, move to
{doc}`controls`.

## Public Repository Policy

The public repository should **not contain raw or access-controlled source
data**.
This includes Census microdata files, local Downloads snapshots, private
research datasets, and generated full-population CSV outputs.

Reviewed model packages are handled separately from raw data. A package may be
distributed when it is intentionally prepared for **public use**, contains
**provenance and review metadata**, and passes the current model-release checks.
Large published packages should be attached as GitHub Release assets and fetched
on demand with `synthpopcan models fetch MODEL_ID`, not bundled into the default
Python install.

Model packages are still derived research artifacts, not raw data. Researchers
preparing a package should follow {doc}`tree`; repository maintainers should
also follow the model-safety and release-asset procedures in
[CONTRIBUTING.md](https://github.com/dlq/synthpopcan/blob/main/CONTRIBUTING.md#data-and-model-safety).

SynthPopCan is independent research software. It is not affiliated with or
endorsed by Statistics Canada or the Government of Canada.

## Getting Started

**Mixed runnable and template commands.** `data doctor` is safe to run as shown.
For `data inspect`, `data schema`, and `data sample`, replace the example path
with a file or directory in our own project.

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

The default data root is `data/` relative to the current directory. If the data
lives elsewhere, pass `--data-root` or set the environment variable so we do not
have to repeat it:

```bash
export SYNTHPOPCAN_DATA_ROOT=/path/to/data
synthpopcan data doctor
```

## Subcommands

### `data example`

Writes small fictional files for a public teaching workflow. The current `ipf`
example contains `seed.csv` and `controls.csv`, works without a source checkout
or network connection, and is used by the [IPF](ipf.md) walkthrough.

```bash
synthpopcan data example ipf --out-dir synthpopcan-ipf-example
```

Options:

- `NAME`: currently `ipf`.
- `--out-dir PATH`: required destination directory.
- `--force`: replace existing example files. Without this flag, SynthPopCan
  refuses to overwrite them.

These values are designed to make the mechanics visible. They do not represent
a real census population and should not be reused as research inputs.

### `data doctor`

Checks the local data directory layout and reports which expected paths are
present and which are missing. The expected subdirectories under the data root
are:

- `raw/statcan/` — Statistics Canada source files fetched with `statcan` commands
- `private/` — restricted files that should not be committed to git

Each path is reported as present or missing. A missing path is not an error in
itself — it means that part of the layout has not been created yet. The report
is a quick way to confirm the working directory is set up before
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
located under `data/private`. Use this to get an overview of what is present
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
or export command to confirm it has the columns we expect and is not
mis-encoded or using an unexpected delimiter.

```bash
synthpopcan data schema data/raw/example.csv
synthpopcan data schema data/raw/example.csv --format json
```

### `data sample`

Prints a small number of rows from a file so we can see its actual structure.

```{admonition} Sampling private data writes it to the terminal
:class: warning

Because `data sample` outputs real source data, files under `data/private`
require `--allow-private`. This deliberate friction helps prevent us from
printing restricted content accidentally in a shared terminal, log, or
screen-share session.
```

```bash
synthpopcan data sample data/raw/example.csv --rows 10
```

```bash
synthpopcan data sample data/private/sources/example.csv \
  --rows 5 \
  --allow-private
```

## Troubleshooting

**The data root is wrong:** pass `--data-root` for one command or set
`SYNTHPOPCAN_DATA_ROOT`.

**Private path refused by `data sample`:** this is intentional. Add
`--allow-private` only for local inspection and only when we are certain the
output will not be shared or logged.

**Columns are unexpected:** do not try to force a file into an adapter using
guessed column names. Use `data schema` to read the exact headers, then write
the appropriate `--dimensions` or `--columns` flags explicitly.

**Private files appear in source paths:** keep source inputs under
`data/private/sources` and do not paste private rows into docs, issues, or
shared reports.

## Further Reading

- Background concept:
  [Statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control).
- Tania Carvalho, Nuno Moniz, Pedro Faria, and Luis Antunes,
  [Survey on Privacy-Preserving Techniques for Data Publishing](https://arxiv.org/abs/2201.08120).
