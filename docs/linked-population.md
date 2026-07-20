# Linked Population Schema

SynthPopCan `0.6.1` defines a versioned contract for generated household and
person artifacts. The contract describes how the two CSV tables relate without
pretending that every model must generate the same demographic attributes.

The schema version is:

```text
synthpopcan-linked-population-v1
```

## Stable v1 contract

A v1 artifact contains two CSV tables:

| Table | Required columns | Meaning |
| --- | --- | --- |
| `households.csv` | `synthetic_household_id` | One row per synthetic household; the identifier is non-empty and unique. |
| `persons.csv` | `synthetic_person_id`, `synthetic_household_id` | One row per synthetic person; the person identifier is non-empty and unique, and the household identifier references exactly one household row. |

Additional household and person columns are allowed. They may be categorical,
numeric, model-specific, or source-harmonized attributes. Their presence does
not make them part of the stable core unless a later schema version explicitly
promotes them.

The contract is shared by 2016 and 2021 Census-derived models. Integration
tests run representative hierarchical inputs from both vintages through
training, package loading, generation, artifact writing, and relationship
validation. Vintage-specific attributes such as the 2016 `SEX` and 2021
`GENDER` columns remain permitted extensions rather than changing the keys or
household/person relationship.

Row order has no semantic meaning. Column order is preserved in the descriptor
for reproducibility but consumers must select columns by name.

## Geography

Small-area output stores the assigned geography on the household table. Person
rows inherit that geography through `synthetic_household_id`; v1 does not copy
the geography onto every person row and does not introduce a separate geography
table.

The linked descriptor records:

```json
{
  "geography": {
    "household_column": "csd",
    "person_assignment": "inherited-via-household"
  }
}
```

The column name may be `ct`, `ada`, `csd`, `da`, or another explicitly declared
geography. Census vintage, geographic level, boundaries, and control provenance
remain workflow metadata rather than being inferred from the column name.

## Descriptor placement

- `write_linked_population` writes `manifest.json` beside `households.csv` and
  `persons.csv`.
- Prepared-model reports and small-area calibration reports include the same
  descriptor under `linked_population`.
- `synthpopcan models generate` retains its generation-manifest version and
  includes the linked descriptor under `linked_population`.

This embedding rule lets an existing workflow manifest keep its own lifecycle
and diagnostic fields while giving all consumers one shared population-table
contract.

## Compatibility and migration

Readers of v1 must:

1. reject unknown linked-population schema versions;
1. require the stable identifier columns and relationship;
1. allow additional attribute columns;
1. treat household geography as optional and, when declared, inherit it for
   people through the household relationship; and
1. validate identifier uniqueness and foreign-key integrity before analysis.

Legacy directories containing only `households.csv` and `persons.csv` are not
automatically invalid. They can be inspected and validated using the v1 rules,
then given a v1 descriptor without rewriting their demographic columns. A
legacy artifact that uses different identifier names requires an explicit,
reviewed migration; SynthPopCan must not guess which arbitrary source column is
the household or person key.

Maintainer and advanced-library code can perform that explicit adoption with:

```python
from pathlib import Path

from synthpopcan.linked_schema import adopt_linked_population_directory

adopt_linked_population_directory(
    Path("legacy-population"),
    geography_column="csd",
)
```

Adoption validates primary-key uniqueness and the person-to-household foreign
key before writing `manifest.json`. It does not rename columns or assert that
the population is statistically fit for a research purpose.

Future compatible additions may add optional metadata fields. Renaming stable
keys, changing relationship semantics, or requiring a new table requires a new
schema version and documented migration path.
