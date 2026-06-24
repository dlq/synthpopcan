import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.exceptions import ClickException

from synthpopcan.controls import (
    ControlCell,
    build_wds_category_mapping_template,
    census_profile_template,
    find_wds_csv_member,
    format_count,
    inspect_census_profile_characteristics,
    inspect_wds_zip,
    read_category_mapping,
    read_census_profile_control_table,
    read_census_profile_mapping,
    read_control_margins,
    read_control_table,
    read_wds_control_table,
    values_are_numeric,
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


def test_normalized_controls_reject_invalid_rows(tmp_path: Path) -> None:
    no_dimensions = tmp_path / "no-dimensions.csv"
    invalid_count = tmp_path / "invalid-count.csv"
    duplicate = tmp_path / "duplicate.csv"
    no_count = tmp_path / "no-count.csv"
    no_dimensions.write_text("margin,dimensions,age,count\nage,,young,60\n")
    invalid_count.write_text("margin,dimensions,age,count\nage,age,young,bad\n")
    duplicate.write_text(
        "margin,dimensions,age,count\nage,age,young,60\nage,age,young,40\n"
    )
    no_count.write_text("margin,dimensions,age\nage,age,young\n")

    with pytest.raises(ValueError, match="row 2 has no dimensions"):
        read_control_table(no_dimensions)
    with pytest.raises(ValueError, match="row 2 has invalid count"):
        read_control_table(invalid_count)
    with pytest.raises(ValueError, match="duplicates target"):
        read_control_table(duplicate)
    with pytest.raises(ValueError, match="requires a count column"):
        read_control_table(no_count)


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


def test_wds_inspection_and_template_reject_invalid_inputs(tmp_path: Path) -> None:
    zip_path = tmp_path / "wds.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("table.csv", "GEO,VALUE\nCanada,100\n")

    with pytest.raises(ValueError, match="sample rows"):
        inspect_wds_zip(zip_path, sample_rows=0)
    with pytest.raises(ValueError, match="at least one dimension"):
        build_wds_category_mapping_template(zip_path, dimensions=())
    with pytest.raises(ValueError, match="known WDS mapping presets"):
        build_wds_category_mapping_template(
            zip_path,
            dimensions=("GEO",),
            preset="unknown",
        )
    with pytest.raises(ValueError, match="missing columns"):
        build_wds_category_mapping_template(zip_path, dimensions=("Age group",))


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


def test_cli_writes_wds_category_mapping_template_with_canonical_preset(
    tmp_path: Path,
) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    output_path = tmp_path / "categories.json"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "Age group,Sex,VALUE\n"
            "0 to 4 years,Female,100\n"
            "5 to 9 years,Male,105\n"
            "10 to 14 years,Another response,3\n",
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
                "--preset",
                "canonical",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    assert json.loads(output_path.read_text()) == {
        "Age group": {
            "0 to 4 years": "age_000_004",
            "5 to 9 years": "age_005_009",
            "10 to 14 years": "age_010_014",
        },
        "Sex": {
            "Another response": "",
            "Female": "female",
            "Male": "male",
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

    with pytest.raises(ClickException) as excinfo:
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
    message = str(excinfo.value)
    assert "unmapped category" in message
    assert "Next step:" in message
    assert "controls wds mapping-template" in message
    assert "--preset canonical" in message


def test_cli_fails_on_missing_wds_columns_with_inspection_next_step(
    tmp_path: Path,
) -> None:
    from synthpopcan.cli import main

    zip_path = tmp_path / "wds.zip"
    output_path = tmp_path / "controls.csv"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "table.csv",
            "Geography,VALUE\nCanada,100\n",
        )

    with pytest.raises(ClickException) as excinfo:
        main(
            [
                "controls",
                "from-wds",
                str(zip_path),
                "--dimensions",
                "GEO,Sex",
                "--count-column",
                "VALUE",
                "--out",
                str(output_path),
            ]
        )
    message = str(excinfo.value)
    assert "missing columns" in message
    assert "Next step:" in message
    assert "controls wds inspect" in message


def test_wds_control_table_rejects_invalid_rows_and_duplicate_targets(
    tmp_path: Path,
) -> None:
    no_dimensions = tmp_path / "wds-no-dimensions.zip"
    missing_column = tmp_path / "wds-missing-column.zip"
    duplicate = tmp_path / "wds-duplicate.zip"
    invalid_count = tmp_path / "wds-invalid-count.zip"
    with ZipFile(no_dimensions, "w") as archive:
        archive.writestr("table.csv", "GEO,VALUE\nCanada,100\n")
    with ZipFile(missing_column, "w") as archive:
        archive.writestr("table.csv", "Geography,VALUE\nCanada,100\n")
    with ZipFile(duplicate, "w") as archive:
        archive.writestr("table.csv", "GEO,VALUE\nCanada,100\nCanada,200\n")
    with ZipFile(invalid_count, "w") as archive:
        archive.writestr("table.csv", "GEO,VALUE\nCanada,not-a-number\n")

    with pytest.raises(ValueError, match="at least one dimension"):
        read_control_table_from_wds_for_test(no_dimensions, dimensions=())
    with pytest.raises(ValueError, match="missing columns"):
        read_control_table_from_wds_for_test(missing_column, dimensions=("GEO",))
    with pytest.raises(ValueError, match="duplicates target"):
        read_control_table_from_wds_for_test(duplicate, dimensions=("GEO",))
    with pytest.raises(ValueError, match="invalid count"):
        read_control_table_from_wds_for_test(invalid_count, dimensions=("GEO",))


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


def test_census_profile_controls_reject_bad_source_rows(tmp_path: Path) -> None:
    mapping_path = tmp_path / "mapping.json"
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
                        },
                    }
                ],
            }
        )
    )
    missing_column = tmp_path / "missing-column.csv"
    duplicate = tmp_path / "duplicate.csv"
    invalid_count = tmp_path / "invalid-count.csv"
    missing_column.write_text("GEO_CODE,CHARACTERISTIC_NAME\n1001,0 to 4 years\n")
    duplicate.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,0 to 4 years,12\n"
        "1001,0 to 4 years,14\n"
    )
    invalid_count.write_text(
        "GEO_CODE,CHARACTERISTIC_NAME,C1_COUNT_TOTAL\n"
        "1001,0 to 4 years,bad\n"
    )

    with pytest.raises(ValueError, match="missing columns"):
        read_census_profile_control_table(missing_column, mapping_path)
    with pytest.raises(ValueError, match="duplicates target"):
        read_census_profile_control_table(duplicate, mapping_path)
    with pytest.raises(ValueError, match="invalid count"):
        read_census_profile_control_table(invalid_count, mapping_path)


