# Implementation Plan Index

Read [PLANS.md](../PLANS.md) first. Open an implementation plan only when the
current task matches its scope.

| Plan | Status | Target | Next action |
| --- | --- | --- | --- |
| [Correctness assurance](2026-07-12-correctness-assurance.md) | Ongoing | Post-`0.5.1` evidence | Preserve the released gate and prioritize the planned assurance improvements. |
| [Local web application runtime](2026-07-10-local-web-application-runtime.md) | `0.6.0` implementation complete (Stages 0–8 verified); `0.6.1` follow-up implemented | `0.6.0`; schema follow-up in `0.6.1` | Preserve the durable-run and browser sequencing regression gates. |
| [Linked population schema](2026-07-18-linked-population-schema.md) | Released | `0.6.1` | Preserve v1 compatibility and review future schema changes explicitly. |
| [Research-software stewardship](2026-07-19-research-software-stewardship.md) | Planned/ongoing | Immediate, `0.7.x`, `0.8.x`, and maturity follow-ons | Add full CFF validation, review archive licensing/automation, and continue FAIR, governance, research-object, and publication work. |
| [Ecosystem enrichment](2026-07-15-ecosystem-enrichment.md) | Planned | `0.7.0`–`0.7.3` | Complete source-level metadata, access, licence, geography, and role profiles without exposing private records. |
| [Simulation interoperability](2026-07-15-simulation-interoperability.md) | Planned | `0.8.0`–`0.8.2` | Validate the simulator-neutral exchange contract against representative ActivitySim, Starsim, Mesa, and GAMA inputs before implementing adapters. |

Move a plan to `plans/archive/` after its completion criteria are met and its
outcome is recorded in [CHANGELOG.md](../CHANGELOG.md).
