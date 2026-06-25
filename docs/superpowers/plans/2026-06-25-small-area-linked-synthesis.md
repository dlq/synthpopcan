# Small-Area Linked Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end workflow that fetches or reuses Census Profile small-area controls, assigns generated linked household/person candidates to target geographies, and calibrates household rows while preserving household/person links.

**Architecture:** Use the existing tree package generator to create plausible linked household/person candidates, then add a separate small-area calibration layer that fits household candidates to each target geography. The first implementation uses Montreal census tracts as the prototype, but the code and CLI must accept any geography dimension, especially `ada` for province-wide/country-wide first runs and `da` for later finer runs. The workflow writes assigned household rows with a configurable geography column, copies linked person rows into the assigned households, and validates the linked output plus controlled household margins.

**Tech Stack:** Python dataclasses, existing `synthpopcan.controls.ControlTable`, existing `synthpopcan.ipf.fit_ipf`, Click CLI, CSV fixtures, pytest.

______________________________________________________________________

## File Structure

- Create: `src/synthpopcan/small_area_synthesis.py`
  - Owns small-area request/result dataclasses, control slicing by geography, household IPF fitting per target geography, and linked household/person realization.
- Create: `src/synthpopcan/cli_small_area.py`
  - Adds `synthpopcan small-area calibrate-linked` for candidate CSVs and `synthpopcan small-area synthesize-from-package` as a later convenience wrapper.
- Modify: `src/synthpopcan/cli.py`
  - Registers the new `small-area` command group.
- Modify: `src/synthpopcan/api.py`
  - Adds a small library wrapper only after the CLI/core workflow is stable.
- Create: `tests/test_small_area_synthesis.py`
  - Unit and CLI tests for control slicing, per-geography household fitting, linked realization, and validation-ready output.
- Modify: `docs/tree.md`, `docs/ipf.md`, `docs/validate.md`, `docs/library.md`, `docs/status.md`
  - Document the generate-then-calibrate bridge without repeating the IPF and tree primers.
- Modify: `PLANS.md`
  - Mark this work as the current high-priority next implementation slice.

## Core Design

Small-area means a target geography column in normalized controls, not a single
fixed Statistics Canada geography. The first prototype can use `tract` because
the Montreal tract files are already staged. Province-wide and country-wide
work should use `ada` first, then `da` once the pipeline handles sparse controls
well enough.

Fetch or reuse controls in this order:

```bash
# Montreal prototype, where CT controls are already staged locally.
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ct \
  --out-dir data/raw/statcan/census-profile/2016

# Province-wide or country-wide first pass.
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ada \
  --out-dir data/raw/statcan/census-profile/2016

# Later finer wall-to-wall pass.
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level da-all \
  --out-dir data/raw/statcan/census-profile/2016
```

Normalize fetched or staged Census Profile rows with reviewed mappings:

```bash
synthpopcan controls from-census-profile 2016-census-profile-ada.csv \
  --mapping ada-household-controls.json \
  --out ada-household-controls.csv
```

The first pass should use candidate linked household/person CSVs as input:

```bash
synthpopcan tree generate-from-package montreal-cma-2016-all-fields \
  --households 50000 \
  --households-out candidates-households.csv \
  --persons-out candidates-persons.csv \
  --manifest-out candidates.manifest.json

synthpopcan small-area calibrate-linked \
  --households candidates-households.csv \
  --persons candidates-persons.csv \
  --controls ada-household-controls.csv \
  --geography-dimension ada \
  --geography-column ada \
  --households-out small-area-households.csv \
  --persons-out small-area-persons.csv \
  --weights-out small-area-household-weights.csv \
  --report small-area-calibration-report.json
```

The controls CSV should use the existing normalized long format. Each target cell includes a geography dimension:

```csv
margin,dimensions,ada,household_size,TENUR,count
ada household size by tenure,"ada,household_size,TENUR",2400101,1,owner,120
ada household size by tenure,"ada,household_size,TENUR",2400101,1,renter,180
ada household size by tenure,"ada,household_size,TENUR",2400101,2,owner,160
ada household size by tenure,"ada,household_size,TENUR",2400102,1,owner,90
```

