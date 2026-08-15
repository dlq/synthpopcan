# Hierarchical PUMF Field Eligibility

SynthPopCan's current “all-fields” model profile is broad, but it does not mean
“every column in the source file.” Before the 1.0 interface freeze, we
classified every column in the 2016 and 2021 Statistics Canada hierarchical
PUMF headers, reviewed its pre-1.0 role, and made each omission explicit.

{download}`Download the machine-readable inventory <./_static/hierarchical-pumf-field-eligibility-v1.json>`.

The versioned inventory contains 238 records: all 116 source columns from 2016
and all 122 from 2021, exactly once. For each vintage it reconciles 35 source
targets to the existing full linked household/person profile. The derived
`household_size` target is documented by the model contract rather than counted
as a source column.

| Reviewed role | Field records | Meaning before 1.0 |
| --- | ---: | --- |
| `target` | 70 | The 35 source targets in each existing full profile. |
| `condition` | 4 | `PR` and `CMA`; broad source context, not generated small-area locations. |
| `structural_key` | 8 | Source household, family, and person identifiers; never generated attributes. |
| `validation_only` | 34 | Main and replicate weights; used as source evidence, not synthetic fields. |
| `defer` | 122 | Intentionally omitted pending the field-specific work recorded in the inventory. |

## What Each Record Establishes

Every record includes the source label and published categories, source
universe, entity level, missing and not-applicable codes, observed cardinality
and missingness, weighted applicable support, aggregate rare-category counts,
and within-entity constancy evidence. It also records:

- a cross-vintage concept and an explicit predecessor or successor relation;
- its only permitted pre-1.0 role and recommended representation;
- dependencies and consistency invariants;
- a reviewed Census Profile control candidate or an explicit `uncontrolled`
  result;
- interpretation and disclosure concerns; and
- a dated decision, rationale, reviewer, and review status.

Cross-vintage records preserve real differences. For example, `SEX` and
`GENDER`, `CIP2011` and `CIP2021`, and `NOCS` and `NOC21` are connected without
being declared definitionally identical.

The observed constancy checks also explain why richer family support belongs
after 1.0. Statistics Canada special codes can differ among records associated
with a family, so the inventory reports raw differences as applicability or
placeholder evidence while testing substantive values separately. Those raw
differences are not evidence that the underlying family measure itself varies.
Family-role fields do vary by design. A future family model therefore needs
explicit economic-family and census-family membership and applicability rules;
these fields cannot safely be flattened into the current household/person
profile.

## What This Does Not Claim

The inventory is review evidence and an extension map. It does **not** add a new
public model profile, claim that deferred fields are locally controlled, or
authorize sensitive attributes for generation. A possible Census Profile
family is recorded only as `candidate_requires_crosswalk`; local
representativeness still requires a versioned control pack, compatible source
universe, and passing evidence.

Source identifiers and weights are never target fields. `PR` and `CMA` remain
conditioning context from the public-use sample, not assigned CSD, CT, ADA, DA,
or building locations.

## Reproduce the Inventory

Maintainers with a locally acquired Statistics Canada source-data workspace can
regenerate the exact artifact from the CSV headers, public metadata, and source
support statistics:

```bash
uv run python scripts/build_field_eligibility_inventory.py
```

The generator records SHA-256 digests for the exact source CSV, variable-label
metadata, and SPSS metadata bytes, embeds the ordered headers for source-free CI
validation, resolves the current target blocks through the production adapter,
and writes a deterministic JSON document. The source files remain excluded
from the repository. No microdata rows, observed raw values, or per-category
frequencies are copied into the artifact; category codes and labels come only
from the public metadata.

See {doc}`tree` for the existing profiles and the
[expanded hierarchical tree-model plan](https://github.com/dlq/synthpopcan/blob/main/plans/2026-08-01-expanded-hierarchical-tree-models.md)
for the additive and chained work that follows the 1.0 freeze.
