# Research-Software Stewardship And Publication Plan

Status: active, with a bounded stewardship baseline and gated publication work\
Created: 2026-07-19\
Last updated: 2026-08-16\
Target: complete the stewardship baseline before another model publication or
mirror; mature toward JOSS only after its public-development and research-use
gates are met\
Next milestone: preserve the verified `1.0.0` DOI and Software Heritage
identifiers while applying the same exact-commit gates to later `1.x` releases\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose And Boundary

Treat SynthPopCan as a maintained scholarly instrument and citable method, not
only as a package that emits CSV files. Stewardship covers software citation,
preservation, licensing, maintenance, reproducibility, responsible claims,
community feedback, and eventual scholarly publication.

This plan owns the bounded stewardship baseline, ongoing release policy,
community introduction, and JOSS maturation gates. It does not duplicate:

- source, language, access, CARE, or OCAP implementation, which belongs in the
  [external-data enrichment framework](archive/2026-07-15-ecosystem-enrichment.md); or
- exchange bundles, RO-Crate experiments, or simulator adapters, which belong
  in the
  [simulation interoperability plan](2026-07-15-simulation-interoperability.md).

Adopt another standard or publication surface only when it solves a concrete
preservation, interoperability, governance, credit, or discovery problem.

## Pre-`1.0` Cut Line

The stewardship work required for `1.0.0` is limited to the accepted model-
licensing policy and archive-correction disposition, full CFF validation, a
verified Software Heritage capture, dated
FAIR4RS and software-management records, supported-platform and maintenance
claims, and the tested bilingual 2021 case study. The release must also publish
the exact stable CLI/API/schema inventory and compatibility policy owned by the
main roadmap.

Focused community introduction may proceed when useful but does not block
`1.0.0`. A model mirror, JOSS submission, broader outreach campaign, or new
publication surface remains demand- and maturity-gated after the stable release.

## Stewardship Baseline

Complete the following bounded tranche before treating the project's
publication and preservation foundation as settled.

### Citation metadata

- **Done (updated 2026-08-16).** `CITATION.cff` records the stable concept DOI,
  exact `1.0.0` version DOI `10.5281/zenodo.21961301`, release date, and completed
  Software Heritage snapshot. A drift test binds the version DOI to both
  citation blocks and keeps older preservation identifiers in their dated
  records rather than presenting them as current.
- **Done (2026-08-15).** Full Citation File Format schema validation now runs
  in local and CI gates without adding a runtime dependency. The existing
  release-drift test remains a separate check.
- Keep `CITATION.cff` current for every later release. Add ORCIDs only when
  supplied and confirmed by their owners; never infer them.
- Preserve the current citation guidance distinguishing the software concept,
  a versioned software release, a prepared model, an upstream data source, and
  any later methods or application paper.

### Model licensing and archival publication

- **Done (updated 2026-08-16).** GitHub releases are connected to Zenodo,
  software releases through `1.0.0` and 32 public prepared models have archival
  records, and release, concept, and model DOIs are exposed through project
  metadata, documentation, and the CLI. The `1.0.0` version DOI was recorded
  only after Zenodo minted it.
- **Done (2026-07-20).** Model deposition tooling defaults to the sandbox and
  draft state, verifies source and uploaded bytes, checkpoints partial work,
  prevents accidental redeposition, and requires explicit production and
  per-record publication confirmation.
- **Maintainer policy accepted (2026-08-15).** Darcy Quesnel accepted an
  open-by-default rights presentation that offers CC BY
  4.0 only for copyright or similar rights the package author owns or controls
  in original selection, organization, schema, documentation, and model
  representation. It leaves Statistics Canada Information under the Open
  Licence and presents the statements as cumulative and scoped, not
  alternatives for the package as a whole. It claims no author-controlled
  rights in source classifications, facts, or unprotectable numeric results.
  ADR-0014 is Accepted. External review is optional rather than a `1.0.0` gate,
  and the project claims no external approval or legal opinion. Open licensing
  does not relax anti-identification, disclosure-risk, attribution, provenance,
  or no-endorsement safeguards. Materially conflicting future authoritative
  guidance triggers prompt prospective review and correction.
