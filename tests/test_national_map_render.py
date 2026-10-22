"""National map render behaviour and regression tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from synthpopcan.map_render import (
    prepare_national_map_statistics,
    render_geography_summary_point_map,
    render_geography_summary_polygon_map,
    render_national_plan_map,
)


def test_render_geography_summary_point_map_uses_boundary_centres(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "summary.csv"
    summary.write_text(
        "DAUID,jurisdiction,households,persons\n"
        "1001,NL,2,5\n"
        "1002,NL,1,1\n"
        "missing,NL,3,8\n"
    )
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "1001"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[-60, 45], [-58, 45], [-58, 47], [-60, 45]]
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "1002"},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [
                                    [
                                        [-56, 48],
                                        [-54, 48],
                                        [-54, 50],
                                        [-56, 48],
                                    ]
                                ]
                            ],
                        },
                    },
                ],
            }
        )
    )

    report = render_geography_summary_point_map(
        summary_path=summary,
        boundaries_path=boundaries,
        geography_column="DAUID",
        out_path=tmp_path / "national-map.html",
        points_path=tmp_path / "national-map.geojson",
    )

    assert report["representation"] == "canonical-feature-bounding-box-centre"
    assert report["matched_geographies"] == 2
    assert report["missing_geographies"] == ["missing"]
    points = json.loads((tmp_path / "national-map.geojson").read_text())
    assert [feature["geometry"]["coordinates"] for feature in points["features"]] == [
        [-59.0, 46.0],
        [-55.0, 49.0],
    ]
    assert points["features"][0]["properties"]["avg_hh_size"] == 2.5
    html = (tmp_path / "national-map.html").read_text()
    assert "boundaries are unchanged" in html
    assert "n_households" in html


def test_render_geography_summary_point_map_rejects_empty_or_unmatched_data(
    tmp_path: Path,
) -> None:
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text('{"type":"FeatureCollection","features":[]}')
    summary = tmp_path / "summary.csv"
    summary.write_text("DAUID,households,persons\n")
    with pytest.raises(ValueError, match="contains no identifiers"):
        render_geography_summary_point_map(
            summary_path=summary,
            boundaries_path=boundaries,
            geography_column="DAUID",
            out_path=tmp_path / "map.html",
        )

    summary.write_text("DAUID,households,persons\n1001,1,2\n")
    with pytest.raises(ValueError, match="no geography summaries matched"):
        render_geography_summary_point_map(
            summary_path=summary,
            boundaries_path=boundaries,
            geography_column="DAUID",
            out_path=tmp_path / "map.html",
        )


def test_render_geography_summary_polygon_map_quantizes_display_boundaries(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "summary.csv"
    summary.write_text(
        "ADAUID,jurisdiction,households,persons\n"
        "1001,NL,2,5\n"
        "1002,NL,1,1\n"
        "missing,NL,3,8\n"
    )
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "1001"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [0.0004, 0.0004],
                                    [1.0004, 0.0004],
                                    [1.0004, 1.0004],
                                    [0.0004, 1.0004],
                                    [0.0004, 0.0004],
                                ],
                                [
                                    [0.1, 0.1],
                                    [0.1001, 0.1],
                                    [0.1, 0.1001],
                                    [0.1, 0.1],
                                ],
                            ],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "1002"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [1.0004, 0.0004],
                                    [2.0004, 0.0004],
                                    [2.0004, 1.0004],
                                    [1.0004, 1.0004],
                                    [1.0004, 0.0004],
                                ]
                            ],
                        },
                    },
                ],
            }
        )
    )
    html_path = tmp_path / "map.html"
    display_path = tmp_path / "display.geojson"

    report = render_geography_summary_polygon_map(
        summary_path=summary,
        boundaries_path=boundaries,
        geography_column="ADAUID",
        out_path=html_path,
        display_boundaries_path=display_path,
        coord_precision=3,
    )

    assert report["representation"] == "display-only-fixed-grid-quantized-polygons"
    assert report["matched_geographies"] == 2
    assert report["missing_geographies"] == ["missing"]
    assert report["collapsed_rings"] == 1
    display = json.loads(display_path.read_text())
    assert display["features"][0]["geometry"]["coordinates"][0][1] == [1.0, 0.0]
    assert display["features"][1]["geometry"]["coordinates"][0][-1] == [1.0, 0.0]
    assert display["features"][0]["properties"]["avg_hh_size"] == 2.5
    html = html_path.read_text()
    assert "syn-fill" in html
    assert "Avg Household Size" in html


def test_render_geography_summary_polygon_map_rejects_invalid_inputs(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "summary.csv"
    summary.write_text("ADAUID,households,persons\n1001,1,2\n")
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text('{"type":"FeatureCollection","features":[]}')
    with pytest.raises(ValueError, match="coord_precision"):
        render_geography_summary_polygon_map(
            summary_path=summary,
            boundaries_path=boundaries,
            geography_column="ADAUID",
            out_path=tmp_path / "map.html",
            coord_precision=-1,
        )
    with pytest.raises(ValueError, match="no geography summaries matched"):
        render_geography_summary_polygon_map(
            summary_path=summary,
            boundaries_path=boundaries,
            geography_column="ADAUID",
            out_path=tmp_path / "map.html",
        )


def test_national_plan_map_aggregates_and_reuses_full_standard_statistics(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    households = population / "households.csv"
    households.write_text(
        "synthetic_household_id,ADAUID,household_size,TENUR,DTYPE,REPAIR,SHELCO\n"
        "h1,1001,1,1,1,3,1000\n"
        "h2,1001,2,2,2,1,2000\n"
    )
    persons = population / "persons.csv"
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ADAUID,AGEGRP,IMMSTAT,"
        "VISMIN,TOTINC\n"
        "p1,h1,1001,2,2,1,10000\n"
        "p2,h2,1001,14,1,2,20000\n"
        "p3,h2,1001,10,1,2,30000\n"
    )
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "1001"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]]],
                        },
                    }
                ],
            }
        )
    )
    batch = {
        "batch_id": "10-0001",
        "status": "completed",
        "jurisdiction": {"abbreviation": "NL"},
        "result": {
            "artifacts": {
                "households": {"path": "population/households.csv"},
                "persons": {"path": "population/persons.csv"},
            }
        },
    }
    (tmp_path / "batch.json").write_text(json.dumps(batch))
    plan = {
        "status": "completed",
        "inputs": {"boundaries": {"path": "boundaries.geojson"}},
        "batches": [{"manifest": "batch.json"}],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))

    statistics = prepare_national_map_statistics(
        plan_path=plan_path,
        geography_column="ADAUID",
    )
    cached = prepare_national_map_statistics(
        plan_path=plan_path,
        geography_column="ADAUID",
    )

    assert statistics == cached
    (tmp_path / "national-map-statistics.csv").write_text("corrupt\n")
    rebuilt = prepare_national_map_statistics(
        plan_path=plan_path,
        geography_column="ADAUID",
    )
    assert rebuilt == statistics
    with (tmp_path / "national-map-statistics.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["n_households"] == "2"
    assert row["n_persons"] == "3"
    assert float(row["pct_owner"]) == 50.0
    assert float(row["median_hh_income"]) == 30000.0

    report = render_national_plan_map(
        plan_path=plan_path,
        geography_level="ada",
        geography_column="ADAUID",
    )

    assert report["matched_geographies"] == 1
    html = (tmp_path / "national-map.html").read_text()
    for label in (
        "Median HH Income",
        "Median Shelter Cost",
        "% Homeowners",
        "% Detached Dwellings",
        "% Needing Major Repairs",
        "% Children (under 20)",
        "% Seniors (65+)",
        "% Immigrants",
        "% Visible Minority",
    ):
        assert label in html


def test_national_plan_map_accepts_completed_jurisdiction_subset(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    (population / "households.csv").write_text(
        "synthetic_household_id,DAUID,household_size,TENUR\nh1,24010001,1,1\n"
    )
    (population / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id,DAUID,AGEGRP,IMMSTAT,VISMIN,TOTINC\n"
        "p1,h1,24010001,2,1,1,10000\n"
    )
    (tmp_path / "boundaries.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "24010001"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]]],
                        },
                    }
                ],
            }
        )
    )
    (tmp_path / "completed.json").write_text(
        json.dumps(
            {
                "batch_id": "24-0001",
                "status": "completed",
                "jurisdiction": {"abbreviation": "QC"},
                "result": {
                    "artifacts": {
                        "households": {"path": "population/households.csv"},
                        "persons": {"path": "population/persons.csv"},
                    }
                },
            }
        )
    )
    (tmp_path / "pending.json").write_text(json.dumps({"status": "planned"}))
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "inputs": {"boundaries": {"path": "boundaries.geojson"}},
                "batches": [
                    {"jurisdiction_pruid": "24", "manifest": "completed.json"},
                    {"jurisdiction_pruid": "35", "manifest": "pending.json"},
                ],
            }
        )
    )

    report = render_national_plan_map(
        plan_path=plan_path,
        geography_level="da",
        geography_column="DAUID",
        jurisdiction_pruids=frozenset({"24"}),
    )

    assert report["matched_geographies"] == 1
    assert report["statistics"]["jurisdiction_pruids"] == ["24"]
    assert (tmp_path / "national-map-statistics-24.csv").is_file()


def test_national_map_statistics_rejects_invalid_plan_and_batches(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "plan.json"
    for payload, message in (
        ([], "must be completed"),
        ({"status": "partial"}, "must be completed"),
        ({"status": "completed", "batches": {}}, "batches must be a list"),
        (
            {"status": "completed", "batches": [3]},
            "batch record must be an object",
        ),
        (
            {"status": "completed", "batches": [{}]},
            "batch manifest is invalid",
        ),
    ):
        plan_path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match=message):
            prepare_national_map_statistics(
                plan_path=plan_path,
                geography_column="ADAUID",
            )

    def run_batch(batch: object) -> None:
        (tmp_path / "batch.json").write_text(json.dumps(batch))
        plan_path.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "batches": [{"manifest": "batch.json"}],
                }
            )
        )
        prepare_national_map_statistics(
            plan_path=plan_path,
            geography_column="ADAUID",
        )

    for batch, message in (
        ({"status": "planned"}, "batch is not completed"),
        ({"status": "completed"}, "batch artifacts are invalid"),
        (
            {"status": "completed", "result": {"artifacts": {}}},
            "households artifact is invalid",
        ),
        (
            {
                "status": "completed",
                "result": {"artifacts": {"households": {}}},
            },
            "households artifact is invalid",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            run_batch(batch)

    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,ADAUID\n")
    persons.write_text("synthetic_person_id,synthetic_household_id,ADAUID\n")
    empty_batch = {
        "status": "completed",
        "result": {
            "artifacts": {
                "households": {"path": households.name},
                "persons": {"path": persons.name},
            }
        },
    }
    with pytest.raises(ValueError, match="contain no map geographies"):
        run_batch(empty_batch)


def test_national_map_statistics_rejects_duplicate_batch_geography(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,ADAUID,household_size\nh1,1001,1\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,ADAUID\np1,h1,1001\n"
    )
    batch = {
        "status": "completed",
        "result": {
            "artifacts": {
                "households": {"path": households.name},
                "persons": {"path": persons.name},
            }
        },
    }
    for index in (1, 2):
        (tmp_path / f"batch-{index}.json").write_text(json.dumps(batch))
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "batches": [
                    {"manifest": "batch-1.json"},
                    {"manifest": "batch-2.json"},
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="appears in multiple batches"):
        prepare_national_map_statistics(
            plan_path=plan_path,
            geography_column="ADAUID",
        )


def test_render_national_plan_map_rejects_invalid_plan_inputs(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"status": "partial"}))
    with pytest.raises(ValueError, match="must be completed"):
        render_national_plan_map(
            plan_path=plan_path,
            geography_level="ada",
            geography_column="ADAUID",
        )

    plan_path.write_text(json.dumps({"status": "completed"}))
    with pytest.raises(ValueError, match="boundary input"):
        render_national_plan_map(
            plan_path=plan_path,
            geography_level="ada",
            geography_column="ADAUID",
        )
