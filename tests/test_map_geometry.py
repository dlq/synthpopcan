"""Map geometry behaviour and regression tests."""

from __future__ import annotations

import numpy as np
import pytest
from support.map_fixtures import (
    _square_ring,
    _wgs84_to_lcc,
)

from synthpopcan.map_render import (
    _classify_polygon_rings,
    _classify_polygon_rings_by_winding,
    _geometry_coordinate_bounds,
    _lcc_to_wgs84,
    _map_variable_specs,
    _median,
    _pct_of,
    _quantize_display_geometry,
    _quantize_display_ring,
    _simplify_ring,
)


def test_display_boundary_quantization_edge_cases() -> None:
    assert _quantize_display_ring(None, 3) is None
    assert _quantize_display_ring(
        [None, [0], ["bad", 0], [0, 0], [1, 0], [0, 1]],
        3,
    ) == [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
    assert _quantize_display_geometry({"type": "Polygon"}, 3) == (None, 0)
    assert _quantize_display_geometry(
        {"type": "Point", "coordinates": [0, 0]},
        3,
    ) == (None, 0)
    assert _quantize_display_geometry(
        {"type": "MultiPolygon", "coordinates": [None]},
        3,
    ) == (None, 0)
    assert _quantize_display_geometry(
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0.0001, 0], [0, 0.0001], [0, 0]]],
        },
        3,
    ) == (None, 1)
    multi, collapsed = _quantize_display_geometry(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [0, 1], [0, 0]]],
                [[[2, 2], [3, 2], [2, 3], [2, 2]]],
            ],
        },
        3,
    )
    assert collapsed == 0
    assert multi is not None
    assert multi["type"] == "MultiPolygon"
    assert _geometry_coordinate_bounds(None) is None
    assert _geometry_coordinate_bounds([]) is None
    assert _map_variable_specs({"1001": {}}) == []


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


def test_median_empty_returns_none() -> None:
    assert _median([]) is None


def test_median_odd_list() -> None:
    assert _median([3.0, 1.0, 2.0]) == 2.0


def test_median_even_list() -> None:
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_single_element() -> None:
    assert _median([7.0]) == 7.0


def test_pct_of_returns_percentage() -> None:
    assert _pct_of({"A": 25}, "A", 100) == 25.0


def test_pct_of_rounds_to_one_decimal() -> None:
    assert _pct_of({"A": 1}, "A", 3) == pytest.approx(33.3, abs=0.05)


def test_pct_of_missing_key_returns_zero_pct() -> None:
    assert _pct_of({}, "A", 100) == 0.0


def test_pct_of_zero_total_returns_none() -> None:
    assert _pct_of({"A": 10}, "A", 0) is None


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
