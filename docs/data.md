# Data

The `data` command group checks local data and metadata setup.

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

This local-data convention is intentionally conservative. Public aggregate data,
restricted microdata, derived model artifacts, and generated outputs can have
different sharing rules and different disclosure risks.

Use this page for local setup checks. Use [Sources](sources.md) to inspect
specific files, and [Statistics Canada Sources](statcan.md) to find and fetch
supported public Statistics Canada sources.

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

Check the default data root:

```bash
synthpopcan data doctor
```

Check a different data root:

```bash
synthpopcan data doctor --data-root /path/to/data
```

For repeated work:

```bash
export SYNTHPOPCAN_DATA_ROOT=/path/to/data
synthpopcan data doctor
```

## Subcommands

### `data doctor`

Reports whether the expected local data and metadata paths are present.

Options:

- `--data-root PATH`: override the data root.
- `--format table|json`: output format.

## Troubleshooting

**The data root is wrong:** pass `--data-root` for one command or set
`SYNTHPOPCAN_DATA_ROOT`.

**Private files appear in source paths:** keep them under `data/private` and do
not paste private rows into docs, issues, or shared reports.

## Further Reading

- Government of Canada,
  [Statistics Act](https://laws-lois.justice.gc.ca/eng/acts/S-19/).
- Background concept:
  [Statistical disclosure control](https://en.wikipedia.org/wiki/Statistical_disclosure_control).
- Tania Carvalho, Nuno Moniz, Pedro Faria, and Luis Antunes,
  [Survey on Privacy-Preserving Techniques for Data Publishing](https://arxiv.org/abs/2201.08120).
