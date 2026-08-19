# Simulation Interoperability And Data Handoff Plan

Status: conditional research; `0.8.0` neutral bundle completed\
Created: 2026-07-15\
Last updated: 2026-08-19\
Target: `0.8.0` neutral bundle; one demand-backed adapter only after `1.0.0`\
Next action: wait for a real consumer, pinned target contract, authorized
fixture, and maintainable import smoke test before selecting one adapter pilot\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md) | Foundations:
[linked-population schema](archive/2026-07-18-linked-population-schema.md) and
[external-data enrichment](archive/2026-07-15-ecosystem-enrichment.md)

## Purpose And Boundary

Make validated SynthPopCan populations straightforward to consume in an
external research model without turning SynthPopCan into a simulation
platform. SynthPopCan owns population construction, linkage, validation,
provenance, and export. A downstream model owns behaviour, dynamics,
interventions, calibration, execution, and interpretation.

A household/person bundle is a population contribution, not a runnable
simulation. A target may additionally require land use, facilities, disease
states, activities, schedules, travel skims, routes, contact networks,
coefficients, settings, or executable model code. The export must name these
missing inputs rather than inventing them.

## Existing Contracts To Compose

The exchange design starts from two released contracts:

- linked-population v1 defines CSV household/person tables,
  `synthetic_household_id`, `synthetic_person_id`, their foreign-key
  relationship, and optional household geography; and
- durable run v1 records run identity, software version, request, seed,
  reproduction information, artifacts, row counts, byte sizes, and SHA-256
  hashes.

The exchange manifest references these records and adds consumer-facing
semantics. It does not rename the stable identifiers, rewrite a source
population, or create a competing run-provenance system. An exported
standalone population without a durable run must still supply equivalent file
hashes and an explicit provenance reference.

## Simulator-Neutral CSV/JSON Bundle

The initial bundle is a directory, with an optional deterministic archive,
containing:

- `households.csv` and `persons.csv`;
- the linked-population descriptor;
- `manifest.json`, which identifies the exchange schema, originating run or
  standalone provenance, software version, files, hashes, row counts,
  relationships, geography and temporal coverage, access classifications, and
  validation records;
- a machine-readable JSON data dictionary for column types, units, code lists,
  missing-value semantics, observed-versus-modeled status, and weights; and
- a JSON validation/reproduction record with the exact library or CLI request.

Existing normalized geography or enrichment tables may be included only when
their released contracts and validation travel with them. The initial bundle
does not fabricate locations, activities, schedules, memberships, networks, or
routes merely to fill a future schema.

CSV and JSON are the authoritative `0.8.0` forms because they match the
released linked-population contract and are readable without new runtime
dependencies. Parquet, GeoParquet, GeoPackage, target-specific XML, and
RO-Crate remain optional future mappings. Add one only after semantic types,
dependency cost, round-trip fidelity, and an actual consumer have been
demonstrated.

The exchange contract specifies:

- required and optional files, primary keys, foreign keys, and cardinalities;
- categorical namespaces, units, weights, and scaling semantics;
- geography identifier namespaces, Census vintages, CRS and precision when
  spatial data exists;
- temporal units and time zones when temporal data exists;
- access, redistribution, and disclosure classification by file and sensitive
  field where needed;
- compatibility rules for additive changes and explicit migration for breaking
  versions; and
- whether the export is only a population contribution or a complete target
  input, with the latter allowed only when target validation proves it.

## Post-`1.0` Adapter Selection Gate

One post-`1.0` release may support one external target, selected only when all
of these exist:

1. a real user, collaborator, or reference model;
1. a concrete research question that fits SynthPopCan's public-health and
   public-service purpose;
1. a pinned target version and authoritative input contract;
1. public-safe target fixtures or permission to derive them;
1. a maintainable parser or minimal import smoke test; and
1. a clear list of external inputs that SynthPopCan will not provide.

Current platform research remains background in [NOTES.md](../NOTES.md), not a
release promise. ActivitySim, Starsim, Mesa, GAMA, MATSim, SUMO, FRED,
Vivarium, and AnyLogic remain candidates:

- ActivitySim can receive population tables but still needs land use, skims,
  settings, and coefficients.
- Mesa and GAMA have no universal population schema; without a concrete model,
  they merit loading examples rather than compatibility claims.
