"""Approximate rounded observations without treating their zeros as structural.

For positive prior probabilities q and fixed household total H, this minimizes

    KL(w || H q) + ||A w - b||² / (2 ridge),  sum(w) = H.

The ridge is 1e-4 in the original count units: fitting the observed counts takes
priority over preserving the prior, while entropy discourages a sparse donor
corner. This is an explicitly approximate policy, not a reconciliation of b.
Genuine zero prior weights remain zero; observed zero targets do not remove
donors. Optimizer success and agreement with all original controls are separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

_RIDGE = 1e-4
_MAX_NEWTON_ITERATIONS = 100


@dataclass(frozen=True)
class _DualState:
    value: float
    weights: np.ndarray
    gradient: np.ndarray


def fit_observed_constraints(
    contributions: np.ndarray,
    targets: np.ndarray,
    initial_weights: np.ndarray,
    *,
    household_total: float,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, bool, int, float, dict[str, Any]]:
    """Fit every supplied observation with a fixed total and a dense prior.

    The bounded trust-region Newton optimizer uses orthogonal control space.
    At most 100 updates are attempted, additionally bounded by max_iterations.
    The returned control
    convergence flag always uses the original matrix and targets, including
    zero targets and controls with no support. No input array is modified.
    """
    matrix, target, initial = _validated_arrays(contributions, targets, initial_weights)
    _validate_options(household_total, max_iterations, tolerance)
    if household_total > 0 and float(np.max(matrix, initial=0)) > (
        np.finfo(float).max / max(household_total, 1.0)
    ):
        raise ValueError("household total and contributions exceed finite count range")
    active = initial > 0
    if household_total > 0 and not np.any(active):
        raise ValueError("a positive household total requires positive prior support")
    limit = min(max_iterations, _MAX_NEWTON_ITERATIONS)
    if household_total == 0:
        return _result(
            matrix,
            target,
            initial,
            np.zeros_like(initial),
            household_total,
            tolerance,
            0,
            limit,
            "zero_household_total",
            True,
            0.0,
        )
    selected = matrix[:, active]
    log_prior = np.log(initial[active])
    log_prior -= _logsumexp(log_prior)
    (
        weights,
        iterations,
        termination,
        optimized,
        gradient_error,
        rank,
        projection_error,
    ) = _control_space_fit(selected, target, log_prior, household_total, limit)
    expanded = np.zeros_like(initial)
    expanded[active] = weights
    result = _result(
        matrix,
        target,
        initial,
        expanded,
        household_total,
        tolerance,
        iterations,
        limit,
        termination,
        optimized,
        gradient_error,
    )
    result[4].update(
        optimizer_parameterization="centered_orthogonal",
        optimizer_coordinate_rank=rank,
        projection_count_error_bound=projection_error,
        optimizer_gradient_is_bound=True,
    )
    return result


def _control_space_fit(matrix, target, log_prior, total, limit):
    """Separate invariant row combinations without changing the primal loss.

    With sum(w)=H, A*w-b = (A-a0)*w - (b-H*a0). Components
    orthogonal to the centered matrix are constant. Their dual optimum is
    analytic and never needs to enter logits as huge cancelling coefficients.
    """
    origin = matrix[:, 0]
    centered = matrix - origin[:, None]
    basis, singular, _ = np.linalg.svd(centered, full_matrices=False)
    threshold = (
        np.finfo(float).eps * max(centered.shape) * float(np.max(singular, initial=0))
    )
    retained = basis[:, singular > threshold]
    reduced = retained.T @ centered
    projection_error = total * float(
        np.max(np.abs(centered - retained @ reduced), initial=0)
    )
    tolerance = max(
        1e-7, 64 * np.finfo(float).eps * max(total, float(np.max(target, initial=0)))
    )
    # Keep all directions if discarding numerical nulls could change counts.
    if projection_error > tolerance / 4:
        retained = basis
        reduced = retained.T @ centered
        projection_error = total * float(
            np.max(np.abs(centered - retained @ reduced), initial=0)
        )
    norm = max(1.0, float(np.max(np.sum(np.abs(retained), axis=1), initial=0)))
    result = _optimize(
        reduced,
        retained.T @ (target - total * origin),
        log_prior,
        total,
        limit,
        gradient_tolerance=tolerance / (2 * norm),
    )
    weights, iterations, termination, optimized, gradient = result
    bound = norm * gradient + projection_error
    return (
        weights,
        iterations,
        termination,
        bool(optimized and bound <= tolerance),
        bound,
        retained.shape[1],
        projection_error,
    )


def _validated_arrays(contributions, targets, initial_weights):
    values = (contributions, targets, initial_weights)
    if any(np.iscomplexobj(value) for value in values):
        raise ValueError("observed calibration arrays must contain real counts")
    matrix, target, initial = (np.asarray(value, dtype=np.float64) for value in values)
    if matrix.ndim != 2 or matrix.shape[1] == 0:
        raise ValueError("contributions must be a matrix with candidate columns")
    if target.shape != (matrix.shape[0],):
        raise ValueError("targets do not match contribution rows")
    if initial.shape != (matrix.shape[1],):
        raise ValueError("initial weights do not match candidate columns")
    if any(not np.all(np.isfinite(value)) for value in (matrix, target, initial)):
        raise ValueError("observed calibration arrays must be finite")
    if any(np.any(value < 0) for value in (matrix, target, initial)):
        raise ValueError("observed calibration arrays must be non-negative")
    return matrix, target, initial


def _validate_options(household_total, max_iterations, tolerance):
    if not np.isfinite(household_total) or household_total < 0:
        raise ValueError("household_total must be finite and non-negative")
    if (
        isinstance(max_iterations, bool)
        or not isinstance(max_iterations, (int, np.integer))
        or max_iterations < 1
    ):
        raise ValueError("max_iterations must be a positive integer")
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")


def _logsumexp(values):
    maximum = float(np.max(values))
    return maximum + float(np.log(np.exp(values - maximum).sum()))


def _evaluate(matrix, target, log_prior, total, dual):
    logits = log_prior + matrix.T @ dual
    normalizer = _logsumexp(logits)
    probabilities = np.exp(logits - normalizer)
    # A second normalization avoids accumulated log-normalizer rounding when
    # large cancelling dual coefficients leave logits with a common offset.
    probabilities /= probabilities.sum()
    weights = total * probabilities
    weights[np.argmax(weights)] += total - float(weights.sum())
    residual = matrix @ weights - target
    gradient = residual + _RIDGE * dual
    objective = float(total * normalizer - target @ dual + 0.5 * _RIDGE * (dual @ dual))
    return _DualState(objective, weights, gradient)


def _optimize(matrix, target, log_prior, total, limit, *, gradient_tolerance=None):
    dual = np.zeros(len(target))
    state = _evaluate(matrix, target, log_prior, total, dual)
    radius = 1.0
    if gradient_tolerance is None:
        gradient_tolerance = max(
            1e-7,
            64 * np.finfo(float).eps * max(total, float(np.max(target, initial=0))),
        )
    for iteration in range(limit + 1):
        gradient_error = float(np.max(np.abs(state.gradient), initial=0))
        if gradient_error <= gradient_tolerance:
            return state.weights, iteration, "gradient_tolerance", True, gradient_error
        if iteration == limit:
            return state.weights, iteration, "iteration_limit", False, gradient_error
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                hessian = _curvature(matrix, state, total)
                direction = _trust_direction(hessian, state.gradient, radius)
                proposed = _evaluate(matrix, target, log_prior, total, dual - direction)
                accepted, radius = _trust_update(
                    state, proposed, direction, hessian, radius
                )
        except (np.linalg.LinAlgError, FloatingPointError):
            return state.weights, iteration, "numerical_failure", False, gradient_error
        if accepted:
            dual -= direction
            state = proposed
    raise AssertionError("bounded Newton loop did not return")  # pragma: no cover


def _curvature(matrix, state, total):
    mean = matrix @ state.weights / total
    centered = matrix - mean[:, None]
    hessian = (centered * state.weights) @ centered.T
    hessian.flat[:: len(mean) + 1] += _RIDGE
    if not np.all(np.isfinite(hessian)):
        raise FloatingPointError("observed calibration curvature exceeds finite range")
    return hessian


def _trust_direction(hessian, gradient, radius):
    """Solve the small positive-curvature trust problem in an eigenbasis.

    Damping limits the update norm without clipping individual donor logits.
    A bisection finds the boundary step when the Newton step exceeds the radius.
    """
    eigenvalues, basis = np.linalg.eigh(hessian)
    projected = basis.T @ gradient
    floor = max(
        0.0,
        -float(eigenvalues.min())
        + np.finfo(float).eps * max(1.0, float(eigenvalues.max())),
    )
    shift = floor
    if np.linalg.norm(projected / (eigenvalues + shift)) > radius:
        low = shift
        high = max(1.0, float(np.linalg.norm(gradient)) / radius, 2 * shift)
        # This upper bound exceeds ||g||/radius and cancels negative roundoff.
        high += floor
        for _ in range(50):
            shift = (low + high) / 2
            if np.linalg.norm(projected / (eigenvalues + shift)) > radius:
                low = shift
            else:
                high = shift
        shift = high
    return basis @ (projected / (eigenvalues + shift))


def _trust_update(state, proposed, direction, hessian, radius):
    predicted = float(
        state.gradient @ direction - 0.5 * direction @ hessian @ direction
    )
    ratio = (state.value - proposed.value) / predicted if predicted > 0 else -1.0
    if ratio < 0.25:
        radius *= 0.25
    elif ratio > 0.75 and np.linalg.norm(direction) > 0.9 * radius:
        radius = min(2 * radius, 1e10)
    roundoff = 16 * np.finfo(float).eps * max(abs(state.value), 1.0)
    improves_gradient = np.max(np.abs(proposed.gradient), initial=0) < np.max(
        np.abs(state.gradient), initial=0
    )
    accepted = ratio > 0.15 or (
        proposed.value <= state.value + roundoff and improves_gradient
    )
    return accepted, radius


def _result(
    matrix,
    target,
    initial,
    weights,
    total,
    tolerance,
    iterations,
    limit,
    termination,
    optimized,
    gradient_error,
):
    residual = matrix @ weights - target
    error = float(np.max(np.abs(residual), initial=0))
    total_error = abs(float(weights.sum()) - total)
    converged = bool(error <= tolerance and total_error <= tolerance)
    zero_residual = float(np.max(np.abs(residual[target == 0]), initial=0))
    return (
        weights,
        converged,
        iterations,
        error,
        {
            "method": "observed_entropy_least_squares",
            "zero_target_policy": "observed",
            "regularization": _RIDGE,
            "loss": (
                "KL(w || household_total * prior) + "
                "sum((A @ w - b)^2) / (2 * regularization)"
            ),
            "optimizer_converged": optimized,
            "optimizer_termination": termination,
            "optimizer_max_iterations": limit,
            "optimizer_gradient_max_abs": gradient_error,
            "controls_converged": converged,
            "max_abs_error": error,
            "zero_target_max_abs_error": zero_residual,
            "household_total": total,
            "household_total_error": total_error,
            "positive_prior_profiles": int(np.count_nonzero(initial)),
            "positive_fitted_profiles": int(np.count_nonzero(weights)),
        },
    )