For each target geography, the fitter removes the geography dimension from that geography's controls, fits candidate household rows to the remaining dimensions, integerizes weights, and emits assigned household rows with the configured geography column populated. Persons are copied from the selected candidate households and rewritten to the new synthetic household identifiers.

This deliberately does not claim person-level small-area calibration yet. Person rows inherit geography from their assigned household, then later validation can show which person margins fit or fail.

### Task 0: Small-Area Source Strategy

**Files:**

- Modify: `docs/status.md`

- Modify: `docs/statcan.md`

- Modify: `docs/controls.md`

- Test: no new code tests; documentation build only.

- [ ] **Step 1: Document the target geography ladder**

Add this text to the small-area synthesis section created in Task 7:

```markdown
For Montreal, we can begin with census tracts because the staged 2016 Census
Profile tract file already covers the Montreal CMA. For province-wide and
country-wide work, we should name the product by the small geography being
used. Use aggregate dissemination areas first because they cover Canada and are
less sparse than dissemination areas. Use dissemination areas later when the
calibration, validation, and sparse-control diagnostics are strong enough.
```

- [ ] **Step 2: Document fetch commands for CT, ADA, and DA**

Add these commands to `docs/statcan.md` or the small-area synthesis page:

```bash
synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ct \
  --out-dir data/raw/statcan/census-profile/2016

synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level ada \
  --out-dir data/raw/statcan/census-profile/2016

synthpopcan statcan census-profile fetch \
  --year 2016 \
  --geo-level da-all \
  --out-dir data/raw/statcan/census-profile/2016
```

- [ ] **Step 3: Document mapping requirement**

Add this warning:

```markdown
Fetching a Census Profile file is not the same as choosing controls. The
workflow still needs reviewed mappings from source profile rows to generated
columns such as `household_size`, `TENUR`, dwelling type, age, and sex. We
should start with a small set of household controls and validate person
controls before trying joint household/person fitting.
```

- [ ] **Step 4: Run docs formatting**

Run:

```bash
uv run --group docs mdformat docs/status.md docs/statcan.md docs/controls.md docs/superpowers/plans/2026-06-25-small-area-linked-synthesis.md PLANS.md
```

Expected: files are formatted.

- [ ] **Step 5: Commit**

```bash
git add docs/status.md docs/statcan.md docs/controls.md docs/superpowers/plans/2026-06-25-small-area-linked-synthesis.md PLANS.md
git commit -m "docs: document small-area control sources"
```

### Task 1: Core Control Slicing

**Files:**

- Create: `src/synthpopcan/small_area_synthesis.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Write failing tests for splitting controls by geography**

Add this test:

```python
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.small_area_synthesis import controls_by_geography


def test_controls_by_geography_removes_target_geography_dimension() -> None:
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size by tenure",
                dimensions=("tract", "household_size", "TENUR"),
                cells=(
                    ControlCell(
                        {"tract": "4620001.00", "household_size": "1", "TENUR": "owner"},
                        10,
                    ),
                    ControlCell(
                        {"tract": "4620001.00", "household_size": "2", "TENUR": "renter"},
                        20,
                    ),
                    ControlCell(
                        {"tract": "4620002.00", "household_size": "1", "TENUR": "owner"},
                        30,
                    ),
                ),
            ),
        ),
        dimensions=("tract", "household_size", "TENUR"),
    )

    grouped = controls_by_geography(controls, geography_dimension="tract")

    assert sorted(grouped) == ["4620001.00", "4620002.00"]
    assert grouped["4620001.00"].dimensions == ("household_size", "TENUR")
    assert grouped["4620001.00"].margins[0].dimensions == (
        "household_size",
        "TENUR",
    )
    assert grouped["4620001.00"].margins[0].cells[0].categories == {
        "household_size": "1",
        "TENUR": "owner",
    }
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_controls_by_geography_removes_target_geography_dimension -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `controls_by_geography`.

- [ ] **Step 3: Implement `controls_by_geography`**

Add:

