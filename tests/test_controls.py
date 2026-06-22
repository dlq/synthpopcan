import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.exceptions import ClickException

from synthpopcan.controls import (
    ControlCell,
    census_profile_template,
    inspect_census_profile_characteristics,
    read_census_profile_control_table,
    read_control_margins,
    read_control_table,
)


def test_reads_normalized_controls_as_control_table(tmp_path: Path) -> None:
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,age,sex,count\n"
        "age,age,young,,60\n"
        "age,age,old,,40\n"
        "sex,sex,,F,50\n"
        "sex,sex,,M,50\n"
    )

    table = read_control_table(controls_path)

    assert table.dimensions == ("age", "sex")
    assert [margin.name for margin in table.margins] == ["age", "sex"]
    assert table.margins[0].cells == (
        ControlCell(categories={"age": "young"}, count=60.0),
        ControlCell(categories={"age": "old"}, count=40.0),
    )
    assert table.to_ipf_margins() == read_control_margins(controls_path)


def test_control_margin_label_must_use_consistent_dimensions(tmp_path: Path) -> None:
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,age,sex,count\ndemo,age,young,,60\ndemo,sex,,F,50\n"
    )

    with pytest.raises(ValueError, match="margin 'demo' mixes dimensions"):
        read_control_margins(controls_path)


