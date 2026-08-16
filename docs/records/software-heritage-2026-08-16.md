# Software Heritage Preservation Record — 2026-08-16

**Origin:** <https://github.com/dlq/synthpopcan>\
**Save Code Now request:** `2428948`\
**Archive visit:** `2`\
**Request time:** `2026-08-16T04:13:44.106960+00:00`\
**Visit time:** `2026-08-16T04:13:53.897000+00:00`\
**Result:** accepted, succeeded, full visit

Software Heritage captured the public Git origin after the annotated `v1.0.0`
release. The completed visit returned this snapshot identifier:

`swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845`

[Browse the preserved snapshot](https://archive.softwareheritage.org/swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845;origin=https://github.com/dlq/synthpopcan),
inspect the [save-request API
record](https://archive.softwareheritage.org/api/1/origin/save/2428948/), or
inspect [visit 2](https://archive.softwareheritage.org/api/1/origin/https://github.com/dlq/synthpopcan/visit/2/).

## Verified References

The completed snapshot and release responses identify the exact source objects
below. Qualified identifiers include the captured origin and visit so a reader
can recover their repository context.

| Reference | Core SWHID | Qualified SWHID and verification |
| --- | --- | --- |
| `main` at capture | `swh:1:rev:a9203d8a477608d78296faf69adcf30fba2b64d7` | [`swh:1:rev:a9203d8a477608d78296faf69adcf30fba2b64d7;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845`](https://archive.softwareheritage.org/swh:1:rev:a9203d8a477608d78296faf69adcf30fba2b64d7;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845) |
| annotated `v1.0.0` tag | `swh:1:rel:7152cfd62259d319a86fdcee497d76fa87667f7b` | [`swh:1:rel:7152cfd62259d319a86fdcee497d76fa87667f7b;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845`](https://archive.softwareheritage.org/swh:1:rel:7152cfd62259d319a86fdcee497d76fa87667f7b;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:1d4d40f874206f2abb70d434402bc9034a127845) |

The archived `v1.0.0` release object targets revision
`swh:1:rev:a9203d8a477608d78296faf69adcf30fba2b64d7`, the exact Git revision tagged
and released as SynthPopCan 1.0.0. These values come from the completed archive
responses; they were not inferred before the visit.

## Earlier Capture

The [2026-08-15 preservation record](software-heritage-2026-08-15.md) remains
the durable evidence for the earlier snapshot and release objects:

- snapshot through `v0.9.0`:
  `swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`;
- annotated `v0.9.0` release:
  `swh:1:rel:9b1b92b09a42a293907a733a1638c269b0819516`; and
- annotated `v0.7.0` release:
  `swh:1:rel:6637b3aa961bbd21888da5aa847a128ac9975d3b`.

The later capture supplements that historical record; it does not replace it.

## Boundary and Recapture Policy

This snapshot preserves source objects and repository references visible during
visit 2. It does not replace:

- the annotated Git tag and GitHub Release as release coordination records;
- the Zenodo 1.0.0 version DOI, `10.5281/zenodo.21961301`, as the canonical
  release citation;
- the PyPI wheel and source distribution installed by a researcher; or
- separate model-package DOIs and checksums.

Request another capture after a later preservation-significant source release,
a repository move, or rewritten public history. Record only identifiers returned
by a completed, full visit.
