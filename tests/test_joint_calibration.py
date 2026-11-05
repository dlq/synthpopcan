"""Analytic and invariant checks for accelerated linked calibration."""

from __future__ import annotations

import numpy as np
import pytest

from synthpopcan._joint_calibration import JointCalibrationSystem, _entropy_fit
from synthpopcan.small_area_synthesis import _fit_joint_constraints


def test_entropy_solution_matches_independent_two_way_table():
    matrix = np.array(
        [[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0], [0, 1, 0, 1]], dtype=float
    )
    target = np.array([30, 70, 40, 60], dtype=float)
    weights, converged, iterations, error, details = JointCalibrationSystem.build(
        matrix
    ).fit(
        target,
        np.ones(4),
        max_iterations=100,
        tolerance=1e-8,
        solver="hybrid",
        legacy=_fit_joint_constraints,
    )
    assert converged and iterations < 20 and error <= 1e-8
    assert weights == pytest.approx([12, 18, 28, 42], abs=1e-8)
    assert details["method"] == "entropy"


def test_initial_and_structural_zeros_remain_exact():
    matrix = np.array([[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0]], dtype=float)
    target = np.array([0, 10, 3], dtype=float)
    result = _entropy_fit(matrix, target, np.ones(4), max_iterations=50, tolerance=1e-8)
    assert result is not None
    weights, _iterations = result
    assert weights == pytest.approx([0, 0, 3, 7], abs=1e-8)
    matrix = np.array([[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0]], dtype=float)
    result = _entropy_fit(
        matrix,
        np.array([30, 70, 40.0]),
        np.array([0, 1, 1, 1.0]),
        max_iterations=50,
        tolerance=1e-8,
    )
    assert result is not None
    assert result[0] == pytest.approx([0, 30, 40, 30], abs=1e-8)


def test_infeasible_entropy_attempt_falls_back_from_original_initial_weights():
    matrix = np.array([[1, 1], [1, 1]], dtype=float)
    target = np.array([1.0, 2.0])
    initial = np.ones(2)
    legacy = _fit_joint_constraints(
        matrix, target, initial_weights=initial, max_iterations=25, tolerance=1e-8
    )
    actual = JointCalibrationSystem.build(matrix).fit(
        target,
        initial,
        max_iterations=25,
        tolerance=1e-8,
        solver="hybrid",
        legacy=_fit_joint_constraints,
    )
    assert actual[0] == pytest.approx(legacy[0], abs=0)
    assert actual[1:4] == legacy[1:4]
    assert actual[4]["method"] == "ipu"
    assert initial.tolist() == [1.0, 1.0]


def test_grouped_profiles_preserve_nonuniform_relative_weights():
    matrix = np.tile(np.eye(2), 300)
    initial = np.arange(1, 601, dtype=float)
    targets = np.array([300.0, 700.0])
    system = JointCalibrationSystem.build(matrix)
    assert system.contributions.shape == (2, 2)
    weights, converged, _iterations, error, _details = system.fit(
        targets,
        initial,
        max_iterations=100,
        tolerance=1e-8,
        solver="hybrid",
        legacy=_fit_joint_constraints,
    )
    expected = initial.copy()
    for row, target in zip(matrix, targets, strict=True):
        expected[row == 1] *= target / initial[row == 1].sum()
    assert converged and error <= 1e-8
    assert weights == pytest.approx(expected, abs=1e-8)
    assert np.array_equal(matrix, np.tile(np.eye(2), 300))


@pytest.mark.parametrize(
    "iterations,tolerance,solver",
    [(0, 0.01, "ipu"), (10, -1, "hybrid"), (10, 0.01, "other")],
)
def test_invalid_solver_options_raise(iterations, tolerance, solver):
    with pytest.raises(ValueError):
        JointCalibrationSystem.build(np.eye(2)).fit(
            np.ones(2),
            np.ones(2),
            max_iterations=iterations,
            tolerance=tolerance,
            solver=solver,
            legacy=_fit_joint_constraints,
        )


def test_distinct_profiles_are_not_copied_or_grouped():
    matrix = np.arange(512, dtype=float)[None, :]
    system = JointCalibrationSystem.build(matrix)
    assert system.inverse is None
    assert system.contributions is matrix


def test_empty_entropy_support_is_discarded():
    assert (
        _entropy_fit(
            np.eye(2), np.zeros(2), np.ones(2), max_iterations=10, tolerance=0.01
        )
        is None
    )
    assert (
        _entropy_fit(
            np.eye(2), np.ones(2), np.zeros(2), max_iterations=10, tolerance=0.01
        )
        is None
    )


def test_negative_starting_weights_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        JointCalibrationSystem.build(np.eye(2)).fit(
            np.ones(2),
            np.array([-1.0, 1.0]),
            max_iterations=10,
            tolerance=0.01,
            solver="hybrid",
            legacy=_fit_joint_constraints,
        )


