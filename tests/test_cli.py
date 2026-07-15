from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click import ClickException

from synthpopcan.cli import (
    _format_model_availability,
    cli,
    main,
    resolve_data_root,
)
from synthpopcan.cli_geo import (
    _coerce_float,
    _format_surface_recommendation,
)


def test_cli_smoke(capsys) -> None:
    assert main([]) == 0
    assert "Choose a Workflow" in capsys.readouterr().out


def test_cli_command_tree_is_coherent() -> None:
    assert "tree" not in cli.commands
    assert set(cli.commands) == {
        "controls",
        "data",
        "geo",
        "guide",
        "ipf",
        "microdata",
        "models",
        "serve",
        "statcan",
        "validate",
    }
    assert set(cli.commands["models"].commands) == {
        "build",
        "fetch",
        "generate",
        "list",
        "remove",
        "show",
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("web_app_ok", "web app, CLI, or Python API"),
        ("cli_or_python_api", "CLI or Python API"),
        ("future_surface", "future_surface"),
    ],
)
def test_format_surface_recommendation(value: str, expected: str) -> None:
    assert _format_surface_recommendation(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(object(), 0.0), ("bad", 0.0), ("2.5", 2.5)]
)
def test_coerce_float_handles_report_values(value: object, expected: float) -> None:
    assert _coerce_float(value) == expected


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

    assert main(["controls", "check", str(controls_path)]) == 0


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
    assert "synthpopcan models fetch" in output
    assert "synthpopcan models show" in output
    assert "synthpopcan models generate" in output
    assert "synthpopcan validate linked" in output


