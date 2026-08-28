# Strict Typing Migration Plan

Status: active maintenance\
Created: 2026-08-01\
Last updated: 2026-08-28\
Target: incremental; not a numbered-release gate\
Next action: refresh the package-wide strict diagnostic baseline in `TYPE12-01`,
then begin the independent boundary slices below\
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

The package source and maintainer scripts are clean under Pyright `standard`.
A 2026-08-15 `--verifytypes`
audit reports all 1,854 exported symbols with known types: 100% public type
completeness when third-party-package unknowns are ignored. The former 33
missing/unknown-parameter diagnostics remain at zero.

The initial 2026-07-31 strict audit reported 986 diagnostics; 923 were
cascading unknown member, variable, or argument types. The first ratchet fixed
the parameter, general-type, and deprecated-annotation findings and reduced
the recorded total to 908. A reproducible package-wide audit is now available
through `pyrightconfig.strict.json`. The latest 2026-08-15 audit reports 1,095
diagnostics across 40 of 59 source files; 1,030 are cascading unknown member,
variable, or argument types. The higher raw total reflects eight source modules
added since the previous baseline as well as the remaining dynamic boundaries;
it is not a regression hidden behind a changed denominator. Nineteen source
files are strict-clean and blocking in Pyright's per-path strict list,
including the new public-interface contract validator and the newly ratcheted
exchange CLI.

Those strict diagnostic counts are a dated snapshot, not a current completion
claim. The recent source-boundary refactor and addition of `scripts` to the
blocking standard check require the `TYPE12-01` recount before another strict
trend is reported.

Recount the baseline after each substantial tranche rather than presenting the
2026-07-31 number as current indefinitely.

Run the non-blocking full audit with:

```bash
uv run pyright --project pyrightconfig.strict.json
```

## PR-Sized Work

Each boundary slice must retain runtime validation at untrusted inputs. Reaching
zero diagnostics by replacing validated structures with broad `Any` or
unchecked casts does not satisfy acceptance.

| ID | Status | Depends on | Deliverable | Acceptance |
| --- | --- | --- | --- | --- |
| `TYPE12-01` | `ready` | Current source tree and strict configuration | Reproducible current strict diagnostic baseline by module and rule | The command, date, source denominator, strict-clean paths, and diagnostic counts are recorded without weakening `standard` or exclusions |
| `TYPE12-02` | `blocked` | `TYPE12-01`, `RB12-02` | Typed small-area preflight request/result boundary | The selected modules are strict-clean or have only named framework exceptions; malformed runtime data still fails validation |
| `TYPE12-03` | `blocked` | `TYPE12-01` | Typed assurance report structures | Persisted and computed assurance fields narrow at one boundary; malformed evidence still fails validation and compatibility fixtures pass |
| `TYPE12-04` | `blocked` | `TYPE12-01` | Typed CLI output and presentation structures | CLI output helpers avoid unknown dictionaries, retain byte-stable machine fixtures, and pass focused CLI plus strict checks |
| `TYPE12-05` | `blocked` | `TYPE12-01` | Typed national-execution manifest and worker-message structures | Persisted/worker inputs validate at the boundary; resume and failure fixtures plus strict checks pass |
| `TYPE12-06` | `blocked` | `TYPE12-01` | Typed durable-run artifact and evidence structures | Run-store read/write, collision, rollback, and schema fixtures pass without unchecked persisted JSON |
| `TYPE12-07` | `blocked` | `TYPE12-01` | Typed GeoJSON and map-render adapter boundary | External shapes narrow once at the adapter; malformed geometries still fail clearly; map fixtures and strict checks pass |
| `TYPE12-08` | `blocked` | Completed applicable `TYPE12-02`–`TYPE12-07` slices | Strict-clean path-list ratchet and updated audit record | Every newly clean module is blocking in CI; the full diagnostic count is no higher; exceptions are narrow and documented |

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
