# ADR-0014: Separate Prepared-Model And Source Licensing

- **Status:** Accepted
- **Maintainer policy decision:** Accepted by Darcy Quesnel on 2026-08-15
- **Production gate:** Open after verified archive correction on 2026-08-16
- **External review:** Optional; not a `1.0.0` or publication gate
- **Archive correction implementation:** Completed
- **Archive correction execution:** Completed
- **Date:** 2026-08-15
- **Decision owner:** Darcy Quesnel

## Context

SynthPopCan's Python source is distributed under the MIT License. Prepared
model packages are different research objects: they contain learned model
representations derived from Statistics Canada Census Public Use Microdata
Files (PUMFs), plus selection, organization, schema, and documentation created
for SynthPopCan. Statistics Canada's Open Licence permits publication and
distribution of Value-added Products, allows sublicensing on terms consistent
with that licence, and says intellectual-property rights in Value-added
Products vest in their maker or another person determined by law. Its
attribution, accuracy, non-identification, non-misrepresentation, and
no-endorsement conditions continue to apply to Statistics Canada Information.

The existing Zenodo model records set their controlled `license` field to CC BY
4.0 and separately name the continuing Statistics Canada conditions. A
read-only API audit on 2026-08-15 found 32 current public model records: all 32
used `cc-by-4.0`, carried the Statistics Canada source-licence paragraph and
no-endorsement attribution, and none explicitly explained which rights CC BY
was intended to cover. The legacy deposition API's single `license` value
applies to every deposited file. Current Zenodo records can instead carry
multiple or custom rights statements. Where the legacy API cannot express
per-right scopes, its verified `other-open` compatibility value can be paired
with one complete composite layered-rights statement in the record description
and the machine-readable contract in the deposited package.

Repository and released-asset inspection also found that the archive landing
pages and installed registry carry the prescribed attribution, while the
historical model JSON bytes themselves do not contain a complete scoped rights
block. Registry-time enrichment is not sufficient for a person who downloads
the immutable file directly from Zenodo or a GitHub Release.

The current representation is therefore an incomplete two-layer presentation.
Applying the software's MIT licence to a prepared model would also be
misleading. This ADR records a project licensing policy, not legal advice or a
claim that the project can license rights it does not own or control.

## Decision

Darcy Quesnel adopts the following open-by-default project policy as of
2026-08-15:

- MIT will continue to apply only to the software source and packaged software;
- to the extent the package author owns or controls copyright or similar rights
  in the original selection, organization, schema, documentation, and model
  representation, those rights will be offered under CC BY 4.0; this does not
  claim author-controlled rights in source classifications, facts, or
  unprotectable numeric results;
- the package and archive record will also preserve the Statistics Canada Open
  Licence URL and prescribed source attribution, and will state that CC BY 4.0
  does not license, replace, or supersede Statistics Canada Information or
  third-party rights;
- the two statements will be described as cumulative and scoped to their
  respective rights, never as alternative licences for the whole package;
- generated-artifact provenance and redistributed packages will retain the
  source notice and applicable source conditions; and
- release metadata will distinguish licence presentation from disclosure,
  statistical-fitness, endorsement, and legal-anonymization claims.

This is the most permissive default the project can responsibly offer: reuse is
authorized wherever the package author controls the relevant rights, while
source conditions, third-party rights, provenance, and privacy boundaries stay
attached to the material they govern. Open licensing does not authorize access
to confidential source data, relax the Statistics Canada anti-identification
condition, permit re-identification, or turn project disclosure-risk checks
into privacy certification.

The operative scope statement will be:

> To the extent the package author owns or controls copyright or similar rights
> in the original selection, organization, schema, documentation, and model
> representation, those rights are licensed under CC BY 4.0. This grant does
> not license, replace, or supersede Statistics Canada Information or rights
> governed by the Statistics Canada Open Licence. Nothing in this statement
> claims author-controlled rights in source classifications, facts, or
> unprotectable numeric results. The two rights statements are cumulative and
> scoped to their respective material; they are not alternative licences for
> the package as a whole.

The maintainer is the project decision authority for this policy. External
review by Statistics Canada or qualified counsel remains welcome but is
optional and is not a `1.0.0` or publication gate. The project will not invent
or imply an external approval, endorsement, or legal opinion.

If later authoritative guidance or a material change to the applicable source
terms conflicts with this interpretation, the maintainer will review it
promptly, revise the policy prospectively, and publish corrected metadata or a
new non-overwriting artifact version where needed. Historical bytes, DOI
bindings, versions, and checksums remain preserved. A future review does not
retroactively convert this project policy into external legal advice.

## Required Correction Path

Before a later production model publication:

1. every model package must embed a versioned rights block containing the exact
   prescribed `Adapted from Statistics Canada ...` no-endorsement notice, the
   Statistics Canada Open Licence URL, the CC BY 4.0 URL and owned-or-controlled-
   rights scope and exclusions, and the cumulative-not-alternative statement;
1. generated-artifact manifests and model inspection output must preserve the
   same source notice and rights references;
1. Zenodo records must use scoped multiple or custom rights statements where
   supported. A legacy-API fallback must use the verified `other-open`
   compatibility value plus the complete composite scope in the record
   description and package bytes; a bare `license: cc-by-4.0` value is not an
   adequate final representation for a mixed-rights file;
