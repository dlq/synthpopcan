from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import synthpopcan.da_proof as da_proof_module
from synthpopcan.da_proof import (
    finalize_quebec_da_proof,
    prepare_quebec_da_proof,
    select_quebec_da_relationships,
)


def _write_dgrf(path: Path) -> tuple[list[str], list[str]]:
    metro = ["24660001", "24660002"]
    rural = ["24790108", "24790109"]
    fieldnames = [
        "PRDGUID_PRIDUGD",
        "CSDDGUID_SDRIDUGD",
        "DADGUID_ADIDUGD",
        "CMADGUID_RMRIDUGD",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for da_id in metro:
            row = {
                "PRDGUID_PRIDUGD": "2021A000224",
                "CSDDGUID_SDRIDUGD": "2021A00052466023",
                "DADGUID_ADIDUGD": f"2021S0512{da_id}",
                "CMADGUID_RMRIDUGD": "2021S0503462",
            }
            writer.writerow(row)
            writer.writerow(row)
        for da_id in rural:
            writer.writerow(
                {
                    "PRDGUID_PRIDUGD": "2021A000224",
                    "CSDDGUID_SDRIDUGD": "2021A00052479088",
                    "DADGUID_ADIDUGD": f"2021S0512{da_id}",
                    "CMADGUID_RMRIDUGD": "",
                }
            )
    return metro, rural


def _write_profile(path: Path, identifiers: list[str]) -> None:
    fieldnames = [
        "GEO_LEVEL",
        "DGUID",
        "ALT_GEO_CODE",
        "CHARACTERISTIC_ID",
        "CHARACTERISTIC_NAME",
        "C1_COUNT_TOTAL",
    ]
    characteristics = [
        ("51", "1 person", "4"),
        ("52", "2 persons", "3"),
        ("53", "3 persons", "2"),
        ("54", "4 persons", "1"),
        ("55", "5 or more persons", "1"),
        ("1415", "Owner", "6"),
        ("1416", "Renter", "5"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for identifier in identifiers:
            for characteristic_id, name, count in characteristics:
                writer.writerow(
                    {
                        "GEO_LEVEL": "Dissemination area",
                        "DGUID": f"2021S0512{identifier}",
                        "ALT_GEO_CODE": identifier,
                        "CHARACTERISTIC_ID": characteristic_id,
                        "CHARACTERISTIC_NAME": name,
                        "C1_COUNT_TOTAL": count,
                    }
                )


def _write_boundaries(path: Path, identifiers: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "geo_id": identifier,
                            "DGUID": f"2021S0512{identifier}",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-73.0, 45.0],
                                    [-73.0, 45.1],
                                    [-72.9, 45.1],
                                    [-73.0, 45.0],
                                ]
                            ],
                        },
                    }
                    for identifier in [*identifiers, "24999999"]
                ],
            }
        )
    )


def test_select_quebec_da_relationships_deduplicates_db_rows(tmp_path: Path) -> None:
    relationship_path = tmp_path / "dgrf.csv"
    metro, rural = _write_dgrf(relationship_path)

    selection = select_quebec_da_relationships(relationship_path, per_area=2)

    relationships = selection["relationships"]
    assert isinstance(relationships, list)
    assert len(relationships) == 4
    assert {
        item["relationship"]["child"]["identifier"] for item in relationships
    } == set(metro + rural)
    assert {item["study_area"] for item in relationships} == {
        "metropolitan",
        "rural-non-cma-ca",
    }


