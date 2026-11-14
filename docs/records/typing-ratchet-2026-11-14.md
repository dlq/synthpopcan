# Strict Typing Ratchet — 2026-11-14

The blocking Pyright configuration now checks the complete package and scripts
in standard mode, with the named strict paths in `pyrightconfig.json`. This
tranche added strict checks for the small-area preflight, durable worker and run
store, assurance, CLI presentation, national batch contract and GeoJSON adapter.
The preflight uses four narrowly identified private-helper exceptions and the
run store uses one existing internal writer exception. The external JSON
containers narrowed by these boundaries are checked before a type cast; the
contracts do not rely on unchecked source structures.

The [before snapshot](typing-ratchet-before-2026-11-14.json) contains 6,042
strict errors in `src/` and `scripts/`, filtered from the audit taken before
these typed-boundary changes. It was taken after the first draft localization
checker was added. The [after snapshot](typing-ratchet-after-2026-11-14.json)
contains 5,504 errors with the same source-and-script scope. The after audit
analyzed 124 files. Five existing files became strict-clean: `assurance.py`,
`cli_output.py`, `jobs.py`, `runs.py` and `workflows/preflight.py`; each is now
in the blocking strict-path list. Both new contract modules are also blocking.
The full package is **not** strict-clean; remaining diagnostics continue to be
tracked as incremental work.

The earlier [October baseline](readiness-2026-10-22/typing.json) recorded 1,912
errors across 86 analyzed files. Its raw total is not directly comparable to
today's 124-file audit: substantial package and script work was added or
extracted in the meantime. This record does not claim that all diagnostics
introduced since October have been removed. It records the before/after change
for this tranche using the same directory scope, including new files.

`pyrightconfig.strict.json` now explicitly includes `src` and `scripts`, so
ignored local run directories and generated scratch files do not silently change
the audit denominator. Reproduce the current inventory with:

```bash
uv run --locked python scripts/audit_release_readiness.py typing --output /tmp/synthpopcan-typing.json
```
