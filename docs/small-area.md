# Small-Area Linked Synthesis

Small-area linked synthesis bridges two sources that do not contain the same
information:

- prepared linked household/person model packages can generate plausible
  synthetic households and people, but they do not know census tract or ADA
  locations by themselves;
- Census Profile tables contain public small-area totals, but they do not
  contain household/person microdata rows.

The current workflow generates a candidate household/person population from a
prepared model package, calibrates candidate households to household-level
small-area controls, assigns each realized household to the target geography,
and copies linked person rows into those assigned households.

This first pass is intentionally household-first. Person rows inherit geography
from their assigned household. Person-level small-area calibration is a later
quality step.

## Command-Line Shape

The first command creates candidate linked household/person rows from a reviewed
package:

```bash
synthpopcan tree generate-from-package MODEL_PACKAGE.json \
  --households 50000 \
  --households-out candidate-households.csv \
  --persons-out candidate-persons.csv \
  --manifest-out candidate-manifest.json \
  --random-seed 462
```

The second command calibrates those candidates to small-area controls:

```bash
synthpopcan small-area calibrate-linked \
  --households candidate-households.csv \
  --persons candidate-persons.csv \
  --controls ct-tenure-controls.csv \
  --geography-dimension ct \
  --geography-column ct \
  --households-out synthetic-households.csv \
  --persons-out synthetic-persons.csv \
  --report small-area-report.json
```

The controls must be a normalized SynthPopCan control CSV. One dimension should
name the target geography, such as `ct` or `ada`. The remaining dimensions must
already exist in the candidate household CSV. For example, a first-pass tenure
control can use `ct,TENUR` when candidate households contain `TENUR`.

## Beginner API Shape

The same calibration step is available from the beginner API:

```python
from pathlib import Path

import synthpopcan as spc

summary = spc.calibrate_small_area_linked(
    households=Path("candidate-households.csv"),
    persons=Path("candidate-persons.csv"),
    controls=Path("ct-tenure-controls.csv"),
    geography_dimension="ct",
    geography_column="ct",
    households_out=Path("synthetic-households.csv"),
    persons_out=Path("synthetic-persons.csv"),
    report_out=Path("small-area-report.json"),
)

summary["assigned_households"], summary["assigned_persons"]
```

Use the API when a notebook needs to keep prose, file choices, and generated
output together. Use the CLI when the output is large enough that streaming CSV
writing and progress feedback are more useful.

## Montreal CT And Quebec ADA Run

The current local real-data smoke run used:

- the reviewed Montreal CMA 2016 all-fields package;
- the reviewed Quebec 2016 all-fields package;
- 2016 Census Profile tenure controls from census tracts for Montreal and
  aggregate dissemination areas for Quebec;
- scaled tenure controls to match the large household counts used in earlier
  model-generation experiments.

Output artifacts were written under `data/private/small-area/`, which is
ignored by git:

| Run | Geography | Households | Persons | Control used | Output |
| --- | --- | ---: | ---: | --- | --- |
| Montreal | Census tract (`ct`) | 1,830,000 | 4,170,389 | Tenure (`TENUR`) | `montreal-ct-synthetic-households-1830000.csv`, `montreal-ct-synthetic-persons-1830000.csv` |
| Quebec | Aggregate dissemination area (`ada`) | 3,750,000 | 8,330,828 | Tenure (`TENUR`) | `quebec-ada-synthetic-households-3750000.csv`, `quebec-ada-synthetic-persons-3750000.csv` |

Both linked outputs passed `synthpopcan validate linked-output`.

The person counts are model-derived. They were not forced to exact official
population totals in this first pass. For example, the Quebec run creates
3,750,000 households and 8,330,828 people because persons are generated from the
household/person package and then copied into calibrated households.

## Current Limits

The current implementation is useful, but still a prototype for substantive
small-area analysis:

- it fits household-level controls only;
- persons inherit the assigned household geography;
- candidate-pool size affects the variety available inside each small area;
- household-size controls from Census Profile need a recoded candidate column
  such as `household_size_profile` before fitting categories like `5 or more`;
- DA-level runs are expected to be sparser than ADA-level runs and need stronger
  diagnostics.

The next quality work belongs in `PLANS.md`: person-level validation and
calibration, richer control mapping helpers, better residual diagnostics, and
performance guidance for province-scale runs.
