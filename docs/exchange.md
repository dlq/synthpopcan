# Portable Population Exchange

SynthPopCan can package linked synthetic households and people for another
research tool without claiming to provide a complete simulation. The `0.8.0`
exchange is deliberately plain: UTF-8 CSV tables plus JSON metadata that can be
read without a simulator, database, GIS library, or optional Python package.

An exchange bundle is a **population contribution**. It does not invent
activities, schedules, locations, behaviour, health states, networks,
coefficients, or target-specific settings. A receiving project must supply and
validate those inputs itself.

## What the bundle contains

| File | Purpose |
| --- | --- |
| `households.csv` | Household rows copied byte-for-byte from the linked population. |
| `persons.csv` | Person rows copied byte-for-byte, retaining the household foreign key. |
| `linked-population.json` | Linked-population v1 table, key, relationship, row-count, and optional household-geography contract. |
| `data-dictionary.json` | Every CSV column, its storage type, structural role, missing-value representation, and modeled status. |
| `provenance.json` | The standalone origin or successful durable-run identity and the exact CLI/library reproduction request. |
| `validation.json` | Creation-time linkage, byte-preservation, dictionary, geography-context, limitations, and reproduction evidence. |
| `manifest.json` | Exchange v1 identity, per-file hashes, byte sizes, row counts, media types, access and redistribution classifications, geography and temporal context, and missing simulation inputs. |

The manifest does not hash itself. It hashes every other required file. The
validator rejects a missing, changed, misclassified, or extra file and then
rebuilds the linked descriptor and dictionary coverage from the CSVs.

```{admonition} A hash is not a disclosure review
:class: warning

Integrity checks prove which bytes travelled. They do not make restricted data
public, grant redistribution permission, certify privacy, or establish that a
population is representative for a particular geography or research question.
Choose `--access` and `--redistribution` from the actual source and project
governance; the defaults are deliberately `local` and `not-assessed`.
```

## Complete fictional example

This example is offline and deterministic. It uses the bundled fictional model,
not Census microdata and not a representative Canadian population.

```bash
synthpopcan models generate demo-linked-household-person \
  --households 10 \
  --condition "geo=Demo North" \
  --out fictional-population/ \
  --random-seed 42

synthpopcan bundle create fictional-population/ \
  --out fictional-exchange/ \
  --access public \
  --redistribution permitted \
  --limitation "Fictional teaching population; not representative." \
  --format json

synthpopcan bundle validate fictional-exchange/ --format json
```

The model-generation manifest contains a nested linked-population v1
descriptor, which the bundle command validates and normalizes to
`linked-population.json`. A directory written by
`synthpopcan.write_linked_population` can be used in the same way.

## Census geography context

Short identifiers such as DAUIDs and CSDUIDs are not meaningful without a
Census vintage, geography level, and namespace. Supply all four geography
options together when household rows carry a Census geography:

```bash
synthpopcan bundle create csd-population/ \
  --out csd-exchange/ \
  --census-vintage 2021 \
  --geography-level csd \
  --identifier-namespace statcan:2021:csd \
  --geography-column CSDUID
```

The command rejects a universe whose identifier column does not match the
linked-population descriptor, a missing identifier column, or an empty
household identifier. Omitting all four options is allowed for a population
without a declared Census geography; the validation record then says that
explicit geography context was not supplied.

## Python API

```python
from pathlib import Path

import synthpopcan as spc
from synthpopcan.geography import statcan_geography_universe

population = spc.LinkedPopulationFiles(
    households=Path("csd-population/households.csv"),
    persons=Path("csd-population/persons.csv"),
    manifest=Path("csd-population/manifest.json"),
)
bundle = spc.create_exchange_bundle(
    population,
    "csd-exchange/",
    geography_universe=statcan_geography_universe(2021, "csd", "CSDUID"),
    reproduction={
        "interface": "python",
        "operation": "project export step",
        "script": "prepare_population.py",
    },
    access_classification="local",
    redistribution_status="not-assessed",
)
assert bundle.report["passed"]
assert spc.validate_exchange_bundle(bundle.directory)["passed"]
```

Pass a successful `synthpopcan-run-v1` file as `run_manifest=` when the
population came from a durable local run. The exchange records the run ID,
workflow, normalized request, random seed, source-manifest hash, and assurance
schema without copying input data. A queued, failed, cancelled, or interrupted
run cannot be named as a successful origin.

## Validation and interpretation

Run validation after copying, restoring, or sharing a bundle:

```bash
synthpopcan bundle validate received-exchange/
```

A passing report establishes that:

- all seven required files are present and no undeclared entry was added;
- declared SHA-256 hashes, byte sizes, media types, and CSV row counts match;
- household and person identifiers remain unique and every person links to a
  household;
- the linked descriptor and data dictionary cover the actual CSV structure;
- supplied Census geography context matches the household geography column;
  and
- provenance and reproduction records use the supported exchange schemas.

It does **not** establish local representativeness, convergence against a set of
controls, substantive validity, disclosure safety, causal validity, or
compatibility with an unnamed simulator. Keep the originating calibration and
model evidence with the research record, and validate any target-specific
mapping in the receiving project.

## Compatibility boundary

`synthpopcan-exchange-v1` fixes the required filenames, population-contribution
meaning, file evidence, relationship representation, and geography semantics.
New optional metadata can be additive. A change that renames required files or
changes their meaning requires a new exchange schema version and an explicit
migration path.

Parquet, GeoParquet, GeoPackage, RO-Crate, deterministic archives, and
simulator-specific adapters are not part of exchange v1. They remain possible
later mappings when a real consumer demonstrates the semantic and maintenance
case.
