# ADR-0005: Keep Source Records Local And Distribute Reviewed Model Artifacts

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

SynthPopCan works with public bulk data, Census microdata, and potentially
restricted research sources. Some prepared models can be distributed safely
after review, but source rows, generated outputs, and model artifacts do not
become public merely because code can read or produce them.

## Decision

Raw bulk downloads, Census microdata, restricted sources, generated
populations, and local run outputs remain in ignored local directories. They
are not bundled in the Python distribution or committed to the repository.

A prepared model can be published only after explicit provenance,
redistribution, disclosure-risk, validation, and licence review. Published
model packages contain no raw source rows or source identifiers, declare their
release classification, and carry integrity metadata. Large reviewed packages
are fetched on demand rather than increasing the installed wheel.

This boundary is a distribution policy, not a claim that every synthetic
artifact is anonymous, representative, or suitable for release.

## Alternatives Considered

- **Commit source data for convenience:** rejected because access,
  redistribution, repository size, and provenance conditions vary.
- **Bundle all models in the wheel:** rejected because model artifacts are
  large, independently versioned, and require separate review.
- **Treat trained models as automatically public:** rejected because models can
  retain sensitive detail and remain subject to source and licence conditions.
- **Treat generated populations as inherently safe:** rejected because
  disclosure and fitness require artifact-specific evidence.

## Consequences

- Reproducible work must record source identifiers, versions, checksums, and
  acquisition instructions without redistributing prohibited records.
- Model release is a reviewed maintainer workflow.
- Examples and tests need public-safe or synthetic fixtures.
- Local inspection commands require visible friction around private rows, but
  user confirmation does not itself establish permission to disclose them.

## Evidence And Related Records

- [Data documentation](../docs/data.md)
- [Contributor data and model safety policy](../CONTRIBUTING.md#data-and-model-safety)
- [Release process](../RELEASING.md)
- [Correctness assurance](../CORRECTNESS.md)
