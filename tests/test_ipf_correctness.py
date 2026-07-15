"""Differential and invariant checks for the two IPF implementations."""

from __future__ import annotations

import math
import os
import random
from collections.abc import Sequence

import numpy as np
import pytest

from synthpopcan.ipf import (
    IPFMargin,
    IPFResult,
    NumpyIPFIndex,
    calculate_max_abs_error,
    expand_records,
    fit_ipf,
    fit_ipf_numpy,
    integerize_weights,
    weighted_totals,
)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_ipf_boundaries_reject_non_finite_controls_and_weights(invalid: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        IPFMargin(("age",), {("young",): invalid})

    margin = IPFMargin(("age",), {("young",): 1.0})
    records = [{"age": "young", "weight": str(invalid)}]
    with pytest.raises(ValueError, match="finite"):
        fit_ipf(records, [margin], weight_field="weight")

    index = NumpyIPFIndex.build(records, [margin])
    with pytest.raises(ValueError, match="finite"):
        index.fit([margin], initial_weights=np.asarray([invalid]))

    with pytest.raises(ValueError, match="finite"):
        weighted_totals(records, [invalid], ("age",))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_ipf_rejects_non_finite_tolerance(invalid: float) -> None:
    records = [{"age": "young"}]
    margins = [IPFMargin(("age",), {("young",): 1.0})]
    with pytest.raises(ValueError, match="tolerance"):
        fit_ipf(records, margins, tolerance=invalid)
    with pytest.raises(ValueError, match="tolerance"):
        NumpyIPFIndex.build(records, margins).fit(margins, tolerance=invalid)


def _assert_converged_invariants(
    result: IPFResult,
    margins: Sequence[IPFMargin],
    *,
    tolerance: float,
) -> None:
    assert result.converged
    assert all(math.isfinite(weight) and weight >= 0 for weight in result.weights)
    assert result.max_abs_error <= tolerance
    independently_calculated_error = calculate_max_abs_error(
        result.records, result.weights, margins
    )
    assert independently_calculated_error <= tolerance
    assert result.max_abs_error == pytest.approx(
        independently_calculated_error, abs=tolerance
    )

    for margin in margins:
        totals = weighted_totals(result.records, result.weights, margin.dimensions)
        for key, target in margin.targets.items():
            assert totals.get(key, 0.0) == pytest.approx(target, abs=tolerance)
        assert sum(totals.values()) == pytest.approx(
            sum(margin.targets.values()), abs=tolerance
        )


def _generated_feasible_cases() -> list[tuple[list[dict[str, str]], list[IPFMargin]]]:
    rng = random.Random(20260715)
    cases: list[tuple[list[dict[str, str]], list[IPFMargin]]] = []

    case_count = 100 if os.environ.get("SYNTHPOPCAN_CORRECTNESS_EXTENDED") else 24
    for _ in range(case_count):
        ages = ("young", "middle", "old")[: rng.randint(2, 3)]
        sexes = ("F", "M")
        records: list[dict[str, str]] = []
        for age in ages:
            for sex in sexes:
                records.extend(
                    {"age": age, "sex": sex} for _ in range(rng.randint(1, 4))
                )

        population = float(rng.randint(20, 250))
        age_shares = [rng.uniform(0.2, 2.0) for _ in ages]
        age_total = sum(age_shares)
        age_targets = {
            (age,): population * share / age_total
            for age, share in zip(ages, age_shares, strict=True)
        }
        female = population * rng.uniform(0.25, 0.75)
        margins = [
            IPFMargin(("age",), age_targets),
            IPFMargin(("sex",), {("F",): female, ("M",): population - female}),
        ]
        cases.append((records, margins))

    return cases


@pytest.mark.parametrize(("records", "margins"), _generated_feasible_cases())
def test_scalar_and_numpy_ipf_agree_on_generated_feasible_tables(
    records: list[dict[str, str]], margins: list[IPFMargin]
) -> None:
    tolerance = 1e-9

    scalar = fit_ipf(records, margins, tolerance=tolerance, max_iterations=500)
    vectorized = fit_ipf_numpy(
        NumpyIPFIndex.build(records, margins),
        margins,
        tolerance=tolerance,
        max_iterations=500,
    )

    _assert_converged_invariants(scalar, margins, tolerance=tolerance)
    _assert_converged_invariants(vectorized, margins, tolerance=tolerance)
    assert vectorized.weights == pytest.approx(scalar.weights, abs=1e-10)
    assert vectorized.max_abs_error == pytest.approx(scalar.max_abs_error, abs=1e-10)
    assert vectorized.iterations == scalar.iterations


def test_scalar_and_numpy_ipf_agree_for_sparse_omitted_target_cells() -> None:
    records = [{"age": "young"}, {"age": "old"}, {"age": "uncontrolled"}]
    margins = [IPFMargin(("age",), {("young",): 6.0, ("old",): 4.0})]

    scalar = fit_ipf(records, margins, tolerance=1e-12)
    vectorized = fit_ipf_numpy(
        NumpyIPFIndex.build(records, margins), margins, tolerance=1e-12
    )

    assert scalar.weights == [6.0, 4.0, 1.0]
    assert vectorized.weights == pytest.approx(scalar.weights)
    assert vectorized.converged is scalar.converged is True
    assert vectorized.max_abs_error == scalar.max_abs_error == 0.0


def test_scalar_and_numpy_ipf_preserve_nonuniform_starting_weight_ratios() -> None:
    records = [
        {"age": "young", "weight": "3"},
        {"age": "young", "weight": "1"},
        {"age": "old", "weight": "2"},
    ]
    margins = [IPFMargin(("age",), {("young",): 8.0, ("old",): 2.0})]

    scalar = fit_ipf(records, margins, weight_field="weight", tolerance=1e-12)
    index = NumpyIPFIndex.build(records, margins)
    weights, converged, iterations, max_abs_error = index.fit(
        margins,
        initial_weights=np.array([3.0, 1.0, 2.0]),
        tolerance=1e-12,
    )

    assert converged is True
    assert iterations == scalar.iterations
    assert max_abs_error == scalar.max_abs_error
    assert weights.tolist() == pytest.approx(scalar.weights)
    assert weights.tolist() == pytest.approx([6.0, 2.0, 2.0])


def test_ipf_control_scaling_scales_fitted_weights() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "young", "sex": "M"},
        {"age": "old", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0}),
        IPFMargin(("sex",), {("F",): 55.0, ("M",): 45.0}),
    ]
    scale = 7.5
    scaled_margins = [
        IPFMargin(
            margin.dimensions,
            {key: target * scale for key, target in margin.targets.items()},
        )
        for margin in margins
    ]

    result = fit_ipf(records, margins, tolerance=1e-12)
    scaled = fit_ipf(records, scaled_margins, tolerance=1e-12)

    assert scaled.weights == pytest.approx(
        [weight * scale for weight in result.weights], abs=1e-10
    )


