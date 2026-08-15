# Prepared-Model Licensing Review — 2026-08-15

**Decision record:** ADR-0014\
**Decision owner:** Darcy Quesnel\
**Maintainer policy:** accepted on 2026-08-15\
**ADR status:** Accepted\
**Production publication:** blocked pending live archive correction;
implementation completed\
**External legal review:** not obtained; optional, not a `1.0.0` gate

This is a dated project decision record, not legal advice or an external legal
opinion. It records the maintainer's open-by-default policy, the evidence
reviewed, the safeguards that remain mandatory, the correction work that
follows from it, and the trigger for any prospective review.

## Evidence Reviewed

The [Statistics Canada Open
Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence) expressly
covers public use microdata files, permits publication and distribution of
Value-added Products, permits sublicensing on terms consistent with the
licence, and addresses intellectual-property rights in Value-added Products.
It also requires the prescribed adapted-from notice and continuing accuracy,
non-identification, non-misrepresentation, and no-endorsement conditions.

[Zenodo's current rights
documentation](https://help.zenodo.org/docs/deposit/describe-records/licenses/)
supports multiple and custom rights statements. Its legacy deposition API's
single `license` field applies one selected licence to every file and cannot
express the intended scope adequately by itself. The safe legacy fallback uses
Zenodo's verified `other-open` compatibility value and repeats one complete
composite layered-rights statement in the record description and deposited
package bytes. Zenodo permits
[published-record metadata
edits](https://help.zenodo.org/docs/deposit/manage-records/) without changing
the DOI.

A 2026-08-15 read-only audit found 32 current public prepared-model records.
All used CC BY 4.0 and carried Statistics Canada attribution in their record
description, but none stated which rights CC BY covered. Inspection of the
repository builder and a representative released package also found that the
immutable JSON bytes do not yet embed a complete scoped rights block. The
installed registry adds provenance at load time, but that does not reach a
direct Zenodo or GitHub Release download.

## Maintainer Position

Darcy Quesnel accepts the following project policy as of 2026-08-15:

> To the extent the package author owns or controls copyright or similar rights
> in the original selection, organization, schema, documentation, and model
> representation, those rights are licensed under CC BY 4.0. This grant does
> not license, replace, or supersede Statistics Canada Information or rights
> governed by the Statistics Canada Open Licence. Nothing in this statement
> claims author-controlled rights in source classifications, facts, or
> unprotectable numeric results. The two rights statements are cumulative and
> scoped to their respective material; they are not alternative licences for
> the package as a whole.

This policy replaces the overly broad shorthand that CC BY covers
"SynthPopCan-authored model material." It accepts ADR-0014 while keeping
production publication closed until the live archive-correction execution gate
is complete.

The policy is permissive about reuse, not about privacy or provenance. It does
not authorize access to confidential source data, relax the Statistics Canada
anti-identification condition, permit re-identification, remove attribution or
no-endorsement requirements, or turn project disclosure-risk checks into legal
privacy certification.

## Correction Disposition

The project has prepared fail-closed package and archive-correction machinery
for the accepted scope. Independent adversarial review completed on 2026-08-15,
closing all three prior executor blockers with 137 focused tests, Ruff, Pyright,
and diff checks passing. The live correction remains a separate, explicitly
authorized operation and will at minimum:

1. embed the prescribed Statistics Canada notice and source-licence URL in the
   actual model-package bytes and generated-artifact provenance; embed the CC BY
   URL, owned-or-controlled limited scope and exclusions, and cumulative-not-
   alternative statement there too;
1. represent the accepted scoped rights with Zenodo multiple or custom rights
   where supported. On the legacy API, use the verified `other-open`
   compatibility value plus the complete composite scope in the record
   description and package bytes, never an all-file `license: cc-by-4.0` value
   alone;
1. correct the metadata of all 32 existing records in place, preserving their
   identifiers and noting the former ambiguity; and
1. where package bytes must change, publish a new non-overwriting version under
   the existing concept DOI with new checksums and a new version DOI. Historical
   versions remain available and are marked superseded for licensing clarity.

No historical archive file will be overwritten, deleted, or silently
relabelled.

Implementation readiness and live execution are separate evidence. The former
is complete after independent review of non-overwriting, ownership, identity,
transaction, and resume boundaries. The latter remains pending and requires all
32 metadata corrections, all 32 new package
versions, exactly 32 registry updates, and a tracked sanitized record of
operation IDs, old/new DOIs, checksums, and remote verification outcomes.

## Optional Future Review Question

External review remains welcome but is not a `1.0.0` or publication gate. If a
future Statistics Canada or qualified-counsel review is useful, the following
question preserves the narrow scope. A recipient, date, or answer must be
recorded only after it exists; none is implied here.

> SynthPopCan publishes trained JSON model packages derived from Statistics
> Canada Census public use microdata files. May the package present, under CC
> BY 4.0, only the copyright or similar rights that the package author owns or
> controls in the original selection, organization, schema, documentation, and
> model representation, while clearly stating that any Statistics Canada
> Information remains governed by the Statistics Canada Open Licence and its
> continuing notices and conditions, and without claiming author-controlled
> rights in source classifications, facts, or unprotectable numeric results?
> The two statements would be cumulative and scoped, not alternative licences
> for the package as a whole.
>
> If so, does placing the exact prescribed “Adapted from Statistics Canada,
> [product name], [reference date]. This does not constitute an endorsement by
> Statistics Canada of this product.” notice both in the accompanying archive
> record and in a clearly identified rights block embedded in the distributed
> JSON satisfy the requirement to include the notice “on such Value-added
> Product”? Please identify any additional wording or placement required.

No external answer, reviewer, approval, or endorsement is recorded as of
2026-08-15.

## Decision And Future-Review Evidence

ADR-0014 is Accepted by maintainer policy decision. The machine-readable
`policy_decision` records:

- `status: accepted`;
- `basis: maintainer-selected-permissive-default`;
- Darcy Quesnel as decision authority and `2026-08-15` as the decision date;
- the accepted ADR-0014 record;
- `external_legal_review: not-obtained`; and
- an explicit statement that this is the project's maintained default, subject
  to cumulative licence layers, provenance requirements, and privacy safeguards,
  and is not legal advice or a claim of external legal review.

Material authoritative guidance that conflicts with this policy triggers a
prompt prospective review. Record the real source, authority, date, and durable
summary only then; revise and re-review the contract and correction tooling as
needed; preserve historical bytes and identifiers; and publish corrected
metadata or a new non-overwriting version rather than silently relabelling an
artifact.

See [ADR-0014](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md)
and the [model release
checklist](https://github.com/dlq/synthpopcan/blob/main/RELEASING.md#model-package-release)
for the governing project records.
