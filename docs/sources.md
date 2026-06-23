# Sources

The `sources` commands inspect local files safely before a workflow tries to
parse them.

## Concept

Census, WDS, profile, and local project files do not all share the same shape.
Inspect structure first:

- What files are present?
- What are the columns?
- What delimiter or encoding appears to be used?
- Is the file under `data/private`?
- Which adapter or workflow should handle it?

For humanities and digital-humanities projects, source inspection is also a
reading practice. Column names, category labels, geography codes, and missing
values all carry interpretation.

## Getting Started

Inspect a source root:

```bash
synthpopcan sources inspect data/raw
```

Inspect a file schema:

```bash
synthpopcan sources schema data/raw/example.csv
```

Sample a few rows:

```bash
synthpopcan sources sample data/raw/example.csv --rows 5
```

Use JSON for scripts:

```bash
synthpopcan sources schema data/raw/example.csv --format json
```

## Subcommands

### `sources inspect`

Lists known local source roots and file counts.

```bash
synthpopcan sources inspect data/raw
```

### `sources schema`

Reports file headers and structural information.

```bash
synthpopcan sources schema data/raw/example.csv
```

### `sources sample`

Prints a small row sample.

```bash
synthpopcan sources sample data/raw/example.csv --rows 10
```

Sampling files under `data/private` requires explicit consent:

```bash
synthpopcan sources sample data/private/example.csv \
  --rows 5 \
  --allow-private
```

## Troubleshooting

**Private path refused:** this is intentional. Add `--allow-private` only for
local inspection.

**Columns are unexpected:** do not force the file into an adapter. Inspect the
source product and create or choose an explicit adapter.

## Further Reading

- Statistics Canada WDS REST base:
  [https://www150.statcan.gc.ca/t1/wds/rest](https://www150.statcan.gc.ca/t1/wds/rest).
- Statistics Canada 2016 Census Profile download endpoint:
  [GetFile.cfm](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm).
- Government of Canada,
  [Statistics Act](https://laws-lois.justice.gc.ca/eng/acts/S-19/).
