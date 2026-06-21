import json

import pytest
from click import ClickException

from synthpopcan.cli import main
from synthpopcan.microdata import (
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
)


def test_reads_fixture_seed_sample_contract(tmp_path) -> None:
    source = tmp_path / "people.csv"
    source.write_text(
        "person_id,geo,age_group,sex,weight\n"
        "p1,QC,age_000_004,female,1\n"
        "p2,QC,age_005_009,male,2\n"
    )

    sample = read_fixture_seed_sample(
        source,
        level="person",
        weight_column="weight",
        geography_columns=("geo",),
        id_columns=("person_id",),
    )

    assert sample.level == "person"
    assert sample.source_format == "fixture-v1"
    assert sample.weight_column == "weight"
    assert sample.geography_columns == ("geo",)
    assert sample.id_columns == ("person_id",)
    assert sample.columns == ("person_id", "geo", "age_group", "sex", "weight")
    assert len(sample.records) == 2


def test_cli_inspects_fixture_microdata(tmp_path, capsys) -> None:
    source = tmp_path / "people.csv"
    source.write_text(
        "person_id,geo,age_group,sex,weight\n"
        "p1,QC,age_000_004,female,1\n"
        "p2,QC,age_005_009,male,2\n"
    )

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "fixture-v1",
                "--level",
                "person",
                "--weight-column",
                "weight",
                "--geography-columns",
                "geo",
                "--id-columns",
                "person_id",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "columns": ["person_id", "geo", "age_group", "sex", "weight"],
        "geography_columns": ["geo"],
        "id_columns": ["person_id"],
        "level": "person",
        "records": 2,
        "source_format": "fixture-v1",
        "weight_column": "weight",
    }


def test_cli_inspects_fixture_without_optional_seed_columns(tmp_path, capsys) -> None:
    source = tmp_path / "people.csv"
    source.write_text("age_group,sex\nage_000_004,female\n")

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "fixture-v1",
                "--level",
                "person",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["geography_columns"] == []
    assert payload["id_columns"] == []
    assert payload["weight_column"] is None


def test_reads_statcan_2016_hierarchical_seed_sample(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
        "2,21,211,21101,81.25,adult,F,renter\n"
    )

    sample = read_statcan_2016_hierarchical_seed_sample(source)

    assert sample.source_format == "statcan-2016-hierarchical"
    assert sample.level == "person"
    assert sample.weight_column == "WEIGHT"
    assert sample.id_columns == ("PP_ID",)
    assert sample.metadata == {
        "household_id_column": "HH_ID",
        "economic_family_id_column": "EF_ID",
        "census_family_id_column": "CF_ID",
        "person_id_column": "PP_ID",
        "households": 2,
        "people": 3,
        "average_household_size": 1.5,
        "duplicate_person_ids": 0,
    }


def test_cli_inspects_statcan_2016_hierarchical_microdata(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
        "2,21,211,21101,81.25,adult,F,renter\n"
    )

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["source_format"] == "statcan-2016-hierarchical"
    assert payload["level"] == "person"
    assert payload["records"] == 3
    assert payload["households"] == 2
    assert payload["people"] == 3
    assert payload["average_household_size"] == 1.5


def test_statcan_2016_hierarchical_requires_known_identifier_columns(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text("HH_ID,PP_ID,WEIGHT\n1,11101,100.5\n")

    with pytest.raises(ValueError, match="missing required columns: EF_ID, CF_ID"):
        read_statcan_2016_hierarchical_seed_sample(source)


def test_fixture_inspection_still_requires_level(tmp_path) -> None:
    source = tmp_path / "people.csv"
    source.write_text("person_id,age_group\np1,adult\n")

    with pytest.raises(ClickException, match="fixture-v1 requires --level"):
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "fixture-v1",
            ]
        )
