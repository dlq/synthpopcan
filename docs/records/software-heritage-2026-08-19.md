# Software Heritage Preservation Record — 2026-08-19

**Origin:** <https://github.com/dlq/synthpopcan>\
**Save Code Now request:** `2440101`\
**Archive visit:** `3`\
**Request time:** `2026-08-19T19:33:20.505914+00:00`\
**Visit time:** `2026-08-19T19:33:27.230000+00:00`\
**Result:** accepted, succeeded, full visit

Software Heritage captured the public Git origin after the annotated `v1.1.0`
release. The completed visit returned this snapshot identifier:

`swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc`

[Browse the preserved snapshot](https://archive.softwareheritage.org/swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc;origin=https://github.com/dlq/synthpopcan),
inspect the [save-request API
record](https://archive.softwareheritage.org/api/1/origin/save/2440101/), or
inspect [visit 3](https://archive.softwareheritage.org/api/1/origin/https://github.com/dlq/synthpopcan/visit/3/).

## Verified References

The completed snapshot and release responses identify the exact source objects
below. Qualified identifiers include the captured origin and visit so a reader
can recover their repository context.

| Reference | Core SWHID | Qualified SWHID and verification |
| --- | --- | --- |
| `main` at capture | `swh:1:rev:662c044466d1aa98c6a4bdb19f9438077acdda24` | [`swh:1:rev:662c044466d1aa98c6a4bdb19f9438077acdda24;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc`](https://archive.softwareheritage.org/swh:1:rev:662c044466d1aa98c6a4bdb19f9438077acdda24;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc) |
| annotated `v1.1.0` tag | `swh:1:rel:27e0a7690094a400a2851cfd1956a22e92c0a1e1` | [`swh:1:rel:27e0a7690094a400a2851cfd1956a22e92c0a1e1;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc`](https://archive.softwareheritage.org/swh:1:rel:27e0a7690094a400a2851cfd1956a22e92c0a1e1;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:a08674a118babe38135d20805b1bf4add98692fc) |

The archived `v1.1.0` release object targets revision
`swh:1:rev:662c044466d1aa98c6a4bdb19f9438077acdda24`, the exact Git revision tagged
and released as SynthPopCan 1.1.0. These values come from completed archive
responses; they were not inferred before the visit.

## Earlier Captures

The [2026-08-16 preservation record](software-heritage-2026-08-16.md) remains
the durable evidence for the `v1.0.0` snapshot and release object. The
[2026-08-15 record](software-heritage-2026-08-15.md) preserves the earlier
`v0.9.0` and `v0.7.0` release objects. This capture supplements those records;
it does not replace them.

## Boundary and Recapture Policy

This snapshot preserves source objects and repository references visible during
visit 3. It does not replace:

- the annotated Git tag and GitHub Release as release coordination records;
- the Zenodo 1.1.0 version DOI, `10.5281/zenodo.22017599`, as the canonical
  release citation;
- the PyPI wheel and source distribution installed by a researcher; or
- separate model-package DOIs and checksums.

Request another capture after a later preservation-significant source release,
a repository move, or rewritten public history. Record only identifiers returned
by a completed, full visit.
