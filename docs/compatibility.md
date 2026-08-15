# Compatibility Policy

SynthPopCan `1.0.0` establishes a stable interface for research scripts,
recorded command lines, and persisted project artifacts. The compatibility
contract is deliberately narrower than every name or JSON object in the source
tree: it covers the surfaces that users are expected to call, record, or keep.

The exact contract is shipped inside every wheel and source distribution as
`synthpopcan/contracts/public-interface-v1.json`. It inventories:

- every command, subcommand, argument, and option in the `synthpopcan` command
  tree;
- the top-level beginner Python API and every advanced member curated in the
  {doc}`API reference <api>`;
- the common command output-stream and exit-status rules; and
- every supported persisted schema identifier, separately from diagnostic,
  cache, benchmark, and UI-only identifiers.

The manifest has schema identifier `synthpopcan-public-interface-v1` and takes
effect with SynthPopCan `1.0.0`. Development releases before `1.0.0` may still
revise the candidate contract. Once `1.0.0` is published, the rules below apply
throughout the `1.x` series.

## Command-Line Contract

Recorded command paths, argument and option names, required/optional status,
accepted choices, and option defaults in the manifest are supported for all
`1.x` releases. A minor release may add a command or an optional option, but it
will not silently rename or remove an existing command or option, change an
existing option's meaning, or make an optional input required.

All commands follow these process-level rules:

| Exit status | Meaning |
| --- | --- |
| `0` | The requested command completed successfully. |
| `1` | A documented input, data, filesystem, network, or runtime check failed. |
| `2` | Click rejected the command-line syntax or option usage. |

In human mode, standard output contains results and workflow narration; some
commands also narrate progress, warnings, or validation findings there.
Standard error always carries Click's usage and final error messages, and many
commands also segregate download progress or file-written status there. Human
mode does not promise a machine-parsable separation between those streams.

When a command that exposes `--format json` reaches its result-reporting step,
it writes exactly one complete JSON value to standard output. Operational
messages from that completed work go to standard error. A failure before a
report can be built may leave standard output empty. A validation command may
write a complete failing report and then exit with status `1`; callers must
check both the JSON and the process status. Human-readable wording, table
decoration, colour, and line wrapping may improve within `1.x`; scripts should
use `--format json` or a written versioned artifact instead of scraping a
displayed table.

`-h` and `--help` remain available at every command level. The packaged
manifest is the exhaustive machine-readable inventory; the workflow chapters
remain the interpretive guide to inputs, outputs, and correctness limits.

## Python Contract

Names in `synthpopcan.__all__` are the stable beginner API taught as:

```python
import synthpopcan as spc
```

The explicitly listed members in the {doc}`API reference <api>` are supported
advanced APIs. The manifest records their import paths, whether each member is
a function, class, or value, and the callable parameter shape. Within `1.x`, a
release may add a symbol or an optional keyword parameter, but will not remove
or rename a listed symbol, remove a parameter, make an optional parameter
required, or change the documented meaning of an existing result.

Modules, attributes, and helpers beginning with `_` are internal. A public name
that merely happens to exist but is neither a top-level export nor explicitly
listed in the API reference is also internal unless another documentation page
states a narrower artifact contract for it. Internal code can change in a
minor release.

In particular, `synthpopcan.da_proof` contains the bounded pre-release proof
builder, while `synthpopcan.national_execution` contains restart, batching, and
cache machinery behind the supported `synthpopcan.national_small_area`
workflow. Those two backend modules remain importable for maintainers but are
not part of the 1.x Python compatibility contract.

SynthPopCan ships `py.typed`. Supported Python versions, static types, and
runtime validation are part of the quality gate, but a type annotation may be
broadened compatibly. Tightening an accepted input type or weakening a promised
result type is a breaking change.

## Persisted Artifact Contract

Only identifiers under `persisted_schemas.supported` in the packaged manifest
are durable interchange or project-record contracts. An artifact bearing one
of those identifiers remains readable across `1.x`, subject to its documented
integrity, provenance, source-access, and validation requirements.

Compatible releases may add optional object members or allow new categorical
values where the individual schema already permits extension. Readers must
continue to tolerate those documented extensions. Renaming a required member,
changing its meaning, changing key or relationship semantics, or requiring a
new table needs a new schema identifier such as `...-v2` and a documented
migration or regeneration path. A new writer may produce v2, but a 1.x release
does not reinterpret old v1 bytes as if they had v2 meaning.

Identifiers under `persisted_schemas.internal` make derived data
self-describing, but they do not create a durable interchange promise. These
cover rebuildable caches, diagnostics, benchmark results, web responses, and
bounded proof artifacts. Keep the originating inputs and commands rather than
depending on those intermediate representations across versions.

CSV schemas remain intentionally extensible unless their own documentation
says otherwise. For example, linked population v1 freezes identifiers and the
household/person relationship while permitting additional demographic columns.

## Deprecation and Breaking Changes

A supported interface may be deprecated when a clearer or safer replacement is
available. Deprecation notices must name the replacement in the changelog and
relevant documentation. The old surface remains functional for the rest of
`1.x`; removal or an incompatible semantic change waits for the next major
release.

An urgent security or correctness issue can require rejecting data that was
previously accepted. Such a change must be narrowly scoped, documented as a
security or correctness exception, and preserve a migration or regeneration
path whenever safely possible. Compatibility never requires silently accepting
corrupt, unsafe, internally inconsistent, or falsely described research data.

## Contributor Check

After intentionally changing a public surface, regenerate the candidate
manifest and review the diff:

```bash
uv run python scripts/build_public_interface.py
```

Normal checks use `--check` and fail when CLI parameters, curated Python names,
callable parameter shapes, or schema classifications drift. The wheel smoke
test performs the same semantic comparison from an isolated installation, so a
source checkout cannot mask missing package data or exports.
