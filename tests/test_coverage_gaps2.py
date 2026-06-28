"""Tests targeting remaining coverage gaps across cli, cli_tree, small_area_synthesis,
models, ipf, tree, microdata, controls, and cli_output."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

import synthpopcan.models as models
from synthpopcan.cli import (
    _format_model_availability,
    _format_model_catalogue_summary,
    main,
)
from synthpopcan.cli_tree import (
    _format_audit_passed,
    _format_default_generation,
    _format_level,
    _format_model_type,
    _format_package_catalogue_summary,
    _format_release_class,
    _format_tree_file_error,
    _format_tree_value_error,
    _read_package_path_or_id,
)
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.ipf import IPFMargin, NumpyIPFIndex, fit_ipf_numpy
from synthpopcan.microdata import SeedSample, resolve_tree_column_block_pair
from synthpopcan.small_area_synthesis import (
    _ordered_fieldnames,
    _subsample_candidates,
    _write_csv_rows,
    _write_realized_population_to_csv,
    _write_weights_csv,
    calibrate_linked_household_csvs,
    controls_by_geography,
    fit_households_by_geography,
    realize_linked_geography_population,
)
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyOutcome,
    FrequencyTreeModel,
    TreeModelSpec,
    generate_cart_rows,
    generate_frequency_rows,
    generate_linked_population_to_csv,
    iter_cart_rows,
)

# ---------------------------------------------------------------------------
# CLI (cli.py) gaps
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


def test_cli_models_path_unknown_id_raises_click_exception() -> None:
    with pytest.raises(click.ClickException) as exc_info:
        main(["models", "path", "nonexistent-id"])
    assert "unknown model package" in exc_info.value.format_message()


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


def test_format_model_catalogue_summary_minimal() -> None:
    result = _format_model_catalogue_summary({"name": "My Model"})
    assert "My Model" in result


def test_format_model_catalogue_summary_with_size_bytes() -> None:
    result = _format_model_catalogue_summary({"name": "Model", "size_bytes": 1048576})
    assert "MB" in result


def test_format_model_catalogue_summary_with_default_generation_households_and_conditions() -> (
    None
):
    result = _format_model_catalogue_summary(
        {
            "name": "Model",
            "default_generation": {"households": 1000, "conditions": "age=young"},
        }
    )
    assert "Default:" in result
    assert "1000 households" in result
    assert "age=young" in result


def test_format_model_catalogue_summary_with_default_generation_households_only() -> (
    None
):
    result = _format_model_catalogue_summary(
        {
            "name": "Model",
            "default_generation": {"households": 500},
        }
    )
    assert "Default:" in result
    assert "500 households" in result


def test_cli_validate_linked_output_oserror(tmp_path) -> None:
    with patch(
        "synthpopcan.cli.validate_linked_population", side_effect=OSError("boom")
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "validate",
                    "linked-output",
                    "--households",
                    str(tmp_path / "h.csv"),
                    "--persons",
                    str(tmp_path / "p.csv"),
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
                    "tree-output",
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
                    "tree-output",
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


def test_cli_data_sample_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_source_sample", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["data", "sample", str(tmp_path / "file.csv"), "--allow-private"])


def test_cli_controls_validate_oserror(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_margins", side_effect=OSError("boom")):
        with pytest.raises(click.ClickException):
            main(["controls", "validate", str(tmp_path / "controls.csv")])


def test_cli_controls_validate_value_error(tmp_path) -> None:
    with patch("synthpopcan.cli.read_control_margins", side_effect=ValueError("bad")):
        with pytest.raises(click.ClickException) as exc_info:
            main(["controls", "validate", str(tmp_path / "controls.csv")])
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
                    "--year",
                    "2016",
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
                    "--year",
                    "2016",
                    "--geo-level",
                    "CT",
                    "--out-dir",
                    str(tmp_path),
                ]
            )
        assert "bad" in exc_info.value.format_message()


# ---------------------------------------------------------------------------
# CLI tree (cli_tree.py) gaps
# ---------------------------------------------------------------------------


def test_cli_tree_train_ioerror_raises_click_exception(tmp_path) -> None:
    source = tmp_path / "training.csv"
    source.write_text("geo,age_group,sex\nQC,adult,F\n")
    out = tmp_path / "model.json"
    with patch(
        "synthpopcan.cli_tree.read_tree_training_sample",
        side_effect=OSError("disk error"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "tree",
                    "train",
                    str(source),
                    "--level",
                    "person",
                    "--target-columns",
                    "age_group",
                    "--conditioning-columns",
                    "geo",
                    "--out",
                    str(out),
                ]
            )


def test_cli_tree_train_linked_ioerror_raises_click_exception(tmp_path) -> None:
    source = tmp_path / "seed.csv"
    source.write_text("dummy\n")
    with patch(
        "synthpopcan.cli_tree.read_statcan_2016_hierarchical_seed_sample",
        side_effect=OSError("disk error"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "tree",
                    "train-linked",
                    str(source),
                    "--household-target-columns",
                    "household_size",
                    "--household-conditioning-columns",
                    "geo",
                    "--person-target-columns",
                    "age_group",
                    "--person-conditioning-columns",
                    "geo,household_size",
                    "--household-model-out",
                    str(tmp_path / "hh.json"),
                    "--person-model-out",
                    str(tmp_path / "p.json"),
                    "--manifest-out",
                    str(tmp_path / "manifest.json"),
                ]
            )


def test_cli_tree_list_packages_ioerror_raises_exception() -> None:
    with patch(
        "synthpopcan.cli_tree.model_catalogue", side_effect=OSError("disk error")
    ):
        with pytest.raises((click.ClickException, OSError)):
            main(["tree", "list-packages"])


def test_cli_tree_list_packages_table_output() -> None:
    assert main(["tree", "list-packages"]) == 0


def test_cli_tree_generate_from_package_ioerror_raises_click_exception(
    tmp_path,
) -> None:
    with patch(
        "synthpopcan.cli_tree._read_package_path_or_id",
        side_effect=OSError("disk error"),
    ):
        with pytest.raises(click.ClickException):
            main(
                [
                    "tree",
                    "generate-from-package",
                    "some-package-id",
                    "--households",
                    "5",
                    "--households-out",
                    str(tmp_path / "hh.csv"),
                    "--persons-out",
                    str(tmp_path / "p.csv"),
                ]
            )


def test_cli_tree_audit_model_ioerror_raises_click_exception(tmp_path) -> None:
    with pytest.raises(click.ClickException):
        main(["tree", "audit-model", str(tmp_path / "missing-model.json")])


def test_cli_tree_package_model_read_ioerror_raises_click_exception(tmp_path) -> None:
    with pytest.raises(click.ClickException):
        main(
            [
                "tree",
                "package-model",
                str(tmp_path / "missing-model.json"),
                "--out",
                str(tmp_path / "pkg.json"),
            ]
        )


def test_cli_tree_prepare_model_release_read_ioerror_raises_click_exception(
    tmp_path,
) -> None:
    with pytest.raises(click.ClickException):
        main(
            [
                "tree",
                "prepare-model-release",
                str(tmp_path / "missing-model.json"),
                "--out",
                str(tmp_path / "candidate.json"),
            ]
        )


def test_cli_tree_release_readiness_ioerror_raises_click_exception(tmp_path) -> None:
    with pytest.raises(click.ClickException):
        main(
            [
                "tree",
                "release-readiness",
                "--household-model",
                str(tmp_path / "missing-hh.json"),
                "--person-model",
                str(tmp_path / "missing-p.json"),
            ]
        )


def test_cli_tree_package_linked_models_ioerror_raises_click_exception(
    tmp_path,
) -> None:
    with pytest.raises(click.ClickException):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(tmp_path / "missing-hh.json"),
                "--person-model",
                str(tmp_path / "missing-p.json"),
                "--out",
                str(tmp_path / "package.json"),
            ]
        )


def test_format_tree_file_error_read_path_match() -> None:
    exc = OSError(2, "No such file", "/tmp/model.json")
    result = _format_tree_file_error(
        exc,
        read_paths=(Path("/tmp/model.json"),),
        write_paths=(),
    )
    assert "read" in result


def test_format_tree_file_error_write_path_match() -> None:
    exc = OSError(2, "No such file", "/tmp/out.json")
    result = _format_tree_file_error(
        exc,
        read_paths=(),
        write_paths=(Path("/tmp/out.json"),),
    )
    assert "write" in result


def test_format_tree_file_error_access_fallback_when_path_unrecognized() -> None:
    exc = OSError(2, "No such file", "/tmp/other.json")
    result = _format_tree_file_error(
        exc,
        read_paths=(Path("/tmp/model.json"),),
        write_paths=(Path("/tmp/out.json"),),
    )
    assert "access" in result


def test_format_tree_file_error_none_filename_uses_first_read_path() -> None:
    exc = OSError(2, "No such file")
    exc.filename = None
    result = _format_tree_file_error(
        exc,
        read_paths=(Path("/tmp/model.json"),),
        write_paths=(),
    )
    assert "read" in result


def test_format_tree_file_error_none_filename_uses_first_write_path() -> None:
    exc = OSError(2, "No such file")
    exc.filename = None
    result = _format_tree_file_error(
        exc,
        read_paths=(),
        write_paths=(Path("/tmp/out.json"),),
    )
    assert "write" in result


def test_format_tree_file_error_none_filename_neither_falls_back_to_file() -> None:
    exc = OSError(2, "No such file")
    exc.filename = None
    result = _format_tree_file_error(exc, read_paths=(), write_paths=())
    assert "file" in result


def test_format_tree_value_error_json_object_message_replaced() -> None:
    exc = ValueError("The payload must be a JSON object")
    result = _format_tree_value_error(exc)
    assert "not a list or plain value" in result


def test_read_package_path_or_id_unknown_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="linked package not found"):
        _read_package_path_or_id("nonexistent-package-id-xyz")


def test_read_package_path_or_id_nonexistent_path_raises_file_not_found(
    tmp_path,
) -> None:
    nonexistent = str(tmp_path / "subdir" / "package.json")
    with pytest.raises(FileNotFoundError):
        _read_package_path_or_id(nonexistent)


def test_format_default_generation_empty_dict() -> None:
    assert _format_default_generation({}) == ""


def test_format_default_generation_households_and_conditions() -> None:
    result = _format_default_generation({"households": 500, "conditions": "age=adult"})
    assert "500 households" in result
    assert "age=adult" in result


def test_format_default_generation_only_households() -> None:
    result = _format_default_generation({"households": 100})
    assert "100 households" in result
    assert ";" not in result


def test_format_package_catalogue_summary_download_not_installed() -> None:
    model = {
        "name": "Test Model",
        "geography": "Canada",
        "release_status": "public",
        "distribution": "download",
        "installed": False,
    }
    result = _format_package_catalogue_summary(model, {})
    assert "download" in result


def test_format_package_catalogue_summary_bundled_no_download_text() -> None:
    model = {
        "name": "Test Model",
        "geography": "Canada",
        "release_status": "public",
        "distribution": "bundled",
    }
    result = _format_package_catalogue_summary(model, {})
    assert "download" not in result


def test_format_audit_passed_true() -> None:
    assert _format_audit_passed(True) == "Audit passed"


def test_format_audit_passed_false_returns_warnings_text() -> None:
    assert _format_audit_passed(False) == "Audit has warnings"


def test_format_audit_passed_none_returns_not_available() -> None:
    assert _format_audit_passed(None) == "Audit not available"


def test_format_level_household() -> None:
    assert _format_level("household") == "Household"


def test_format_level_person() -> None:
    assert _format_level("person") == "Person"


def test_format_level_other_returns_value_as_string() -> None:
    assert _format_level("region") == "region"


def test_format_level_none_returns_empty_string() -> None:
    assert _format_level(None) == ""


def test_format_model_type_cart() -> None:
    assert _format_model_type("cart") == "CART"


def test_format_model_type_other_returns_value_as_string() -> None:
    assert _format_model_type("unknown-type") == "unknown-type"


def test_format_release_class_private_working() -> None:
    assert _format_release_class("private_working") == "Private working model"


def test_format_release_class_other_returns_value_as_string() -> None:
    assert _format_release_class("unknown") == "unknown"


# ---------------------------------------------------------------------------
# small_area_synthesis.py gaps
# ---------------------------------------------------------------------------


def test_controls_by_geography_raises_when_margin_missing_geography_dimension() -> None:
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("household_size",),
                cells=(ControlCell({"household_size": "1"}, 10),),
            ),
        ),
        dimensions=("household_size",),
    )
    with pytest.raises(ValueError, match="does not include geography dimension"):
        controls_by_geography(controls, geography_dimension="tract")


def test_controls_by_geography_raises_when_margin_only_has_geography_dimension() -> (
    None
):
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="total",
                dimensions=("tract",),
                cells=(ControlCell({"tract": "4620001.00"}, 10),),
            ),
        ),
        dimensions=("tract",),
    )
    with pytest.raises(ValueError, match="must include at least one dimension besides"):
        controls_by_geography(controls, geography_dimension="tract")


def test_controls_by_geography_raises_when_cell_has_empty_geography() -> None:
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("tract", "household_size"),
                cells=(ControlCell({"tract": "", "household_size": "1"}, 10),),
            ),
        ),
        dimensions=("tract", "household_size"),
    )
    with pytest.raises(ValueError, match="has a cell without"):
        controls_by_geography(controls, geography_dimension="tract")


def test_fit_households_by_geography_raises_when_households_empty() -> None:
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("tract", "household_size"),
                cells=(ControlCell({"tract": "4620001.00", "household_size": "1"}, 1),),
            ),
        ),
        dimensions=("tract", "household_size"),
    )
    with pytest.raises(
        ValueError, match="at least one candidate household row is required"
    ):
        fit_households_by_geography([], controls, geography_dimension="tract")


def test_fit_households_by_geography_raises_when_id_column_missing() -> None:
    households = [{"household_size": "1", "TENUR": "owner"}]
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="size",
                dimensions=("tract", "household_size"),
                cells=(ControlCell({"tract": "4620001.00", "household_size": "1"}, 1),),
            ),
        ),
        dimensions=("tract", "household_size"),
    )
    with pytest.raises(ValueError, match="requires 'synthetic_household_id'"):
        fit_households_by_geography(households, controls, geography_dimension="tract")


def test_fit_households_by_geography_raises_when_controls_have_no_geographies() -> None:
    controls = ControlTable(margins=(), dimensions=())
    households = [{"synthetic_household_id": "h1", "household_size": "1"}]
    with pytest.raises(ValueError, match="controls contain no target geographies"):
        fit_households_by_geography(households, controls, geography_dimension="tract")


def test_realize_linked_geography_population_raises_when_weights_empty() -> None:
    households = [{"synthetic_household_id": "h1", "household_size": "1"}]
    with pytest.raises(ValueError, match="at least one target geography is required"):
        realize_linked_geography_population(
            households,
            [],
            weights_by_geography={},
            geography_column="tract",
        )


def test_realize_linked_geography_population_raises_when_weights_length_mismatch() -> (
    None
):
    households = [{"synthetic_household_id": "h1", "household_size": "1"}]
    with pytest.raises(ValueError, match="do not match household rows"):
        realize_linked_geography_population(
            households,
            [],
            weights_by_geography={"4620001.00": [1.0, 0.0]},
            geography_column="tract",
        )


def test_calibrate_linked_household_csvs_subsamples_when_pool_size_smaller(
    tmp_path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    controls = tmp_path / "controls.csv"

    households.write_text(
        "synthetic_household_id,household_size\nh1,1\nh2,1\nh3,1\nh4,1\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id\np1,h1\np2,h2\np3,h3\np4,h4\n"
    )
    controls.write_text(
        "margin,dimensions,tract,household_size,count\n"
        'size,"tract,household_size",4620001.00,1,2\n'
    )

    summary = calibrate_linked_household_csvs(
        households_path=households,
        persons_path=persons,
        controls_path=controls,
        geography_dimension="tract",
        geography_column="tract",
        households_out=tmp_path / "out-hh.csv",
        persons_out=tmp_path / "out-p.csv",
        pool_size=2,
        max_iterations=50,
        tolerance=1e-9,
    )
    assert summary["candidate_households"] == 2
    assert summary["assigned_households"] == 2


def test_write_csv_rows_raises_when_rows_empty(tmp_path) -> None:
    with pytest.raises(ValueError, match="no rows to write"):
        _write_csv_rows(tmp_path / "out.csv", [])


def test_write_csv_rows_writes_file_when_rows_nonempty(tmp_path) -> None:
    out = tmp_path / "out.csv"
    _write_csv_rows(out, [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
    assert out.exists()
    lines = out.read_text().splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"
    assert lines[2] == "3,4"


def test_subsample_candidates_returns_correct_pool_size() -> None:
    households = [
        {"synthetic_household_id": f"h{i}", "household_size": "1"} for i in range(10)
    ]
    persons = [
        {"synthetic_person_id": f"p{i}", "synthetic_household_id": f"h{i}"}
        for i in range(10)
    ]
    sampled_hh, sampled_p = _subsample_candidates(
        households,
        persons,
        pool_size=4,
        household_id_column="synthetic_household_id",
    )
    assert len(sampled_hh) == 4
    sampled_ids = {hh["synthetic_household_id"] for hh in sampled_hh}
    assert all(p["synthetic_household_id"] in sampled_ids for p in sampled_p)


def test_write_realized_population_to_csv_raises_when_households_empty(
    tmp_path,
) -> None:
    with pytest.raises(
        ValueError, match="at least one candidate household row is required"
    ):
        _write_realized_population_to_csv(
            tmp_path / "hh.csv",
            tmp_path / "p.csv",
            [],
            [],
            weights_by_geography={"4620001.00": []},
            geography_column="tract",
            household_id_column="synthetic_household_id",
            person_id_column="synthetic_person_id",
        )


def test_write_realized_population_raises_when_weights_mismatch(tmp_path) -> None:
    households = [{"synthetic_household_id": "h1", "household_size": "1"}]
    with pytest.raises(ValueError, match="do not match household rows"):
        _write_realized_population_to_csv(
            tmp_path / "hh.csv",
            tmp_path / "p.csv",
            households,
            [],
            weights_by_geography={"4620001.00": [1.0, 0.0]},
            geography_column="tract",
            household_id_column="synthetic_household_id",
            person_id_column="synthetic_person_id",
        )


def test_realize_population_with_no_persons_writes_empty_persons_file(tmp_path) -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1"},
        {"synthetic_household_id": "h2", "household_size": "2"},
    ]
    hh_out = tmp_path / "hh.csv"
    p_out = tmp_path / "p.csv"

    result = _write_realized_population_to_csv(
        hh_out,
        p_out,
        households,
        [],
        weights_by_geography={"4620001.00": [1.0, 1.0]},
        geography_column="tract",
        household_id_column="synthetic_household_id",
        person_id_column="synthetic_person_id",
    )
    assert result["assigned_persons"] == 0
    assert p_out.exists()
    assert p_out.read_text() == ""


def test_write_weights_csv_fallback_integerizes_without_precomputed(tmp_path) -> None:
    households = [
        {"synthetic_household_id": "h1", "household_size": "1"},
        {"synthetic_household_id": "h2", "household_size": "2"},
    ]
    out = tmp_path / "weights.csv"
    _write_weights_csv(
        out,
        households,
        {"4620001.00": [1.5, 0.5]},
        household_id_column="synthetic_household_id",
        integer_weights_by_geography=None,
    )
    assert out.exists()
    lines = out.read_text().splitlines()
    assert (
        lines[0]
        == "target_geography,source_candidate_household_id,weight,integer_weight"
    )
    assert len(lines) == 3


def test_ordered_fieldnames_returns_unique_ordered_keys() -> None:
    rows = [
        {"a": "1", "b": "2"},
        {"b": "3", "c": "4"},
        {"a": "5", "d": "6"},
    ]
    result = _ordered_fieldnames(rows)
    assert result == ["a", "b", "c", "d"]


# ---------------------------------------------------------------------------
# models/__init__.py gaps
# ---------------------------------------------------------------------------


def test_model_payload_raises_for_non_dict_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    list_json = tmp_path / "montreal-cma-2016-all-fields-package.json"
    list_json.write_text("[1, 2, 3]")

    with patch.object(models, "model_cache_path", return_value=list_json):
        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(ValueError, match="must be a JSON object"):
                models.model_payload("montreal-cma-2016-all-fields")


def test_model_cache_dir_win32_with_localappdata(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with patch.object(sys, "platform", "win32"):
        result = models.model_cache_dir()
    assert result == tmp_path / "SynthPopCan" / "models"


def test_model_cache_dir_win32_without_localappdata_falls_to_xdg(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with patch.object(sys, "platform", "win32"):
        result = models.model_cache_dir()
    assert result == tmp_path / "synthpopcan" / "models"


def test_model_cache_dir_linux_with_xdg_cache_home(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with patch.object(sys, "platform", "linux"):
        result = models.model_cache_dir()
    assert result == tmp_path / "synthpopcan" / "models"


def test_model_cache_dir_linux_without_xdg_falls_to_home_cache(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    with patch.object(sys, "platform", "linux"):
        result = models.model_cache_dir()
    assert result == Path.home() / ".cache" / "synthpopcan" / "models"


def test_fetch_model_package_returns_early_for_bundled_model(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    result = models.fetch_model_package("demo-linked-household-person")
    assert result.exists()
    assert result.name == "demo-linked-household-person-package.json"


def test_fetch_model_package_returns_cached_file_without_redownloading(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    content = b'{"schema_version": "synthpopcan-linked-tree-package-v1"}'
    cached = tmp_path / "montreal-cma-2016-all-fields-package.json"
    cached.write_bytes(content)

    with patch.object(models, "_verify_model_checksum"):
        result = models.fetch_model_package("montreal-cma-2016-all-fields")

    assert result == cached


def test_fetch_model_package_cleans_up_temp_file_on_exception(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(
        models,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("network failure")),
    )

    with pytest.raises(OSError, match="network failure"):
        models.fetch_model_package("montreal-cma-2016-all-fields")

    temp_files = list(tmp_path.glob("*.part"))
    assert temp_files == []


def test_remove_cached_model_returns_false_for_bundled_model(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    assert models.remove_cached_model("demo-linked-household-person") is False


def test_remove_cached_model_returns_false_when_not_downloaded(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    assert models.remove_cached_model("montreal-cma-2016-all-fields") is False


def test_verify_model_checksum_skips_when_no_expected_sha256(tmp_path) -> None:
    from synthpopcan.models import _verify_model_checksum

    f = tmp_path / "model.json"
    f.write_bytes(b"content")
    _verify_model_checksum(f, {"filename": "model.json"})


def test_verify_model_checksum_raises_on_mismatch(tmp_path) -> None:
    from synthpopcan.models import _verify_model_checksum

    f = tmp_path / "model.json"
    f.write_bytes(b"actual content")
    with pytest.raises(ValueError, match="checksum did not match"):
        _verify_model_checksum(f, {"filename": "model.json", "sha256": "0" * 64})


def test_download_size_ignores_non_integer_content_length() -> None:
    from synthpopcan.models import _download_size

    class _FakeResponse:
        headers = {"Content-Length": "not-a-number"}

    assert _download_size(_FakeResponse(), {"size_bytes": 42}) == 42


def test_download_size_ignores_bad_header_and_missing_size_bytes() -> None:
    from synthpopcan.models import _download_size

    class _FakeResponse:
        headers = {"Content-Length": "bad"}

    assert _download_size(_FakeResponse(), {}) is None


def test_read_wds_control_table_raises_for_non_zip_file(tmp_path) -> None:
    from synthpopcan.controls import read_wds_control_table

    bad_zip = tmp_path / "notazip.zip"
    bad_zip.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="not a valid WDS ZIP"):
        read_wds_control_table(
            bad_zip,
            dimensions=("age",),
            count_column="count",
            margin_name="age",
        )


def test_build_wds_category_mapping_template_raises_for_non_zip_file(tmp_path) -> None:
    from synthpopcan.controls import build_wds_category_mapping_template

    bad_zip = tmp_path / "notazip.zip"
    bad_zip.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="not a valid WDS ZIP"):
        build_wds_category_mapping_template(bad_zip, dimensions=("age",))


def test_control_suggestion_note_with_reason_but_no_role() -> None:
    from synthpopcan.cli_output import _control_suggestion_note

    result = _control_suggestion_note(
        {"reason": "Use this as a control"}, "Run synthpopcan validate"
    )
    assert result == "Use this as a control Run synthpopcan validate"


def test_control_suggestion_note_with_no_role_and_no_reason() -> None:
    from synthpopcan.cli_output import _control_suggestion_note

    result = _control_suggestion_note({}, "Run synthpopcan validate")
    assert result == "Run synthpopcan validate"


def test_render_small_area_map_delegates_to_render_synthesis_map(tmp_path) -> None:
    import synthpopcan.api as api

    calls: list[dict] = []

    def _fake_render(**kwargs):
        calls.append(kwargs)
        return tmp_path / "out.html"

    with patch("synthpopcan.map_render.render_synthesis_map", _fake_render):
        result = api.render_small_area_map(
            households=str(tmp_path / "hh.csv"),
            boundaries=str(tmp_path / "bounds.shp"),
            geography_column="ct",
            geography_id_field="CTUID",
            out=str(tmp_path / "out.html"),
        )

    assert len(calls) == 1
    assert calls[0]["geography_column"] == "ct"
    assert calls[0]["geography_id_field"] == "CTUID"
    assert result == tmp_path / "out.html"


# ---------------------------------------------------------------------------
# ipf.py gaps
# ---------------------------------------------------------------------------


def test_numpy_ipf_index_fit_raises_on_wrong_margins_count() -> None:
    records = [{"age": "young"}, {"age": "old"}]
    margins = [IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0})]
    index = NumpyIPFIndex.build(records, margins)

    extra = IPFMargin(("sex",), {("F",): 50.0, ("M",): 50.0})
    with pytest.raises(ValueError, match="margins count"):
        index.fit([margins[0], extra])


def test_numpy_ipf_index_fit_raises_on_missing_seed_category() -> None:
    records = [{"age": "A"}, {"age": "A"}]
    margins = [IPFMargin(("age",), {("A",): 2.0})]
    index = NumpyIPFIndex.build(records, margins)

    bad_margin = IPFMargin(("age",), {("Z",): 5.0})
    with pytest.raises(ValueError, match="has no seed records"):
        index.fit([bad_margin])


def test_numpy_ipf_index_fit_returns_not_converged_when_max_iterations_reached() -> (
    None
):
    records = [
        {"age": "young", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    margins = [
        IPFMargin(("age",), {("young",): 10.0, ("old",): 90.0}),
        IPFMargin(("sex",), {("F",): 90.0, ("M",): 10.0}),
    ]
    index = NumpyIPFIndex.build(records, margins)

    weights, converged, iterations, max_abs_error = index.fit(
        margins, max_iterations=1, tolerance=0.0
    )
    assert converged is False
    assert iterations == 1
    assert max_abs_error > 0


def test_fit_ipf_numpy_raises_on_empty_margins() -> None:
    records = [{"age": "young"}, {"age": "old"}]
    margin = IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0})
    index = NumpyIPFIndex.build(records, [margin])

    with pytest.raises(ValueError, match="at least one margin"):
        fit_ipf_numpy(index, [])


def test_fit_ipf_numpy_with_valid_margins_returns_result() -> None:
    records = [{"age": "young"}, {"age": "old"}]
    margins = [IPFMargin(("age",), {("young",): 60.0, ("old",): 40.0})]
    index = NumpyIPFIndex.build(records, margins)

    result = fit_ipf_numpy(index, margins)
    assert len(result.weights) == 2
    assert result.converged is True


# ---------------------------------------------------------------------------
# tree.py gaps
# ---------------------------------------------------------------------------


def test_generate_linked_population_to_csv_raises_on_wrong_household_level(
    tmp_path,
) -> None:
    household_model = MagicMock()
    household_model.spec.level = "person"
    person_model = MagicMock()
    person_model.spec.level = "person"

    with pytest.raises(ValueError, match="household model must have level"):
        generate_linked_population_to_csv(
            household_model,
            person_model,
            households=10,
            households_path=tmp_path / "hh.csv",
            persons_path=tmp_path / "p.csv",
        )


def test_generate_linked_population_to_csv_raises_on_wrong_person_level(
    tmp_path,
) -> None:
    household_model = MagicMock()
    household_model.spec.level = "household"
    person_model = MagicMock()
    person_model.spec.level = "household"

    with pytest.raises(ValueError, match="person model must have level"):
        generate_linked_population_to_csv(
            household_model,
            person_model,
            households=10,
            households_path=tmp_path / "hh.csv",
            persons_path=tmp_path / "p.csv",
        )


def test_generate_linked_population_to_csv_raises_on_non_positive_households(
    tmp_path,
) -> None:
    household_model = MagicMock()
    household_model.spec.level = "household"
    person_model = MagicMock()
    person_model.spec.level = "person"

    with pytest.raises(ValueError, match="households must be greater than zero"):
        generate_linked_population_to_csv(
            household_model,
            person_model,
            households=0,
            households_path=tmp_path / "hh.csv",
            persons_path=tmp_path / "p.csv",
        )


def test_generate_linked_population_to_csv_raises_on_non_positive_progress_interval(
    tmp_path,
) -> None:
    household_model = MagicMock()
    household_model.spec.level = "household"
    person_model = MagicMock()
    person_model.spec.level = "person"

    with pytest.raises(ValueError, match="progress interval must be greater than zero"):
        generate_linked_population_to_csv(
            household_model,
            person_model,
            households=10,
            households_path=tmp_path / "hh.csv",
            persons_path=tmp_path / "p.csv",
            progress_interval=0,
        )


def test_generate_frequency_rows_raises_on_non_positive_rows() -> None:
    spec = TreeModelSpec(
        level="person",
        target_columns=("age",),
        conditioning_columns=("geo",),
    )
    model = FrequencyTreeModel(
        spec=spec,
        groups=(),
        global_outcomes=(FrequencyOutcome(values={"age": "adult"}, weight=1.0),),
        source_format="fixture-v1",
        records_trained=1,
    )

    with pytest.raises(ValueError, match="rows must be greater than zero"):
        generate_frequency_rows(model, rows=0)


def _minimal_cart_model() -> CartTreeModel:
    spec = TreeModelSpec(
        level="person",
        target_columns=("age",),
        conditioning_columns=("geo",),
    )
    return CartTreeModel(
        spec=spec,
        feature_categories={"geo": ("ON", "QC")},
        target_classes=({"age": "adult"},),
        children_left=(-1,),
        children_right=(-1,),
        feature=(-2,),
        threshold=(-2.0,),
        value=((1.0,),),
        n_node_samples=(5,),
        weighted_n_node_samples=(5.0,),
        source_format="fixture-v1",
        records_trained=5,
        min_samples_leaf=1,
        max_depth=None,
    )


def test_generate_cart_rows_raises_on_non_positive_rows() -> None:
    model = _minimal_cart_model()

    with pytest.raises(ValueError, match="rows must be greater than zero"):
        generate_cart_rows(model, rows=0)


def test_iter_cart_rows_raises_on_non_positive_rows() -> None:
    model = _minimal_cart_model()
    with pytest.raises(ValueError, match="rows must be greater than zero"):
        list(iter_cart_rows(model, rows=0))


def test_iter_cart_rows_raises_when_leaf_has_no_positive_probabilities() -> None:
    spec = TreeModelSpec(
        level="person",
        target_columns=("age",),
        conditioning_columns=("geo",),
    )
    model = CartTreeModel(
        spec=spec,
        feature_categories={"geo": ("ON",)},
        target_classes=({"age": "adult"},),
        children_left=(-1,),
        children_right=(-1,),
        feature=(-2,),
        threshold=(-2.0,),
        value=((0.0,),),
        n_node_samples=(0,),
        weighted_n_node_samples=(0.0,),
        source_format="fixture-v1",
        records_trained=5,
        min_samples_leaf=1,
        max_depth=None,
    )

    with pytest.raises(ValueError, match="no positive target probabilities"):
        list(iter_cart_rows(model, rows=1))


# ---------------------------------------------------------------------------
# microdata.py gaps
# ---------------------------------------------------------------------------


def test_resolve_tree_column_block_pair_raises_on_all_household_with_no_blocks() -> (
    None
):
    sample = SeedSample(
        level="household",
        source_format="fixture-v1",
        records=(),
        columns=("geo", "age"),
        weight_column=None,
        geography_columns=("geo",),
        id_columns=(),
    )

    with pytest.raises(ValueError):
        resolve_tree_column_block_pair(
            sample,
            household_block="all",
            person_block="all",
        )


def test_resolve_tree_column_block_pair_raises_on_all_household_when_suggestion_returns_empty() -> (
    None
):
    sample = SeedSample(
        level="household",
        source_format="fixture-v1",
        records=(),
        columns=("geo", "age"),
        weight_column=None,
        geography_columns=("geo",),
        id_columns=(),
    )

    with patch(
        "synthpopcan.microdata.suggest_tree_column_blocks",
        return_value={"blocks": []},
    ):
        with pytest.raises(
            ValueError, match="no available household tree column blocks"
        ):
            resolve_tree_column_block_pair(
                sample,
                household_block="all",
                person_block="all",
            )


def test_resolve_tree_column_block_pair_raises_on_all_person_with_no_blocks() -> None:
    sample = SeedSample(
        level="household",
        source_format="fixture-v1",
        records=(),
        columns=("PR", "household_size"),
        weight_column=None,
        geography_columns=("PR",),
        id_columns=(),
    )

    fake_suggestion = {
        "blocks": [
            {
                "name": "household_core",
                "level": "household",
                "target_columns": ["household_size"],
                "conditioning_columns": ["PR"],
            }
        ]
    }

    with patch(
        "synthpopcan.microdata.suggest_tree_column_blocks",
        return_value=fake_suggestion,
    ):
        with pytest.raises(ValueError, match="no available person tree column blocks"):
            resolve_tree_column_block_pair(
                sample,
                household_block="all",
                person_block="all",
            )


# ---------------------------------------------------------------------------
# Additional targeted gap tests
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
