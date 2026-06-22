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
    assert "train-linked" in output
    assert "generate" in output
    assert "package-linked-models" in output


def test_tree_train_help_shows_core_options(capsys) -> None:
    assert main(["tree", "train", "--help"]) == 0

    output = capsys.readouterr().out
    assert "--target-columns" in output
    assert "--conditioning-columns" in output
    assert "--min-support" in output


def test_tree_generate_help_shows_core_options(capsys) -> None:
    assert main(["tree", "generate", "--help"]) == 0

    output = capsys.readouterr().out
    assert "--rows" in output
    assert "--condition" in output
    assert "--out" in output
