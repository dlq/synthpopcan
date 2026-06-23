# Statistics Canada Sources

The `statcan` commands help find and fetch supported Statistics Canada sources.
Network commands depend on current public Statistics Canada services and should
be treated as live-source operations.

## Concept

Statistics Canada sources are not all shaped the same way. SynthPopCan separates
source discovery and download from control normalization:

1. Search or fetch a public source.
2. Inspect the downloaded file.
3. Normalize only the dimensions needed for the research question.
4. Check compatibility with the seed or generated rows.

This keeps source interpretation visible.

Statistics Canada tables are official aggregate sources, but the work of
choosing dimensions, geographies, and category mappings still belongs to the
researcher. A table that is useful for one geography or population universe may
be misleading for another.

## Getting Started

Search WDS table metadata:

```bash
synthpopcan statcan wds search "population dwelling" --limit 10
```

Explain a product before downloading it:

```bash
synthpopcan statcan wds explain PRODUCT_ID
```

Fetch the table:

```bash
synthpopcan statcan wds fetch PRODUCT_ID \
  --lang en \
  --out-dir data/raw/statcan/wds
```

Inspect and normalize after download:

```bash
synthpopcan controls wds inspect data/raw/statcan/wds/PRODUCT_ID-eng.zip
```

## Subcommands

### `statcan wds search`

Searches the WDS table inventory.

```bash
synthpopcan statcan wds search "age sex population"
synthpopcan statcan wds search "age sex population" --format json
```

Options:

- `--limit INTEGER`: number of results.
- `--format table|tsv|json`: output format.

### `statcan wds explain`

Summarizes metadata for a product ID.

```bash
synthpopcan statcan wds explain 98100001
synthpopcan statcan wds explain 98100001 --format json
```

Use this before download to check whether a table is plausible for your
workflow.

### `statcan wds fetch`

Downloads a full WDS table CSV ZIP.

```bash
synthpopcan statcan wds fetch 98100001 \
  --lang en \
  --out-dir data/raw/statcan/wds
```

### `statcan wds metadata`

Fetches WDS metadata and optionally writes JSON.

```bash
synthpopcan statcan wds metadata 98100001 --out metadata.json
```

### `statcan census-profile fetch`

Downloads a known Census Profile bulk CSV.

```bash
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level pt \
  --out-dir data/raw/statcan/census-profile/2016
```

Currently supported year values are limited by the implementation.

## Troubleshooting

**Search finds a table but controls do not fit:** the table may describe a
different population universe, geography, or category scheme.

**Download fails:** public Statistics Canada URLs can change. Keep the product
ID, date, command, and error message in your notes.

**A table has many columns:** normalize only the dimensions needed for the first
fit. Add complexity after validation works.

## Further Reading

- Statistics Canada WDS REST base:
  [https://www150.statcan.gc.ca/t1/wds/rest](https://www150.statcan.gc.ca/t1/wds/rest).
- Statistics Canada 2016 Census Profile download endpoint:
  [GetFile.cfm](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm).
- Government of Canada,
  [Statistics Act](https://laws-lois.justice.gc.ca/eng/acts/S-19/),
  for the legal framework around Statistics Canada.
