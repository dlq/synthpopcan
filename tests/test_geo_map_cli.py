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
