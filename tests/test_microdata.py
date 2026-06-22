import json

import pytest
from click import ClickException

from synthpopcan.cli import main
from synthpopcan.microdata import (
    check_statcan_2016_household_seed_columns,
    derive_statcan_2016_household_seed_sample,
    export_seed_rows,
    export_training_rows,
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
    suggest_tree_column_blocks,
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


def test_exports_selected_seed_rows_from_fixture_sample(tmp_path) -> None:
    source = tmp_path / "people.csv"
    source.write_text(
        "person_id,geo,age_group,sex,weight,extra\n"
        "p1,QC,age_000_004,female,1,ignored\n"
        "p2,QC,age_005_009,male,2,ignored\n"
    )
    sample = read_fixture_seed_sample(
        source,
        level="person",
        weight_column="weight",
        geography_columns=("geo",),
        id_columns=("person_id",),
    )

    rows, summary = export_seed_rows(
        sample,
        columns=("age_group", "sex"),
    )

    assert rows == [
        {
            "person_id": "p1",
            "geo": "QC",
            "age_group": "age_000_004",
            "sex": "female",
            "weight": "1",
        },
        {
            "person_id": "p2",
            "geo": "QC",
            "age_group": "age_005_009",
            "sex": "male",
            "weight": "2",
        },
    ]
    assert summary == {
        "source_format": "fixture-v1",
        "level": "person",
        "rows_read": 2,
        "rows_written": 2,
        "columns": ["person_id", "geo", "age_group", "sex", "weight"],
        "selected_columns": ["age_group", "sex"],
        "id_columns": ["person_id"],
        "geography_columns": ["geo"],
        "weight_column": "weight",
    }


def test_cli_exports_seed_csv_from_statcan_2016_hierarchical(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    output = tmp_path / "seed.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
    )

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(output),
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert output.read_text() == (
        "PP_ID,AGEGRP,SEX,WEIGHT\n11101,adult,F,100.5\n11102,child,M,100.5\n"
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows_written"] == 2
    assert payload["columns"] == ["PP_ID", "AGEGRP", "SEX", "WEIGHT"]


def test_derives_household_seed_rows_from_statcan_2016_hierarchical(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
        "2,21,211,21101,81.25,adult,F,renter\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    household_sample = derive_statcan_2016_household_seed_sample(
        sample,
        columns=("TENUR",),
    )
    rows, summary = export_seed_rows(household_sample, columns=("TENUR",))

    assert rows == [
        {
            "HH_ID": "1",
            "TENUR": "owner",
            "household_size": "2",
            "WEIGHT": "100.5",
        },
        {
            "HH_ID": "2",
            "TENUR": "renter",
            "household_size": "1",
            "WEIGHT": "81.25",
        },
    ]
    assert summary["level"] == "household"
    assert summary["rows_read"] == 2
    assert summary["rows_written"] == 2


def test_cli_exports_household_seed_csv_from_statcan_2016_hierarchical(
    tmp_path, capsys
) -> None:
    source = tmp_path / "hierarchical.csv"
    output = tmp_path / "households.csv"
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
                "export-seed",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "household",
                "--columns",
                "TENUR",
                "--out",
                str(output),
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert output.read_text() == (
        "HH_ID,TENUR,household_size,WEIGHT\n1,owner,2,100.5\n2,renter,1,81.25\n"
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "household"
    assert payload["columns"] == ["HH_ID", "TENUR", "household_size", "WEIGHT"]


def test_exports_person_training_rows_from_statcan_2016_hierarchical(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
        "2,21,211,21101,81.25,adult,F,renter\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    rows, summary = export_training_rows(
        sample,
        level="person",
        target_columns=("AGEGRP", "SEX"),
        conditioning_columns=("TENUR", "household_size"),
    )

    assert rows == [
        {
            "PP_ID": "11101",
            "HH_ID": "1",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "adult",
            "SEX": "F",
            "WEIGHT": "100.5",
        },
        {
            "PP_ID": "11102",
            "HH_ID": "1",
            "TENUR": "owner",
            "household_size": "2",
            "AGEGRP": "child",
            "SEX": "M",
            "WEIGHT": "100.5",
        },
        {
            "PP_ID": "21101",
            "HH_ID": "2",
            "TENUR": "renter",
            "household_size": "1",
            "AGEGRP": "adult",
            "SEX": "F",
            "WEIGHT": "81.25",
        },
    ]
    assert summary == {
        "source_format": "statcan-2016-hierarchical",
        "level": "person",
        "rows_read": 3,
        "rows_written": 3,
        "columns": [
            "PP_ID",
            "HH_ID",
            "TENUR",
            "household_size",
            "AGEGRP",
            "SEX",
            "WEIGHT",
        ],
        "target_columns": ["AGEGRP", "SEX"],
        "conditioning_columns": ["TENUR", "household_size"],
        "id_columns": ["PP_ID", "HH_ID"],
        "weight_column": "WEIGHT",
    }


def test_cli_exports_training_csv_from_statcan_2016_hierarchical(
    tmp_path, capsys
) -> None:
    source = tmp_path / "hierarchical.csv"
    output = tmp_path / "person-training.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
        "1,11,111,11102,100.5,child,M,owner\n"
    )

    assert (
        main(
            [
                "microdata",
                "export-training",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP,SEX",
                "--conditioning-columns",
                "TENUR,household_size",
                "--out",
                str(output),
                "--format",
                "json",
            ]
        )
        == 0
    )

    assert output.read_text() == (
        "PP_ID,HH_ID,TENUR,household_size,AGEGRP,SEX,WEIGHT\n"
        "11101,1,owner,2,adult,F,100.5\n"
        "11102,1,owner,2,child,M,100.5\n"
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "person"
    assert payload["target_columns"] == ["AGEGRP", "SEX"]
    assert payload["conditioning_columns"] == ["TENUR", "household_size"]


def test_exports_household_training_rows_from_statcan_2016_hierarchical(
    tmp_path,
) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR\n"
        "1,11,111,11101,100.5,owner\n"
        "1,11,111,11102,100.5,owner\n"
        "2,21,211,21101,81.25,renter\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    rows, summary = export_training_rows(
        sample,
        level="household",
        target_columns=("TENUR",),
        conditioning_columns=("household_size",),
    )

    assert rows == [
        {
            "HH_ID": "1",
            "household_size": "2",
            "TENUR": "owner",
            "WEIGHT": "100.5",
        },
        {
            "HH_ID": "2",
            "household_size": "1",
            "TENUR": "renter",
            "WEIGHT": "81.25",
        },
    ]
    assert summary["level"] == "household"
    assert summary["columns"] == ["HH_ID", "household_size", "TENUR", "WEIGHT"]


def test_checks_household_seed_columns_before_export(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR,ROOMS\n"
        "1,11,111,11101,100.5,owner,5\n"
        "1,11,111,11102,100.5,owner,6\n"
        "2,21,211,21101,81.25,renter,3\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    report = check_statcan_2016_household_seed_columns(
        sample,
        columns=("TENUR", "ROOMS"),
    )

    assert report == {
        "source_format": "statcan-2016-hierarchical",
        "level": "household",
        "households": 2,
        "people": 3,
        "passed": False,
        "checks": [
            {
                "column": "TENUR",
                "role": "selected household column",
                "status": "ok",
                "detail": "constant within each HH_ID",
                "problem_households": 0,
            },
            {
                "column": "ROOMS",
                "role": "selected household column",
                "status": "problem",
                "detail": "varies within 1 household",
                "problem_households": 1,
            },
            {
                "column": "WEIGHT",
                "role": "weight",
                "status": "ok",
                "detail": "constant within each HH_ID",
                "problem_households": 0,
            },
            {
                "column": "household_size",
                "role": "derived",
                "status": "ok",
                "detail": "derived from row count per HH_ID",
                "problem_households": 0,
            },
        ],
    }


def test_cli_checks_household_seed_columns_as_json(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR,ROOMS\n"
        "1,11,111,11101,100.5,owner,5\n"
        "1,11,111,11102,100.5,owner,6\n"
    )

    assert (
        main(
            [
                "microdata",
                "check-seed",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "household",
                "--columns",
                "TENUR,ROOMS",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["checks"][0]["column"] == "TENUR"
    assert payload["checks"][0]["status"] == "ok"
    assert payload["checks"][1]["column"] == "ROOMS"
    assert payload["checks"][1]["status"] == "problem"
    assert payload["checks"][1]["detail"] == "varies within 1 household"


def test_cli_checks_household_seed_columns_as_readable_table(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR,ROOMS\n"
        "1,11,111,11101,100.5,owner,5\n"
        "1,11,111,11102,100.5,owner,6\n"
    )

    assert (
        main(
            [
                "microdata",
                "check-seed",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "household",
                "--columns",
                "TENUR,ROOMS",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Seed Column Check" in output
    assert "TENUR" in output
    assert "OK" in output
    assert "ROOMS" in output
    assert "Problem" in output
    assert "varies within 1 household" in output


def test_suggests_tree_column_blocks_from_statcan_2016_columns(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,WT1,PR,CMA,TENUR,DTYPE,ROOM,BEDRM,"
        "CONDO,VALUE,SHELCO,AGEGRP,SEX,MarStH,IMMSTAT,HDGREE,LFTAG,TOTINC,"
        "CITIZEN,VISMIN\n"
        "1,11,111,11101,1,1,24,462,1,2,5,3,4,1,6,4,1,2,1,6,3,7,1,1\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    suggestion = suggest_tree_column_blocks(sample)

    assert suggestion["source_format"] == "statcan-2016-hierarchical"
    assert suggestion["profile"] == "statcan-2016-hierarchical"
    assert suggestion["excluded_columns"] == [
        {"column": "HH_ID", "reason": "identifier"},
        {"column": "EF_ID", "reason": "identifier"},
        {"column": "CF_ID", "reason": "identifier"},
        {"column": "PP_ID", "reason": "identifier"},
        {"column": "WEIGHT", "reason": "weight"},
        {"column": "WT1", "reason": "replicate_weight"},
    ]
    assert suggestion["geography_columns"] == ["PR", "CMA"]
    assert suggestion["blocks"] == [
        {
            "name": "household_core",
            "level": "household",
            "target_columns": [
                "household_size",
                "TENUR",
                "DTYPE",
                "ROOM",
                "BEDRM",
                "CONDO",
                "VALUE",
                "SHELCO",
            ],
            "conditioning_columns": ["PR"],
            "available_target_columns": [
                "household_size",
                "TENUR",
                "DTYPE",
                "ROOM",
                "BEDRM",
                "CONDO",
                "VALUE",
                "SHELCO",
            ],
            "missing_target_columns": ["PRESMORTG", "SUBSIDY", "REPAIR", "BUILT"],
        },
        {
            "name": "person_demographics",
            "level": "person",
            "target_columns": ["AGEGRP", "SEX", "MarStH", "IMMSTAT"],
            "conditioning_columns": ["PR", "household_size", "TENUR"],
            "available_target_columns": ["AGEGRP", "SEX", "MarStH", "IMMSTAT"],
            "missing_target_columns": [],
        },
        {
            "name": "person_identity_language",
            "level": "person",
            "target_columns": ["CITIZEN", "VISMIN"],
            "conditioning_columns": [
                "PR",
                "household_size",
                "TENUR",
                "AGEGRP",
                "SEX",
            ],
            "available_target_columns": ["CITIZEN", "VISMIN"],
            "missing_target_columns": [
                "GENSTAT",
                "POB",
                "MTNEn",
                "MTNFr",
                "MTNNO",
                "HLBEN",
                "HLBFR",
                "HLBNO",
            ],
        },
        {
            "name": "person_education_work_income",
            "level": "person",
            "target_columns": ["HDGREE", "LFTAG", "TOTINC"],
            "conditioning_columns": [
                "PR",
                "household_size",
                "TENUR",
                "AGEGRP",
                "SEX",
            ],
            "available_target_columns": ["HDGREE", "LFTAG", "TOTINC"],
            "missing_target_columns": [
                "EMPIN",
                "FPTWK",
                "HRSWRK",
                "WKSWRK",
                "WRKACT",
            ],
        },
    ]


def test_cli_suggests_tree_columns_as_json(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,DTYPE,AGEGRP,SEX\n"
        "1,11,111,11101,1,24,1,2,4,1\n"
    )

    assert (
        main(
            [
                "microdata",
                "suggest-tree-columns",
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
    assert payload["blocks"][0]["name"] == "household_core"
    assert payload["blocks"][0]["target_columns"] == [
        "household_size",
        "TENUR",
        "DTYPE",
    ]
    assert payload["blocks"][1]["target_columns"] == ["AGEGRP", "SEX"]


def test_household_seed_export_rejects_conflicting_household_attributes(
    tmp_path,
) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR\n"
        "1,11,111,11101,100.5,owner\n"
        "1,11,111,11102,100.5,renter\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    with pytest.raises(ValueError, match="conflicting household column 'TENUR'"):
        derive_statcan_2016_household_seed_sample(sample, columns=("TENUR",))


def test_household_seed_export_rejects_conflicting_household_weights(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR\n"
        "1,11,111,11101,100.5,owner\n"
        "1,11,111,11102,99.0,owner\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    with pytest.raises(ValueError, match="conflicting household weight"):
        derive_statcan_2016_household_seed_sample(sample, columns=("TENUR",))


def test_cli_inspects_microdata_as_readable_table(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    rows = [
        f"{household_id},11,111,{household_id:04d}{person_id:02d},100.5,adult,F,owner\n"
        for household_id in range(1, 618)
        for person_id in (1, 2)
    ]
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n" + "".join(rows)
    )

    assert (
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Microdata Summary" in output
    assert "Records" in output
    assert "1,234" in output
    assert "Households" in output
    assert "617" in output
    assert "Average household size" in output


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
