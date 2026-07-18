import csv
import json
from pathlib import Path

import click
import pytest

from synthpopcan.cli import main
from synthpopcan.microdata import (
    export_training_rows,
    inspect_statcan_microdata,
    read_statcan_2021_hierarchical_seed_sample,
    read_statcan_2021_individual_seed_sample,
    read_statcan_hierarchical_seed_sample,
    suggest_tree_column_blocks,
)


def _write_hierarchical(path: Path) -> None:
    path.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,CMA,TENUR,DTYPE,ROOM,BEDRM,"
        "CONDO,PRESMORTG,VALUE,SHELCO,SUBSIDY,REPAIR,BUILT,FCOND,NOS,"
        "AGEGRP,GENDER,MARSTH,IMMSTAT\n"
        "1,11,111,11101,100.5,24,462,1,1,6,3,0,1,500000,1200,0,1,3,0,1,11,1,1,1\n"
        "1,11,111,11102,100.5,24,462,1,1,6,3,0,1,500000,1200,0,1,3,0,1,3,2,6,9\n"
        "2,21,211,21101,80.25,35,535,2,5,4,2,1,0,99999999,900,1,1,4,0,2,11,2,6,1\n"
    )


def test_reads_and_profiles_2021_hierarchical_pumf(tmp_path: Path) -> None:
    source = tmp_path / "hierarchical-2021.csv"
    _write_hierarchical(source)

    sample = read_statcan_2021_hierarchical_seed_sample(source)
    suggestions = suggest_tree_column_blocks(sample)

    assert sample.source_format == "statcan-2021-hierarchical"
    assert sample.metadata["census_year"] == 2021
    assert sample.metadata["households"] == 2
    assert sample.metadata["people"] == 3
    demographics = next(
        block
        for block in suggestions["blocks"]
        if block["name"] == "person_demographics"
    )
    assert demographics["target_columns"] == [
        "AGEGRP",
        "GENDER",
        "MARSTH",
        "IMMSTAT",
    ]
    assert demographics["missing_target_columns"] == []


def test_exports_linked_2021_household_and_person_training_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "hierarchical-2021.csv"
    _write_hierarchical(source)
    sample = read_statcan_2021_hierarchical_seed_sample(source)

    households, household_summary = export_training_rows(
        sample,
        level="household",
        target_columns=("household_size", "TENUR"),
        conditioning_columns=("PR",),
    )
    people, person_summary = export_training_rows(
        sample,
        level="person",
        target_columns=("AGEGRP", "GENDER"),
        conditioning_columns=("PR", "household_size", "TENUR"),
    )

    assert households[0] == {
        "HH_ID": "1",
        "PR": "24",
        "household_size": "2",
        "TENUR": "1",
        "WEIGHT": "100.5",
    }
    assert people[0]["household_size"] == "2"
    assert household_summary["source_format"] == "statcan-2021-hierarchical"
    assert person_summary["source_format"] == "statcan-2021-hierarchical"


def test_reads_and_exports_2021_individual_pumf(tmp_path: Path) -> None:
    source = tmp_path / "individual-2021.csv"
    source.write_text(
        "PPSORT,PR,CMA,AGEGRP,Gender,WEIGHT\n1,24,462,11,1,37.5\n2,35,535,13,2,42.0\n"
    )
    sample = read_statcan_2021_individual_seed_sample(
        source,
        columns=("PR", "AGEGRP", "Gender"),
    )
    rows, summary = export_training_rows(
        sample,
        level="person",
        target_columns=("AGEGRP", "Gender"),
        conditioning_columns=("PR",),
    )

    assert sample.metadata["linked_households"] is False
    assert rows[0] == {
        "PPSORT": "1",
        "PR": "24",
        "AGEGRP": "11",
        "Gender": "1",
        "WEIGHT": "37.5",
    }
    assert summary["id_columns"] == ["PPSORT"]
    with pytest.raises(ValueError, match="only person-level"):
        export_training_rows(
            sample,
            level="household",
            target_columns=("AGEGRP",),
            conditioning_columns=("PR",),
        )


def test_streams_2021_inspection_and_rejects_unknown_formats(tmp_path: Path) -> None:
    individual = tmp_path / "individual-2021.csv"
    individual.write_text("PPSORT,PR,AGEGRP,WEIGHT\n1,24,11,37.5\n1,24,13,42.0\n")
    summary = inspect_statcan_microdata(
        individual,
        source_format="statcan-2021-individual",
    )
    sample = read_statcan_2021_individual_seed_sample(individual)

    assert summary["records"] == 2
    assert summary["duplicate_record_ids"] == 1
    assert sample.columns == ("PPSORT", "PR", "AGEGRP", "WEIGHT")
    assert sample.metadata["duplicate_record_ids"] == 1
    with pytest.raises(ValueError, match="unsupported StatCan source format"):
        inspect_statcan_microdata(individual, source_format="unknown")
    with pytest.raises(ValueError, match="unsupported hierarchical source format"):
        read_statcan_hierarchical_seed_sample(
            individual,
            source_format="statcan-2021-individual",
        )


def test_cli_uses_explicit_2021_formats(tmp_path: Path, capsys) -> None:
    hierarchical = tmp_path / "hierarchical-2021.csv"
    individual = tmp_path / "individual-2021.csv"
    training = tmp_path / "person-training.csv"
    _write_hierarchical(hierarchical)
    individual.write_text("PPSORT,PR,CMA,AGEGRP,Gender,WEIGHT\n1,24,462,11,1,37.5\n")

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(hierarchical),
                "--input-format",
                "statcan-2021-hierarchical",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["census_year"] == 2021

    assert (
        main(
            [
                "microdata",
                "export-training",
                str(individual),
                "--input-format",
                "statcan-2021-individual",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,Gender",
                "--conditioning-columns",
                "PR",
                "--out",
                str(training),
                "--format",
                "json",
            ]
        )
        == 0
    )
    with training.open(newline="") as handle:
        assert list(csv.DictReader(handle))[0]["PPSORT"] == "1"

    with pytest.raises(
        click.ClickException, match="cannot produce household seed rows"
    ):
        main(
            [
                "microdata",
                "export-seed",
                str(individual),
                "--input-format",
                "statcan-2021-individual",
                "--level",
                "household",
                "--columns",
                "AGEGRP",
                "--out",
                str(tmp_path / "invalid-households.csv"),
            ]
        )


def test_cli_trains_linked_2021_models(tmp_path: Path) -> None:
    source = tmp_path / "hierarchical-2021.csv"
    household_model = tmp_path / "household-model.json"
    person_model = tmp_path / "person-model.json"
    manifest = tmp_path / "manifest.json"
    _write_hierarchical(source)

    assert (
        main(
            [
                "models",
                "build",
                "train-linked",
                str(source),
                "--input-format",
                "statcan-2021-hierarchical",
                "--household-block",
                "household_core",
                "--person-block",
                "person_demographics",
                "--household-model-out",
                str(household_model),
                "--person-model-out",
                str(person_model),
                "--manifest-out",
                str(manifest),
                "--min-support",
                "1",
            ]
        )
        == 0
    )
    payload = json.loads(manifest.read_text())
    assert payload["source"]["source_format"] == "statcan-2021-hierarchical"
    assert payload["column_source"]["profile"] == "statcan-2021-hierarchical"