- **Correction implementation completed (2026-08-15).** A
  live audit found that all 32 current model records retain Statistics Canada
  attribution and use CC BY 4.0, but none explains the CC scope and the
  immutable model JSON does not embed the complete rights block. The local
  correction builder now verifies each historical file against the registry,
  inserts only the exact licensing field while preserving every other JSON
  byte, and emits deterministic, non-overwriting candidates. The executor
  supports identifier-preserving metadata edits and new versions under each
  existing concept DOI with draft ownership, supersession, predecessor and
  replacement verification, exact registry candidates, transactional execution
  indexing, and operation/version/hash-aware resume. Independent adversarial
  review closed all three prior blockers; 137 focused tests, Ruff, Pyright, and
  diff checks pass. ADR-0014's implementation marker is Completed.
- **Correction execution completed (2026-08-16).** All 32 identifier-preserving
  metadata corrections and 32 non-overwriting package versions remotely
  verified, no mutable drafts remain, and the registry now selects the exact 32
  corrected releases. The tracked
  [transaction record](../docs/records/prepared-model-archive-correction-2026-08-16.md)
  and packaged machine-readable evidence preserve the 64 operation identities,
  old/new DOIs, sizes, hashes, and outcomes without credentials or private
  executor URLs.
- Treat review-only metadata generation and validation as candidates for
  automation. Historical assets are not eligible for sandbox upload. Preserve
  a human approval gate for irreversible production publication unless a later
  reviewed process establishes an equally clear safety boundary.
- Keep Git tags, GitHub Releases, PyPI artifacts, documentation, Zenodo records,
  identifiers, and checksums mutually consistent and test all deterministic
  relationships.

The ecosystem plan owns retention of source-bundle licence material and
licence/checksum fields in future immutable source manifests. This plan owns
the public model-archive decision and release presentation.

### Independent source preservation

- **Done (2026-08-15).** Software Heritage captured the public GitHub origin.
- **Done (2026-08-15).** The captured snapshot contains the annotated `v0.7.0`
  and `v0.9.0` releases; the relevant qualified SWHIDs are linked from a dated
  preservation record.
- **Done (2026-08-16).** A completed full visit preserves the annotated
  `v1.0.0` release, its exact source revision, and snapshot in a separate dated
  preservation record. The earlier capture remains available as historical
  evidence.
- Revisit capture after important source releases or repository moves; do not
  imply that one snapshot replaces Git tags, Zenodo release records, or model
  archives.

### Dated FAIR4RS and management records

- **Done (2026-08-15).** A lightweight, dated FAIR for Research Software
  self-assessment links evidence and assigns each remaining gap to an active
  plan or an explicit decision.
- **Done (2026-08-15).** A concise Software Management Plan covers ownership,
  decision and release authority, contribution and credit, dependency and
  security practice, testing, archival, licensing, support expectations,
  succession/bus-factor risk, and end-of-life policy.
- Reuse and link `CONTRIBUTING.md`, `SECURITY.md`, `RELEASING.md`, the ADRs,
  `CORRECTNESS.md`, and citation metadata rather than duplicating them.
- **Done (updated 2026-08-15).** The dated prepared-model licensing review
  records the accepted maintainer policy, the 32-record audit, its privacy and
  provenance boundaries, the correction disposition, and the optional future-
  review trigger without implying external approval.
- Review these two dated records at major releases or after a material change
  to maintainers, infrastructure, data authority, distribution, or governance;
  ordinary patch releases do not require a ceremonial rewrite.

### Supported environments and maintenance

- **Done (2026-08-15).** Publish a support policy that distinguishes the tested
  Ubuntu/Python and Chromium matrix from best-effort macOS/WSL paths and the
  unsupported native-Windows path.
