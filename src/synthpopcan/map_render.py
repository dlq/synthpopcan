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
import hashlib
import json
import math
import statistics
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
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


def filter_boundaries_geojson(
    source_path: Path,
    out_path: Path,
    keep_ids: set[str],
    *,
    id_property: str = "geo_id",
) -> dict[str, Any]:
    """Stream a small reviewed boundary subset from a large FeatureCollection.

    The source is decoded one feature at a time, so filtering a national DA
    file does not require loading the complete GeoJSON document into memory.
    The returned report names missing identifiers and records input/output
    sizes for resource-planning evidence.
    """

    if not keep_ids:
        raise ValueError("keep_ids must contain at least one geography identifier")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    matched: set[str] = set()
    source_features = 0
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=out_path.parent,
            prefix=f".{out_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write('{"type":"FeatureCollection","features":[')
            first = True
            features = _iter_selected_geojson_features(
                source_path,
                keep_ids,
                id_property,
            )
            for feature in features:
                source_features += 1
                if feature is None:
                    continue
                properties = feature.get("properties")
                if not isinstance(properties, dict):
                    continue
                identifier = str(properties.get(id_property, "")).strip()
                if identifier not in keep_ids:
                    continue
                if not first:
                    output.write(",")
                json.dump(feature, output, separators=(",", ":"))
                first = False
                matched.add(identifier)
            output.write("]}")
        temporary.replace(out_path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return {
        "schema_version": "synthpopcan-boundary-subset-v1",
        "source_features": source_features,
        "requested_identifiers": len(keep_ids),
        "matched_identifiers": len(matched),
        "missing_identifiers": sorted(keep_ids - matched),
        "source_bytes": source_path.stat().st_size,
        "output_bytes": out_path.stat().st_size,
    }


def partition_boundaries_geojson(
    source_path: Path,
    output_paths: Mapping[str, Path],
    identifier_partitions: Mapping[str, str],
    *,
    id_property: str = "geo_id",
) -> dict[str, Any]:
    """Partition national boundaries in one pass using an explicit ID mapping.

    Each requested identifier must map to a key in ``output_paths``. Outputs
    are compact FeatureCollections written atomically. The report records
    missing identifiers independently for each partition.
    """

    if not output_paths:
        raise ValueError("output_paths must contain at least one partition")
    unknown_partitions = sorted(set(identifier_partitions.values()) - set(output_paths))
    if unknown_partitions:
        raise ValueError(
            "identifier mapping references unknown partitions: "
            + ", ".join(unknown_partitions)
        )
    handles: dict[str, Any] = {}
    temporary_paths: dict[str, Path] = {}
    first = dict.fromkeys(output_paths, True)
    matched: dict[str, set[str]] = {key: set() for key in output_paths}
    source_features = 0
    try:
        for key, output_path in output_paths.items():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            )
            handles[key] = handle
            temporary_paths[key] = Path(handle.name)
            handle.write('{"type":"FeatureCollection","features":[')

        for feature in _iter_geojson_features_for_partition(source_path):
            source_features += 1
            if not isinstance(feature, dict):
                raise ValueError("GeoJSON features must be objects")
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                continue
            identifier = str(properties.get(id_property, "")).strip()
            partition = identifier_partitions.get(identifier)
            if partition is None:
                continue
            handle = handles[partition]
            if not first[partition]:
                handle.write(",")
            json.dump(feature, handle, separators=(",", ":"))
            first[partition] = False
            matched[partition].add(identifier)

        for handle in handles.values():
            handle.write("]}")
            handle.close()
        handles.clear()
        for key, output_path in output_paths.items():
            temporary_paths[key].replace(output_path)
    except BaseException:
        for handle in handles.values():
            handle.close()
        for temporary in temporary_paths.values():
            temporary.unlink(missing_ok=True)
        raise

    partitions: dict[str, dict[str, Any]] = {}
    for key, output_path in output_paths.items():
        requested = {
            identifier
            for identifier, partition in identifier_partitions.items()
            if partition == key
        }
        partitions[key] = {
            "requested_identifiers": len(requested),
            "matched_identifiers": len(matched[key]),
            "missing_identifiers": sorted(requested - matched[key]),
            "output_bytes": output_path.stat().st_size,
        }
    return {
        "schema_version": "synthpopcan-boundary-partition-v1",
        "source_features": source_features,
        "source_bytes": source_path.stat().st_size,
        "partitions": partitions,
    }


