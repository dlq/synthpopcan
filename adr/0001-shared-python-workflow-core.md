# ADR-0001: Use A Shared Python Workflow Core

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

SynthPopCan exposes related work through a Python library, Click commands, and
a local browser application. Implementing synthesis or validation separately
for each surface would let results, defaults, diagnostics, and provenance drift.
Making one adapter invoke another would also couple structured callers to
terminal output or a running server.

## Decision

Python domain modules own synthesis, controls, model generation, validation,
and diagnostics. UI-independent modules under `synthpopcan.workflows`
orchestrate file-backed workflows where shared orchestration is needed.

The beginner library, CLI, and loopback HTTP API call this Python code directly.
The HTTP API does not shell out to Click, the CLI does not call the HTTP API,
and the browser does not maintain a parallel implementation of the numerical
methods. Dependencies point inward from adapters toward workflows and domain
modules.

## Alternatives Considered

- **Implement each interface independently:** rejected because behavioral and
  numerical parity would be difficult to preserve.
- **Use the CLI as the integration layer:** rejected because parsing terminal
  output is not a stable structured contract.
- **Make HTTP the primary internal API:** rejected because notebooks, scripts,
  and commands should not require a running local service.

## Consequences

- Tests can compare interfaces against the same underlying behavior.
- Core modules must remain independent of Click, Rich, FastAPI, and browser
  code.
- Adapter-specific presentation remains separate even when domain behavior is
  shared.
- New interfaces should compose the workflow or domain layers rather than copy
  their algorithms.

## Evidence And Related Records

- [Local web application runtime plan](../plans/archive/2026-07-10-local-web-application-runtime.md)
- [Contributor module boundaries](../CONTRIBUTING.md#module-boundaries)
- [`tests/test_architecture.py`](../tests/test_architecture.py)
