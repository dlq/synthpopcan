"""Bounded methodological oracles and realization comparisons.

This module is evidence infrastructure, not a second production calibration
path.  It deliberately uses a different formulation from the linked
multiplicative updater: a bounded exhaustive feasibility check followed by a
dual Newton solver for relative-entropy calibration.  The bounded scope keeps
the default test suite deterministic and dependency-free while still giving
small linked-calibration cases an independent oracle.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from synthpopcan.ipf import integerize_weights

__all__ = [
    "CALIBRATION_ORACLE_BACKEND",
    "INTEGERIZATION_BACKEND_DECISION",
    "INTEGERIZATION_DECISION_SCHEMA_VERSION",
    "METHODOLOGY_EVIDENCE_SCHEMA_VERSION",
    "LinkedCalibrationFixture",
    "OracleResult",
    "build_calibration_oracle_comparison",
    "build_integerization_comparison",
    "build_methodology_evidence",
    "generated_linked_calibration_fixtures",
    "largest_remainder_integerize",
    "solve_relative_entropy_oracle",
]

CALIBRATION_ORACLE_BACKEND = "bounded-relative-entropy-dual-newton-v1"
METHODOLOGY_EVIDENCE_SCHEMA_VERSION = "synthpopcan-methodology-evidence-v1"
INTEGERIZATION_DECISION_SCHEMA_VERSION = (
    "synthpopcan-integerization-backend-decision-v1"
)
_MAX_ORACLE_CANDIDATES = 14
_MAX_ORACLE_CONSTRAINTS = 20


@dataclass(frozen=True)
class LinkedCalibrationFixture:
    """A small household-contribution calibration problem.

    ``contributions`` has one row per control cell and one column per candidate
    household.  Person-control rows may contain values greater than one because
    selecting a household selects all of its linked people.
    """

    name: str
    contributions: np.ndarray
    targets: np.ndarray
    initial_weights: np.ndarray
    expected_feasible: bool
    features: tuple[str, ...]
    known_feasible_weights: np.ndarray | None = None


@dataclass(frozen=True)
class OracleResult:
    """Result from the bounded independent calibration oracle."""

    backend: str
    status: Literal["optimal", "infeasible", "iteration_limit"]
    weights: tuple[float, ...] | None
    iterations: int
    max_abs_error: float | None
    relative_entropy: float | None
    feasibility_witness: tuple[float, ...] | None
    message: str


INTEGERIZATION_BACKEND_DECISION: dict[str, Any] = {
    "schema_version": INTEGERIZATION_DECISION_SCHEMA_VERSION,
    "decision": "retain",
    "production_backend": "deterministic-systematic-midpoint-v1",
    "comparison_backend": "deterministic-largest-remainder-v1",
    "scope": "independent realization of one fitted geography at a time",
    "reasons": [
        (
            "Both methods preserve the rounded household total and never select "
            "a zero-weight candidate."
        ),
        (
            "Systematic midpoint selection retains distribution across ordered "
            "subunit-weight candidate pools where largest remainder can concentrate "
            "all tied remainders at the start of the pool."
        ),
        (
            "The bounded comparison does not show a material reviewed benefit that "
            "would justify changing existing deterministic outputs."
        ),
        (
            "Neither backend jointly guarantees household, person, or parent-"
            "geography controls; fractional and realized residual reports remain "
            "mandatory."
        ),
    ],
    "applicability": [
        "non-negative finite fitted household weights",
        "one independently realized geography",
        "stable candidate ordering and deterministic reproduction",
    ],
    "not_claimed": [
        "simultaneous control preservation",
        "joint optimality across geographies",
        "hierarchical parent-child reconciliation",
    ],
}


def generated_linked_calibration_fixtures(
    *, seed: int = 20260810, generated_cases: int = 3
) -> tuple[LinkedCalibrationFixture, ...]:
    """Return deterministic analytical, generated, and infeasible fixtures.

    Every fixture whose name starts with ``generated_`` obtains its targets by
    multiplying the contribution matrix by a known non-negative household
    weight vector.  The fixed fixtures retain edge cases that should not depend
    on pseudorandom generation.
    """

    if generated_cases < 0:
        raise ValueError("generated_cases must be non-negative")

    fixtures = [
        _fixture(
            "analytical_identity",
            [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [2.0, 3.0, 1.5],
            [1.0, 1.0, 1.0],
            features=("analytical", "ordinary_household_indicators"),
            known_weights=[2.0, 3.0, 1.5],
        ),
        _fixture_from_known_weights(
            "linked_person_counts",
            [[1, 1, 1, 1], [2, 0, 1, 3], [0, 2, 2, 1]],
            [0.75, 1.25, 2.0, 2.0],
            [1.0, 0.8, 1.4, 1.6],
            features=(
                "ordinary_household_indicators",
                "linked_person_counts_greater_than_one",
                "non_uniform_initial_weights",
            ),
        ),
        _fixture_from_known_weights(
            "sparse_rare_and_zero",
            [
                [1, 1, 1, 1, 1],
                [0, 0, 0, 1, 0],
                [0, 2, 1, 0, 3],
                [0, 0, 0, 0, 1],
            ],
            [1.5, 0.75, 2.0, 0.5, 0.0],
            [0.9, 1.4, 1.1, 0.8, 1.3],
            features=(
                "sparse_category",
                "rare_category",
                "zero_target",
                "linked_person_counts_greater_than_one",
            ),
        ),
        _fixture_from_known_weights(
            "redundant_constraints",
            [[1, 1, 0], [0, 0, 1], [1, 1, 1], [2, 2, 2]],
            [1.25, 0.75, 2.0],
            [0.7, 1.4, 1.2],
            features=("redundant_constraints", "linearly_dependent_constraints"),
        ),
        _fixture_from_known_weights(
            "nearly_dependent_constraints",
            [[1, 1, 1], [1, 1, 1.001], [0, 0, 1]],
            [0.8, 1.7, 0.5],
            [1.2, 0.9, 1.4],
            features=("nearly_dependent_constraints",),
        ),
    ]

    rng = np.random.default_rng(seed)
    for index in range(generated_cases):
        candidate_count = 6 + index
        known = rng.uniform(0.25, 2.5, size=candidate_count)
        known[-1] = 0.0
        initial = rng.uniform(0.5, 2.0, size=candidate_count)
        split = max(2, candidate_count // 2)
        group_a = [1.0 if item < split else 0.0 for item in range(candidate_count)]
        group_b = [1.0 - value for value in group_a]
        person_counts = rng.integers(0, 4, size=candidate_count).astype(float)
        person_counts[0] = 3.0
        rare = [0.0] * candidate_count
        rare[index % (candidate_count - 1)] = 1.0
        forced_zero = [0.0] * candidate_count
        forced_zero[-1] = 1.0
        fixtures.append(
            _fixture_from_known_weights(
                f"generated_{index + 1:02d}",
                [
                    [1.0] * candidate_count,
                    group_a,
                    group_b,
                    person_counts.tolist(),
                    rare,
                    forced_zero,
                ],
                known.tolist(),
                initial.tolist(),
                features=(
                    "generated_feasible",
                    "ordinary_household_indicators",
                    "linked_person_counts_greater_than_one",
                    "sparse_category",
                    "rare_category",
                    "redundant_constraints",
                    "zero_target",
                    "non_uniform_initial_weights",
                ),
            )
        )

    fixtures.extend(
        (
            _fixture(
                "unsupported_positive_target",
                [[1, 0], [0, 0]],
                [1.0, 1.0],
                [1.0, 1.0],
                expected_feasible=False,
                features=("unsupported_positive_target",),
            ),
            _fixture(
                "inconsistent_dependent_constraints",
                [[1, 1], [2, 2]],
                [1.0, 3.0],
                [1.0, 1.0],
                expected_feasible=False,
                features=("linearly_dependent_constraints", "infeasible"),
            ),
            _fixture(
                "structural_zero_removes_support",
                [[1, 0], [1, 0]],
                [0.0, 1.0],
                [1.0, 1.0],
                expected_feasible=False,
                features=("zero_target", "unsupported_after_structural_zero"),
            ),
        )
    )
    return tuple(fixtures)


def solve_relative_entropy_oracle(
    contributions: Sequence[Sequence[float]] | np.ndarray,
    targets: Sequence[float] | np.ndarray,
    initial_weights: Sequence[float] | np.ndarray,
    *,
    tolerance: float = 1e-9,
    max_iterations: int = 200,
) -> OracleResult:
    """Solve a bounded non-negative calibration problem independently.

    Feasibility is classified first by enumerating the small problem's
    candidate subsets and solving each equality system with ``numpy.linalg``.
    For feasible cases, damped Newton iteration solves the relative-entropy
    dual.  Zero targets are treated as structural zeros because all supported
    contribution values are non-negative.

    The oracle accepts at most 14 candidate households and 20 constraints.  It
    is evidence for bounded fixtures, not an optional large-run backend.
    """

    matrix, target_array, prior = _validated_calibration_arrays(
        contributions,
        targets,
        initial_weights,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )
    forced_zero = np.any(
        (matrix > 0) & np.isclose(target_array[:, None], 0.0, atol=tolerance),
        axis=0,
    )
    eligible = (prior > 0) & ~forced_zero
    positive_rows = target_array > tolerance
    positive_matrix = matrix[positive_rows][:, eligible]
    positive_targets = target_array[positive_rows]

    if positive_targets.size:
        witness_reduced = _nonnegative_feasibility_witness(
            positive_matrix,
            positive_targets,
            tolerance=tolerance,
        )
        if witness_reduced is None:
            return OracleResult(
                CALIBRATION_ORACLE_BACKEND,
                "infeasible",
                None,
                0,
                None,
                None,
                None,
                (
                    "no non-negative household weights satisfy all positive "
                    "targets after structural-zero and initial-weight support"
                ),
            )
    else:
        witness_reduced = np.zeros(int(np.count_nonzero(eligible)), dtype=float)

    witness = np.zeros(matrix.shape[1], dtype=float)
    witness[eligible] = witness_reduced
    if not positive_targets.size:
        optimal = prior.copy()
        optimal[forced_zero] = 0.0
        residual = _maximum_absolute_control_error(matrix, optimal, target_array)
        return OracleResult(
            CALIBRATION_ORACLE_BACKEND,
            "optimal",
            tuple(float(value) for value in optimal),
            0,
            residual,
            _relative_entropy(optimal, prior),
            tuple(float(value) for value in witness),
            "all targets are structural zeros or unconstrained",
        )

    active_prior = prior[eligible]
    reduced_matrix, reduced_targets = _independent_constraint_basis(
        positive_matrix, positive_targets, tolerance=tolerance
    )
    multipliers = np.zeros(reduced_matrix.shape[0], dtype=float)
    optimal_reduced = active_prior.copy()

    for iteration in range(max_iterations + 1):
        exponent = np.clip(
            _deterministic_matrix_vector_product(reduced_matrix.T, multipliers),
            -700.0,
            700.0,
        )
        optimal_reduced = np.fromiter(
            (
                float(weight) * math.exp(float(value))
                for weight, value in zip(active_prior, exponent, strict=True)
            ),
            dtype=np.float64,
            count=active_prior.size,
        )
        residual_vector = (
            _deterministic_matrix_vector_product(reduced_matrix, optimal_reduced)
            - reduced_targets
        )
        optimal = np.zeros(matrix.shape[1], dtype=float)
        optimal[eligible] = optimal_reduced
        max_abs_error = _maximum_absolute_control_error(matrix, optimal, target_array)
        if max_abs_error <= tolerance:
            return OracleResult(
                CALIBRATION_ORACLE_BACKEND,
                "optimal",
                tuple(float(value) for value in optimal),
                iteration,
                max_abs_error,
                _relative_entropy(optimal, prior),
                tuple(float(value) for value in witness),
                "bounded feasibility and relative-entropy optimum established",
            )
        if iteration == max_iterations:
            break

        hessian = _deterministic_weighted_crossproduct(reduced_matrix, optimal_reduced)
        newton_step = _solve_linear_system(hessian, residual_vector)
        directional_decrease = math.fsum(
            float(residual) * float(step)
            for residual, step in zip(residual_vector, newton_step, strict=True)
        )
        objective = _dual_objective(
            multipliers, reduced_matrix, reduced_targets, active_prior
        )
        step_scale = 1.0
        accepted = False
        while step_scale >= 2.0**-24:
            proposed = multipliers - step_scale * newton_step
            proposed_objective = _dual_objective(
                proposed, reduced_matrix, reduced_targets, active_prior
            )
            armijo_satisfied = proposed_objective <= (
                objective - 1e-4 * step_scale * directional_decrease
            )
            solves_controls = False
            if math.isfinite(proposed_objective) and not armijo_satisfied:
                # Near the optimum, the rounded dual objective can appear flat or
                # increase by a few ulps.  An exponential-family proposal that
                # satisfies every original control already meets the bounded
                # oracle's primal and stationarity tolerances, so accept it.
                proposed_exponent = np.clip(
                    _deterministic_matrix_vector_product(reduced_matrix.T, proposed),
                    -700.0,
                    700.0,
                )
                proposed_reduced = np.fromiter(
                    (
                        float(weight) * math.exp(float(value))
                        for weight, value in zip(
                            active_prior, proposed_exponent, strict=True
                        )
                    ),
                    dtype=np.float64,
                    count=active_prior.size,
                )
                proposed_optimal = np.zeros(matrix.shape[1], dtype=float)
                proposed_optimal[eligible] = proposed_reduced
                solves_controls = (
                    _maximum_absolute_control_error(
                        matrix, proposed_optimal, target_array
                    )
                    <= tolerance
                )
            if math.isfinite(proposed_objective) and (
                armijo_satisfied or solves_controls
            ):
                multipliers = proposed
                accepted = True
                break
            step_scale *= 0.5
        if not accepted:
            break

    optimal = np.zeros(matrix.shape[1], dtype=float)
    optimal[eligible] = optimal_reduced
    max_abs_error = _maximum_absolute_control_error(matrix, optimal, target_array)
    return OracleResult(
        CALIBRATION_ORACLE_BACKEND,
        "iteration_limit",
        tuple(float(value) for value in optimal),
        max_iterations,
        max_abs_error,
        _relative_entropy(optimal, prior),
        tuple(float(value) for value in witness),
        "feasible problem did not reach the requested numerical tolerance",
    )


def largest_remainder_integerize(weights: Sequence[float]) -> list[int]:
    """Integerize with deterministic floor-plus-largest-remainder allocation."""

    array = np.asarray(weights, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError("weights must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise ValueError("weights must be finite")
    if np.any(array < 0):
        raise ValueError("weights must be non-negative")
    counts = np.floor(array).astype(np.int64)
    remainder = round(math.fsum(float(value) for value in array)) - int(counts.sum())
    if remainder:
        fractions = array - counts
        order = sorted(range(len(array)), key=lambda index: (-fractions[index], index))
        for index in order[:remainder]:
            counts[index] += 1
    return [int(value) for value in counts]


def build_calibration_oracle_comparison(
    fixtures: Sequence[LinkedCalibrationFixture] | None = None,
    *,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    """Compare the production linked updater with the independent oracle."""

    from synthpopcan.small_area_synthesis import _fit_joint_constraints

    selected = tuple(fixtures or generated_linked_calibration_fixtures())
    cases: list[dict[str, Any]] = []
    for fixture in selected:
        oracle = solve_relative_entropy_oracle(
            fixture.contributions,
            fixture.targets,
            fixture.initial_weights,
            tolerance=tolerance,
        )
        production_weights: np.ndarray | None = None
        production_error: str | None = None
        try:
            weights, converged, iterations, max_abs_error = _fit_joint_constraints(
                fixture.contributions,
                fixture.targets,
                initial_weights=fixture.initial_weights,
                max_iterations=2_000,
                tolerance=tolerance,
            )
            production_weights = weights
            production_status = "converged" if converged else "iteration_limit"
        except ValueError as exc:
            production_status = "rejected"
            production_error = str(exc)
            iterations = 0
            max_abs_error = None

        oracle_weights = (
            np.asarray(oracle.weights, dtype=float)
            if oracle.weights is not None
            else None
        )
        cases.append(
            {
                "name": fixture.name,
                "features": list(fixture.features),
                "candidate_households": fixture.contributions.shape[1],
                "constraints": fixture.contributions.shape[0],
                "expected_feasible": fixture.expected_feasible,
                "evidence_classification": (
                    "feasible" if oracle.status != "infeasible" else "infeasible"
                ),
                "oracle": {
                    "status": oracle.status,
                    "iterations": oracle.iterations,
                    "max_abs_error": _rounded(oracle.max_abs_error),
                    "relative_entropy": _rounded(oracle.relative_entropy),
                    "weight_metrics": _weight_metrics(
                        oracle_weights, fixture.initial_weights
                    ),
                    "message": oracle.message,
                },
                "production": {
                    "status": production_status,
                    "iterations": iterations,
                    "max_abs_error": _rounded(max_abs_error),
                    "relative_entropy": _rounded(
                        _relative_entropy(production_weights, fixture.initial_weights)
                        if production_weights is not None
                        else None
                    ),
                    "weight_metrics": _weight_metrics(
                        production_weights, fixture.initial_weights
                    ),
                    "error": production_error,
                },
                "comparison": {
                    "feasibility_matches_expectation": (
                        (oracle.status != "infeasible") == fixture.expected_feasible
                    ),
                    "both_meet_controls": bool(
                        oracle.status == "optimal" and production_status == "converged"
                    ),
                    "oracle_objective_no_worse": bool(
                        oracle.relative_entropy is not None
                        and production_weights is not None
                        and oracle.relative_entropy
                        <= _relative_entropy(
                            production_weights, fixture.initial_weights
                        )
                        + 1e-7
                    ),
                },
            }
        )

    return {
        "oracle_backend": CALIBRATION_ORACLE_BACKEND,
        "production_backend": "linked-multiplicative-updater-v1",
        "applicability": {
            "maximum_candidate_households": _MAX_ORACLE_CANDIDATES,
            "maximum_constraints": _MAX_ORACLE_CONSTRAINTS,
            "contribution_domain": "finite non-negative household contributions",
            "initial_weight_domain": "finite non-negative candidate weights",
            "purpose": "bounded independent evidence; not a production backend",
        },
        "cases": cases,
    }


def build_integerization_comparison() -> dict[str, Any]:
    """Compare systematic integerization with deterministic largest remainder."""

    cases = _integerization_cases()
    comparisons: list[dict[str, Any]] = []
    for name, weights, contributions, targets in cases:
        systematic = integerize_weights(weights.tolist())
        largest_remainder = largest_remainder_integerize(weights.tolist())
        fractional_total = math.fsum(float(weight) for weight in weights)
        comparisons.append(
            {
                "name": name,
                "candidate_households": len(weights),
                "fractional_total": _rounded(fractional_total),
                "rounded_total": round(fractional_total),
                "systematic": _integerization_metrics(
                    systematic, weights, contributions, targets
                ),
                "largest_remainder": _integerization_metrics(
                    largest_remainder, weights, contributions, targets
                ),
            }
        )
    return {
        "decision": INTEGERIZATION_BACKEND_DECISION,
        "cases": comparisons,
    }


def build_methodology_evidence() -> dict[str, Any]:
    """Build the deterministic machine-readable 0.9 methodological evidence."""

    return {
        "schema_version": METHODOLOGY_EVIDENCE_SCHEMA_VERSION,
        "calibration": build_calibration_oracle_comparison(),
        "integerization": build_integerization_comparison(),
    }


def _fixture(
    name: str,
    contributions: Sequence[Sequence[float]] | np.ndarray,
    targets: Sequence[float] | np.ndarray,
    initial_weights: Sequence[float] | np.ndarray,
    *,
    expected_feasible: bool = True,
    features: tuple[str, ...],
    known_weights: Sequence[float] | np.ndarray | None = None,
) -> LinkedCalibrationFixture:
    return LinkedCalibrationFixture(
        name=name,
        contributions=np.asarray(contributions, dtype=np.float64),
        targets=np.asarray(targets, dtype=np.float64),
        initial_weights=np.asarray(initial_weights, dtype=np.float64),
        expected_feasible=expected_feasible,
        features=features,
        known_feasible_weights=(
            np.asarray(known_weights, dtype=np.float64)
            if known_weights is not None
            else None
        ),
    )


def _fixture_from_known_weights(
    name: str,
    contributions: Sequence[Sequence[float]],
    known_weights: Sequence[float],
    initial_weights: Sequence[float],
    *,
    features: tuple[str, ...],
) -> LinkedCalibrationFixture:
    matrix = np.asarray(contributions, dtype=np.float64)
    known = np.asarray(known_weights, dtype=np.float64)
    return _fixture(
        name,
        matrix,
        _deterministic_matrix_vector_product(matrix, known),
        initial_weights,
        features=features,
        known_weights=known,
    )


def _deterministic_matrix_vector_product(
    matrix: np.ndarray, vector: np.ndarray
) -> np.ndarray:
    """Multiply in a fixed order without BLAS-dependent reductions."""

    return np.fromiter(
        (
            math.fsum(
                float(coefficient) * float(value)
                for coefficient, value in zip(row, vector, strict=True)
            )
            for row in matrix
        ),
        dtype=np.float64,
        count=matrix.shape[0],
    )


def _validated_calibration_arrays(
    contributions: Sequence[Sequence[float]] | np.ndarray,
    targets: Sequence[float] | np.ndarray,
    initial_weights: Sequence[float] | np.ndarray,
    *,
    tolerance: float,
    max_iterations: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = np.asarray(contributions, dtype=np.float64)
    target_array = np.asarray(targets, dtype=np.float64)
    prior = np.asarray(initial_weights, dtype=np.float64)
    if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
        raise ValueError("contributions must be a non-empty two-dimensional array")
    if target_array.shape != (matrix.shape[0],):
        raise ValueError("targets must match the number of contribution rows")
    if prior.shape != (matrix.shape[1],):
        raise ValueError("initial weights must match the candidate households")
    if matrix.shape[1] > _MAX_ORACLE_CANDIDATES:
        raise ValueError(
            f"bounded oracle accepts at most {_MAX_ORACLE_CANDIDATES} candidates"
        )
    if matrix.shape[0] > _MAX_ORACLE_CONSTRAINTS:
        raise ValueError(
            f"bounded oracle accepts at most {_MAX_ORACLE_CONSTRAINTS} constraints"
        )
    if not np.all(np.isfinite(matrix)) or np.any(matrix < 0):
        raise ValueError("contributions must be finite and non-negative")
    if not np.all(np.isfinite(target_array)) or np.any(target_array < 0):
        raise ValueError("targets must be finite and non-negative")
    if not np.all(np.isfinite(prior)) or np.any(prior < 0):
        raise ValueError("initial weights must be finite and non-negative")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be finite and positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    return matrix, target_array, prior


def _nonnegative_feasibility_witness(
    matrix: np.ndarray, targets: np.ndarray, *, tolerance: float
) -> np.ndarray | None:
    candidate_count = matrix.shape[1]
    if not candidate_count:
        return None
    scaled_tolerance = tolerance * max(1.0, float(np.max(np.abs(targets))))
    max_subset = min(matrix.shape[0], candidate_count)
    for subset_size in range(1, max_subset + 1):
        for subset in itertools.combinations(range(candidate_count), subset_size):
            selected = matrix[:, subset]
            solution = np.linalg.lstsq(selected, targets, rcond=None)[0]
            if np.any(solution < -scaled_tolerance):
                continue
            clipped = np.maximum(solution, 0.0)
            if (
                _maximum_absolute_control_error(selected, clipped, targets)
                > scaled_tolerance
            ):
                continue
            witness = np.zeros(candidate_count, dtype=float)
            witness[list(subset)] = clipped
            return witness
    return None


def _independent_constraint_basis(
    matrix: np.ndarray, targets: np.ndarray, *, tolerance: float
) -> tuple[np.ndarray, np.ndarray]:
    """Select a canonical full-rank subset of the original constraint rows.

    Singular vectors are not a canonical basis: their signs, and their
    orientation within repeated singular-value subspaces, may vary between
    LAPACK implementations.  Feeding those vectors into the Newton iteration
    made the last reported evidence digits platform-dependent.  Input-order
    Gaussian elimination gives the bounded oracle a stable basis while
    preserving the original constraint equations.
    """

    scale = max(float(np.max(np.abs(matrix))), 1.0)
    threshold = tolerance * max(matrix.shape) * scale
    echelon_rows: list[np.ndarray] = []
    pivot_columns: list[int] = []
    selected_rows: list[int] = []

    for row_index, row in enumerate(matrix):
        residual = row.copy()
        for pivot_column, echelon_row in zip(pivot_columns, echelon_rows, strict=True):
            residual -= residual[pivot_column] * echelon_row

        pivot_candidates = np.flatnonzero(np.abs(residual) > threshold)
        if not pivot_candidates.size:
            continue
        pivot_column = int(pivot_candidates[0])
        residual /= residual[pivot_column]
        residual[np.abs(residual) <= threshold] = 0.0
        pivot_columns.append(pivot_column)
        echelon_rows.append(residual)
        selected_rows.append(row_index)

    return matrix[selected_rows], targets[selected_rows]


def _dual_objective(
    multipliers: np.ndarray,
    matrix: np.ndarray,
    targets: np.ndarray,
    prior: np.ndarray,
) -> float:
    exponent = np.clip(
        _deterministic_matrix_vector_product(matrix.T, multipliers),
        -700.0,
        700.0,
    )
    exponential_sum = math.fsum(
        float(weight) * math.exp(float(value))
        for weight, value in zip(prior, exponent, strict=True)
    )
    target_product = math.fsum(
        float(target) * float(multiplier)
        for target, multiplier in zip(targets, multipliers, strict=True)
    )
    return exponential_sum - target_product


def _deterministic_weighted_crossproduct(
    matrix: np.ndarray, weights: np.ndarray
) -> np.ndarray:
    row_count, column_count = matrix.shape
    result = np.empty((row_count, row_count), dtype=np.float64)
    for left_index in range(row_count):
        for right_index in range(left_index, row_count):
            value = math.fsum(
                float(matrix[left_index, column_index])
                * float(weights[column_index])
                * float(matrix[right_index, column_index])
                for column_index in range(column_count)
            )
            result[left_index, right_index] = value
            result[right_index, left_index] = value
    return result


def _solve_linear_system(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    """Solve a small full-rank system with fixed-order Gaussian elimination."""

    size = matrix.shape[0]
    rows = [[float(value) for value in row] for row in matrix]
    values = [float(value) for value in vector]

    for column in range(size):
        pivot_row = max(
            range(column, size),
            key=lambda row_index: abs(rows[row_index][column]),
        )
        if rows[pivot_row][column] == 0.0:
            raise ValueError("independent constraint basis produced a singular Hessian")
        if pivot_row != column:
            rows[column], rows[pivot_row] = rows[pivot_row], rows[column]
            values[column], values[pivot_row] = values[pivot_row], values[column]

        for row_index in range(column + 1, size):
            factor = rows[row_index][column] / rows[column][column]
            rows[row_index][column] = 0.0
            for entry_index in range(column + 1, size):
                rows[row_index][entry_index] -= factor * rows[column][entry_index]
            values[row_index] -= factor * values[column]

    solution = [0.0] * size
    for row_index in range(size - 1, -1, -1):
        tail = math.fsum(
            rows[row_index][column] * solution[column]
            for column in range(row_index + 1, size)
        )
        solution[row_index] = (values[row_index] - tail) / rows[row_index][row_index]
    return np.asarray(solution, dtype=np.float64)


def _maximum_absolute_control_error(
    matrix: np.ndarray, weights: np.ndarray, targets: np.ndarray
) -> float:
    residuals = _deterministic_matrix_vector_product(matrix, weights) - targets
    return max(abs(float(value)) for value in residuals)


def _relative_entropy(weights: np.ndarray | None, prior: np.ndarray) -> float:
    if weights is None:
        return float("nan")
    positive = weights > 0
    if np.any(positive & (prior <= 0)):
        return float("inf")
    return math.fsum(
        (
            float(weight) * math.log(float(weight) / float(initial_weight))
            - float(weight)
            + float(initial_weight)
            if weight > 0
            else float(initial_weight)
        )
        for weight, initial_weight in zip(weights, prior, strict=True)
    )


def _weight_metrics(
    weights: np.ndarray | None, initial_weights: np.ndarray
) -> dict[str, float | int | None] | None:
    if weights is None:
        return None
    total = math.fsum(float(weight) for weight in weights)
    squares = math.fsum(float(weight) * float(weight) for weight in weights)
    return {
        "minimum": _rounded(float(np.min(weights))),
        "maximum": _rounded(float(np.max(weights))),
        "total": _rounded(total),
        "maximum_share": _rounded(float(np.max(weights)) / total if total else 0.0),
        "effective_sample_size": _rounded(total * total / squares if squares else 0.0),
        "positive_candidates": int(np.count_nonzero(weights > 0)),
        "l1_distance_from_initial": _rounded(
            math.fsum(
                abs(float(weight) - float(initial_weight))
                for weight, initial_weight in zip(weights, initial_weights, strict=True)
            )
        ),
    }


def _integerization_cases() -> tuple[
    tuple[str, np.ndarray, np.ndarray, np.ndarray], ...
]:
    balanced_weights = np.full(10, 0.2, dtype=float)
    balanced_contributions = np.asarray(
        [[1.0] * 5 + [0.0] * 5, [0.0] * 5 + [1.0] * 5], dtype=float
    )
    linked_weights = np.asarray([0.6, 1.4, 0.8, 1.2], dtype=float)
    linked_contributions = np.asarray(
        [[1, 1, 1, 1], [2, 0, 1, 3], [0, 2, 2, 1]], dtype=float
    )
    sparse_weights = np.asarray([0.0, 0.49, 0.51, 1.2, 0.8], dtype=float)
    sparse_contributions = np.asarray(
        [[1, 1, 1, 1, 1], [0, 0, 1, 0, 0], [0, 2, 0, 1, 3]], dtype=float
    )
    return (
        (
            "balanced_subunit_pool",
            balanced_weights,
            balanced_contributions,
            _deterministic_matrix_vector_product(
                balanced_contributions, balanced_weights
            ),
        ),
        (
            "linked_person_contributions",
            linked_weights,
            linked_contributions,
            _deterministic_matrix_vector_product(linked_contributions, linked_weights),
        ),
        (
            "sparse_structural_zero",
            sparse_weights,
            sparse_contributions,
            _deterministic_matrix_vector_product(sparse_contributions, sparse_weights),
        ),
    )


def _integerization_metrics(
    counts: Sequence[int],
    weights: np.ndarray,
    contributions: np.ndarray,
    targets: np.ndarray,
) -> dict[str, Any]:
    count_array = np.asarray(counts, dtype=float)
    residuals = (
        _deterministic_matrix_vector_product(contributions, count_array) - targets
    )
    positive_weight = weights > 0
    retained_positive = int(np.count_nonzero((count_array > 0) & positive_weight))
    return {
        "counts": [int(value) for value in counts],
        "total": int(sum(counts)),
        "max_abs_control_residual": _rounded(float(np.max(np.abs(residuals)))),
        "sum_abs_control_residual": _rounded(
            math.fsum(abs(float(residual)) for residual in residuals)
        ),
        "selected_candidates": int(np.count_nonzero(count_array)),
        "maximum_expansion": int(np.max(count_array)) if len(count_array) else 0,
        "positive_weight_candidates_retained": retained_positive,
        "positive_weight_candidate_recall": _rounded(
            retained_positive / int(np.count_nonzero(positive_weight))
            if np.any(positive_weight)
            else 1.0
        ),
        "structural_zeros_preserved": bool(np.all(count_array[~positive_weight] == 0)),
    }


def _rounded(value: float | None, digits: int = 10) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)
