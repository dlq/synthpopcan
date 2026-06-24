from pathlib import Path

from synthpopcan.cli import main, resolve_data_root


def test_cli_smoke() -> None:
    assert main([]) == 0


def test_resolve_data_root_defaults_to_data(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_DATA_ROOT", raising=False)

    assert resolve_data_root(None) == Path("data")


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


def test_guide_command_shows_web_app_workflow_choices(capsys) -> None:
    assert main(["guide"]) == 0

    output = capsys.readouterr().out
    assert "Choose a Workflow" in output
    assert "IPF from margin tables" in output
    assert "Generate from existing model" in output
    assert "synthpopcan guide ipf" in output
    assert "synthpopcan guide model" in output


def test_guide_ipf_matches_beginner_web_flow(capsys) -> None:
    assert main(["guide", "ipf"]) == 0

    output = capsys.readouterr().out
    assert "IPF from Margin Tables" in output
    assert "Setup Path" in output
    assert "Command or Next Step" in output
    assert "Use a demo or make templates" in output
    assert "Generate from a StatCan table" in output
    assert "Inspect product" in output
    assert "synthpopcan statcan wds search" in output
    assert "synthpopcan controls from-wds" in output
    assert "synthpopcan ipf fit" in output


def test_guide_model_matches_beginner_web_flow(capsys) -> None:
    assert main(["guide", "model"]) == 0

    output = capsys.readouterr().out
    assert "Generate from Existing Model" in output
    assert "Setup Path" in output
    assert "Command or Next Step" in output
    assert "Use premade model" in output
    assert "Inspect selected model" in output
    assert "Generate rows" in output
    assert "synthpopcan tree inspect-package" in output
    assert "synthpopcan tree generate-from-package" in output
    assert "synthpopcan validate linked-output" in output


def test_tree_commands_are_visible_in_help(capsys) -> None:
    assert main(["tree", "--help"]) == 0

    output = capsys.readouterr().out
    assert "Tree-based synthetic population generator" in output
    assert "train" in output
    assert "train-linked" in output
    assert "generate" in output
    assert "prepare-model-release" in output
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