1. the 32 existing model records must receive in-place metadata corrections
   that preserve their identifiers and disclose the previous ambiguity; and
1. where correction requires changing archived package bytes, publish a new
   non-overwriting version under the existing concept DOI with new checksums
   and a new version DOI. Retain the old version, mark it as superseded for
   licensing clarity, and update the SynthPopCan registry only after the new
   artifact is verified.

Do not delete, replace, or silently relabel immutable historical files.
The identifier-preserving metadata edits above clarify rather than reverse
[ADR-0010](0010-pre-1-0-compatibility-evolution.md): published bytes, versions,
checksums, and DOI bindings remain immutable, while audited descriptive
metadata may be corrected without changing the preserved object.

The exact **Archive correction implementation** marker above became `Completed`
on 2026-08-15 after independent adversarial review closed all previously
identified executor blockers. The reviewed implementation edits each existing
record's metadata in place, creates a non-overwriting file version under that
record's existing concept DOI, records supersession, verifies both the new and
preserved historical assets, and emits exact registry candidates without
confusing an old draft or version with the replacement. Its 137 focused tests,
Ruff, Pyright, and diff checks passed. Review-only manifests remain
non-executable; execution manifests are transactionally bound to the exact
operation set, version, historical and candidate asset hashes, desired-metadata
hash, and execution-index digest.

The separate **Archive correction execution** marker became `Completed` on
2026-08-16 after all 32 production metadata corrections and all 32 corrected
versions were remotely verified, exactly 32 registry updates were integrated,
and an independent read-only audit repeated the old/new identity, latest-link,
file-set, size, SHA-256, embedded-licensing, and mutable-draft checks. The
[tracked correction record](../docs/records/prepared-model-archive-correction-2026-08-16.md)
and its packaged machine-readable evidence omit credentials and private
executor state while preserving all 64 operation identities and outcomes.

Correction operations still require Accepted status and completed
implementation. Fresh production model records additionally require the
completed execution marker, the tracked 64-operation evidence, and the exact 32
installed registry updates. This keeps the gate reproducible in a clean clone
without trusting ignored local checkpoints.

## Alternatives Considered

- **Apply MIT to software and models alike:** rejected because it obscures the
  source-data conditions and treats unlike research objects as equivalent.
- **Use CC0 for the prepared-model layer:** rejected because the project cannot
  waive Statistics Canada or third-party rights, and removing attribution from
  the authored layer would work against the provenance this research object
  needs. CC BY 4.0 permits broad reuse while preserving attribution and keeping
  the scope boundary explicit.
- **Name only the Statistics Canada Open Licence:** rejected as the default
  because it unnecessarily withholds an express open grant over original rights
  the package author owns or controls. It remains available if authoritative
  future guidance requires a narrower presentation.
- **Publish both licences without describing their layers:** rejected because a
  bare dual-licence label could imply that users may choose either licence for
  the entire object.
- **Continue publishing under the current wording before correction:** rejected
  because archive publication is durable and difficult to correct completely.

## Consequences

- Production model publication may resume only through the documented human
  approval boundary; the 32-record correction prerequisite is now satisfied.
- The metadata builder may continue producing review-only manifests with the
  verified `other-open` compatibility value, the full layered statement, and
  the Statistics Canada notice. Review-only manifests never authorize an
  upload; any future archive transaction still requires separate explicit
  authority and new checksum-bound evidence.
- Package construction, generated provenance, registry presentation, archive
  metadata, release guidance, and all 32 affected model concepts now reflect
  the completed correction.
- This decision does not authorize publication of access-controlled source
  material or artifacts derived from sources other than the public PUMFs.
- External review is optional ongoing risk management. Material authoritative
  guidance is a trigger for prompt prospective review and correction, not a
  reason to misstate current external approval or defer the `1.0.0` decision.

## Evidence And Related Records

- [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence)
- [Statistics Canada Open Licence FAQ](https://www.statcan.gc.ca/en/terms-conditions/open-licence-faq)
- [Zenodo licences and rights](https://help.zenodo.org/docs/deposit/describe-records/licenses/)
- [Zenodo published-record metadata edits](https://help.zenodo.org/docs/deposit/manage-records/)
- [Creative Commons licensing considerations](https://creativecommons.org/share-your-work/licensing-considerations/version4/)
- [Data and model licensing guidance](../docs/data.md#source-licensing-and-attribution)
- [Dated licensing review record](../docs/records/prepared-model-licensing-review-2026-08-15.md)
- [Completed archive-correction record](../docs/records/prepared-model-archive-correction-2026-08-16.md)
- [Model release checklist](../RELEASING.md#model-package-release)
- [Research-software stewardship plan](../plans/2026-07-19-research-software-stewardship.md)
- [Zenodo metadata builder](../scripts/build_zenodo_depositions.py)
- [Zenodo model-record API query, page 1](https://zenodo.org/api/records?q=metadata.related_identifiers.identifier:%2210.5281/zenodo.21461463%22&size=25&page=1)
- [Zenodo model-record API query, page 2](https://zenodo.org/api/records?q=metadata.related_identifiers.identifier:%2210.5281/zenodo.21461463%22&size=25&page=2)
