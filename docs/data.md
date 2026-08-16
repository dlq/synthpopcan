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
    geodata/             # maintainer-built display-boundary release assets
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

Each vintage root can have a `manifest.json` inventory of the products actually
present in a research environment. A full project cache may contain national
hierarchical and individual PUMFs plus CT, ADA, and national CSD Census
Profiles for both vintages. A national 2021 DA workflow additionally needs all
six regional DA Census Profiles, the national DA boundary, and the final
Dissemination Geographies Relationship File. None of these large source files
is installed with SynthPopCan or tracked in git. Matching product coverage does
not imply column-identical schemas:
adapters must still account for the identifiers, characteristic codes, and
count/rate columns used by each vintage.

The national PUMFs, publisher-issued national or regional Census Profile
downloads, and official relationship files stay under `raw`. The shared 2021
national small-area planner reads the six regional DA Profile products or the
single national ADA Profile product through level-specific adapters; these
source-layout differences do not change its batching and execution contract.
Project-created
regional extracts, flattened tables, notebook-produced reusable intermediates,
and prepared GeoJSON stay under `derived`. Disposable model builds and
exploratory synthesis outputs stay under `work`. Each provider and product
family is organized by census vintage before product type.

The end-user cache managed by {doc}`geodata` is separate from this repository
layout. It stores verified published display assets under the platform's user
cache directory (or `SYNTHPOPCAN_GEODATA_CACHE`), not under `data/raw`. Those
files are derived visualization geometry, not canonical Statistics Canada
source boundaries.

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

## Source Licensing And Attribution

Statistics Canada public use microdata files (PUMFs) are released under the
[Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence).
That licence defines "Information" to include public use microdata files, and
grants a worldwide, royalty-free, non-exclusive right to reproduce, publish, and
freely distribute both the Information and **Value-added Products** — products
made by adapting or incorporating it. It also permits sublicensing on terms
consistent with the Open Licence and addresses intellectual-property rights in
Value-added Products.

The project treats a trained SynthPopCan model package as a Value-added Product,
for which the licence grants publication and redistribution rights subject to
its continuing conditions. This project guidance is not a substitute for
licensing advice.

Darcy Quesnel accepted this open-by-default project policy on 2026-08-15: to
the extent the package author owns or controls copyright or similar rights in
the original selection, organization, schema, documentation, and model
representation, those rights are offered under CC BY 4.0. That grant does
not license, replace, or supersede Statistics Canada Information or rights
governed by the Open Licence, and it claims no author-controlled rights in
source classifications, facts, or unprotectable numeric results. The statements
are cumulative and scoped to their respective material; they are not alternative
licences for the package as a whole.

CC BY 4.0 is deliberately used instead of CC0 for that authored layer: it
permits broad reuse while preserving attribution, and it avoids implying that
the project can waive Statistics Canada or other third-party rights.

The policy is Accepted in
[ADR-0014](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md),
with Darcy Quesnel as decision authority on 2026-08-15. External review is
welcome but optional and is not a `1.0.0` gate; no Statistics Canada approval or
legal opinion is claimed. The live archive correction completed on 2026-08-16:
the registry now selects 32 verified non-overwriting package versions whose
bytes embed this contract, while historical versions remain available. The
[dated review record](records/prepared-model-licensing-review-2026-08-15.md)
records the decision, and the [archive-correction
record](records/prepared-model-archive-correction-2026-08-16.md) records its
execution.

For Census-derived packages, the embedded `policy_decision` uses
`status: accepted`, `basis: maintainer-selected-permissive-default`, the
accepted ADR-0014 record, Darcy Quesnel as `decided_by`, `2026-08-15` as
`decided_on`, and `external_legal_review: not-obtained`. Synthetic-only examples
use `not-applicable`; unclassified legacy material remains `unresolved`. These
values make the source of project authority explicit without fabricating an
external opinion.

The continuing source conditions are presented as follows:

- **Attribution.** The model catalogue and current archive descriptions carry
  the licence's prescribed notice. New and corrected packages derive the exact
  vintage-specific wording from the authoritative machine-readable licensing
  metadata at `licensing.source_information.prescribed_notice`, including the
  official product title, catalogue number, and Census reference year. The
  enclosing `synthpopcan-prepared-model-licensing-v1` object also records the
  cumulative authored/source layers, explicit rights exclusions, continuing
  conditions, and policy decision. View it with the `models show` command; do
  not shorten or reconstruct the notice from the Census year alone.
- **Historical-byte correction.** The 2026-08-15 review found that the 32
  historical archive records describe the source terms but the immutable model
  JSON bytes do not yet embed a complete scoped rights block. Corrected bytes
  will be published as new, non-overwriting versions under the existing concept
  DOIs, with new checksums and version DOIs. Existing records receive in-place
  metadata clarification and remain available for reproducibility. The
  accepted project policy requires both record-level and embedded-JSON rights
  statements. Materially conflicting future authoritative guidance will trigger
  a prospective review and, where needed, another non-overwriting correction.
- **No endorsement.** The notice states this explicitly, and SynthPopCan makes no
  claim of affiliation with Statistics Canada.
- **No re-identification.** The licence forbids merging or linking the
  Information with other databases to attempt to identify a person, business, or
  organization. Do not use SynthPopCan outputs for that purpose.
- **No misrepresentation.** Generated populations are synthetic artifacts. They
  must not be presented as real Census records, as confidential Statistics Canada
  information, or as legally anonymized data. Passing SynthPopCan's
  disclosure-risk checks is a project-level screen, not certification.

When you redistribute a package or an output derived from one, carry the exact
source notice and Open Licence link with it. Do not treat a bare `CC BY 4.0`
label as the complete rights statement for a Census-derived model package.

**This release path covers Census PUMF-derived packages only.** Published model
packages are trained from Statistics Canada public use microdata files and
nothing else. Access-controlled sources are used locally, if at all, and are
never redistributed through SynthPopCan — neither the source material nor any
artifact derived from it.

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

Checks the local data directory layout and reports which expected paths and
metadata records are present, missing, or invalid. It checks:

- the `raw`, `derived`, and `work` directories;
- versioned `manifest.json` product inventories for the 2016 and 2021 Census
  caches;
- extracted 2016 and 2021 hierarchical and individual PUMF variable metadata;
  and
- the canonical 2016 CT Census Profile provenance manifest used by the
  documented tract walkthrough.

Each check is reported independently. Missing optional material is not a
command failure; it tells us which documented workflows the current cache is
not yet ready to run. An invalid inventory, missing file named by an inventory,
or wrong Census year is reported as a problem that should be corrected before
relying on that cache.

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
