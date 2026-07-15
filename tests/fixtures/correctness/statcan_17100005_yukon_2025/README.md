# Statistics Canada reference fixture

This fixture is a pinned two-row extract from Statistics Canada table
17-10-0005-01, *Population estimates on July 1, by age and gender*. It was
downloaded on 2026-07-15 from the WDS full-table CSV endpoint:

<https://www150.statcan.gc.ca/n1/tbl/csv/17100005-eng.zip>

The source archive identified itself as the 2025-09-24 table snapshot. The
extract retains reference period 2025, geography Yukon, age `0 years`, unit
`Persons`, and the `Men+` and `Women+` gender rows. The retained source vectors
are `v470185` and `v470186`.

Independent expected calculation:

- `Men+`: the published `VALUE` is 231;
- `Women+`: the published `VALUE` is 210;
- combined selected population: `231 + 210 = 441`;
- the mapping changes only labels (`Men+ -> M`, `Women+ -> F`, and
  `0 years -> age_000`), so expected control counts remain 231 and 210.

`source.csv` deliberately retains only the fields needed to identify and audit
these rows. Live WDS tests detect service drift; this versioned fixture is the
offline numerical oracle.
