"""Independent reconciliation checks for emitted small-area artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from synthpopcan.small_area_synthesis import calibrate_linked_household_csvs


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _run_household_calibration(
    root: Path,
    *,
    n_workers: int,
    pool_size: int | None = None,
    subsample_seed: int = 42,
) -> dict[str, Path]:
    root.mkdir()
    households = root / "households-in.csv"
    persons = root / "persons-in.csv"
    controls = root / "controls.csv"
    households_out = root / "households.csv"
    persons_out = root / "persons.csv"
    weights_out = root / "weights.csv"
    report_out = root / "report.json"

    households.write_text(
        "synthetic_household_id,household_size,TENUR\n"
        "h1,1,owner\n"
        "h2,1,renter\n"
        "h3,2,owner\n"
        "h4,2,renter\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h3,adult\n"
        "p4,h3,child\n"
        "p5,h4,adult\n"
        "p6,h4,child\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",G1,1,3\n'
        'size,"tract,household_size",G1,2,1\n'
        'size,"tract,household_size",G2,1,1\n'
        'size,"tract,household_size",G2,2,3\n'
    )

    calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=households_out,
        persons_out=persons_out,
        weights_out=weights_out,
        report_out=report_out,
        tolerance=1e-9,
        n_workers=n_workers,
        pool_size=pool_size,
        subsample_seed=subsample_seed,
    )
    return {
        "households": households_out,
        "persons": persons_out,
        "weights": weights_out,
        "report": report_out,
    }


def test_emitted_small_area_artifacts_reconcile_independently_and_in_parallel(
    tmp_path: Path,
) -> None:
    serial = _run_household_calibration(tmp_path / "serial", n_workers=1)
    parallel = _run_household_calibration(tmp_path / "parallel", n_workers=4)

    for artifact in ("households", "persons", "weights", "report"):
        assert serial[artifact].read_bytes() == parallel[artifact].read_bytes()

    households = _read_rows(serial["households"])
    persons = _read_rows(serial["persons"])
    report = json.loads(serial["report"].read_text())

    independently_aggregated = Counter(
        (row["tract"], row["household_size"]) for row in households
    )
    assert independently_aggregated == {
        ("G1", "1"): 3,
        ("G1", "2"): 1,
        ("G2", "1"): 1,
        ("G2", "2"): 3,
    }
    assert Counter(row["tract"] for row in households) == {"G1": 4, "G2": 4}
    assert report["assigned_households"] == len(households) == 8
    assert report["assigned_persons"] == len(persons)

    households_by_id = {row["synthetic_household_id"]: row for row in households}
    assert len(households_by_id) == len(households)
    assert len({row["synthetic_person_id"] for row in persons}) == len(persons)
    for person in persons:
        household = households_by_id[person["synthetic_household_id"]]
        assert person["tract"] == household["tract"]

    realized_summary_by_geography = {
        geography: details["realized_margin_summaries"][0]
        for geography, details in report["geographies"].items()
    }
    assert report["summary"]["realized_max_abs_error"] == 0.0
    for geography, summary in realized_summary_by_geography.items():
        independently_assigned = sum(
            count
            for (row_geography, _size), count in independently_aggregated.items()
            if row_geography == geography
        )
        assert summary["target_total"] == 4.0
        assert summary["fitted_total"] == independently_assigned
        assert summary["max_abs_error"] == 0.0


def test_joint_household_person_artifacts_reconcile_to_independent_oracle(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households-in.csv"
    persons = tmp_path / "persons-in.csv"
    household_controls = tmp_path / "household-controls.csv"
    person_controls = tmp_path / "person-controls.csv"
    households_out = tmp_path / "households.csv"
    persons_out = tmp_path / "persons.csv"
    report_out = tmp_path / "report.json"

    households.write_text("synthetic_household_id,household_size\nh1,1\nh2,2\nh3,2\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,AGEGRP\n"
        "p1,h1,adult\n"
        "p2,h2,adult\n"
        "p3,h2,child\n"
        "p4,h3,child\n"
        "p5,h3,child\n"
    )
    household_controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",G1,1,1\n'
        'size,"tract,household_size",G1,2,3\n'
        'size,"tract,household_size",G2,1,2\n'
        'size,"tract,household_size",G2,2,3\n'
    )
    person_controls.write_text(
        "margin,dimensions,tract,AGEGRP,count\n"
        'age,"tract,AGEGRP",G1,adult,3\n'
        'age,"tract,AGEGRP",G1,child,4\n'
        'age,"tract,AGEGRP",G2,adult,3\n'
        'age,"tract,AGEGRP",G2,child,5\n'
    )

    calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=household_controls,
        person_controls_path=person_controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=households_out,
        persons_out=persons_out,
        report_out=report_out,
        tolerance=1e-9,
        n_workers=2,
    )

    emitted_households = _read_rows(households_out)
    emitted_persons = _read_rows(persons_out)
    report = json.loads(report_out.read_text())
    household_totals = Counter(
        (row["tract"], row["household_size"]) for row in emitted_households
    )
    person_totals = Counter((row["tract"], row["AGEGRP"]) for row in emitted_persons)

    assert household_totals == {
        ("G1", "1"): 1,
        ("G1", "2"): 3,
        ("G2", "1"): 2,
        ("G2", "2"): 3,
    }
    assert person_totals == {
        ("G1", "adult"): 3,
        ("G1", "child"): 4,
        ("G2", "adult"): 3,
        ("G2", "child"): 5,
    }
    household_by_id = {row["synthetic_household_id"]: row for row in emitted_households}
    assert len(household_by_id) == len(emitted_households)
    for person in emitted_persons:
        assert (
            person["tract"]
            == household_by_id[person["synthetic_household_id"]]["tract"]
        )

    assert report["calibration_mode"] == "household_and_person"
    assert report["summary"]["max_abs_error"] <= 1e-9
    assert report["summary"]["realized_max_abs_error"] == 0.0
    for details in report["geographies"].values():
        summaries = {
            summary["unit"]: summary for summary in details["realized_margin_summaries"]
        }
        assert summaries["household"]["max_abs_error"] == 0.0
        assert summaries["person"]["max_abs_error"] == 0.0


def test_subsampled_artifacts_are_reproducible_and_reconcile_independently(
    tmp_path: Path,
) -> None:
    first = _run_household_calibration(
        tmp_path / "first", n_workers=1, pool_size=3, subsample_seed=7
    )
    second = _run_household_calibration(
        tmp_path / "second", n_workers=2, pool_size=3, subsample_seed=7
    )

    for artifact in ("households", "persons", "weights", "report"):
        assert first[artifact].read_bytes() == second[artifact].read_bytes()

    households = _read_rows(first["households"])
    report = json.loads(first["report"].read_text())
    assert Counter((row["tract"], row["household_size"]) for row in households) == {
        ("G1", "1"): 3,
        ("G1", "2"): 1,
        ("G2", "1"): 1,
        ("G2", "2"): 3,
    }
    assert report["subsample"] == {
        "applied": True,
        "pool_size": 3,
        "subsample_seed": 7,
        "input_households": 4,
        "input_persons": 6,
        "selected_households": 3,
        "selected_persons": 5,
    }
    assert report["summary"]["realized_max_abs_error"] == 0.0


def test_nonconverged_artifacts_report_independently_observed_residuals(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households-in.csv"
    persons = tmp_path / "persons-in.csv"
    controls = tmp_path / "controls.csv"
    households_out = tmp_path / "households.csv"
    persons_out = tmp_path / "persons.csv"
    report_out = tmp_path / "report.json"
    households.write_text(
        "synthetic_household_id,household_size,TENUR\nh1,1,owner\nh2,2,renter\n"
    )
    persons.write_text("synthetic_person_id,synthetic_household_id\np1,h1\np2,h2\n")
    controls.write_text(
        "margin,dimensions,tract,household_size,TENUR,count\n"
        'size,"tract,household_size",G1,1,,50\n'
        'size,"tract,household_size",G1,2,,50\n'
        'tenure,"tract,TENUR",G1,,owner,80\n'
        'tenure,"tract,TENUR",G1,,renter,20\n'
    )

    calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=households_out,
        persons_out=persons_out,
        report_out=report_out,
        max_iterations=2,
        tolerance=1e-9,
    )

    emitted = _read_rows(households_out)
    report = json.loads(report_out.read_text())
    observed_sizes = Counter(row["household_size"] for row in emitted)
    observed_tenure = Counter(row["TENUR"] for row in emitted)
    assert observed_sizes == {"1": 80, "2": 20}
    assert observed_tenure == {"owner": 80, "renter": 20}
    independently_observed_error = max(
        abs(observed_sizes[size] - 50) for size in ("1", "2")
    )
    assert independently_observed_error == 30
    assert report["summary"]["non_converged_geographies"] == ["G1"]
    assert report["summary"]["max_abs_error"] == independently_observed_error
    assert report["summary"]["realized_max_abs_error"] == independently_observed_error
