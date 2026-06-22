import csv
import json

from synthpopcan.tree_benchmark import run_linked_tree_benchmark


def test_runs_linked_tree_benchmark_fixture(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    output_dir = tmp_path / "benchmark"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,AGEGRP,SEX\n"
        "1,11,111,11101,1,24,owner,adult,F\n"
        "1,11,111,11102,1,24,owner,child,M\n"
        "2,21,211,21101,1,24,renter,adult,F\n"
    )

    summary = run_linked_tree_benchmark(
        source,
        output_dir=output_dir,
        household_target_columns=("household_size", "TENUR"),
        household_conditioning_columns=("PR",),
        person_target_columns=("AGEGRP", "SEX"),
        person_conditioning_columns=("PR", "household_size", "TENUR"),
        households=2,
        conditions={"PR": "24"},
        random_seed=7,
    )

    assert summary["source"]["records"] == 3
    assert summary["source"]["households"] == 2
    assert summary["generation"]["households"] == 2
    assert summary["generation"]["persons"] >= 2
    assert summary["linked_validation"]["passed"] is True
    assert summary["outputs"] == {
        "household_training": str(output_dir / "household-training.csv"),
        "person_training": str(output_dir / "person-training.csv"),
        "household_model": str(output_dir / "household-model.json"),
        "person_model": str(output_dir / "person-model.json"),
        "synthetic_households": str(output_dir / "synthetic-households.csv"),
        "synthetic_persons": str(output_dir / "synthetic-persons.csv"),
        "linked_validation": str(output_dir / "linked-validation.json"),
        "household_distribution_validation": str(
            output_dir / "household-distribution-validation.json"
        ),
        "person_distribution_validation": str(
            output_dir / "person-distribution-validation.json"
        ),
        "summary": str(output_dir / "benchmark-summary.json"),
    }

    with (output_dir / "synthetic-households.csv").open(newline="") as handle:
        household_rows = list(csv.DictReader(handle))
    with (output_dir / "synthetic-persons.csv").open(newline="") as handle:
        person_rows = list(csv.DictReader(handle))
    linked_report = json.loads((output_dir / "linked-validation.json").read_text())
    written_summary = json.loads((output_dir / "benchmark-summary.json").read_text())

    assert len(household_rows) == 2
    assert len(person_rows) == summary["generation"]["persons"]
    assert linked_report["passed"] is True
    assert written_summary["generation"] == summary["generation"]
