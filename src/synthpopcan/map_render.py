"""Generate a self-contained MapLibre GL JS choropleth map from synthesis output."""

from __future__ import annotations

__all__ = [
    "filter_boundaries_geojson",
    "partition_boundaries_geojson",
    "prepare_national_map_statistics",
    "prepare_boundaries_geojson",
    "render_geography_summary_polygon_map",
    "render_geography_summary_point_map",
    "render_national_plan_map",
    "render_synthesis_map",
]

import csv
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from html import escape as html_escape
from pathlib import Path
from typing import Any

# Retain existing helper import paths while the implementation has its own owner.
from synthpopcan._map_boundaries import (
    _classify_polygon_rings as _classify_polygon_rings,
)
from synthpopcan._map_boundaries import (
    _classify_polygon_rings_by_winding as _classify_polygon_rings_by_winding,
)
from synthpopcan._map_boundaries import (
    _geometry_coordinate_bounds as _geometry_coordinate_bounds,
)
from synthpopcan._map_boundaries import (
    _iter_compact_geojson_feature_bytes as _iter_compact_geojson_feature_bytes,
)
from synthpopcan._map_boundaries import (
    _iter_geojson_features as _iter_geojson_features,
)
from synthpopcan._map_boundaries import (
    _iter_geojson_features_for_partition as _iter_geojson_features_for_partition,
)
from synthpopcan._map_boundaries import (
    _iter_marker_delimited_geojson_features as _iter_marker_delimited_geojson_features,
)
from synthpopcan._map_boundaries import (
    _iter_selected_geojson_features as _iter_selected_geojson_features,
)
from synthpopcan._map_boundaries import (
    _lcc_to_wgs84 as _lcc_to_wgs84,
)
from synthpopcan._map_boundaries import (
    _orient_ring as _orient_ring,
)
from synthpopcan._map_boundaries import (
    _point_in_ring as _point_in_ring,
)
from synthpopcan._map_boundaries import (
    _prepare_boundaries_geojson as _prepare_boundaries_geojson,
)
from synthpopcan._map_boundaries import (
    _quantize_display_geometry as _quantize_display_geometry,
)
from synthpopcan._map_boundaries import (
    _quantize_display_ring as _quantize_display_ring,
)
from synthpopcan._map_boundaries import (
    _read_geojson_file as _read_geojson_file,
)
from synthpopcan._map_boundaries import (
    _read_shapefile_geojson as _read_shapefile_geojson,
)
from synthpopcan._map_boundaries import (
    _ring_signed_area as _ring_signed_area,
)
from synthpopcan._map_boundaries import (
    _shapefile_property_indices as _shapefile_property_indices,
)
from synthpopcan._map_boundaries import (
    _simplify_ring as _simplify_ring,
)
from synthpopcan._map_boundaries import (
    filter_boundaries_geojson as filter_boundaries_geojson,
)
from synthpopcan._map_boundaries import (
    partition_boundaries_geojson as partition_boundaries_geojson,
)
from synthpopcan._map_statistics import compute_geo_statistics
from synthpopcan._national_map_statistics import (
    _prepare_national_map_statistics,
)
from synthpopcan._national_map_statistics import (
    _resolve_plan_path as _resolve_plan_path,
)

# ---------------------------------------------------------------------------
# Boundary conversion
# ---------------------------------------------------------------------------


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
    return _prepare_boundaries_geojson(
        shp_path,
        id_field,
        out_path,
        coord_precision,
        property_fields,
        trust_ring_winding,
        reader=_read_shapefile_geojson,
    )


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
    """Compute observed statistics through the shared map-statistics boundary."""
    return compute_geo_statistics(households_path, geography_column, persons_path)


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
    #leg-ticks{{position:relative;height:16px;font-size:10px;color:#666}}
    #leg-ticks span{{position:absolute;transform:translateX(-50%)}}
    #leg-scale{{font-size:10px;color:#666;margin-top:3px}}
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
  <p id="variable-note" hidden
     style="font-size:12px;max-width:380px;line-height:1.4"></p>
