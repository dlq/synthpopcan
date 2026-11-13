"""Linked calibration failures identify the geography and retain their cause."""

from __future__ import annotations

import pytest

from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.small_area_synthesis import fit_linked_by_geography


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("solver", ["ipu", "hybrid"])
def test_structural_zero_failure_names_affected_geography(workers, solver):
    good, bad = "24010001", "24990001"
    households = [
        {"synthetic_household_id": "h1", "household_size": "1"},
        {"synthetic_household_id": "h2", "household_size": "1"},
    ]
    persons = [
        {
            "synthetic_household_id": "h1",
            "zero_feature": "present",
            "positive_feature": "needed",
        },
        {
            "synthetic_household_id": "h2",
            "zero_feature": "absent",
            "positive_feature": "other",
        },
    ]
    household_controls = ControlTable(
        margins=(
            ControlMargin(
                name="household size",
                dimensions=("ada", "household_size"),
                cells=tuple(
                    ControlCell({"ada": geography, "household_size": "1"}, 2)
                    for geography in (good, bad)
                ),
            ),
        ),
        dimensions=("ada", "household_size"),
    )
    person_controls = ControlTable(
        margins=(
            ControlMargin(
                name="zero feature",
                dimensions=("ada", "zero_feature"),
                cells=(
                    ControlCell({"ada": good, "zero_feature": "present"}, 1),
                    ControlCell({"ada": good, "zero_feature": "absent"}, 1),
                    ControlCell({"ada": bad, "zero_feature": "present"}, 0),
                    ControlCell({"ada": bad, "zero_feature": "absent"}, 2),
                ),
            ),
            ControlMargin(
                name="positive feature",
                dimensions=("ada", "positive_feature"),
                cells=tuple(
                    ControlCell({"ada": geography, "positive_feature": category}, 1)
                    for geography in (good, bad)
                    for category in ("needed", "other")
                ),
            ),
        ),
        dimensions=("ada", "zero_feature", "positive_feature"),
    )
    with pytest.raises(
        ValueError,
        match=r"24990001.*no household support.*structural-zero controls",
    ) as caught:
        fit_linked_by_geography(
            households,
            persons,
            household_controls,
            person_controls,
            geography_dimension="ada",
            n_workers=workers,
            joint_solver=solver,
        )

    assert isinstance(caught.value.__cause__, ValueError)
    assert str(caught.value.__cause__) == (
        "a positive linked calibration target has no household support "
        "after applying structural-zero controls"
    )


@pytest.mark.parametrize(
    ("population", "message"),
    [
        (9, "at least 10 people.*person target is 9"),
        (11, "at most 10 people.*person target is 11"),
    ],
)
def test_linked_fit_rejects_population_outside_household_size_bounds(
    population, message
):
    geography = "9350156.05"
    household = ControlTable(
        margins=(
            ControlMargin(
                "size",
                ("ct", "household_size_group"),
                (ControlCell({"ct": geography, "household_size_group": "5"}, 2),),
            ),
        ),
        dimensions=("ct", "household_size_group"),
    )
    person = ControlTable(
        margins=(
            ControlMargin(
                "population",
                ("ct", "group"),
                (ControlCell({"ct": geography, "group": "all"}, population),),
            ),
        ),
        dimensions=("ct", "group"),
    )
    with pytest.raises(ValueError, match=rf"9350156\.05.*{message}"):
        fit_linked_by_geography(
            [{"synthetic_household_id": "h1", "household_size_group": "5"}],
            [{"synthetic_household_id": "h1"} for _ in range(5)],
            household,
            person,
            geography_dimension="ct",
        )