```python
"""Small-area linked household/person synthesis helpers."""

from __future__ import annotations

from collections import defaultdict

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable


def controls_by_geography(
    controls: ControlTable,
    *,
    geography_dimension: str,
) -> dict[str, ControlTable]:
    """Split normalized controls into one control table per target geography."""

    grouped: dict[str, list[ControlMargin]] = defaultdict(list)
    for margin in controls.margins:
        if geography_dimension not in margin.dimensions:
            raise ValueError(
                f"control margin {margin.name!r} does not include "
                f"geography dimension {geography_dimension!r}"
            )
        reduced_dimensions = tuple(
            dimension
            for dimension in margin.dimensions
            if dimension != geography_dimension
        )
        cells_by_geography: dict[str, list[ControlCell]] = defaultdict(list)
        for cell in margin.cells:
            geography = cell.categories.get(geography_dimension, "")
            if not geography:
                raise ValueError(
                    f"control margin {margin.name!r} has a cell without "
                    f"{geography_dimension!r}"
                )
            cells_by_geography[geography].append(
                ControlCell(
                    categories={
                        dimension: cell.categories[dimension]
                        for dimension in reduced_dimensions
                    },
                    count=cell.count,
                )
            )
        for geography, cells in cells_by_geography.items():
            grouped[geography].append(
                ControlMargin(
                    name=margin.name,
                    dimensions=reduced_dimensions,
                    cells=tuple(cells),
                )
            )

    return {
        geography: ControlTable(
            margins=tuple(margins),
            dimensions=_control_dimensions(margins),
        )
        for geography, margins in grouped.items()
    }


def _control_dimensions(margins: list[ControlMargin]) -> tuple[str, ...]:
    seen: list[str] = []
    for margin in margins:
        for dimension in margin.dimensions:
            if dimension not in seen:
                seen.append(dimension)
    return tuple(seen)
```

- [ ] **Step 4: Run the test again**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_controls_by_geography_removes_target_geography_dimension -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/small_area_synthesis.py tests/test_small_area_synthesis.py
git commit -m "feat: split controls by target geography"
```

### Task 2: Household Fit Per Geography

**Files:**

- Modify: `src/synthpopcan/small_area_synthesis.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Write failing tests for fitting household candidates to each target geography**

Add:

```python
from synthpopcan.small_area_synthesis import fit_households_by_geography


def test_fit_households_by_geography_returns_weights_for_each_target() -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1", "TENUR": "owner"},
        {"synthetic_household_id": "h2", "household_size": "1", "TENUR": "renter"},
        {"synthetic_household_id": "h3", "household_size": "2", "TENUR": "owner"},
        {"synthetic_household_id": "h4", "household_size": "2", "TENUR": "renter"},
    ]
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("tract", "household_size"),
                cells=(
                    ControlCell({"tract": "4620001.00", "household_size": "1"}, 3),
                    ControlCell({"tract": "4620001.00", "household_size": "2"}, 1),
                    ControlCell({"tract": "4620002.00", "household_size": "1"}, 1),
                    ControlCell({"tract": "4620002.00", "household_size": "2"}, 3),
                ),
            ),
        ),
        dimensions=("tract", "household_size"),
    )

    result = fit_households_by_geography(
        households,
        controls,
        geography_dimension="tract",
        household_id_column="synthetic_household_id",
        max_iterations=50,
        tolerance=1e-9,
    )

    assert set(result.weights_by_geography) == {"4620001.00", "4620002.00"}
    assert result.weights_by_geography["4620001.00"] == [1.5, 1.5, 0.5, 0.5]
    assert result.weights_by_geography["4620002.00"] == [0.5, 0.5, 1.5, 1.5]
    assert result.reports["4620001.00"]["converged"] is True
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_fit_households_by_geography_returns_weights_for_each_target -q
```

Expected: FAIL because `fit_households_by_geography` does not exist.

- [ ] **Step 3: Implement fitting result dataclass and function**

Add:

