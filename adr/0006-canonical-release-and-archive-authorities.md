# ADR-0006: Give Publication Surfaces Defined Authorities

- **Status:** Accepted (retrospective)
- **Date:** 2026-07-25
- **Decision owners:** Maintainers

## Context

Software, documentation, source trees, and prepared models appear through
several services. Treating every copy as equally authoritative would make it
unclear which bytes, metadata, version, and citation a researcher should use.
Additional discovery services may be useful, but they should not weaken
version-specific reproducibility.

## Decision

Each publication surface has a defined role:

- PyPI distributes released Python packages;
- Git tags and GitHub Releases identify source releases and provide the
  project-built release assets;
- Read the Docs publishes the maintained user and API documentation;
- Zenodo is the canonical citable archive for released software and prepared
  model packages; and
- Software Heritage provides independent source-tree preservation when
  registered.

Checksums and versioned identifiers connect the surfaces. A secondary catalogue
or download surface, including a possible Hugging Face pilot, must reproduce
the exact reviewed bytes, link to the canonical DOI and licence, and identify a
pinned revision. It does not become the archival authority merely by hosting a
copy.

## Alternatives Considered

- **Treat GitHub alone as the archive:** rejected because durable scholarly
  citation benefits from archival records and DOIs.
- **Treat every mirror as canonical:** rejected because divergent metadata or
  bytes would create ambiguous research objects.
- **Rebuild artifacts for each service:** rejected because equivalent source
  does not guarantee byte-identical published packages.
- **Avoid secondary discovery services entirely:** rejected as a permanent
  rule because a bounded mirror may improve discovery without changing
  authority.

## Consequences

- Release procedures must reconcile versions, identifiers, metadata, licences,
  and checksums across services.
- Citations should identify the relevant software or model version and its
  archival DOI.
- Mirrors remain optional and can be removed without invalidating canonical
  records.
- A new publication service requires an explicit role rather than an ad hoc
  upload.

## Evidence And Related Records

- [Research-software stewardship plan](../plans/2026-07-19-research-software-stewardship.md)
- [Release process](../RELEASING.md)
- [Citation metadata](../CITATION.cff)
- [Model registry](../src/synthpopcan/models/__init__.py)
