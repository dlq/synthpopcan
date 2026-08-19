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
