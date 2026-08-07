# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Active baseline | `0.9.0` bounded assurance, then ongoing `1.x` evidence | Review and fixture the core 2016/2021 household and private-household person control crosswalks before making new local-representativeness claims. |
| [Methodological validation and uncertainty](2026-08-02-methodological-validation-and-uncertainty.md) | Planned cross-cutting assurance track | Oracle, integerization decision, bounded validation, and Canadian comparison for `0.9.0`; deeper ensembles and attacks post-`1.0` | Add generated feasible linked-calibration cases and an independent solver-backed oracle, then publish the first convergence and residual comparison. |
| [Expanded small-area controls](2026-08-01-expanded-small-area-controls.md) | Planned correctness and implementation track | Core private-household packs for `0.9.0`; broader fields and population universes post-`1.0` | Define the compatibility registry and fixture the core 2016/2021 household and private-household person control packs. |
| [Expanded hierarchical tree models](2026-08-01-expanded-hierarchical-tree-models.md) | Planned research and implementation track | Pre-`1.0` inventory and extension-contract proof only; richer profiles and family hierarchy post-`1.0` | Build and review the 2016/2021 field eligibility inventory without committing new public profiles before the interface freeze. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Active baseline; ongoing release policy | Bounded licensing, preservation, management, and bilingual case-study gates for `1.0.0`; outreach, mirrors, and JOSS later | Settle model licensing, add full CFF validation, capture Software Heritage identifiers, publish dated FAIR4RS/management records, and test the bilingual 2021 case study. |
| [Simulation interoperability](2026-07-15-simulation-interoperability.md) | Neutral bundle completed; adapter conditional | `0.8.0` neutral bundle released; adapter pilot only after `1.0.0` | Wait for a real post-`1.0` consumer, pinned target contract, and authorized fixture before selecting one adapter pilot. |
| [Strict typing](2026-08-01-strict-typing.md) | Active maintenance ratchet | Incremental; not a numbered-release gate | Type shared dynamic-data boundaries and expand the strict-clean module list without weakening the package-wide standard gate. |

## Archived Plans

Archived plans preserve completed decisions and acceptance evidence. They do
not own new work.

| Plan | Completed | Outcome |
| --- | --- | --- |
| [Local web application runtime](archive/2026-07-10-local-web-application-runtime.md) | `0.6.0`, with `0.6.1` follow-up | Durable FastAPI/Uvicorn local runs, shared backend workflows, bounded artifacts, and browser sequencing. |
| [Linked population schema](archive/2026-07-18-linked-population-schema.md) | `0.6.1` | Stable v1 household/person/geography artifact contract and compatibility checks. |
| [Small-area geography](archive/2026-07-22-small-area-geography.md) | `0.7.0` | Explicit geography identity, reviewed Québec DA evidence, restartable national DA/ADA orchestration, bounded Nunavut proofs, and completed Canada ADA execution. |
| [External-data enrichment framework](archive/2026-07-15-ecosystem-enrichment.md) | `0.7.2` | Reusable enrichment contracts plus maintained Can-FED area-context and corrected ODEF facility-inventory adapters with pinned source evidence. |

Move a plan to `plans/archive/` after its completion criteria are met and its
outcome is recorded in [CHANGELOG.md](../CHANGELOG.md).