def test_ipu_cached_lookups_are_shared_read_only_and_not_rebuilt(monkeypatch):
    system = JointCalibrationSystem.build(np.eye(2))
    encoded = system.encoded
    assert encoded is not None
    assert all(
        not codes.flags.writeable and not exponents.flags.writeable
        for codes, exponents in encoded
    )
    snapshots = [(codes.copy(), exponents.copy()) for codes, exponents in encoded]

    def unexpected_encode(_matrix):
        raise AssertionError("shared lookups must not be rebuilt per geography")

    monkeypatch.setattr(
        "synthpopcan.small_area_synthesis._encode_linked_contributions",
        unexpected_encode,
    )
    for targets in (np.array([3.0, 7.0]), np.array([6.0, 4.0])):
        weights, converged, _iterations, _error, _details = system.fit(
            targets,
            np.ones(2),
            max_iterations=100,
            tolerance=1e-9,
            solver="ipu",
            legacy=_fit_joint_constraints,
        )
        assert converged
        assert weights == pytest.approx(targets)
    for (codes, exponents), (before_codes, before_exponents) in zip(
        encoded, snapshots, strict=True
    ):
        assert np.array_equal(codes, before_codes)
        assert np.array_equal(exponents, before_exponents)


def test_concurrent_geographies_keep_independent_structural_zero_support():
    from concurrent.futures import ThreadPoolExecutor

    from synthpopcan._joint_calibration import encode_ipu_contributions

    matrix = np.tile(
        np.array(
            [
                [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                [2.0, 5.0, 1.0, 3.0, 4.0, 2.0],
                [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
            ]
        ),
        100,
    )
    initial = np.ones(matrix.shape[1])
    targets = [np.array([0.0, 10.0, 40.0, 0.0]), np.array([10.0, 0.0, 30.0, 0.0])]
    reference = [
        _fit_joint_constraints(
            matrix, target, initial_weights=initial, max_iterations=100, tolerance=1e-9
        )
        for target in targets
    ]
    encoded = encode_ipu_contributions(matrix)

    def fit(target):
        return _fit_joint_constraints(
            matrix,
            target,
            initial_weights=initial,
            max_iterations=100,
            tolerance=1e-9,
            encoded_contributions=encoded,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        actual = list(executor.map(fit, targets))
    for result, expected, target in zip(actual, reference, targets, strict=True):
        assert np.array_equal(result[0], expected[0])
        assert result[1:] == expected[1:]
        assert not np.any(result[0][np.any(matrix[target == 0] > 0, axis=0)])
    assert np.array_equal(initial, np.ones(matrix.shape[1]))


@pytest.mark.parametrize(
    "target,initial", [(1e300, 1e-300), (1e-300, 1e300), (1.0, 4.0)]
)
def test_scalar_ipu_clipping_matches_numpy_bounds(target, initial):
    # One control/household has an independently calculable one-step update.
    with np.errstate(over="ignore", under="ignore", divide="ignore"):
        expected = initial * np.exp(
            np.clip(np.log(np.float64(target) / initial), -50.0, 50.0)
        )
        weights, _converged, iterations, _error = _fit_joint_constraints(
            np.ones((1, 1)),
            np.array([target]),
            initial_weights=np.array([initial]),
            max_iterations=1,
            tolerance=0.0,
        )
    assert iterations == 1
    assert weights[0] == expected


@pytest.mark.parametrize("initial_zero", [False, True])
@pytest.mark.parametrize("iterations", [1, 3, 12])
def test_pruned_support_retains_original_zero_weight_maximum_normalizer(
    initial_zero, iterations
):
    # The removed 5-count column sets the original first-row exponent to 2/5.
    # Recomputing max after pruning would incorrectly use 2/2 instead.
    matrix = np.tile(np.array([[2.0, 5.0, 0.0], [0.0, 0.0, 1.0]]), 200)
    initial = np.ones(600)
    targets = np.array([10.0, 8.0])
    if initial_zero:
        initial[1::3] = 0.0
    else:
        matrix = np.vstack([matrix, np.tile([0.0, 1.0, 0.0], 200)])
        targets = np.append(targets, 0.0)
    before = initial.copy()
    actual, converged, count, error = _fit_joint_constraints(
        matrix,
        targets,
        initial_weights=initial,
        max_iterations=iterations,
        tolerance=0.0,
    )
    expected = np.zeros(600)
    expected[0::3] = (10.0 / 400.0) ** (1.0 - 0.6**iterations)
    expected[2::3] = 8.0 / 200.0
    assert actual == pytest.approx(expected, abs=1e-12)
    assert count == iterations and not converged
    assert error == pytest.approx(float(np.max(np.abs(matrix @ expected - targets))))
    assert np.array_equal(initial, before)


def test_all_zero_ipu_support_raises_original_positive_target_error():
    with pytest.raises(ValueError, match="after applying structural-zero controls"):
        _fit_joint_constraints(
            np.ones((1, 600)),
            np.ones(1),
            initial_weights=np.zeros(600),
            max_iterations=100,
            tolerance=0.01,
        )


def test_all_zero_targets_keep_full_zero_output_and_converge():
    weights, converged, iterations, error = _fit_joint_constraints(
        np.ones((1, 600)),
        np.zeros(1),
        initial_weights=np.ones(600),
        max_iterations=100,
        tolerance=0.01,
    )
    assert converged and iterations == 1 and error == 0
    assert np.array_equal(weights, np.zeros(600))
