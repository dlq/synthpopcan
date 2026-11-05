"""Shared control profiles and an optional entropy-dual acceleration step."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from synthpopcan._numba_ipu import IPUBackendCache


class StructuralZeroSupportError(ValueError):
    """A positive linked target loses support under the structural-zero policy."""


@dataclass(frozen=True)
class JointCalibrationSystem:
    """Group indistinguishable control columns without dropping households.

    Multiplicative updates give identical columns identical factors. Their
    initial relative weights are invariant, so fitting their summed weights and
    expanding in those proportions preserves the fitting problem and diversity.
    """

    contributions: np.ndarray
    inverse: np.ndarray | None
    original: np.ndarray
    encoded: tuple[tuple[np.ndarray, np.ndarray], ...] | None = None
    _ipu_backend: IPUBackendCache = field(
        default_factory=IPUBackendCache, repr=False, compare=False
    )

    @classmethod
    def build(cls, contributions: np.ndarray) -> JointCalibrationSystem:
        if contributions.shape[1] < 512:
            return cls(
                contributions,
                None,
                contributions,
                encode_ipu_contributions(contributions),
            )
        profiles, inverse = np.unique(contributions.T, axis=0, return_inverse=True)
        if len(profiles) >= contributions.shape[1] * 0.9:
            return cls(
                contributions,
                None,
                contributions,
                encode_ipu_contributions(contributions),
            )
        grouped = np.ascontiguousarray(profiles.T)
        return cls(grouped, inverse, contributions, encode_ipu_contributions(grouped))

    def fit(
        self,
        targets: np.ndarray,
        initial_weights: np.ndarray,
        *,
        max_iterations: int,
        tolerance: float,
        solver: str,
        legacy: Callable[..., tuple[np.ndarray, bool, int, float]],
    ) -> tuple[np.ndarray, bool, int, float, dict[str, Any]]:
        if solver not in {"ipu", "hybrid"}:
            raise ValueError("joint_solver must be 'ipu' or 'hybrid'")
        if max_iterations < 1 or tolerance < 0:
            raise ValueError(
                "max_iterations must be positive and tolerance non-negative"
            )
        initial = np.asarray(initial_weights, dtype=np.float64)
        if initial.shape != (self.original.shape[1],):
            raise ValueError("joint calibration contributions do not match households")
        if np.any(initial < 0):
            raise ValueError("initial household weights must be non-negative")
        grouped = (
            initial.copy()
            if self.inverse is None
            else np.bincount(self.inverse, weights=initial)
        )
        attempt = None
        if solver == "hybrid":
            attempt = _entropy_fit(
                self.contributions,
                targets,
                grouped,
                max_iterations=min(max_iterations, 50),
                tolerance=tolerance,
            )
        if attempt is None:
            weights, converged, iterations, _error = legacy(
                self.contributions,
                targets,
                initial_weights=grouped,
                encoded_contributions=self.encoded,
                backend_cache=self._ipu_backend,
                max_iterations=max_iterations,
                tolerance=tolerance,
            )
            method = "ipu"
        else:
            weights, iterations = attempt
            converged, method = True, "entropy"
        expanded = self._expand(weights, initial, grouped)
        error = float(np.max(np.abs(self.original @ expanded - targets)))
        # Accept acceleration only against the original, uncompressed system.
        if method == "entropy" and error > tolerance:
            fallback = self.fit(
                targets,
                initial,
                max_iterations=max_iterations,
                tolerance=tolerance,
                solver="ipu",
                legacy=legacy,
            )
            fallback[4]["requested"] = solver
            return fallback
        return (
            expanded,
            bool(converged and error <= tolerance),
            iterations,
            error,
            {
                "requested": solver,
                "method": method,
                "candidate_households": len(initial),
                "control_profiles": len(grouped),
            },
        )

    def _expand(self, weights, initial, grouped):
        if self.inverse is None:
            return weights
        denominator = grouped[self.inverse]
        proportions = np.divide(
            initial, denominator, out=np.zeros_like(initial), where=denominator > 0
        )
        return weights[self.inverse] * proportions


def _entropy_fit(contributions, targets, initial, *, max_iterations, tolerance):
    """Find a feasible exponential tilt, or leave the legacy fit untouched.

    A feasible w = w0 exp(A.T lambda) is the KL projection of w0. The legacy
    multiplicative updates stay in this same exponential family. Newton's dual
    Hessian has one row per control cell, not one row per candidate household.
    Zero targets and initially zero weights retain their exact support policy.
    Failed/ill-conditioned/infeasible attempts are discarded, never published.
    """
    allowed = np.all(contributions[targets == 0] == 0, axis=0) & (initial > 0)
    positive = targets > 0
    if not np.any(positive) or not np.any(allowed):
        return None
    matrix = contributions[positive][:, allowed]
    target = targets[positive]
    scale = np.maximum(target, 1.0)
    scaled = matrix / scale[:, None]
    desired = target / scale
    log_initial = np.log(initial[allowed])
    dual = np.zeros(len(target))
    for iteration in range(1, max_iterations + 1):
        log_weights = log_initial + scaled.T @ dual
        if np.max(log_weights) > 700:
            return None
        weights = np.exp(log_weights)
        residual = matrix @ weights - target
        if float(np.max(np.abs(residual))) <= tolerance:
            result = np.zeros_like(initial)
            result[allowed] = weights
            return result, iteration
        gradient = scaled @ weights - desired
        hessian = (scaled * weights) @ scaled.T
        try:
            direction = np.linalg.lstsq(hessian, gradient, rcond=1e-12)[0]
        except np.linalg.LinAlgError:
            return None
        if not _dual_step(dual, direction, gradient, log_initial, scaled, desired):
            return None
    return None


def _dual_step(dual, direction, gradient, log_initial, scaled, desired):
    descent = float(gradient @ direction)
    if not np.isfinite(descent) or descent <= 0:
        return False
    current = log_initial + scaled.T @ dual
    objective = float(np.exp(current).sum() - desired @ dual)
    step = 1.0
    for _attempt in range(40):
        candidate = dual - step * direction
        proposed = log_initial + scaled.T @ candidate
        if np.max(proposed) < 700:
            value = float(np.exp(proposed).sum() - desired @ candidate)
            if value <= objective - 1e-4 * step * descent:
                dual[:] = candidate
                return True
        step *= 0.5
    return False


def encode_ipu_contributions(
    contributions: np.ndarray,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    """Prepare immutable lookup codes once for the shared contribution matrix."""
    encoded = []
    for row in contributions:
        values, codes = np.unique(row, return_inverse=True)
        exponents = values / max(float(np.max(values, initial=0)), 1.0)
        codes.setflags(write=False)
        exponents.setflags(write=False)
        encoded.append((codes, exponents))
    return tuple(encoded)


@dataclass(frozen=True)
class IPUSupport:
    """Compact immutable-zero support, with full-system residual checks.

    Encodings come from the full matrix: removing a zero-weight maximum-count
    column must never change a row's exponent normalization. Only geometry-local
    weight arrays and code copies are compacted; shared cached tables stay read-only.
    """

    matrix: np.ndarray
    weights: np.ndarray
    encoding: Sequence[tuple[np.ndarray, np.ndarray]]
    full_matrix: np.ndarray
    full_weights: np.ndarray
    active: np.ndarray | None

    @classmethod
    def prepare(
        cls,
        matrix: np.ndarray,
        weights: np.ndarray,
        encoding: Sequence[tuple[np.ndarray, np.ndarray]],
    ) -> IPUSupport:
        active = np.flatnonzero(weights != 0)
        if len(weights) >= 512 and 0 < len(active) < len(weights) * 0.8:
            compact = []
            for codes, exponents in encoding:
                selected = codes[active]
                selected.setflags(write=False)
                compact.append((selected, exponents))
            return cls(
                np.ascontiguousarray(matrix[:, active]),
                weights[active],
                tuple(compact),
                matrix,
                weights,
                active,
            )
        return cls(matrix, weights, encoding, matrix, weights, None)

    def max_error(self, targets: np.ndarray) -> float:
        # Use the same full matrix for every convergence decision, even when
        # zero-weight columns are omitted from the repeated sequential updates.
        if self.active is not None:
            self.full_weights[self.active] = self.weights
        return float(np.max(np.abs(self.full_matrix @ self.full_weights - targets)))
