"""StatCan boundary conversion, bounded GeoJSON reads and display geometry."""

from __future__ import annotations

import json
import math
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np


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
    E0, N0 = 6_200_000.0, 3_000_000.0  # noqa: N806 - projection notation

    def _m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2)

    def _t(phi: float) -> float:
        sp = math.sin(phi)
        ec = ((1 + e * sp) / (1 - e * sp)) ** (e / 2)
        return math.tan(math.pi / 4 - phi / 2) * ec

    m1, m2 = _m(phi1), _m(phi2)
    t1, t2 = _t(phi1), _t(phi2)
    n = math.log(m1 / m2) / math.log(t1 / t2)
    F = m1 / (n * t1**n)  # noqa: N806 - projection notation
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


def _shapefile_property_indices(
    field_names: Sequence[str], property_fields: Sequence[str]
) -> dict[str, int]:
    indices = {name: field_names.index(name) for name in property_fields}
    if "LANDAREA" in field_names:
        indices.setdefault("LANDAREA", field_names.index("LANDAREA"))
    return indices


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
        property_indices = _shapefile_property_indices(field_names, property_fields)

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


def _prepare_boundaries_geojson(
    shp_path: Path,
    id_field: str,
    out_path: Path,
    coord_precision: int = 5,
    property_fields: tuple[str, ...] = (),
    trust_ring_winding: bool = False,
    *,
    reader,
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

            reader(
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
