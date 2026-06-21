from pathlib import Path
from zipfile import ZipFile

import pytest

from synthpopcan.controls import ControlCell, read_control_margins, read_control_table


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


def test_cli_normalizes_controls_from_csv(tmp_path: Path) -> None:
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
