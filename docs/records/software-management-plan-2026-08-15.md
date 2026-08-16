# Software Management Plan — 2026-08-15

**Software:** SynthPopCan\
**Record scope:** `0.9.0` baseline and work toward `1.0.0`\
**Owner and current release authority:** Darcy Quesnel\
**Review date:** 2026-08-15\
**Next routine review:** the `1.0.0` major release

This lightweight plan follows the [Software Sustainability Institute's
guidance](https://www.software.ac.uk/guide/writing-and-using-software-management-plan).
It records current practice and known risks; it does not imply institutional
support, funding, or a service-level agreement.

## Outputs and Scope

The project produces:

- an MIT-licensed Python package and command-line application;
- a local browser workbench backed by the same Python workflow core;
- task-oriented and API documentation;
- versioned linked-population, control-pack, assurance, enrichment, and
  exchange schemas;
- reviewed prepared-model and display-geodata artifacts published separately
  from the wheel; and
- tests, correctness evidence, release manifests, checksums, citation metadata,
  and provenance records needed to interpret those outputs.

Raw PUMFs, private research data, generated full populations, credentials, and
local caches are not project outputs and must not enter the public repository.

## Governance, Decisions, and Credit

Darcy Quesnel is the current maintainer, decision owner, and production release
authority. Repository-wide decisions are recorded as ADRs; observable work is
reviewed through commits and pull requests; releases follow
[`RELEASING.md`](https://github.com/dlq/synthpopcan/blob/main/RELEASING.md). No other person or institution should be
described as a maintainer, partner, funder, or release authority without their
confirmed agreement.

Contributions are accepted under the repository's MIT licence and reviewed by
the maintainer. [`CONTRIBUTING.md`](https://github.com/dlq/synthpopcan/blob/main/CONTRIBUTING.md) welcomes code,
documentation, accessibility, terminology, and methodological contributions.
Git history records implementation credit; `CITATION.cff`, release metadata,
and acknowledgements record scholarly credit. ORCIDs, affiliations, and roles
are added only when supplied and confirmed by their owners.

## Revision, Dependencies, and Security

Git and the public GitHub repository are the revision-control authority.
Protected `main` checks the supported Python matrix, web assets, documentation,
installed wheel, types, formatting, tests, and coverage. `pyproject.toml`
declares runtime and authoring dependencies; `uv.lock` records the resolved
development/release graph. Dependabot proposes bounded dependency updates;
CodeQL, secret scanning, and private vulnerability reporting provide security
signals.

Only the latest released line receives security fixes. Reports follow
[`SECURITY.md`](https://github.com/dlq/synthpopcan/blob/main/SECURITY.md); private or restricted data must never be
included. Dependency updates are accepted only after checks pass. Runtime
dependencies are kept separate from authoring tools such as CART training and
CFF validation.

## Development, Acceptance, and Release

The normal local acceptance gate is `./scripts/check.sh`; method-sensitive work
also runs `scripts/check-correctness.sh`. The checks cover lint, format, types,
tests, branch coverage, CFF schema validity, warning-clean documentation,
JavaScript tests, and browser scenarios. Release candidates additionally build
and inspect the wheel in an isolated environment and reconcile version, tag,
DOI, checksums, and release evidence.

[`CORRECTNESS.md`](https://github.com/dlq/synthpopcan/blob/main/CORRECTNESS.md) states only the claims supported by
tests and independent evidence. Passing the gate does not establish source-data
accuracy, privacy, representativeness, causal validity, or fitness for every
research use.

## Data, Privacy, and Licensing

Large or access-controlled sources remain in ignored local storage. Public
artifacts must contain no raw microdata rows, source row identifiers,
credentials, or private local paths. Model publication requires provenance,
disclosure-risk review, checksums, and a human release decision.

The source and software distributions use MIT. Statistics Canada PUMF-derived
artifacts retain the prescribed attribution and continuing Open Licence
conditions. [ADR-0014](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md)
accepts CC BY 4.0 as the maintainer-selected permissive default only for
original prepared-model rights the package author owns or controls. The layers
are cumulative, not alternatives, and do not relax privacy, attribution,
provenance, or no-endorsement safeguards. External review is optional and no
external approval is claimed.

Fail-closed tooling prepared byte-preserving corrected packages and
identifier-preserving archive metadata/new-version operations. After its
independent adversarial review, all 64 correction operations and 32 registry
updates remotely verified on 2026-08-16. The sanitized
[durable correction record](prepared-model-archive-correction-2026-08-16.md)
contains no credentials or private executor state, and the clean-clone gate
binds it to the installed registry.

## Distribution, Citation, and Preservation

- GitHub is the source and release-coordination surface.
- PyPI distributes released wheels and source distributions.
- Read the Docs publishes maintained documentation.
- Zenodo is the canonical citable archive for software releases and prepared
  models.
- Software Heritage independently preserves source history; the verified
  snapshot and tag identifiers are recorded in the [preservation
  record](software-heritage-2026-08-15.md).

Versioned DOIs, annotated tags, checksums, and build provenance connect these
surfaces. Mirrors may improve discovery but cannot silently become canonical or
rebuild different bytes under an existing identifier.

## Support, Resourcing, and Continuity Risk

The [stewardship and support policy](../stewardship.md) distinguishes tested
Ubuntu/Python environments from best-effort macOS and WSL use. Ordinary issue
support is best effort; security reports have a seven-day initial-response
target. No continuing funding, institutional service guarantee, or support
budget is documented.

The project currently has a bus factor of one: no second release authority or
named successor is recorded. Public source, an OSI licence, documented release
steps, dependency locks, CI, ADRs, archived releases, and preservation reduce
knowledge-loss risk but do not remove it. Before transferring authority, the
maintainer should document the successor's consent, repository and package
permissions, archive ownership, security contacts, and credential rotation. No
successor should be inferred from past collaboration or acknowledgement.

## End of Life

If active maintenance ends, the maintainer should, where access remains:

1. publish a dated notice in the README and documentation with the last
   supported version and date;
1. close or transfer security-reporting and package-publication authority
   deliberately rather than leaving stale credentials;
1. mark the GitHub repository archived and the PyPI project unmaintained or
   point users to an explicitly accepted successor;
1. request a final Software Heritage capture and retain Zenodo records and
   checksums; and
1. avoid deleting releases or reassigning identifiers to different artifacts.

The MIT licence permits forks, but no fork becomes the official successor
without a public, consensual transfer record.

## Review Triggers

Review this plan at every major release and whenever maintainers, release
authority, funding, support expectations, licensing, data authority,
distribution infrastructure, security posture, or end-of-life status changes.
Patch releases do not require a new dated copy when none of those facts change.