def test_cli_models_list_marks_downloadable_models(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))

    assert main(["models", "list", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    models = {m["id"]: m for m in payload["models"]}
    demo = models["demo-linked-household-person"]
    assert demo["distribution"] == "bundled"
    assert demo["installed"] is True
    montreal = models["montreal-cma-2016-all-fields"]
    assert montreal["distribution"] == "download"
    assert montreal["installed"] is False
    quebec = models["quebec-2016-all-fields"]
    assert quebec["distribution"] == "download"
    assert quebec["installed"] is False


def test_cli_models_list_table_stays_compact(capsys) -> None:
    assert main(["models", "list"]) == 0

    output = capsys.readouterr().out
    assert "Package ID" in output
    assert "Geography" in output
    assert "Known limitations" not in output
    assert len(output.splitlines()) < 100


def test_cli_models_show_reports_detailed_metadata(capsys) -> None:
    assert main(["models", "show", "demo-linked-household-person"]) == 0

    output = capsys.readouterr().out
    assert "Census vintage" in output
    assert "Asset release" in output
    assert "v0.4.0" in output
    assert "Known limitations" in output


def test_cli_models_show_rejects_unknown_id() -> None:
    with pytest.raises(ClickException, match="unknown model package"):
        main(["models", "show", "missing-model"])


def test_cli_models_fetch_uses_model_cache(monkeypatch, tmp_path, capsys) -> None:
    fetched_paths: list[Path] = []

    def fake_fetch_model_package(model_id: str, **kwargs: object) -> Path:
        callback = kwargs.get("progress_callback")
        if callable(callback):
            callback(1, 1)
        path = tmp_path / f"{model_id}.json"
        fetched_paths.append(path)
        return path

    monkeypatch.setattr("synthpopcan.cli.fetch_model_package", fake_fetch_model_package)

    assert main(["models", "fetch", "montreal-cma-2016-all-fields"]) == 0

    output = capsys.readouterr()
    assert fetched_paths == [tmp_path / "montreal-cma-2016-all-fields.json"]
    assert "Model package ready" in output.err
    assert output.out.strip() == str(fetched_paths[0])


def test_model_build_commands_are_visible_in_help(capsys) -> None:
    assert main(["models", "build", "--help"]) == 0

    output = capsys.readouterr().out
    assert "Train, audit, and package model artifacts" in output
    assert "train" in output
    assert "train-linked" in output
    assert "generate" in output
    assert "prepare-release" in output
    assert "package-linked" in output


def test_tree_train_help_shows_core_options(capsys) -> None:
    assert main(["models", "build", "train", "--help"]) == 0

    output = capsys.readouterr().out
    assert "--target-columns" in output
    assert "--conditioning-columns" in output
    assert "--min-support" in output


def test_tree_generate_help_shows_core_options(capsys) -> None:
    assert main(["models", "build", "generate", "--help"]) == 0

    output = capsys.readouterr().out
    assert "--rows" in output
    assert "--condition" in output
    assert "--out" in output


# ---------------------------------------------------------------------------
# Helpers shared by geo tests (from test_coverage_gaps.py)
# ---------------------------------------------------------------------------

_PROFILE_FIELDNAMES = [
    "GEO_LEVEL",
    "GEO_CODE (POR)",
    "Member ID: Profile of Census Tracts (2247)",
    "Dim: Sex (3): Member ID: [1]: Total - Sex",
]


def _write_profile(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_PROFILE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _profile_row(
    geo_level: str, geo_code: str, member_id: str, value: str
) -> dict[str, str]:
    return {
        "GEO_LEVEL": geo_level,
        "GEO_CODE (POR)": geo_code,
        "Member ID: Profile of Census Tracts (2247)": member_id,
        "Dim: Sex (3): Member ID: [1]: Total - Sex": value,
    }


def _minimal_profile(path: Path) -> None:
    """Write a minimal two-geography profile valid for CT (GEO_LEVEL 2)."""
    rows = [
        _profile_row("2", "G1", "52", "10"),
        _profile_row("2", "G1", "53", "20"),
        _profile_row("2", "G1", "54", "30"),
        _profile_row("2", "G1", "55", "15"),
        _profile_row("2", "G1", "56", "5"),
        _profile_row("2", "G1", "1618", "50"),
        _profile_row("2", "G1", "1619", "30"),
        _profile_row("2", "G2", "52", "40"),
        _profile_row("2", "G2", "53", "60"),
        _profile_row("2", "G2", "1618", "70"),
        _profile_row("2", "G2", "1619", "30"),
    ]
    _write_profile(path, rows)


# ---------------------------------------------------------------------------
# cli_geo.py — extract-controls without --candidates (lines 531, 611-612)
# ---------------------------------------------------------------------------


def test_extract_controls_no_candidates_uses_geo_column_default_name(
    tmp_path, monkeypatch, capsys
) -> None:
    """Line 531: controls_out defaults to '<geo-column>-controls-<target>.csv'."""
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    # Work from tmp_path so the default output file lands there.
    monkeypatch.chdir(tmp_path)

    result = main(
        [
            "geo",
            "controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ct",
            "--target",
            "100",
        ]
    )

    assert result == 0
    # The default output path should follow the geo-column-based pattern.
    assert (tmp_path / "ct-controls-100.csv").exists()


def test_extract_controls_no_candidates_prints_synthesize_from_package_next_step(
    tmp_path, monkeypatch, capsys
) -> None:
    """Lines 611-612: no candidates; else branch prints synthesize-from-package."""
    profile = tmp_path / "profile.csv"
    _minimal_profile(profile)
    monkeypatch.chdir(tmp_path)

    main(
        [
            "geo",
            "controls",
            "--profile",
            str(profile),
            "--geo-column",
            "ct",
            "--target",
            "100",
        ]
    )

    output = capsys.readouterr().out
    assert "geo synthesize" in output


# ---------------------------------------------------------------------------
# cli_geo.py — synthesize-from-package error branches (lines 830-836)
# ---------------------------------------------------------------------------


def test_synthesize_from_package_missing_file_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 830-831: non-existent package path raises ClickException."""
    missing = tmp_path / "nonexistent-package.json"

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize",
                str(missing),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


def test_synthesize_from_package_invalid_json_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 830-831: invalid JSON in package path raises ClickException."""
    bad_package = tmp_path / "bad.json"
    bad_package.write_text("not valid json{{{")

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize",
                str(bad_package),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


def test_synthesize_from_package_not_publishable_candidate_raises_click_exception(
    tmp_path,
) -> None:
    """Lines 835-836: package without publishable_candidate=true raises ClickException.

    A minimal package JSON that reads but fails validation.
    """
    # A minimal package JSON that reads without error but fails validation.
    package = tmp_path / "package.json"
    package.write_text(
        json.dumps(
            {
                "version": "1",
                "privacy": {"publishable_candidate": False},
                "household_model": {},
                "person_model": {},
            }
        )
    )

    with pytest.raises(ClickException):
        main(
            [
                "geo",
                "synthesize",
                str(package),
                "--households",
                "10",
                "--controls",
                str(tmp_path / "controls.csv"),
                "--geo-dimension",
                "ct",
                "--geo-column",
                "ct",
                "--households-out",
                str(tmp_path / "hh.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


@pytest.mark.parametrize(
    "command_template,needs_controls,needs_out",
    [
        (
            [
                "ipf",
                "check-inputs",
                "--seed",
                "{missing}",
                "--controls",
                "{controls}",
            ],
            True,
            False,
        ),
        (["ipf", "suggest-controls", "--seed", "{missing}"], False, False),
        (
            [
                "ipf",
                "fit",
                "--seed",
                "{missing}",
                "--controls",
                "{controls}",
                "--out",
                "{out}",
            ],
            True,
            True,
        ),
        (
            [
                "microdata",
                "inspect",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
            ],
            False,
            False,
        ),
        (
            [
                "microdata",
                "check-seed",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "household",
                "--columns",
                "HHSIZE",
            ],
            False,
            False,
        ),
        (
            [
                "microdata",
                "suggest-tree-columns",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
            ],
            False,
            False,
        ),
        (
            [
                "microdata",
                "tree-geography-feasibility",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
                "--geo-column",
                "PR",
                "--household-block",
                "HHSIZE",
                "--person-block",
                "AGEGRP",
            ],
            False,
            False,
        ),
        (
            [
                "microdata",
                "export-seed",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "HHSIZE",
                "--out",
                "{out}",
            ],
            False,
            True,
        ),
        (
            [
                "microdata",
                "export-training",
                "{missing}",
                "--input-format",
                "statcan-2016-hierarchical",
                "--level",
                "person",
                "--target-columns",
                "AGEGRP",
                "--conditioning-columns",
                "HHSIZE",
                "--out",
                "{out}",
            ],
            False,
            True,
        ),
    ],
)
def test_cli_missing_input_files_raise_click_exception(
    tmp_path,
    command_template: list[str],
    needs_controls: bool,
    needs_out: bool,
) -> None:
    missing = tmp_path / "missing.csv"
    controls = tmp_path / "controls.csv"
    if needs_controls:
        controls.write_text(
            "margin,dimensions,age,count\nage,age,young,50\nage,age,old,50\n"
        )
    out = tmp_path / "out.csv"
    replacements = {
        "{missing}": str(missing),
        "{controls}": str(controls),
        "{out}": str(out),
    }
    command = [replacements.get(part, part) for part in command_template]

    with pytest.raises(ClickException):
        main(command)
    if needs_out:
        assert not out.exists()


def test_ipf_fit_nonconvergence_raises_click_exception(tmp_path) -> None:
    """Lines 179-180: non-converged IPF without --allow-nonconverged raises an error.

    Uses conflicting margins to force non-convergence.
    """
    seed = tmp_path / "seed.csv"
    # Multi-dimensional seed so conflicting margins cause non-convergence.
    seed.write_text("age,sex\nyoung,M\nyoung,F\nold,M\n")

    controls = tmp_path / "controls.csv"
    # Conflicting margins: almost all old + almost all F, but only one old,M row.
    controls.write_text(
        "margin,dimensions,age,sex,count\n"
        "age,age,young,,1\n"
        "age,age,old,,9999\n"
        "sex,sex,,M,5\n"
        "sex,sex,,F,9995\n"
    )
    out = tmp_path / "out.csv"

    with pytest.raises(ClickException):
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed),
                "--controls",
                str(controls),
                "--out",
                str(out),
                "--max-iterations",
                "2",
                "--tolerance",
                "1e-100",
            ]
        )


# ---------------------------------------------------------------------------
# CLI (cli.py) gaps (from test_coverage_gaps2.py)
# ---------------------------------------------------------------------------


def test_cli_models_list_table_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    assert main(["models", "list"]) == 0


def test_cli_models_fetch_key_error_raises_click_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        "synthpopcan.cli.fetch_model_package",
        lambda *a, **kw: (_ for _ in ()).throw(KeyError("demo")),
    )
    with pytest.raises(click.ClickException) as exc_info:
        main(["models", "fetch", "demo"])
    assert "unknown model package" in exc_info.value.format_message()


def test_cli_models_fetch_oserror_raises_click_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        "synthpopcan.cli.fetch_model_package",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("network")),
    )
    with pytest.raises(click.ClickException) as exc_info:
        main(["models", "fetch", "demo"])
    assert "could not fetch" in exc_info.value.format_message()


