# Responsibility Boundaries And Maintainability Ratchet

Status: active maintenance\
Created: 2026-08-26\
Last updated: 2026-08-28\
Target: initial bounded tranche in `1.2.0`, then an ongoing `1.x` ratchet\
Next action: complete `RB12-02`, extracting the characterized small-area
preflight responsibility now that `RB12-01` route registration is separated\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) |
[Release train](2026-08-19-post-1-0-release-train.md)

## Outcome

Keep SynthPopCan understandable as its statistical and bilingual surfaces grow
by assigning each decision and side effect to one explicit layer. Preserve the
stable public façades while extracting cohesive internal responsibilities in
small, behaviour-preserving steps.

The governing rule is:

> Adapters translate, workflows coordinate, domain modules decide, and
> infrastructure performs effects.

This is not a request to maximize the number of files or introduce generic
service and repository abstractions. A boundary is justified when the enclosed
code has one reason to change, can be tested through a narrow contract, and
removes a dependency or policy decision from the wrong layer.

## Responsibility Model

| Layer | Owns | Must not own |
| --- | --- | --- |
| Public façade | Stable imports, documented entry points, and delegation | Algorithms, branching validation policy, network or filesystem work |
| CLI/web adapter | Request and option parsing, output selection, presentation-specific error translation | Statistical decisions, persistence rules, archive state transitions |
| Workflow | Use-case sequencing, calls to domain operations, and evidence assembly | Click, Rich, FastAPI, browser state, or transport-specific behaviour |
| Domain/core | Calibration, validation, contracts, transformations, and research invariants | UI frameworks, network clients, prompts, or process lifecycle |
| Infrastructure | Filesystem, HTTP, subprocess, checkpoint, and clock effects behind narrow interfaces | Statistical meaning, compatibility policy, or operator authorization |
| Presentation/localization | Human messages, tables, help, accessibility text, and locale selection | Machine schema keys, identifiers, checksums, exit semantics, or numerical results |

Prefer typed request/result dataclasses or narrow protocols at these seams.
Do not replace a clear function call with an untyped dictionary unless that
dictionary is itself a supported versioned artifact.

## PR-Sized Work

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `RB12-01` | `done` | Existing route-order and application-state behavior | Explicit `webapi` composition context and cohesive route-registration helpers | Factory state and exact route order are characterized; supported HTTP paths and handler behavior remain unchanged |
| `RB12-02` | `ready` | `RB12-01` | Small-area preflight request/result and orchestration boundary | Success, rejection, event ordering, and durable-run behavior are characterized; the route delegates without owning calibration or persistence policy |
| `RB12-03` | `blocked` | `RB12-04`; active `1.2.0` feature pressure | One selected `cli_geo` or `control_packs` responsibility extraction | The selected adapter becomes thinner, its supported façade remains compatible, and focused behavior plus forbidden-import tests pass |
| `RB12-04` | `ready` | Current source tree | Reproducible function-complexity and module-concentration baseline | The command, inputs, exclusions, and result are recorded; changed functions cannot silently raise the baseline |
| `RB12-05` | `ready` | Current coverage configuration | Exact two-decimal coverage comparison and candidate headroom | A result below `95.00%` fails without integer rounding; the release candidate reaches `95.25%` or the release remains blocked |
| `RB12-06` | `ready` | Supported beginner/advanced surface inventories | Beginner-export documentation and changed-symbol docstring ratchet | Every beginner export is documented; changed supported symbols have docstrings; the measured undocumented count does not increase |
| `RB12-07` | `ready` | Existing archive fault and recovery fixtures | Archive state/action matrix and proceed-or-defer decision | Every current transition, refusal, recovery state, and effect boundary is characterized; the decision either admits `RB12-08` or marks `RB12-08` and `RB12-09` deferred for `1.2.0` |
| `RB12-08` | `blocked` | `RB12-07` proceed decision | Pure archive transition component | Given validated manifest, checkpoint, and remote state, the component selects the next permitted action without HTTP, prompts, or checkpoint effects |
| `RB12-09` | `blocked` | `RB12-08` | Existing executor integration and fault/recovery verification | Fail-closed identity, authorization, recovery, checksum, remote verification, and no-overwrite behavior remain unchanged; no new archive operation enlarges the executor |

## Initial Hotspots And Intended Boundaries

The 2026-08-26 maintainability audit found that the architecture is coherent
but responsibility is concentrated in a few orchestration modules. The counts
below are an audit snapshot, not permanent line-count limits: the ten largest
package modules held about 47% of package code, and a diagnostic Ruff `C901`
run found 58 functions above complexity 10.

### Local web API

Keep `synthpopcan.webapi` as the supported composition point. Extract cohesive
route groups for models, generation, small-area work, runs, and data where the
existing behaviour supports the split. Route handlers should validate
HTTP-specific input, invoke one workflow, and translate its result or domain
exception. They must not own calibration, feasibility, persistence, or
research-policy decisions.

The route-registration slice is complete: `create_web_app` now constructs a
shared application context and delegates cohesive route groups, with exact
route-order and application-state characterization. The next slice is the
small-area preflight. Preserve event ordering and durable run behaviour while
moving its orchestration behind a narrow request/result boundary.

