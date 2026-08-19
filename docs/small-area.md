# Small-Area Linked Synthesis

Small-area synthesis assigns already-linked synthetic households and people to
smaller Census geographies while preserving household membership and checking
the result against reviewed public controls. It is an advanced workflow: a
geography code and a plausible-looking table are not enough to establish a
compatible universe, vintage, or model field.

## Choose a Path

| Goal | Start here |
| --- | --- |
| Understand the household-first workflow | [Workflow overview](#workflow-overview) |
| Run the guided command-line sequence | [Command-Line Getting Started](command-line.md) and `synthpopcan guide small-area` |
| Follow the complete Québec example | [Quebec 2021 Case Study](case-study-quebec-2021.md) |
| Inspect which controls are currently supported | [Small-Area Control Coverage](small-area-control-coverage.md) |
| Use control packs, national execution, mapping, or every `geo` command | [Execution and Command Reference](small-area-reference.md) |
| Call the maintained Python surface | [Beginner API](library-getting-started.md) or [advanced small-area recipes](library-recipes.md#small-area-synthesis) |

## Workflow Overview

The maintained workflow is deliberately household-first:

1. identify the Census vintage and canonical geography identifiers;
1. inspect controls, universes, suppression, and source provenance;
1. generate or load linked household/person candidates;
1. estimate feasibility and resource requirements before calibration;
1. calibrate households against a reviewed, model-compatible control pack;
1. carry the household assignment to linked people;
1. validate controls, linkage, residuals, support, and output provenance; and
1. render maps only from separately prepared display boundaries.

The calibration target is a statistical constraint, not an observed address.
Passing numerical checks does not prove representativeness, disclosure safety,
or substantive fitness for an unrelated research question.

## Minimum Safe Sequence

Use the built-in guide for the exact current commands:

```bash
synthpopcan guide small-area
```

Before a substantial run, use `geo estimate`; choose a reviewed control pack;
keep the generated plan, manifests, and validation evidence; and stop when the
tool reports an incompatible universe, vintage, geography, or model field.

## Related Documentation

- [Geography identity and display boundaries](geodata.md)
- [Prepared-model generation](tree-generate.md)
- [Linked-population contract](linked-population.md)
- [Validation](validate.md)
- [Correctness claims and limitations](correctness.md)

The [complete execution and command reference](small-area-reference.md)
contains the worked workflow, bounded Québec proof, national DA/ADA execution,
all `geo` subcommands, Python examples, adaptation guidance, troubleshooting,
quality interpretation, and current limits.