def test_cli_models_fetch_value_error_raises_click_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        "synthpopcan.cli.fetch_model_package",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("bad")),
    )
    with pytest.raises(click.ClickException) as exc_info:
        main(["models", "fetch", "demo"])
    assert "bad" in exc_info.value.format_message()


def test_cli_models_remove_not_cached_prints_no_cached() -> None:
    with patch("synthpopcan.cli.remove_cached_model", return_value=False):
        with patch("synthpopcan.cli.print_success") as mock_print:
            assert main(["models", "remove", "any-model"]) == 0
            assert "No cached downloadable" in mock_print.call_args[0][0]


def test_cli_models_remove_cached_prints_removed() -> None:
    with patch("synthpopcan.cli.remove_cached_model", return_value=True):
        with patch("synthpopcan.cli.print_success") as mock_print:
            assert main(["models", "remove", "any-model"]) == 0
            assert "Removed cached" in mock_print.call_args[0][0]


def test_cli_models_remove_unknown_raises_click_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        "synthpopcan.cli.remove_cached_model",
        lambda model_id: (_ for _ in ()).throw(KeyError(model_id)),
    )
    with pytest.raises(click.ClickException) as exc_info:
        main(["models", "remove", "nonexistent-id"])
    assert "unknown model package" in exc_info.value.format_message()


