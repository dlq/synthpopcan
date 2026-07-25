# Research-Software Stewardship Plan

Status: planned and ongoing\
Created: 2026-07-19\
Last updated: 2026-07-25\
Target: immediate maintenance, `0.7.x`, `0.8.x`, and maturity follow-ons\
Next action: add full CFF schema validation, review the licence representation
and safe automation of model archives, define the Hugging Face distribution
pilot, prepare the focused bilingual community introduction, and register
important releases with Software Heritage\
Roadmap: [PLANS.md](../PLANS.md) | [Plan index](README.md)

## Purpose

Treat SynthPopCan as a maintained scholarly instrument and citable method, not
only as a package that emits CSV files. The project sits across research
software engineering, computational social science, public-health research,
and the digital humanities. Its stewardship must therefore cover numerical
correctness and reproducibility as well as the history and meaning of Census
categories, bilingual terminology, provenance, exclusions, uncertainty,
accessibility to non-programmers, and responsible reuse.

Adopt standards only where they solve a concrete preservation,
interoperability, governance, or credit problem. Domain conventions such as
TEI or IIIF are not core requirements unless a later humanities use case
actually needs them.

## Immediate And Ongoing Work

### Citation and scholarly credit

- **Done (2026-07-20).** Update `CITATION.cff` for every release and test that
  its version and release date agree with package and changelog metadata. The
  file now tracks `0.6.2`, `RELEASING.md` covers it, and
  `tests/test_docs.py::test_citation_metadata_matches_release` guards it.
- Add full CFF validation to an appropriate local or CI documentation/release
  gate without imposing a new runtime dependency.
- Add author ORCID identifiers only when supplied and confirmed by their
  owners; never infer them.
- **Done (2026-07-20).** State clearly how users should cite the software
  version, archived release, prepared models, data sources, and any associated
  methods publication. The README "How To Cite" section distinguishes the
  concept, version, and package DOIs, `CITATION.cff` records the concept and
  version DOIs, and `synthpopcan models show` prints each package's DOI.
- Retain the licence agreements shipped inside each Statistics Canada PUMF
  download. The catalogue pages state the product bundle "contains ... all
  licence agreements", but the local `data/raw` copies keep only the data and
  variable metadata. Archived packages cite the Open Licence, so the agreement
  actually distributed with the source should be retained beside it as
  provenance rather than relied on from memory.
- Follow the FORCE11 software citation principles: make software a first-class
  research output with importance, credit, unique identification, persistence,
  accessibility, and version specificity.

### Persistent preservation and releases

- **Done (2026-07-20).** Connect GitHub releases to Zenodo, archive the `0.6.2`
  release and prepared model packages, and expose release, concept, and model
  DOIs in metadata, docs, and the CLI.
- Before further model publication, obtain an informed review of how the
  licence on SynthPopCan-authored model material should be represented beside
  the continuing Statistics Canada Open Licence conditions. Update the live
  Zenodo records if that review changes the current representation.
- Verify archival metadata, authors, licence, related identifiers, checksums,
  and bilingual title/description capability before making publication fully
  automatic.
- Register or verify Software Heritage capture and record SWHIDs for important
  releases so cited source trees remain independently identifiable.
- Keep Git tags, GitHub Releases, PyPI artifacts, documentation, Zenodo records,
  and archival identifiers mutually consistent and test what can be tested.

### Hugging Face model-distribution pilot

Evaluate Hugging Face as a **secondary discovery and download surface** for
prepared models, not as the project's archival authority. Zenodo should remain
the canonical citable archive, and GitHub Releases should remain the source of
the release artifacts. A Hugging Face copy must point readers back to the
corresponding DOI, release, documentation, source licence, and provenance.

Keep the first experiment deliberately small:

- Create a SynthPopCan organization or namespace and one collection for
  prepared Census 2021 models.
- Publish one model repository for each of
  `canada-2021-all-fields`, `quebec-2021-all-fields`, and
  `montreal-cma-2021-all-fields`. Copy the exact existing compressed package
  bytes rather than rebuilding or transforming them for Hugging Face.
- Generate each model card from the model registry so its identifier, compatible
  SynthPopCan version, Census vintage, geography, source PUMF, frequency/CART
  method, intended and unsuitable uses, limitations, privacy review, DOI,
  validation summary, checksum, and CLI and Python examples do not drift from
  the package and public documentation.
- Represent Statistics Canada Open Licence conditions explicitly. If the Hub
  cannot name that licence directly, use its custom-licence metadata fields and
  link to the authoritative licence text. Complete the broader model-archive
  licence review before treating this representation as settled.
- Tag or otherwise record the published Hub revision, verify its SHA-256 digest
  against the GitHub/Zenodo artifact, and use a pinned revision in any
  reproducible download example rather than relying on a moving default branch.
