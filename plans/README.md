# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Ongoing | Post-`0.5.1` evidence | Preserve the released gate and prioritize the planned assurance improvements. |
| [Small-area geography](2026-07-22-small-area-geography.md) | Planned and partially implemented | After `0.6.2`, before DA-dependent enrichment | Prove a bounded province-scale DA workflow with matching controls, boundaries, relationship metadata, validation, and resource estimates. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Planned/ongoing | Immediate, `0.7.x`, `0.8.x`, and maturity follow-ons | Add full CFF validation, review archive licensing/automation, define a three-model Hugging Face pilot, and continue community, FAIR, governance, research-object, and JOSS preparation. |
| [Ecosystem enrichment](2026-07-15-ecosystem-enrichment.md) | Planned | `0.7.0`–`0.7.3` | Complete source-level metadata, access, licence, geography, and role profiles without exposing private records. |
| [Simulation interoperability](2026-07-15-simulation-interoperability.md) | Planned | `0.8.0`–`0.8.2` | Validate the simulator-neutral exchange contract against representative ActivitySim, Starsim, Mesa, and GAMA inputs before implementing adapters. |

## Archived Plans

Archived plans preserve completed decisions and acceptance evidence. They do
not own new work.

| Plan | Completed | Outcome |
| --- | --- | --- |
| [Local web application runtime](archive/2026-07-10-local-web-application-runtime.md) | `0.6.0`, with `0.6.1` follow-up | Durable FastAPI/Uvicorn local runs, shared backend workflows, bounded artifacts, and browser sequencing. |
| [Linked population schema](archive/2026-07-18-linked-population-schema.md) | `0.6.1` | Stable v1 household/person/geography artifact contract and compatibility checks. |

Move a plan to `plans/archive/` after its completion criteria are met and its
outcome is recorded in [CHANGELOG.md](../CHANGELOG.md).