def test_format_model_availability_bundled() -> None:
    assert _format_model_availability({"distribution": "bundled"}) == "Bundled"


def test_format_model_availability_installed() -> None:
    assert (
        _format_model_availability({"distribution": "download", "installed": True})
        == "Downloaded"
    )


def test_format_model_availability_not_installed() -> None:
    result = _format_model_availability(
        {"distribution": "download", "installed": False}
    )
    assert "Download with" in result


def test_cli_validate_linked_output_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.validate_linked_population", side_effect=OSError("boom")
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "validate",
                    "linked",
                    str(tmp_path),
                ]
            )


def test_cli_validate_tree_output_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.build_tree_output_validation_report",
        side_effect=OSError("boom"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "validate",
                    "model",
                    "--generated",
                    str(tmp_path / "gen.csv"),
                    "--training",
                    str(tmp_path / "train.csv"),
                    "--target-columns",
                    "age",
                ]
            )


def test_cli_validate_tree_output_value_error(tmp_path) -> None:
    gen = tmp_path / "gen.csv"
    train = tmp_path / "train.csv"
    gen.write_text("age\nadult\n")
    train.write_text("age\nadult\n")
    with patch(
        "synthpopcan.cli.build_tree_output_validation_report",
        side_effect=ValueError("bad"),
    ):
        with pytest.raises(click.ClickException) as exc_info:
            main(
                [
                    "validate",
                    "model",
                    "--generated",
                    str(gen),
                    "--training",
                    str(train),
                    "--target-columns",
                    "age",
                ]
            )
        assert "bad" in exc_info.value.format_message()


def test_cli_data_inspect_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.inspect_source_root", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["data", "inspect", str(tmp_path)])


def test_cli_data_example_writes_public_ipf_files(tmp_path) -> None:
    out_dir = tmp_path / "ipf-example"

    assert main(["data", "example", "ipf", "--out-dir", str(out_dir)]) == 0
    assert (out_dir / "seed.csv").read_text().splitlines()[0] == (
        "PP_ID,AGEGRP,SEX,WEIGHT"
    )
    assert (out_dir / "controls.csv").read_text().splitlines()[0] == (
        "margin,dimensions,AGEGRP,SEX,count"
    )

    with pytest.raises(click.ClickException, match="already exist"):
        main(["data", "example", "ipf", "--out-dir", str(out_dir)])

    assert (
        main(
            [
                "data",
                "example",
                "ipf",
                "--out-dir",
                str(out_dir),
                "--force",
            ]
        )
        == 0
    )


