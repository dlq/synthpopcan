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
        "3,31,311,31101,1,35,renter,adult,M\n"
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

    assert summary["source"]["records"] == 4
    assert summary["source"]["households"] == 3
    assert summary["generation"]["households"] == 2
    assert summary["generation"]["persons"] >= 2
    assert summary["generation"]["average_household_size"] == round(
        summary["generation"]["persons"] / summary["generation"]["households"],
        4,
    )
    assert summary["linked_validation"]["passed"] is True
    assert summary["distribution_validation"]["training_household_records"] == 2
    assert summary["distribution_validation"]["training_person_records"] == 3
    assert summary["distribution_validation"]["training_average_household_size"] == 1.5
    assert "household_max_delta" in summary["distribution_validation"]
    assert "person_max_delta" in summary["distribution_validation"]
    assert summary["distribution_validation"]["household_warnings"] >= 0
    assert summary["distribution_validation"]["person_warnings"] >= 0
    assert summary["artifact_sizes_bytes"]["household_model"] > 0
    assert summary["artifact_sizes_bytes"]["person_model"] > 0
    assert summary["artifact_sizes_bytes"]["synthetic_households"] > 0
    assert summary["artifact_sizes_bytes"]["synthetic_persons"] > 0
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


def test_runs_linked_tree_benchmark_from_suggested_blocks(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    output_dir = tmp_path / "benchmark"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,DTYPE,ROOM,BEDRM,CONDO,"
        "PRESMORTG,VALUE,SHELCO,SUBSIDY,REPAIR,BUILT,AGEGRP,SEX,MarStH,IMMSTAT\n"
        "1,11,111,11101,1,24,owner,detached,6,3,no,yes,500000,1200,no,"
        "regular,1991,adult,F,married,non_immigrant\n"
        "1,11,111,11102,1,24,owner,detached,6,3,no,yes,500000,1200,no,"
        "regular,1991,child,M,never_married,non_immigrant\n"
        "2,21,211,21101,1,24,renter,apartment,4,2,yes,no,0,900,no,"
        "regular,2001,adult,F,single,immigrant\n"
        "3,31,311,31101,1,35,renter,row,5,2,no,no,0,850,yes,"
        "minor,1981,adult,M,married,non_immigrant\n"
    )

    summary = run_linked_tree_benchmark(
        source,
        output_dir=output_dir,
        household_target_columns=None,
        household_conditioning_columns=None,
        person_target_columns=None,
        person_conditioning_columns=None,
        household_block="household_core",
        person_block="person_demographics",
        households=2,
        conditions={"PR": "24"},
        random_seed=7,
    )

    assert summary["column_source"] == {
        "mode": "profile",
        "profile": "statcan-2016-hierarchical",
        "household_block": "household_core",
        "person_block": "person_demographics",
    }
    assert summary["training"]["household"]["target_columns"] == [
        "household_size",
        "TENUR",
        "DTYPE",
        "ROOM",
        "BEDRM",
        "CONDO",
        "PRESMORTG",
        "VALUE",
        "SHELCO",
        "SUBSIDY",
        "REPAIR",
        "BUILT",
    ]
    assert summary["training"]["person"]["target_columns"] == [
        "AGEGRP",
        "SEX",
        "MarStH",
        "IMMSTAT",
    ]

    with (output_dir / "synthetic-households.csv").open(newline="") as handle:
        household_rows = list(csv.DictReader(handle))
    with (output_dir / "synthetic-persons.csv").open(newline="") as handle:
        person_rows = list(csv.DictReader(handle))

    assert len(household_rows) == 2
    assert {"DTYPE", "ROOM", "BEDRM", "BUILT"}.issubset(household_rows[0])
    assert {"AGEGRP", "SEX", "MarStH", "IMMSTAT"}.issubset(person_rows[0])
