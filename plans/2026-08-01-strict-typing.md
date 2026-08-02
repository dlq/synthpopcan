# Strict Typing Migration Plan

Status: active maintenance ratchet\
Created: 2026-08-01\
Last updated: 2026-08-02\
Target: incremental; not a numbered-release gate\
Next action: type the shared dynamic-data boundaries in assurance, preflight,
CLI output, national execution, run artifacts, and GeoJSON/map handling\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose And Boundary

Move the source package from Pyright `standard` toward `strict` without hiding
uncertainty behind blanket `Any`, unchecked casts, or validation models created
only to silence the checker. The migration improves maintainability and
interface confidence; it does not by itself establish numerical or research
validity.

Package-wide `standard` mode remains blocking. Strict mode is a ratchet rather
than an all-at-once release requirement unless a future release explicitly
adopts it as a gate.

## Baseline

The package is clean under Pyright `standard`. A 2026-08-02 `--verifytypes`
audit reports all 1,453 exported symbols with known types: 100% public type
completeness when third-party-package unknowns are ignored. The former 33
missing/unknown-parameter diagnostics remain at zero.

The initial 2026-07-31 strict audit reported 986 diagnostics; 923 were
cascading unknown member, variable, or argument types. The first ratchet fixed
the parameter, general-type, and deprecated-annotation findings and reduced
the recorded total to 908. A fresh 2026-08-02 audit reports 921 diagnostics
across 35 of 51 source files; 864 are cascading unknown member, variable, or
argument types. Sixteen source files remain strict-clean and blocking in
Pyright's per-path strict list.

Recount the baseline after each substantial tranche rather than presenting the
2026-07-31 number as current indefinitely.

## Sequenced Work

1. Keep `standard` blocking for the complete package and the existing
   strict-clean path list blocking against regression.
1. Type dynamic-data boundaries shared by assurance and preflight reports, CLI
   output, national execution manifests, run artifacts, and GeoJSON/map paths.
1. Retain validated Pydantic models at untrusted HTTP, persisted JSON, and
   worker-message boundaries instead of immediately converting them to
   `dict[str, Any]`.
1. Prefer `TypedDict`, dataclasses, and protocols for trusted internal
   structures.
1. Concentrate root fixes in `map_render.py`, `cli_output.py`, `webapi.py`,
   `national_execution.py`, `tree.py`, and `assurance.py` before addressing
   cascades.
1. Isolate pandas, pyshp, and scikit-learn behind typed adapters or reviewed
   stubs, and document narrow framework exceptions.
1. Expand the strict path list whenever a module reaches zero diagnostics.

## Completion Criteria

- The full source package passes strict mode apart from narrowly documented
  third-party or framework exceptions.
- Standard and strict-clean checks remain blocking in CI throughout migration.
- Public signatures remain complete and compatible unless a separately
  reviewed interface change is intended.
- No tranche relies on blanket `Any`, unchecked casts, or Pydantic models whose
  only purpose is satisfying the type checker.
