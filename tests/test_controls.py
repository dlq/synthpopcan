from pathlib import Path

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
