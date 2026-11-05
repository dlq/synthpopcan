"""Independent analytic checks for fitting rounded observed controls."""

from __future__ import annotations

import numpy as np
import pytest

from synthpopcan._observed_calibration import fit_observed_constraints


def fit(matrix, target, initial=None, *, total=2.0, iterations=100, tolerance=1e-5):
    matrix = np.asarray(matrix, dtype=float)
    return fit_observed_constraints(
        matrix,
        np.asarray(target, dtype=float),
        np.ones(matrix.shape[1]) if initial is None else np.asarray(initial),
        household_total=total,
        max_iterations=iterations,
        tolerance=tolerance,
    )


def test_incompatible_duplicate_observations_have_analytic_dense_compromise():
    # Both rows measure the same cell. Squared residuals [x, x-2] have their
    # minimum at x=1; the symmetric entropy prior has the same exact minimum.
    matrix = np.array([[1.0, 0.0], [1.0, 0.0]])
    target = np.array([0.0, 2.0])
    initial = np.ones(2)
    weights, converged, iterations, error, details = fit(matrix, target, initial)
    assert weights == pytest.approx([1.0, 1.0], abs=1e-10)
    assert not converged and error == pytest.approx(1.0)
    # The orthogonal formulation recognizes that the prior is already optimal.
    assert iterations == 0
    assert details["optimizer_converged"] and not details["controls_converged"]
    assert details["zero_target_max_abs_error"] == pytest.approx(1.0)
    assert details["household_total_error"] == 0
    np.testing.assert_array_equal(matrix, [[1, 0], [1, 0]])
    np.testing.assert_array_equal(target, [0, 2])
    np.testing.assert_array_equal(initial, [1, 1])


def test_feasible_interior_table_is_fitted_without_sparse_donors():
    # Independent 2x2 margins have the entropy solution [12,18,28,42]. The
    # explicit ridge permits a small, measured count bias around that solution.
    matrix = [[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0], [0, 1, 0, 1]]
    weights, converged, _iterations, error, details = fit(
        matrix, [30, 70, 40, 60], total=100, tolerance=1e-3
    )
    assert converged and error <= 1e-3
    assert weights == pytest.approx([12, 18, 28, 42], abs=1e-3)
    assert sum(weights) == 100
    assert details["optimizer_converged"]


def test_observed_zero_permits_small_residual_without_changing_its_target():
    target = np.array([0.0, 10.0])
    weights, converged, _iterations, error, details = fit(
        np.eye(2), target, total=10, tolerance=1e-3
    )
    assert converged and 0 < weights[0] < 1e-3
    assert weights.sum() == 10
    assert error == pytest.approx(weights[0])
    assert details["zero_target_max_abs_error"] == pytest.approx(weights[0])
    np.testing.assert_array_equal(target, [0, 10])


def test_zero_prior_is_preserved_and_unsupported_observation_is_reported():
    weights, converged, _iterations, error, details = fit(
        np.eye(2), [1, 1], initial=[0, 1]
    )
    assert weights.tolist() == [0, 2]
    assert not converged and error == 1
    assert details["optimizer_converged"]
    assert details["positive_prior_profiles"] == 1


def test_indistinguishable_donors_keep_prior_ratios_and_fractional_total():
    matrix = np.tile(np.array([[1, 0], [0, 1]]), 100)
    initial = np.arange(1, 201, dtype=float)
    total = 127.25
    result = fit(matrix, [50, 77.25], initial, total=total, tolerance=1e-3)
    weights = result[0]
    assert result[1] and weights.sum() == total
    assert np.all(weights > 0)
    for parity in (0, 1):
        ratios = weights[parity::2] / initial[parity::2]
        np.testing.assert_allclose(ratios, ratios[0], rtol=1e-12)
    repeated = fit(matrix, [50, 77.25], initial, total=total, tolerance=1e-3)
    np.testing.assert_array_equal(weights, repeated[0])
    assert result[1:] == repeated[1:]


def test_empty_control_system_returns_normalized_prior():
    weights, converged, iterations, error, details = fit(
        np.empty((0, 3)), [], [1, 2, 1], total=8
    )
    assert weights == pytest.approx([2, 4, 2])
    assert converged and iterations == 0 and error == 0
    assert details["optimizer_converged"]


def test_read_only_inputs_and_extreme_finite_prior_weights_are_supported():
    matrix = np.eye(2)
    target = np.ones(2)
    prior = np.array([1e308, 1e308])
    for value in (matrix, target, prior):
        value.setflags(write=False)
    weights, converged, iterations, error, _details = fit(matrix, target, prior)
    assert weights.tolist() == [1, 1]
    assert converged and iterations == 0 and error == 0


def test_extreme_prior_odds_remain_stable_and_find_dense_compromise():
    weights, converged, iterations, _error, details = fit(
        np.eye(2), [5, 5], [1e-100, 1], total=10, tolerance=0.1
    )
    assert converged and iterations < 100 and details["optimizer_converged"]
    assert weights.sum() == 10 and np.all(weights > 0)
    # Independent first-order condition for the one-dimensional fixed-total
    # primal: entropy log odds plus the derivative of both squared residuals.
    derivative = (
        np.log(weights[0] / weights[1]) - np.log(1e-100) + 2 * (weights[0] - 5) / 1e-4
    )
    assert abs(derivative) < 1e-3


