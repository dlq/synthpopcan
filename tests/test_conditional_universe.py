"""Age-universe semantics, independent target vectors, and rejection reasons."""

from dataclasses import replace

import pytest

from synthpopcan._conditional_universe import ConditionalPersonUniverse
from synthpopcan.geography import statcan_geography_identity


@pytest.fixture
def universe() -> ConditionalPersonUniverse:
    return ConditionalPersonUniverse(
        geography=statcan_geography_identity(2021, "da", "24660244"),
        all_private_household_persons=1000,
        age_15_plus_persons=800,
        under_15_persons=200,
        source_evidence="fixture:independently-reviewed-counts",
    )


def test_eligible_categories_and_explicit_children_are_accepted(universe):
    universe.validate_targets(
        universe.geography, (300, 500), under_15_not_applicable=200
    )


def test_all_person_total_cannot_replace_the_eligible_denominator(universe):
    with pytest.raises(ValueError, match=r"age-15\+ denominator"):
        universe.validate_targets(
            universe.geography, (500, 500), under_15_not_applicable=200
        )


def test_children_cannot_be_silently_dropped_from_not_applicable_state(universe):
    with pytest.raises(ValueError, match="under-15 not-applicable target"):
        universe.validate_targets(
            universe.geography, (300, 500), under_15_not_applicable=0
        )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        pytest.param(
            "schema_version", "unknown", "unsupported.*schema", id="unknown-schema"
        ),
        pytest.param(
            "geography", None, "requires a geography identity", id="missing-geography"
        ),
        pytest.param(
            "minimum_age", 18, "private-household persons", id="wrong-age-cutoff"
        ),
        pytest.param(
            "population",
            "all-persons",
            "private-household persons",
            id="wrong-population",
        ),
        pytest.param(
            "source_evidence", " ", "requires source evidence", id="blank-evidence"
        ),
        pytest.param(
            "source_evidence", None, "requires source evidence", id="missing-evidence"
        ),
    ],
)
def test_universe_rejects_invalid_metadata_for_the_expected_reason(
    universe, field, value, reason
):
    with pytest.raises(ValueError, match=reason):
        replace(universe, **{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "all_private_household_persons",
        "age_15_plus_persons",
        "under_15_persons",
    ],
)
@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param(None, id="missing-or-suppressed"),
        pytest.param(True, id="boolean"),
        pytest.param(-1, id="negative"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinite"),
        pytest.param("800", id="textual-count"),
    ],
)
def test_each_universe_count_requires_finite_nonnegative_observed_data(
    universe, field, invalid
):
    with pytest.raises(
        ValueError, match="counts must be observed, finite and non-negative"
    ):
        replace(universe, **{field: invalid})


def test_raw_rounded_universe_totals_require_reconciliation(universe):
    with pytest.raises(
        ValueError,
        match="raw rounding differences require reviewed source reconciliation",
    ):
        replace(universe, under_15_persons=205)


@pytest.mark.parametrize(
    "vintage,level,identifier",
    [
        pytest.param(2016, "da", "24660244", id="other-vintage"),
        pytest.param(2021, "ct", "4620055.00", id="other-level"),
        pytest.param(2021, "da", "24660245", id="other-geography"),
    ],
)
def test_target_geography_must_match_the_evidenced_universe(
    universe, vintage, level, identifier
):
    geography = statcan_geography_identity(vintage, level, identifier)
    with pytest.raises(ValueError, match="geography identity"):
        universe.validate_targets(geography, (300, 500), under_15_not_applicable=200)


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("identifier_namespace", "other.namespace", id="other-namespace"),
        pytest.param("dguid", "different", id="conflicting-dguid"),
    ],
)
def test_target_namespace_and_dguid_cannot_conflict(universe, field, value):
    geography = replace(universe.geography, **{field: value})
    with pytest.raises(ValueError, match="geography identity"):
        universe.validate_targets(geography, (800,), under_15_not_applicable=200)


def test_unreviewed_census_vintage_is_rejected(universe):
    with pytest.raises(ValueError, match="reviewed 2016/2021 evidence"):
        replace(universe, geography=replace(universe.geography, census_vintage=2011))


def test_eligible_category_vector_cannot_be_empty(universe):
    with pytest.raises(ValueError, match="exhaustive eligible category vector"):
        universe.validate_targets(universe.geography, (), under_15_not_applicable=200)


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param(None, id="missing-or-suppressed"),
        pytest.param(True, id="boolean"),
        pytest.param(-1, id="negative"),
        pytest.param(float("inf"), id="infinite"),
        pytest.param(float("nan"), id="nan"),
        pytest.param("800", id="textual-count"),
    ],
)
@pytest.mark.parametrize("target", ["eligible", "under-15"])
def test_each_target_requires_observed_finite_nonnegative_counts(
    universe, invalid, target
):
    counts, children = ((invalid,), 200) if target == "eligible" else ((800,), invalid)
    with pytest.raises(
        ValueError, match="counts must be observed, finite and non-negative"
    ):
        universe.validate_targets(
            universe.geography, counts, under_15_not_applicable=children
        )


def test_zero_eligible_population_is_an_explicit_valid_universe(universe):
    children_only = replace(universe, age_15_plus_persons=0, under_15_persons=1000)
    children_only.validate_targets(
        children_only.geography, (0, 0), under_15_not_applicable=1000
    )


def test_reconciled_fractional_targets_preserve_the_eligible_total(universe):
    universe.validate_targets(
        universe.geography, (300.25, 499.75), under_15_not_applicable=200
    )


def test_overflowing_category_total_is_an_invalid_target(universe):
    large = replace(
        universe,
        all_private_household_persons=1e308,
        age_15_plus_persons=1e308,
        under_15_persons=0,
    )
    with pytest.raises(ValueError, match="total must be finite"):
        large.validate_targets(
            large.geography, (1e308, 1e308), under_15_not_applicable=0
        )
