# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Active | `0.6.3` and ongoing evidence | Correct small-area reproduction parity, retain durable release evidence, and keep linked-population v1 unchanged. |
| [Small-area geography](2026-07-22-small-area-geography.md) | Active prerequisite | `0.7.0` | Make geography identity explicit and prove one bounded Québec 2016 DA workflow with matching controls, relationships, validation, and resource evidence. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Active baseline; ongoing release policy | Before another model publication or mirror; JOSS only after maturity gates | Settle model licensing, add full CFF validation, capture Software Heritage identifiers, publish dated FAIR4RS/management records, and release a tested bilingual 2021 case study for focused community introduction. |
| [Ecosystem enrichment](2026-07-15-ecosystem-enrichment.md) | Planned | `0.7.0`–`0.7.2` | Co-design the `0.7.0` source/enrichment foundation, integrate Can-FED in `0.7.1`, then select one demand-backed public service/location pilot. |
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