```python
from dataclasses import dataclass

from synthpopcan.diagnostics import build_ipf_fit_report
from synthpopcan.ipf import fit_ipf


@dataclass(frozen=True)
class GeographyHouseholdFit:
    """Fitted candidate-household weights for each target geography."""

    weights_by_geography: dict[str, list[float]]
    reports: dict[str, dict[str, object]]


def fit_households_by_geography(
    households: list[dict[str, str]],
    controls: ControlTable,
    *,
    geography_dimension: str,
    household_id_column: str = "synthetic_household_id",
    weight_field: str | None = None,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> GeographyHouseholdFit:
    """Fit the same candidate household pool to each target geography."""

    if not households:
        raise ValueError("at least one candidate household row is required")
    if household_id_column not in households[0]:
        raise ValueError(f"household rows require {household_id_column!r}")

    controls_for_geographies = controls_by_geography(
        controls,
        geography_dimension=geography_dimension,
    )
    weights_by_geography: dict[str, list[float]] = {}
    reports: dict[str, dict[str, object]] = {}
    for geography, geography_controls in controls_for_geographies.items():
        result = fit_ipf(
            households,
            geography_controls.to_ipf_margins(),
            weight_field=weight_field,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
        weights_by_geography[geography] = result.weights
        reports[geography] = build_ipf_fit_report(geography_controls, result)

    return GeographyHouseholdFit(
        weights_by_geography=weights_by_geography,
        reports=reports,
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py -q
```

Expected: PASS for Task 1 and Task 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/small_area_synthesis.py tests/test_small_area_synthesis.py
git commit -m "feat: fit household candidates by target geography"
```

### Task 3: Linked Household/Person Realization

**Files:**

- Modify: `src/synthpopcan/small_area_synthesis.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Write failing tests for realizing linked small-area rows**

Add:

```python
from synthpopcan.small_area_synthesis import realize_linked_geography_population


def test_realize_linked_geography_population_preserves_person_links() -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1", "TENUR": "owner"},
        {"synthetic_household_id": "h2", "household_size": "2", "TENUR": "renter"},
    ]
    persons = [
        {"synthetic_person_id": "p1", "synthetic_household_id": "h1", "AGEGRP": "adult"},
        {"synthetic_person_id": "p2", "synthetic_household_id": "h2", "AGEGRP": "adult"},
        {"synthetic_person_id": "p3", "synthetic_household_id": "h2", "AGEGRP": "child"},
    ]

    assigned_households, assigned_persons = realize_linked_geography_population(
        households,
        persons,
        weights_by_geography={"4620001.00": [1.0, 1.0]},
        geography_column="tract",
        household_id_column="synthetic_household_id",
        person_id_column="synthetic_person_id",
        random_seed=7,
    )

    assert [row["tract"] for row in assigned_households] == [
        "4620001.00",
        "4620001.00",
    ]
    assert [row["synthetic_household_id"] for row in assigned_households] == [
        "4620001.00-1",
        "4620001.00-2",
    ]
    assert {row["synthetic_household_id"] for row in assigned_persons} == {
        "4620001.00-1",
        "4620001.00-2",
    }
    assert len(assigned_persons) == 3
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_realize_linked_geography_population_preserves_person_links -q
```

Expected: FAIL because `realize_linked_geography_population` does not exist.

- [ ] **Step 3: Implement linked realization**

Add:

```python
from collections import defaultdict

from synthpopcan.ipf import integerize_weights


def realize_linked_geography_population(
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    weights_by_geography: dict[str, list[float]],
    geography_column: str,
    household_id_column: str = "synthetic_household_id",
    person_id_column: str = "synthetic_person_id",
    random_seed: int | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Integerize geography weights and copy linked persons into assigned households."""

    persons_by_household: dict[str, list[dict[str, str]]] = defaultdict(list)
    for person in persons:
        persons_by_household[person.get(household_id_column, "")].append(person)

    assigned_households: list[dict[str, str]] = []
    assigned_persons: list[dict[str, str]] = []
    next_household_number = 1
    next_person_number = 1
    for geography in sorted(weights_by_geography):
        integer_weights = integerize_weights(weights_by_geography[geography])
        for candidate_index, repeats in enumerate(integer_weights):
            source_household = households[candidate_index]
            source_household_id = source_household[household_id_column]
            for _copy_index in range(repeats):
                assigned_household_id = f"{geography}-{next_household_number}"
                next_household_number += 1
                assigned_household = {
                    **source_household,
                    household_id_column: assigned_household_id,
                    geography_column: geography,
                    "source_candidate_household_id": source_household_id,
                }
                assigned_households.append(assigned_household)
                for source_person in persons_by_household.get(source_household_id, []):
                    assigned_person = {
                        **source_person,
                        person_id_column: f"{geography}-{next_person_number}",
                        household_id_column: assigned_household_id,
                        geography_column: geography,
                        "source_candidate_person_id": source_person.get(
                            person_id_column,
                            "",
                        ),
                    }
                    next_person_number += 1
                    assigned_persons.append(assigned_person)

    return assigned_households, assigned_persons
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/small_area_synthesis.py tests/test_small_area_synthesis.py
git commit -m "feat: realize linked small-area populations"
```

