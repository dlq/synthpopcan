# Architecture Decision Records

This directory records consequential, repository-wide technical decisions for
SynthPopCan. An architecture decision record (ADR) explains **why** a durable
choice was made, the alternatives considered, and the consequences we accept.
It complements, rather than replaces, the other project records:

- [`PLANS.md`](../PLANS.md) and [`plans/`](../plans/) describe work that remains
  open;
- [`CHANGELOG.md`](../CHANGELOG.md) describes observable changes by release;
- [`CORRECTNESS.md`](../CORRECTNESS.md) records correctness claims and evidence;
  and
- the user documentation explains how to use and interpret the software.

## Decision Index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-shared-python-workflow-core.md) | Accepted (retrospective) | Use a shared Python workflow core for the CLI, library, and local web app. |
| [0002](0002-local-durable-web-workbench.md) | Accepted (retrospective) | Keep the web app local, file-backed, and durable. |
| [0003](0003-versioned-linked-population-schema.md) | Accepted (retrospective) | Use a versioned linked household/person/geography schema. |
| [0004](0004-small-beginner-python-api.md) | Accepted (retrospective) | Maintain a small beginner-facing top-level Python API. |
| [0005](0005-local-source-data-and-reviewed-model-artifacts.md) | Accepted (retrospective) | Keep source records local and distribute only reviewed model artifacts. |
| [0006](0006-canonical-release-and-archive-authorities.md) | Accepted (retrospective) | Give each publication surface a defined authority. |
| [0007](0007-explicit-census-geography-identity.md) | Accepted (retrospective) | Identify Census geography by vintage, level, namespace, and identifier. |
| [0008](0008-immutable-enrichment-sidecars.md) | Accepted (retrospective) | Add external context through governed, immutable sidecars. |

## Recording A Decision

Copy [`template.md`](template.md), assign the next four-digit number, and use a
short descriptive filename. An ADR is appropriate when a choice:

- constrains several modules, interfaces, or future implementations;
- would be costly or risky to reverse;
- establishes an important data, privacy, compatibility, or publication
  boundary; or
- is likely to be questioned again after its original context has faded.

Do not use ADRs for temporary tasks, ordinary implementation details,
research-specific control choices, or judgments about whether an individual
model is fit for a particular study.

Use one of these statuses:

- **Proposed:** under review and not yet authoritative;
- **Accepted:** governs current work;
- **Accepted (retrospective):** records a decision already implemented before
  the ADR existed;
- **Superseded:** replaced by a later ADR, which must be linked; or
- **Deprecated:** retained for history but no longer recommended.

After acceptance, preserve the original context and decision. Add newly
discovered consequences or supersede the record instead of rewriting history.