def test_cli_data_sample_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_source_sample", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["data", "sample", str(tmp_path / "file.csv"), "--allow-private"])


def test_cli_controls_validate_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_margins", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["controls", "check", str(tmp_path / "controls.csv")])


def test_cli_controls_validate_value_error(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_margins", side_effect=ValueError("bad")):
        with pytest.raises(click.ClickException) as exc_info:
            main(["controls", "check", str(tmp_path / "controls.csv")])
        assert "bad" in exc_info.value.format_message()


def test_cli_controls_from_csv_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_table", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(
                [
                    "controls",
                    "from-csv",
                    str(tmp_path / "source.csv"),
                    "--out",
                    str(tmp_path / "out.csv"),
                ]
            )


def test_cli_controls_from_csv_value_error(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_table", side_effect=ValueError("bad")):
        with pytest.raises(click.ClickException) as exc_info:
            main(
                [
                    "controls",
                    "from-csv",
                    str(tmp_path / "source.csv"),
                    "--out",
                    str(tmp_path / "out.csv"),
                ]
            )
        assert "bad" in exc_info.value.format_message()


def test_cli_controls_from_wds_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_wds_control_table", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(
                [
                    "controls",
                    "from-wds",
                    str(tmp_path / "source.zip"),
                    "--dimensions",
                    "AGE",
                    "--out",
                    str(tmp_path / "out.csv"),
                ]
            )


def test_cli_controls_wds_inspect_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.inspect_wds_zip", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["controls", "wds", "inspect", str(tmp_path / "source.zip")])


def test_cli_controls_wds_mapping_template_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.build_wds_category_mapping_template",
        side_effect=OSError("boom"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "controls",
                    "wds",
                    "mapping-template",
                    str(tmp_path / "source.zip"),
                    "--dimensions",
                    "AGE",
                    "--out",
                    str(tmp_path / "mapping.json"),
                ]
            )


def test_cli_controls_from_census_profile_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.read_census_profile_control_table", side_effect=OSError("boom")
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "controls",
                    "from-census-profile",
                    str(tmp_path / "profile.csv"),
                    "--mapping",
                    str(tmp_path / "mapping.json"),
                    "--out",
                    str(tmp_path / "out.csv"),
                ]
            )


def test_cli_controls_census_profile_inspect_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.inspect_census_profile_characteristics",
        side_effect=OSError("boom"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "controls",
                    "census-profile",
                    "inspect",
                    str(tmp_path / "profile.csv"),
                ]
            )


