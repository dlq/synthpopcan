"""Explicit rounded-zero CLI fitting retains targets and surfaces residuals."""

from __future__ import annotations

import json

from click.testing import CliRunner

from synthpopcan.cli import cli
from synthpopcan.linked_schema import build_linked_population_contract


def _inputs(tmp_path):
    source = tmp_path / "candidates"
    source.mkdir()
    hh, pp = source / "households.csv", source / "persons.csv"
    hh.write_text("synthetic_household_id,household_size\nh1,1\nh2,1\n")
    pp.write_text(
        "synthetic_person_id,synthetic_household_id,group,flag\n"
        "p1,h1,A,yes\np2,h2,B,no\n"
    )
    (source / "manifest.json").write_text(
        json.dumps(build_linked_population_contract(hh, pp))
    )
    household, person = tmp_path / "hh-controls.csv", tmp_path / "pp-controls.csv"
    household.write_text(
        'margin,dimensions,ada,household_size,count\nsize,"ada,household_size",24010001,1,10\n'
    )
    person.write_text(
        'margin,dimensions,ada,group,flag,count\ngroup,"ada,group",24010001,A,,10\ngroup,"ada,group",24010001,B,,0\nflag,"ada,flag",24010001,,yes,0\nflag,"ada,flag",24010001,,no,10\n'
    )
    return source, household, person


def test_observed_cli_reports_approximation_and_keeps_targets(tmp_path):
    source, household, person = _inputs(tmp_path)
    original = household.read_bytes(), person.read_bytes()
    output = tmp_path / "observed"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(source),
            "--controls",
            str(household),
            "--person-controls",
            str(person),
            "--geo-dimension",
            "ada",
            "--zero-target-policy",
            "observed",
            "--workers",
            "1",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Approximate control fitting was used in 1" in result.output
    assert "did not converge" in result.output
    report = json.loads((output / "report.json").read_text())
    assert report["assigned_households"] == report["assigned_persons"] == 10
    assert report["summary"]["non_converged_count"] == 1
    assert report["zero_target_policy"]["effective_counts"]["observed"] == 1
    assert (
        report["geographies"]["24010001"]["joint_solver"]["controls_converged"] is False
    )
    assert (household.read_bytes(), person.read_bytes()) == original


def test_structural_default_still_rejects_incompatible_zero_support(tmp_path):
    source, household, person = _inputs(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(source),
            "--controls",
            str(household),
            "--person-controls",
            str(person),
            "--geo-dimension",
            "ada",
            "--workers",
            "1",
            "--out",
            str(tmp_path / "strict"),
        ],
    )
    assert result.exit_code == 1
    assert "24010001" in result.output
    assert "no household support" in result.output


def test_observed_cli_requires_linked_person_controls(tmp_path):
    source, household, _person = _inputs(tmp_path)
    output = tmp_path / "invalid"
    result = CliRunner().invoke(
        cli,
        [
            "geo",
            "calibrate",
            str(source),
            "--controls",
            str(household),
            "--geo-dimension",
            "ada",
            "--zero-target-policy",
            "observed",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 2
    assert "requires --person-controls" in result.output
    assert not output.exists()


def test_completion_summary_separates_fractional_and_realized_fit(capsys, tmp_path):
    from synthpopcan.cli_geo import _print_calibration_completion

    _print_calibration_completion(
        {
            "summary": {"converged_count": 1021, "non_converged_count": 117},
            "prepared_control_plan": {
                "target_households": 3748989,
                "target_persons": 8308305,
            },
            "assigned_households": 3752983,
            "assigned_persons": 8309573,
            "realized_control_audit": {
                "matched_exactly": 3547,
                "control_cells": 50882,
                "max_abs_error": 342.0,
            },
        },
        tmp_path / "report.json",
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Exit status 0 means completion, not exact calibration" in captured.err
    assert (
        "1,021/1,138 fractional area fits converged; 117 did not converge"
        in captured.err
    )
    assert "difference +3,994" in captured.err
    assert "difference +1,268" in captured.err
    assert "3,547/50,882 cells match exactly" in captured.err


def test_completed_fractional_fit_does_not_claim_exact_integer_fit(capsys, tmp_path):
    from synthpopcan.cli_geo import _print_calibration_completion

    _print_calibration_completion(
        {
            "summary": {"converged_count": 1, "non_converged_count": 0},
            "prepared_control_plan": {"target_households": 10, "target_persons": 0},
            "assigned_households": 9,
            "assigned_persons": 0,
        },
        tmp_path / "report.json",
    )
    message = capsys.readouterr().err
    assert "1/1 fractional area fits converged" in message
    assert "difference -1" in message
    assert "difference +0" in message
    assert "not exact calibration" in message


def test_exclusion_warning_reports_known_gap_and_unknown_counts(capsys, tmp_path):
    from synthpopcan.cli_geo_prepare import _print_exclusion_warning

    _print_exclusion_warning(
        {
            "excluded_geographies": [{"ada": "a"}, {"ada": "b"}],
            "coverage": {
                "eligible_geographies": 3,
                "selected_geographies": 5,
                "known_excluded_households": 46,
                "unavailable_household_geographies": ["b"],
            },
        },
        tmp_path,
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "excluded 2 geographies" in captured.err
    assert "46 known households omitted" in captured.err
    assert "areas with unknown household counts: 1 (not zero)" in captured.err
    assert str(tmp_path / "plan.json") in captured.err


def test_no_exclusions_produce_no_warning(capsys, tmp_path):
    from synthpopcan.cli_geo_prepare import _print_exclusion_warning

    _print_exclusion_warning({"excluded_geographies": []}, tmp_path)
    assert capsys.readouterr().err == ""