### Task 4: CSV Workflow and Report

**Files:**

- Modify: `src/synthpopcan/small_area_synthesis.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Write failing integration test for CSV inputs and outputs**

Add a test that writes `households.csv`, `persons.csv`, and `controls.csv`, then calls a high-level function:

```python
from pathlib import Path

from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs


def test_calibrate_linked_household_csvs_writes_outputs(tmp_path: Path) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    controls = tmp_path / "controls.csv"
    out_households = tmp_path / "small-area-households.csv"
    out_persons = tmp_path / "small-area-persons.csv"
    weights = tmp_path / "weights.csv"
    report = tmp_path / "report.json"

    households.write_text(
        "synthetic_household_id,household_size,TENUR\n"
        "h1,1,owner\n"
        "h2,2,renter\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h2,child\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,\"tract,household_size\",4620001.00,1,1\n'
        'size,\"tract,household_size\",4620001.00,2,1\n'
    )

    summary = calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=out_households,
        persons_out=out_persons,
        weights_out=weights,
        report_out=report,
        max_iterations=50,
        tolerance=1e-9,
    )

    assert summary["assigned_households"] == 2
    assert summary["assigned_persons"] == 3
    assert out_households.read_text().splitlines()[0].startswith(
        "synthetic_household_id,"
    )
    assert "4620001.00" in out_persons.read_text()
    assert "geography" in report.read_text()
```

- [ ] **Step 2: Run the failing integration test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_calibrate_linked_household_csvs_writes_outputs -q
```

Expected: FAIL because `calibrate_linked_household_csvs` does not exist.

- [ ] **Step 3: Implement CSV helpers and report shape**

Implement helpers using `csv.DictReader` and `csv.DictWriter`. The report must include:

```json
{
  "schema_version": "synthpopcan-small-area-linked-calibration-v1",
  "geography_dimension": "tract",
  "geography_column": "tract",
  "candidate_households": 2,
  "candidate_persons": 3,
  "assigned_households": 2,
  "assigned_persons": 3,
  "geographies": {
    "4620001.00": {
      "converged": true,
      "assigned_households": 2
    }
  }
}
```

The weights CSV must include:

```csv
target_geography,source_candidate_household_id,weight,integer_weight
4620001.00,h1,1.0,1
4620001.00,h2,1.0,1
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/small_area_synthesis.py tests/test_small_area_synthesis.py
git commit -m "feat: calibrate linked household csvs"
```

### Task 5: CLI Command

**Files:**

- Create: `src/synthpopcan/cli_small_area.py`

- Modify: `src/synthpopcan/cli.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Write failing CLI test**

Add:

```python
from synthpopcan.cli import main