def test_ipf_is_invariant_to_record_order_and_consistent_category_renaming() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "young", "sex": "M"},
        {"age": "old", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 63.0, ("old",): 37.0}),
        IPFMargin(("sex",), {("F",): 54.0, ("M",): 46.0}),
    ]
    baseline = fit_ipf(records, margins, tolerance=1e-12)

    reordered_records = [records[index] for index in (2, 0, 3, 1)]
    reordered = fit_ipf(reordered_records, margins, tolerance=1e-12)
    for dimensions in (("age",), ("sex",), ("age", "sex")):
        assert reordered.margin_totals(dimensions) == pytest.approx(
            baseline.margin_totals(dimensions), abs=1e-10
        )

    renamed_records = [
        {"age": {"young": "Y", "old": "O"}[row["age"]], "sex": row["sex"]}
        for row in records
    ]
    renamed_margins = [
        IPFMargin(("age",), {("Y",): 63.0, ("O",): 37.0}),
        margins[1],
    ]
    renamed = fit_ipf(renamed_records, renamed_margins, tolerance=1e-12)
    assert renamed.weights == pytest.approx(baseline.weights, abs=1e-10)


def test_equivalent_duplicated_records_preserve_aggregate_fitted_totals() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "young", "sex": "M"},
        {"age": "old", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0}),
        IPFMargin(("sex",), {("F",): 52.0, ("M",): 48.0}),
    ]
    baseline = fit_ipf(records, margins, tolerance=1e-12)
    duplicated = fit_ipf(
        [row for record in records for row in (dict(record), dict(record))],
        margins,
        tolerance=1e-12,
    )

    for dimensions in (("age",), ("sex",), ("age", "sex")):
        assert duplicated.margin_totals(dimensions) == pytest.approx(
            baseline.margin_totals(dimensions), abs=1e-10
        )


