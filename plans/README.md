# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Active baseline | Ongoing evidence | Maintain the released reproduction, assurance-schema, permanent-evidence, and linked-population v1 gates; add stronger generated or mutation evidence when prioritized. |
| [Small-area geography](2026-07-22-small-area-geography.md) | Implementation complete; release pending | `0.7.0` | Preserve the reviewed Québec proof, shared national DA/ADA plans, and bounded Nunavut executions through release. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Active baseline; ongoing release policy | Before another model publication or mirror; JOSS only after maturity gates | Settle model licensing, add full CFF validation, capture Software Heritage identifiers, publish dated FAIR4RS/management records, and release a tested bilingual 2021 case study for focused community introduction. |
| [External-data enrichment framework](2026-07-15-ecosystem-enrichment.md) | Active; `0.7.0` foundation validated | `0.7.0` framework with `0.7.1`–`0.7.2` reference implementations | Preserve the contracts through release, then demonstrate reuse with Can-FED v2 and ODEF v3 before selecting later adapters by evidence. |
| [Simulation interoperability](2026-07-15-simulation-interoperability.md) | Planned and conditional | `0.8.0`–`0.8.1` | Define a simulator-neutral exchange bundle, then validate one demand-backed target adapter against a pinned input contract. |

## Archived Plans

Archived plans preserve completed decisions and acceptance evidence. They do
not own new work.

| Plan | Completed | Outcome |
| --- | --- | --- |
| [Local web application runtime](archive/2026-07-10-local-web-application-runtime.md) | `0.6.0`, with `0.6.1` follow-up | Durable FastAPI/Uvicorn local runs, shared backend workflows, bounded artifacts, and browser sequencing. |
| [Linked population schema](archive/2026-07-18-linked-population-schema.md) | `0.6.1` | Stable v1 household/person/geography artifact contract and compatibility checks. |

Move a plan to `plans/archive/` after its completion criteria are met and its
outcome is recorded in [CHANGELOG.md](../CHANGELOG.md).
