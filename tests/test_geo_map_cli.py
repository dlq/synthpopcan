"""Geo map cli behaviour and regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.map_fixtures import (
    _write_fake_shapefile,
)


def test_cli_map_command_creates_html(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
    )
    out = tmp_path / "out.html"

    exit_code = cli_main(
        [
            "geo",
            "map",
            str(hh),
            "--boundaries",
            str(shp_path),
            "--geo-column",
            "ct",
            "--census-vintage",
            "2021",
            "--geo-level",
            "ct",
            "--geo-namespace",
            "statcan:census:2021:ct",
            "--out",
            str(out),
            "--title",
            "Test",
        ]
    )

    assert exit_code == 0
    assert out.exists()
    assert "maplibre" in out.read_text().lower()
    assert '"identifier_namespace":"statcan:census:2021:ct"' in out.read_text()


def test_cli_map_command_default_out_and_title(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    hh = tmp_path / "my-households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
    )

    exit_code = cli_main(
        [
            "geo",
            "map",
            str(hh),
            "--boundaries",
            str(shp_path),
            "--geo-column",
            "ct",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "my-households-map.html").exists()


def test_resolve_boundaries_raises_when_no_shp_found(tmp_path: Path) -> None:
    import click

    from synthpopcan.cli_geo import _resolve_boundaries

    with pytest.raises(click.ClickException, match="No .shp file found"):
        _resolve_boundaries(tmp_path, "ct")


def test_resolve_boundaries_raises_when_multiple_shp_found(tmp_path: Path) -> None:
    import click

    from synthpopcan.cli_geo import _resolve_boundaries

    (tmp_path / "a.shp").write_text("")
    (tmp_path / "b.shp").write_text("")

    with pytest.raises(click.ClickException, match="Multiple shapefiles"):
        _resolve_boundaries(tmp_path, "unknown_geo")


def test_resolve_id_field_warns_for_unknown_geography(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from synthpopcan.cli_geo import _resolve_id_field

    result = _resolve_id_field("cma", tmp_path / "fake.shp")

    assert result == "CMAUID"
    captured = capsys.readouterr()
    assert "Warning" in captured.err


def test_resolve_boundaries_returns_single_shp_from_directory(
    tmp_path: Path,
) -> None:
    from synthpopcan.cli_geo import _resolve_boundaries

    shp = tmp_path / "lct_000b16a_e.shp"
    shp.write_bytes(b"")

    result = _resolve_boundaries(tmp_path, "ct")

    assert result == shp


def test_cli_map_command_import_error(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")
    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    with patch(
        "synthpopcan.map_render.render_synthesis_map",
        side_effect=ImportError("No module named 'shapefile'"),
    ):
        with pytest.raises(click.ClickException, match="shapefile"):
            cli_main(
                [
                    "geo",
                    "map",
                    str(hh),
                    "--boundaries",
                    str(shp_path),
                    "--geo-column",
                    "ct",
                    "--out",
                    str(out),
                ]
            )


def test_cli_map_command_oserror(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")
    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    with patch(
        "synthpopcan.map_render.render_synthesis_map",
        side_effect=OSError("disk error"),
    ):
        with pytest.raises(click.ClickException, match="disk error"):
            cli_main(
                [
                    "geo",
                    "map",
                    str(hh),
                    "--boundaries",
                    str(shp_path),
                    "--geo-column",
                    "ct",
                    "--out",
                    str(out),
                ]
            )


def test_cli_map_command_value_error(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")
    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    with patch(
        "synthpopcan.map_render.render_synthesis_map",
        side_effect=ValueError("bad column"),
    ):
        with pytest.raises(click.ClickException, match="bad column"):
            cli_main(
                [
                    "geo",
                    "map",
                    str(hh),
                    "--boundaries",
                    str(shp_path),
                    "--geo-column",
                    "ct",
                    "--out",
                    str(out),
                ]
            )


def test_resolve_boundaries_passes_through_geojson(tmp_path: Path) -> None:
    from synthpopcan.cli_geo import _resolve_boundaries

    gj = tmp_path / "boundaries.geojson"
    gj.write_text("{}")

    result = _resolve_boundaries(gj, "ct")

    assert result == gj


def test_cli_prepare_boundaries_success(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")
    geojson_path = tmp_path / "2016-boundary-ct.geojson"
    geojson_path.write_text('{"type":"FeatureCollection","features":[]}\n')
    (tmp_path / "2016-boundary-ct.json").write_text(json.dumps({"resources": []}))

    with (
        patch(
            "synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path
        ) as mock_dl,
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            return_value=geojson_path,
        ) as mock_conv,
    ):
        exit_code = cli_main(
            [
                "geo",
                "boundaries",
                "--geo-level",
                "ct",
                "--out-dir",
                str(tmp_path),
            ]
        )

    assert exit_code == 0
    mock_dl.assert_called_once()
    mock_conv.assert_called_once()
    assert not shp_path.exists()
    assert mock_conv.call_args.kwargs["property_fields"] == (
        "CTNAME",
        "PRUID",
        "PRNAME",
        "CMAUID",
        "CMAPUID",
        "CMANAME",
        "CMATYPE",
    )


def test_cli_prepare_boundaries_2021_preserves_dguid(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(
        tmp_path, "4620001.00", dguid="2021S05074620001.00"
    )
    geojson_path = tmp_path / "2021-boundary-ct.geojson"
    geojson_path.write_text('{"type":"FeatureCollection","features":[]}\n')
    (tmp_path / "2021-boundary-ct.json").write_text(json.dumps({"resources": []}))
    with (
        patch(
            "synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path
        ) as mock_dl,
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            return_value=geojson_path,
        ) as mock_conv,
    ):
        exit_code = cli_main(
            [
                "geo",
                "boundaries",
                "--census-year",
                "2021",
                "--geo-level",
                "ct",
                "--out-dir",
                str(tmp_path),
            ]
        )

    assert exit_code == 0
    mock_dl.assert_called_once_with("ct", tmp_path, census_year=2021, url=None)
    assert mock_conv.call_args.kwargs["property_fields"] == (
        "DGUID",
        "LANDAREA",
        "PRUID",
    )
    assert mock_conv.call_args.kwargs["trust_ring_winding"] is True
    assert mock_conv.call_args.kwargs["out_path"].name == "2021-boundary-ct.geojson"
    manifest = json.loads((tmp_path / "2021-boundary-ct.json").read_text())
    assert manifest["geojson_properties"] == [
        "geo_id",
        "DGUID",
        "LANDAREA",
        "PRUID",
    ]
    assert manifest["schema_version"] == "synthpopcan-statcan-resource-v1"
    assert manifest["geography"]["census_vintage"] == 2021
    assert manifest["geography"]["geography_level"] == "ct"
    assert manifest["resource"]["byte_size"] == geojson_path.stat().st_size
    assert len(manifest["resource"]["sha256"]) == 64


def test_cli_prepare_boundaries_download_oserror(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    with patch(
        "synthpopcan.statcan.fetch_boundary_zip",
        side_effect=OSError("network error"),
    ):
        with pytest.raises(click.ClickException, match="network error"):
            cli_main(
                [
                    "geo",
                    "boundaries",
                    "--geo-level",
                    "ada",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


def test_cli_prepare_boundaries_convert_import_error(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    with (
        patch("synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path),
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            side_effect=ImportError("no shapefile"),
        ),
    ):
        with pytest.raises(click.ClickException, match="no shapefile"):
            cli_main(
                [
                    "geo",
                    "boundaries",
                    "--geo-level",
                    "ct",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


def test_cli_prepare_boundaries_convert_oserror(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    with (
        patch("synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path),
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            side_effect=OSError("disk full"),
        ),
    ):
        with pytest.raises(click.ClickException, match="disk full"):
            cli_main(
                [
                    "geo",
                    "boundaries",
                    "--geo-level",
                    "ct",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


def test_cli_prepare_boundaries_download_value_error(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    with patch(
        "synthpopcan.statcan.fetch_boundary_zip",
        side_effect=ValueError("bad zip"),
    ):
        with pytest.raises(click.ClickException, match="bad zip"):
            cli_main(
                [
                    "geo",
                    "boundaries",
                    "--geo-level",
                    "ct",
                    "--out-dir",
                    str(tmp_path),
                ]
            )


@pytest.mark.parametrize("input_mode", ["directory", "csv", "default-output"])
def test_cli_map_both_writes_distinct_household_and_person_views(tmp_path, input_mode):
    from click.testing import CliRunner
    from support.map_fixtures import _write_fake_geojson

    from synthpopcan.cli import cli

    population = tmp_path / "population"
    population.mkdir()
    households = population / "households.csv"
    households.write_text("synthetic_household_id,ct,household_size,TENUR\nh1,G1,2,1\n")
    persons = population / "persons.csv"
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ct,AGEGRP,HDGREE,TOTINC\n"
        "p1,h1,G1,4,7,10000\np2,h1,G1,12,1,30000\n"
    )
    boundaries = tmp_path / "boundaries.geojson"
    _write_fake_geojson(boundaries, ["G1"])
    args = [
        "geo",
        "map",
        str(households if input_mode == "csv" else population),
        "--both",
        "--person-profile",
        "statcan-hierarchical-2021",
        "--boundaries",
        str(boundaries),
        "--geo-column",
        "ct",
        "--title",
        "Example",
    ]
    if input_mode == "csv":
        args += ["--persons", str(persons)]
    base = (
        population / "map"
        if input_mode == "default-output"
        else tmp_path / "example.v1"
    )
    if input_mode != "default-output":
        args += ["--out", str(base.with_name(base.name + ".html"))]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    household_map = base.with_name(base.name + "-households.html")
    population_map = base.with_name(base.name + "-population.html")
    household_html = household_map.read_text()
    population_html = population_map.read_text()
    assert '"n_households":1' in household_html
    assert '"pct_owner":100.0' in household_html
    assert '"n_persons":2' in population_html
    assert '"median_personal_income":20000.0' in population_html
    assert '"pct_bachelor_plus":50.0' in population_html
    assert '"n_households"' not in population_html
    assert "Example — households" in household_html
    assert "Example — population" in population_html
    assert str(household_map) in result.output
    assert str(population_map) in result.output
    assert not base.with_name(base.name + ".html").exists()


@pytest.mark.parametrize(
    "problem,expected_code,message",
    [
        ("profile", 2, "--both requires --person-profile"),
        ("persons-option", 2, "household CSV with --persons"),
        ("persons-file", 1, "persons.csv"),
        ("person-schema", 1, "AGEGRP"),
    ],
)
def test_cli_map_both_validates_person_inputs_before_writing_maps(
    tmp_path, problem, expected_code, message
):
    from click.testing import CliRunner
    from support.map_fixtures import _write_fake_geojson

    from synthpopcan.cli import cli

    households = tmp_path / "households.csv"
    households.write_text("synthetic_household_id,ct,household_size\nh1,G1,1\n")
    persons = tmp_path / "persons.csv"
    if problem == "person-schema":
        persons.write_text("ct\nG1\n")
    boundaries = tmp_path / "boundaries.geojson"
    _write_fake_geojson(boundaries, ["G1"])
    args = [
        "geo",
        "map",
        str(households),
        "--both",
        "--boundaries",
        str(boundaries),
        "--geo-column",
        "ct",
        "--out",
        str(tmp_path / "map.html"),
    ]
    if problem != "profile":
        args += ["--person-profile", "statcan-hierarchical-2021"]
    if problem != "persons-option":
        args += ["--persons", str(persons)]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == expected_code, result.output
    assert message in result.output
    assert not list(tmp_path.glob("*.html"))


def test_cli_map_both_rejects_national_plan(tmp_path):
    from click.testing import CliRunner

    from synthpopcan.cli import cli

    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    result = CliRunner().invoke(cli, ["geo", "map", str(plan), "--both"])
    assert result.exit_code == 2
    assert "rather than a national plan" in result.output
