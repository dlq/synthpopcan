# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Active maintenance baseline | `1.0.0` compatibility and local release evidence complete | Preserve the frozen baseline, exact-commit CI, coverage/correctness gates, and release-evidence binding in later 1.x releases. |
| [Methodological validation and uncertainty](2026-08-02-methodological-validation-and-uncertainty.md) | Active post-1.0 research track; bounded 0.9 tranche completed | Deeper ensembles and attacks post-`1.0` | After the interface freeze, design the first explicit candidate-pool and control-uncertainty ensemble. |
| [Expanded small-area controls](2026-08-01-expanded-small-area-controls.md) | Active post-1.0 expansion track; core 0.9 packs completed | Broader fields and population universes post-`1.0` | After the interface freeze, select one additional control family for bounded source, universe, suppression, and validation review. |
| [Expanded hierarchical tree models](2026-08-01-expanded-hierarchical-tree-models.md) | Active post-1.0 research track; pre-1.0 inventory completed | Pre-`1.0` inventory and extension-contract proof complete; richer profiles and family hierarchy post-`1.0` | After the freeze, select one coherent additive field family from the reviewed inventory and design a separately versioned profile without rewriting archived packages. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Active maintenance baseline; scoped policy, archive correction, and 1.0 preservation completed | Preservation, management, support, CFF, bilingual case study, embedded licensing, 64-operation correction, 32 registry updates, 1.0 DOI, and full Software Heritage visit complete; outreach, mirrors, and JOSS later | Preserve the verified 1.0 identifiers and apply the exact-commit publication and preservation gates to later 1.x releases. |
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
