# Controls

Controls are the target totals that IPF tries to match. They often come from a
Statistics Canada table, but they can also come from a local CSV prepared by a
researcher.

## Concept

SynthPopCan uses a normalized long control format:

```text
margin,dimensions,AGEGRP,SEX,count
age,AGEGRP,adult,,100
age,AGEGRP,child,,100
sex,SEX,,F,100
sex,SEX,,M,100
```

Each row describes one target cell. The `dimensions` column names the seed
column or columns that define the margin. Blank category cells mean that column
is not part of that margin row.

A joint margin uses more than one dimension:

```text
margin,dimensions,AGEGRP,SEX,count
age_sex,"AGEGRP,SEX",adult,F,55
age_sex,"AGEGRP,SEX",adult,M,45
age_sex,"AGEGRP,SEX",child,F,45
age_sex,"AGEGRP,SEX",child,M,55
```

Joint margins are more specific, but they need more seed coverage.

Control tables should be read as source interpretation, not just file
formatting. The same source table can often be normalized in multiple ways
depending on geography, universe, dimensions, and category mapping.

## Getting Started

Validate an existing normalized file:

```bash
synthpopcan controls validate controls.csv
```

Normalize a local long CSV:

```bash
synthpopcan controls from-csv source-controls.csv \
  --out controls.csv
```

Normalize a WDS ZIP:

```bash
synthpopcan controls from-wds table.zip \
  --dimensions "GEO,Age group,Sex" \
  --count-column VALUE \
  --margin-name population \
  --out controls.csv
```

Check the normalized controls against a seed before fitting:

```bash
synthpopcan ipf check-inputs \
  --seed seed.csv \
  --controls controls.csv
```

## Subcommands

### `controls validate`

Checks a normalized long control CSV.

```bash
synthpopcan controls validate controls.csv
```

### `controls from-csv`

Normalizes a local long control CSV.

```bash
synthpopcan controls from-csv source-controls.csv \
  --out controls.csv
```

### `controls from-wds`

Normalizes a local Statistics Canada WDS CSV ZIP.

```bash
synthpopcan controls from-wds table.zip \
  --dimensions Sex \
  --count-column VALUE \
  --mapping categories.json \
  --out controls.csv
```

Options:

- `--dimensions TEXT`: comma-separated WDS columns to use as dimensions.
- `--count-column TEXT`: WDS column containing counts.
- `--margin-name TEXT`: name for the generated margin.
- `--mapping PATH`: optional category mapping JSON.
- `--out PATH`: output controls CSV.

### `controls wds inspect`

Inspects a local WDS ZIP before normalization.

```bash
synthpopcan controls wds inspect table.zip
synthpopcan controls wds inspect table.zip --format json
```

### `controls wds mapping-template`

Creates a starter category mapping.

```bash
synthpopcan controls wds mapping-template table.zip \
  --dimensions "Age group,Sex" \
  --preset canonical \
  --out categories.json
```

Use `--preset blank` for an empty template or `--preset canonical` for common
labels SynthPopCan already recognizes.

### `controls census-profile inspect`

Lists candidate Census Profile characteristic rows.

```bash
synthpopcan controls census-profile inspect profile.csv \
  --search "years"
```

### `controls census-profile template`

Writes starter Census Profile mappings.

```bash
synthpopcan controls census-profile template age5 \
  --out census-profile-mapping.json
```

Available templates currently include `age5` and `sex`.

### `controls from-census-profile`

Normalizes a Census Profile CSV using a reviewed mapping.

```bash
synthpopcan controls from-census-profile profile.csv \
  --mapping census-profile-mapping.json \
  --out controls.csv
```

## Troubleshooting

**Valid controls still fail `ipf check-inputs`:** the controls may be valid, but
not compatible with that seed. Check missing columns and category labels.

**Too many dimensions:** start with a simpler margin. Add joint margins after a
one-way fit works.

**Unclear category labels:** create and keep a mapping file. Category mapping is
an interpretive research decision, not just a technical step.

## Further Reading

- Statistics Canada WDS REST base used by SynthPopCan:
  [https://www150.statcan.gc.ca/t1/wds/rest](https://www150.statcan.gc.ca/t1/wds/rest).
- Statistics Canada 2016 Census Profile download endpoint used by SynthPopCan:
  [GetFile.cfm](https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm).
- IPF background: [Iterative proportional fitting](https://en.wikipedia.org/wiki/Iterative_proportional_fitting).
