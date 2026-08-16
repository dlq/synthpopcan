# Stewardship, Support, and Preservation

SynthPopCan is maintained research software, not a hosted service. This page
states which environments the release process tests, what support users can
expect, where releases are preserved, and which decisions still require human
review. These are project policies, not guarantees of fitness for a particular
study.

## Supported Environments

| Environment | Release status | Evidence and boundary |
| --- | --- | --- |
| CPython 3.11–3.14 on the current GitHub Actions Ubuntu runner | Tested | Every change runs lint, type, test, coverage, documentation, and CFF checks across the declared Python matrix; a separate Python 3.12 job tests the installed wheel. |
| Current macOS with CPython 3.11–3.14 | Best-effort supported | The maintainer uses the project on macOS and the installation path is documented, but macOS is not an automated release matrix. Report platform-specific failures. |
| Windows Subsystem for Linux (Ubuntu) | Best-effort supported | The documented Windows path is WSL. It follows the Unix commands, but is not an automated release matrix. |
| Native Windows Python and PowerShell | Not a supported 1.0 environment | Shell scripts and path-sensitive workflows are not release-tested natively. Use WSL or contribute a tested native-Windows path. |
| Local browser workbench in current Chromium/Chrome | Tested on Chromium | Playwright exercises Chromium on Ubuntu. Other current standards-based browsers may work but are best effort. |

“Tested” means the repository release checks exercise that environment. It does
not mean every source dataset, population size, optional external service, or
research workflow has been tested there. Package metadata defines the minimum
Python version; the release matrix records the currently tested versions and
operating-system evidence.

## Maintenance and Help

- The latest released version receives maintenance and security fixes. Upgrade
  before reporting a problem already corrected in a later release.
- Use the [issue tracker](https://github.com/dlq/synthpopcan/issues) for
  reproducible bugs, documentation problems, accessibility concerns, and
  feature proposals. Contributions do not have to be code.
- Use [private vulnerability
  reporting](https://github.com/dlq/synthpopcan/security/advisories/new) for
  security or disclosure concerns; do not attach private data or raw microdata
  to an issue.
- Security reports have a seven-day initial-response target. Ordinary support
  is best effort and has no response-time or continued-service guarantee.
- The project currently has one release authority and no documented funded
  support commitment or named successor. The dated management plan records the
  resulting continuity risk and the end-of-life procedure.

See [CONTRIBUTING.md](https://github.com/dlq/synthpopcan/blob/main/CONTRIBUTING.md)
for development and review practice and
[SECURITY.md](https://github.com/dlq/synthpopcan/blob/main/SECURITY.md) for the
private reporting boundary.

## Publication and Licensing Boundaries

- Software source and packaged software use the MIT License.
- Census PUMF-derived prepared models carry the prescribed Statistics Canada
  source attribution and continuing Open Licence conditions.
- Darcy Quesnel accepted on 2026-08-15 a scoped CC BY 4.0 grant
  only for copyright or similar rights the package author owns or controls in
  original selection, organization, schema, documentation, and model
  representation. It claims no author-controlled rights in source
  classifications, facts, or unprotectable numeric results. It is cumulative
  with, and does not replace, the Statistics Canada Open Licence conditions
  applying to source Information.
- [ADR-0014](https://github.com/dlq/synthpopcan/blob/main/adr/0014-separate-prepared-model-and-source-licensing.md)
  is Accepted as the maintainer-selected permissive default. External review is
  welcome but optional, is not a `1.0.0` gate, and is not claimed to have
  occurred. The [dated
  review](records/prepared-model-licensing-review-2026-08-15.md) records the
  project decision, its limits, and the prospective review trigger.
- Open licensing authorizes reuse only within the stated rights. It does not
  relax confidential-source access controls, the Statistics Canada
  anti-identification condition, project disclosure-risk caveats, required
  attribution, provenance, or the no-endorsement statement.
- The fail-closed archive-correction implementation passed independent
  adversarial review on 2026-08-15. On 2026-08-16 all 32 metadata corrections,
  32 non-overwriting versions, remote byte checks, latest-link checks, and 32
  registry updates completed. The [archive-correction
  record](records/prepared-model-archive-correction-2026-08-16.md) preserves
  the sanitized evidence and interpretation boundary.
- Current registered model bytes embed the scoped rights contract and
  prescribed source notice. Zenodo uses the verified `other-open` compatibility
  value plus the complete composite statement, while every historical version
  remains available under its original identifier and checksum.
- Zenodo publication is human-approved and irreversible. Tooling may generate
  review-only metadata and dry-run plans; they do not authorize another archive
  write. Material authoritative guidance that conflicts with the accepted
  policy triggers prompt prospective review and, where needed, a new
  non-overwriting correction.

Passing a release, model, or disclosure-readiness check is not legal advice,
official approval, privacy certification, or evidence that an output is
representative or fit for a particular research question.

## Preservation and Citation

Git tags and GitHub Releases identify project releases; PyPI distributes the
Python package; Read the Docs publishes maintained guidance; and Zenodo is the
canonical citable archive for released software and prepared models. Software
Heritage independently preserves the source history.

The completed 2026-08-16 Software Heritage capture contains the exact annotated
`v1.0.0` release and source revision:

- snapshot: `swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845`;
- archived `v1.0.0` tag: `swh:1:rel:7152cfd62259d319a86fdcee497d76fa87667f7b`;
- tagged source revision:
  `swh:1:rev:a9203d8a477608d78296faf69adcf30fba2b64d7`.

The 2026-08-15 capture remains durable historical evidence for the earlier
source history:

- snapshot: `swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`;
- archived `v0.9.0` tag: `swh:1:rel:9b1b92b09a42a293907a733a1638c269b0819516`;
- archived `v0.7.0` tag: `swh:1:rel:6637b3aa961bbd21888da5aa847a128ac9975d3b`.

Use the [1.0.0 version DOI](https://doi.org/10.5281/zenodo.21961301) when
reproducing work from that release. A Software Heritage identifier pins source
objects but does not replace the PyPI artifact, Zenodo release DOI, model DOI,
or published checksums.

## Dated Records

These records describe the `0.9.0` baseline and the evidence used to establish
the `1.0.0` line. They are self-assessments and management records, not
external certifications:

```{toctree}
:maxdepth: 1

records/fair4rs-2026-08-15
records/software-management-plan-2026-08-15
records/software-heritage-2026-08-15
records/software-heritage-2026-08-16
records/prepared-model-licensing-review-2026-08-15
records/prepared-model-archive-correction-2026-08-16
```

Review the records at every major release and after a material change to
maintainers, support, infrastructure, licensing, data authority, or
distribution. Patch releases do not require a ceremonial rewrite.
