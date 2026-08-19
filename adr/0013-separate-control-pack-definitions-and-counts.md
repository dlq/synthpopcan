# ADR-0013: Separate Control-Pack Definitions From Geography Counts

- **Status:** Accepted
- **Date:** 2026-08-10
- **Decision owners:** Maintainers

## Context

Small-area calibration needs more than a CSV of counts. A defensible run must
also identify the Census vintage and geography, population universe, source
rows, category crosswalks, candidate derivations, suppression and zero-cell
policy, required linked fields, supported claims, and known limitations.

Embedding all per-geography Census counts in a package definition would make
the contract large, obscure source exclusions and revisions, and encourage a
pack identifier to be mistaken for proof that any uploaded counts or
geography set are valid. Leaving all semantics implicit in CSV headers would
make compatibility impossible to inspect before a fit.

## Decision

Use two explicit inputs with different responsibilities:

- a strict, checksummed `synthpopcan-control-pack-v1` manifest declares the
  reviewed compatibility, source, universe, crosswalk, derivation, margin,
  suppression, provenance, limitation, and permitted-claim contract;
- normalized household and person `ControlTable` inputs carry the actual
  per-geography counts selected for one run; and
- a strict checksummed `synthpopcan-control-pack-evidence-v1` document carries
  pack identity, control-table hashes, source revisions, and companion values,
  such as total population and persons in private households, that are needed
  to prove the declared universe reconciliation.

Built-in `0.9.0` packs are definitions only. They do not bundle or download
Census counts. The eight initial built-in manifests cover the 2016 and 2021 core
private-household profile at CSD, CT, ADA, and DA levels. A feasibility plan
must validate the manifest, candidate fields and categories, linked entities,
exact margin structure, common geography set, structural support, and supplied
count and universe-evidence tables before calibration. It may not silently
remove a margin or geography to make a request pass.

The control-pack identifier is an additive declaration accepted by the shared
library, CLI, and local-web workflow. Existing normalized control inputs remain
usable without a pack, but only a declared and passing pack plan supports the
pack-specific claims. Later packs add versioned manifests through the same
extension point rather than requiring a command or API option for each new
control family.

## Alternatives Considered

- **Bundle national count tables inside every pack:** rejected because it
  conflates a reusable semantic contract with large, revision-sensitive data
  and makes suppression or bounded geography selection less visible.
- **Store only pack IDs in code:** rejected because persisted runs could not
  independently inspect or hash the exact semantic definition.
- **Infer the pack from CSV dimensions:** rejected because matching column
  names do not establish Census vintage, universe, crosswalk, source revision,
  or compatible generated categories.
- **Require a pack for every legacy calibration:** deferred until the `1.0.0`
  interface review; raw normalized controls remain a useful generic path and
  the pre-`1.0` tranche is additive.
- **Create separate commands for each control family:** rejected because it
  would freeze a non-extensible CLI surface immediately before `1.0.0`.

## Consequences

- A pack can be listed, inspected, round-tripped, and compatibility-checked
  without downloading or fitting data.
- A run remains explicit about the exact count files and geography
  intersection it used.
- Pack definitions need independent versioning and semantic checksums; changed
  crosswalks or policies produce a new reviewable definition.
- Built-in availability does not imply wall-to-wall Canadian coverage. CT is
  not national, and the private-household age-by-sex/gender margin is eligible
  only under its declared universe reconciliation.
- Uncontrolled model fields remain broad-model estimates and are listed as
  uncontrolled even when carried through a calibrated linked population.

## Evidence And Related Records

- [Expanded small-area controls plan](../plans/2026-08-01-expanded-small-area-controls.md)
- [Small-area control coverage inventory](../docs/small-area-control-coverage.md)
- [Explicit Census geography identity](0007-explicit-census-geography-identity.md)
- [Versioned linked-population schema](0003-versioned-linked-population-schema.md)
- `synthpopcan.control_packs`

## 2026-08-19 Additive Implementation Note

The same decision boundary now supports eight expanded-housing and eight broad
private-household manifests, for 24 built-ins in total. The new
packs reuse the separate count and evidence contracts; no Census counts were
added to package definitions and the eight stable core manifests remain
available unchanged.