- Keep Hub access optional during the pilot. Do not add
  `huggingface_hub` as a required runtime dependency or silently change the
  existing model-fetch path. Assess an explicit mirror or fallback only after
  the pilot establishes a useful maintenance and integrity model.
- Treat generated synthetic populations as **datasets**, not models. Publishing
  them would require a separate methodological, disclosure, provenance,
  licensing, and dataset-card review.

The pilot succeeds only if all three repositories are publicly understandable
without private context, model-card metadata can be regenerated from maintained
project records, downloaded bytes match the canonical checksums, DOI and
licence relationships are unambiguous, and an unauthenticated clean environment
can retrieve a pinned artifact. Before expanding to the full catalogue, review
whether the Hub materially improves discovery, citation, reuse, or community
feedback relative to its maintenance burden.

Stop or redesign the experiment if publication requires manual duplicate
metadata, produces version ambiguity, obscures the canonical archive, or cannot
represent attribution and licence conditions responsibly.

### FAIR4RS and reproducibility

- Perform and publish a lightweight FAIR for Research Software (FAIR4RS)
  self-assessment covering findability, accessibility, interoperability, and
  reusability; turn gaps into versioned roadmap tasks.
- Repeat the assessment at major releases or after material distribution,
  schema, governance, or archival changes.
- Preserve exact software/model versions, inputs, geography and source
  versions, seeds, configuration, commands, checksums, validation evidence,
  licences, and known limitations for every reproducible run or bundle.
- Keep correctness claims scoped: reproducible execution does not by itself
  establish statistical fitness, representativeness, privacy, or causal
  validity.

### Software management and governance

- Write a concise Software Management Plan describing ownership, maintenance,
  roles, dependency and security practice, testing, releases, archival,
  licensing, citation, succession/bus-factor risk, and end-of-life policy.
- Review the plan at major releases and when maintainers, infrastructure, data
  access, or institutional responsibilities change.
- Document decision authority and contribution/credit practices without
  overstating institutional endorsement.
- Engage with the Digital Research Alliance of Canada and the Research
  Software Association of Canada where their training, preservation,
  sustainability, or community practices would materially help the project.

## Discoverability, Community Engagement, And Scholarly Publication

Treat dissemination as a staged effort to find users, reviewers, and research
collaborators rather than a one-time publicity campaign. Do not imply that
SynthPopCan simulates health outcomes: it generates and validates synthetic
populations that can support downstream public-health, social-science,
accessibility, and service-planning research.

### Focused community introduction

- Prepare one concise English/French project introduction with the repository,
  documentation, PyPI installation, Zenodo DOI, current limitations, a concrete
  reproducible Census 2021 example, and a specific request for feedback.
- Introduce the project first through a small number of well-matched venues:
  Canadian civic/open-data communities such as Civic Tech Toronto, Code the
  North or Code for Montreal, and the Canadian Open Data Society; Canadian and
  international research-software communities including RSCAN and ReSA;
  CSDH/SCHN and related computational social-science or digital-humanities
  networks; and PyData Montreal or Montreal Python for a technical demo.
- Seek direct feedback from Canadian public-health, health-geography,
  accessibility, food-environment, education, and health-services researchers
  once a use case speaks to their work. Prefer targeted conversations and
  demonstrations to undifferentiated promotion.
- Use the maintainer's professional channels and an appropriate Python project
  showcase to make the initial release discoverable, but avoid posting the same
  bare repository link across many communities.
- Record which audiences respond, what they try, and what blocks independent
  use. Convert repeated findings into documentation, interoperability, data,
  or correctness tasks rather than optimizing for raw traffic.

### JOSS preparation

Treat a Journal of Open Source Software paper as a serious near-to-medium-term
scholarly publication goal, with submission timing determined by readiness
rather than an arbitrary release number. Before submitting:

- confirm that the software meets JOSS scope and substantial-scholarly-effort
  expectations, and that the paper makes a clear claim about the research
  problem solved rather than repeating the user documentation;
- demonstrate credible research use, preferably including an independent user,
  collaborator, citation, application, or reproducible case study beyond the
  maintainer's own development examples;
- keep the public repository, OSI-compatible software licence, contributor and
  governance guidance, issue history, tests, correctness claims, documentation,
  examples, citation metadata, releases, and archived DOI in reviewable shape;
- prepare a compact JOSS paper describing purpose, domain context, method,
  architecture, validation and correctness evidence, limitations, related
  software, and research impact, with claims carefully separated from domain
  validation, privacy assurance, and causal inference;
- ensure a reviewer can install a released package, reproduce a representative
  2016/2021 workflow from public-safe inputs, inspect its provenance and
  validation evidence, and understand any data-access or licensing boundary;
  and
