import json

import pytest
from click import ClickException

from synthpopcan.cli import main
from synthpopcan.cli_microdata import parse_columns, write_rows
from synthpopcan.microdata import (
    SeedSample,
    build_tree_geography_feasibility_report,
    canadian_aggregation_hint,
    check_statcan_2016_household_seed_columns,
    columns_to_review,
    derive_statcan_2016_household_seed_sample,
    export_seed_rows,
    export_training_rows,
    feasibility_reasons,
    feasibility_tier,
    find_suggested_tree_column_block,
    group_records_by_household,
    household_size_lookup,
    minimal_household_targets,
    minimal_person_targets,
    person_records_for_feasibility,
    read_fixture_seed_sample,
    read_statcan_2016_hierarchical_seed_sample,
    reduced_conditioning_columns,
    reduced_household_targets,
    reduced_person_targets,
    require_suggested_tree_columns,
    resolve_tree_column_block_pair,
    suggest_tree_column_blocks,
    suggested_feasibility_action,
    support_and_purity_summary,
    training_value,
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
                "--geo-columns",
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


def test_cli_microdata_inspect_requires_fixture_level(tmp_path) -> None:
    source = tmp_path / "people.csv"
    source.write_text("age_group,sex\nadult,F\n")

    with pytest.raises(ClickException, match="--level household or --level person"):
        main(["microdata", "inspect", str(source), "--input-format", "fixture-v1"])

    with pytest.raises(ClickException, match="missing required columns: weight"):
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
            ]
        )


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


def test_cli_exports_fixture_seed_as_table_and_requires_level(tmp_path, capsys) -> None:
    source = tmp_path / "people.csv"
    output = tmp_path / "seed.csv"
    source.write_text("person_id,geo,age_group,sex,weight\np1,QC,adult,F,1\n")

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(source),
                "--input-format",
                "fixture-v1",
                "--level",
                "person",
                "--columns",
                "age_group,sex",
                "--weight-column",
                "weight",
                "--geo-columns",
                "geo",
                "--id-columns",
                "person_id",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    assert "Seed Export Summary" in capsys.readouterr().out

    with pytest.raises(ClickException, match="--level household or --level person"):
        main(
            [
                "microdata",
                "export-seed",
                str(source),
                "--input-format",
                "fixture-v1",
                "--columns",
                "age_group",
                "--out",
                str(output),
            ]
        )
    with pytest.raises(ClickException, match="missing required columns: missing"):
        main(
            [
                "microdata",
                "export-seed",
                str(source),
                "--input-format",
                "fixture-v1",
                "--level",
                "person",
                "--columns",
                "missing",
                "--out",
                str(output),
            ]
        )


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


def test_cli_exports_training_csv_as_table_and_wraps_bad_columns(
    tmp_path,
    capsys,
) -> None:
    source = tmp_path / "hierarchical.csv"
    output = tmp_path / "person-training.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,AGEGRP,SEX,TENUR\n"
        "1,11,111,11101,100.5,adult,F,owner\n"
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
                "AGEGRP",
                "--conditioning-columns",
                "TENUR",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    assert "Training Export Summary" in capsys.readouterr().out

    with pytest.raises(ClickException, match="at least one column"):
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
                " , ",
                "--conditioning-columns",
                "TENUR",
                "--out",
                str(output),
            ]
        )
    bad_source = tmp_path / "bad-hierarchical.csv"
    bad_source.write_text("HH_ID,WEIGHT\n1,1\n")
    with pytest.raises(ClickException, match="missing required columns"):
        main(
            [
                "microdata",
                "export-training",
                str(bad_source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP",
                "--conditioning-columns",
                "TENUR",
                "--out",
                str(output),
            ]
        )


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


def test_cli_check_seed_wraps_bad_hierarchical_source(tmp_path) -> None:
    source = tmp_path / "bad.csv"
    source.write_text("HH_ID,WEIGHT\n1,1\n")

    with pytest.raises(ClickException, match="missing required columns"):
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
                "TENUR",
            ]
        )


