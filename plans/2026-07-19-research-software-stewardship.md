# Research-Software Stewardship Plan

Status: planned and ongoing\
Created: 2026-07-19\
Last updated: 2026-07-20\
Target: immediate maintenance, `0.7.x`, `0.8.x`, and maturity follow-ons\
Next action: add full CFF schema validation, review the licence representation
and safe automation of model archives, then register important releases with
Software Heritage\
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

- Consider a Journal of Open Source Software submission once the API and
  methods are stable, research use and contribution are demonstrable, tests and
  documentation support independent use, and the paper can make a clear
  scholarly contribution claim.
- Treat a JOSS paper as peer review and discoverability for the software, not
  as a substitute for domain validation or papers supporting individual
  scientific results.
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
- A dated FAIR4RS assessment and Software Management Plan are public and linked
  from contributor/release documentation.
- `0.7.x` source governance records language, authority, licence/access,
  translation, ethical, and community-control considerations where relevant.
- `0.8.x` publishes validated, public-safe RO-Crate examples tied to the native
  interchange contract.
- Any future JOSS submission reflects an independently usable, documented,
  tested, archived, and adopted research-software contribution.

## References

- [FAIR Principles for Research Software (FAIR4RS)](https://www.rd-alliance.org/groups/fair-research-software-fair4rs-wg/outputs/?output=94498)
- [Citation File Format](https://citation-file-format.github.io/)
- [FORCE11 Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/)
- [Zenodo GitHub integration](https://help.zenodo.org/docs/github/)
- [Software Heritage](https://www.softwareheritage.org/)
- [RO-Crate specification](https://www.researchobject.org/ro-crate/specification.html)
- [Software Sustainability Institute: Software Management Plans](https://www.software.ac.uk/guide/writing-and-using-software-management-plan)
- [Digital Research Alliance of Canada research-software services](https://alliancecan.ca/en/services/research-software)
- [Research Software Canada (RSCAN), listed by the International Council of RSE Associations](https://researchsoftware.org/assoc.html)
- [CARE Principles for Indigenous Data Governance](https://www.gida-global.org/careprinciples)
- [First Nations principles of OCAP](https://fnigc.ca/ocap-training/)
- [Journal of Open Source Software](https://joss.theoj.org/about)