- **Done (2026-08-15).** Record maintenance, security-reporting, succession,
  bus-factor, and end-of-life expectations without implying funded or
  guaranteed support.

Reproducibility evidence must preserve applicable software and model versions,
inputs and source versions, geography, seeds, configuration, commands,
checksums, validation evidence, licences, and known limitations. Reproducible
execution alone does not establish statistical fitness, representativeness,
privacy, or causal validity.

### Contributor and repository health

- **Done (2026-08-01).** The repository publishes contribution, conduct,
  security, pull-request, bug, feature, model-release, and question/help
  guidance; issue forms carry appropriate labels and warn against disclosing
  private or restricted data.
- **Done (2026-08-01).** The public repository description is outcome-focused,
  and empty Wiki and Projects surfaces are disabled so contributors are not
  sent to abandoned destinations.
- Keep first-contact documentation understandable to researchers who are not
  software developers, and treat documentation, terminology, method, and
  accessibility reports as first-class contributions.
- Review repository navigation and community-health files at major releases or
  after repeated contributor confusion.

## Bilingual 2021 Case Study And Community Introduction

Treat dissemination as a focused effort to find users, reviewers, and research
collaborators, not a one-time publicity campaign.

### Tested launch artifact

**Done (2026-08-15).** Prepare a short English/French case study that:

- installs a named released SynthPopCan version in a clean environment;
- fetches and inspects one public 2021 prepared model;
- records the model DOI, checksum, source, Census vintage, and known limits;
- generates a bounded population with a fixed seed and validates the linked
  output;
- shows the expected validation summary and enough provenance to repeat the
  example; and
- says explicitly that SynthPopCan generates and validates synthetic
  populations but does not simulate health outcomes, infer causal effects, or
  certify fitness or disclosure safety.

Test the published commands as an installed-package smoke scenario. Keep the
case study's licence language aligned with accepted ADR-0014 and preserve its
privacy, provenance, and fitness caveats.

### Focused introduction

- Prepare one concise bilingual introduction linking the repository,
  documentation, PyPI package, Zenodo DOI, case study, limitations, and a
  specific request for feedback.
- Share it first with three to five well-matched audiences, such as Canadian
  civic/open-data groups, research-software communities, CSDH/SCHN or related
  computational social-science networks, and a Montréal Python or PyData
  community. Reconfirm that a named venue is active and accepts this kind of
  introduction before posting.
- Seek direct feedback from public-health, health-geography, accessibility,
  food-environment, education, and health-services researchers when the case
  study speaks to their work.
- Direct reproducible problems and feature requests into public issues or
  discussions where possible. Record what people try and what blocks
  independent use; convert repeated findings into documentation, correctness,
  data, or interoperability work rather than optimizing for raw traffic.

## Optional Demand-Backed Model Mirror

Hugging Face is not a current deliverable. Reconsider a pilot only after
community feedback identifies a concrete model-discovery or download problem
that GitHub Releases, Zenodo, and `synthpopcan models fetch` do not solve.

If that gate is met:

- require the accepted model-archive licensing policy and completed archive
  correction;
- mirror exactly one representative 2021 package without rebuilding it;
- generate its model card from maintained registry metadata;
- identify Zenodo as the canonical citable archive and GitHub Releases as the
  project-built artifact source;
- verify byte identity and expose the DOI, checksum, source licence,
  provenance, limitations, and a pinned mirror revision;
- keep mirror access optional and add no required runtime dependency; and
- stop after the pilot unless measured discovery, reuse, or feedback justifies
  its maintenance cost.

Generated synthetic populations are datasets, not prepared models. Publishing
one would require a separate methodological, disclosure, provenance, licensing,
and dataset-card review.

## JOSS Maturation Gate

Status: **not submission-ready**.

