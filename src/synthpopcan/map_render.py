"""Generate a self-contained MapLibre GL JS choropleth map from synthesis output."""

from __future__ import annotations

__all__ = ["prepare_boundaries_geojson", "render_synthesis_map"]

import csv
import json
import math
import statistics
import tempfile
from collections.abc import Callable
from html import escape as html_escape
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Projection: StatCan Lambert → WGS-84
# Both ADA and CT boundary shapefiles use NAD83 / Statistics Canada Lambert.
# ---------------------------------------------------------------------------


def _lcc_to_wgs84(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverse Lambert Conformal Conic for StatCan 2016 census boundaries."""
    a = 6_378_137.0  # GRS80 semi-major axis
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
        ec = ((1 + e * sp) / (1 - e * sp)) ** (e / 2)
        return math.tan(math.pi / 4 - phi / 2) * ec

    m1, m2 = _m(phi1), _m(phi2)
    t1, t2 = _t(phi1), _t(phi2)
    n = math.log(m1 / m2) / math.log(t1 / t2)
    F = m1 / (n * t1**n)
    rho0 = a * F * _t(phi0) ** n

    dx = x - E0
    dy = y - N0
    rho_p = np.sign(n) * np.sqrt(dx**2 + (rho0 - dy) ** 2)
    theta_p = np.arctan2(dx, rho0 - dy)
    t_p = (rho_p / (a * F)) ** (1.0 / n)

    lam = theta_p / n + lam0

    # Iterative phi (converges in < 5 steps)
    phi = np.pi / 2 - 2 * np.arctan(t_p)
    for _ in range(5):
        sp = np.sin(phi)
        phi = np.pi / 2 - 2 * np.arctan(t_p * ((1 - e * sp) / (1 + e * sp)) ** (e / 2))

    return np.degrees(lam), np.degrees(phi)


# ---------------------------------------------------------------------------
# Shapefile reader (pyshp) + reprojection + simplification
# ---------------------------------------------------------------------------


def _read_shapefile_geojson(
    shp_path: Path,
    id_field: str,
    keep_ids: set[str] | None,
    coord_precision: int = 5,
    property_fields: tuple[str, ...] = (),
    feature_sink: Callable[[dict[str, Any]], None] | None = None,
    trust_ring_winding: bool = False,
) -> tuple[dict[str, Any], tuple[float, float, float, float]]:
    """Read a StatCan LCC shapefile and return a WGS-84 GeoJSON FeatureCollection.

    When *keep_ids* is ``None``, all features are included.
    Returns (geojson_dict, (west, south, east, north)) bounding box.
    """
    import shapefile  # pyshp

    features: list[dict[str, Any]] = []
    bbox = [math.inf, math.inf, -math.inf, -math.inf]

    with shapefile.Reader(str(shp_path), encoding="latin1") as sf:
        field_names = [f[0] for f in sf.fields[1:]]  # type: ignore[attr-defined]
        id_idx = field_names.index(id_field)
        property_indices = {name: field_names.index(name) for name in property_fields}

        for sr in sf.iterShapeRecords():  # type: ignore[attr-defined]
            geo_id = str(sr.record[id_idx]).strip()
            if keep_ids is not None and geo_id not in keep_ids:
                continue

            shape = sr.shape
            pts = np.array(shape.points, dtype=np.float64)
            if len(pts) == 0:
                continue

            lons, lats = _lcc_to_wgs84(pts[:, 0], pts[:, 1])

            bbox[0] = min(bbox[0], float(lons.min()))
            bbox[1] = min(bbox[1], float(lats.min()))
            bbox[2] = max(bbox[2], float(lons.max()))
            bbox[3] = max(bbox[3], float(lats.max()))

            parts = list(shape.parts) + [len(pts)]
            rings: list[list[list[float]]] = []
            for i in range(len(shape.parts)):
                lo, hi = parts[i], parts[i + 1]
                ring = _simplify_ring(lons[lo:hi], lats[lo:hi], coord_precision)
                if ring:
                    rings.append(ring)

            if not rings:
                continue

            polygons = (
                _classify_polygon_rings_by_winding(rings)
                if trust_ring_winding
                else _classify_polygon_rings(rings)
            )
            if not polygons:
                continue
            geom_type = "MultiPolygon" if len(polygons) > 1 else "Polygon"
            coords = polygons if geom_type == "MultiPolygon" else polygons[0]

            properties = {"geo_id": geo_id}
            for name, index in property_indices.items():
                value = sr.record[index]
                properties[name] = value.strip() if isinstance(value, str) else value
            feature = {
                "type": "Feature",
                "properties": properties,
                "geometry": {"type": geom_type, "coordinates": coords},
            }
            if feature_sink is None:
                features.append(feature)
            else:
                feature_sink(feature)

    return (
        {"type": "FeatureCollection", "features": features},
        (bbox[0], bbox[1], bbox[2], bbox[3]),
    )


def prepare_boundaries_geojson(
    shp_path: Path,
    id_field: str,
    out_path: Path,
    coord_precision: int = 5,
    property_fields: tuple[str, ...] = (),
    trust_ring_winding: bool = False,
) -> Path:
    """Convert a StatCan LCC shapefile to a WGS-84 GeoJSON file.

    Reads *all* features from *shp_path*, reprojects coordinates from
    NAD83 / Statistics Canada Lambert to WGS-84, and writes a
    FeatureCollection to *out_path*. Each feature carries a ``geo_id``
    property taken from *id_field*. Named *property_fields* are also copied;
    this is used to retain the 2021 Census ``DGUID``.

    Set *trust_ring_winding* for official shapefiles whose exterior/interior
    orientation follows the format contract. This avoids costly containment
    tests for highly fragmented national coastal features.

    The resulting file can be passed directly to ``render_synthesis_map``
    as the *boundaries_path* argument (suffix ``.geojson``), avoiding the
    need to ship the full shapefile alongside the synthesis outputs.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=out_path.parent,
            prefix=f".{out_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temp_path = Path(output.name)
            output.write('{"type":"FeatureCollection","features":[')
            first_feature = True

            def write_feature(feature: dict[str, Any]) -> None:
                nonlocal first_feature
                if not first_feature:
                    output.write(",")
                json.dump(feature, output, separators=(",", ":"))
                first_feature = False

            _read_shapefile_geojson(
                shp_path,
                id_field=id_field,
                keep_ids=None,
                coord_precision=coord_precision,
                property_fields=property_fields,
                feature_sink=write_feature,
                trust_ring_winding=trust_ring_winding,
            )
            output.write("]}")
        temp_path.replace(out_path)
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    return out_path


def _read_geojson_file(
    geojson_path: Path,
    keep_ids: set[str],
) -> tuple[dict[str, Any], tuple[float, float, float, float]]:
    """Read a pre-converted WGS-84 GeoJSON file and filter to *keep_ids*.

    Returns (geojson_dict, (west, south, east, north)) bounding box.
    """
    raw = json.loads(geojson_path.read_text())
    features = [
        f
        for f in raw.get("features", [])
        if str(f.get("properties", {}).get("geo_id", "")).strip() in keep_ids
    ]

    bbox = [math.inf, math.inf, -math.inf, -math.inf]
    for feature in features:
        geom = feature.get("geometry") or {}
        coords_iter: list[Any] = []
        if geom.get("type") == "Polygon":
            coords_iter = [pt for ring in geom["coordinates"] for pt in ring]
        elif geom.get("type") == "MultiPolygon":
            coords_iter = [
                pt for poly in geom["coordinates"] for ring in poly for pt in ring
            ]
        for lon, lat in coords_iter:
            bbox[0] = min(bbox[0], lon)
            bbox[1] = min(bbox[1], lat)
            bbox[2] = max(bbox[2], lon)
            bbox[3] = max(bbox[3], lat)

    if bbox[0] == math.inf:
        bbox = [-180.0, -90.0, 180.0, 90.0]

    return (
        {"type": "FeatureCollection", "features": features},
        (bbox[0], bbox[1], bbox[2], bbox[3]),
    )


def _simplify_ring(
    lons: np.ndarray,
    lats: np.ndarray,
    precision: int,
) -> list[list[float]] | None:
    """Round coordinates, remove consecutive duplicates; return None if degenerate."""
    scale = 10**precision
    rx = np.round(lons * scale) / scale
    ry = np.round(lats * scale) / scale

    # Remove consecutive duplicates
    keep = np.ones(len(rx), dtype=bool)
    keep[1:] = (rx[1:] != rx[:-1]) | (ry[1:] != ry[:-1])
    rx, ry = rx[keep], ry[keep]

    if len(rx) < 4:
        return None

    # Ensure ring is closed
    if rx[0] != rx[-1] or ry[0] != ry[-1]:
        rx = np.append(rx, rx[0])
        ry = np.append(ry, ry[0])

    return [[float(x), float(y)] for x, y in zip(rx, ry, strict=False)]


def _ring_signed_area(ring: list[list[float]]) -> float:
    """Return the signed planar area of a closed coordinate ring."""

    return 0.5 * sum(
        x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False)
    )


