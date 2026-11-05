"""Observed zero controls retain source targets and disclose approximate fits."""

from __future__ import annotations

import copy
import csv
import json

import numpy as np
import pytest

from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
    write_control_table,
)
from synthpopcan.small_area_synthesis import (
    calibrate_linked_household_csvs,
    fit_linked_by_geography,
)


def _margin(name, dimension, values, geographies):
    return ControlMargin(
        name=name,
        dimensions=("ada", dimension),
        cells=tuple(
            ControlCell({"ada": geography, dimension: category}, target)
            for geography in geographies
            for category, target in values
        ),
    )


def _population(*, household_zero=False, repeat=1, geographies=("24990001",)):
    households, persons = [], []
    pattern = (3, 1, 0, 2) if repeat > 1 else (1, 1)
    for index, prior in enumerate(pattern * repeat):
        identifier = f"h{index}"
        present = index % len(pattern) != len(pattern) - 1
        households.append(
            {
                "synthetic_household_id": identifier,
                "household_size": "1",
                "kind": "present" if present else "absent",
                "prior": str(prior),
            }
        )
        persons.append(
            {
                "synthetic_household_id": identifier,
                "synthetic_person_id": f"p{index}",
                "zero_feature": "present" if present else "absent",
                "positive_feature": "needed" if present else "other",
            }
        )
    household_margins = [_margin("size", "household_size", [("1", 2)], geographies)]
    person_margins = [
        _margin(
            "positive", "positive_feature", [("needed", 1), ("other", 1)], geographies
        )
    ]
    zero = _margin(
        "zero",
        "kind" if household_zero else "zero_feature",
        [("present", 0), ("absent", 2)],
        geographies,
    )
    (household_margins if household_zero else person_margins).append(zero)
    household_controls = ControlTable(
        margins=tuple(household_margins), dimensions=("ada", "household_size", "kind")
    )
    person_controls = ControlTable(
        margins=tuple(person_margins),
        dimensions=("ada", "zero_feature", "positive_feature"),
    )
    return households, persons, household_controls, person_controls


@pytest.mark.parametrize("solver", ["ipu", "hybrid"])
def test_observed_policy_retains_incompatible_targets_and_reports_residuals(solver):
    inputs = _population()
    before = copy.deepcopy(inputs)
    with pytest.raises(ValueError, match="24990001.*structural-zero controls"):
        fit_linked_by_geography(*inputs, geography_dimension="ada", joint_solver=solver)

    result = fit_linked_by_geography(
        *inputs,
        geography_dimension="ada",
        joint_solver=solver,
        zero_target_policy="observed",
        max_iterations=100,
    )
    assert inputs == before
    weights = np.asarray(result.weights_by_geography["24990001"])
    assert np.all(np.isfinite(weights)) and np.all(weights > 0)
    assert weights.sum() == pytest.approx(2)
    report = result.reports["24990001"]
    assert report["converged"] is False
    assert report["zero_target_policy"] == {
        "requested": "observed",
        "effective": "observed",
    }
    assert report["joint_solver"]["method"] == "observed_entropy_least_squares"
    zero_cell = next(
        margin for margin in report["margins"] if margin["name"] == "zero"
    )["cells"][0]
    assert zero_cell["target"] == 0
    assert zero_cell["fitted"] > 0
    assert zero_cell["residual"] == zero_cell["fitted"]
    assert report["realized"]["margins"][-1]["cells"][0]["target"] == 0


def test_observed_fallback_recovers_original_prior_and_preserves_group_proportions():
    inputs = _population(
        household_zero=True, repeat=150, geographies=("24990001", "24990002")
    )
    before = copy.deepcopy(inputs)
    results = [
        fit_linked_by_geography(
            *inputs,
            geography_dimension="ada",
            weight_field="prior",
            zero_target_policy="observed",
            n_workers=workers,
            max_iterations=100,
        )
        for workers in (1, 2)
    ]
    assert inputs == before
    assert results[0] == results[1]
    result = results[0]
    assert (
        result.weights_by_geography["24990001"]
        == result.weights_by_geography["24990002"]
    )
    weights = np.asarray(result.weights_by_geography["24990001"])
    assert weights.sum() == pytest.approx(2)
    assert np.all(weights[2::4] == 0)
    assert np.all(weights[0::4] > 0)
    assert weights[0::4] == pytest.approx(3 * weights[1::4], rel=1e-12)
    assert result.reports["24990001"]["joint_solver"]["control_profiles"] == 2
    stage_zero = result.reports["24990001"]["household_stage"]["margins"][-1]["cells"][
        0
    ]
    assert stage_zero["fitted"] == 0


def test_observed_policy_uses_unchanged_strict_fit_when_feasible():
    households, persons, household_controls, _person_controls = _population()
    controls = ControlTable(
        margins=(
            _margin(
                "positive",
                "positive_feature",
                [("needed", 1), ("other", 1)],
                ("24990001",),
            ),
        ),
        dimensions=("ada", "positive_feature"),
    )
    args = households, persons, household_controls, controls
    default = fit_linked_by_geography(*args, geography_dimension="ada")
    explicit = fit_linked_by_geography(
        *args, geography_dimension="ada", zero_target_policy="structural"
    )
    observed = fit_linked_by_geography(
        *args, geography_dimension="ada", zero_target_policy="observed"
    )
    assert default == explicit
    assert default.weights_by_geography == observed.weights_by_geography
    observed_report = copy.deepcopy(observed.reports["24990001"])
    assert observed_report.pop("zero_target_policy") == {
        "requested": "observed",
        "effective": "structural",
    }
    assert observed_report == default.reports["24990001"]