The repository began its public history in June 2026. Current Journal of Open
Source Software screening requires more than six months of public, iterative
development and demonstrated research use. January 2027 is therefore only the
earliest plausible readiness review, not a submission deadline or promise.
Recheck the current JOSS rules before acting because editorial policy can
change.

Do not submit until all of these gates are met:

- the repository has more than six months of verifiably public, sustained,
  iterative development, with releases and meaningful public issue, pull
  request, discussion, or feedback history appropriate to the project;
- the software has demonstrated research use rather than only aspirational
  examples, with independent use, adoption, collaboration, citation, or a
  reproducible external case study treated as especially strong evidence;
- the scoped core contribution is feature-complete, installable, maintained,
  and clearly within JOSS research-software scope even though later enrichment
  and simulator work remains planned;
- the public repository has an OSI-compatible software licence, tests and CI,
  documentation, contribution and support guidance, releases, citation
  metadata, an archived DOI, and a reviewer-reproducible public-safe workflow;
- a reviewer can install the released package and reproduce representative
  2016 and 2021 behavior while understanding source-data, model-licensing,
  statistical-validity, and disclosure boundaries; and
- the paper's claims distinguish software correctness and reproducibility from
  domain validation, privacy assurance, representativeness, and causal
  inference.

When those gates are close:

1. audit the repository against the then-current JOSS author and review
   checklists;
1. add `paper.md`, its bibliography, and any figures to a Git-based branch or
   the repository as required by the current format;
1. describe purpose, research context, methods, architecture, validation,
   limitations, related software, community use, and research impact without
   making the JOSS paper a report of new scientific results;
1. include required funding and conflict-of-interest statements; and
1. include an accurate generative-AI usage disclosure naming the tools and
   versions used, where and how they assisted code, tests, documentation, or
   manuscript work, and confirming human review, validation, and ownership of
   the core design decisions.

Begin maintaining the AI-use record now while the development history can still
be reconstructed accurately. Community introduction and JOSS maturation
reinforce each other, but neither substitutes for method-specific validation or
responsible review of generated populations.

## Baseline Completion Evidence

The bounded stewardship baseline is complete when:

- full CFF schema validation and existing release-drift checks pass locally and
  in CI;
- accepted ADR-0014 governs future archives and mirrors without implying
  external legal review; its correction executor has passed the documented
  non-overwriting and resume gates; and exactly 32 metadata corrections, 32
  corrected package versions, and 32 registry updates have remotely verified
  tracked evidence;
- the protected, human-approved Zenodo process is documented as the publication
  boundary;
- Software Heritage capture and the selected SWHIDs are recorded;
- dated FAIR4RS and Software Management Plan documents are public and linked
  from maintained project documentation;
- contributor and repository-health guidance remains current and gives
  technical and non-technical contributors a clear, privacy-safe entry path;
  and
- the tested bilingual 2021 case study and focused community introduction are
  public, with substantive feedback captured as issues, documentation changes,
  or roadmap decisions.

An optional model mirror and a future JOSS submission are not required to close
this baseline. They remain demand- and evidence-gated follow-ons.

## References

- [FAIR Principles for Research Software (FAIR4RS)](https://www.rd-alliance.org/groups/fair-research-software-fair4rs-wg/outputs/?output=94498)
- [Citation File Format](https://citation-file-format.github.io/)
- [FORCE11 Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/)
- [Zenodo GitHub integration](https://help.zenodo.org/docs/github/)
- [Software Heritage](https://www.softwareheritage.org/)
- [Software Sustainability Institute: Software Management Plans](https://www.software.ac.uk/guide/writing-and-using-software-management-plan)
- [Digital Research Alliance of Canada research-software services](https://alliancecan.ca/en/services/research-software)
- [Research Software Canada (RSCAN), listed by the International Council of RSE Associations](https://researchsoftware.org/assoc.html)
- [Journal of Open Source Software submission requirements](https://joss.readthedocs.io/en/latest/submitting.html)
- [Journal of Open Source Software review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html)
