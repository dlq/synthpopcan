"""Map render behaviour and regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from support.map_fixtures import (
    _wgs84_to_lcc,
    _write_fake_geojson,
    _write_fake_shapefile,
)

from synthpopcan.map_render import (
    _json_for_inline_script,
    render_synthesis_map,
)


def test_inline_map_json_cannot_terminate_script_element() -> None:
    encoded = _json_for_inline_script({"geo_id": "</script><img src=x>"})

    assert "</script>" not in encoded
    assert "<img" not in encoded
    assert "\\u003c/script\\u003e" in encoded


def test_render_synthesis_map_creates_html(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,4620001.00,2,1,1,1,1200\n"
        "h2,4620001.00,3,2,2,1,900\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="Test Map",
        coord_precision=3,
        geography_context={
            "schema_version": "synthpopcan-geography-universe-v1",
            "census_vintage": 2021,
            "geography_level": "ct",
            "identifier_namespace": "statcan:census:2021:ct",
            "identifier_column": "ct",
            "dguid_column": None,
        },
    )

    assert out.exists()
    html = out.read_text()
    assert "MapLibre" in html or "maplibre" in html.lower()
    assert "4620001.00" in html
    assert "Test Map" in html
    assert 'const GEOGRAPHY = {"schema_version":' in html
    assert '"identifier_namespace":"statcan:census:2021:ct"' in html


def test_render_synthesis_map_includes_geojson_feature(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")

    geo_id = "4620001.00"
    shp_path = _write_fake_shapefile(tmp_path, geo_id)

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1500\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="T",
        coord_precision=3,
    )

    html = out.read_text()
    # GeoJSON is embedded as a JS variable; the geo_id should appear in it
    assert geo_id in html


def test_render_synthesis_map_with_persons(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")

    geo_id = "4620001.00"
    shp_path = _write_fake_shapefile(tmp_path, geo_id)

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1200\n"
    )
    persons = tmp_path / "persons.csv"
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ct,"
        "AGEGRP,IMMSTAT,VISMIN,TOTINC\n"
        f"p1,h1,{geo_id},5,1,2,50000\n"
        f"p2,h1,{geo_id},88,2,1,30000\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        persons_path=persons,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="T",
        coord_precision=3,
    )

    assert out.exists()
    html = out.read_text()
    # Person-level variable fields should appear in the HTML
    assert "pct_senior" in html
    assert "pct_vismin" in html


def test_render_synthesis_map_skips_geo_not_in_households(tmp_path: Path) -> None:
    """Shapefile has an extra feature not in households — line 90 is hit."""
    pytest.importorskip("shapefile")
    import shapefile

    geo_id = "4620001.00"
    extra = "9999999.99"
    x0, y0 = _wgs84_to_lcc(-73.6, 45.5)
    d = 5_000.0

    shp_path = tmp_path / "test.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("CTUID", "C", 20)
        ring1 = [(x0, y0), (x0 + d, y0), (x0 + d, y0 + d), (x0, y0 + d), (x0, y0)]
        w.poly([ring1])
        w.record(CTUID=geo_id)
        ring2 = [
            (x0 + 2 * d, y0),
            (x0 + 3 * d, y0),
            (x0 + 3 * d, y0 + d),
            (x0 + 2 * d, y0 + d),
            (x0 + 2 * d, y0),
        ]
        w.poly([ring2])
        w.record(CTUID=extra)

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="T",
        coord_precision=3,
    )

    assert out.exists()
    assert extra not in out.read_text()


def test_render_synthesis_map_skips_null_shape(tmp_path: Path) -> None:
    """Null shapefile feature (empty pts) for a known geo — line 95 is hit."""
    pytest.importorskip("shapefile")
    import shapefile

    geo_id = "4620001.00"
    x0, y0 = _wgs84_to_lcc(-73.6, 45.5)
    d = 5_000.0
    ring = [(x0, y0), (x0 + d, y0), (x0 + d, y0 + d), (x0, y0 + d), (x0, y0)]

    shp_path = tmp_path / "test.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("CTUID", "C", 20)
        w.null()  # type-0 null shape: points == [] — skipped at line 95
        w.record(CTUID=geo_id)
        w.poly([ring])  # valid shape for the same geo to keep the map renderable
        w.record(CTUID=geo_id)

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="T",
        coord_precision=3,
    )

    assert out.exists()
    assert geo_id in out.read_text()


def test_render_synthesis_map_rejects_no_matching_boundaries(tmp_path: Path) -> None:
    gj_path = tmp_path / "boundaries.geojson"
    _write_fake_geojson(gj_path, ["different-geography"])
    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,requested-geography,2,1,1,1,1200\n"
    )

    with pytest.raises(ValueError, match="No population geography values matched"):
        render_synthesis_map(
            households_path=hh,
            boundaries_path=gj_path,
            geography_column="ct",
            geography_id_field="CTUID",
            out_path=tmp_path / "map.html",
        )


def test_render_synthesis_map_escapes_title_and_uses_text_tooltips(
    tmp_path: Path,
) -> None:
    gj_path = tmp_path / "boundaries.geojson"
    _write_fake_geojson(gj_path, ["G1"])
    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,G1,2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=gj_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title='Unsafe </script><img src=x onerror="alert(1)">',
    )

    output = out.read_text()
    assert '<img src=x onerror="alert(1)">' not in output
    assert "&lt;/script&gt;&lt;img" in output
    assert "tip.innerHTML" not in output
    assert "tip.replaceChildren()" in output


def test_render_synthesis_map_skips_degenerate_ring(tmp_path: Path) -> None:
    """Polygon ring that simplifies to < 4 unique pts — line 113 is hit."""
    pytest.importorskip("shapefile")
    import shapefile

    geo_id = "4620001.00"
    x0, y0 = _wgs84_to_lcc(-73.6, 45.5)
    d = 5_000.0
    # 1-metre offset rounds to same (lon, lat) at 3 dp → dedup yields 1 unique pt → None
    deg_ring = [(x0, y0), (x0 + 1, y0), (x0, y0)]
    valid_ring = [(x0, y0), (x0 + d, y0), (x0 + d, y0 + d), (x0, y0 + d), (x0, y0)]

    shp_path = tmp_path / "test.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("CTUID", "C", 20)
        w.poly([deg_ring])  # all rings degenerate → rings=[] → skipped at line 113
        w.record(CTUID=geo_id)
        w.poly([valid_ring])  # valid shape so the map still renders
        w.record(CTUID=geo_id)

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=shp_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="T",
        coord_precision=3,
    )

    assert out.exists()


def test_render_synthesis_map_with_geojson_boundaries(tmp_path: Path) -> None:
    """render_synthesis_map accepts a pre-converted .geojson boundaries file."""
    geo_id = "4620001.00"
    gj_path = tmp_path / "boundaries.geojson"
    _write_fake_geojson(gj_path, [geo_id])

    hh = tmp_path / "households.csv"
    hh.write_text(
        "synthetic_household_id,ct,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        f"h1,{geo_id},2,1,1,1,1200\n"
    )
    out = tmp_path / "map.html"

    render_synthesis_map(
        households_path=hh,
        boundaries_path=gj_path,
        geography_column="ct",
        geography_id_field="CTUID",
        out_path=out,
        title="GeoJSON Map",
        coord_precision=5,
    )

    assert out.exists()
    assert geo_id in out.read_text()
