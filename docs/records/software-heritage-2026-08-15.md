# Software Heritage Preservation Record — 2026-08-15

**Origin:** <https://github.com/dlq/synthpopcan>\
**Save Code Now request:** `2427275`\
**Request date:** 2026-08-15 17:20:30 UTC\
**Visit date:** 2026-08-15 17:20:35 UTC\
**Result:** accepted, succeeded, full visit

Software Heritage captured the public Git origin through its normal Save Code
Now service. The archive returned this snapshot identifier:

`swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`

[Browse the preserved snapshot](https://archive.softwareheritage.org/swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9;origin=https://github.com/dlq/synthpopcan)
or inspect the [save-request API
record](https://archive.softwareheritage.org/api/1/origin/save/2427275/).

## Verified References

The snapshot API reported the following objects. Qualified identifiers include
the captured origin and visit so a reader can recover the repository context.

| Reference | Core SWHID | Qualified SWHID and verification |
| --- | --- | --- |
| `main` at capture | `swh:1:rev:80c32b18fdb3d49dc739ee2d045aaa33645503c7` | [`swh:1:rev:80c32b18fdb3d49dc739ee2d045aaa33645503c7;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`](https://archive.softwareheritage.org/swh:1:rev:80c32b18fdb3d49dc739ee2d045aaa33645503c7;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9) |
| annotated `v0.9.0` tag | `swh:1:rel:9b1b92b09a42a293907a733a1638c269b0819516` | [`swh:1:rel:9b1b92b09a42a293907a733a1638c269b0819516;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`](https://archive.softwareheritage.org/swh:1:rel:9b1b92b09a42a293907a733a1638c269b0819516;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9) |
| annotated `v0.7.0` tag | `swh:1:rel:6637b3aa961bbd21888da5aa847a128ac9975d3b` | [`swh:1:rel:6637b3aa961bbd21888da5aa847a128ac9975d3b;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9`](https://archive.softwareheritage.org/swh:1:rel:6637b3aa961bbd21888da5aa847a128ac9975d3b;origin=https://github.com/dlq/synthpopcan;visit=swh:1:snp:98f7bee54900f50bc99ac5c9f000a728e80016b9) |

The archived release objects name the expected annotated tags and target Git
revisions:

- `v0.9.0` targets revision
  `swh:1:rev:b11fc4ede4a060f1210fe46a649e11d070381bb2`;
- `v0.7.0` targets revision
  `swh:1:rev:b35a006f65a2c3cd681d40c063169a0e1e2af96a`.

These values were checked against the snapshot and release API responses, not
inferred from a GitHub page or invented before capture.

## Boundary and Recapture Policy

This snapshot preserves source objects and repository references visible at the
visit. It does not replace:

- a Git tag or GitHub Release as the project's release coordination record;
- the Zenodo version DOI as the canonical citation for released software;
- the PyPI wheel and source distribution actually installed by a researcher;
- separate model-package DOIs and checksums; or
- a later capture of the final `1.0.0` source.

Request another capture after `1.0.0`, a repository move, rewritten public
history, or another preservation-significant source release. Record only the
SWHIDs returned by that completed capture.
