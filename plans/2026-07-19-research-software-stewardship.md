# Research-Software Stewardship And Publication Plan

Status: active, with a bounded stewardship baseline and gated publication work\
Created: 2026-07-19\
Last updated: 2026-07-27\
Target: complete the stewardship baseline before another model publication or
mirror; mature toward JOSS only after its public-development and research-use
gates are met\
Next milestone: settle model licensing, validate CFF metadata, capture the
source in Software Heritage, publish dated FAIR4RS and management records, and
release a tested bilingual 2021 case study for focused community introduction\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose And Boundary

Treat SynthPopCan as a maintained scholarly instrument and citable method, not
only as a package that emits CSV files. Stewardship covers software citation,
preservation, licensing, maintenance, reproducibility, responsible claims,
community feedback, and eventual scholarly publication.

This plan owns the bounded stewardship baseline, ongoing release policy,
community introduction, and JOSS maturation gates. It does not duplicate:

- source, language, access, CARE, or OCAP implementation, which belongs in the
  [external-data enrichment framework](2026-07-15-ecosystem-enrichment.md); or
- exchange bundles, RO-Crate experiments, or simulator adapters, which belong
  in the
  [simulation interoperability plan](2026-07-15-simulation-interoperability.md).

Adopt another standard or publication surface only when it solves a concrete
preservation, interoperability, governance, credit, or discovery problem.

## Stewardship Baseline

Complete the following bounded tranche before treating the project's
publication and preservation foundation as settled.

### Citation metadata

- **Done (2026-07-20).** `CITATION.cff` records the `0.6.2` concept and version
  DOIs, and a drift test checks its version and release date against package and
  changelog metadata.
- Add full Citation File Format schema validation to a local and CI
  documentation or release gate without adding a runtime dependency. Keep the
  existing release-drift test as a separate check.
- Keep `CITATION.cff` current for every later release. Add ORCIDs only when
  supplied and confirmed by their owners; never infer them.
- Preserve the current citation guidance distinguishing the software concept,
  a versioned software release, a prepared model, an upstream data source, and
  any later methods or application paper.

### Model licensing and archival publication

- **Done (2026-07-20).** GitHub releases are connected to Zenodo, the `0.6.2`
  software release and 32 public prepared models have archival records, and the
  release, concept, and model DOIs are exposed through project metadata,
  documentation, and the CLI.
- **Done (2026-07-20).** Model deposition tooling defaults to the sandbox and
  draft state, verifies source and uploaded bytes, checkpoints partial work,
  prevents accidental redeposition, and requires explicit production and
  per-record publication confirmation.
- Before publishing another prepared model or placing a model on a mirror,
  obtain an informed review of how any licence on SynthPopCan-authored model
  material should be represented beside continuing Statistics Canada Open
  Licence conditions. Record the decision in an ADR or equivalent durable
  record, update release guidance, and correct live archive metadata if the
  review changes the current representation.
- Treat metadata generation, validation, and draft preparation as candidates
  for automation. Preserve a human approval gate for irreversible production
  publication unless a later reviewed process establishes an equally clear
  safety boundary.
- Keep Git tags, GitHub Releases, PyPI artifacts, documentation, Zenodo records,
  identifiers, and checksums mutually consistent and test all deterministic
  relationships.

The ecosystem plan owns retention of source-bundle licence material and
licence/checksum fields in future immutable source manifests. This plan owns
the public model-archive decision and release presentation.

### Independent source preservation

- Request Software Heritage capture of the public GitHub origin.
- Verify that the captured snapshot contains the annotated `v0.6.2` release,
  record the relevant qualified SWHIDs, and link them from an appropriate
  preservation or release record.
- Revisit capture after important source releases or repository moves; do not
  imply that one snapshot replaces Git tags, Zenodo release records, or model
  archives.

### Dated FAIR4RS and management records

- Publish a lightweight, dated FAIR for Research Software self-assessment tied
  to the current release. For each FAIR4RS principle, link existing evidence,
  state the gap, and assign any product work to one active implementation plan.
- Publish a concise Software Management Plan covering ownership, decision and
  release authority, contribution and credit, dependency and security
  practice, testing, archival, licensing, support expectations,
  succession/bus-factor risk, and end-of-life policy.
- Reuse and link `CONTRIBUTING.md`, `SECURITY.md`, `RELEASING.md`, the ADRs,
  `CORRECTNESS.md`, and citation metadata rather than duplicating them.
- Review these two dated records at major releases or after a material change
  to maintainers, infrastructure, data authority, distribution, or governance;
  ordinary patch releases do not require a ceremonial rewrite.

Reproducibility evidence must preserve applicable software and model versions,
inputs and source versions, geography, seeds, configuration, commands,
checksums, validation evidence, licences, and known limitations. Reproducible
execution alone does not establish statistical fitness, representativeness,
privacy, or causal validity.

## Bilingual 2021 Case Study And Community Introduction

Treat dissemination as a focused effort to find users, reviewers, and research
collaborators, not a one-time publicity campaign.

### Tested launch artifact

Prepare a short English/French case study that:

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

Test the published commands as an installed-package smoke scenario. Resolve the
model-archive licensing decision before the case study presents its licence
language as settled.

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

- complete the model-archive licensing decision first;
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
- a durable model-licensing decision governs future archives and mirrors;
- the protected, human-approved Zenodo process is documented as the publication
  boundary;
- Software Heritage capture and the selected SWHIDs are recorded;
- dated FAIR4RS and Software Management Plan documents are public and linked
  from maintained project documentation; and
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
