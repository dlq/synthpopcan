from __future__ import annotations

import csv
import json
import shlex
from pathlib import Path

from synthpopcan.models import model_payload
from synthpopcan.workflows.small_area import (
    SmallAreaRequest,
    synthesize_small_area_files,
)


def test_small_area_workflow_generates_calibrates_and_reports(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(model_payload("demo-linked-household-person")))
    controls_path = tmp_path / "controls.csv"
    controls_path.write_text(
        "margin,dimensions,tract,tenure,count\n"
        'tenure,"tract,tenure",001,owner,2\n'
        'tenure,"tract,tenure",001,renter,1\n'
        'tenure,"tract,tenure",002,owner,2\n'
        'tenure,"tract,tenure",002,renter,1\n'
    )
    boundaries_path = tmp_path / "boundaries.geojson"
    boundaries_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": geography},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [offset, 0],
                                    [offset + 0.5, 0],
                                    [offset + 0.5, 0.5],
                                    [offset, 0.5],
                                    [offset, 0],
                                ]
                            ],
                        },
                    }
                    for geography, offset in (("001", 0), ("002", 1))
                ],
            }
        )
    )
    events = []

    result = synthesize_small_area_files(
        SmallAreaRequest(
            package_path=package_path,
            controls_path=controls_path,
            candidates_dir=tmp_path / "candidates",
            output_dir=tmp_path / "output",
            candidate_households=20,
            geography_dimension="tract",
            geography_column="tract",
            conditions={"geo": "Demo North"},
            package_reference="demo-linked-household-person",
            random_seed=13,
            pool_size=20,
            subsample_seed=7,
            chunk_size=3,
            max_household_size=5,
            include_weights=True,
            boundaries_path=boundaries_path,
            map_path=tmp_path / "output" / "map.html",
        ),
        progress=events.append,
    )

    households = list(csv.DictReader(result.households_path.open()))
    persons = list(csv.DictReader(result.persons_path.open()))
    assert len(households) == 6
    assert len(persons) > 0
    assert {row["tract"] for row in households} == {"001", "002"}
    assert result.details["assigned_households"] == 6
    assert result.details["assigned_persons"] == len(persons)
    assert (
        result.details["linked_population"]["schema_version"]
        == "synthpopcan-linked-population-v1"
    )
    assert result.details["linked_population"]["geography"] == {
        "household_column": "tract",
        "person_assignment": "inherited-via-household",
    }
    assert result.details["summary"]["non_converged_count"] == 0
    assert result.map_path is not None
    assert "maplibregl" in result.map_path.read_text()
    assert result.weights_path is not None
    assert result.weights_path.is_file()
    assert {event.stage for event in events} >= {
        "generating",
        "calibrating",
        "completed",
    }
    assert shlex.split(result.reproduction.command.render())[:4] == [
        "synthpopcan",
        "geo",
        "synthesize",
        "demo-linked-household-person",
    ]


def test_small_area_workflow_accepts_existing_linked_candidates(tmp_path: Path) -> None:
    households_path = tmp_path / "candidate-households.csv"
    persons_path = tmp_path / "candidate-persons.csv"
    controls_path = tmp_path / "controls.csv"
    households_path.write_text(
        "synthetic_household_id,household_size,tenure\nh1,1,owner\nh2,1,renter\n"
    )
    persons_path.write_text(
        "synthetic_person_id,synthetic_household_id,sex\np1,h1,F\np2,h2,M\n"
    )
    controls_path.write_text(
        "margin,dimensions,tract,tenure,count\n"
        'tenure,"tract,tenure",001,owner,1\n'
        'tenure,"tract,tenure",001,renter,1\n'
    )

    result = synthesize_small_area_files(
        SmallAreaRequest(
            package_path=None,
            controls_path=controls_path,
            candidates_dir=tmp_path / "candidates",
            output_dir=tmp_path / "output",
            candidate_households=2,
            geography_dimension="tract",
            geography_column="tract",
            conditions={},
            candidate_households_path=households_path,
            candidate_persons_path=persons_path,
            pool_size=2,
        )
    )

    assert result.details["assigned_households"] == 2
    assert result.details["assigned_persons"] == 2
    assert shlex.split(result.reproduction.command.render())[:3] == [
        "synthpopcan",
        "geo",
        "calibrate",
    ]