def _iter_geojson_features_for_partition(path: Path) -> Iterator[Any]:
    """Yield every feature from compact or general FeatureCollection JSON."""

    compact_prefix = b'{"type":"FeatureCollection","features":['
    pretty_prefix = (
        b'{\n  "type": "FeatureCollection",\n  "features": [\n'
        b'    {\n      "type": "Feature",'
    )
    with path.open("rb") as source:
        prefix = source.read(max(len(compact_prefix), len(pretty_prefix)))
    if prefix.startswith(compact_prefix):
        for raw_feature in _iter_compact_geojson_feature_bytes(path, compact_prefix):
            yield json.loads(raw_feature)
        return
    if prefix.startswith(pretty_prefix):
        marker = b'\n    {\n      "type": "Feature",'
        yield from _iter_marker_delimited_geojson_features(path, marker)
        return
    yield from _iter_geojson_features(path)


def _iter_marker_delimited_geojson_features(
    path: Path,
    marker: bytes,
) -> Iterator[Any]:
    """Split a consistently indented FeatureCollection without decode retries."""

    end_marker = b"\n  ]\n}"
    buffer = bytearray()
    started = False
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            buffer.extend(chunk)
            if not started:
                index = buffer.find(marker)
                if index < 0:
                    if len(buffer) > 1024 * 1024:
                        raise ValueError(
                            "formatted GeoJSON feature marker was not found"
                        )
                    continue
                del buffer[: index + 1]
                started = True
            while (index := buffer.find(marker, 1)) >= 0:
                raw_feature = bytes(buffer[:index]).rstrip()
                if raw_feature.endswith(b","):
                    raw_feature = raw_feature[:-1].rstrip()
                if raw_feature:
                    yield json.loads(raw_feature)
                del buffer[: index + 1]
    if not started:
        raise ValueError("formatted GeoJSON does not contain features")
    end = buffer.rfind(end_marker)
    if end < 0:
        raise ValueError("formatted GeoJSON features array is incomplete")
    final_feature = bytes(buffer[:end]).rstrip()
    if final_feature.endswith(b","):
        final_feature = final_feature[:-1].rstrip()
    if final_feature:
        yield json.loads(final_feature)


def _iter_selected_geojson_features(
    path: Path,
    keep_ids: set[str],
    id_property: str,
) -> Iterator[dict[str, Any] | None]:
    """Yield selected compact features and ``None`` for each skipped feature."""

    compact_prefix = b'{"type":"FeatureCollection","features":['
    with path.open("rb") as source:
        is_compact = source.read(len(compact_prefix)) == compact_prefix
    if not is_compact:
        for feature in _iter_geojson_features(path):
            if not isinstance(feature, dict):
                raise ValueError("GeoJSON features must be objects")
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                yield None
                continue
            identifier = str(properties.get(id_property, "")).strip()
            yield feature if identifier in keep_ids else None
        return

    tokens = {
        identifier: (
            json.dumps(id_property, separators=(",", ":")).encode()
            + b":"
            + json.dumps(identifier, separators=(",", ":")).encode()
        )
        for identifier in keep_ids
    }
    for raw_feature in _iter_compact_geojson_feature_bytes(path, compact_prefix):
        identifier = next(
            (candidate for candidate, token in tokens.items() if token in raw_feature),
            None,
        )
        if identifier is None:
            yield None
            continue
        feature = json.loads(raw_feature)
        if not isinstance(feature, dict):
            raise ValueError("GeoJSON features must be objects")
        yield feature


def _iter_compact_geojson_feature_bytes(
    path: Path,
    prefix: bytes,
) -> Iterator[bytes]:
    """Split the compact FeatureCollection emitted by this module in C-speed."""

    marker = b',{"type":"Feature","properties":'
    with path.open("rb") as source:
        if source.read(len(prefix)) != prefix:
            raise ValueError("GeoJSON is not a compact SynthPopCan FeatureCollection")
        buffer = b""
        while chunk := source.read(4 * 1024 * 1024):
            buffer += chunk
            while (index := buffer.find(marker)) >= 0:
                feature = buffer[:index]
                if feature:
                    yield feature
                buffer = buffer[index + 1 :]
        if not buffer.endswith(b"]}"):
            raise ValueError("compact GeoJSON features array is incomplete")
        final_feature = buffer[:-2]
        if final_feature:
            yield final_feature


