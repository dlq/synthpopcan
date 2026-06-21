import json

from synthpopcan.census_microdata import read_fixture_seed_sample
from synthpopcan.cli import main


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


def test_cli_inspects_fixture_census_microdata(tmp_path, capsys) -> None:
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
