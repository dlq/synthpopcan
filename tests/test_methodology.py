import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from synthpopcan.methodology import (
    CALIBRATION_ORACLE_BACKEND,
    INTEGERIZATION_BACKEND_DECISION,
    METHODOLOGY_EVIDENCE_SCHEMA_VERSION,
    _independent_constraint_basis,
    build_calibration_oracle_comparison,
    build_integerization_comparison,
    build_methodology_evidence,
    generated_linked_calibration_fixtures,
    largest_remainder_integerize,
    solve_relative_entropy_oracle,
)

ROOT = Path(__file__).parents[1]
PUBLISHED_EVIDENCE = ROOT / "docs" / "_static" / "methodology-evidence-v1.json"
SCRIPT = ROOT / "scripts" / "build_methodology_evidence.py"
SPEC = importlib.util.spec_from_file_location("build_methodology_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SCRIPT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT_MODULE)
render_evidence = SCRIPT_MODULE.render_evidence


def test_generated_feasible_fixture_targets_come_from_known_weights() -> None:
    fixtures = generated_linked_calibration_fixtures(seed=17, generated_cases=5)
    generated = [
        fixture for fixture in fixtures if fixture.name.startswith("generated_")
    ]

    assert len(generated) == 5
    for fixture in generated:
        assert fixture.expected_feasible is True
        assert fixture.known_feasible_weights is not None
        assert fixture.targets == pytest.approx(
            fixture.contributions @ fixture.known_feasible_weights
        )
        assert np.max(fixture.contributions) > 1
        assert "zero_target" in fixture.features
        assert fixture.targets[-1] == 0


def test_generated_fixture_targets_use_platform_independent_reductions() -> None:
    fixture = next(
        fixture
        for fixture in generated_linked_calibration_fixtures()
        if fixture.name == "generated_02"
    )
    assert fixture.known_feasible_weights is not None

    expected = np.fromiter(
        (
            math.fsum(
                float(coefficient) * float(weight)
                for coefficient, weight in zip(
                    row, fixture.known_feasible_weights, strict=True
                )
            )
            for row in fixture.contributions
        ),
        dtype=np.float64,
    )

    np.testing.assert_array_equal(fixture.targets, expected)
    assert fixture.targets[2].hex() == "0x1.76eef48c61663p+2"
    assert fixture.targets[3].hex() == "0x1.4ac3a0a008251p+4"


def test_constraint_basis_selects_original_rows_in_input_order() -> None:
    matrix = np.asarray(
        [
            [1, 1, 1, 1],
            [1, 1, 0, 0],
            [0, 0, 1, 1],
            [0, 1, 0, 0],
        ],
        dtype=np.float64,
    )
    targets = np.asarray([6, 3, 3, 2], dtype=np.float64)

    basis, basis_targets = _independent_constraint_basis(
        matrix, targets, tolerance=1e-8
    )

    np.testing.assert_array_equal(basis, matrix[[0, 1, 3]])
    np.testing.assert_array_equal(basis_targets, targets[[0, 1, 3]])


def test_fixture_catalog_covers_methodological_edge_cases() -> None:
    fixtures = generated_linked_calibration_fixtures()
    features = {feature for fixture in fixtures for feature in fixture.features}

    assert {
        "analytical",
        "linked_person_counts_greater_than_one",
        "sparse_category",
        "rare_category",
        "redundant_constraints",
        "linearly_dependent_constraints",
        "nearly_dependent_constraints",
        "zero_target",
        "unsupported_positive_target",
        "non_uniform_initial_weights",
    } <= features


def test_relative_entropy_oracle_solves_analytical_case_exactly() -> None:
    fixture = generated_linked_calibration_fixtures(generated_cases=0)[0]

    result = solve_relative_entropy_oracle(
        fixture.contributions,
        fixture.targets,
        fixture.initial_weights,
    )

    assert result.backend == CALIBRATION_ORACLE_BACKEND
    assert result.status == "optimal"
    assert result.weights == pytest.approx([2.0, 3.0, 1.5], abs=1e-9)
    assert result.max_abs_error is not None and result.max_abs_error <= 1e-9
    assert result.relative_entropy == pytest.approx(1.7903288892807479)
    assert result.feasibility_witness is not None


def test_oracle_classifies_all_declared_fixture_feasibility() -> None:
    for fixture in generated_linked_calibration_fixtures():
        result = solve_relative_entropy_oracle(
            fixture.contributions,
            fixture.targets,
            fixture.initial_weights,
            tolerance=1e-8,
        )

        assert (result.status != "infeasible") is fixture.expected_feasible
        if fixture.expected_feasible:
            assert result.status == "optimal"
            assert result.weights is not None
            assert result.max_abs_error is not None
            assert result.max_abs_error <= 1e-8
        else:
            assert result.status == "infeasible"
            assert result.weights is None
            assert result.max_abs_error is None


def test_oracle_respects_initial_weight_and_structural_zero_support() -> None:
    result = solve_relative_entropy_oracle(
        [[1, 0, 0], [0, 1, 0]],
        [1, 0],
        [1, 2, 0],
    )

    assert result.status == "optimal"
    assert result.weights == pytest.approx([1, 0, 0])

    unsupported = solve_relative_entropy_oracle([[0, 1]], [1], [1, 0])
    assert unsupported.status == "infeasible"


def test_oracle_keeps_unconstrained_prior_on_all_zero_problem() -> None:
    result = solve_relative_entropy_oracle(
        [[1, 0, 0]],
        [0],
        [2, 3, 4],
    )

    assert result.status == "optimal"
    assert result.iterations == 0
    assert result.weights == pytest.approx([0, 3, 4])
    assert result.max_abs_error == 0


def test_oracle_reports_iteration_limit_separately_from_infeasibility() -> None:
    result = solve_relative_entropy_oracle(
        [[1, 0], [0, 1]],
        [10, 20],
        [1, 1],
        max_iterations=1,
        tolerance=1e-15,
    )

    assert result.status == "iteration_limit"
    assert result.weights is not None
    assert result.feasibility_witness is not None
    assert result.max_abs_error is not None and result.max_abs_error > 0


def test_oracle_accepts_a_solved_step_when_objective_rounding_masks_it() -> None:
    result = solve_relative_entropy_oracle(
        [[3, 0, 0, 3, 1, 2, 0, 0]],
        [10.50837462965823],
        [1] * 8,
        tolerance=1e-8,
        max_iterations=300,
    )

    assert result.status == "optimal"
    assert result.max_abs_error is not None
    assert result.max_abs_error <= 1e-8


@pytest.mark.parametrize(
    ("contributions", "targets", "initial", "kwargs", "message"),
    [
        ([], [], [], {}, "non-empty two-dimensional"),
        ([[1]], [1, 2], [1], {}, "targets must match"),
        ([[1, 0]], [1], [1], {}, "initial weights must match"),
        ([[float("nan")]], [1], [1], {}, "contributions must be finite"),
        ([[-1]], [1], [1], {}, "contributions must be finite"),
        ([[1]], [float("inf")], [1], {}, "targets must be finite"),
        ([[1]], [-1], [1], {}, "targets must be finite"),
        ([[1]], [1], [float("nan")], {}, "initial weights must be finite"),
        ([[1]], [1], [-1], {}, "initial weights must be finite"),
        ([[1]], [1], [1], {"tolerance": 0}, "tolerance must be finite"),
        ([[1]], [1], [1], {"max_iterations": 0}, "max_iterations must be"),
        (
            [[1] * 15],
            [1],
            [1] * 15,
            {},
            "at most 14 candidates",
        ),
        (
            [[1] for _ in range(21)],
            [1] * 21,
            [1],
            {},
            "at most 20 constraints",
        ),
    ],
)
def test_oracle_rejects_invalid_or_out_of_scope_inputs(
    contributions: list[list[float]],
    targets: list[float],
    initial: list[float],
    kwargs: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        solve_relative_entropy_oracle(contributions, targets, initial, **kwargs)


def test_production_comparison_meets_feasible_cases_and_names_infeasibility() -> None:
    report = build_calibration_oracle_comparison()
    cases = {case["name"]: case for case in report["cases"]}

    assert report["applicability"]["purpose"].endswith("not a production backend")
    assert all(
        case["comparison"]["both_meet_controls"]
        for case in cases.values()
        if case["expected_feasible"]
    )
    assert all(
        case["comparison"]["oracle_objective_no_worse"]
        for case in cases.values()
        if case["expected_feasible"]
    )
    inconsistent = cases["inconsistent_dependent_constraints"]
    assert inconsistent["evidence_classification"] == "infeasible"
    assert inconsistent["oracle"]["status"] == "infeasible"
    assert inconsistent["production"]["status"] == "iteration_limit"
    unsupported = cases["unsupported_positive_target"]
    assert unsupported["evidence_classification"] == "infeasible"
    assert unsupported["production"]["status"] == "rejected"


def test_largest_remainder_is_deterministic_and_preserves_total_and_zeros() -> None:
    weights = [0.0, 0.2, 0.2, 0.2, 1.4]

    counts = largest_remainder_integerize(weights)

    assert counts == [0, 0, 0, 0, 2]
    assert counts == largest_remainder_integerize(weights)
    assert sum(counts) == round(sum(weights))
    assert counts[0] == 0


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ([[1.0]], "one-dimensional"),
        ([float("nan")], "finite"),
        ([float("inf")], "finite"),
        ([-0.1], "non-negative"),
    ],
)
def test_largest_remainder_rejects_invalid_weights(
    weights: list[float] | list[list[float]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        largest_remainder_integerize(weights)  # type: ignore[arg-type]


def test_integerization_comparison_supports_retaining_systematic_backend() -> None:
    report = build_integerization_comparison()
    cases = {case["name"]: case for case in report["cases"]}

    assert report["decision"] == INTEGERIZATION_BACKEND_DECISION
    assert report["decision"]["decision"] == "retain"
    assert report["decision"]["production_backend"] == (
        "deterministic-systematic-midpoint-v1"
    )
    balanced = cases["balanced_subunit_pool"]
    assert balanced["systematic"]["max_abs_control_residual"] == 0
    assert balanced["largest_remainder"]["max_abs_control_residual"] == 1
    for case in cases.values():
        for backend in ("systematic", "largest_remainder"):
            assert case[backend]["total"] == case["rounded_total"]
            assert case[backend]["structural_zeros_preserved"] is True


def test_published_evidence_is_reproducible_and_matches_module_decision() -> None:
    evidence = build_methodology_evidence()
    published = json.loads(PUBLISHED_EVIDENCE.read_text())

    assert evidence["schema_version"] == METHODOLOGY_EVIDENCE_SCHEMA_VERSION
    assert published == evidence
    assert render_evidence(evidence) == PUBLISHED_EVIDENCE.read_text()
    assert published["integerization"]["decision"] == (INTEGERIZATION_BACKEND_DECISION)