def test_suggests_tree_column_blocks_from_statcan_2016_columns(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,WT1,PR,CMA,TENUR,DTYPE,ROOM,BEDRM,"
        "CONDO,VALUE,SHELCO,FCOND,NOS,AGEGRP,SEX,MarStH,IMMSTAT,HDGREE,"
        "LFTAG,TOTINC,CITIZEN,VISMIN\n"
        "1,11,111,11101,1,1,24,462,1,2,5,3,4,1,6,1,2,4,1,2,1,6,3,7,1,1\n"
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
            "name": "household_family_context",
            "level": "household",
            "target_columns": ["FCOND", "NOS"],
            "conditioning_columns": ["PR", "household_size", "TENUR"],
            "available_target_columns": ["FCOND", "NOS"],
            "missing_target_columns": [],
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


def test_tree_column_suggestions_reject_unknown_source_format() -> None:
    sample = SeedSample(
        level="person",
        source_format="unknown-format",
        records=(),
        columns=(),
        weight_column=None,
        geography_columns=(),
        id_columns=(),
    )

    with pytest.raises(ValueError, match="not available for unknown-format"):
        suggest_tree_column_blocks(sample)


def test_builds_tree_geography_feasibility_report(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,CMA,TENUR,DTYPE,ROOM,BEDRM,CONDO,"
        "PRESMORTG,VALUE,SHELCO,SUBSIDY,REPAIR,BUILT,AGEGRP,SEX,MarStH,IMMSTAT\n"
        "1,11,111,11101,1,24,462,1,2,5,3,4,1,6,4,1,2,9,adult,F,married,non_immigrant\n"
        "1,11,111,11102,1,24,462,1,2,5,3,4,1,6,4,1,2,9,child,M,single,non_immigrant\n"
        "2,21,211,21101,1,24,462,2,3,4,2,5,2,7,5,2,3,8,adult,F,single,immigrant\n"
        "3,31,311,31101,1,11,999,1,2,5,3,4,1,6,4,1,2,9,adult,F,married,non_immigrant\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)

    report = build_tree_geography_feasibility_report(
        sample,
        geography_column="PR",
        household_block="household_core",
        person_block="person_demographics",
        likely_person_rows=3,
        likely_household_rows=2,
        borderline_person_rows=2,
        borderline_household_rows=1,
        min_support=1,
        max_purity=1.0,
    )

    assert report["geography_column"] == "PR"
    assert report["column_source"] == {
        "mode": "profile",
        "profile": "statcan-2016-hierarchical",
        "household_block": "household_core",
        "person_block": "person_demographics",
    }
    regions = {region["geography"]: region for region in report["regions"]}
    assert regions["24"]["person_rows"] == 3
    assert regions["24"]["household_rows"] == 2
    assert regions["24"]["tier"] == "likely"
    assert regions["24"]["suggested_action"] == "candidate for full block review"
    assert regions["24"]["model_design"]["scope"] == "separate_geography_model"
    assert regions["24"]["model_design"]["block_strategy"] == "use_requested_blocks"
    assert (
        "Train and audit this geography separately."
        in regions["24"]["model_design"]["next_steps"]
    )
    assert regions["11"]["person_rows"] == 1
    assert regions["11"]["household_rows"] == 1
    assert regions["11"]["tier"] == "unlikely"
    assert "too few person rows" in regions["11"]["reasons"]
    assert regions["11"]["model_design"]["scope"] == "aggregate_geography_model"
    assert "Atlantic aggregate" in regions["11"]["model_design"]["aggregation_hint"]
    assert regions["11"]["model_design"]["household_targets"] == [
        "household_size",
        "TENUR",
    ]
    assert regions["11"]["model_design"]["person_targets"] == ["AGEGRP", "SEX"]


def test_tree_geography_feasibility_rejects_unknown_source_format() -> None:
    sample = SeedSample(
        level="person",
        source_format="fixture-v1",
        records=(),
        columns=("geo",),
        weight_column=None,
        geography_columns=("geo",),
        id_columns=(),
    )

    with pytest.raises(ValueError, match="requires statcan-2016-hierarchical"):
        build_tree_geography_feasibility_report(sample, geography_column="geo")


def test_cli_reports_tree_geography_feasibility_as_json(tmp_path, capsys) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,AGEGRP,SEX\n"
        "1,11,111,11101,1,24,1,adult,F\n"
        "1,11,111,11102,1,24,1,child,M\n"
        "2,21,211,21101,1,11,2,adult,F\n"
    )

    assert (
        main(
            [
                "microdata",
                "tree-geography-feasibility",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--geo-column",
                "PR",
                "--likely-person-rows",
                "2",
                "--likely-household-rows",
                "1",
                "--borderline-person-rows",
                "1",
                "--borderline-household-rows",
                "1",
                "--min-support",
                "1",
                "--max-purity",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["regions"][0]["geography"] == "24"
    assert report["regions"][0]["tier"] == "likely"


def test_cli_reports_tree_geography_feasibility_as_table_and_wraps_errors(
    tmp_path,
    capsys,
) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,AGEGRP,SEX\n"
        "1,11,111,11101,1,24,1,adult,F\n"
    )

    assert (
        main(
            [
                "microdata",
                "tree-geography-feasibility",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--geo-column",
                "PR",
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )
    assert "Tree Geography Feasibility" in capsys.readouterr().out

    with pytest.raises(ClickException, match="missing required columns"):
        main(
            [
                "microdata",
                "tree-geography-feasibility",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--geo-column",
                "MISSING",
            ]
        )


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
    blocks_by_name = {block["name"]: block for block in payload["blocks"]}
    assert blocks_by_name["person_demographics"]["target_columns"] == ["AGEGRP", "SEX"]


def test_cli_suggests_tree_columns_as_table_and_wraps_errors(tmp_path, capsys) -> None:
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
            ]
        )
        == 0
    )
    assert "Tree Column Suggestions" in capsys.readouterr().out

    bad_source = tmp_path / "bad.csv"
    bad_source.write_text("HH_ID,WEIGHT\n1,1\n")
    with pytest.raises(ClickException, match="missing required columns"):
        main(
            [
                "microdata",
                "suggest-tree-columns",
                str(bad_source),
                "--input-format",
                "statcan-2016-hierarchical",
            ]
        )


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


def test_seed_and_training_exports_reject_invalid_inputs(tmp_path) -> None:
    fixture_path = tmp_path / "people.csv"
    fixture_path.write_text("person_id,age_group\np1,adult\n")
    fixture = read_fixture_seed_sample(
        fixture_path,
        level="person",
        weight_column=None,
        geography_columns=(),
        id_columns=("person_id",),
    )
    hierarchical_path = tmp_path / "hierarchical.csv"
    hierarchical_path.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,TENUR,AGEGRP\n1,11,111,11101,1,owner,adult\n"
    )
    hierarchical = read_statcan_2016_hierarchical_seed_sample(hierarchical_path)

    with pytest.raises(ValueError, match="at least one seed column"):
        export_seed_rows(fixture, columns=())
    with pytest.raises(ValueError, match="missing required columns"):
        export_seed_rows(fixture, columns=("sex",))
    with pytest.raises(ValueError, match="requires statcan-2016-hierarchical"):
        export_training_rows(
            fixture,
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("person_id",),
        )
    with pytest.raises(ValueError, match="at least one target column"):
        export_training_rows(
            hierarchical,
            level="person",
            target_columns=(),
            conditioning_columns=("TENUR",),
        )
    with pytest.raises(ValueError, match="at least one conditioning column"):
        export_training_rows(
            hierarchical,
            level="person",
            target_columns=("AGEGRP",),
            conditioning_columns=(),
        )
    with pytest.raises(ValueError, match="household derivation requires"):
        derive_statcan_2016_household_seed_sample(fixture, columns=("TENUR",))
    with pytest.raises(ValueError, match="at least one household column"):
        derive_statcan_2016_household_seed_sample(hierarchical, columns=())
    with pytest.raises(ValueError, match="household seed checks require"):
        check_statcan_2016_household_seed_columns(fixture, columns=("TENUR",))
    with pytest.raises(ValueError, match="at least one household column"):
        check_statcan_2016_household_seed_columns(hierarchical, columns=())


def test_cli_microdata_helpers_reject_empty_columns_and_rows(tmp_path) -> None:
    with pytest.raises(ClickException, match="at least one column"):
        parse_columns(" , ")
    with pytest.raises(ValueError, match="empty CSV output"):
        write_rows(tmp_path / "empty.csv", [])


def test_tree_column_block_resolution_and_helper_errors(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,AGEGRP,SEX\n"
        "1,11,111,11101,1,24,owner,adult,F\n"
    )
    sample = read_statcan_2016_hierarchical_seed_sample(source)
    suggestion = suggest_tree_column_blocks(sample)

    (
        household_targets,
        household_conditions,
        person_targets,
        person_conditions,
        report,
    ) = resolve_tree_column_block_pair(
        sample,
        household_block="household_core",
        person_block="person_demographics",
    )
    assert household_targets == ("household_size", "TENUR")
    assert household_conditions == ("PR",)
    assert person_targets == ("AGEGRP", "SEX")
    assert person_conditions == ("PR", "household_size", "TENUR")
    assert report["mode"] == "profile"
    (
        household_targets,
        household_conditions,
        person_targets,
        person_conditions,
        report,
    ) = resolve_tree_column_block_pair(
        sample,
        household_block="all",
        person_block="all",
    )
    assert household_targets == ("household_size", "TENUR")
    assert household_conditions == ("PR",)
    assert person_targets == ("AGEGRP", "SEX")
    assert person_conditions == ("PR", "household_size", "TENUR")
    assert report["household_blocks"] == ["household_core"]
    assert report["person_blocks"] == ["person_demographics"]
    with pytest.raises(ValueError, match="not a person block"):
        find_suggested_tree_column_block(
            suggestion,
            name="household_core",
            level="person",
        )
    with pytest.raises(ValueError, match="was not found"):
        find_suggested_tree_column_block(
            suggestion,
            name="missing",
            level="person",
        )
    with pytest.raises(ValueError, match="blocks must be a list"):
        find_suggested_tree_column_block({"blocks": "bad"}, name="x", level="person")
    with pytest.raises(ValueError, match="invalid target_columns"):
        require_suggested_tree_columns(
            {"name": "bad", "target_columns": "bad"},
            "target_columns",
        )
    with pytest.raises(ValueError, match="has no target_columns"):
        require_suggested_tree_columns(
            {"name": "bad", "target_columns": []},
            "target_columns",
        )


def test_geography_feasibility_advisory_helpers() -> None:
    rows = [
        {"group": "A", "target": "x", "WEIGHT": "2"},
        {"group": "A", "target": "x", "WEIGHT": "1"},
        {"group": "B", "target": "y", "WEIGHT": "1"},
    ]

    assert support_and_purity_summary(
        [],
        conditioning_columns=("group",),
        target_columns=("target",),
    ) == {"groups": 0, "minimum_support": 0.0, "maximum_purity": 0.0}
    assert support_and_purity_summary(
        rows,
        conditioning_columns=("group",),
        target_columns=("target",),
    ) == {"groups": 2, "minimum_support": 1.0, "maximum_purity": 1.0}
    reasons = feasibility_reasons(
        person_rows=100,
        household_rows=50,
        household_risk={"minimum_support": 1.0, "maximum_purity": 1.0},
        person_risk={"minimum_support": 1.0, "maximum_purity": 1.0},
        likely_person_rows=1000,
        likely_household_rows=500,
        borderline_person_rows=200,
        borderline_household_rows=100,
        min_support=50,
        max_purity=0.95,
    )
    assert "too few person rows" in reasons
    assert (
        feasibility_tier(
            [],
            person_rows=1000,
            household_rows=500,
            likely_person_rows=1000,
            likely_household_rows=500,
        )
        == "likely"
    )
    assert (
        feasibility_tier(
            ["limited person rows"],
            person_rows=500,
            household_rows=250,
            likely_person_rows=1000,
            likely_household_rows=500,
        )
        == "borderline"
    )
    assert (
        feasibility_tier(
            ["household conditioning support below threshold"],
            person_rows=1000,
            household_rows=500,
            likely_person_rows=1000,
            likely_household_rows=500,
        )
        == "unlikely"
    )
    assert (
        feasibility_tier(
            ["person outcome purity above threshold"],
            person_rows=1000,
            household_rows=500,
            likely_person_rows=1000,
            likely_household_rows=500,
        )
        == "unlikely"
    )
    assert (
        feasibility_tier(
            ["purity review needed"],
            person_rows=1000,
            household_rows=500,
            likely_person_rows=1000,
            likely_household_rows=500,
        )
        == "unlikely"
    )
    assert suggested_feasibility_action("likely") == "candidate for full block review"
    assert suggested_feasibility_action("borderline") == (
        "coarsen targets or review before training"
    )
    assert columns_to_review([], ("VALUE",), preferred_review_columns=("VALUE",)) == [
        "VALUE"
    ]
    assert columns_to_review(
        [{"VALUE": str(index)} for index in range(8)],
        ("VALUE",),
        preferred_review_columns=(),
    ) == ["VALUE"]
    assert reduced_household_targets(("household_size", "TENUR", "VALUE")) == [
        "household_size",
        "TENUR",
    ]
    assert reduced_person_targets(("AGEGRP", "SEX", "TOTINC")) == ["AGEGRP", "SEX"]
    assert minimal_household_targets(("household_size", "ROOM")) == ["household_size"]
    assert minimal_person_targets(("AGEGRP", "MarStH")) == ["AGEGRP"]
    assert reduced_conditioning_columns(
        ("PR",),
        ("household_size", "TENUR"),
        geography_column="PR",
    ) == ["PR", "household_size", "TENUR"]
    assert canadian_aggregation_hint("PR", "11").startswith("Use an Atlantic")
    assert canadian_aggregation_hint("PR", "70").startswith("Use a territories")
    assert canadian_aggregation_hint("PR", "10").startswith("Review as an Atlantic")
    assert canadian_aggregation_hint("CMA", "999").startswith("Treat as non-CMA")
    assert canadian_aggregation_hint("CMA", "462").startswith("Use only")
    assert canadian_aggregation_hint("CD", "24").startswith("Aggregate")


def test_household_grouping_helpers_reject_missing_household_ids() -> None:
    records = (
        {"HH_ID": "1", "WEIGHT": "1", "AGEGRP": "adult"},
        {"HH_ID": "1", "WEIGHT": "1", "AGEGRP": "child"},
    )

    assert household_size_lookup(records) == {"1": "2"}
    assert (
        training_value(
            {"HH_ID": "1", "AGEGRP": "adult"},
            "household_size",
            household_sizes={"1": "2"},
        )
        == "2"
    )
    assert (
        training_value(
            {"HH_ID": "1", "AGEGRP": "adult"},
            "AGEGRP",
            household_sizes={"1": "2"},
        )
        == "adult"
    )
    with pytest.raises(ValueError, match="non-empty HH_ID"):
        group_records_by_household(({"HH_ID": "", "WEIGHT": "1"},))


def test_person_feasibility_rows_skip_missing_geography_and_block_noise() -> None:
    sample = SeedSample(
        level="person",
        source_format="statcan-2016-hierarchical",
        records=(
            {"HH_ID": "1", "PP_ID": "10", "WEIGHT": "1", "PR": "24", "AGEGRP": "adult"},
            {"HH_ID": "2", "PP_ID": "20", "WEIGHT": "1", "PR": "", "AGEGRP": "child"},
        ),
        columns=("HH_ID", "PP_ID", "WEIGHT", "PR", "AGEGRP"),
        weight_column="WEIGHT",
        geography_columns=("PR",),
        id_columns=("PP_ID",),
    )

    assert person_records_for_feasibility(
        sample,
        geography_column="PR",
        household_sizes={"1": "1", "2": "1"},
        columns=("PR", "household_size", "AGEGRP"),
    ) == [
        {
            "PP_ID": "10",
            "HH_ID": "1",
            "WEIGHT": "1",
            "PR": "24",
            "household_size": "1",
            "AGEGRP": "adult",
        }
    ]
    assert (
        find_suggested_tree_column_block(
            {
                "blocks": [
                    "ignored",
                    {
                        "name": "household_core",
                        "level": "household",
                        "target_columns": [],
                        "conditioning_columns": [],
                    },
                ]
            },
            name="household_core",
            level="household",
        )["name"]
        == "household_core"
    )


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

    with pytest.raises(ClickException, match="--level household or --level person"):
        main(
            [
                "microdata",
                "inspect",
                str(source),
                "--input-format",
                "fixture-v1",
            ]
        )
