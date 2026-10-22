# Advanced Library Use

This page routes Python users to the smallest maintained API for their
task. Start with `import synthpopcan as spc`; reach into submodules only when a
research or contributor workflow genuinely needs the advanced objects.

## Choose a Python Interface

| Need | Documentation |
| --- | --- |
| First notebook or teaching workflow | [Getting Started With the Beginner API](library-getting-started.md) |
| Exact function, class, parameter, or return type | [API Reference](api.rst) |
| Lower-level recipes and intermediate objects | [Advanced Library Recipes](library-recipes.md) |
| CLI-equivalent generation from a prepared model | [Generate From a Model Package](tree-generate.md) |
| Small-area calibration | [Small-Area Linked Synthesis](small-area.md) |

## Import Boundary

Prefer the curated top-level API:

```python
import synthpopcan as spc
```

The top-level exports and intentionally documented advanced symbols are covered
by the public-interface compatibility contract. A symbol merely being
importable from an internal module does not make it a supported interface.

Use the beginner guide when learning the workflow, the API reference when the
name is already known, and the recipe collection when an example needs
lower-level controls, microdata adapters, geography objects, enrichment,
tree-model training, or validation intermediates.

## Development Naming Updates

The development branch provides the preferred names `CARTTreeModel`,
`ODEFAdapter`, and `WDSSelection`. Existing imports of `CartTreeModel`,
`OdefAdapter`, and `WdsSelection` remain aliases to the same classes. These
additions are unreleased; use the older spellings with published version 1.1.1.

New dictionary-serialization calls use `as_dict()`. Existing `to_dict()` calls
and subclass overrides remain supported; `as_summary()` denotes an incomplete
summary. Control-advice helpers now live in `synthpopcan.control_suggestions`;
the previous `synthpopcan.calibration.build_control_suggestion_report` import
continues to work. These changes preserve command spellings and saved formats.

## Evidence and Output Contracts

Library calls follow the same provenance, schema, validation, and licensing
boundaries as the CLI and local web app. Keep manifests and validation reports
with generated rows. Do not treat an in-memory success as evidence that a
particular source, model, geography, or research use is valid.

Continue to [Advanced Library Recipes](library-recipes.md), or use the
[API Reference](api.rst) for exact signatures.
