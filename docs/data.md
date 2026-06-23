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