### Geography CLI

Keep the existing Click tree and every frozen command path. Split internal
implementation by user capability rather than arbitrary size:

- geography catalogue and verified downloads;
- analytical and display-boundary preparation;
- small-area planning and calibration;
- national execution; and
- maps and reports.

Each command adapter parses options, invokes a workflow, and renders a result.
Shared decisions belong in workflows or domain modules, not a new CLI utility
layer.

### Control packs

Keep `synthpopcan.control_packs` as a compatibility façade while separating:

- immutable pack definitions and registry lookup;
- compatibility, universe, support, and structural-zero validation;
- vintage-specific Statistics Canada Profile extraction and crosswalks; and
- evidence and manifest construction.

Pack definitions should become predominantly declarative. Validation consumes
those definitions instead of accumulating pack-specific branches in extraction
or presentation code.

### Archive and Zenodo tooling

Separate the maintainer archive workflow into:

- HTTP transport and exact response normalization;
- immutable manifest and evidence validation;
- correction and new-version state transitions;
- checkpoint persistence;
- remote post-write verification; and
- operator CLI, confirmation, and reporting.

The transition component should be pure where practical: given a manifest,
checkpoint, and verified remote state, it determines the next permitted action.
An executor performs effects. Existing fail-closed identity, authorization,
crash-recovery, no-overwrite, checksum, and final-verification behaviour remains
the contract. This extraction proceeds conservatively and may span later minor
releases; no new archive operation should enlarge the monolithic path.

### Localization

All newly covered CLI and web prose passes through the message-catalogue
boundary owned by the
[bilingual localization plan](2026-08-19-bilingual-localization.md). Domain and
workflow modules return language-neutral results and structured errors.
Presentation code may localize them without changing machine contracts.

## Enforced Dependency Rules

Extend `tests/test_architecture.py` as each boundary becomes real:

- route modules may depend on workflows, but workflows may not depend on route
  modules or FastAPI;
- CLI modules may depend on workflows and presentation helpers, but workflows
  may not depend on Click or Rich;
- domain modules may not depend on concrete filesystem, network, prompt, or
  process clients;
- the archive transition module may not depend on HTTP, terminal prompting, or
  checkpoint storage;
- presentation and localization modules may not define machine schema keys,
  identifiers, exit statuses, or numerical results; and
- public façades may delegate inward, but internal implementation modules may
  not import those façades backward.

Record a reproducible complexity baseline. A function changed by this tranche
must not increase above its recorded complexity without an explicit reason in
the review, and newly extracted orchestration should remain within the normal
Ruff `C901` threshold where practical. Complexity is a review signal, not a
substitute for responsibility and behaviour tests.

## Extraction Procedure

For each slice:

1. add characterization tests around current success, failure, evidence, and
   side-effect behaviour;
1. identify one responsibility with a distinct reason to change;
1. extract pure validation or transformation before moving effects;
1. retain the old supported function or module as a delegating façade;
1. add the corresponding forbidden-import architecture test;
1. compare the frozen public-interface and persisted-artifact fixtures;
1. run focused fault, crash/recovery, packaging, and installed-wheel tests; and
1. remove obsolete branches only after behavioural equivalence is established.

Do not combine responsibility extraction with a statistical-method change,
schema migration, CLI rename, or archive write. Land those as separately
reviewable changes.

## `1.2.0` Acceptance Gate

- `webapi` small-area preflight and route registration have explicit internal
  boundaries, with unchanged supported HTTP, run, event, and artifact
  behaviour;
- at least one feature-adjacent `cli_geo` or `control_packs` hotspot has reduced
  branching or responsibility count rather than another path added directly to
  it;
- the archive transition boundary is introduced or, if its safety proof cannot
  be completed in the release window, no new archive operation enlarges the
  current executor and the deferred extraction remains explicit;
- exact two-decimal combined branch coverage is at least `95.00%`, with the
  release candidate at or above `95.25%`;
- every beginner export is documented, newly added or changed supported symbols
  have docstrings, and the measured undocumented supported-surface count does
  not increase;
- all new user-facing CLI and web text in covered modules uses the localization
  boundary;
- architecture, public-interface, schema compatibility, type, lint,
  documentation, browser, fault-injection, and installed-distribution gates
  pass; and
- no supported CLI path, beginner export, advanced API, persisted schema, or
  machine-output fixture is removed or changed incompatibly.

## Continuing Ratchet

After `1.2.0`, revisit the concentration and complexity inventory at every
minor release. Choose the next extraction based on active feature pressure and
change risk, not merely the largest file. Document accepted boundary changes
in the contributor guide and architecture tests; record user-visible outcomes
in the changelog. Archive this plan only when responsibility ownership is part
of normal contribution practice and any remaining hotspots are explicitly
owned by successor plans.

## Non-Goals

- no package-wide rewrite or simultaneous module split;
- no breaking change to the frozen `1.x` interface;
- no universal dependency-injection framework;
- no line-count gate detached from responsibility or behaviour;
- no relocation of domain decisions into generic `utils`, `services`, or
  adapter helpers; and
- no weakening of runtime validation, provenance, privacy, or archive safety to
  make extraction easier.
