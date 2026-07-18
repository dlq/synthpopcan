"""Tests for map_render — projection, ring simplification, stats, and rendering."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

from synthpopcan.map_render import (
    _classify_polygon_rings,
    _classify_polygon_rings_by_winding,
    _compute_geo_stats,
    _json_for_inline_script,
    _lcc_to_wgs84,
    _median,
    _pct_of,
    _read_geojson_file,
    _simplify_ring,
    prepare_boundaries_geojson,
    render_synthesis_map,
)


def test_classify_polygon_rings_preserves_holes_and_islands() -> None:
    exterior = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[2, 2], [2, 8], [8, 8], [8, 2], [2, 2]]
    island = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]

    polygons = _classify_polygon_rings([hole, island, exterior])

    assert len(polygons) == 2
    assert sorted(len(polygon) for polygon in polygons) == [1, 2]
    polygon_with_hole = next(polygon for polygon in polygons if len(polygon) == 2)
    assert polygon_with_hole[0][0] == exterior[0]
    assert polygon_with_hole[1][0] == hole[-1]


def test_classify_polygon_rings_by_winding_preserves_holes_and_islands() -> None:
    exterior = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[2, 2], [2, 8], [8, 8], [8, 2], [2, 2]]
    island = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]

    polygons = _classify_polygon_rings_by_winding([hole, island, exterior])

    assert sorted(len(polygon) for polygon in polygons) == [1, 2]


def test_inline_map_json_cannot_terminate_script_element() -> None:
    encoded = _json_for_inline_script({"geo_id": "</script><img src=x>"})

    assert "</script>" not in encoded
    assert "<img" not in encoded
    assert "\\u003c/script\\u003e" in encoded


# ---------------------------------------------------------------------------
# _median
# ---------------------------------------------------------------------------


def test_median_empty_returns_none() -> None:
    assert _median([]) is None


def test_median_odd_list() -> None:
    assert _median([3.0, 1.0, 2.0]) == 2.0


def test_median_even_list() -> None:
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_single_element() -> None:
    assert _median([7.0]) == 7.0


# ---------------------------------------------------------------------------
# _pct_of
# ---------------------------------------------------------------------------


def test_pct_of_returns_percentage() -> None:
    assert _pct_of({"A": 25}, "A", 100) == 25.0


def test_pct_of_rounds_to_one_decimal() -> None:
    assert _pct_of({"A": 1}, "A", 3) == pytest.approx(33.3, abs=0.05)


def test_pct_of_missing_key_returns_zero_pct() -> None:
    assert _pct_of({}, "A", 100) == 0.0


def test_pct_of_zero_total_returns_none() -> None:
    assert _pct_of({"A": 10}, "A", 0) is None


# ---------------------------------------------------------------------------
# _lcc_to_wgs84
# ---------------------------------------------------------------------------


def _wgs84_to_lcc(lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Forward StatCan LCC for test round-trips."""
    a = 6_378_137.0
    f = 1.0 / 298.257_222_101
    e2 = 2 * f - f**2
    e = math.sqrt(e2)
    phi0 = math.radians(63.390675)
    phi1 = math.radians(49.0)
    phi2 = math.radians(77.0)
    lam0 = math.radians(-91.86666666666666)
    E0, N0 = 6_200_000.0, 3_000_000.0

    def _m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)

    def _t(phi: float) -> float:
        sp = math.sin(phi)
        return math.tan(math.pi / 4 - phi / 2) * ((1 + e * sp) / (1 - e * sp)) ** (
            e / 2
        )

    m1, m2 = _m(phi1), _m(phi2)
    t1, t2 = _t(phi1), _t(phi2)
    n = math.log(m1 / m2) / math.log(t1 / t2)
    F = m1 / (n * t1**n)
    rho0 = a * F * _t(phi0) ** n

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    rho = a * F * _t(phi) ** n
    theta = n * (lam - lam0)
    x = E0 + rho * math.sin(theta)
    y = N0 + rho0 - rho * math.cos(theta)
    return x, y


def test_lcc_to_wgs84_round_trip_montreal() -> None:
    lon_in, lat_in = -73.6, 45.5  # central Montreal
    x, y = _wgs84_to_lcc(lon_in, lat_in)
    lons, lats = _lcc_to_wgs84(np.array([x]), np.array([y]))
    assert abs(float(lons[0]) - lon_in) < 0.001
    assert abs(float(lats[0]) - lat_in) < 0.001