def test_cli_calibrates_linked_households_to_small_area_controls(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    controls = tmp_path / "controls.csv"
    out_households = tmp_path / "small-area-households.csv"
    out_persons = tmp_path / "small-area-persons.csv"

    households.write_text(
        "synthetic_household_id,household_size,TENUR\n"
        "h1,1,owner\n"
        "h2,2,renter\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h2,child\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,\"tract,household_size\",4620001.00,1,1\n'
        'size,\"tract,household_size\",4620001.00,2,1\n'
    )

    exit_code = main(
        [
            "small-area",
            "calibrate-linked",
            "--households",
            str(households),
            "--persons",
            str(persons),
            "--controls",
            str(controls),
            "--geography-dimension",
            "tract",
            "--geography-column",
            "tract",
            "--households-out",
            str(out_households),
            "--persons-out",
            str(out_persons),
        ]
    )

    assert exit_code == 0
    assert out_households.exists()
    assert out_persons.exists()
```

- [ ] **Step 2: Run the failing CLI test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_cli_calibrates_linked_households_to_tract_controls -q
```

Expected: FAIL because the `small-area` command group is not registered.

- [ ] **Step 3: Implement `cli_small_area.py`**

Add a Click group:

```python
"""Small-area linked synthesis commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from synthpopcan.cli_output import format_file_access_error
from synthpopcan.console import print_wrote
from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs

_PATH = click.Path(path_type=Path)


@click.group()
def small_area() -> None:
    """Assign and calibrate linked households to target geographies."""


@small_area.command("calibrate-linked")
@click.option("--households", "households_path", required=True, type=_PATH)
@click.option("--persons", "persons_path", required=True, type=_PATH)
@click.option("--controls", "controls_path", required=True, type=_PATH)
@click.option("--geography-dimension", required=True)
@click.option("--geography-column", required=True)
@click.option("--households-out", required=True, type=_PATH)
@click.option("--persons-out", required=True, type=_PATH)
@click.option("--weights-out", type=_PATH)
@click.option("--report", "report_out", type=_PATH)
@click.option("--max-iterations", default=100, type=int, show_default=True)
@click.option("--tolerance", default=1e-6, type=float, show_default=True)
def calibrate_linked_command(
    households_path: Path,
    persons_path: Path,
    controls_path: Path,
    geography_dimension: str,
    geography_column: str,
    households_out: Path,
    persons_out: Path,
    weights_out: Path | None,
    report_out: Path | None,
    max_iterations: int,
    tolerance: float,
) -> None:
    """Calibrate linked household/person candidates to geography controls."""

    try:
        summary = calibrate_linked_household_csvs(
            households_path=households_path,
            persons_path=persons_path,
            controls_path=controls_path,
            geography_dimension=geography_dimension,
            geography_column=geography_column,
            households_out=households_out,
            persons_out=persons_out,
            weights_out=weights_out,
            report_out=report_out,
            max_iterations=max_iterations,
            tolerance=tolerance,
        )
    except OSError as exc:
        raise click.ClickException(
            format_file_access_error(exc.filename or households_path, "process", exc)
        ) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    print_wrote(households_out)
    print_wrote(persons_out)
    if weights_out:
        print_wrote(weights_out)
    if report_out:
        print_wrote(report_out)
    click.echo(json.dumps(summary, sort_keys=True))
```

Register the command in `src/synthpopcan/cli.py`:

```python
from synthpopcan.cli_small_area import small_area

cli.add_command(small_area, name="small-area")
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py tests/test_tree.py::test_cli_generates_linked_households_and_persons -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/cli.py src/synthpopcan/cli_small_area.py tests/test_small_area_synthesis.py
git commit -m "feat: add small-area linked calibration cli"
```

### Task 6: Validation Hooks

**Files:**

- Modify: `src/synthpopcan/small_area_synthesis.py`

- Test: `tests/test_small_area_synthesis.py`

- [ ] **Step 1: Add a test that outputs validate cleanly**

Use existing validation helpers:

```python
from synthpopcan.validation import build_control_validation_report
from synthpopcan.tree import validate_linked_population


def test_small_area_outputs_validate_against_controls_and_links(
    tmp_path: Path,
) -> None:
    # Reuse the small CSV fixture from Task 4.
    # After calibration, read output rows and verify both validators pass.
    household_report = build_control_validation_report(
        population_rows=read_csv_rows(out_households),
        controls=read_control_table(controls),
        kind="expanded",
    )
    linked_report = validate_linked_population(
        read_csv_rows(out_households),
        read_csv_rows(out_persons),
    )

    assert household_report["passed"] is True
    assert linked_report["passed"] is True
```

Implement the test with local helper functions so it is runnable.

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py::test_small_area_outputs_validate_against_controls_and_links -q
```

Expected: FAIL if output field ordering, geography assignment, or validator compatibility is incomplete.

- [ ] **Step 3: Fix output compatibility**

Ensure assigned household rows include all controlled dimensions, including the geography column. Ensure person rows use the same `synthetic_household_id` values as household rows. Do not change the existing validators unless they expose a real bug.

- [ ] **Step 4: Run validation-focused tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py tests/test_tree.py::test_cli_validates_linked_output -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthpopcan/small_area_synthesis.py tests/test_small_area_synthesis.py
git commit -m "test: validate small-area linked outputs"
```

### Task 7: Documentation and User Guidance

**Files:**

- Modify: `docs/tree.md`

- Modify: `docs/ipf.md`

- Modify: `docs/validate.md`

- Modify: `docs/library.md`

- Modify: `docs/status.md`

- Modify: `PLANS.md`

- [ ] **Step 1: Add a short conceptual section to `docs/tree.md`**

Add text explaining:

```markdown
### From Broad Microdata to Small-Area Outputs

The 2016 hierarchical PUMF gives us linked households and people, but not
census small-area identifiers on each source household. Census Profile tables give
us small-area controls, but not household microdata. The small-area workflow bridges
those sources by generating plausible linked household/person candidates, then
calibrating household candidates separately for each target geography.
```

- [ ] **Step 2: Add a command example**

Add this example:

```bash
synthpopcan small-area calibrate-linked \
  --households candidates-households.csv \
  --persons candidates-persons.csv \
  --controls ada-household-controls.csv \
  --geography-dimension ada \
  --geography-column ada \
  --households-out small-area-households.csv \
  --persons-out small-area-persons.csv \
  --report small-area-calibration-report.json
```

- [ ] **Step 3: Update validation docs**

Explain that users should run:

```bash
synthpopcan validate controls \
  --population small-area-households.csv \
  --controls ada-household-controls.csv \
  --kind expanded

synthpopcan validate linked-output \
  --households small-area-households.csv \
  --persons small-area-persons.csv
```

- [ ] **Step 4: Run docs checks**

Run:

```bash
uv run --group docs sphinx-build -b html docs docs/_build/html
```

Expected: build completes without warnings.

- [ ] **Step 5: Commit**

```bash
git add docs/tree.md docs/ipf.md docs/validate.md docs/library.md docs/status.md PLANS.md
git commit -m "docs: explain small-area linked synthesis"
```

### Task 8: Full Verification

**Files:**

- No new files unless verification exposes a defect.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
uv run pytest tests/test_small_area_synthesis.py tests/test_ipf.py tests/test_tree.py tests/test_validation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run default suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run docs build**

Run:

```bash
uv run --group docs sphinx-build -b html docs docs/_build/html
```

Expected: PASS.

- [ ] **Step 4: Check formatting and accidental personal paths**

Run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
rg -n "/Users/|~/Downloads|dlq" docs README.md PLANS.md NOTES.md src tests
```

Expected: Ruff passes. `rg` should not show personal local paths in public docs or code.

- [ ] **Step 5: Commit final fixes**

```bash
git status --short
git add src/synthpopcan/small_area_synthesis.py src/synthpopcan/cli_small_area.py src/synthpopcan/cli.py tests/test_small_area_synthesis.py docs PLANS.md
git commit -m "feat: add small-area linked synthesis workflow"
```

## Self-Review

Spec coverage:

- The plan implements the missing bridge between broad-geography PUMF-derived linked candidates and small-area Census Profile controls.
- The first pass explicitly calibrates household-level small-area controls and preserves linked persons.
- Person-level small-area calibration remains outside the first implementation, but validation commands are included so we can see person-margin gaps before adding joint calibration.

Placeholder scan:

- The plan avoids placeholder task names and gives concrete files, commands, test examples, and expected outputs.

Type consistency:

- The plan consistently uses `geography_dimension` for the control-table dimension and `geography_column` for the output CSV column.
- The plan consistently uses `synthetic_household_id` and `synthetic_person_id` as linked output identifiers.
