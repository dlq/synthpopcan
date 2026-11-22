# Census Profile Control Fixtures

These small aggregate-only fixtures preserve the public Census Profile rows
used by the `1.1.0` expanded-household extraction regression tests. They contain
no microdata or record-level observations.

- `2016-ct-expanded-household-controls.csv` is the complete set of reviewed
  household control roots and children for Census tract `0010001.00`, extracted
  from Statistics Canada's 2016 Census Profile of Census Tracts, catalogue
  `98-316-X2016001`.
- `2021-ada-expanded-household-controls.csv` is the corresponding public slice
  for aggregate dissemination area `10010001`, extracted from Statistics
  Canada's 2021 Census Profile, catalogue `98-316-X2021001`.

The fixtures intentionally retain independently rounded root and child counts.
Tests require every source vector to reconcile within the documented base-five
rounding bound before any normalization or scaling. Statistics Canada source
Information remains governed by the
[Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence).

The paired `profile-{year}-{en,fr}-quebec.csv` fixtures retain the original
header and complete aggregate rows for Québec CMA `421` and tract
`4210001.01`, selected from the official bulk tract archives. Original bytes
and encodings are preserved; these are independent language-specific files,
not translations produced by tests. Their source archive URLs, capture dates,
and SHA-256 hashes are in the
[bilingual source review](../../../docs/records/bilingual-profile-source-review-2026-11-21.md).
Fixture SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `profile-2016-en-quebec.csv` | `bf806210899fad99de5853916cb339d787448655b6b55664a2b510001053ad03` |
| `profile-2016-fr-quebec.csv` | `255ed2bec6d44eefc7d70198f402629d29db0fa1b5d475fe6ec84a822b8e0cc6` |
| `profile-2021-en-quebec.csv` | `1032bb5e116a258781fefd48ab9f4db15fc052186a40d4cd085a584fbec7a899` |
| `profile-2021-fr-quebec.csv` | `590acda6d83a620ec17879b81e4e4ccee0b4d9319afdec695eeaf43cb3d5eaa4` |