def test_lcc_to_wgs84_round_trip_toronto() -> None:
    lon_in, lat_in = -79.4, 43.7  # Toronto
    x, y = _wgs84_to_lcc(lon_in, lat_in)
    lons, lats = _lcc_to_wgs84(np.array([x]), np.array([y]))
    assert abs(float(lons[0]) - lon_in) < 0.001
    assert abs(float(lats[0]) - lat_in) < 0.001


def test_lcc_to_wgs84_preserves_array_shape() -> None:
    x = np.array([4_812_000.0, 5_100_000.0])
    y = np.array([5_099_000.0, 5_200_000.0])
    lons, lats = _lcc_to_wgs84(x, y)
    assert lons.shape == (2,)
    assert lats.shape == (2,)


def test_lcc_to_wgs84_output_is_degrees() -> None:
    x = np.array([6_200_000.0])  # false easting origin
    y = np.array([3_000_000.0])  # false northing origin
    lons, lats = _lcc_to_wgs84(x, y)
    # origin maps to lam0, phi0
    assert abs(float(lons[0]) - (-91.867)) < 0.1
    assert abs(float(lats[0]) - 63.39) < 0.1


# ---------------------------------------------------------------------------
# _simplify_ring
# ---------------------------------------------------------------------------


def _square_ring(n: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Return a closed square ring with *n* points per side."""
    t = np.linspace(0, 1, n, endpoint=False)
    top = np.column_stack([t, np.ones(n)])
    right = np.column_stack([np.ones(n), 1 - t])
    bottom = np.column_stack([1 - t, np.zeros(n)])
    left = np.column_stack([np.zeros(n), t])
    pts = np.vstack([top, right, bottom, left])
    return pts[:, 0], pts[:, 1]


def test_simplify_ring_closes_open_ring() -> None:
    lons, lats = _square_ring()
    result = _simplify_ring(lons, lats, precision=5)
    assert result is not None
    assert result[0] == result[-1]


def test_simplify_ring_removes_consecutive_duplicates() -> None:
    lons = np.array([0.0, 0.0, 1.0, 1.0, 0.0])
    lats = np.array([0.0, 0.0, 0.0, 1.0, 0.0])
    result = _simplify_ring(lons, lats, precision=5)
    assert result is not None
    # No two consecutive identical points (except closing pair)
    for i in range(len(result) - 1):
        assert result[i] != result[i + 1] or i == len(result) - 2


def test_simplify_ring_returns_none_for_degenerate() -> None:
    lons = np.array([0.0, 0.0, 0.0])
    lats = np.array([0.0, 0.0, 0.0])
    assert _simplify_ring(lons, lats, precision=5) is None


def test_simplify_ring_rounds_to_precision() -> None:
    lons = np.array([0.123456, 1.0, 1.0, 0.0, 0.0])
    lats = np.array([0.0, 0.0, 1.0, 1.0, 0.0])
    result = _simplify_ring(lons, lats, precision=3)
    assert result is not None
    # First coordinate should be rounded to 3 dp
    assert result[0][0] == pytest.approx(0.123, abs=0.001)


# ---------------------------------------------------------------------------
# _compute_geo_stats — household-only
# ---------------------------------------------------------------------------


def _write_households(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_compute_geo_stats_counts_households(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1200",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "3",
                "TENUR": "2",
                "DTYPE": "2",
                "REPAIR": "1",
                "SHELCO": "900",
            },
            {
                "synthetic_household_id": "h3",
                "ct": "G2",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "3",
                "SHELCO": "800",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["n_households"] == 2
    assert stats["G2"]["n_households"] == 1


def test_compute_geo_stats_avg_hh_size(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "4",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["avg_hh_size"] == 3.0


def test_compute_geo_stats_pct_owner(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "2",
                "DTYPE": "2",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["pct_owner"] == 50.0


def test_compute_geo_stats_pct_major_repairs(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "3",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h3",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
            {
                "synthetic_household_id": "h4",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["pct_major_repairs"] == 25.0


def test_compute_geo_stats_skips_sentinel_shelter_cost(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "99999999",
            },
            {
                "synthetic_household_id": "h2",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1200",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["median_shelter_cost"] == 1200


# ---------------------------------------------------------------------------
# _compute_geo_stats — person-level variables
# ---------------------------------------------------------------------------


def _write_persons(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_compute_geo_stats_person_counts(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "50000",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "2",
                "IMMSTAT": "2",
                "VISMIN": "1",
                "TOTINC": "30000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["n_persons"] == 2


def test_compute_geo_stats_pct_senior_agegrp88(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "88",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_senior"] == 50.0


def test_compute_geo_stats_vismin_coding(tmp_path: Path) -> None:
    """VISMIN=1 is visible minority (opposite of standard PUMF)."""
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "1",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_vismin"] == 50.0


def test_compute_geo_stats_median_hh_income(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "2",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "40000",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "20000",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    # Both persons in h1 → household income = 60000
    assert stats["G1"]["median_hh_income"] == 60000


def test_compute_geo_stats_pct_immigrant(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            {
                "synthetic_household_id": "h1",
                "ct": "G1",
                "household_size": "1",
                "TENUR": "1",
                "DTYPE": "1",
                "REPAIR": "1",
                "SHELCO": "1000",
            },
        ],
    )
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            # IMMSTAT 2 = immigrant, 3 = non-permanent resident (both count)
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "2",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "3",
                "VISMIN": "2",
                "TOTINC": "0",
            },
            {
                "synthetic_person_id": "p3",
                "synthetic_household_id": "h1",
                "ct": "G1",
                "AGEGRP": "5",
                "IMMSTAT": "1",
                "VISMIN": "2",
                "TOTINC": "0",
            },
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_immigrant"] == pytest.approx(66.7, abs=0.05)


# ---------------------------------------------------------------------------
# render_synthesis_map — smoke test with a fake shapefile
# ---------------------------------------------------------------------------


def _write_fake_shapefile(
    shp_dir: Path,
    geo_id: str,
    *,
    dguid: str | None = None,
    landarea: float | None = None,
    pruid: str | None = None,
) -> Path:
    """Write the simplest possible polygon shapefile using pyshp."""
    import shapefile

    shp_path = shp_dir / "fake_lct.shp"
    # Use forward-projected LCC coordinates for a small square near Montreal.
    x0, y0 = _wgs84_to_lcc(-73.6, 45.5)
    d = 5_000.0  # 5 km square
    ring = [
        (x0, y0),
        (x0 + d, y0),
        (x0 + d, y0 + d),
        (x0, y0 + d),
        (x0, y0),
    ]
    with shapefile.Writer(str(shp_path)) as w:
        w.field("CTUID", "C", 20)
        if dguid is not None:
            w.field("DGUID", "C", 30)
        if landarea is not None:
            w.field("LANDAREA", "F", 18, 6)
        if pruid is not None:
            w.field("PRUID", "C", 2)
        w.poly([ring])
        record = {"CTUID": geo_id}
        if dguid is not None:
            record["DGUID"] = dguid
        if landarea is not None:
            record["LANDAREA"] = landarea
        if pruid is not None:
            record["PRUID"] = pruid
        w.record(**record)
    return shp_path


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
    )

    assert out.exists()
    html = out.read_text()
    assert "MapLibre" in html or "maplibre" in html.lower()
    assert "4620001.00" in html
    assert "Test Map" in html


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


# ---------------------------------------------------------------------------
# _compute_geo_stats — exception branches (ValueError on bad field values)
# ---------------------------------------------------------------------------


def _hh_row(
    hh_id: str,
    ct: str,
    *,
    household_size: str = "2",
    tenur: str = "1",
    dtype: str = "1",
    repair: str = "1",
    shelco: str = "1000",
) -> dict[str, str]:
    return {
        "synthetic_household_id": hh_id,
        "ct": ct,
        "household_size": household_size,
        "TENUR": tenur,
        "DTYPE": dtype,
        "REPAIR": repair,
        "SHELCO": shelco,
    }


def _person_row(
    pid: str,
    hh_id: str,
    ct: str,
    *,
    agegrp: str = "5",
    immstat: str = "1",
    vismin: str = "2",
    totinc: str = "0",
) -> dict[str, str]:
    return {
        "synthetic_person_id": pid,
        "synthetic_household_id": hh_id,
        "ct": ct,
        "AGEGRP": agegrp,
        "IMMSTAT": immstat,
        "VISMIN": vismin,
        "TOTINC": totinc,
    }


def test_compute_geo_stats_skips_rows_with_no_geo(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(
        hh,
        [
            _hh_row("h1", "G1"),
            _hh_row("h2", ""),  # empty geo — should be skipped
        ],
    )

    stats = _compute_geo_stats(hh, "ct")

    assert "G1" in stats
    assert "" not in stats
    assert stats["G1"]["n_households"] == 1


def test_compute_geo_stats_non_numeric_shelco_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1", shelco="x")])

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["median_shelter_cost"] is None


def test_compute_geo_stats_non_numeric_hhsize_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1", household_size="x")])

    stats = _compute_geo_stats(hh, "ct")

    assert stats["G1"]["avg_hh_size"] is None


def test_compute_geo_stats_person_in_unknown_geo_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(
        persons,
        [
            _person_row("p1", "h1", "G1"),
            _person_row("p2", "h2", "NOWHERE"),  # geo not in stats → skipped
        ],
    )

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["n_persons"] == 1


def test_compute_geo_stats_non_numeric_agegrp_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", agegrp="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_senior"] == 0.0
    assert stats["G1"]["pct_child"] == 0.0


def test_compute_geo_stats_non_numeric_immstat_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", immstat="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_immigrant"] == 0.0


def test_compute_geo_stats_non_numeric_vismin_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", vismin="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["pct_vismin"] == 0.0


def test_compute_geo_stats_non_numeric_totinc_skipped(tmp_path: Path) -> None:
    hh = tmp_path / "hh.csv"
    _write_households(hh, [_hh_row("h1", "G1")])
    persons = tmp_path / "persons.csv"
    _write_persons(persons, [_person_row("p1", "h1", "G1", totinc="x")])

    stats = _compute_geo_stats(hh, "ct", persons_path=persons)

    assert stats["G1"]["median_hh_income"] == 0


# ---------------------------------------------------------------------------
# CLI: small-area map
# ---------------------------------------------------------------------------


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
            "--out",
            str(out),
            "--title",
            "Test",
        ]
    )

    assert exit_code == 0
    assert out.exists()
    assert "maplibre" in out.read_text().lower()


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


# ---------------------------------------------------------------------------
# render_synthesis_map — shapefile filtering / skipping branches
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CLI: small-area map — error-handler branches
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _resolve_boundaries — GeoJSON passthrough
# ---------------------------------------------------------------------------


def test_resolve_boundaries_passes_through_geojson(tmp_path: Path) -> None:
    from synthpopcan.cli_geo import _resolve_boundaries

    gj = tmp_path / "boundaries.geojson"
    gj.write_text("{}")

    result = _resolve_boundaries(gj, "ct")

    assert result == gj


# ---------------------------------------------------------------------------
# _read_geojson_file
# ---------------------------------------------------------------------------


def _write_fake_geojson(path: Path, geo_ids: list[str]) -> None:
    """Write a minimal WGS-84 GeoJSON FeatureCollection."""
    import json as _json

    features = [
        {
            "type": "Feature",
            "properties": {"geo_id": gid},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-73.6, 45.5],
                        [-73.5, 45.5],
                        [-73.5, 45.6],
                        [-73.6, 45.6],
                        [-73.6, 45.5],
                    ]
                ],
            },
        }
        for gid in geo_ids
    ]
    path.write_text(_json.dumps({"type": "FeatureCollection", "features": features}))


def test_read_geojson_file_filters_to_keep_ids(tmp_path: Path) -> None:
    gj = tmp_path / "b.geojson"
    _write_fake_geojson(gj, ["A1", "A2", "A3"])

    result, bbox = _read_geojson_file(gj, {"A1", "A3"})

    ids = [f["properties"]["geo_id"] for f in result["features"]]
    assert sorted(ids) == ["A1", "A3"]
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]


def test_read_geojson_file_empty_keep_ids_returns_empty(tmp_path: Path) -> None:
    gj = tmp_path / "b.geojson"
    _write_fake_geojson(gj, ["A1"])

    result, bbox = _read_geojson_file(gj, set())

    assert result["features"] == []
    assert bbox == (-180.0, -90.0, 180.0, 90.0)


def test_read_geojson_file_multipolygon(tmp_path: Path) -> None:
    import json as _json

    gj = tmp_path / "b.geojson"
    gj.write_text(
        _json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "X1"},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [[[-73.6, 45.5], [-73.5, 45.5], [-73.6, 45.5]]],
                                [[[-74.0, 46.0], [-73.9, 46.0], [-74.0, 46.0]]],
                            ],
                        },
                    }
                ],
            }
        )
    )

    result, bbox = _read_geojson_file(gj, {"X1"})

    assert len(result["features"]) == 1
    assert bbox[0] < -73.9


# ---------------------------------------------------------------------------
# prepare_boundaries_geojson
# ---------------------------------------------------------------------------


def test_prepare_boundaries_geojson_writes_geojson(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    import json as _json

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")
    out = tmp_path / "out.geojson"

    result = prepare_boundaries_geojson(shp_path, "CTUID", out, coord_precision=3)

    assert result == out
    assert out.exists()
    data = _json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["geo_id"] == "4620001.00"


def test_prepare_boundaries_geojson_preserves_requested_properties(
    tmp_path: Path,
) -> None:
    pytest.importorskip("shapefile")
    import json as _json

    shp_path = _write_fake_shapefile(
        tmp_path,
        "4620001.00",
        dguid="2021S05074620001.00",
        landarea=12.345678,
        pruid="24",
    )
    out = tmp_path / "out.geojson"

    prepare_boundaries_geojson(
        shp_path,
        "CTUID",
        out,
        property_fields=("DGUID", "LANDAREA", "PRUID"),
    )

    properties = _json.loads(out.read_text())["features"][0]["properties"]
    assert properties == {
        "geo_id": "4620001.00",
        "DGUID": "2021S05074620001.00",
        "LANDAREA": 12.345678,
        "PRUID": "24",
    }


def test_prepare_boundaries_geojson_streams_multiple_features(
    tmp_path: Path, monkeypatch
) -> None:
    import json as _json

    def fake_reader(*_args, feature_sink=None, **_kwargs):
        assert feature_sink is not None
        for geo_id in ("A", "B"):
            feature_sink(
                {
                    "type": "Feature",
                    "properties": {"geo_id": geo_id},
                    "geometry": None,
                }
            )
        return ({"type": "FeatureCollection", "features": []}, (0, 0, 1, 1))

    monkeypatch.setattr("synthpopcan.map_render._read_shapefile_geojson", fake_reader)
    out = tmp_path / "out.geojson"

    prepare_boundaries_geojson(tmp_path / "unused.shp", "CTUID", out)

    assert [
        feature["properties"]["geo_id"]
        for feature in _json.loads(out.read_text())["features"]
    ] == ["A", "B"]


def test_prepare_boundaries_geojson_removes_partial_output_on_failure(
    tmp_path: Path, monkeypatch
) -> None:
    def failing_reader(*_args, **_kwargs):
        raise RuntimeError("conversion failed")

    monkeypatch.setattr(
        "synthpopcan.map_render._read_shapefile_geojson", failing_reader
    )
    out = tmp_path / "out.geojson"

    with pytest.raises(RuntimeError, match="conversion failed"):
        prepare_boundaries_geojson(tmp_path / "unused.shp", "CTUID", out)

    assert not out.exists()
    assert not list(tmp_path.glob(".out.geojson.*.tmp"))


# ---------------------------------------------------------------------------
# render_synthesis_map — GeoJSON boundaries path
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# geo boundaries CLI
# ---------------------------------------------------------------------------


def test_cli_prepare_boundaries_success(tmp_path: Path) -> None:
    pytest.importorskip("shapefile")
    from unittest.mock import patch

    from synthpopcan.cli import main as cli_main

    shp_path = _write_fake_shapefile(tmp_path, "4620001.00")

    with (
        patch(
            "synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path
        ) as mock_dl,
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            return_value=tmp_path / "2016-boundary-ct.geojson",
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
    with (
        patch(
            "synthpopcan.statcan.fetch_boundary_zip", return_value=shp_path
        ) as mock_dl,
        patch(
            "synthpopcan.map_render.prepare_boundaries_geojson",
            return_value=tmp_path / "2021-boundary-ct.geojson",
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


def test_cli_downloads_2021_relationship_file(tmp_path: Path) -> None:
    from unittest.mock import patch

    from synthpopcan.cli import main as cli_main

    csv_path = tmp_path / "2021_98260004.csv"
    with patch(
        "synthpopcan.statcan.fetch_dgrf_2021", return_value=csv_path
    ) as mock_fetch:
        exit_code = cli_main(["geo", "relationship-file", "--out-dir", str(tmp_path)])

    assert exit_code == 0
    mock_fetch.assert_called_once_with(tmp_path, url=None)


def test_cli_relationship_file_reports_download_error(tmp_path: Path) -> None:
    from unittest.mock import patch

    import click

    from synthpopcan.cli import main as cli_main

    with patch(
        "synthpopcan.statcan.fetch_dgrf_2021", side_effect=OSError("network error")
    ):
        with pytest.raises(click.ClickException, match="network error"):
            cli_main(["geo", "relationship-file", "--out-dir", str(tmp_path)])


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