def test_cli_normalizes_controls_from_csv(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    source_path = tmp_path / "source.csv"
    output_path = tmp_path / "controls.csv"
    source_path.write_text(
        "margin,dimensions,age,sex,count\n"
        "sex,sex,,M,50\n"
        "age,age,young,,60\n"
        "sex,sex,,F,50\n"
        "age,age,old,,40\n"
    )

    assert (
        main(
            [
                "controls",
                "from-csv",
                str(source_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert output_path.read_text() == (
        "margin,dimensions,age,sex,count\n"
        "sex,sex,,M,50\n"
        "sex,sex,,F,50\n"
        "age,age,young,,60\n"
        "age,age,old,,40\n"
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"Wrote {output_path}" in captured.err


def test_cli_normalizes_controls_from_wds_zip(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    output_path = tmp_path / "controls.csv"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "GEO,Age group,Sex,VALUE,STATUS\n"
            "Canada,0 to 4 years,Female,100,\n"
            "Canada,0 to 4 years,Male,105,\n"
            "Canada,5 to 9 years,Female,95,\n",
        )

    assert (
        main(
            [
                "controls",
                "from-wds",
                str(zip_path),
                "--dimensions",
                "GEO,Age group,Sex",
                "--count-column",
                "VALUE",
                "--margin-name",
                "population",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert output_path.read_text() == (
        "margin,dimensions,GEO,Age group,Sex,count\n"
        'population,"GEO,Age group,Sex",Canada,0 to 4 years,Female,100\n'
        'population,"GEO,Age group,Sex",Canada,0 to 4 years,Male,105\n'
        'population,"GEO,Age group,Sex",Canada,5 to 9 years,Female,95\n'
    )


def test_cli_inspects_wds_zip_and_suggests_normalization_command(
    tmp_path: Path, capsys
) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "98100001-eng.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "98100001.csv",
            "GEO,Age group,Sex,VALUE,STATUS,SYMBOL\n"
            "Canada,0 to 4 years,Female,100,,\n"
            "Canada,0 to 4 years,Male,105,,\n",
        )

    assert (
        main(
            [
                "controls",
                "wds",
                "inspect",
                str(zip_path),
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report == {
        "csv_member": "98100001.csv",
        "columns": ["GEO", "Age group", "Sex", "VALUE", "STATUS", "SYMBOL"],
        "row_count": 2,
        "count_column_candidates": ["VALUE"],
        "dimension_candidates": ["GEO", "Age group", "Sex"],
        "sample_rows": [
            {
                "GEO": "Canada",
                "Age group": "0 to 4 years",
                "Sex": "Female",
                "VALUE": "100",
                "STATUS": "",
                "SYMBOL": "",
            },
            {
                "GEO": "Canada",
                "Age group": "0 to 4 years",
                "Sex": "Male",
                "VALUE": "105",
                "STATUS": "",
                "SYMBOL": "",
            },
        ],
        "suggested_command": (
            "synthpopcan controls from-wds "
            f"{zip_path} "
            "--dimensions 'GEO,Age group,Sex' "
            "--count-column VALUE "
            "--margin-name wds "
            "--out controls.csv"
        ),
    }


def test_cli_writes_wds_category_mapping_template(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    output_path = tmp_path / "categories.json"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "GEO,Age group,Sex,VALUE\n"
            "Canada,0 to 4 years,Female,100\n"
            "Canada,0 to 4 years,Male,105\n"
            "Canada,5 to 9 years,Female,95\n",
        )

    assert (
        main(
            [
                "controls",
                "wds",
                "mapping-template",
                str(zip_path),
                "--dimensions",
                "Age group,Sex",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert json.loads(output_path.read_text()) == {
        "Age group": {
            "0 to 4 years": "",
            "5 to 9 years": "",
        },
        "Sex": {
            "Female": "",
            "Male": "",
        },
    }


def test_cli_applies_category_mapping_to_wds_controls(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    mapping_path = tmp_path / "categories.json"
    output_path = tmp_path / "controls.csv"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "Age group,Sex,VALUE\n0 to 4 years,Female,100\n0 to 4 years,Male,105\n",
        )
    mapping_path.write_text(
        json.dumps(
            {
                "Age group": {"0 to 4 years": "age_000_004"},
                "Sex": {"Female": "female", "Male": "male"},
            }
        )
    )

    assert (
        main(
            [
                "controls",
                "from-wds",
                str(zip_path),
                "--dimensions",
                "Age group,Sex",
                "--count-column",
                "VALUE",
                "--margin-name",
                "population",
                "--mapping",
                str(mapping_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert output_path.read_text() == (
        "margin,dimensions,Age group,Sex,count\n"
        'population,"Age group,Sex",age_000_004,female,100\n'
        'population,"Age group,Sex",age_000_004,male,105\n'
    )


def test_cli_fails_on_unmapped_wds_category(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    mapping_path = tmp_path / "categories.json"
    output_path = tmp_path / "controls.csv"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "Age group,Sex,VALUE\n0 to 4 years,Female,100\n5 to 9 years,Female,95\n",
        )
    mapping_path.write_text(
        json.dumps(
            {
                "Age group": {"0 to 4 years": "age_000_004"},
                "Sex": {"Female": "female"},
            }
        )
    )

    with pytest.raises(ClickException, match="unmapped category"):
        main(
            [
                "controls",
                "from-wds",
                str(zip_path),
                "--dimensions",
                "Age group,Sex",
                "--count-column",
                "VALUE",
                "--mapping",
                str(mapping_path),
                "--out",
                str(output_path),
            ]
        )


def test_reads_census_profile_controls_with_explicit_mapping(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.csv"
    mapping_path = tmp_path / "mapping.json"
    profile_path.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,0 to 4 years,12\n"
        "1001,5 to 9 years,14\n"
        "1002,0 to 4 years,8\n"
        "1002,5 to 9 years,9\n"
    )
    mapping_path.write_text(
        json.dumps(
            {
                "geography": {"column": "GEO_CODE", "dimension": "geo"},
                "characteristic_column": "CHARACTERISTIC_NAME",
                "count_column": "C1_COUNT_TOTAL",
                "margins": [
                    {
                        "name": "age",
                        "dimensions": ["geo", "age"],
                        "categories": {
                            "0 to 4 years": {"age": "age_000_004"},
                            "5 to 9 years": {"age": "age_005_009"},
                        },
                    }
                ],
            }
        )
    )

    table = read_census_profile_control_table(profile_path, mapping_path)

    assert table.dimensions == ("geo", "age")
    assert table.margins[0].name == "age"
    assert table.margins[0].cells == (
        ControlCell({"geo": "1001", "age": "age_000_004"}, 12.0),
        ControlCell({"geo": "1001", "age": "age_005_009"}, 14.0),
        ControlCell({"geo": "1002", "age": "age_000_004"}, 8.0),
        ControlCell({"geo": "1002", "age": "age_005_009"}, 9.0),
    )


def test_cli_normalizes_controls_from_census_profile(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    profile_path = tmp_path / "profile.csv"
    mapping_path = tmp_path / "mapping.json"
    output_path = tmp_path / "controls.csv"
    profile_path.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,0 to 4 years,12\n"
        "1001,5 to 9 years,14\n"
    )
    mapping_path.write_text(
        json.dumps(
            {
                "geography": {"column": "GEO_CODE", "dimension": "geo"},
                "characteristic_column": "CHARACTERISTIC_NAME",
                "count_column": "C1_COUNT_TOTAL",
                "margins": [
                    {
                        "name": "age",
                        "dimensions": ["geo", "age"],
                        "categories": {
                            "0 to 4 years": {"age": "age_000_004"},
                            "5 to 9 years": {"age": "age_005_009"},
                        },
                    }
                ],
            }
        )
    )

    assert (
        main(
            [
                "controls",
                "from-census-profile",
                str(profile_path),
                "--mapping",
                str(mapping_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert output_path.read_text() == (
        "margin,dimensions,geo,age,count\n"
        'age,"geo,age",1001,age_000_004,12\n'
        'age,"geo,age",1001,age_005_009,14\n'
    )


def test_inspects_census_profile_characteristics(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.csv"
    profile_path.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,Population,100\n"
        "1001,0 to 4 years,12\n"
        "1001,5 to 9 years,14\n"
        "1002,0 to 4 years,8\n"
    )

    rows = inspect_census_profile_characteristics(
        profile_path,
        characteristic_column="CHARACTERISTIC_NAME",
        count_column="C1_COUNT_TOTAL",
        search="years",
    )

    assert rows == [
        {
            "characteristic": "0 to 4 years",
            "example_count": "12",
            "rows": "2",
        },
        {
            "characteristic": "5 to 9 years",
            "example_count": "14",
            "rows": "1",
        },
    ]


def test_cli_inspects_census_profile_characteristics(tmp_path: Path, capsys) -> None:
    from synthpopcan.cli import main

    profile_path = tmp_path / "profile.csv"
    profile_path.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,Population,100\n"
        "1001,0 to 4 years,12\n"
    )

    assert (
        main(
            [
                "controls",
                "census-profile",
                "inspect",
                str(profile_path),
                "--search",
                "years",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "Census Profile Characteristics" in output
    assert "0 to 4 years" in output
    assert "12" in output


def test_builds_census_profile_age_template() -> None:
    template = census_profile_template("age5")

    assert template["geography"] == {"column": "GEO_CODE", "dimension": "geo"}
    assert template["characteristic_column"] == "CHARACTERISTIC_NAME"
    assert template["count_column"] == "C1_COUNT_TOTAL"
    assert template["margins"][0]["name"] == "age"
    assert template["margins"][0]["categories"]["0 to 4 years"] == {
        "age": "age_000_004"
    }


def test_cli_writes_census_profile_template(tmp_path: Path) -> None:
    from synthpopcan.cli import main

    output_path = tmp_path / "mapping.json"

    assert (
        main(
            [
                "controls",
                "census-profile",
                "template",
                "sex",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text())
    assert payload["margins"][0]["name"] == "sex"
    assert payload["margins"][0]["categories"] == {
        "Female": {"sex": "female"},
        "Male": {"sex": "male"},
    }