def test_cli_statcan_wds_fetch_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.fetch_wds_table", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(
                [
                    "statcan",
                    "wds",
                    "fetch",
                    "12345678",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


def test_cli_statcan_wds_fetch_value_error(tmp_path) -> None:
    with patch("synthpopcan.cli.fetch_wds_table", side_effect=ValueError("bad")):
        with pytest.raises(click.ClickException) as exc_info:
            main(
                [
                    "statcan",
                    "wds",
                    "fetch",
                    "12345678",
                    "--out-dir",
                    str(tmp_path),
                ]
            )
        assert "bad" in exc_info.value.format_message()


def test_cli_statcan_wds_search_oserror() -> None:
    with patch(
        "synthpopcan.cli.search_wds_tables_for_cli", side_effect=OSError("boom")
    ):
        with pytest.raises(click.ClickException):
            main(["statcan", "wds", "search", "age"])


def test_cli_statcan_wds_search_value_error() -> None:
    with patch(
        "synthpopcan.cli.search_wds_tables_for_cli", side_effect=ValueError("bad")
    ):
        with pytest.raises(click.ClickException) as exc_info:
            main(["statcan", "wds", "search", "age"])
        assert "bad" in exc_info.value.format_message()


def test_cli_statcan_wds_metadata_oserror() -> None:
    with patch("synthpopcan.cli.fetch_wds_metadata", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["statcan", "wds", "metadata", "12345678"])


def test_cli_statcan_wds_metadata_value_error() -> None:
    with patch("synthpopcan.cli.fetch_wds_metadata", side_effect=ValueError("bad")):
        with pytest.raises(click.ClickException) as exc_info:
            main(["statcan", "wds", "metadata", "12345678"])
        assert "bad" in exc_info.value.format_message()


def test_cli_statcan_wds_explain_oserror() -> None:
    with patch("synthpopcan.cli.fetch_wds_metadata", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["statcan", "wds", "explain", "12345678"])


def test_cli_statcan_census_profile_fetch_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.fetch_census_profile_2016", side_effect=OSError("boom")
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "statcan",
                    "census-profile",
                    "fetch",
                    "--geo-level",
                    "CT",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


def test_cli_statcan_census_profile_fetch_value_error(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.fetch_census_profile_2016", side_effect=ValueError("bad")
    ):
        with pytest.raises(click.ClickException) as exc_info:
            main(
                [
                    "statcan",
                    "census-profile",
                    "fetch",
                    "--geo-level",
                    "CT",
                    "--out-dir",
                    str(tmp_path),
                ]
            )
        assert "bad" in exc_info.value.format_message()


# ---------------------------------------------------------------------------
# Additional targeted gap tests (from test_coverage_gaps2.py end section)
# ---------------------------------------------------------------------------


def test_cli_ipf_check_inputs_value_error_on_controls_raises_click_exception(
    tmp_path,
) -> None:
    seed = tmp_path / "seed.csv"
    seed.write_text("age,weight\nyoung,1\n")
    controls = tmp_path / "controls.csv"
    controls.write_text("not a valid controls file\n")
    with patch(
        "synthpopcan.cli_ipf.read_control_table", side_effect=ValueError("bad controls")
    ):
        with pytest.raises(click.ClickException) as exc_info:
            main(
                [
                    "ipf",
                    "check-inputs",
                    "--seed",
                    str(seed),
                    "--controls",
                    str(controls),
                ]
            )
        assert "bad controls" in exc_info.value.format_message()


def test_cli_ipf_expand_oserror_raises_click_exception(tmp_path) -> None:
    with pytest.raises(click.ClickException):
        main(
            [
                "ipf",
                "expand",
                "--weights",
                str(tmp_path / "missing-weights.csv"),
                "--out",
                str(tmp_path / "out.csv"),
            ]
        )


def test_cli_controls_from_wds_write_oserror_raises_click_exception(tmp_path) -> None:
    from synthpopcan.controls import ControlTable

    dummy_table = ControlTable(margins=(), dimensions=())
    with patch("synthpopcan.cli.read_wds_control_table", return_value=dummy_table):
        with patch(
            "synthpopcan.cli.write_control_table", side_effect=OSError("disk full")
        ):
            with pytest.raises(click.ClickException):
                main(
                    [
                        "controls",
                        "from-wds",
                        str(tmp_path / "source.zip"),
                        "--dimensions",
                        "AGE",
                        "--count-column",
                        "count",
                        "--out",
                        str(tmp_path / "out.csv"),
                    ]
                )


_MICRODATA_IPF_FIXTURES = (
    Path(__file__).parent / "fixtures" / "workflows" / "microdata_ipf"
)


def test_doc_example_installation_quick_getting_started(tmp_path) -> None:
    """Verify the Quick Getting Started commands from docs/installation.md run."""
    hierarchical = _MICRODATA_IPF_FIXTURES / "hierarchical.csv"
    controls = _MICRODATA_IPF_FIXTURES / "controls.csv"
    seed = tmp_path / "seed.csv"
    weights = tmp_path / "weights.csv"
    report = tmp_path / "fit-report.json"

    assert (
        main(
            [
                "microdata",
                "export-seed",
                str(hierarchical),
                "--input-format",
                "statcan-2016-hierarchical",
                "--columns",
                "AGEGRP,SEX",
                "--out",
                str(seed),
            ]
        )
        == 0
    )
    assert seed.exists()

    assert (
        main(
            [
                "ipf",
                "check-inputs",
                "--seed",
                str(seed),
                "--controls",
                str(controls),
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "ipf",
                "fit",
                "--seed",
                str(seed),
                "--controls",
                str(controls),
                "--weight-column",
                "WEIGHT",
                "--out",
                str(weights),
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert weights.exists()
    assert report.exists()

    assert main(["ipf", "report", str(report)]) == 0

    assert (
        main(
            [
                "validate",
                "ipf",
                "--population",
                str(weights),
                "--controls",
                str(controls),
                "--kind",
                "weights",
            ]
        )
        == 0
    )
