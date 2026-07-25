# ADR-0002: Keep The Web App Local, File-Backed, And Durable

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

Some readers benefit from forms, previews, and visible progress, while
population synthesis can take substantial time and produce artifacts too large
for browser memory. A hosted or multi-user application would introduce
authentication, remote data handling, storage, queueing, and operational
responsibilities that the project is not prepared to assume.

## Decision

`synthpopcan serve` starts a loopback-only local research workbench. Runs are
durable directories containing manifests, parameters, status, progress,
diagnostics, provenance, reproduction information, and output artifacts.
Long-running work executes outside the web request and writes results directly
to disk.

The first implementation runs one synthesis worker at a time. The HTTP layer
owns request validation and local job control; packaged HTML, CSS, and
JavaScript own interaction and presentation. The application is not a public
hosting target or a multi-user service.

## Alternatives Considered

- **Public hosted service:** rejected because it would require a substantially
  different privacy, security, governance, and operations model.
- **Keep runs only in browser state:** rejected because refreshes and browser
  memory limits would make research runs fragile.
- **Add a database and distributed queue:** rejected as unnecessary complexity
  for predictable single-user local execution.
- **Run long jobs inside HTTP requests:** rejected because cancellation,
  recovery, and durable progress would be unreliable.

## Consequences

- Researchers retain local control of inputs and outputs.
- Runs can survive browser refreshes and support later inspection.
- Local files and the run schema become compatibility and recovery concerns.
- Concurrent or remotely shared work requires a future decision rather than an
  incremental change to this architecture.

## Evidence And Related Records

- [Local web application runtime plan](../plans/archive/2026-07-10-local-web-application-runtime.md)
- [Local Web App documentation](../docs/web-app.md)
- [ADR-0001](0001-shared-python-workflow-core.md)