</div>

<div id="legend">
  <div id="leg-title"></div>
  <div id="leg-bar"></div>
  <div id="leg-labels"><span id="leg-lo"></span><span id="leg-hi"></span></div>
  <div id="leg-ticks" hidden></div>
  <div id="leg-scale" hidden>Logarithmic density scale</div>
</div>

<div id="tip"></div>

<script>
const GEOJSON = {geojson};
const VARIABLES = {variables};
const GEOGRAPHY = {geography};

const COLORS = [
  '#f7fbff','#deebf7','#c6dbef','#9ecae1',
  '#6baed6','#4292c6','#2171b5','#08519c','#08306b'
];

function makeInterp(v) {{
  if (v.min === v.max) return COLORS[Math.floor(COLORS.length / 2)];
  const n = COLORS.length - 1;
  const logarithmic = v.scale === 'log1p';
  const low = logarithmic ? Math.log1p(v.min) : v.min;
  const high = logarithmic ? Math.log1p(v.max) : v.max;
  const raw = ['coalesce',['get', v.field], v.min];
  const input = logarithmic ? ['ln', ['+', 1, ['max', 0, raw]]] : raw;
  return ['interpolate',['linear'],
    input,
    ...COLORS.flatMap((c,i) => [low + (high - low)*i/n, c])
  ];
}}

let current = VARIABLES[0];

function makeOpacity(v) {{
  return ['case', ['==', ['get', v.field], null], 0,
    ['case', ['boolean', ['feature-state','hover'], false], 0.92, 0.72]];
}}

const map = new maplibregl.Map({{
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/liberty',
  bounds: {bounds},
  fitBoundsOptions: {{padding: 50}},
}});

map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({{unit:'metric'}}), 'bottom-right');

function setLegend(v) {{
  const note = document.getElementById('variable-note');
  note.textContent = v.note || '';
  note.hidden = !v.note;
  document.getElementById('leg-title').textContent = v.label;
  document.getElementById('leg-bar').style.background =
    v.min === v.max ? COLORS[Math.floor(COLORS.length / 2)]
      : 'linear-gradient(to right,' + COLORS.join(',') + ')';
  document.getElementById('leg-lo').textContent = v.fmtLo;
  document.getElementById('leg-hi').textContent = v.fmtHi;
  setDensityLegend(v);
}}

function setDensityLegend(v) {{
  const logarithmic = v.scale === 'log1p';
  document.getElementById('leg-labels').hidden = logarithmic;
  document.getElementById('leg-labels').style.display = logarithmic ? 'none' : 'flex';
  const scaleLabel = document.getElementById('leg-scale');
  scaleLabel.hidden = false;
  scaleLabel.textContent = v.min === v.max ? 'Constant value across mapped tracts'
    : logarithmic ? 'Logarithmic density scale' : 'Linear scale · observed range';
  document.getElementById('legend').style.minWidth = logarithmic ? '300px' : '170px';
  const ticks = document.getElementById('leg-ticks');
  ticks.hidden = !logarithmic;
  ticks.replaceChildren();
  if (!logarithmic) return;
  v.legendTicks.forEach((value, i) => {{
    const label = document.createElement('span');
    const position = v.legendTicks.length === 1 ? 50 : 100*i/(v.legendTicks.length-1);
    label.style.left = position + '%';
    if (v.legendTicks.length > 1) {{
      if (i === 0) label.style.transform = 'none';
      if (i === v.legendTicks.length-1) label.style.transform = 'translateX(-100%)';
    }}
    label.textContent = value.toLocaleString(undefined, {{maximumFractionDigits: 0}});
    ticks.appendChild(label);
  }});
}}

