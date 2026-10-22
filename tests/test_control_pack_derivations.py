"""Control pack derivations behaviour and regression tests."""

from __future__ import annotations

import pytest
from support.control_pack_fixtures import (
    _population,
)

from synthpopcan.control_packs import (
    apply_control_pack_derivations,
)


def test_candidate_derivations_are_non_mutating_and_vintage_specific() -> None:
    households, persons = _population(2021)
    derived_households, derived_persons = apply_control_pack_derivations(
        "statcan-2021-core-private-household-da-v1",
        households,
        persons,
    )

    assert "household_size_group" not in households[0]
    assert "age_group_3" not in persons[0]
    assert [row["household_size_group"] for row in derived_households] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert {row["age_group_3"] for row in derived_persons} == {
        "0_14",
        "15_64",
        "65_plus",
    }
    assert all("GENDER" in row for row in derived_persons)


def test_candidate_derivation_rejects_unmapped_age_without_mutating() -> None:
    households, persons = _population(2016)
    persons[0]["AGEGRP"] = "19"

    with pytest.raises(ValueError, match="unmapped category '19'"):
        apply_control_pack_derivations(
            "statcan-2016-core-private-household-csd-v1",
            households,
            persons,
        )
    assert "age_group_3" not in persons[0]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "value is missing"),
        ("not-an-integer", "expected an integer"),
        ("0", "expected a positive integer"),
    ],
)
def test_candidate_derivation_rejects_invalid_household_size_values(
    value: str | None,
    message: str,
) -> None:
    households, persons = _population(2021)
    if value is None:
        households[0].pop("household_size")
    else:
        households[0]["household_size"] = value

    with pytest.raises(ValueError, match=message):
        apply_control_pack_derivations(
            "statcan-2021-core-private-household-da-v1",
            households,
            persons,
        )
