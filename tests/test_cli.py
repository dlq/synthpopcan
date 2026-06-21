import pytest
from click import ClickException

from synthpopcan.cli import main


def test_cli_smoke() -> None:
    assert main([]) == 0


def test_controls_validate_accepts_long_control_csv(tmp_path) -> None:
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,age,sex,count\n"
        "age,age,young,,60\n"
        "age,age,old,,40\n"
        "sex,sex,,F,50\n"
        "sex,sex,,M,50\n"
    )

    assert main(["controls", "validate", str(controls_path)]) == 0


def test_tree_commands_are_visible_in_help(capsys) -> None:
    assert main(["tree", "--help"]) == 0

    output = capsys.readouterr().out
    assert "Tree-based synthetic population generator" in output
    assert "train" in output
    assert "generate" in output


def test_tree_train_is_clear_placeholder() -> None:
    with pytest.raises(
        ClickException, match="Tree generator training is not implemented"
    ):
        main(["tree", "train"])


def test_tree_generate_is_clear_placeholder() -> None:
    with pytest.raises(
        ClickException, match="Tree generator output is not implemented"
    ):
        main(["tree", "generate"])
