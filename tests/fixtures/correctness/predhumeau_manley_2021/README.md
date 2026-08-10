# Prédhumeau–Manley External Comparison Fixture

This directory records the pinned public dataset selected for the bounded
external Canadian comparison, a two-row project-authored schema fixture, and a
Nunavut aggregate-only empirical artifact. The CSV contains no copied or
transformed external records. The JSON contains only territory aggregates and
source checksums; it contains no source rows or direct identifiers.

The full version 2.1.0 archive is approximately 9.6 GB. It is never downloaded
by default tests, is never committed to git, and may be resolved only after an
explicit opt-in into a caller-selected cache. The publisher supplied an MD5
content checksum; the descriptor records that checksum honestly instead of
inventing a stronger digest. Any extracted slice needs its own SHA-256 digest
before it can support release evidence.

The aggregate artifact was produced from the FA 2021 Nunavut archive member
`Canada/nunavut/syn_pop/FA/synthetic_pop_2021_hh_.csv` and local SynthPopCan
2021 Nunavut output. The external projected population retains 2016 DA
identities while the local output uses 2021 DAs, so the comparison is limited
to Nunavut territory aggregates and performs no DA join. FA is not the LG
scenario used for validation in the associated article.

Both datasets are modelled populations, not observed truth. The artifact is a
method-to-method check of scale, linkage, and household-size composition; it
does not support a DA-level, scenario-superiority, national-quality, or local
representativeness claim. Default tests remain offline. Regeneration is opt-in
through `scripts/build_external_canadian_comparison.py` and requires the pinned
member plus local household/person CSVs.