def _iter_geojson_features(path: Path) -> Iterator[Any]:
    """Yield top-level FeatureCollection members with bounded buffering."""

    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as source:
        buffer = ""
        marker = '"features"'
        while marker not in buffer:
            chunk = source.read(64 * 1024)
            if not chunk:
                raise ValueError("GeoJSON does not contain a features array")
            buffer += chunk
            if len(buffer) > 1024 * 1024:
                raise ValueError("GeoJSON features array was not found in its header")
        marker_index = buffer.index(marker) + len(marker)
        array_index = buffer.find("[", marker_index)
        while array_index < 0:
            chunk = source.read(64 * 1024)
            if not chunk:
                raise ValueError("GeoJSON features value is not an array")
            buffer += chunk
            array_index = buffer.find("[", marker_index)
        buffer = buffer[array_index + 1 :]

        while True:
            buffer = buffer.lstrip()
            if buffer.startswith(","):
                buffer = buffer[1:].lstrip()
            while not buffer:
                chunk = source.read(64 * 1024)
                if not chunk:
                    raise ValueError("GeoJSON features array is incomplete")
                buffer += chunk
                buffer = buffer.lstrip()
            if buffer.startswith("]"):
                return
            try:
                feature, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError as exc:
                chunk = source.read(64 * 1024)
                if not chunk:
                    raise ValueError("GeoJSON contains an invalid feature") from exc
                buffer += chunk
                continue
            yield feature
            buffer = buffer[end:]


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
const GEOGRAPHY = {geography};

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


