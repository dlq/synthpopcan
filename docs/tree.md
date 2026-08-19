# Tree Models

Tree models are one way SynthPopCan represents conditional household and person
distributions for linked generation. Most users do not need to train one: use a
reviewed prepared model package through the guided generation workflow instead.
Training commands require the optional `synthpopcan[model-build]` extra.

## Choose a Path

| Goal | Start here |
| --- | --- |
| Generate from an existing package | [Generate From a Model Package](tree-generate.md) |
| Understand package and linked-output contracts | [Linked Populations](linked-population.md) and [Data and Model Licensing](data.md) |
| Train, audit, package, inspect, or prepare a model release | [Tree-Model Development and Release Reference](tree-model-development.md) |
| Use Python rather than the CLI | [Beginner API](library-getting-started.md) or [advanced tree-model recipes](library-recipes.md#tree-models) |
| Reproduce a complete bilingual example | [Quebec 2021 Case Study](case-study-quebec-2021.md) |

## What to Know Before Training

A decision tree partitions observed training rows into conditional groups. A
forest uses multiple trees to reduce dependence on a single partition. Neither
automatically makes sparse support, structural zeros, source bias, privacy
risk, or household/person consistency disappear.

Release candidates therefore need more than predictive fit. Review support and
leaf purity, rare paths, linkage rules, disclosure-risk evidence, source and
licensing metadata, validation results, and the exact serialized package.

## Maintained User Workflow

For ordinary generation, list the catalogue, inspect a package, fetch it, and
generate linked rows:

```bash
synthpopcan models list
synthpopcan models show demo-linked-household-person
synthpopcan models generate demo-linked-household-person \
  --households 10 --random-seed 42 --out population/
synthpopcan validate linked population/
```

Prepared packages carry their model identity, source provenance, licensing,
schema version, and validation-relevant metadata. Preserve those records with
derived outputs.

The [complete development reference](tree-model-development.md) explains tree
and forest quality, support and purity, disclosure review, every model-building
subcommand, repository release assets, package licensing, inspection, and
troubleshooting.