- conduct a pre-submission review against the current JOSS author guidelines
  and checklist, resolve avoidable documentation or packaging gaps, and identify
  appropriate domain expertise for peer review without attempting to select or
  influence reviewers improperly.

Community introduction and JOSS preparation reinforce each other: early users
provide evidence of usability and scholarly relevance, while publication
readiness improves the materials those users need. Neither substitutes for
method-specific validation or responsible review of generated populations.

## 0.7.x: Data And Knowledge Governance

- Integrate bilingual source metadata and terminology provenance with the
  enrichment contract: distinguish official translations from reviewed
  project translations and make omissions and fallbacks visible.
- Apply CARE principles alongside FAIR when data concern Indigenous Peoples,
  communities, lands, or knowledge; open availability alone is not adequate
  authority for use.
- Where First Nations data are involved, require an OCAP-informed governance
  review and appropriate community/steward participation. Do not claim that a
  generic checklist establishes OCAP compliance.
- Record access authority, collective benefit, control, responsibility,
  ethics, permitted purposes, retention, disclosure, and reuse constraints in
  source profiles and derived artifacts where applicable.
- Preserve historical Census category definitions and vintage-specific meaning
  rather than smoothing conceptual changes into one apparently timeless field.

Detailed implementation belongs in the
[ecosystem enrichment plan](2026-07-15-ecosystem-enrichment.md).

## 0.8.x: Portable Research Objects

- Map the versioned interchange/run bundle to RO-Crate so data, code, people,
  licences, source versions, provenance, checksums, and validation evidence can
  be exchanged as a coherent research object.
- Define a small SynthPopCan RO-Crate profile and publish synthetic golden
  examples before claiming interoperability.
- Validate round trips and ensure the crate supplements rather than weakens the
  native manifest, schema, privacy classification, and access controls.
- Keep restricted inputs and sensitive derivatives out of public crates while
  retaining safe metadata about their role and access conditions.

Detailed implementation belongs in the
[simulation interoperability plan](2026-07-15-simulation-interoperability.md).

## Maturity Follow-ons

- Submit to JOSS when the preparation criteria above are met and the software
  has a defensible scholarly-use story; treat peer review and discoverability
  as complements to, not substitutes for, domain validation or papers
  supporting individual scientific results.
- Establish sustainable maintainer succession, documented release authority,
  and an archival/end-of-life path before institutional or community reliance
  grows.
- Revisit relevant research-software and digital-humanities communities and
  standards as actual users and research outputs reveal concrete needs.

## Acceptance Evidence

- `CITATION.cff` is current, valid, and automatically checked against release
  metadata.
- Versioned releases have verified Zenodo records and DOIs, and important
  source trees have recorded Software Heritage identifiers.
- Any Hugging Face pilot preserves exact archived bytes, checksums, DOI links,
  licence and provenance metadata, pinned revisions, and optional installation
  semantics.
- A dated FAIR4RS assessment and Software Management Plan are public and linked
  from contributor/release documentation.
- `0.7.x` source governance records language, authority, licence/access,
  translation, ethical, and community-control considerations where relevant.
- `0.8.x` publishes validated, public-safe RO-Crate examples tied to the native
  interchange contract.
- Any future JOSS submission reflects an independently usable, documented,
  tested, archived, and adopted research-software contribution.
- A focused bilingual project introduction and reproducible demonstration have
  been shared with relevant communities, and substantive feedback has been
  captured as issues, documentation changes, or roadmap decisions.

## References

- [FAIR Principles for Research Software (FAIR4RS)](https://www.rd-alliance.org/groups/fair-research-software-fair4rs-wg/outputs/?output=94498)
- [Citation File Format](https://citation-file-format.github.io/)
- [FORCE11 Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/)
- [Zenodo GitHub integration](https://help.zenodo.org/docs/github/)
- [Hugging Face model cards](https://huggingface.co/docs/hub/model-cards)
- [Hugging Face repositories](https://huggingface.co/docs/hub/en/repositories)
- [Hugging Face collections](https://huggingface.co/docs/hub/en/collections)
- [Software Heritage](https://www.softwareheritage.org/)
- [RO-Crate specification](https://www.researchobject.org/ro-crate/specification.html)
- [Software Sustainability Institute: Software Management Plans](https://www.software.ac.uk/guide/writing-and-using-software-management-plan)
- [Digital Research Alliance of Canada research-software services](https://alliancecan.ca/en/services/research-software)
- [Research Software Canada (RSCAN), listed by the International Council of RSE Associations](https://researchsoftware.org/assoc.html)
- [CARE Principles for Indigenous Data Governance](https://www.gida-global.org/careprinciples)
- [First Nations principles of OCAP](https://fnigc.ca/ocap-training/)
- [Journal of Open Source Software](https://joss.theoj.org/about)