def test_census_profile_characteristic_inspection_rejects_bad_inputs(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile.csv"
    profile_path.write_text("GEO_CODE,CHARACTERISTIC_NAME\n1001,Population\n")

    with pytest.raises(ValueError, match="limit must be at least 1"):
        inspect_census_profile_characteristics(profile_path, limit=0)
    with pytest.raises(ValueError, match="missing columns"):
        inspect_census_profile_characteristics(profile_path)


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


def test_census_profile_template_accepts_overrides_and_rejects_unknown_names() -> None:
    template = census_profile_template(
        "sex",
        geography_column="ALT_GEO",
        geography_dimension="region",
        characteristic_column="CHAR",
        count_column="COUNT",
    )

    assert template["geography"] == {"column": "ALT_GEO", "dimension": "region"}
    assert template["characteristic_column"] == "CHAR"
    assert template["count_column"] == "COUNT"
    assert template["margins"][0]["dimensions"] == ["region", "sex"]
    with pytest.raises(ValueError, match="known Census Profile templates"):
        census_profile_template("unknown")


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


def test_category_mapping_validation_and_numeric_detection(tmp_path: Path) -> None:
    non_object = tmp_path / "non-object.json"
    bad_dimension = tmp_path / "bad-dimension.json"
    bad_value = tmp_path / "bad-value.json"
    non_object.write_text("[]")
    bad_dimension.write_text(json.dumps({"Age": []}))
    bad_value.write_text(json.dumps({"Age": {"0 to 4 years": 1}}))

    with pytest.raises(ValueError, match="must be a JSON object"):
        read_category_mapping(non_object)
    with pytest.raises(ValueError, match="map dimension names to objects"):
        read_category_mapping(bad_dimension)
    with pytest.raises(ValueError, match="values must be strings"):
        read_category_mapping(bad_value)
    assert values_are_numeric([]) is False
    assert values_are_numeric(["1", "2.5"]) is True
    assert values_are_numeric(["1", "not-a-number"]) is False
    assert format_count(1.25) == "1.25"


def test_census_profile_mapping_validation_errors(tmp_path: Path) -> None:
    cases = [
        ("[]", "must be a JSON object"),
        (
            {"characteristic_column": "CHAR", "count_column": "COUNT", "margins": []},
            "missing 'geography'",
        ),
        (
            {
                "geography": [],
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [],
            },
            "geography must be an object",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": 1,
                "count_column": "COUNT",
                "margins": [],
            },
            "must be strings",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [],
            },
            "non-empty list",
        ),
        (
            {
                "geography": {"column": "GEO"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"name": "age", "dimensions": ["geo"], "categories": {}}],
            },
            "geography is missing 'dimension'",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": 1},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"name": "age", "dimensions": ["geo"], "categories": {}}],
            },
            "column and dimension must be strings",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": ["bad"],
            },
            "margin 1 must be an object",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"dimensions": ["geo"], "categories": {}}],
            },
            "margin 1 is missing 'name'",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"name": 1, "dimensions": ["geo"], "categories": {}}],
            },
            "name must be text",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"name": "age", "dimensions": [1], "categories": {}}],
            },
            "dimensions must be text",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [{"name": "age", "dimensions": ["geo"], "categories": []}],
            },
            "categories must be an object",
        ),
        (
            {
                "geography": {"column": "GEO", "dimension": "geo"},
                "characteristic_column": "CHAR",
                "count_column": "COUNT",
                "margins": [
                    {"name": "age", "dimensions": ["geo"], "categories": {"x": []}}
                ],
            },
            "categories must map source labels to objects",
        ),
    ]

    for index, (payload, message) in enumerate(cases):
        mapping_path = tmp_path / f"mapping-{index}.json"
        mapping_path.write_text(
            payload if isinstance(payload, str) else json.dumps(payload)
        )
        with pytest.raises(ValueError, match=message):
            read_census_profile_mapping(mapping_path)


def test_wds_csv_member_detection_rejects_missing_or_ambiguous_csvs(
    tmp_path: Path,
) -> None:
    no_csv = tmp_path / "no-csv.zip"
    multiple_csv = tmp_path / "multiple-csv.zip"
    with ZipFile(no_csv, "w") as archive:
        archive.writestr("readme.txt", "no table")
    with ZipFile(multiple_csv, "w") as archive:
        archive.writestr("one.csv", "GEO,VALUE\nCanada,1\n")
        archive.writestr("two.csv", "GEO,VALUE\nCanada,1\n")

    with ZipFile(no_csv) as archive:
        with pytest.raises(ValueError, match="does not contain a CSV"):
            find_wds_csv_member(archive)
    with ZipFile(multiple_csv) as archive:
        with pytest.raises(ValueError, match="multiple CSV"):
            find_wds_csv_member(archive)


def read_control_table_from_wds_for_test(
    path: Path,
    *,
    dimensions: tuple[str, ...],
):
    return read_wds_control_table(
        path,
        dimensions=dimensions,
        count_column="VALUE",
        margin_name="wds",
    )