@pytest.mark.scenario("SCN-GEO-001")
def test_prepare_quebec_da_proof_writes_bounded_review_artifacts(
    tmp_path: Path,
) -> None:
    relationship_path = tmp_path / "dgrf.csv"
    metro, rural = _write_dgrf(relationship_path)
    profile_path = tmp_path / "profile.csv"
    _write_profile(profile_path, metro + rural)
    boundary_path = tmp_path / "boundaries.geojson"
    _write_boundaries(boundary_path, metro + rural)
    output = tmp_path / "proof"

    manifest = prepare_quebec_da_proof(
        profile_path,
        boundary_path,
        relationship_path,
        output,
        target_households=80,
        per_area=2,
    )

    assert manifest["status"] == "prepared"
    assert manifest["controls"]["selected_geographies"] == 4
    assert manifest["boundaries"]["matched_identifiers"] == 4
    assert manifest["boundaries"]["source_features"] == 5
    assert (output / "controls.csv").is_file()
    assert (output / "boundaries.geojson").is_file()
    assert (output / "relationships.json").is_file()
    assert (
        json.loads((output / "proof-manifest.json").read_text())["schema_version"]
        == "synthpopcan-quebec-da-proof-v1"
    )

    population = output / "population"
    population.mkdir()
    identifiers = metro + rural
    (population / "households.csv").write_text(
        "synthetic_household_id,household_size,DAUID\n"
        + "".join(
            f"h{index},1,{identifier}\n" for index, identifier in enumerate(identifiers)
        )
    )
    (population / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id\n"
        + "".join(f"p{index},h{index}\n" for index in range(len(identifiers)))
    )
    geography_records = {
        identifier: {
            "assigned_households": 1,
            "realized_margin_summaries": [
                {"max_abs_error": 0.0},
            ],
        }
        for identifier in identifiers
    }
    (population / "report.json").write_text(
        json.dumps(
            {
                "calibration_mode": "household_only",
                "geography_universe": {
                    "census_vintage": 2021,
                    "geography_level": "da",
                    "identifier_namespace": "statcan:census:2021:da",
                },
                "geographies": geography_records,
                "input_checks": {"household": {"passed": True}},
                "summary": {
                    "converged_count": 4,
                    "non_converged_count": 0,
                    "non_converged_geographies": [],
                    "max_abs_error": 1e-8,
                    "realized_max_abs_error": 0.0,
                },
            }
        )
    )
    (population / "map.html").write_text(
        '<!doctype html><script>const GEOGRAPHY={"identifier_namespace":'
        '"statcan:census:2021:da"};</script>'
    )

    completed = finalize_quebec_da_proof(output, synthesis_seconds=1.25)

    assert completed["status"] == "completed"
    evidence = completed["synthesis_evidence"]
    assert evidence["linked_validation"]["passed"] is True
    assert evidence["geography_identifiers"]["unknown"] == []
    assert len(evidence["calibration"]["parent_summary"]) == 2
    assert evidence["resource_evidence"]["synthesis_seconds"] == 1.25

    manifest_path = output / "proof-manifest.json"
    valid_manifest = manifest_path.read_text()
    valid_households = (population / "households.csv").read_text()
    valid_report = (population / "report.json").read_text()
    valid_map = (population / "map.html").read_text()

    manifest_path.write_text(json.dumps({"schema_version": "bad"}))
    with pytest.raises(ValueError, match="unsupported"):
        finalize_quebec_da_proof(output)
    manifest_path.write_text(valid_manifest)

    (population / "households.csv").write_text(
        valid_households.replace(identifiers[0], "24999999")
    )
    with pytest.raises(ValueError, match="do not match"):
        finalize_quebec_da_proof(output)
    (population / "households.csv").write_text(valid_households)

    bad_report = json.loads(valid_report)
    bad_report["geography_universe"]["census_vintage"] = 2016
    (population / "report.json").write_text(json.dumps(bad_report))
    with pytest.raises(ValueError, match="incompatible geography"):
        finalize_quebec_da_proof(output)
    (population / "report.json").write_text(valid_report)

    bad_report = json.loads(valid_report)
    bad_report["summary"]["non_converged_count"] = 1
    (population / "report.json").write_text(json.dumps(bad_report))
    with pytest.raises(ValueError, match="did not converge"):
        finalize_quebec_da_proof(output)
    (population / "report.json").write_text(valid_report)

    (population / "map.html").unlink()
    with pytest.raises(ValueError, match="map is missing"):
        finalize_quebec_da_proof(output)
    (population / "map.html").write_text("<html></html>")
    with pytest.raises(ValueError, match="geography identity"):
        finalize_quebec_da_proof(output)
    (population / "map.html").write_text(valid_map)


def test_da_selection_rejects_bad_limits_and_relationship_inputs(
    tmp_path: Path,
) -> None:
    relationship_path = tmp_path / "dgrf.csv"
    _write_dgrf(relationship_path)
    with relationship_path.open("a") as handle:
        handle.write("2021A000235,,,\n")
        handle.write("2021A000224,,,\n")
    with pytest.raises(ValueError, match="at least 1"):
        select_quebec_da_relationships(relationship_path, per_area=0)
    with pytest.raises(ValueError, match="too few"):
        select_quebec_da_relationships(relationship_path, per_area=3)
    with pytest.raises(ValueError, match="rural CSD"):
        select_quebec_da_relationships(
            relationship_path,
            per_area=1,
            rural_csd="2400000",
        )

    missing = tmp_path / "missing.csv"
    missing.write_text("PRDGUID_PRIDUGD\n2021A000224\n")
    with pytest.raises(ValueError, match="missing required columns"):
        select_quebec_da_relationships(missing)

    invalid = tmp_path / "invalid.csv"
    invalid.write_text(
        "PRDGUID_PRIDUGD,CSDDGUID_SDRIDUGD,DADGUID_ADIDUGD,"
        "CMADGUID_RMRIDUGD\n"
        "2021A000224,2021A00052466023,bad,2021S0503462\n"
    )
    with pytest.raises(ValueError, match="invalid DA DGUID"):
        select_quebec_da_relationships(invalid, per_area=1)

    with invalid.open("a") as handle:
        handle.write("2021A000235,,,\n")
        handle.write("2021A000224,,,\n")
    with pytest.raises(ValueError, match="invalid DA DGUID"):
        select_quebec_da_relationships(invalid, per_area=1)


