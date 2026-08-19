# Implementation Plan Index

Read the [project roadmap](../PLANS.md) first. This directory contains detailed
implementation and research scopes; it is not a second roadmap.

## Plan Lifecycle

| State | Meaning |
| --- | --- |
| **Active maintenance** | Owns a recurring project obligation. It may have no feature release attached. |
| **Conditional research** | Preserves a reviewed scope, but implementation waits for the trigger named in the plan. |
| **Archived** | Completion criteria were met and the observable outcome was recorded in the changelog. The file remains historical evidence and owns no new work. |

Every non-archived plan must state its status, target, and current next action
near the top. A completed milestone may remain as context inside an active
plan, but new release narrative belongs in [CHANGELOG.md](../CHANGELOG.md).

## Active Maintenance

| Plan | Ongoing responsibility | Current next action |
| --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Compatibility, exact-commit CI, coverage, correctness, release evidence, assurance, and reproduction gates | Preserve the frozen baseline; reassess Python 3.15 support in November 2026 after its final release and ecosystem-wheel availability. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Citation, preservation, licensing, support boundaries, publication evidence, and future scholarly-readiness gates | Preserve the verified `1.1.0` identifiers, earlier records, and exact-commit publication process. |
| [Strict typing](2026-08-01-strict-typing.md) | Package-wide Pyright `standard` and an incremental strict-clean ratchet | Type shared dynamic-data boundaries without weakening runtime validation. |
| [Post-1.0 release train](2026-08-19-post-1-0-release-train.md) | Bounded minor-release scope, confidence, sequencing, and acceptance gates | Begin bounded `1.2.0` evidence work; keep `1.3.0` explicitly forecast. |

## Active Feature Implementation

| Plan | Target release | Current next action |
| --- | --- | --- |
| [Expanded small-area controls](2026-08-01-expanded-small-area-controls.md) | `1.2.0` conditional person controls | Preserve the released 24-pack/14-family baseline while building the bounded conditional-control evidence tranche. |

## Conditional Research

These plans are maintained scopes, not scheduled releases.

| Plan | Completed foundation | Trigger for the next tranche |
| --- | --- | --- |
| [Expanded hierarchical tree models](2026-08-01-expanded-hierarchical-tree-models.md) | Field-eligibility inventory and `1.x` extension boundary | A concrete use justifies one coherent additive field family and separately versioned profile. |
| [Methodological validation and uncertainty](2026-08-02-methodological-validation-and-uncertainty.md) | Bounded oracle, integerization comparison, multi-scale validation, and Canadian comparison | A study requires a named uncertainty ensemble, utility evaluation, or disclosure-risk tranche. |
| [Simulation interoperability](2026-07-15-simulation-interoperability.md) | Released simulator-neutral exchange bundle | A real consumer supplies a pinned target contract, authorized fixture, and maintainable import smoke test. |

## Archived Plans

Archived plans preserve completed decisions and acceptance evidence. They do
not own new work.

| Plan | Completed | Outcome |
| --- | --- | --- |
| [Local web application runtime](archive/2026-07-10-local-web-application-runtime.md) | `0.6.0`, with `0.6.1` follow-up | Durable FastAPI/Uvicorn local runs, shared backend workflows, bounded artifacts, and browser sequencing. |
| [Linked population schema](archive/2026-07-18-linked-population-schema.md) | `0.6.1` | Stable v1 household/person/geography artifact contract and compatibility checks. |
| [Small-area geography](archive/2026-07-22-small-area-geography.md) | `0.7.0` | Explicit geography identity, reviewed Québec DA evidence, restartable national DA/ADA orchestration, and bounded national execution. |
| [External-data enrichment framework](archive/2026-07-15-ecosystem-enrichment.md) | `0.7.2` | Reusable enrichment contracts plus maintained Can-FED and corrected ODEF reference adapters. |
| [Correctness assurance baseline](archive/2026-07-12-correctness-assurance-baseline.md) | `1.0.0` | Detailed numerical, artifact, reproduction, coverage, and release-evidence implementation record. |
| [Research-software stewardship baseline](archive/2026-07-19-research-software-stewardship-baseline.md) | `1.0.0` | Detailed citation, preservation, licensing, FAIR, support, case-study, and scholarly-readiness record. |

Move a plan to `plans/archive/` only after its completion criteria are met and
its observable outcome is recorded in [CHANGELOG.md](../CHANGELOG.md). If new
work later revisits the same area, create a new dated plan or explicitly
reactivate and update the existing scope; do not silently turn an archived
record back into a live task list.