def _point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    """Return whether *point* lies inside *ring* using an even-odd ray cast."""

    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
    return inside


def _orient_ring(ring: list[list[float]], *, clockwise: bool) -> list[list[float]]:
    """Return a GeoJSON ring with the requested winding order."""

    is_clockwise = _ring_signed_area(ring) < 0
    return list(reversed(ring)) if is_clockwise != clockwise else ring


def _classify_polygon_rings(
    rings: list[list[list[float]]],
) -> list[list[list[list[float]]]]:
    """Group shapefile rings into GeoJSON polygons while preserving holes.

    Shapefile winding order is not consistently preserved by all producers, so
    containment depth is used: even-depth rings are exteriors and odd-depth
    rings are holes belonging to their nearest containing exterior.
    """

    if not rings:
        return []
    areas = [abs(_ring_signed_area(ring)) for ring in rings]
    bounds = [
        (
            min(point[0] for point in ring),
            min(point[1] for point in ring),
            max(point[0] for point in ring),
            max(point[1] for point in ring),
        )
        for ring in rings
    ]
    grid_size = min(128, max(8, math.ceil(math.sqrt(len(rings)))))
    all_west = min(value[0] for value in bounds)
    all_south = min(value[1] for value in bounds)
    width = max(max(value[2] for value in bounds) - all_west, 1e-12)
    height = max(max(value[3] for value in bounds) - all_south, 1e-12)

    def grid_cell(x: float, y: float) -> tuple[int, int]:
        column = min(grid_size - 1, max(0, int((x - all_west) / width * grid_size)))
        row = min(grid_size - 1, max(0, int((y - all_south) / height * grid_size)))
        return column, row

    grid: dict[tuple[int, int], set[int]] = {}
    global_candidates: set[int] = set()
    for index, (west, south, east, north) in enumerate(bounds):
        first_column, first_row = grid_cell(west, south)
        last_column, last_row = grid_cell(east, north)
        cell_count = (last_column - first_column + 1) * (last_row - first_row + 1)
        if cell_count > 1_024:
            global_candidates.add(index)
            continue
        for column in range(first_column, last_column + 1):
            for row in range(first_row, last_row + 1):
                grid.setdefault((column, row), set()).add(index)

    containers: list[list[int]] = []
    for index, ring in enumerate(rings):
        west, south, east, north = bounds[index]
        candidate_indices = grid.get(grid_cell(*ring[0]), set()) | global_candidates
        containers.append(
            [
                candidate
                for candidate in candidate_indices
                if candidate != index
                and areas[candidate] > areas[index]
                and bounds[candidate][0] <= west
                and bounds[candidate][1] <= south
                and bounds[candidate][2] >= east
                and bounds[candidate][3] >= north
                and _point_in_ring(ring[0], rings[candidate])
            ]
        )
    depths = [len(value) for value in containers]
    exterior_indexes = [index for index, depth in enumerate(depths) if depth % 2 == 0]
    polygons: dict[int, list[list[list[float]]]] = {
        index: [_orient_ring(rings[index], clockwise=False)]
        for index in exterior_indexes
    }
    for index, depth in enumerate(depths):
        if depth % 2 == 0:
            continue
        possible_exteriors = [
            candidate for candidate in containers[index] if depths[candidate] % 2 == 0
        ]
        if not possible_exteriors:
            # Malformed orphan holes are safer to preserve as visible polygons
            # than to silently discard.
            polygons[index] = [_orient_ring(rings[index], clockwise=False)]
            continue
        parent = max(possible_exteriors, key=lambda candidate: depths[candidate])
        polygons[parent].append(_orient_ring(rings[index], clockwise=True))
    return [polygons[index] for index in sorted(polygons)]