- Starsim requires a concrete disease-state and network mapping.
- MATSim and SUMO require activities, schedules, modes, locations, and
  transport networks that SynthPopCan does not currently produce.
- FRED, Vivarium, and AnyLogic require separate evidence of a stable,
  maintainable import path.

No popularity ranking selects the adapter. Fit to the research question,
contract stability, testability, maintenance cost, Canadian or Québec demand,
and dependency impact do.

## Adapter Contract

The selected adapter must:

1. declare accepted exchange and target versions;
1. validate required tables, keys, codes, units, weights, geography, time, and
   external prerequisites before export;
1. translate without silently inventing behaviour, mobility, health states, or
   target defaults;
1. write a mapping report listing source and target fields, conversions,
   defaults, dropped fields, expected losses, warnings, and unsupported
   semantics;
1. preserve originating run/provenance references, file hashes, and validation
   evidence;
1. reconcile source and exported row counts, links, and relevant aggregates;
1. state whether the result is a population contribution or runnable target
   input and enumerate missing external components; and
1. provide an exact reproduction command or Python call.

Target libraries and dependency stacks remain optional. Core bundle creation
and validation must work from a normal SynthPopCan installation.

## Release Slices

### `0.8.0`: Simulator-neutral exchange

Implement:

- a versioned exchange-manifest validator that composes linked-population v1,
  durable-run v1 where available, and released enrichment descriptors;
- shared Python bundle-writing and validation workflows used by any CLI or
  local-workbench presentation;
- required household/person CSV and JSON manifest, dictionary,
  validation/reproduction, hashes, and access classifications;
- tamper detection, foreign-key and row-count reconciliation, and explicit
  geography-vintage checks;
- a deterministic public synthetic example containing household/person data
  and only those optional geography or enrichment layers that already exist;
  and
- an installed-package example that reads and validates the bundle without a
  simulator or optional export dependency.

Validate the contract before declaring exchange schema v1 stable. If archives
are supported, normalize file ordering and metadata so identical input produces
identical archive bytes.

### Post-`1.0`: One demand-backed adapter pilot

After the selection gate passes:

- derive the mapping from independently reviewed target documentation and an
  official or authorized fixture;
- implement one adapter and prerequisite validator;
- produce mapping, reconciliation, provenance, and missing-input reports;
- demonstrate a parser or minimal import smoke test against the pinned target
  version; and
- document a complete, exact population-contribution handoff from a public
  synthetic SynthPopCan bundle.

Compatibility claims cover only the pinned versions and semantics exercised by
that evidence. Simulation outputs and substantive model validity remain
outside SynthPopCan's correctness claims.

## Deferred Decisions

No `0.8.2` adapter is committed. A second target, transport-plan export,
target-specific spatial form, or richer layer should be scheduled only after
the first pilot demonstrates real use and acceptable maintenance.

MATSim and SUMO remain conditional follow-ons until independently supplied and
validated activities, locations, schedules, modes, routes, and transport
networks exist. Mesa or GAMA examples become adapters only for a concrete model
with a testable schema. Starsim, FRED, Vivarium, and AnyLogic likewise require a
specific maintained target contract.

Parquet and GIS formats remain optional and must not enlarge the core
dependency set without measured benefit. RO-Crate mapping remains owned by the
research-software stewardship track after the native bundle stabilizes.

## Acceptance Criteria

### `0.8.0`

- A fresh standard installation can create, read, and independently validate
  the bundle without a simulator or optional format library.
- The bundle preserves `synthetic_household_id`,
  `synthetic_person_id`, household membership, row counts, weights, geography
  semantics, run provenance, and every recorded file hash.
- Any changed, missing, extra-required, or misclassified file fails validation
  with an actionable message.
- The public example reproduces deterministically and contains no restricted
  source material or prohibited derived values.
- The manifest clearly describes the export as a population contribution and
  lists absent simulation inputs.

### Post-`1.0` adapter pilot

- The supported target, version, fixture authority, mapping, prerequisites, and
  exact reproduction are documented and machine-checkable.
- Source and exported identifiers, links, row counts, weights, code mappings,
  units, and relevant aggregates reconcile, with all expected losses reported.
- The pinned target parser or minimal import smoke test succeeds in an optional
  compatibility tier.
- Simulator-specific dependencies remain optional, and no behaviour, network,
  schedule, state, or target default is silently invented.
