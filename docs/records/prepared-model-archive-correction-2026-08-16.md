# Prepared-Model Archive Correction — 2026-08-16

**Status:** Completed\
**Target:** Production Zenodo\
**Executor commit:** `b72d85ee36a057cf5a235b1c743a249ea933df20`\
**Policy authority:** Accepted ADR-0014

## Outcome

All 32 prepared-model concepts completed the non-destructive correction
transaction:

- 32 existing record metadata corrections preserve each historical record ID,
  version DOI, concept DOI, publication date, filename, size, and SHA-256;
- 32 corrected packages were published as new, non-overwriting
  `v1.0.0-rights.1` versions under the same concept DOIs;
- every corrected package embeds the exact
  `synthpopcan-prepared-model-licensing-v1` contract while preserving the
  historical JSON except for that top-level insertion;
- all 32 historical and all 32 corrected compressed and uncompressed sizes
  and SHA-256 hashes were independently reverified from the public archive;
- every historical record's `latest` link resolves to its expected corrected
  version; and
- the authenticated concept inventory found no mutable drafts. Zenodo's
  `status=draft` query returned one already-published predecessor per concept;
  each exact terminal artifact was identified and excluded.

The historical assets total 49,557,434 compressed bytes and 3,765,430,651
uncompressed bytes. The corrected assets total 43,967,253 compressed bytes
and 3,765,538,331 uncompressed bytes. The different gzip sizes are expected;
the corrected uncompressed bytes differ only by the canonical licensing
object.

## Durable Evidence

The packaged
[machine-readable evidence](../../src/synthpopcan/archive_correction_evidence_v1.json)
contains the exact 64 operation IDs, execution-index and candidate-envelope
digests, old and new identities, public download URLs, compressed and
uncompressed sizes and hashes, and the 32 registry updates. Its SHA-256 at
review time is
`f4e8705daa006a1ef1523b3db8bf2c818fa76032d48a4488b0c0d9b2f954a47e`.
It also pins the canonical licensing-object SHA-256 values for 2016
(`21dd4bfa0014dec4295e2b9155ee54382082d984a9cab775f0863d2c52219392`)
and 2021
(`efe68065a2f6ca9bb36ee3d5236743cff7e6f6be6edc75c1691a934324e814d8`).
The installed registry derives its 32 release entries from that validated
resource, so a clean checkout or wheel does not depend on ignored local
checkpoints.

The evidence deliberately excludes credentials, request headers, private
bucket and deposition-management URLs, raw API responses, local `file://`
candidate paths, and 32 quarantined legacy model-only checkpoint rows. Those
rows were local executor residue, had no operation ID, and were never evidence
of live drafts.

The production executor itself recorded all 64 current operations as
`state=verified` and `verified=true`, with exact agreement among its
execution index, results, candidate assets, and emitted registry updates.
The independent final audit then repeated remote identity, metadata, latest-
link, file-set, size, and SHA-256 verification without making a Zenodo write.

One immediate post-publication Calgary 2021 verification received a transient
short response. The checkpoint remained safely at `published`; no new-version
operation had started. The same record subsequently returned its exact
registered size and hash through curl and repeated executor streams, after
which normal read-only resume completed verification. No archive content
changed.

## Model Versions