def _classify_polygon_rings_by_winding(
    rings: list[list[list[float]]],
) -> list[list[list[list[float]]]]:
    """Classify rings using a shapefile producer's reliable winding contract."""

    if not rings:
        return []
    signed_areas = [_ring_signed_area(ring) for ring in rings]
    largest = max(range(len(rings)), key=lambda index: abs(signed_areas[index]))
    exterior_clockwise = signed_areas[largest] < 0
    exterior_indexes = [
        index
        for index, area in enumerate(signed_areas)
        if (area < 0) == exterior_clockwise
    ]
    polygons: dict[int, list[list[list[float]]]] = {
        index: [_orient_ring(rings[index], clockwise=False)]
        for index in exterior_indexes
    }
    bounds = [
        (
            min(point[0] for point in ring),
            min(point[1] for point in ring),
            max(point[0] for point in ring),
            max(point[1] for point in ring),
        )
        for ring in rings
    ]
    for index in range(len(rings)):
        if index in polygons:
            continue
        west, south, east, north = bounds[index]
        candidates = sorted(
            (
                candidate
                for candidate in exterior_indexes
                if bounds[candidate][0] <= west
                and bounds[candidate][1] <= south
                and bounds[candidate][2] >= east
                and bounds[candidate][3] >= north
            ),
            key=lambda candidate: abs(signed_areas[candidate]),
        )
        parent = next(
            (
                candidate
                for candidate in candidates
                if _point_in_ring(rings[index][0], rings[candidate])
            ),
            None,
        )
        if parent is None:
            polygons[index] = [_orient_ring(rings[index], clockwise=False)]
        else:
            polygons[parent].append(_orient_ring(rings[index], clockwise=True))
    return [polygons[index] for index in sorted(polygons)]


