# Generate From a Model Package

A model package is a **reviewed, self-contained artifact** that bundles a trained
household model and a person model together with the provenance and audit
results needed to trust the output. Packages are the normal starting point for
**linked household/person generation**: we do not need access to restricted
microdata, and we do not need to train or audit a model ourselves.

If we need to train a model from microdata — because no suitable published
package exists for the geography or period — see {doc}`tree`.

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
use with `tree inspect-package` and check the source provenance and review notes
before generating output we intend to publish or share.

## Getting Started

List the packages SynthPopCan knows about:

```bash
synthpopcan tree list-packages
```

Download a package into the local model cache:

```bash
synthpopcan models fetch montreal-cma-2016-all-fields
```

For a Canada-wide package, use:

```bash
synthpopcan models fetch canada-2016-all-fields
```

Inspect a package before generating — confirms what geography, columns, and
conditioning structure it contains:

```bash
synthpopcan tree inspect-package montreal-cma-2016-all-fields
```

Generate linked households and persons:

```bash
synthpopcan tree generate-from-package montreal-cma-2016-all-fields \
  --households 100000 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --manifest-out generation-manifest.json \
  --random-seed 42
```

Validate the linked output before using it:

```bash
synthpopcan validate linked-output \
  --households synthetic-households.csv \
  --persons synthetic-persons.csv
```

If we want to assign the generated households to census tracts or aggregate
dissemination areas, continue with {doc}`small-area`.

## Subcommands

### `tree list-packages` / `models list`

Lists model packages known to SynthPopCan. The tiny demo package is bundled
with the tool. Published packages (such as provincial or CMA models) appear as
downloadable until fetched into the local cache. Both commands show the same
list; `models list` is the shorter alias.

```bash
synthpopcan tree list-packages
synthpopcan models list
synthpopcan models list --format json
```

### `models fetch`

Downloads a published package into the local model cache by ID. The ID comes
from `models list`. GitHub Release assets are gzip-compressed to keep downloads
small; `models fetch` decompresses them into normal JSON package files in the
local cache.

```bash
synthpopcan models fetch montreal-cma-2016-all-fields
synthpopcan models fetch canada-2016-all-fields
```

### `tree inspect-package`

Prints a summary of a package — its geography, training period, column
inventory, and embedded audit results — without dumping the full model payload.
Use this to confirm a package is suitable for the intended use before generating.

```bash
synthpopcan tree inspect-package montreal-cma-2016-all-fields
synthpopcan tree inspect-package linked-model-package.json
synthpopcan tree inspect-package linked-model-package.json --format json
```

The first argument can be a package ID from `models list` or a path to a local
package JSON file.

### `tree generate-from-package`

Generates linked household and person CSVs from a reviewed package. Streams
output as it generates, so large runs do not need to fit in memory before
writing.

```bash
synthpopcan tree generate-from-package montreal-cma-2016-all-fields \
  --households 1000 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --manifest-out generation-manifest.json \
  --random-seed 42
```

Options:

- `--households INTEGER`: number of households to generate.
- `--condition COL=VAL`: restrict generation to a specific condition value
  (e.g. `PR=24` for Quebec). Can be repeated.
- `--households-out PATH`: output household CSV.
- `--persons-out PATH`: output person CSV.
- `--manifest-out PATH`: generation manifest recording the requested and actual
  counts, random seed, and package identity.
- `--random-seed INTEGER`: seed for reproducibility.

The household count is controlled directly. The person count is derived from
the model's household-size distribution and will not match a separate population
target exactly.

### `tree generate-linked`

Generates linked rows from two separate model JSON files rather than a packaged
artifact. Use this when working with local model files that have not yet been
packaged.

```bash
synthpopcan tree generate-linked \
  --household-model household-model.json \
  --person-model person-model.json \
  --households 1000 \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --manifest-out generation-manifest.json \
  --random-seed 42
```

### `tree generate`

Generates flat rows from a single model file. Use this for non-linked
(flat person or household) models rather than the household/person pair.

```bash
synthpopcan tree generate person-model.json \
  --rows 1000 \
  --condition PR=24 \
  --out synthetic-persons.csv \
  --manifest-out generation-manifest.json
```

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

## Training Your Own Model

If no suitable package exists for the geography, census year, or column profile,
we can train a model from restricted microdata. That workflow —
including source preparation, training, audit, release checks, and packaging —
is covered in {doc}`tree`.