| Model | Preserved historical version | Corrected version | Corrected compressed SHA-256 |
|---|---|---|---|
| `alberta-2016-all-fields` | [10.5281/zenodo.21461537](https://doi.org/10.5281/zenodo.21461537) | [10.5281/zenodo.21960302](https://doi.org/10.5281/zenodo.21960302) | `608ac152a9d00bcbe9571591bdb4df329b8d3f4361bd8d447eafac9ab1af5906` |
| `alberta-2021-all-fields` | [10.5281/zenodo.21461541](https://doi.org/10.5281/zenodo.21461541) | [10.5281/zenodo.21960311](https://doi.org/10.5281/zenodo.21960311) | `f8006418a324c885a2eea0f4f28fbda70d4ffb571bc720bda23f4fb4d73a1234` |
| `bc-2016-all-fields` | [10.5281/zenodo.21461543](https://doi.org/10.5281/zenodo.21461543) | [10.5281/zenodo.21960313](https://doi.org/10.5281/zenodo.21960313) | `b26104615c118f0e7e3253fbfb099eddd122f38ca56d23225c2f03af7b202711` |
| `bc-2021-all-fields` | [10.5281/zenodo.21461545](https://doi.org/10.5281/zenodo.21461545) | [10.5281/zenodo.21960316](https://doi.org/10.5281/zenodo.21960316) | `2e623e9ff11bad7444c1f4cb9193d0aa2c590dd881f7ffc5414d6680072885a6` |
| `calgary-cma-2016-all-fields` | [10.5281/zenodo.21461554](https://doi.org/10.5281/zenodo.21461554) | [10.5281/zenodo.21960257](https://doi.org/10.5281/zenodo.21960257) | `91c8bc8024b4455273bb00c0e0c40820e4913c10c3574127f76c453a0be68e8a` |
| `calgary-cma-2021-all-fields` | [10.5281/zenodo.21461556](https://doi.org/10.5281/zenodo.21461556) | [10.5281/zenodo.21960288](https://doi.org/10.5281/zenodo.21960288) | `c9e28ec428bb43a0d583171424e34e37b51a78eb94340b447e2195d447d6e413` |
| `canada-2016-all-fields` | [10.5281/zenodo.21461559](https://doi.org/10.5281/zenodo.21461559) | [10.5281/zenodo.21960354](https://doi.org/10.5281/zenodo.21960354) | `6cb54a3c4ff2801052a1e3d588a96005eac8539394a6ecfaf0eed07c0728db93` |
| `canada-2021-all-fields` | [10.5281/zenodo.21461578](https://doi.org/10.5281/zenodo.21461578) | [10.5281/zenodo.21960375](https://doi.org/10.5281/zenodo.21960375) | `d035c5519955c6c5a192f94d78be7f4b5a4658a62eebbfaa2b716c0eff06a881` |
| `edmonton-cma-2016-all-fields` | [10.5281/zenodo.21461580](https://doi.org/10.5281/zenodo.21461580) | [10.5281/zenodo.21960253](https://doi.org/10.5281/zenodo.21960253) | `b58d7b949f15d9fc4a642a714f3625f8867b7476451343310fe1be375a47b891` |
| `edmonton-cma-2021-all-fields` | [10.5281/zenodo.21461582](https://doi.org/10.5281/zenodo.21461582) | [10.5281/zenodo.21960264](https://doi.org/10.5281/zenodo.21960264) | `4f1658cb56b93c661a520de991a84755304fb712a3be064e731dc3d3e234777b` |
| `manitoba-2016-all-fields` | [10.5281/zenodo.21461584](https://doi.org/10.5281/zenodo.21461584) | [10.5281/zenodo.21960252](https://doi.org/10.5281/zenodo.21960252) | `9c2ad14e8a04ca942a81772a59243285055b11508ac7bc1662fa1cee81b4293e` |
| `manitoba-2021-all-fields` | [10.5281/zenodo.21461587](https://doi.org/10.5281/zenodo.21461587) | [10.5281/zenodo.21960240](https://doi.org/10.5281/zenodo.21960240) | `bfe72ac98a9c9aef367ef8deb46ef6ca2ac53d619e5a2e5dc4d4e872a255f3f4` |
| `montreal-cma-2016-all-fields` | [10.5281/zenodo.21461590](https://doi.org/10.5281/zenodo.21461590) | [10.5281/zenodo.21960306](https://doi.org/10.5281/zenodo.21960306) | `729b09dc5bd05ba47bb67fb4389aaef3ef5391e67e0b878586915624fa18d19d` |
| `montreal-cma-2021-all-fields` | [10.5281/zenodo.21461593](https://doi.org/10.5281/zenodo.21461593) | [10.5281/zenodo.21960295](https://doi.org/10.5281/zenodo.21960295) | `5b32165f972d08d4b6384cb4c883e7817e4ab2667b7f6eadcfff9dbfbc545150` |
| `new-brunswick-2016-all-fields` | [10.5281/zenodo.21461596](https://doi.org/10.5281/zenodo.21461596) | [10.5281/zenodo.21960229](https://doi.org/10.5281/zenodo.21960229) | `180c370dc77b346fd0a17c4857830a11b99ef017130baf93ff1f7332191eb52d` |
| `new-brunswick-2021-all-fields` | [10.5281/zenodo.21461598](https://doi.org/10.5281/zenodo.21461598) | [10.5281/zenodo.21960228](https://doi.org/10.5281/zenodo.21960228) | `9a24e08efa625a659ff21bc3202be1b38020b52120af4cfc516dc05f95cf817f` |
| `newfoundland-2016-all-fields` | [10.5281/zenodo.21461600](https://doi.org/10.5281/zenodo.21461600) | [10.5281/zenodo.21960221](https://doi.org/10.5281/zenodo.21960221) | `89108da1bee0f3f58cdcac3095017998af5d619979e5b8f67689e4821080632d` |
| `newfoundland-2021-all-fields` | [10.5281/zenodo.21461602](https://doi.org/10.5281/zenodo.21461602) | [10.5281/zenodo.21960213](https://doi.org/10.5281/zenodo.21960213) | `17a7186705751286510182b800f24cd055ee4b90def6980b0ffb12adf0b00361` |
| `nova-scotia-2016-all-fields` | [10.5281/zenodo.21461604](https://doi.org/10.5281/zenodo.21461604) | [10.5281/zenodo.21960237](https://doi.org/10.5281/zenodo.21960237) | `092a0bd320ba2f96c8f45fcdc1c6b1e34c3be103354fe178cd6219ee86b07be5` |
| `nova-scotia-2021-all-fields` | [10.5281/zenodo.21461606](https://doi.org/10.5281/zenodo.21461606) | [10.5281/zenodo.21960241](https://doi.org/10.5281/zenodo.21960241) | `172cbc1026bb98ce075cf0257e3bd7f15405bc5ff5aa6dda63aa847cae68acb2` |
| `ontario-2016-all-fields` | [10.5281/zenodo.21461608](https://doi.org/10.5281/zenodo.21461608) | [10.5281/zenodo.21960346](https://doi.org/10.5281/zenodo.21960346) | `a10491591fcc25bdc6dbfaff24d0948a423dfdd1655a6c85b4b4ae39493b9c13` |
| `ontario-2021-all-fields` | [10.5281/zenodo.21461610](https://doi.org/10.5281/zenodo.21461610) | [10.5281/zenodo.21960343](https://doi.org/10.5281/zenodo.21960343) | `47ff848e848bb83591ca355685ea6d655acaa97b140c2ad34e354c51556ef2ab` |
| `pei-2016-minimal` | [10.5281/zenodo.21461612](https://doi.org/10.5281/zenodo.21461612) | [10.5281/zenodo.21960199](https://doi.org/10.5281/zenodo.21960199) | `463ea4cf8258c461e996c42515892734d9087fb4c80968156cd43c7b805a2505` |
| `pei-2021-minimal` | [10.5281/zenodo.21461527](https://doi.org/10.5281/zenodo.21461527) | [10.5281/zenodo.21960090](https://doi.org/10.5281/zenodo.21960090) | `0009386ef95d07fe85fdc8fcdee874d515b387aa56622ef39082479c5c451a0c` |
| `quebec-2016-all-fields` | [10.5281/zenodo.21461614](https://doi.org/10.5281/zenodo.21461614) | [10.5281/zenodo.21960337](https://doi.org/10.5281/zenodo.21960337) | `de3cc1e5f03b219988b7bfda889a6084ecaff3f9f9a5ed60b868b71746fd5c64` |
| `quebec-2021-all-fields` | [10.5281/zenodo.21461616](https://doi.org/10.5281/zenodo.21461616) | [10.5281/zenodo.21960324](https://doi.org/10.5281/zenodo.21960324) | `58add7c06fc89512f125db9f3dd3ebc86fd1f9a019fd0631bcbecd29ccd2c499` |
| `saskatchewan-2016-all-fields` | [10.5281/zenodo.21461618](https://doi.org/10.5281/zenodo.21461618) | [10.5281/zenodo.21960249](https://doi.org/10.5281/zenodo.21960249) | `635b5be860796aa0586d71db3199e06be4a473fc9ce13224f98285e5929bb1cd` |
| `saskatchewan-2021-all-fields` | [10.5281/zenodo.21461620](https://doi.org/10.5281/zenodo.21461620) | [10.5281/zenodo.21960232](https://doi.org/10.5281/zenodo.21960232) | `f72b629cb86c70528321d73464a4a21397efbdf3967fca2eb36ea5e2e435b761` |
| `toronto-cma-2016-all-fields` | [10.5281/zenodo.21461622](https://doi.org/10.5281/zenodo.21461622) | [10.5281/zenodo.21960327](https://doi.org/10.5281/zenodo.21960327) | `fbf37557ea2564781916cbb741b16e112d667c04001e27a8867761a325f9a791` |
| `toronto-cma-2021-all-fields` | [10.5281/zenodo.21461624](https://doi.org/10.5281/zenodo.21461624) | [10.5281/zenodo.21960330](https://doi.org/10.5281/zenodo.21960330) | `37a46b9fd59a60b068c206d9ebc288bfc00b747394c8ce4d570647cc8a71d40c` |
| `vancouver-cma-2016-all-fields` | [10.5281/zenodo.21461626](https://doi.org/10.5281/zenodo.21461626) | [10.5281/zenodo.21960289](https://doi.org/10.5281/zenodo.21960289) | `4f63d9f16d82361534ea754921aa83de29c78512741e29ee7600ee7af0b146e2` |
| `vancouver-cma-2021-all-fields` | [10.5281/zenodo.21461630](https://doi.org/10.5281/zenodo.21461630) | [10.5281/zenodo.21960299](https://doi.org/10.5281/zenodo.21960299) | `48ccf0df1cfdfdc5f3d57d690178bffc0cc1b1ccb709c298d6c3d0b01358ebd7` |

## Interpretation Boundary

Completion records the archive and registry transaction, not external legal
approval, Statistics Canada endorsement, privacy certification, or fitness
for every research use. ADR-0014 remains the maintainer's scoped
open-by-default policy: the authored layer's CC BY 4.0 grant is cumulative
with the continuing Statistics Canada Open Licence, attribution,
non-identification, accuracy, non-misrepresentation, and no-endorsement
conditions. Historical versions remain publicly available for
reproducibility.
