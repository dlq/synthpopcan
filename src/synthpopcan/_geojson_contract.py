"""Narrow external GeoJSON values at the map presentation boundary."""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Literal, TypedDict, cast


class Geometry(TypedDict):
    """A decoded geometry with a declared type and coordinate array."""

    type: str
    coordinates: list[object]


class Feature(TypedDict):
    """A decoded GeoJSON feature retaining its original properties and geometry."""

    type: Literal["Feature"]
    properties: dict[str, object]
    geometry: Geometry


def _string_keyed(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(key, str) for key in cast(dict[object, object], value))


def feature_or_none(value: object) -> Feature | None:
    """Return a validated feature or None; never coerce or alter source data."""
    if not _string_keyed(value):
        return None
    fields = cast(dict[str, object], value)
    properties = fields.get("properties")
    geometry = fields.get("geometry")
    if fields.get("type") != "Feature" or not _string_keyed(properties):
        return None
    if not _string_keyed(geometry):
        return None
    shape = cast(dict[str, object], geometry)
    geometry_type = shape.get("type")
    if not isinstance(geometry_type, str) or geometry_type not in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
    }:
        return None
    if not isinstance(shape.get("coordinates"), list):
        return None
    return cast(Feature, fields)


def collection_features(value: object) -> list[object]:
    """Validate a decoded FeatureCollection and return its unmodified entries."""
    if not _string_keyed(value):
        raise ValueError("GeoJSON boundaries must be a FeatureCollection object")
    fields = cast(dict[str, object], value)
    features = fields.get("features")
    if fields.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise ValueError("GeoJSON boundaries must contain a FeatureCollection list")
    return cast(list[object], features)


def polygon_positions(geometry: Geometry) -> Iterator[tuple[float, float]]:
    """Stream finite positions from a polygon or multipolygon, rejecting bad rows."""
    coordinates = geometry["coordinates"]
    polygons = coordinates if geometry["type"] == "MultiPolygon" else [coordinates]
    found = False
    for polygon in polygons:
        if not isinstance(polygon, list):
            raise ValueError("GeoJSON polygon coordinates are invalid")
        for ring in cast(list[object], polygon):
            if not isinstance(ring, list):
                raise ValueError("GeoJSON polygon ring is invalid")
            for point in cast(list[object], ring):
                position = _position(point)
                found = True
                yield position
    if not found:
        raise ValueError("GeoJSON polygon has no valid coordinates")


def _position(value: object) -> tuple[float, float]:
    if not isinstance(value, list):
        raise ValueError("GeoJSON polygon position is invalid")
    items = cast(list[object], value)
    if len(items) < 2 or any(
        isinstance(item, bool) or not isinstance(item, (int, float))
        for item in items[:2]
    ):
        raise ValueError("GeoJSON polygon position is invalid")
    x, y = float(cast(int | float, items[0])), float(cast(int | float, items[1]))
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("GeoJSON polygon position must be finite")
    return x, y