def test_observed_policy_does_not_hide_other_domain_errors():
    with pytest.raises(ValueError, match="24990001.*joint_solver must"):
        fit_linked_by_geography(
            *_population(),
            geography_dimension="ada",
            zero_target_policy="observed",
            joint_solver="invalid",
        )
    with pytest.raises(ValueError, match="zero_target_policy must"):
        fit_linked_by_geography(
            *_population(), geography_dimension="ada", zero_target_policy="invalid"
        )


def test_csv_entry_propagates_observed_policy_and_preserves_control_files(tmp_path):
    households, persons, household_controls, person_controls = _population()
    for filename, rows in (("households", households), ("persons", persons)):
        with (tmp_path / f"{filename}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    for filename, controls in (
        ("hh-controls", household_controls),
        ("pp-controls", person_controls),
    ):
        write_control_table(tmp_path / f"{filename}.csv", controls)
    before = [(tmp_path / f"{name}-controls.csv").read_bytes() for name in ("hh", "pp")]
    summary = calibrate_linked_household_csvs(
        households_path=tmp_path / "households.csv",
        persons_path=tmp_path / "persons.csv",
        controls_path=tmp_path / "hh-controls.csv",
        person_controls_path=tmp_path / "pp-controls.csv",
        geography_dimension="ada",
        geography_column="ada",
        households_out=tmp_path / "assigned-households.csv",
        persons_out=tmp_path / "assigned-persons.csv",
        report_out=tmp_path / "report.json",
        zero_target_policy="observed",
    )
    assert before == [
        (tmp_path / f"{name}-controls.csv").read_bytes() for name in ("hh", "pp")
    ]
    assert summary["assigned_households"] == 2
    assert summary["summary"]["non_converged_count"] == 1
    assert summary["zero_target_policy"] == {
        "requested": "observed",
        "effective_counts": {"structural": 0, "observed": 1},
    }
    report = json.loads((tmp_path / "report.json").read_text())
    assert (
        report["geographies"]["24990001"]["zero_target_policy"]["effective"]
        == "observed"
    )


def test_observed_csv_policy_requires_person_controls(tmp_path):
    with pytest.raises(ValueError, match="requires person_controls_path"):
        calibrate_linked_household_csvs(
            households_path=tmp_path / "unused",
            persons_path=tmp_path / "unused",
            controls_path=tmp_path / "unused",
            geography_dimension="ada",
            geography_column="ada",
            households_out=tmp_path / "unused",
            persons_out=tmp_path / "unused",
            zero_target_policy="observed",
        )


@pytest.mark.parametrize("maximum,strict_iterations", [(16, 16), (3000, 300)])
def test_observed_stagnation_keeps_targets_and_improves_conflicting_cells(
    maximum, strict_iterations
):
    from synthpopcan._joint_calibration import JointCalibrationSystem
    from synthpopcan.small_area_synthesis import _fit_linked_system_with_zero_policy

    matrix = np.array([[1.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 0.0, 1.0]])
    targets = np.array([10.0, 2.0, 8.0])
    prior = np.array([1.0, 1.0, 0.0])
    original = targets.copy()
    system = JointCalibrationSystem.build(matrix)

    def run(policy):
        return _fit_linked_system_with_zero_policy(
            system,
            targets,
            prior,
            max_iterations=maximum,
            tolerance=0.01,
            solver="ipu",
            zero_target_policy=policy,
            original_prior=prior,
            household_total=10.0,
        )

    strict, observed = run("structural"), run("observed")
    assert not observed[1]
    assert observed[0].sum() == pytest.approx(10.0)
    assert observed[0][2] == 0
    assert observed[3] < strict[3]
    assert observed[4]["strict_iterations"] == strict_iterations
    assert observed[4]["strict_iteration_budget"] == maximum
    assert observed[4]["optimizer_max_iterations"] == 100
    assert ("stagnated" in observed[4]["fallback_reason"]) is (maximum == 3000)
    np.testing.assert_array_equal(targets, original)


@pytest.mark.parametrize("maximum", [200, 3000])
def test_moving_strict_fit_keeps_remaining_budget_and_reports_total(maximum):
    from types import SimpleNamespace

    from synthpopcan.small_area_synthesis import _observed_strict_attempt

    budgets = []

    def moving(targets, initial, **kwargs):
        budgets.append(kwargs["max_iterations"])
        return (
            np.array([float(len(budgets))]),
            len(budgets) == 3,
            budgets[-1],
            1.0,
            {"requested": kwargs["solver"]},
        )

    result, reason, spent = _observed_strict_attempt(
        SimpleNamespace(fit=moving),
        np.array([1.0]),
        np.array([0.0]),
        maximum,
        0.01,
        "hybrid",
        True,
    )
    assert sum(budgets) == maximum
    assert spent == result[2] == maximum
    assert result[4]["requested"] == "hybrid"
    assert result[1] is (maximum == 3000)
    assert "stagnated" not in reason