_NATIONAL_MAP_STATISTIC_FIELDS = (
    "n_households",
    "n_persons",
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
)


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

    from synthpopcan.statcan import file_integrity

    plan = json.loads(plan_path.read_text())
    if not isinstance(plan, Mapping):
        raise ValueError("national small-area plan must be completed")
    if plan.get("status") != "completed" and jurisdiction_pruids is None:
        raise ValueError("national small-area plan must be completed")
    records = plan.get("batches")
    if not isinstance(records, list):
        raise ValueError("national small-area plan batches must be a list")
    root = plan_path.parent
    out_path = out_path or root / "national-map-statistics.csv"
    manifest_path = out_path.with_suffix(".json")
    sources: list[dict[str, object]] = []
    batches: list[tuple[str, str, Path, Path]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("national small-area batch record must be an object")
        if (
            jurisdiction_pruids is not None
            and record.get("jurisdiction_pruid") not in jurisdiction_pruids
        ):
            continue
        manifest_value = record.get("manifest")
        if not isinstance(manifest_value, str):
            raise ValueError("national small-area batch manifest is invalid")
        batch_path = _resolve_plan_path(root, manifest_value)
        batch = json.loads(batch_path.read_text())
        if not isinstance(batch, Mapping) or batch.get("status") != "completed":
            raise ValueError(
                f"national small-area batch is not completed: {batch_path}"
            )
        result = batch.get("result")
        artifacts = result.get("artifacts") if isinstance(result, Mapping) else None
        if not isinstance(artifacts, Mapping):
            raise ValueError(
                f"national small-area batch artifacts are invalid: {batch_path}"
            )
        paths: dict[str, Path] = {}
        evidence: dict[str, object] = {"batch_id": batch.get("batch_id")}
        for name in ("households", "persons"):
            artifact = artifacts.get(name)
            if not isinstance(artifact, Mapping):
                raise ValueError(
                    f"national batch {name} artifact is invalid: {batch_path}"
                )
            path_value = artifact.get("path")
            if not isinstance(path_value, str):
                raise ValueError(
                    f"national batch {name} artifact is invalid: {batch_path}"
                )
            paths[name] = _resolve_plan_path(root, path_value)
            evidence[name] = {
                key: artifact.get(key) for key in ("path", "byte_size", "sha256")
            }
        jurisdiction = batch.get("jurisdiction")
        abbreviation = (
            str(jurisdiction.get("abbreviation", ""))
            if isinstance(jurisdiction, Mapping)
            else ""
        )
        batch_id = str(batch.get("batch_id", ""))
        batches.append((batch_id, abbreviation, paths["households"], paths["persons"]))
        sources.append(evidence)
    source_digest = hashlib.sha256(
        json.dumps(sources, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    if out_path.is_file() and manifest_path.is_file():
        cached = json.loads(manifest_path.read_text())
        if (
            isinstance(cached, Mapping)
            and cached.get("schema_version") == "synthpopcan-national-map-statistics-v1"
            and cached.get("source_digest") == source_digest
            and cached.get("geography_column") == geography_column
        ):
            artifact = cached.get("artifact")
            integrity = file_integrity(out_path)
            if isinstance(artifact, Mapping) and all(
                artifact.get(key) == integrity[key] for key in ("byte_size", "sha256")
            ):
                return dict(cached)

    rows: dict[str, dict[str, object]] = {}
    for batch_id, jurisdiction, households_path, persons_path in batches:
        statistics_by_geography = _compute_geo_stats(
            households_path,
            geography_column,
            persons_path,
        )
        for identifier, geography_statistics in statistics_by_geography.items():
            if identifier in rows:
                raise ValueError(
                    f"national map geography appears in multiple batches: {identifier}"
                )
            rows[identifier] = {
                geography_column: identifier,
                "jurisdiction": jurisdiction,
                "batch_id": batch_id,
                **geography_statistics,
            }
    if not rows:
        scope = (
            "selected national small-area batches"
            if jurisdiction_pruids
            else "national small-area batches"
        )
        raise ValueError(f"{scope} contain no map geographies")
    fieldnames = [
        geography_column,
        "jurisdiction",
        "batch_id",
        *_NATIONAL_MAP_STATISTIC_FIELDS,
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(f".{out_path.name}.tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for identifier in sorted(rows):
            writer.writerow(rows[identifier])
    temporary.replace(out_path)
    report: dict[str, object] = {
        "schema_version": "synthpopcan-national-map-statistics-v1",
        "source_digest": source_digest,
        "geography_column": geography_column,
        "jurisdiction_pruids": sorted(jurisdiction_pruids or ()),
        "geographies": len(rows),
        "batches": len(batches),
        "artifact": {
            "path": out_path.name,
            **file_integrity(out_path),
        },
    }
    manifest_temporary = manifest_path.with_name(f".{manifest_path.name}.tmp")
    manifest_temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    manifest_temporary.replace(manifest_path)
    return report


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


def _resolve_plan_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.is_file():
        return path
    for parent in (root, *root.parents):
        candidate = parent / path
        if candidate.is_file():
            return candidate
    return root / path


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


def _map_variable_specs(
    summaries: Mapping[str, Mapping[str, object]],
) -> list[dict[str, Any]]:
    scalar_definitions = (
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


def _quantize_display_geometry(
    geometry: Mapping[str, object],
    precision: int,
) -> tuple[dict[str, object] | None, int]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        return None, 0
    polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        return None, 0
    simplified_polygons: list[list[list[list[float]]]] = []
    collapsed = 0
    for polygon in polygons:
        if not isinstance(polygon, list):
            continue
        rings: list[list[list[float]]] = []
        exterior_collapsed = False
        for index, ring in enumerate(polygon):
            simplified = _quantize_display_ring(ring, precision)
            if simplified is None:
                collapsed += 1
                if index == 0:
                    exterior_collapsed = True
                    break
                continue
            rings.append(simplified)
        if rings and not exterior_collapsed:
            simplified_polygons.append(rings)
    if not simplified_polygons:
        return None, collapsed
    if geometry_type == "Polygon" and len(simplified_polygons) == 1:
        return {
            "type": "Polygon",
            "coordinates": simplified_polygons[0],
        }, collapsed
    return {
        "type": "MultiPolygon",
        "coordinates": simplified_polygons,
    }, collapsed


def _quantize_display_ring(
    value: object,
    precision: int,
) -> list[list[float]] | None:
    if not isinstance(value, list):
        return None
    ring: list[list[float]] = []
    for position in value:
        if (
            not isinstance(position, list)
            or len(position) < 2
            or not isinstance(position[0], (int, float))
            or not isinstance(position[1], (int, float))
        ):
            continue
        point = [
            round(float(position[0]), precision),
            round(float(position[1]), precision),
        ]
        if not ring or point != ring[-1]:
            ring.append(point)
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    if len(ring) < 4 or len({tuple(point) for point in ring[:-1]}) < 3:
        return None
    return ring


def _geometry_coordinate_bounds(
    value: object,
) -> tuple[float, float, float, float] | None:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        x = float(value[0])
        y = float(value[1])
        return x, y, x, y
    if not isinstance(value, list):
        return None
    children = [
        bounds
        for child in value
        if (bounds := _geometry_coordinate_bounds(child)) is not None
    ]
    if not children:
        return None
    return (
        min(bounds[0] for bounds in children),
        min(bounds[1] for bounds in children),
        max(bounds[2] for bounds in children),
        max(bounds[3] for bounds in children),
    )


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