# ---------------------------------------------------------------------------
# Stats from synthesis CSVs
# ---------------------------------------------------------------------------

_SENTINEL = 99_999_999


def _pct_of(counts: dict[str, int], key: str, total: int) -> float | None:
    return round(counts.get(key, 0) / total * 100, 1) if total else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _compute_geo_stats(
    households_path: Path,
    geography_column: str,
    persons_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute per-geography stats from synthesis CSVs.

    Household-level variables (always computed):
        n_households, avg_hh_size, pct_owner, pct_detached,
        median_shelter_cost, pct_major_repairs

    Person-level variables (requires *persons_path*):
        n_persons, pct_child, pct_senior, pct_immigrant,
        pct_vismin, median_hh_income
    """
    # --- household pass ---
    hh_geo: dict[str, str] = {}  # hh_id → geo
    counts: dict[str, int] = {}
    owners: dict[str, int] = {}
    detached: dict[str, int] = {}
    maj_rep: dict[str, int] = {}
    shelter: dict[str, list[float]] = {}
    sizes: dict[str, list[int]] = {}
    hh_id_col = "synthetic_household_id"

    with households_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            geo = row.get(geography_column, "").strip()
            if not geo:
                continue
            hh_id = row.get(hh_id_col, "")
            hh_geo[hh_id] = geo

            counts[geo] = counts.get(geo, 0) + 1
            if row.get("TENUR") == "1":
                owners[geo] = owners.get(geo, 0) + 1
            if row.get("DTYPE") == "1":
                detached[geo] = detached.get(geo, 0) + 1
            if row.get("REPAIR") == "3":
                maj_rep[geo] = maj_rep.get(geo, 0) + 1
            try:
                sc = int(row.get("SHELCO", 0) or 0)
                if 1 <= sc < _SENTINEL:
                    shelter.setdefault(geo, []).append(sc)
            except ValueError:
                pass
            try:
                sz = int(row.get("household_size", 0) or 0)
                if sz > 0:
                    sizes.setdefault(geo, []).append(sz)
            except ValueError:
                pass

    stats: dict[str, dict[str, Any]] = {}
    for geo, n in counts.items():
        sc_med = _median(shelter.get(geo, []))
        sz_lst = sizes.get(geo, [])
        avg_sz = round(sum(sz_lst) / len(sz_lst), 2) if sz_lst else None
        stats[geo] = {
            "n_households": n,
            "avg_hh_size": avg_sz,
            "pct_owner": _pct_of(owners, geo, n),
            "pct_detached": _pct_of(detached, geo, n),
            "median_shelter_cost": round(sc_med) if sc_med is not None else None,
            "pct_major_repairs": _pct_of(maj_rep, geo, n),
        }

    if persons_path is None:
        return stats

    # --- person pass ---
    n_persons: dict[str, int] = {}
    children: dict[str, int] = {}
    seniors: dict[str, int] = {}
    immigrants: dict[str, int] = {}
    vismin: dict[str, int] = {}
    hh_inc_lists: dict[str, list[float]] = {}  # hh_id → person incomes

    with persons_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            geo = row.get(geography_column, "").strip()
            if not geo or geo not in stats:
                continue
            hh_id = row.get(hh_id_col, "")

            n_persons[geo] = n_persons.get(geo, 0) + 1

            try:
                age = int(row.get("AGEGRP", 0) or 0)
                if 1 <= age <= 4:
                    children[geo] = children.get(geo, 0) + 1
                # 88 = 65+ (collapsed senior category in linked-model recode)
                if age == 88 or age >= 14:
                    seniors[geo] = seniors.get(geo, 0) + 1
            except ValueError:
                pass

            try:
                immstat = int(row.get("IMMSTAT", 0) or 0)
                if immstat in (2, 3):  # immigrant or non-permanent resident
                    immigrants[geo] = immigrants.get(geo, 0) + 1
            except ValueError:
                pass

            try:
                vm = int(row.get("VISMIN", 0) or 0)
                # In linked-model recode: 1=visible minority, 2=not visible minority
                # (collapsed from PUMF's 2–13 groups into a single indicator)
                if vm == 1:
                    vismin[geo] = vismin.get(geo, 0) + 1
            except ValueError:
                pass

            try:
                inc = int(row.get("TOTINC", 0) or 0)
                if abs(inc) < _SENTINEL:
                    hh_inc_lists.setdefault(hh_id, []).append(inc)
            except ValueError:
                pass

    # Aggregate per-household income into per-geography medians
    hh_income_by_geo: dict[str, list[float]] = {}
    for hh_id, incomes in hh_inc_lists.items():
        geo = hh_geo.get(hh_id)
        if geo and geo in stats:
            hh_income_by_geo.setdefault(geo, []).append(sum(incomes))

    for geo in stats:
        np_ = n_persons.get(geo, 0)
        med_inc = round(_median(hh_income_by_geo.get(geo, [])) or 0)
        stats[geo].update(
            {
                "n_persons": np_,
                "pct_child": _pct_of(children, geo, np_),
                "pct_senior": _pct_of(seniors, geo, np_),
                "pct_immigrant": _pct_of(immigrants, geo, np_),
                "pct_vismin": _pct_of(vismin, geo, np_),
                "median_hh_income": med_inc,
            }
        )

    return stats


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
  <link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
  <script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:system-ui,sans-serif;background:#1a1a2e}}
    #map{{width:100vw;height:100vh}}
    #panel{{position:absolute;top:12px;left:12px;z-index:1;
      background:rgba(255,255,255,.94);border-radius:10px;
      padding:12px 16px;box-shadow:0 3px 14px rgba(0,0,0,.25);min-width:210px}}
    #panel h3{{font-size:13px;font-weight:700;color:#222;margin-bottom:10px;
      border-bottom:1px solid #eee;padding-bottom:8px}}
    #panel label{{display:block;font-size:11px;color:#555;margin-bottom:4px}}
    #var-select{{width:100%;padding:5px 8px;border:1px solid #ccc;
      border-radius:5px;font-size:12px;background:#fff;cursor:pointer}}
    #legend{{position:absolute;bottom:32px;left:12px;z-index:1;
      background:rgba(255,255,255,.94);border-radius:10px;
      padding:10px 14px;box-shadow:0 3px 14px rgba(0,0,0,.25);min-width:170px}}
    #leg-title{{font-size:11px;font-weight:600;color:#444;margin-bottom:6px}}
    #leg-bar{{height:9px;border-radius:4px;margin-bottom:4px}}
    #leg-labels{{display:flex;justify-content:space-between;font-size:10px;color:#666}}
    #tip{{position:absolute;pointer-events:none;z-index:9;
      background:rgba(15,15,30,.88);color:#f0f0f0;border-radius:8px;
      padding:9px 13px;font-size:12px;box-shadow:0 2px 12px rgba(0,0,0,.4);
      display:none;max-width:220px}}
    #tip strong{{font-size:13px;display:block;margin-bottom:5px;color:#fff}}
    .tip-row{{display:flex;justify-content:space-between;gap:16px;
      padding:2px 0;border-top:1px solid rgba(255,255,255,.1)}}
    .tip-lbl{{color:#aaa}}.tip-val{{font-weight:600;color:#e0e0ff}}
  </style>
</head>
<body>
<div id="map"></div>

<div id="panel">
  <h3>{title}</h3>
  <label for="var-select">Variable</label>
  <select id="var-select"></select>
</div>

<div id="legend">
  <div id="leg-title"></div>
  <div id="leg-bar"></div>
  <div id="leg-labels"><span id="leg-lo"></span><span id="leg-hi"></span></div>
</div>

<div id="tip"></div>

<script>
const GEOJSON = {geojson};
const VARIABLES = {variables};

const COLORS = [
  '#f7fbff','#deebf7','#c6dbef','#9ecae1',
  '#6baed6','#4292c6','#2171b5','#08519c','#08306b'
];

function makeInterp(v) {{
  const n = COLORS.length - 1;
  return ['interpolate',['linear'],
    ['coalesce',['get', v.field], v.min],
    ...COLORS.flatMap((c,i) => [v.min + (v.max - v.min)*i/n, c])
  ];
}}

let current = VARIABLES[0];

const map = new maplibregl.Map({{
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/liberty',
  bounds: {bounds},
  fitBoundsOptions: {{padding: 50}},
}});

map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({{unit:'metric'}}), 'bottom-right');

function setLegend(v) {{
  document.getElementById('leg-title').textContent = v.label;
  document.getElementById('leg-bar').style.background =
    'linear-gradient(to right,' + COLORS.join(',') + ')';
  document.getElementById('leg-lo').textContent = v.fmtLo;
  document.getElementById('leg-hi').textContent = v.fmtHi;
}}

map.on('load', () => {{
  map.addSource('syn', {{type:'geojson', data:GEOJSON, generateId:true}});

  map.addLayer({{
    id:'syn-fill', type:'fill', source:'syn',
    paint:{{
      'fill-color': makeInterp(current),
      'fill-opacity': ['case',['boolean',['feature-state','hover'],false], 0.92, 0.72],
    }}
  }});

  map.addLayer({{
    id:'syn-line', type:'line', source:'syn',
    paint:{{
      'line-color': ['case',['boolean',['feature-state','hover'],false],
        '#ffffff','rgba(255,255,255,0.35)'],
      'line-width': ['case',['boolean',['feature-state','hover'],false], 1.8, 0.4],
    }}
  }});

  setLegend(current);

  const sel = document.getElementById('var-select');
  VARIABLES.forEach((v,i) => {{
    const o = document.createElement('option');
    o.value = i; o.textContent = v.label; sel.appendChild(o);
  }});
  sel.addEventListener('change', () => {{
    current = VARIABLES[+sel.value];
    map.setPaintProperty('syn-fill', 'fill-color', makeInterp(current));
    setLegend(current);
  }});

  // Hover
  let hid = null;
  const tip = document.getElementById('tip');

  map.on('mousemove', 'syn-fill', e => {{
    if (!e.features.length) return;
    const f = e.features[0];
    const p = f.properties;
    map.getCanvas().style.cursor = 'pointer';
    if (hid !== null) map.setFeatureState({{source:'syn',id:hid}},{{hover:false}});
    hid = f.id;
    map.setFeatureState({{source:'syn',id:hid}},{{hover:true}});

    tip.replaceChildren();
    const heading = document.createElement('strong');
    heading.textContent = String(p.geo_id ?? '');
    tip.appendChild(heading);
    VARIABLES.forEach(v => {{
      const row = document.createElement('div');
      row.className = 'tip-row';
      const label = document.createElement('span');
      label.className = 'tip-lbl';
      label.textContent = v.label;
      const value = document.createElement('span');
      value.className = 'tip-val';
      value.textContent = p[v.field] != null ? v.fmt(p[v.field]) : '—';
      row.append(label, value);
      tip.appendChild(row);
    }});
    tip.style.display = 'block';
    tip.style.left = (e.point.x + 16) + 'px';
    tip.style.top  = (e.point.y - 10) + 'px';
  }});

  const hide = () => {{
    if (hid !== null) map.setFeatureState({{source:'syn',id:hid}},{{hover:false}});
    hid = null; map.getCanvas().style.cursor = ''; tip.style.display = 'none';
  }};
  map.on('mouseleave','syn-fill', hide);
  map.on('mousemove', e => {{
    if (tip.style.display === 'block') {{
      tip.style.left = (e.point.x + 16) + 'px';
      tip.style.top  = (e.point.y - 10) + 'px';
    }}
  }});
}});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Variable spec helpers
# ---------------------------------------------------------------------------

# JS formatter strings — must match the splice-in replacements below
_FMT_INT = "function(v){return v.toLocaleString()}"
_FMT_DOLLAR = "function(v){return '$'+Math.round(v).toLocaleString()}"
_FMT_PCT = "function(v){return v.toFixed(1)+'%'}"
_FMT_F2 = "function(v){return v.toFixed(2)}"

_JS_FUNCS = [_FMT_INT, _FMT_DOLLAR, _FMT_PCT, _FMT_F2]


def _variable_spec(
    field: str,
    label: str,
    values: list[float],
    fmt_js: str,
    fmt_lo: str,
    fmt_hi: str,
) -> dict[str, Any]:
    return {
        "field": field,
        "label": label,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 100.0,
        "fmt": fmt_js,
        "fmtLo": fmt_lo,
        "fmtHi": fmt_hi,
    }


def _pct_spec(field: str, label: str, values: list[float]) -> dict[str, Any]:
    return _variable_spec(
        field,
        label,
        values,
        _FMT_PCT,
        fmt_lo=f"{min(values):.1f}%" if values else "0%",
        fmt_hi=f"{max(values):.1f}%" if values else "100%",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_synthesis_map(
    *,
    households_path: Path,
    persons_path: Path | None = None,
    boundaries_path: Path,
    geography_column: str,
    geography_id_field: str,
    out_path: Path,
    title: str = "Synthetic Population",
    coord_precision: int = 5,
) -> Path:
    """Generate a MapLibre GL JS choropleth HTML file from synthesis output.

    Parameters
    ----------
    households_path:
        Synthesis household CSV (output of ``geo calibrate``).
    persons_path:
        Synthesis person CSV (output of ``geo calibrate``). When provided,
        adds person-level variables: persons, % children, % seniors,
        % immigrants, % visible minority, median household income.
    boundaries_path:
        StatCan shapefile (.shp) for the target geography level.
    geography_column:
        Column in the household CSV naming the target geography (e.g. ``ct``).
    geography_id_field:
        Field name in the shapefile attribute table matching that column
        (e.g. ``CTUID`` or ``ADAUID``).
    out_path:
        Destination HTML file.
    title:
        Map title shown in the panel and browser tab.
    coord_precision:
        Decimal places to keep in WGS-84 coordinates (5 ≈ 1 m accuracy).
    """

    # 1. Compute per-geography stats
    stats = _compute_geo_stats(households_path, geography_column, persons_path)
    keep_ids = set(stats)

    # 2. Read + reproject + simplify boundaries
    if boundaries_path.suffix.lower() == ".geojson":
        geojson, bbox = _read_geojson_file(boundaries_path, keep_ids)
    else:
        geojson, bbox = _read_shapefile_geojson(
            boundaries_path,
            id_field=geography_id_field,
            keep_ids=keep_ids,
            coord_precision=coord_precision,
        )

    if not geojson["features"]:
        raise ValueError(
            "No population geography values matched the supplied boundary features. "
            "Check the geography column, boundary ID field, and identifier formats."
        )

    # 3. Join stats into feature properties
    for feature in geojson["features"]:
        geo_id = feature["properties"]["geo_id"]
        feature["properties"].update(stats.get(geo_id, {}))

    # 4. Build variable specs for the UI
    def _vals(field: str) -> list[float]:
        return [
            f["properties"][field]
            for f in geojson["features"]
            if f["properties"].get(field) is not None
        ]

    variables: list[dict[str, Any]] = []

    # --- household variables ---
    for field, label, fmt in [
        ("n_households", "Households", _FMT_INT),
        ("n_persons", "Persons", _FMT_INT),
        ("avg_hh_size", "Avg Household Size", _FMT_F2),
        ("median_hh_income", "Median HH Income", _FMT_DOLLAR),
        ("median_shelter_cost", "Median Shelter Cost", _FMT_DOLLAR),
    ]:
        vals = _vals(field)
        if not vals:
            continue
        lo, hi = min(vals), max(vals)
        if fmt == _FMT_INT:
            lo_s, hi_s = f"{lo:,.0f}", f"{hi:,.0f}"
        elif fmt == _FMT_DOLLAR:
            lo_s, hi_s = f"${lo:,.0f}", f"${hi:,.0f}"
        else:
            lo_s, hi_s = f"{lo:.2f}", f"{hi:.2f}"
        variables.append(
            _variable_spec(field, label, vals, fmt, fmt_lo=lo_s, fmt_hi=hi_s)
        )

    # --- percentage variables ---
    for field, label in [
        ("pct_owner", "% Homeowners"),
        ("pct_detached", "% Detached Dwellings"),
        ("pct_major_repairs", "% Needing Major Repairs"),
        ("pct_child", "% Children (under 20)"),
        ("pct_senior", "% Seniors (65+)"),
        ("pct_immigrant", "% Immigrants"),
        ("pct_vismin", "% Visible Minority"),
    ]:
        vals = _vals(field)
        if vals:
            variables.append(_pct_spec(field, label, vals))

    # 5. Serialise — compact JSON (no whitespace) keeps file small
    geojson_js = _json_for_inline_script(geojson)
    variables_js = _json_for_inline_script(variables)

    # JS formatter functions must be raw JS, not JSON strings — splice them in
    for fn in _JS_FUNCS:
        variables_js = variables_js.replace(f'"{fn}"', fn)

    bounds_js = f"[[{bbox[0]},{bbox[1]}],[{bbox[2]},{bbox[3]}]]"

    html = _TEMPLATE.format(
        title=html_escape(title, quote=True),
        geojson=geojson_js,
        variables=variables_js,
        bounds=bounds_js,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _json_for_inline_script(value: object) -> str:
    """Serialize JSON without permitting data to terminate the script element."""

    return (
        json.dumps(value, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