def test_da_selection_rejects_conflicting_db_relationships(tmp_path: Path) -> None:
    relationship_path = tmp_path / "dgrf.csv"
    fieldnames = [
        "PRDGUID_PRIDUGD",
        "CSDDGUID_SDRIDUGD",
        "DADGUID_ADIDUGD",
        "CMADGUID_RMRIDUGD",
    ]
    with relationship_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for csd in ("2021A00052466023", "2021A00052466024"):
            writer.writerow(
                {
                    "PRDGUID_PRIDUGD": "2021A000224",
                    "CSDDGUID_SDRIDUGD": csd,
                    "DADGUID_ADIDUGD": "2021S051224660001",
                    "CMADGUID_RMRIDUGD": "2021S0503462",
                }
            )
    with pytest.raises(ValueError, match="conflicting"):
        select_quebec_da_relationships(relationship_path, per_area=1)


def test_prepare_proof_rejects_missing_controls_and_boundaries(
    tmp_path: Path,
) -> None:
    relationship_path = tmp_path / "dgrf.csv"
    metro, rural = _write_dgrf(relationship_path)
    identifiers = metro + rural
    profile_path = tmp_path / "profile.csv"
    boundary_path = tmp_path / "boundaries.geojson"
    _write_boundaries(boundary_path, identifiers)

    _write_profile(profile_path, identifiers[:-1])
    with pytest.raises(ValueError, match="lack complete profile controls"):
        prepare_quebec_da_proof(
            profile_path,
            boundary_path,
            relationship_path,
            tmp_path / "missing-controls",
            target_households=40,
            per_area=2,
        )

    _write_profile(profile_path, identifiers)
    _write_boundaries(boundary_path, identifiers[:-1])
    with pytest.raises(ValueError, match="missing boundaries"):
        prepare_quebec_da_proof(
            profile_path,
            boundary_path,
            relationship_path,
            tmp_path / "missing-boundaries",
            target_households=40,
            per_area=2,
        )


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"relationships": [1]},
        {"relationships": [{}]},
        {"relationships": [{"relationship": {}}]},
    ],
)
def test_selected_identifier_parser_rejects_invalid_records(
    selection: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        da_proof_module._selected_identifiers(selection)


def test_da_proof_helper_validation_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid DA DGUID"):
        da_proof_module._short_id("bad", 8, "DA")
    not_object = tmp_path / "not-object.json"
    not_object.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        da_proof_module._read_json(not_object)
    with pytest.raises(ValueError, match="must be an object"):
        da_proof_module._mapping_value({"x": []}, "x")
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("other\n1\n")
    with pytest.raises(ValueError, match="missing DAUID"):
        da_proof_module._csv_identifiers(csv_path, "DAUID")


def test_finalize_rejects_failed_linkage_before_reading_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "proof-manifest.json").write_text(
        json.dumps({"schema_version": "synthpopcan-quebec-da-proof-v1"})
    )
    monkeypatch.setattr(
        da_proof_module,
        "validate_linked_population_files",
        lambda *args, **kwargs: {"passed": False},
    )

    with pytest.raises(ValueError, match="linked population"):
        finalize_quebec_da_proof(tmp_path)


@pytest.mark.parametrize(
    ("selection", "geographies", "message"),
    [
        ({}, {}, "relationships must be a list"),
        ({"relationships": [1]}, {}, "must be an object"),
        (
            {"relationships": [{}]},
            {},
            "relationship is invalid",
        ),
        (
            {
                "relationships": [
                    {
                        "study_area": "rural",
                        "relationship": {"parent": {}, "child": []},
                    }
                ]
            },
            {},
            "identities are invalid",
        ),
        (
            {
                "relationships": [
                    {
                        "study_area": "rural",
                        "relationship": {
                            "parent": {"identifier": 1},
                            "child": {"identifier": "001"},
                        },
                    }
                ]
            },
            {},
            "identifiers are invalid",
        ),
        (
            {
                "relationships": [
                    {
                        "study_area": "rural",
                        "relationship": {
                            "parent": {"identifier": "p"},
                            "child": {"identifier": "001"},
                        },
                    }
                ]
            },
            {},
            "missing selected DA",
        ),
        (
            {
                "relationships": [
                    {
                        "study_area": "rural",
                        "relationship": {
                            "parent": {"identifier": "p"},
                            "child": {"identifier": "001"},
                        },
                    }
                ]
            },
            {"001": {"assigned_households": "1"}},
            "must be an integer",
        ),
        (
            {
                "relationships": [
                    {
                        "study_area": "rural",
                        "relationship": {
                            "parent": {"identifier": "p"},
                            "child": {"identifier": "001"},
                        },
                    }
                ]
            },
            {"001": {"assigned_households": 1, "realized_margin_summaries": {}}},
            "must be a list",
        ),
    ],
)
def test_parent_summary_rejects_invalid_evidence(
    selection: dict[str, object],
    geographies: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        da_proof_module._parent_summary(selection, geographies)
