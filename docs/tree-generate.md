# Generate From a Model Package

A model package is a **reviewed, self-contained artifact** that bundles a trained
household model and a person model together with the provenance and audit
results needed to trust the output. Packages are the normal starting point for
**linked household/person generation**: we do not need access to restricted
microdata, and we do not need to train or audit a model ourselves.

If we need to train a model from microdata — because no suitable published
package exists for the geography or period — see {doc}`tree`.

For a complete released-model example with pinned checksums, a fixed seed, and
parallel English/French interpretation, follow the {doc}`case-study-quebec-2021`.

## Concept

Generation from a package is a **two-step process**. The household model generates
household records (tenure, dwelling type, size, and other attributes). The
person model then generates the people inside each household, conditioned on
household attributes so that household and person rows remain consistent with
each other. Both steps are driven by the distributions the model learned from
its training microdata.

The output is a **linked pair of CSVs**: one row per household and one row per
person, joined by a shared household identifier. Person rows inherit geography
from their household after any small-area calibration step.

Generated values preserve the source model's **raw codes**. For packages derived
from the 2016 PUMF, values such as `99999999`, `9999`, `99`, and `9` are
Statistics Canada special codes (not applicable, not available, valid skip)
that vary by column. Do not treat them as ordinary numeric values without
checking the field metadata for the relevant table.

**Choosing a package for the research question.** A package trained on 2016
Census microdata will reproduce the household and person relationships present
in that microdata, including its category definitions, its geographic scope, and
the population universe it covers. If the research requires a different census
year, a different province or city, or different category boundaries, a
pre-trained package may not be appropriate — and training a custom model from
suitable microdata is the right path instead. Inspect any package we plan to
use with `models build inspect` and check the source provenance and review notes
before generating output we intend to publish or share.

## Getting Started

**Network required for published packages.** `models list` also shows the
bundled fictional package, but the Montréal and Canada packages below must be
downloaded on first use. To test generation entirely offline, use the bundled
package in {doc}`installation`.

List the packages SynthPopCan knows about:

```bash
synthpopcan models list
```

Download a package into the local model cache:

```bash
synthpopcan models fetch montreal-cma-2016-all-fields
```

For a Canada-wide package, use:

```bash
synthpopcan models fetch canada-2021-all-fields
```

Parallel 2016 and 2021 packages are available for Canada, supported provinces,
and the five PUMF-coded CMAs. Prince Edward Island uses a reduced package
because its PUMF sample is smaller. Use `models show MODEL_ID` to review the
census vintage, model limitations, package size, and browser compatibility.

Inspect a package before generating — confirms what geography, columns, and
conditioning structure it contains:

```bash
synthpopcan models build inspect montreal-cma-2016-all-fields
```

Generate linked households and persons:

```bash
synthpopcan models generate montreal-cma-2016-all-fields \
  --households 100000 \
  --out synthetic-population/ \
  --random-seed 42
```

Validate the linked output before using it:

```bash
synthpopcan validate linked synthetic-population/
```

If we want to assign the generated households to census tracts or aggregate
dissemination areas, continue with {doc}`small-area`.

## Subcommands

### `models list` and `models show`

Lists model packages known to SynthPopCan. The tiny demo package is bundled
with the tool. Published packages (such as provincial or CMA models) appear as
downloadable until fetched into the local cache. `models list` is compact;
`models show MODEL_ID` expands the metadata for one package.

```bash
synthpopcan models list
synthpopcan models list --format json
synthpopcan models show montreal-cma-2016-all-fields
```

The default list is deliberately compact so model IDs, geography, vintage,
size, and availability remain easy to scan. Use `models show MODEL_ID` for the
source, release, privacy-review status, generation guidance, and known
limitations of one package; use JSON for automation.

### `models fetch`

Downloads a published package into the local model cache by ID. The ID comes
from `models list`. GitHub Release assets are gzip-compressed to keep downloads
small; `models fetch` decompresses them into normal JSON package files in the
local cache.

```bash
synthpopcan models fetch montreal-cma-2016-all-fields
synthpopcan models fetch canada-2021-all-fields
```

Packages above the documented direct-payload browser-memory limit cannot be
returned through the legacy whole-model API. They can still be downloaded and
used by the Python-backed web run service or the CLI; review memory and disk
estimates before starting a large run.

### `models remove`

Removes a downloaded package from the local model cache. It does not remove the
package from the public catalogue, and it cannot remove the bundled teaching
model. We can fetch a removed package again later.

```bash
synthpopcan models remove montreal-cma-2016-all-fields
```

### `models build inspect`

Prints a summary of a package — its geography, training period, column
inventory, and embedded audit results — without dumping the full model payload.
Use this to confirm a package is suitable for the intended use before generating.

```bash
synthpopcan models build inspect montreal-cma-2016-all-fields
synthpopcan models build inspect linked-model-package.json
synthpopcan models build inspect linked-model-package.json --format json
```

The first argument can be a package ID from `models list` or a path to a local
package JSON file.

### `models generate`

Generates linked household and person CSVs from a reviewed package. Streams
output as it generates, so large runs do not need to fit in memory before
writing.

```bash
synthpopcan models generate montreal-cma-2016-all-fields \
  --households 1000 \
  --out synthetic-population/ \
  --random-seed 42
```

Options:

- `--households INTEGER`: number of households to generate.
- `--condition COL=VAL`: restrict generation to a specific condition value
  (e.g. `PR=24` for Quebec). Can be repeated.
- `--out DIRECTORY`: writes `households.csv`, `persons.csv`, and `manifest.json`
  together as one linked-population artifact.
- `--random-seed INTEGER`: seed for reproducibility.
- `--household-size-column TEXT`: override the package field that records how
  many people belong to each household. Normally we should keep the package
  default; use this only when a reviewed local package documents another field.

The household count is controlled directly. The person count is derived from
the model's household-size distribution and will not match a separate population
target exactly.

The generated `manifest.json` retains the package's complete
`synthpopcan-prepared-model-licensing-v1` object. Keep that object with shared or
archived outputs: it distinguishes authored and Statistics Canada source
layers, preserves the exact source notice and continuing conditions, and makes
the accepted maintainer policy decision visible without implying external
legal review. Its open licence grant does not relax privacy, attribution, or
provenance safeguards.

## Troubleshooting

**Package not found after `models fetch`:** confirm the ID with `models list`.
Large packages may take several minutes to download.

**Generated rows have unexpected special codes:** check the field metadata for
the package's source table. Statistics Canada PUMF columns use codes such as
`9`, `99`, `9999`, and `99999999` for not applicable or valid skip, which vary
by column.

**Person count does not match a target:** person count is model-derived from
the household-size distribution. To anchor the total population to a target,
calibrate to Census Profile controls using {doc}`small-area`.

**Validation reports mismatched household sizes:** check that the
`household_size` column in the household CSV matches the number of person rows
per household ID. This can occur with packages trained on different household-
size capping conventions. See {doc}`tree` for audit details.

## Training a Model

If no suitable package exists for the geography, census year, or column profile,
we can train a model from restricted microdata. That workflow —
including source preparation, training, audit, release checks, and packaging —
is covered in {doc}`tree`.