def test_large_redundant_offsets_do_not_destabilize_the_fixed_total_optimum():
    total = 2_000_000.0
    matrix = np.array([[1, 0], [1, 0]], dtype=float) + 100_000
    target = total * 100_000 + np.array([0, total])
    weights, converged, iterations, error, details = fit(matrix, target, total=total)
    assert weights == pytest.approx([total / 2, total / 2], abs=1e-8)
    assert not converged and error == total / 2 and iterations == 0
    assert details["optimizer_converged"]
    assert details["optimizer_coordinate_rank"] == 1
    assert details["projection_count_error_bound"] < 1e-7


def test_trust_region_finds_compromise_despite_extreme_prior_and_conflicting_counts():
    # Three observations on two donors reduce to a scalar strictly convex
    # primal. Solve its first-order condition independently by bisection.
    total = 2000.0
    low, high = 1e-100, total - 1e-10
    for _ in range(80):
        x = (low + high) / 2
        derivative = np.log(x / (total - x)) - np.log(1e-100) + (3 * x - 1000) / 1e-4
        if derivative > 0:
            high = x
        else:
            low = x
    weights, converged, iterations, error, details = fit(
        [[1, 0], [1, 0], [0, 1]], [0, 1000, 2000], [1e-100, 1], total=total
    )
    assert weights == pytest.approx([x, total - x], abs=1e-6)
    assert weights.sum() == total and np.all(weights > 0)
    assert not converged and error > 600
    assert iterations < 100 and details["optimizer_converged"]


def test_unrepresentable_curvature_returns_finite_result_without_optimizer_success():
    weights, converged, iterations, error, details = fit(
        [[1e200, 0]], [0], total=1, tolerance=0
    )
    assert weights.tolist() == [0.5, 0.5]
    assert not converged and iterations == 0 and np.isfinite(error)
    assert not details["optimizer_converged"]
    assert details["optimizer_termination"] == "numerical_failure"


def test_zero_household_total_reports_original_positive_target_residual():
    weights, converged, iterations, error, details = fit(
        np.eye(2), [1, 0], [0, 0], total=0
    )
    assert weights.tolist() == [0, 0]
    assert not converged and iterations == 0 and error == 1
    assert details["optimizer_termination"] == "zero_household_total"


def test_iteration_limit_keeps_finite_total_preserving_result_and_honest_status():
    weights, _converged, iterations, error, details = fit(
        np.eye(2), [0, 1000], total=1000, iterations=1, tolerance=0
    )
    assert np.all(np.isfinite(weights)) and np.all(weights >= 0)
    assert weights.sum() == 1000 and iterations == 1 and error > 0
    assert not details["optimizer_converged"]
    assert details["optimizer_termination"] == "iteration_limit"


@pytest.mark.parametrize(
    "matrix,target,initial,message",
    [
        ([1, 0], [1], [1, 1], "matrix"),
        (np.empty((1, 0)), [1], [], "candidate"),
        ([[1, 0]], [1, 2], [1, 1], "targets"),
        ([[1, 0]], [1], [1], "weights"),
        ([[np.nan, 0]], [1], [1, 1], "finite"),
        ([[1, 0]], [np.inf], [1, 1], "finite"),
        ([[1, 0]], [1], [np.inf, 1], "finite"),
        ([[-1, 0]], [1], [1, 1], "non-negative"),
        ([[1, 0]], [-1], [1, 1], "non-negative"),
        ([[1, 0]], [1], [-1, 1], "non-negative"),
        ([[1, 0]], [1], [0, 0], "positive prior"),
        ([[1j, 0]], [1], [1, 1], "real"),
        ([[1e308, 0]], [1], [1, 1], "finite count range"),
    ],
)
def test_invalid_arrays_fail_before_optimization(matrix, target, initial, message):
    with pytest.raises(ValueError, match=message):
        fit_observed_constraints(
            matrix,
            target,
            initial,
            household_total=2,
            max_iterations=10,
            tolerance=0.01,
        )


@pytest.mark.parametrize(
    "options,message",
    [
        ({"household_total": -1}, "household_total"),
        ({"household_total": np.inf}, "household_total"),
        ({"max_iterations": 0}, "max_iterations"),
        ({"max_iterations": 1.5}, "max_iterations"),
        ({"max_iterations": True}, "max_iterations"),
        ({"tolerance": -1}, "tolerance"),
        ({"tolerance": np.nan}, "tolerance"),
    ],
)
def test_invalid_options_fail_before_optimization(options, message):
    parameters = dict(household_total=2, max_iterations=10, tolerance=0.01)
    parameters.update(options)
    with pytest.raises(ValueError, match=message):
        fit_observed_constraints(np.eye(2), np.ones(2), np.ones(2), **parameters)