map.on('load', () => {{
  map.addSource('syn', {{type:'geojson', data:GEOJSON, generateId:true}});

  map.addLayer({{
    id:'syn-fill', type:'fill', source:'syn',
    paint:{{
      'fill-color': makeInterp(current),
      'fill-opacity': makeOpacity(current),
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
    map.setPaintProperty('syn-fill', 'fill-opacity', makeOpacity(current));
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
    const shown = VARIABLES.some(v => v.note)
      ? VARIABLES.filter(v => v.field === current.field || v.field === 'n_persons')
      : VARIABLES;
    shown.forEach(v => {{
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
    if (p[current.field + '_n'] != null) {{
      const detail = document.createElement('div');
      detail.style.fontSize = '12px';
      const denominator = Number(p[current.field + '_n']).toLocaleString();
      const known = Number(p[current.field + '_known']).toLocaleString();
      const eligible = Number(p[current.field + '_eligible']).toLocaleString();
      detail.textContent = 'Denominator: ' + denominator
        + ' · Valid source records: ' + known + ' / ' + eligible
        + ' age-eligible people';
      tip.appendChild(detail);
    }}
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
    return _with_density_scale(
        {
            "field": field,
            "label": label,
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 100.0,
            "fmt": fmt_js,
            "fmtLo": fmt_lo,
            "fmtHi": fmt_hi,
        }
    )


def _with_density_scale(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["field"] in {"persons_per_km2", "households_per_km2"}:
        spec.update(_density_scale(spec["min"], spec["max"]))
    return spec


def _density_scale(low: float, high: float) -> dict[str, Any]:
    """Match logarithmic colour spacing with ticks in original density units."""
    if low == high:
        ticks = [low]
    else:
        start, stop = math.log1p(low), math.log1p(high)
        ticks = [math.expm1(start + (stop - start) * i / 4) for i in range(5)]
        ticks[0], ticks[-1] = low, high
    return {"scale": "log1p", "legendTicks": ticks}


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
    geography_context: Mapping[str, object] | None = None,
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
    geography_context:
        Optional versioned geography-universe payload embedded in the HTML.
    """

    # 1. Compute per-geography stats
    stats = _compute_geo_stats(households_path, geography_column, persons_path)
    return _render_statistics_map(
        stats=stats,
        boundaries_path=boundaries_path,
        geography_id_field=geography_id_field,
        out_path=out_path,
        title=title,
        coord_precision=coord_precision,
        geography_context=geography_context,
    )


def _render_statistics_map(
    *,
    stats: dict[str, dict[str, Any]],
    boundaries_path: Path,
    geography_id_field: str,
    out_path: Path,
    title: str,
    coord_precision: int,
    geography_context: Mapping[str, object] | None,
    person_attributes: bool = False,
    _boundary_cache: dict[Any, Any] | None = None,
) -> Path:
    """Join either household/person or person-only statistics to boundaries."""
    keep_ids = set(stats)

    cache_key = (
        boundaries_path.resolve(),
        geography_id_field,
        coord_precision,
        frozenset(keep_ids),
    )
    if _boundary_cache is not None and cache_key in _boundary_cache:
        geojson, bbox = _boundary_cache[cache_key]
    elif boundaries_path.suffix.lower() == ".geojson":
        geojson, bbox = _read_geojson_file(boundaries_path, keep_ids)
    else:
        geojson, bbox = _read_shapefile_geojson(
            boundaries_path,
            id_field=geography_id_field,
            keep_ids=keep_ids,
            coord_precision=coord_precision,
        )

    if _boundary_cache is not None:
        _boundary_cache[cache_key] = (geojson, bbox)
        # Geometry is immutable during rendering. Each view owns its feature
        # properties so household fields cannot leak into the population view.
        geojson = {
            **geojson,
            "features": [
                {**feature, "properties": dict(feature["properties"])}
                for feature in geojson["features"]
            ],
        }

    if not geojson["features"]:
        raise ValueError(
            "No population geography values matched the supplied boundary features. "
            "Check the geography column, boundary ID field, and identifier formats."
        )

    # 3. Join stats into feature properties
    for feature in geojson["features"]:
        geo_id = feature["properties"]["geo_id"]
        _add_density_statistics(stats[geo_id], feature["properties"].get("LANDAREA"))
        feature["properties"].update(stats.get(geo_id, {}))

    # 4. Build variable specs for the UI
    if person_attributes:
        variables = _person_variable_specs(stats)
    else:
        variables = _map_variable_specs(stats)

    # 5. Serialise — compact JSON (no whitespace) keeps file small
    geojson_js = _json_for_inline_script(geojson)
    variables_js = _json_for_inline_script(variables)
    geography_js = _json_for_inline_script(geography_context)

    # JS formatter functions must be raw JS, not JSON strings — splice them in
    for fn in _JS_FUNCS:
        variables_js = variables_js.replace(f'"{fn}"', fn)

    bounds_js = f"[[{bbox[0]},{bbox[1]}],[{bbox[2]},{bbox[3]}]]"

    html = _TEMPLATE.format(
        title=html_escape(title, quote=True),
        geojson=geojson_js,
        variables=variables_js,
        geography=geography_js,
        bounds=bounds_js,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_geography_summary_point_map(
    *,
    summary_path: Path,
    boundaries_path: Path,
    geography_column: str,
    out_path: Path,
    points_path: Path | None = None,
    geography_id_field: str = "geo_id",
    title: str = "National Synthetic Population",
    geography_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Render a compact national point overview without altering boundaries.

    Each marker is placed at the centre of its canonical feature's bounding
    box. The result is explicitly a display index, not a simplified analytical
    boundary. The source boundary remains unchanged.
    """

    summaries = _read_geography_summaries(summary_path, geography_column)

    features: list[dict[str, object]] = []
    extent = [math.inf, math.inf, -math.inf, -math.inf]
    matched: set[str] = set()
    for feature in _iter_geojson_features_for_partition(boundaries_path):
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        identifier = str(properties.get(geography_id_field, "")).strip()
        if identifier not in summaries:
            continue
        bounds = _geometry_coordinate_bounds(geometry.get("coordinates"))
        if bounds is None:
            continue
        west, south, east, north = bounds
        longitude = (west + east) / 2
        latitude = (south + north) / 2
        extent[0] = min(extent[0], longitude)
        extent[1] = min(extent[1], latitude)
        extent[2] = max(extent[2], longitude)
        extent[3] = max(extent[3], latitude)
        features.append(
            {
                "type": "Feature",
                "properties": summaries[identifier],
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(longitude, 5), round(latitude, 5)],
                },
            }
        )
        matched.add(identifier)
    if not features:
        raise ValueError("no geography summaries matched canonical boundaries")

    point_collection = {"type": "FeatureCollection", "features": features}
    points_path = points_path or out_path.with_suffix(".geojson")
    points_path.parent.mkdir(parents=True, exist_ok=True)
    points_path.write_text(
        json.dumps(point_collection, separators=(",", ":")),
        encoding="utf-8",
    )
    html = _POINT_SUMMARY_TEMPLATE.format(
        title=html_escape(title, quote=True),
        geojson=_json_for_inline_script(point_collection),
        geography=_json_for_inline_script(geography_context),
        bounds=f"[[{extent[0]},{extent[1]}],[{extent[2]},{extent[3]}]]",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {
        "representation": "canonical-feature-bounding-box-centre",
        "requested_geographies": len(summaries),
        "matched_geographies": len(matched),
        "missing_geographies": sorted(set(summaries) - matched),
        "map_path": str(out_path),
        "points_path": str(points_path),
    }


def render_geography_summary_polygon_map(
    *,
    summary_path: Path,
    boundaries_path: Path,
    geography_column: str,
    out_path: Path,
    display_boundaries_path: Path | None = None,
    prepared_display_boundary_paths: Sequence[Path] | None = None,
    geography_id_field: str = "geo_id",
    title: str = "National Synthetic Population",
    coord_precision: int = 3,
    geography_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Render an aggregate choropleth from prepared or fallback boundaries.

    Coordinates are snapped to one fixed decimal grid before consecutive
    duplicates are removed. Because every feature uses the same grid, shared
    boundary vertices remain shared. The canonical source is never modified,
    and the derived geometry must not be used for analysis.
    """

    if coord_precision < 0:
        raise ValueError("coord_precision must be non-negative")
    summaries = _read_geography_summaries(summary_path, geography_column)
    boundary_paths = tuple(prepared_display_boundary_paths or (boundaries_path,))
    uses_prepared_display = prepared_display_boundary_paths is not None
    features: list[dict[str, object]] = []
    extent = [math.inf, math.inf, -math.inf, -math.inf]
    matched: set[str] = set()
    collapsed_rings = 0
    for boundary_path in boundary_paths:
        for feature in _iter_geojson_features_for_partition(boundary_path):
            if not isinstance(feature, Mapping):
                continue
            properties = feature.get("properties")
            geometry = feature.get("geometry")
            if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
                continue
            identifier = str(properties.get(geography_id_field, "")).strip()
            if identifier not in summaries:
                continue
            if uses_prepared_display:
                simplified, dropped = dict(geometry), 0
            else:
                simplified, dropped = _quantize_display_geometry(
                    geometry,
                    coord_precision,
                )
            collapsed_rings += dropped
            if simplified is None:
                continue
            bounds = _geometry_coordinate_bounds(simplified["coordinates"])
            if bounds is None:
                continue
            extent[0] = min(extent[0], bounds[0])
            extent[1] = min(extent[1], bounds[1])
            extent[2] = max(extent[2], bounds[2])
            extent[3] = max(extent[3], bounds[3])
            _add_density_statistics(summaries[identifier], properties.get("LANDAREA"))
            features.append(
                {
                    "type": "Feature",
                    "properties": summaries[identifier],
                    "geometry": simplified,
                }
            )
            matched.add(identifier)
    if not features:
        raise ValueError("no geography summaries matched canonical boundaries")

    collection = {"type": "FeatureCollection", "features": features}
    display_boundaries_path = display_boundaries_path or out_path.with_suffix(
        ".geojson"
    )
    display_boundaries_path.parent.mkdir(parents=True, exist_ok=True)
    display_boundaries_path.write_text(
        json.dumps(collection, separators=(",", ":")),
        encoding="utf-8",
    )
    variables = _map_variable_specs(summaries)
    variables_json = _json_for_inline_script(variables)
    for formatter in _JS_FUNCS:
        variables_json = variables_json.replace(f'"{formatter}"', formatter)
    html = _TEMPLATE.format(
        title=html_escape(title, quote=True),
        geojson=_json_for_inline_script(collection),
        variables=variables_json,
        geography=_json_for_inline_script(geography_context),
        bounds=f"[[{extent[0]},{extent[1]}],[{extent[2]},{extent[3]}]]",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {
        "representation": (
            "display-only-topology-preserving-polygons"
            if uses_prepared_display
            else "display-only-fixed-grid-quantized-polygons"
        ),
        "coordinate_precision": coord_precision,
        "requested_geographies": len(summaries),
        "matched_geographies": len(matched),
        "missing_geographies": sorted(set(summaries) - matched),
        "collapsed_rings": collapsed_rings,
        "prepared_display_boundary_paths": (
            [str(path) for path in boundary_paths] if uses_prepared_display else []
        ),
        "map_path": str(out_path),
        "display_boundaries_path": str(display_boundaries_path),
    }


def prepare_national_map_statistics(
    *,
    plan_path: Path,
    geography_column: str,
    out_path: Path | None = None,
    jurisdiction_pruids: frozenset[str] | None = None,
) -> dict[str, object]:
    """Aggregate and cache map statistics from national-plan batch artifacts.

    Every selected completed household/person pair is streamed once and tied to
    its recorded checksum. A complete plan is required unless
    ``jurisdiction_pruids`` explicitly selects completed subsets. The returned
    evidence identifies coverage, source artifacts, cache validity, and the
    standard household/person variables available to the map.
    """

    return _prepare_national_map_statistics(
        compute_statistics=_compute_geo_stats,
        plan_path=plan_path,
        geography_column=geography_column,
        out_path=out_path,
        jurisdiction_pruids=jurisdiction_pruids,
    )


def render_national_plan_map(
    *,
    plan_path: Path,
    geography_level: str,
    geography_column: str,
    out_path: Path | None = None,
    coord_precision: int = 3,
    title: str = "National Synthetic Population",
    jurisdiction_pruids: frozenset[str] | None = None,
) -> dict[str, object]:
    """Render a national polygon map or an explicit completed subset.

    Plan geography, prepared jurisdiction boundaries, and cached batch
    statistics are validated and combined into the standard interactive
    choropleth. Partial plans require ``jurisdiction_pruids`` so their output
    cannot be mistaken for national coverage. The returned report records the
    map path, selected coverage, and supporting artifacts.
    """

    from synthpopcan.geography import statcan_geography_universe

    plan = json.loads(plan_path.read_text())
    if not isinstance(plan, Mapping):
        raise ValueError("national small-area plan must be completed")
    if plan.get("status") != "completed" and jurisdiction_pruids is None:
        raise ValueError("national small-area plan must be completed")
    inputs = plan.get("inputs")
    boundaries = inputs.get("boundaries") if isinstance(inputs, Mapping) else None
    boundary_value = boundaries.get("path") if isinstance(boundaries, Mapping) else None
    if not isinstance(boundary_value, str):
        raise ValueError("national plan boundary input path is invalid")
    root = plan_path.parent
    boundary_path = _resolve_plan_path(root, boundary_value)
    prepared_display_boundary_paths = sorted(
        (root / "boundaries").glob(
            f"*-boundary-{geography_level.lower()}-*-display-topo.geojson"
        )
    )
    if jurisdiction_pruids is not None:
        prepared_display_boundary_paths = [
            path
            for path in prepared_display_boundary_paths
            if any(
                path.name.endswith(f"-{pruid}-display-topo.geojson")
                for pruid in jurisdiction_pruids
            )
        ]
    if not prepared_display_boundary_paths:
        sibling_display = boundary_path.with_name(
            f"{boundary_path.stem}-display-topo.geojson"
        )
        if sibling_display.is_file():
            prepared_display_boundary_paths = [sibling_display]
    if not prepared_display_boundary_paths and jurisdiction_pruids is not None:
        from synthpopcan.geodata import fetch_display_boundaries

        try:
            prepared_display_boundary_paths = [
                fetch_display_boundaries(
                    2021,
                    geography_level,
                    pruid=pruid,
                )
                for pruid in sorted(jurisdiction_pruids)
            ]
        except FileNotFoundError:
            # A release catalogue is optional until the geodata release is
            # published; retain the canonical-boundary fallback in that case.
            prepared_display_boundary_paths = []
    out_path = out_path or root / "national-map.html"
    scope = "-".join(sorted(jurisdiction_pruids or ()))
    statistics_path = root / (
        f"national-map-statistics-{scope}.csv"
        if scope
        else "national-map-statistics.csv"
    )
    statistics = prepare_national_map_statistics(
        plan_path=plan_path,
        geography_column=geography_column,
        out_path=statistics_path,
        jurisdiction_pruids=jurisdiction_pruids,
    )
    report = render_geography_summary_polygon_map(
        summary_path=statistics_path,
        boundaries_path=boundary_path,
        geography_column=geography_column,
        out_path=out_path,
        display_boundaries_path=out_path.with_suffix(".geojson"),
        prepared_display_boundary_paths=(prepared_display_boundary_paths or None),
        coord_precision=coord_precision,
        title=title,
        geography_context=statcan_geography_universe(
            2021,
            geography_level,
            geography_column,
            dguid_column="DGUID",
        ).as_dict(),
    )
    report["statistics"] = statistics
    return report


def _read_geography_summaries(
    summary_path: Path,
    geography_column: str,
) -> dict[str, dict[str, object]]:
    summaries: dict[str, dict[str, object]] = {}
    with summary_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            identifier = str(row.get(geography_column, "")).strip()
            if not identifier:
                continue
            households = int(row.get("n_households", row.get("households", 0)) or 0)
            persons = int(row.get("n_persons", row.get("persons", 0)) or 0)
            summary: dict[str, object] = {
                "geo_id": identifier,
                "jurisdiction": str(row.get("jurisdiction", "")),
                "n_households": households,
                "n_persons": persons,
            }
            for field in (
                "avg_hh_size",
                "median_hh_income",
                "median_shelter_cost",
                "pct_owner",
                "pct_detached",
                "pct_major_repairs",
                "pct_child",
                "pct_senior",
                "pct_immigrant",
                "pct_vismin",
            ):
                raw_value = row.get(field)
                if raw_value not in (None, ""):
                    summary[field] = float(raw_value)
            summary.setdefault(
                "avg_hh_size",
                persons / households if households else 0.0,
            )
            summaries[identifier] = summary
    if not summaries:
        raise ValueError("geography summary contains no identifiers")
    return summaries


def _add_density_statistics(summary: dict[str, Any], land_area: object) -> None:
    """Use published land area in km², never area from simplified display geometry."""
    if isinstance(land_area, bool):
        return
    try:
        area = float(land_area)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    if not math.isfinite(area) or area <= 0:
        return
    for count_field, density_field in (
        ("n_households", "households_per_km2"),
        ("n_persons", "persons_per_km2"),
    ):
        count = summary.get(count_field)
        if isinstance(count, (int, float)) and math.isfinite(count) and count >= 0:
            summary[density_field] = count / area


def _person_variable_spec(name, label, values, formatter):
    if formatter == _FMT_PCT:
        return _pct_spec(name, label, values)
    prefix = "$" if formatter == _FMT_DOLLAR else ""
    decimals = 0 if formatter in (_FMT_DOLLAR, _FMT_INT) else 2
    return _variable_spec(
        name,
        label,
        values,
        formatter,
        f"{prefix}{min(values):,.{decimals}f}",
        f"{prefix}{max(values):,.{decimals}f}",
    )


def _person_variable_specs(
    summaries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    from synthpopcan._person_map_statistics import _INCOMES, _METRICS

    definitions = [
        (
            "persons_per_km2",
            "People per km²",
            _FMT_F2,
            "People divided by published land area in km².",
        ),
        (
            "n_persons",
            "Total people",
            _FMT_INT,
            "Synthetic people in private households, counted from person records.",
        ),
        *[
            (
                m.name,
                m.label,
                _FMT_PCT,
                f"Denominator: {m.universe}. Missing and inapplicable values excluded.",
            )
            for m in _METRICS
        ],
        *[
            (
                name,
                label,
                _FMT_DOLLAR,
                "Known income among people aged 15+. Includes observed zero and "
                "negative income; excludes unavailable/inapplicable codes.",
            )
            for _, name, label in _INCOMES
        ],
    ]
    variables = []
    for name, label, formatter, note in definitions:
        values = [
            float(s[name])
            for s in summaries.values()
            if isinstance(s.get(name), (int, float)) and math.isfinite(s[name])
        ]
        if not values:
            continue
        spec = _person_variable_spec(name, label, values, formatter)
        if name.startswith(("pct_mother_tongue_", "pct_home_language_")):
            note += " Multiple language responses may overlap."
        spec["note"] = note
        variables.append(spec)
    return variables


def _map_variable_specs(
    summaries: Mapping[str, Mapping[str, object]],
) -> list[dict[str, Any]]:
    scalar_definitions = (
        ("persons_per_km2", "People per km²", _FMT_F2),
        ("households_per_km2", "Households per km²", _FMT_F2),
        ("n_households", "Households", _FMT_INT),
        ("n_persons", "Persons", _FMT_INT),
        ("avg_hh_size", "Avg Household Size", _FMT_F2),
        ("median_hh_income", "Median HH Income", _FMT_DOLLAR),
        ("median_shelter_cost", "Median Shelter Cost", _FMT_DOLLAR),
    )
    variables: list[dict[str, Any]] = []
    for field, label, formatter in scalar_definitions:
        values: list[float] = []
        for summary in summaries.values():
            value = summary.get(field)
            if isinstance(value, (int, float)):
                values.append(float(value))
        if not values:
            continue
        if formatter == _FMT_INT:
            low, high = f"{min(values):,.0f}", f"{max(values):,.0f}"
        elif formatter == _FMT_DOLLAR:
            low, high = f"${min(values):,.0f}", f"${max(values):,.0f}"
        else:
            low, high = f"{min(values):.2f}", f"{max(values):.2f}"
        variables.append(
            _variable_spec(field, label, values, formatter, fmt_lo=low, fmt_hi=high)
        )
    for field, label in (
        ("pct_owner", "% Homeowners"),
        ("pct_detached", "% Detached Dwellings"),
        ("pct_major_repairs", "% Needing Major Repairs"),
        ("pct_child", "% Children (under 20)"),
        ("pct_senior", "% Seniors (65+)"),
        ("pct_immigrant", "% Immigrants"),
        ("pct_vismin", "% Visible Minority"),
    ):
        values = [
            float(value)
            for summary in summaries.values()
            if isinstance((value := summary.get(field)), (int, float))
        ]
        if values:
            variables.append(_pct_spec(field, label, values))
    return variables


_POINT_SUMMARY_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
  <link href="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.css" rel="stylesheet">
  <script src="https://unpkg.com/maplibre-gl@4/dist/maplibre-gl.js"></script>
  <style>
    html,body,#map{{height:100%;margin:0}}
    body{{font-family:system-ui,sans-serif}}
    #panel{{position:absolute;z-index:2;left:12px;top:12px;background:#fffffff2;
      border-radius:9px;padding:10px 13px;box-shadow:0 2px 12px #0004}}
    #panel strong{{display:block;font-size:13px}}
    #panel span{{font-size:11px;color:#555}}
    #tip{{position:absolute;display:none;z-index:3;pointer-events:none;
      background:#111e;color:white;padding:8px 11px;border-radius:7px;font-size:12px}}
  </style>
</head>
<body>
<div id="map"></div>
<div id="panel"><strong>{title}</strong>
  <span>Markers use canonical-feature bounding-box centres;
    boundaries are unchanged.</span>
</div>
<div id="tip"></div>
<script>
const DATA={geojson};
const GEOGRAPHY={geography};
const map=new maplibregl.Map({{
  container:'map',style:'https://tiles.openfreemap.org/styles/liberty',
  bounds:{bounds},fitBoundsOptions:{{padding:35}}
}});
map.addControl(new maplibregl.NavigationControl(),'top-right');
map.on('load',()=>{{
  map.addSource('areas',{{type:'geojson',data:DATA}});
  map.addLayer({{
    id:'areas',type:'circle',source:'areas',
    paint:{{
      'circle-radius':['interpolate',['linear'],['sqrt',['get','n_households']],
        0,2,350,6,1200,11],
      'circle-color':['interpolate',['linear'],['get','n_persons'],
        0,'#deebf7',1000,'#6baed6',5000,'#08519c'],
      'circle-opacity':0.72,'circle-stroke-color':'#fff','circle-stroke-width':0.5
    }}
  }});
  const tip=document.getElementById('tip');
  map.on('mousemove','areas',e=>{{
    const p=e.features[0].properties;
    const households=Number(p.n_households).toLocaleString();
    const persons=Number(p.n_persons).toLocaleString();
    tip.textContent=`${{p.geo_id}} · ${{households}} households ·
      ${{persons}} persons`;
    tip.style.display='block';tip.style.left=(e.point.x+14)+'px';tip.style.top=(e.point.y-8)+'px';
  }});
  map.on('mouseleave','areas',()=>{{tip.style.display='none'}});
}});
</script>
</body>
</html>
"""


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