def test_numpy_ipf_rejects_reused_index_with_different_dimension_order() -> None:
    records = [
        {"age": "young", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    indexed_margin = IPFMargin(("age", "sex"), {("young", "F"): 1.0, ("old", "M"): 1.0})
    index = NumpyIPFIndex.build(records, [indexed_margin])
    reordered_margin = IPFMargin(
        ("sex", "age"), {("F", "young"): 1.0, ("M", "old"): 1.0}
    )

    with pytest.raises(ValueError, match="do not match index encoding"):
        index.fit([reordered_margin])


def _generated_weight_vectors() -> list[list[float]]:
    rng = random.Random(15072026)
    vectors = [
        [],
        [0.0],
        [0.0, 0.0, 0.0],
        [0.01, 0.02, 0.03],
        [0.49, 0.49, 0.49],
        [1.0, 2.0, 3.0],
        [10_000.25, 20_000.75],
    ]
    vector_count = 200 if os.environ.get("SYNTHPOPCAN_CORRECTNESS_EXTENDED") else 40
    for _ in range(vector_count):
        vectors.append(
            [
                0.0 if rng.random() < 0.25 else rng.uniform(0.001, 20.0)
                for _ in range(rng.randint(1, 30))
            ]
        )
    return vectors


@pytest.mark.parametrize("weights", _generated_weight_vectors())
def test_systematic_integerization_generated_properties(weights: list[float]) -> None:
    counts = integerize_weights(weights)

    assert counts == integerize_weights(weights)
    assert len(counts) == len(weights)
    assert all(isinstance(count, int) and count >= 0 for count in counts)
    assert sum(counts) == round(sum(weights))
    assert all(
        count == 0 for weight, count in zip(weights, counts, strict=True) if weight == 0
    )

    total = sum(weights)
    integer_total = round(total)
    if integer_total:
        cumulative_weight = 0.0
        cumulative_count = 0
        for weight, count in zip(weights, counts, strict=True):
            cumulative_weight += weight
            cumulative_count += count
            expected_count = cumulative_weight * integer_total / total
            assert abs(cumulative_count - expected_count) <= 0.5 + 1e-9


def test_integerized_expansion_reproduces_counts_and_unique_traceable_ids() -> None:
    records = [
        {"id": "seed-a", "age": "young"},
        {"id": "seed-b", "age": "old"},
        {"id": "seed-c", "age": "old"},
    ]
    weights = [1.2, 2.8, 0.0]
    expected_counts = integerize_weights(weights)

    expanded = expand_records(records, weights)

    assert len(expanded) == sum(expected_counts)
    assert [row["synthetic_id"] for row in expanded] == [
        str(index) for index in range(1, len(expanded) + 1)
    ]
    assert [row["seed_id"] for row in expanded].count("seed-a") == expected_counts[0]
    assert [row["seed_id"] for row in expanded].count("seed-b") == expected_counts[1]
    assert "seed-c" not in {row["seed_id"] for row in expanded}

    with pytest.raises(ValueError, match="reserved generated columns"):
        expand_records([{"id": "seed-a", "synthetic_id": "raw"}], [1.0])


@pytest.mark.parametrize("invalid", [[float("nan")], [float("inf")], [-float("inf")]])
def test_integerization_rejects_non_finite_weights(invalid: list[float]) -> None:
    with pytest.raises(ValueError, match="finite"):
        integerize_weights(invalid)
