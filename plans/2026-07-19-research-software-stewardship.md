# Research-Software Stewardship Maintenance Plan

Status: active maintenance; `1.0.0` baseline completed\
Created: 2026-07-19\
Last updated: 2026-08-19\
Target: preserve citation, archives, licensing, support, and publication
evidence in later releases\
Next action: retain the verified `1.0.0` DOI and Software Heritage identifiers
while applying the exact-commit publication process to later `1.x` releases\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Current Contract

SynthPopCan is maintained as a citable scholarly instrument, not only as a
package that emits files. Every public release or prepared artifact must keep
its software identity, source provenance, licensing scope, support boundary,
validation evidence, and archive identity understandable together.

The maintained baseline requires:

- valid citation metadata with stable concept and exact version identifiers;
- non-overwriting software and prepared-model archives;
- independently verifiable source preservation;
- explicit separation of author-controlled rights from continuing source
  conditions;
- truthful tested, best-effort, and unsupported environment claims;
- durable dated records for preservation, FAIR, management, and archive
  corrections;
- public documentation that distinguishes research evidence from universal
  fitness, privacy, or endorsement claims; and
- a tested bilingual Canadian case study using public, redistributable
  interfaces and artifacts.

The current identifiers and public records are summarized in
[Stewardship and Preservation](../docs/stewardship.md). Publication procedures
live in [RELEASING.md](../RELEASING.md).

## Maintenance Triggers

Review this plan whenever a change:

- prepares a software, model, geodata, or evidence release;
- changes citation, authorship, licensing, attribution, or source conditions;
- changes supported platforms, maintenance expectations, or public interfaces;
- adds an archive, registry, mirror, catalogue, or scholarly-publication
  surface; or
- changes a public stewardship, reuse, FAIR, or preservation claim.

Never infer or pre-record an external identifier. Add a DOI, SWHID, archive
record, or completion statement only after the public object exists and its
identity has been independently verified.

## Ongoing Release Obligations

For each later release:

1. bind citation metadata, changelog, package version, tag, CI, distributions,
   and release evidence to one exact commit;
1. verify public archives, attestations, checksums, documentation, and package
   indexes after publication;
1. preserve older version identifiers and dated records rather than rewriting
   their historical context;
1. add a new dated preservation record when the current Software Heritage or
   archive identity changes; and
1. keep prepared-model licensing, provenance, and non-overwriting version
   rules enforced in package bytes and publication tooling.

## Conditional Work

These are not current release commitments:

- a JOSS submission before public-development and independent-research-use
  evidence satisfies its gate;
- a model mirror without demonstrated availability demand and maintained
  integrity checks;
- another publication standard or metadata surface without a concrete
  preservation, governance, credit, or discovery problem; or
- broader outreach that overstates bounded methods, privacy, or support
  evidence.

Simulator-specific interoperability remains owned by the
[Simulation Interoperability Plan](2026-07-15-simulation-interoperability.md).

## Preserved Baseline

The detailed implementation, archive correction, FAIR4RS assessment, software
management plan, case-study preparation, and JOSS readiness analysis through
`1.0.0` are preserved as the
[Research-Software Stewardship Baseline](archive/2026-07-19-research-software-stewardship-baseline.md).
That file is historical evidence, not the current task list.
