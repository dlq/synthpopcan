# Prepared Display Boundaries

The `geodata` command group downloads **prepared display boundaries** for maps.
It gives us a smaller alternative to repeatedly simplifying large canonical
Statistics Canada boundary files, while preserving a clear distinction between
geometry used for analysis and geometry used for presentation.

```{admonition} Added in 0.7.0; separately versioned geodata assets
:class: note

The `geodata` commands retrieve the independently versioned
[`geodata-v1` release](https://github.com/dlq/synthpopcan/releases/tag/geodata-v1)
of prepared files and its catalogue.
```

## Concept

A census boundary can serve two different purposes:

- **Canonical analytical geometry** preserves the publisher's boundary product
  for selection, relationships, area calculations, reconciliation, and other
  substantive geographic work.
- **Prepared display geometry** removes detail to make an interactive map
  smaller and faster. It is derived from the canonical geometry and may not
  preserve measurements or every coastline detail needed for analysis.

SynthPopCan never silently treats the display copy as the analytical source.
Each release catalogue identifies the Census year, geography level, optional
province or territory, representation, immutable release URL, compressed
SHA-256, and unpacked SHA-256. The fetcher verifies both byte representations
before installing the GeoJSON in a user cache.

Start with {doc}`small-area` if we still need to choose CT, CSD, ADA, or DA,
prepare controls, or calibrate a population. Return here when we are ready to
prepare map geometry.

## Getting Started

**Network required; source checkout required until 0.7.0.** Configure the
published catalogue for the current terminal session:

```bash
export SYNTHPOPCAN_GEODATA_CATALOGUE="https://github.com/dlq/synthpopcan/releases/download/geodata-v1/geodata-catalogue.json"
```

Fetch the 2021 Québec DA display boundary:

```bash
synthpopcan geodata fetch 2021 da --pruid 24
```

The command prints the verified local `.geojson` path. Keep that path for a map
command, or print the cache root again later:

```bash
synthpopcan geodata cache-dir
```

The downloaded file remains in the cache and is reused only when its unpacked
checksum still matches the catalogue. A missing or changed file is downloaded
and verified again.

## Published Coverage

The `geodata-v1` catalogue contains:

| Census year | Geography | Scope used by `geodata fetch` |
| --- | --- | --- |
| 2016 | CT, CSD, ADA, and DA | National; omit `--pruid` |
| 2021 | CT | National; omit `--pruid` |
| 2021 | CSD, ADA, and DA | One asset per province or territory; supply `--pruid` |

For example:

```bash
# National 2016 census tracts
synthpopcan geodata fetch 2016 ct

# National 2021 census tracts
synthpopcan geodata fetch 2021 ct

# Ontario 2021 census subdivisions
synthpopcan geodata fetch 2021 csd --pruid 35
```

The catalogue requires an **exact** year, level, and PRUID match. It does not
guess that a national asset can replace a regional request, or combine regional
files implicitly.

## Use the Result in a Map

For an ordinary linked population, pass the path printed by `geodata fetch` to
`geo map` as its boundary input:

```bash
synthpopcan geo map synthetic-da-population/ \
  --boundaries /path/printed/by/geodata-fetch.geojson \
  --geo-column da \
  --out synthetic-da-map.html
```

**Template: replace the population and printed cache path.** The population's
geography identifiers must describe the same Census vintage and universe as the
display file. A successful checksum does not establish that compatibility.

Completed national-plan maps first look for prepared display files in the
plan's `boundaries/` directory. A jurisdiction-scoped national-plan map can
also fetch its regional display file when
`SYNTHPOPCAN_GEODATA_CATALOGUE` is configured. If no prepared file or catalogue
is available, the current renderer retains its documented canonical-boundary
fallback rather than changing the analytical source.

## Command Reference

### `geodata fetch CENSUS_YEAR GEOGRAPHY_LEVEL`

Downloads one exact catalogue asset, verifies it, decompresses it atomically,
and prints the cache path.

- `CENSUS_YEAR`: integer Census vintage represented by the asset.
- `GEOGRAPHY_LEVEL`: one of `ct`, `csd`, `ada`, or `da`.
- `--pruid`: two-digit province or territory identifier for a regional asset.
- `--catalogue`: local `synthpopcan-geodata-catalogue-v1` JSON path. For an
  HTTPS catalogue, set `SYNTHPOPCAN_GEODATA_CATALOGUE` instead.

The cache root can be overridden with `SYNTHPOPCAN_GEODATA_CACHE`. This is
useful when a research environment keeps downloaded artifacts on a dedicated
volume or in a project-controlled cache.

### `geodata cache-dir`

Prints the effective cache directory. SynthPopCan uses:

- `SYNTHPOPCAN_GEODATA_CACHE`, when set;
- `~/Library/Caches/synthpopcan/geodata` on macOS; or
- `$XDG_CACHE_HOME/synthpopcan/geodata`, falling back to
  `~/.cache/synthpopcan/geodata`, on other supported systems.

## What We Should Record

Keep the following with a mapped research output:

- SynthPopCan software version and command;
- geodata release and catalogue URL;
- Census vintage, geography level, and PRUID scope;
- catalogue asset filename and both checksums;
- canonical boundary and control provenance used for the analytical workflow;
  and
- a note that the prepared geometry is display-only.

The interactive HTML may embed a copy of the selected display features. That
does not turn the simplified geometry into an analytical boundary product.

## Troubleshooting

**No geodata catalogue is configured:** set
`SYNTHPOPCAN_GEODATA_CATALOGUE` to the published HTTPS catalogue, or pass a
downloaded local catalogue with `--catalogue`.

**No unique asset matches:** compare the requested year, level, and PRUID with
the coverage table. In particular, 2021 DA, ADA, and CSD assets require a
PRUID, while the 2016 assets and 2021 CT asset are national.

**A checksum does not match:** do not use the downloaded file. Rerun the fetch,
confirm the catalogue comes from the pinned release, and report a repeatable
mismatch with the asset name.

**The cache cannot be written:** set `SYNTHPOPCAN_GEODATA_CACHE` to a directory
we can write, then fetch again.

**The map has missing geographies:** checksum verification establishes byte
identity, not agreement with the synthetic population. Compare Census vintage,
geography level, identifier namespace, and selected province or territory. See
{doc}`small-area` for geography-universe troubleshooting.

For Python retrieval, continue to {doc}`library`. Exact function signatures are
in {doc}`api`.
