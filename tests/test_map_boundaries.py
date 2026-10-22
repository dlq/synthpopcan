"""Map boundaries behaviour and regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.map_fixtures import (
    _write_fake_geojson,
    _write_fake_shapefile,
)

from synthpopcan.map_render import (
    _read_geojson_file,
    filter_boundaries_geojson,
    prepare_boundaries_geojson,
)


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


def test_filter_boundaries_geojson_streams_reviewed_subset(tmp_path: Path) -> None:
    source = tmp_path / "national.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "001", "DGUID": "d1"},
                        "geometry": {"type": "Point", "coordinates": [1, 2]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "002", "DGUID": "d2"},
                        "geometry": {"type": "Point", "coordinates": [3, 4]},
                    },
                ],
            },
            indent=2,
        )
    )
    output = tmp_path / "subset.geojson"

    report = filter_boundaries_geojson(source, output, {"002", "003"})

    payload = json.loads(output.read_text())
    assert [feature["properties"]["geo_id"] for feature in payload["features"]] == [
        "002"
    ]
    assert report["source_features"] == 2
    assert report["matched_identifiers"] == 1
    assert report["missing_identifiers"] == ["003"]
    assert report["output_bytes"] < report["source_bytes"]


def test_filter_boundaries_geojson_rejects_empty_selection(tmp_path: Path) -> None:
    source = tmp_path / "national.geojson"
    source.write_text('{"type":"FeatureCollection","features":[]}')

    with pytest.raises(ValueError, match="at least one"):
        filter_boundaries_geojson(source, tmp_path / "subset.geojson", set())


def test_filter_boundaries_geojson_uses_compact_streaming_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "national.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"geo_id": identifier},
                "geometry": {"type": "Point", "coordinates": [index, index]},
            }
            for index, identifier in enumerate(("001", "002", "003"))
        ],
    }
    source.write_text(json.dumps(payload, separators=(",", ":")))
    output = tmp_path / "subset.geojson"

    report = filter_boundaries_geojson(source, output, {"001", "003"})

    result = json.loads(output.read_text())
    assert [feature["properties"]["geo_id"] for feature in result["features"]] == [
        "001",
        "003",
    ]
    assert report["source_features"] == 3


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
