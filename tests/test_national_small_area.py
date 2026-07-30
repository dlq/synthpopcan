from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click import ClickException, UsageError

import synthpopcan.national_da as national_da_compat
import synthpopcan.national_execution as national_execution_module
import synthpopcan.national_small_area as national_small_area_module
from synthpopcan.cli import main
from synthpopcan.cli_geo import (
    _national_plan_is_complete,
    _render_deferred_national_maps,
    _render_national_summary_map,
)
from synthpopcan.map_render import partition_boundaries_geojson
from synthpopcan.national_execution import (
    NationalBatchRunConfiguration,
    build_national_geography_summary,
    find_cached_national_candidate_pools,
    prepare_national_candidate_pools,
    reset_nonconverged_national_batches,
    run_national_cached_batch,
)
from synthpopcan.national_small_area import (
    CANADA_DA_JURISDICTIONS,
    estimate_national_small_area_storage,
    execute_canada_small_area_plan,
    load_2021_da_jurisdictions,
    load_2021_small_area_jurisdictions,
    prepare_canada_small_area_plan,
    regional_2021_da_profile_paths,
    required_2021_da_profile_keys,
    required_2021_profile_keys,
    small_area_specification,
)
from synthpopcan.statcan import file_integrity


def _parallel_test_batch(
    batch: dict[str, object],
    _root: Path,
) -> dict[str, object]:
    return {"batch_id": batch["batch_id"]}


def _parallel_fail_batch(
    batch: dict[str, object],
    _root: Path,
) -> dict[str, object]:
    raise RuntimeError(f"failed {batch['batch_id']}")


def test_national_da_compatibility_module_reexports_da_api() -> None:
    assert national_da_compat.CANADA_DA_JURISDICTIONS is CANADA_DA_JURISDICTIONS


def test_national_da_compatibility_path_and_relationship_wrappers(
    tmp_path: Path,
) -> None:
    expected = regional_2021_da_profile_paths(tmp_path)
    assert expected == national_small_area_module.national_2021_profile_paths(
        tmp_path,
        "da",
    )
    relationships = tmp_path / "relationships.csv"
    relationships.write_text(
        "PRDGUID_PRIDUGD,DADGUID_ADIDUGD\n2021A000210,2021S051210000001\n"
    )
    assert load_2021_da_jurisdictions(relationships) == {"10000001": "10"}
    assert (
        national_da_compat.prepare_canada_da_plan
        is national_small_area_module.prepare_canada_da_plan
    )
    assert (
        national_da_compat.execute_canada_da_plan
        is national_small_area_module.execute_canada_da_plan
    )


def _identifiers() -> dict[str, str]:
    return {
        jurisdiction.pruid: f"{jurisdiction.pruid}000001"
        for jurisdiction in CANADA_DA_JURISDICTIONS
    }


def _plan_identity(geography_level: str = "da") -> dict[str, object]:
    identifier_column = "DAUID" if geography_level == "da" else "ADAUID"
    return {
        "geography": {
            "schema_version": "synthpopcan-geography-universe-v1",
            "census_vintage": 2021,
            "geography_level": geography_level,
            "identifier_namespace": f"statcan:census:2021:{geography_level}",
            "identifier_column": identifier_column,
            "dguid_column": "DGUID",
        }
    }


def _write_dgrf(path: Path, identifiers: dict[str, str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "PRDGUID_PRIDUGD",
                "DADGUID_ADIDUGD",
                "ADADGUID_ADAIDUGD",
            ],
        )
        writer.writeheader()
        for pruid, identifier in identifiers.items():
            row = {
                "PRDGUID_PRIDUGD": f"2021A0002{pruid}",
                "DADGUID_ADIDUGD": f"2021S0512{identifier}",
                "ADADGUID_ADAIDUGD": f"2021S0516{identifier}",
            }
            writer.writerow(row)
            writer.writerow(row)


def _write_profile(
    path: Path,
    identifiers: list[str],
    geography_level: str = "da",
) -> None:
    fieldnames = [
        "GEO_LEVEL",
        "DGUID",
        "ALT_GEO_CODE",
        "CHARACTERISTIC_ID",
        "C1_COUNT_TOTAL",
    ]
    characteristics = [
        ("51", "4"),
        ("52", "3"),
        ("53", "2"),
        ("54", "1"),
        ("55", "1"),
        ("1415", "6"),
        ("1416", "5"),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for identifier in identifiers:
            for characteristic, count in characteristics:
                writer.writerow(
                    {
                        "GEO_LEVEL": (
                            "Dissemination area"
                            if geography_level == "da"
                            else "Aggregate dissemination area"
                        ),
                        "DGUID": (
                            f"2021S0512{identifier}"
                            if geography_level == "da"
                            else f"2021S0516{identifier}"
                        ),
                        "ALT_GEO_CODE": identifier,
                        "CHARACTERISTIC_ID": characteristic,
                        "C1_COUNT_TOTAL": count,
                    }
                )


def _write_profiles(
    root: Path,
    identifiers: dict[str, str],
    geography_level: str = "da",
) -> dict[str, Path]:
    paths = {
        key: root / f"2021-census-profile-{key}.csv"
        for key in required_2021_profile_keys(geography_level)
    }
    for key, path in paths.items():
        _write_profile(
            path,
            [
                identifiers[jurisdiction.pruid]
                for jurisdiction in CANADA_DA_JURISDICTIONS
                if small_area_specification(geography_level).profile_key_for(
                    jurisdiction
                )
                == key
            ],
            geography_level,
        )
    return paths


def _write_boundaries(path: Path, identifiers: dict[str, str]) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": identifier},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-75.0, 45.0],
                                    [-75.0, 45.1],
                                    [-74.9, 45.1],
                                    [-75.0, 45.0],
                                ]
                            ],
                        },
                    }
                    for identifier in identifiers.values()
                ],
            }
        )
    )


def _prepare(
    tmp_path: Path,
    geography_level: str = "da",
    *,
    compatibility_api: bool = False,
) -> tuple[Path, dict[str, object]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    identifiers = _identifiers()
    dgrf = tmp_path / "dgrf.csv"
    _write_dgrf(dgrf, identifiers)
    profiles = _write_profiles(tmp_path, identifiers, geography_level)
    boundaries = tmp_path / "boundaries.geojson"
    _write_boundaries(boundaries, identifiers)
    output = tmp_path / "national"
    progress: list[str] = []
    if compatibility_api:
        manifest = national_da_compat.prepare_canada_da_plan(
            profiles,
            boundaries,
            dgrf,
            output,
            max_households_per_batch=15,
            progress=progress.append,
        )
    else:
        manifest = prepare_canada_small_area_plan(
            profiles,
            boundaries,
            dgrf,
            output,
            geography_level=geography_level,
            max_households_per_batch=15,
            progress=progress.append,
        )
    assert progress[-1] == "Writing NU controls and batch manifests"
    return output / "plan.json", manifest


def test_national_da_profiles_cover_all_thirteen_jurisdictions() -> None:
    assert len(CANADA_DA_JURISDICTIONS) == 13
    assert required_2021_da_profile_keys() == (
        "da-atlantic",
        "da-quebec",
        "da-ontario",
        "da-prairies",
        "da-british-columbia",
        "da-territories",
    )
    assert {item.pruid for item in CANADA_DA_JURISDICTIONS} == {
        "10",
        "11",
        "12",
        "13",
        "24",
        "35",
        "46",
        "47",
        "48",
        "59",
        "60",
        "61",
        "62",
    }
    with pytest.raises(ValueError, match="must be da or ada"):
        small_area_specification("ct")
    assert {
        item.pruid: item.pumf_pr
        for item in CANADA_DA_JURISDICTIONS
        if item.pruid in {"60", "61", "62"}
    } == {"60": "70", "61": "70", "62": "70"}


def test_partition_boundaries_supports_compact_files_and_reports_missing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.geojson"
    source.write_text(
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","properties":{"geo_id":"10000001"},'
        '"geometry":{"type":"Polygon","coordinates":[]}},'
        '{"type":"Feature","properties":{"geo_id":"35000001"},'
        '"geometry":{"type":"Polygon","coordinates":[]}}]}'
    )
    outputs = {"10": tmp_path / "nl.geojson", "35": tmp_path / "on.geojson"}

    report = partition_boundaries_geojson(
        source,
        outputs,
        {
            "10000001": "10",
            "35000001": "35",
            "35000002": "35",
        },
    )

    assert report["source_features"] == 2
    assert report["partitions"]["10"]["matched_identifiers"] == 1
    assert report["partitions"]["35"]["missing_identifiers"] == ["35000002"]
    assert (
        json.loads(outputs["10"].read_text())["features"][0]["properties"]["geo_id"]
        == "10000001"
    )

    with pytest.raises(ValueError, match="at least one partition"):
        partition_boundaries_geojson(source, {}, {})
    with pytest.raises(ValueError, match="unknown partitions"):
        partition_boundaries_geojson(
            source,
            outputs,
            {"10000001": "missing"},
        )


def test_partition_boundaries_streams_pretty_printed_features(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pretty.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"geo_id": identifier},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [0, 0]]],
                        },
                    }
                    for identifier in ("10000001", "35000001")
                ],
            },
            indent=2,
        )
        + "\n"
    )
    outputs = {"10": tmp_path / "nl.geojson", "35": tmp_path / "on.geojson"}

    report = partition_boundaries_geojson(
        source,
        outputs,
        {"10000001": "10", "35000001": "35"},
    )

    assert report["source_features"] == 2
    assert all(
        item["matched_identifiers"] == 1 for item in report["partitions"].values()
    )


def test_partition_boundaries_rejects_incomplete_pretty_geojson(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incomplete.geojson"
    source.write_text(
        '{\n  "type": "FeatureCollection",\n  "features": [\n'
        '    {\n      "type": "Feature",'
    )

    with pytest.raises(ValueError, match="features array is incomplete"):
        partition_boundaries_geojson(
            source,
            {"one": tmp_path / "one.geojson"},
            {"001": "one"},
        )
    assert not (tmp_path / "one.geojson").exists()


def test_partition_boundaries_rejects_non_object_features(tmp_path: Path) -> None:
    source = tmp_path / "invalid.geojson"
    source.write_text('{"type":"FeatureCollection","features":[1]}')

    with pytest.raises(ValueError, match="features must be objects"):
        partition_boundaries_geojson(
            source,
            {"one": tmp_path / "one.geojson"},
            {"001": "one"},
        )
    assert not (tmp_path / "one.geojson").exists()


def test_partition_boundaries_skips_unusable_properties_and_unselected_ids(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mixed.geojson"
    source.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": None, "geometry": None},
                    {
                        "type": "Feature",
                        "properties": {"geo_id": "unselected"},
                        "geometry": None,
                    },
                ],
            },
            indent=2,
        )
    )
    output = tmp_path / "one.geojson"

    report = partition_boundaries_geojson(
        source,
        {"one": output},
        {"001": "one"},
    )

    assert report["source_features"] == 2
    assert report["partitions"]["one"]["missing_identifiers"] == ["001"]
    assert json.loads(output.read_text())["features"] == []


def test_prepare_canada_da_plan_covers_every_jurisdiction(tmp_path: Path) -> None:
    plan_path, manifest = _prepare(tmp_path, compatibility_api=True)

    assert manifest["status"] == "planned"
    assert manifest["coverage"] == {
        "jurisdictions": 13,
        "expected_geographies": 13,
        "usable_geographies": 13,
        "excluded_geographies": 0,
    }
    assert len(manifest["batches"]) == 13
    assert len(manifest["jurisdictions"]) == 13
    assert manifest["boundary_partition"]["source_features"] == 13
    expected_storage = {
        "total_households": 143,
        "largest_batch_households": 11,
        "estimated_persistent_output_bytes": 71_500,
        "estimated_peak_batch_working_bytes": 16_500,
        "recommended_free_space_bytes": 5 * 1024**3 + 88_000,
    }
    assert manifest["storage_estimate"] == expected_storage
    assert (
        national_da_compat.estimate_national_da_storage([{"target_households": 143}])[
            "total_households"
        ]
        == 143
    )
    assert plan_path.is_file()
    for record in manifest["batches"]:
        batch = json.loads((plan_path.parent / record["manifest"]).read_text())
        assert batch["status"] == "planned"
        assert batch["target_households"] == 11
        assert batch["small_areas"] == 1
        assert (plan_path.parent / batch["controls"]["path"]).is_file()
        assert (plan_path.parent / batch["boundaries"]).is_file()


def test_prepare_canada_ada_plan_has_national_da_parity(tmp_path: Path) -> None:
    plan_path, manifest = _prepare(tmp_path, "ada")

    assert required_2021_profile_keys("ada") == ("ada",)
    assert manifest["geography"]["geography_level"] == "ada"
    assert manifest["geography"]["identifier_column"] == "ADAUID"
    assert manifest["coverage"] == {
        "jurisdictions": 13,
        "expected_geographies": 13,
        "usable_geographies": 13,
        "excluded_geographies": 0,
    }
    assert len(manifest["batches"]) == 13
    assert {report["profile_key"] for report in manifest["jurisdictions"]} == {"ada"}
    for record in manifest["batches"]:
        batch = json.loads((plan_path.parent / record["manifest"]).read_text())
        assert batch["geography"]["geography_level"] == "ada"
        assert batch["geography"]["identifier_column"] == "ADAUID"
        assert "boundary-ada-" in batch["boundaries"]
        controls = plan_path.parent / batch["controls"]["path"]
        assert csv.DictReader(controls.open()).fieldnames[2] == "ada"


def test_national_profile_path_adapters_support_flat_and_nested_layouts(
    tmp_path: Path,
) -> None:
    ada_nested = tmp_path / "ada"
    ada_nested.mkdir()
    ada_profile = ada_nested / "2021-census-profile-ada.csv"
    ada_profile.write_text("ada")
    assert national_small_area_module.national_2021_profile_paths(
        tmp_path,
        "ada",
    ) == {"ada": ada_profile}

    flat = tmp_path / "2021-census-profile-da-atlantic.csv"
    flat.write_text("da")
    assert (
        national_small_area_module.national_2021_profile_paths(
            tmp_path,
            "da",
        )["da-atlantic"]
        == flat
    )


def test_candidate_pools_are_generated_once_and_reused(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_path = tmp_path / "plan.json"
    manifests = []
    for index, target in enumerate((7, 9), start=1):
        batch_path = tmp_path / "batches" / str(index) / "batch.json"
        batch_path.parent.mkdir(parents=True)
        batch_path.write_text(
            json.dumps(
                {
                    "schema_version": "synthpopcan-canada-small-area-batch-v1",
                    "batch_id": f"10-{index:04d}",
                    "jurisdiction": {"pruid": "10", "pumf_pr": "10"},
                    "target_households": target,
                }
            )
        )
        manifests.append(
            {
                "manifest": str(batch_path.relative_to(tmp_path)),
                "jurisdiction_pruid": "10",
            }
        )
    plan_path.write_text(json.dumps({"batches": manifests}))
    calls = 0

    def fake_generate(
        _household_model,
        _person_model,
        *,
        households,
        households_path,
        persons_path,
        household_conditions,
        **_options,
    ):
        nonlocal calls
        calls += 1
        assert household_conditions == {"PR": "10"}
        household_rows = []
        person_rows = []
        for index in range(1, households + 1):
            size = index % 3 + 1
            household_rows.append(
                {
                    "synthetic_household_id": str(index),
                    "PR": "10",
                    "household_size": str(size),
                    "TENUR": str(index % 2 + 1),
                }
            )
            for person in range(1, size + 1):
                person_rows.append(
                    {
                        "synthetic_person_id": f"{index}-{person}",
                        "synthetic_household_id": str(index),
                    }
                )
        with households_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=household_rows[0])
            writer.writeheader()
            writer.writerows(household_rows)
        with persons_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=person_rows[0])
            writer.writeheader()
            writer.writerows(person_rows)
        return len(household_rows), len(person_rows)

    monkeypatch.setattr(
        "synthpopcan.national_execution.generate_linked_population_to_csv",
        fake_generate,
    )
    monkeypatch.setattr(
        "synthpopcan.national_execution.validate_linked_population_files",
        lambda *_args: {"passed": True, "issues": []},
    )

    first = prepare_national_candidate_pools(
        plan_path,
        household_model=object(),
        person_model=object(),
        household_size_column="household_size",
        model_evidence={"sha256": "model"},
        requested_pool_size=5,
        base_seed=40,
    )
    second = prepare_national_candidate_pools(
        plan_path,
        household_model=object(),
        person_model=object(),
        household_size_column="household_size",
        model_evidence={"sha256": "model"},
        requested_pool_size=5,
        base_seed=40,
    )

    assert calls == 1
    assert first["10"]["rows"]["households"] == 5
    assert second["10"]["artifacts"] == first["10"]["artifacts"]
    assert first["10"]["support"]["categories"]["PR"] == {"10": 5}
    assert (
        find_cached_national_candidate_pools(
            plan_path,
            model_evidence={"sha256": "model"},
            requested_pool_size=5,
            base_seed=40,
        )
        is not None
    )
    assert (
        find_cached_national_candidate_pools(
            plan_path,
            model_evidence={"sha256": "different"},
            requested_pool_size=5,
            base_seed=40,
        )
        is None
    )
    monkeypatch.setattr(
        "synthpopcan.national_execution.validate_linked_population_files",
        lambda *_args: {"passed": False},
    )
    with pytest.raises(ValueError, match="linked validation failed"):
        prepare_national_candidate_pools(
            plan_path,
            household_model=object(),
            person_model=object(),
            household_size_column="household_size",
            model_evidence={"sha256": "model"},
            requested_pool_size=5,
            base_seed=40,
            force=True,
        )
    monkeypatch.setattr(
        "synthpopcan.national_execution.validate_linked_population_files",
        lambda *_args: {"passed": True, "issues": []},
    )
    assert (
        find_cached_national_candidate_pools(
            plan_path,
            model_evidence={"sha256": "model"},
            requested_pool_size=4,
            base_seed=40,
        )
        is None
    )
    updated_plan = json.loads(plan_path.read_text())
    assert (
        updated_plan["candidate_pools"]["conditions"]["10"]["target_households"] == 16
    )
    messages: list[str] = []
    prepare_national_candidate_pools(
        plan_path,
        household_model=object(),
        person_model=object(),
        household_size_column="household_size",
        model_evidence={"sha256": "model"},
        requested_pool_size=5,
        base_seed=40,
        progress=messages.append,
    )
    prepare_national_candidate_pools(
        plan_path,
        household_model=object(),
        person_model=object(),
        household_size_column="household_size",
        model_evidence={"sha256": "model"},
        requested_pool_size=5,
        base_seed=40,
        force=True,
        progress=messages.append,
    )
    assert calls == 3
    assert any(message.startswith("Using cached") for message in messages)
    assert any(message.startswith("Generating") for message in messages)
    manifest_path = plan_path.parent / "candidate-pools/pr-10/manifest.json"
    original_manifest = json.loads(manifest_path.read_text())
    for mutate in (
        lambda payload: payload.update(configuration=[]),
        lambda payload: payload["configuration"].update(condition={"PR": "35"}),
        lambda payload: payload["configuration"].update(random_seed=999),
        lambda payload: payload["artifacts"]["households"].update(sha256="bad"),
    ):
        payload = json.loads(json.dumps(original_manifest))
        mutate(payload)
        manifest_path.write_text(json.dumps(payload))
        assert (
            find_cached_national_candidate_pools(
                plan_path,
                model_evidence={"sha256": "model"},
                requested_pool_size=5,
                base_seed=40,
            )
            is None
        )
    manifest_path.unlink()
    assert (
        find_cached_national_candidate_pools(
            plan_path,
            model_evidence={"sha256": "model"},
            requested_pool_size=5,
            base_seed=40,
        )
        is None
    )


def test_cached_pool_batch_writes_timing_integrity_and_national_summary(
    tmp_path: Path,
) -> None:
    plan_path, _ = _prepare(tmp_path, "ada")
    plan = json.loads(plan_path.read_text())
    record = plan["batches"][0]
    batch_path = plan_path.parent / record["manifest"]
    batch = json.loads(batch_path.read_text())
    pumf_pr = batch["jurisdiction"]["pumf_pr"]

    pool_root = plan_path.parent / "candidate-pools" / f"pr-{pumf_pr}"
    pool_root.mkdir(parents=True)
    households_path = pool_root / "households.csv"
    persons_path = pool_root / "persons.csv"
    household_rows = []
    person_rows = []
    for index in range(1, 11):
        size = (index - 1) % 5 + 1
        household_rows.append(
            {
                "synthetic_household_id": str(index),
                "PR": pumf_pr,
                "household_size": str(size),
                "TENUR": str((index - 1) % 2 + 1),
                "household_size_group": str(size),
            }
        )
        for person in range(1, size + 1):
            person_rows.append(
                {
                    "synthetic_person_id": f"{index}-{person}",
                    "synthetic_household_id": str(index),
                }
            )
    with households_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=household_rows[0])
        writer.writeheader()
        writer.writerows(household_rows)
    with persons_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=person_rows[0])
        writer.writeheader()
        writer.writerows(person_rows)
    pool_manifest = {
        "rows": {"households": 10, "persons": len(person_rows)},
        "artifacts": {
            "households": {"path": "households.csv"},
            "persons": {"path": "persons.csv"},
        },
    }
    pool_manifest_path = pool_root / "manifest.json"
    pool_manifest_path.write_text(json.dumps(pool_manifest))
    configuration = NationalBatchRunConfiguration(
        pool_manifests={pumf_pr: str(pool_manifest_path.relative_to(plan_path.parent))},
        geography_level="ada",
        identifier_column="ADAUID",
        identifier_namespace="statcan:census:2021:ada",
        fit_workers=1,
    )
    stale_output = plan_path.parent / batch["output_directory"]
    stale_output.mkdir(parents=True)
    (stale_output / "stale.txt").write_text("stale")

    result = run_national_cached_batch(
        batch,
        plan_path.parent,
        configuration=configuration,
    )

    output = plan_path.parent / batch["output_directory"]
    assert not (output / "stale.txt").exists()
    report = json.loads((output / "report.json").read_text())
    assert result["linked_validation"]["passed"] is True
    assert result["candidate_pool"]["households"] == 10
    assert result["timing_seconds"]["calibration_and_realization"] >= 0
    assert report["timing_seconds"]["calibration"] >= 0
    assert (
        sum(
            geography["assigned_persons"]
            for geography in report["geographies"].values()
        )
        == report["assigned_persons"]
    )
    assert (
        result["artifacts"]["households"]["sha256"]
        == file_integrity(output / "households.csv")["sha256"]
    )

    batch["status"] = "completed"
    batch["result"] = result
    batch_path.write_text(json.dumps(batch))
    summary = build_national_geography_summary(plan_path)
    assert summary["batches"]["completed"] == 1
    assert summary["assigned_households"] == 11
    geography_rows = list(
        csv.DictReader((plan_path.parent / "national-geography-summary.csv").open())
    )
    assert geography_rows[0]["ADAUID"].startswith("10")
    assert (
        sum(int(row["persons"]) for row in geography_rows)
        == summary["assigned_persons"]
    )


def test_parallel_plan_execution_completes_bounded_batches(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)

    result = execute_canada_small_area_plan(
        plan_path,
        _parallel_test_batch,
        limit=2,
        workers=2,
    )

    assert result["last_execution"]["attempted_batches"] == 2
    assert result["last_execution"]["workers"] == 2
    assert result["last_execution"]["status_counts"]["completed"] == 2


def test_parallel_plan_execution_records_worker_failure(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)

    with pytest.raises(RuntimeError, match=r"failed \d{2}-0001"):
        execute_canada_small_area_plan(
            plan_path,
            _parallel_fail_batch,
            limit=2,
            workers=2,
        )

    persisted = json.loads(plan_path.read_text())
    assert persisted["last_execution"]["failed_batches"]
    failed_path = plan_path.parent / persisted["batches"][0]["manifest"]
    failed = json.loads(failed_path.read_text())
    assert failed["status"] == "failed"
    assert "RuntimeError" in failed["worker_traceback"]


def test_sequential_plan_interrupt_is_restartable(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)

    with pytest.raises(KeyboardInterrupt):
        execute_canada_small_area_plan(
            plan_path,
            lambda _batch, _root: (_ for _ in ()).throw(KeyboardInterrupt()),
            limit=1,
        )

    persisted = json.loads(plan_path.read_text())
    batch_path = plan_path.parent / persisted["batches"][0]["manifest"]
    batch = json.loads(batch_path.read_text())
    assert batch["status"] == "planned"
    assert batch["interrupted_attempt"] == 1
    with pytest.raises(ValueError, match="workers"):
        execute_canada_small_area_plan(plan_path, _parallel_test_batch, workers=0)


def test_parallel_worker_entry_serializes_success_and_failure(tmp_path: Path) -> None:
    messages: list[object] = []

    class Queue:
        def put(self, value) -> None:
            messages.append(value)

    national_small_area_module._parallel_batch_entry(
        _parallel_test_batch,
        {"batch_id": "ok"},
        tmp_path,
        "ok",
        Queue(),
    )
    national_small_area_module._parallel_batch_entry(
        _parallel_fail_batch,
        {"batch_id": "bad"},
        tmp_path,
        "bad",
        Queue(),
    )

    assert messages[0] == ("ok", "ok", {"batch_id": "ok"})
    assert messages[1][0:4] == (
        "error",
        "bad",
        "RuntimeError",
        "failed bad",
    )
    assert "RuntimeError" in messages[1][4]


def test_parallel_executor_validates_candidates_and_filters(
    tmp_path: Path,
) -> None:
    plan_path, _ = _prepare(tmp_path)
    plan = json.loads(plan_path.read_text())
    original_records = plan["batches"]

    plan["batches"] = ["invalid"]
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="record is invalid"):
        execute_canada_small_area_plan(plan_path, _parallel_test_batch, workers=2)

    plan["batches"] = original_records
    plan_path.write_text(json.dumps(plan))
    filtered = execute_canada_small_area_plan(
        plan_path,
        _parallel_test_batch,
        workers=2,
        jurisdiction_pruids={"99"},
    )
    assert filtered["last_execution"]["attempted_batches"] == 0

    first_path = plan_path.parent / original_records[0]["manifest"]
    first = json.loads(first_path.read_text())
    original_schema = first["schema_version"]
    first["schema_version"] = "old"
    first_path.write_text(json.dumps(first))
    with pytest.raises(ValueError, match="unsupported batch schema"):
        execute_canada_small_area_plan(plan_path, _parallel_test_batch, workers=2)

    first["schema_version"] = original_schema
    first["attempts"] = "once"
    first_path.write_text(json.dumps(first))
    with pytest.raises(ValueError, match="attempts"):
        execute_canada_small_area_plan(
            plan_path,
            _parallel_test_batch,
            workers=2,
            limit=1,
        )


def test_parallel_executor_can_continue_after_worker_failures(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)

    result = execute_canada_small_area_plan(
        plan_path,
        _parallel_fail_batch,
        workers=2,
        limit=2,
        continue_on_error=True,
    )

    assert len(result["last_execution"]["failed_batches"]) == 2
    assert result["last_execution"]["status_counts"]["failed"] == 2


def test_parallel_executor_skips_completed_batches(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)
    plan = json.loads(plan_path.read_text())
    for record in plan["batches"]:
        batch_path = plan_path.parent / record["manifest"]
        batch = json.loads(batch_path.read_text())
        batch["status"] = "completed"
        batch_path.write_text(json.dumps(batch))

    result = execute_canada_small_area_plan(
        plan_path,
        _parallel_test_batch,
        workers=2,
    )

    assert result["last_execution"]["attempted_batches"] == 0
    assert result["last_execution"]["status_counts"] == {"completed": 13}


def test_completed_national_plan_renders_polygon_and_point_summary_maps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_path = tmp_path / "plan.json"
    boundary_path = tmp_path / "boundaries.geojson"
    boundary_path.write_text(
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
                    }
                ],
            }
        )
    )
    (tmp_path / "national-geography-summary.csv").write_text(
        "DAUID,jurisdiction,households,persons\n1001,NL,2,5\n"
    )
    population = tmp_path / "population"
    population.mkdir()
    (population / "households.csv").write_text(
        "synthetic_household_id,DAUID,household_size,TENUR\nh1,1001,2,1\nh2,1001,3,2\n"
    )
    (population / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id,DAUID\n"
        "p1,h1,1001\n"
        "p2,h1,1001\n"
        "p3,h2,1001\n"
        "p4,h2,1001\n"
        "p5,h2,1001\n"
    )
    (tmp_path / "batch.json").write_text(
        json.dumps(
            {
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
        )
    )
    plan = {
        "status": "completed",
        "inputs": {"boundaries": {"path": "boundaries.geojson"}},
        "batches": [{"manifest": "batch.json"}],
    }
    plan_path.write_text(json.dumps(plan))
    summary: dict[str, object] = {
        "artifacts": {},
        "geographies": 1,
        "assigned_households": 2,
        "assigned_persons": 5,
    }

    monkeypatch.chdir(tmp_path)
    assert _national_plan_is_complete(plan)
    rendered = _render_national_summary_map(
        plan_path,
        plan,
        summary,
        geography_level="da",
        identifier_column="DAUID",
    )

    assert (tmp_path / "national-map.html").is_file()
    assert (tmp_path / "national-map.geojson").is_file()
    assert (tmp_path / "national-points-map.html").is_file()
    assert (tmp_path / "national-points.geojson").is_file()
    assert rendered["map"]["matched_geographies"] == 1
    assert rendered["map"]["point_overview"]["matched_geographies"] == 1
    assert rendered["artifacts"]["map"]["sha256"]
    assert rendered["artifacts"]["map_boundaries"]["sha256"]
    assert rendered["artifacts"]["map_statistics"]["sha256"]
    assert rendered["artifacts"]["point_map"]["sha256"]
    assert json.loads((tmp_path / "national-summary.json").read_text()) == rendered
    assert not _national_plan_is_complete({"status": "partial"})


def test_geo_map_cli_accepts_completed_national_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "geography": {
                    "geography_level": "ada",
                    "identifier_column": "ADAUID",
                }
            }
        )
    )
    calls: list[dict[str, object]] = []

    def fake_render(**options):
        calls.append(options)
        return tmp_path / "map.html"

    monkeypatch.setattr(
        "synthpopcan.api.render_small_area_map",
        fake_render,
    )

    assert (
        main(
            [
                "geo",
                "map",
                str(plan_path),
                "--coord-precision",
                "4",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "households": plan_path,
            "out": None,
            "title": None,
            "coord_precision": 4,
        }
    ]
    assert str(tmp_path / "map.html") in capsys.readouterr().out
    assert (
        main(
            [
                "geo",
                "map",
                str(plan_path),
                "--jurisdiction",
                "qc",
            ]
        )
        == 0
    )
    assert calls[-1]["jurisdiction_pruids"] == ("24",)
    with pytest.raises(UsageError, match="--persons must be omitted"):
        main(
            [
                "geo",
                "map",
                str(plan_path),
                "--persons",
                str(tmp_path / "persons.csv"),
            ]
        )


def test_deferred_batch_maps_are_recorded_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    batch_path = tmp_path / "batches" / "10" / "0001" / "batch.json"
    batch_path.parent.mkdir(parents=True)
    output = tmp_path / "population"
    output.mkdir()
    (output / "households.csv").write_text("synthetic_household_id,DAUID\n1,1001\n")
    (output / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id,DAUID\n1,1,1001\n"
    )
    (tmp_path / "boundaries.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}'
    )
    batch_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "batch_id": "10-0001",
                "output_directory": "population",
                "boundaries": "boundaries.geojson",
                "result": {"artifacts": {}, "timing_seconds": {}},
            }
        )
    )
    calls: list[Path] = []

    def fake_render(**options) -> None:
        map_path = options["out_path"]
        calls.append(map_path)
        map_path.write_text("map")

    monkeypatch.setattr("synthpopcan.map_render.render_synthesis_map", fake_render)
    plan = {
        "batches": [
            {
                "jurisdiction_pruid": "10",
                "manifest": str(batch_path.relative_to(tmp_path)),
            },
            {"jurisdiction_pruid": "35", "manifest": "missing.json"},
            {},
            "invalid",
        ]
    }

    _render_deferred_national_maps(
        tmp_path / "plan.json",
        plan,
        jurisdiction_pruids={"10"},
        geography_level="da",
        identifier_column="DAUID",
    )
    _render_deferred_national_maps(
        tmp_path / "plan.json",
        plan,
        jurisdiction_pruids={"10"},
        geography_level="da",
        identifier_column="DAUID",
    )

    assert calls == [output / "map.html"]
    persisted = json.loads(batch_path.read_text())
    assert persisted["result"]["artifacts"]["map"]["sha256"]
    assert persisted["result"]["timing_seconds"]["deferred_map"] >= 0


def test_deferred_batch_maps_skip_inapplicable_records(tmp_path: Path) -> None:
    records: list[object] = [{}, "invalid"]
    for name, payload in (
        ("planned", {"status": "planned"}),
        ("result", {"status": "completed", "result": None}),
        ("artifacts", {"status": "completed", "result": {"artifacts": []}}),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload))
        records.append({"jurisdiction_pruid": "10", "manifest": path.name})

    _render_deferred_national_maps(
        tmp_path / "plan.json",
        {"batches": records},
        jurisdiction_pruids={"10"},
        geography_level="da",
        identifier_column="DAUID",
    )
    with pytest.raises(ValueError, match="batches must be a list"):
        _render_deferred_national_maps(
            tmp_path / "plan.json",
            {"batches": "bad"},
            jurisdiction_pruids=None,
            geography_level="da",
            identifier_column="DAUID",
        )


def test_national_summary_map_rejects_missing_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with pytest.raises(ValueError, match="boundary input"):
        _render_national_summary_map(
            tmp_path / "plan.json",
            {},
            {},
            geography_level="da",
            identifier_column="DAUID",
        )
    monkeypatch.setattr(
        "synthpopcan.map_render.render_geography_summary_point_map",
        lambda **_options: {},
    )
    monkeypatch.setattr(
        "synthpopcan.map_render.render_national_plan_map",
        lambda **_options: {},
    )
    with pytest.raises(ValueError, match="artifacts must be"):
        _render_national_summary_map(
            tmp_path / "plan.json",
            {"inputs": {"boundaries": {"path": "missing.geojson"}}},
            {"artifacts": []},
            geography_level="da",
            identifier_column="DAUID",
        )


def test_candidate_pool_cache_rejects_corrupt_evidence(tmp_path: Path) -> None:
    directory = tmp_path / "pool"
    directory.mkdir()
    configuration = {"pool_size": 2}
    households = directory / "households.csv"
    persons = directory / "persons.csv"
    households.write_text("id\n1\n")
    persons.write_text("id\n1\n")
    artifacts = {
        name: {"path": path.name, **file_integrity(path)}
        for name, path in (("households", households), ("persons", persons))
    }
    manifest = {
        "schema_version": "synthpopcan-national-candidate-pool-v1",
        "configuration": configuration,
        "artifacts": artifacts,
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    assert (
        national_execution_module._validated_cached_pool(directory, configuration)
        == manifest
    )

    for mutate in (
        lambda payload: payload.update(schema_version="old"),
        lambda payload: payload.update(artifacts=[]),
        lambda payload: payload["artifacts"].update(households=[]),
        lambda payload: payload["artifacts"]["persons"].update(path="missing.csv"),
        lambda payload: payload["artifacts"]["persons"].update(byte_size=999),
        lambda payload: payload["artifacts"]["persons"].update(sha256="bad"),
        lambda payload: payload["artifacts"]["persons"].update(path=3),
    ):
        payload = json.loads(json.dumps(manifest))
        mutate(payload)
        manifest_path.write_text(json.dumps(payload))
        assert (
            national_execution_module._validated_cached_pool(
                directory,
                configuration,
            )
            is None
        )
    manifest_path.write_text("[]")
    assert (
        national_execution_module._validated_cached_pool(directory, configuration)
        is None
    )
    manifest_path.unlink()
    assert (
        national_execution_module._validated_cached_pool(directory, configuration)
        is None
    )


def test_candidate_pool_excludes_unknown_tenure_and_linked_persons(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("synthetic_household_id,TENUR\nh1,1\nh2,8\nh3,2\n")
    persons.write_text(
        "synthetic_person_id,synthetic_household_id\np1,h1\np2,h2\np3,h2\np4,h3\n"
    )

    report = national_execution_module._exclude_unusable_linked_candidates(
        households,
        persons,
        tmp_path / "households-filtered.csv",
        tmp_path / "persons-filtered.csv",
    )

    assert report["households"] == 2
    assert report["persons"] == 2
    assert report["excluded"]["household_values"]["TENUR"] == {"8": 1}
    assert "h2" not in (tmp_path / "households-filtered.csv").read_text()
    assert "p2" not in (tmp_path / "persons-filtered.csv").read_text()


def test_candidate_pool_filter_rejects_malformed_linked_csvs(tmp_path: Path) -> None:
    empty_households = tmp_path / "empty-households.csv"
    empty_households.write_text("")
    persons = tmp_path / "persons.csv"
    persons.write_text("synthetic_person_id,synthetic_household_id\n")
    with pytest.raises(ValueError, match="household CSV has no header"):
        national_execution_module._exclude_unusable_linked_candidates(
            empty_households,
            persons,
            tmp_path / "households-out.csv",
            tmp_path / "persons-out.csv",
        )

    households_without_id = tmp_path / "households-without-id.csv"
    households_without_id.write_text("synthetic_household_id,TENUR\n,1\n")
    with pytest.raises(ValueError, match="household has no identifier"):
        national_execution_module._exclude_unusable_linked_candidates(
            households_without_id,
            persons,
            tmp_path / "households-out.csv",
            tmp_path / "persons-out.csv",
        )

    households = tmp_path / "households.csv"
    households.write_text("synthetic_household_id,TENUR\nh1,1\n")
    empty_persons = tmp_path / "empty-persons.csv"
    empty_persons.write_text("")
    with pytest.raises(ValueError, match="person CSV has no header"):
        national_execution_module._exclude_unusable_linked_candidates(
            households,
            empty_persons,
            tmp_path / "households-out.csv",
            tmp_path / "persons-out.csv",
        )


def test_reset_nonconverged_batches_preserves_prior_result(tmp_path: Path) -> None:
    plan_path, plan = _prepare(tmp_path)
    record = plan["batches"][0]
    batch_path = plan_path.parent / record["manifest"]
    batch = json.loads(batch_path.read_text())
    report_path = batch_path.parent / "report.json"
    report_path.write_text(
        json.dumps(
            {"geographies": {"10010001": {"converged": False, "max_abs_error": 2.0}}}
        )
    )
    batch["status"] = "completed"
    batch["result"] = {
        "artifacts": {
            "report": {
                "path": str(report_path.relative_to(plan_path.parent)),
            }
        }
    }
    batch_path.write_text(json.dumps(batch))

    reset = reset_nonconverged_national_batches(
        plan_path,
        jurisdiction_pruids={"10"},
    )

    assert reset == [batch["batch_id"]]
    persisted = json.loads(batch_path.read_text())
    assert persisted["status"] == "planned"
    assert "result" not in persisted
    assert persisted["superseded_results"][0]["result"] == batch["result"]
    updated_plan = json.loads(plan_path.read_text())
    assert updated_plan["status"] == "partial"


def test_reset_nonconverged_batches_handles_ineligible_records(
    tmp_path: Path,
) -> None:
    invalid_plan = tmp_path / "invalid-plan.json"
    invalid_plan.write_text(json.dumps({"batches": {}}))
    with pytest.raises(ValueError, match="batches must be a list"):
        reset_nonconverged_national_batches(invalid_plan)

    batch_path = tmp_path / "batch.json"
    report_path = tmp_path / "report.json"

    def run(record: object, batch: object | None = None) -> list[str]:
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps({"batches": [record]}))
        if batch is not None:
            batch_path.write_text(json.dumps(batch))
        return reset_nonconverged_national_batches(plan_path)

    assert run(3) == []
    assert run({}) == []
    assert run({"manifest": "batch.json"}, {"status": "planned"}) == []
    assert run({"manifest": "batch.json"}, {"status": "completed"}) == []
    assert (
        run(
            {"manifest": "batch.json"},
            {"status": "completed", "result": {"artifacts": {}}},
        )
        == []
    )

    report_path.write_text(
        json.dumps({"geographies": {"10010001": {"converged": True}}})
    )
    completed = {
        "batch_id": "10-0001",
        "status": "completed",
        "result": {
            "artifacts": {"report": {"path": report_path.name}},
        },
    }
    assert run({"manifest": batch_path.name}, completed) == []

    report_path.write_text(
        json.dumps({"geographies": {"10010001": {"converged": False}}})
    )
    completed["superseded_results"] = {}
    with pytest.raises(ValueError, match="superseded_results must be a list"):
        run({"manifest": batch_path.name}, completed)


def test_national_execution_helpers_reject_malformed_payloads(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    with pytest.raises(ValueError, match="at least 1"):
        prepare_national_candidate_pools(
            plan,
            household_model=object(),
            person_model=object(),
            household_size_column="household_size",
            model_evidence={},
            requested_pool_size=0,
            base_seed=1,
        )
    with pytest.raises(ValueError, match="batches must be a list"):
        national_execution_module._targets_by_condition(
            plan,
            {},
            condition_by_jurisdiction=True,
            pumf_pr_values=None,
        )
    for records, message in (
        ([3], "record is invalid"),
        ([{}], "manifest is invalid"),
    ):
        with pytest.raises(ValueError, match=message):
            national_execution_module._targets_by_condition(
                plan,
                {"batches": records},
                condition_by_jurisdiction=True,
                pumf_pr_values=None,
            )
    assert national_execution_module._candidate_support(
        _write_candidate_support_fixture(tmp_path / "support.csv")
    )["categories"]["TENUR"] == {"": 1}
    with pytest.raises(ValueError, match="rows are invalid"):
        national_execution_module._pool_row_count({}, "households")
    with pytest.raises(ValueError, match="households count"):
        national_execution_module._pool_row_count({"rows": {}}, "households")
    with pytest.raises(ValueError, match="JSON object"):
        national_execution_module._read_json(_write_text(tmp_path / "array.json", "[]"))

    batch_path = tmp_path / "batch.json"
    for batch, message in (
        ({"jurisdiction": "bad", "target_households": 1}, "jurisdiction or target"),
        (
            {"jurisdiction": {"pumf_pr": 10}, "target_households": 1},
            "PUMF condition",
        ),
    ):
        batch_path.write_text(json.dumps(batch))
        with pytest.raises(ValueError, match=message):
            national_execution_module._targets_by_condition(
                plan,
                {"batches": [{"manifest": batch_path.name}]},
                condition_by_jurisdiction=True,
                pumf_pr_values=None,
            )
    batch_path.write_text(
        json.dumps({"jurisdiction": {"pumf_pr": "10"}, "target_households": 3})
    )
    assert not national_execution_module._targets_by_condition(
        plan,
        {"batches": [{"manifest": batch_path.name}]},
        condition_by_jurisdiction=True,
        pumf_pr_values={"35"},
    )


def test_national_summary_skips_incomplete_batch_evidence(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    with pytest.raises(ValueError, match="plan is incomplete"):
        build_national_geography_summary(
            _write_text(plan_path, json.dumps({"batches": []}))
        )
    with pytest.raises(ValueError, match="identifier column"):
        build_national_geography_summary(
            _write_text(
                plan_path,
                json.dumps({"geography": {}, "batches": []}),
            )
        )

    records: list[object] = ["invalid", {}]
    payloads = [
        {"status": "planned"},
        {"status": "completed", "result": None, "jurisdiction": {}},
        {"status": "completed", "result": {}, "jurisdiction": {}},
        {
            "status": "completed",
            "result": {"artifacts": {}},
            "jurisdiction": {},
        },
        {
            "status": "completed",
            "result": {"artifacts": {"report": {}}},
            "jurisdiction": {},
        },
    ]
    for index, payload in enumerate(payloads):
        path = tmp_path / f"batch-{index}.json"
        path.write_text(json.dumps(payload))
        records.append({"manifest": path.name})
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "assigned_households": 1,
                "assigned_persons": 2,
                "geographies": {"1001": "invalid"},
            }
        )
    )
    complete = tmp_path / "complete.json"
    complete.write_text(
        json.dumps(
            {
                "status": "completed",
                "result": {"artifacts": {"report": {"path": report.name}}},
                "jurisdiction": {},
            }
        )
    )
    records.append({"manifest": complete.name})
    no_geographies_report = tmp_path / "no-geographies-report.json"
    no_geographies_report.write_text(
        json.dumps(
            {
                "assigned_households": 0,
                "assigned_persons": 0,
                "geographies": [],
            }
        )
    )
    no_geographies = tmp_path / "no-geographies.json"
    no_geographies.write_text(
        json.dumps(
            {
                "status": "completed",
                "result": {
                    "artifacts": {
                        "report": {"path": no_geographies_report.name},
                    }
                },
                "jurisdiction": {},
            }
        )
    )
    records.append({"manifest": no_geographies.name})
    plan_path.write_text(
        json.dumps(
            {
                "geography": {"identifier_column": "DAUID"},
                "batches": records,
            }
        )
    )

    summary = build_national_geography_summary(plan_path)

    assert summary["batches"]["completed"] == 2
    assert summary["geographies"] == 0


def _write_text(path: Path, value: str) -> Path:
    path.write_text(value)
    return path


def _write_candidate_support_fixture(path: Path) -> Path:
    path.write_text("PR,TENUR,household_size_group\n10,,1\n")
    return path


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"output_directory": 2}, "output directory is invalid"),
        ({"jurisdiction": {"pumf_pr": ""}}, "pumf_pr must be"),
        ({"jurisdiction": {"pumf_pr": "10"}}, "has no PR=10"),
    ],
)
def test_cached_batch_rejects_missing_pool_configuration(
    tmp_path: Path,
    change: dict[str, object],
    message: str,
) -> None:
    batch: dict[str, object] = {
        "batch_id": "10-0001",
        "controls": {"path": "controls.csv"},
        "jurisdiction": {"pumf_pr": "10"},
        "target_households": 2,
        "output_directory": "population",
        **change,
    }
    configuration = NationalBatchRunConfiguration(
        pool_manifests={},
        geography_level="da",
        identifier_column="DAUID",
        identifier_namespace="statcan:census:2021:da",
        fit_workers=1,
    )
    with pytest.raises(ValueError, match=message):
        run_national_cached_batch(batch, tmp_path, configuration=configuration)


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ({}, "artifacts are invalid"),
        ({"artifacts": {}}, "files are invalid"),
    ],
)
def test_cached_batch_rejects_malformed_pool_manifest(
    tmp_path: Path,
    manifest: dict[str, object],
    message: str,
) -> None:
    pool = tmp_path / "pool"
    pool.mkdir()
    (pool / "manifest.json").write_text(json.dumps(manifest))
    configuration = NationalBatchRunConfiguration(
        pool_manifests={"10": "pool/manifest.json"},
        geography_level="da",
        identifier_column="DAUID",
        identifier_namespace="statcan:census:2021:da",
        fit_workers=1,
    )
    batch = {
        "batch_id": "10-0001",
        "controls": {"path": "controls.csv"},
        "jurisdiction": {"pumf_pr": "10"},
        "target_households": 2,
        "output_directory": "population",
    }
    with pytest.raises(ValueError, match=message):
        run_national_cached_batch(batch, tmp_path, configuration=configuration)


def test_cached_batch_cleans_staging_after_link_validation_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pool = tmp_path / "pool"
    pool.mkdir()
    for name in ("households.csv", "persons.csv"):
        (pool / name).write_text("id\n1\n")
    (pool / "manifest.json").write_text(
        json.dumps(
            {
                "rows": {"households": 1, "persons": 1},
                "artifacts": {
                    "households": {"path": "households.csv"},
                    "persons": {"path": "persons.csv"},
                },
            }
        )
    )

    def fake_calibrate(**options):
        options["households_out"].write_text("id\n1\n")
        options["persons_out"].write_text("id\n1\n")
        options["report_out"].write_text("{}")
        return {}

    monkeypatch.setattr(
        "synthpopcan.national_execution.calibrate_linked_household_csvs",
        fake_calibrate,
    )
    monkeypatch.setattr(
        "synthpopcan.national_execution.validate_linked_population_files",
        lambda *_args: {"passed": False},
    )
    configuration = NationalBatchRunConfiguration(
        pool_manifests={"10": "pool/manifest.json"},
        geography_level="da",
        identifier_column="DAUID",
        identifier_namespace="statcan:census:2021:da",
        fit_workers=1,
    )
    batch = {
        "batch_id": "10-0001",
        "controls": {"path": "controls.csv"},
        "jurisdiction": {"pumf_pr": "10"},
        "target_households": 1,
        "output_directory": "population",
    }

    with pytest.raises(ValueError, match="linked-population validation failed"):
        run_national_cached_batch(batch, tmp_path, configuration=configuration)

    assert not list(tmp_path.glob(".population-*"))


def test_prepare_canada_da_plan_reports_missing_controls(tmp_path: Path) -> None:
    identifiers = _identifiers()
    dgrf = tmp_path / "dgrf.csv"
    _write_dgrf(dgrf, identifiers)
    profiles = _write_profiles(tmp_path, identifiers)
    _write_profile(profiles["da-territories"], [])
    boundaries = tmp_path / "boundaries.geojson"
    _write_boundaries(boundaries, identifiers)

    manifest = prepare_canada_small_area_plan(
        profiles,
        boundaries,
        dgrf,
        tmp_path / "out",
        geography_level="da",
    )

    assert manifest["coverage"]["excluded_geographies"] == 3
    territory_reports = [
        report
        for report in manifest["jurisdictions"]
        if report["pruid"] in {"60", "61", "62"}
    ]
    assert all(report["usable_geographies"] == 0 for report in territory_reports)
    assert all(
        len(report["missing_profile_controls"]) == 1 for report in territory_reports
    )


def test_prepare_rejects_usable_controls_without_a_boundary(tmp_path: Path) -> None:
    identifiers = _identifiers()
    dgrf = tmp_path / "dgrf.csv"
    _write_dgrf(dgrf, identifiers)
    profiles = _write_profiles(tmp_path, identifiers)
    boundaries = tmp_path / "boundaries.geojson"
    _write_boundaries(boundaries, identifiers)
    payload = json.loads(boundaries.read_text())
    missing_id = identifiers["35"]
    payload["features"] = [
        feature
        for feature in payload["features"]
        if feature["properties"]["geo_id"] != missing_id
    ]
    boundaries.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="usable DA controls without matching"):
        prepare_canada_small_area_plan(
            profiles,
            boundaries,
            dgrf,
            tmp_path / "out",
            geography_level="da",
        )


def test_execute_canada_da_plan_resumes_completed_batches(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)
    calls: list[str] = []

    def run_batch(batch, _root):
        calls.append(batch["batch_id"])
        return {"passed": True}

    partial = national_da_compat.execute_canada_da_plan(
        plan_path,
        run_batch,
        limit=2,
    )
    assert partial["status"] == "partial"
    assert partial["last_execution"]["status_counts"] == {
        "completed": 2,
        "planned": 11,
    }

    completed = execute_canada_small_area_plan(plan_path, run_batch)
    assert completed["status"] == "completed"
    assert len(calls) == 13
    assert completed["last_execution"]["status_counts"] == {"completed": 13}


def test_execute_canada_da_plan_can_select_one_jurisdiction(tmp_path: Path) -> None:
    plan_path, _ = _prepare(tmp_path)
    calls = []

    result = execute_canada_small_area_plan(
        plan_path,
        lambda batch, _root: calls.append(batch["batch_id"]) or {},
        jurisdiction_pruids={"35"},
    )

    assert calls == ["35-0001"]
    assert result["status"] == "partial"
    assert result["last_execution"]["attempted_batches"] == 1

    untouched_path, _ = _prepare(tmp_path / "untouched")
    untouched = execute_canada_small_area_plan(
        untouched_path,
        lambda _batch, _root: {},
        jurisdiction_pruids={"99"},
    )
    assert untouched["status"] == "planned"


def test_execute_canada_da_plan_records_and_can_continue_after_failure(
    tmp_path: Path,
) -> None:
    plan_path, _ = _prepare(tmp_path)

    def fail_first(batch, _root):
        if batch["batch_id"] == "10-0001":
            raise RuntimeError("synthetic failure")
        return {}

    result = execute_canada_small_area_plan(
        plan_path,
        fail_first,
        limit=2,
        continue_on_error=True,
    )
    assert result["status"] == "failed"
    assert result["last_execution"]["failed_batches"] == ["10-0001"]
    failed = json.loads((plan_path.parent / "batches/10/0001/batch.json").read_text())
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1
    assert failed["error"] == "RuntimeError: synthetic failure"


def test_national_da_validation_rejects_invalid_inputs(tmp_path: Path) -> None:
    dgrf = tmp_path / "dgrf.csv"
    dgrf.write_text("other\nvalue\n")
    with pytest.raises(ValueError, match="missing required columns"):
        load_2021_small_area_jurisdictions(dgrf, "da")

    dgrf.write_text("PRDGUID_PRIDUGD,DADGUID_ADIDUGD\n2021A000299,2021S051299000001\n")
    with pytest.raises(ValueError, match="unsupported PRUID"):
        load_2021_small_area_jurisdictions(dgrf, "da")

    plan_path, _ = _prepare(tmp_path / "valid")
    with pytest.raises(ValueError, match="limit"):
        execute_canada_small_area_plan(plan_path, lambda _batch, _root: {}, limit=0)

    bad = tmp_path / "bad-plan.json"
    bad.write_text(json.dumps({"schema_version": "bad"}))
    with pytest.raises(ValueError, match="unsupported national"):
        execute_canada_small_area_plan(bad, lambda _batch, _root: {})

    with pytest.raises(ValueError, match="target_households"):
        estimate_national_small_area_storage([{"target_households": "many"}])
    assert estimate_national_small_area_storage([])["total_households"] == 0

    with pytest.raises(ValueError, match="at least 1"):
        prepare_canada_small_area_plan(
            {},
            tmp_path / "b",
            dgrf,
            tmp_path / "out",
            geography_level="da",
            max_households_per_batch=0,
        )
    with pytest.raises(ValueError, match="missing 2021"):
        prepare_canada_small_area_plan(
            {},
            tmp_path / "b",
            dgrf,
            tmp_path / "out",
            geography_level="da",
        )


def test_dgrf_validation_rejects_conflicts_and_invalid_identifiers(
    tmp_path: Path,
) -> None:
    dgrf = tmp_path / "dgrf.csv"
    dgrf.write_text(
        "PRDGUID_PRIDUGD,DADGUID_ADIDUGD\n"
        "2021A000210,2021S051210000001\n"
        "2021A000211,2021S051210000001\n"
    )
    with pytest.raises(ValueError, match="conflicting jurisdictions"):
        load_2021_small_area_jurisdictions(dgrf, "da")

    dgrf.write_text(
        "PRDGUID_PRIDUGD,DADGUID_ADIDUGD\n,\nnot-a-province,2021S051210000001\n"
    )
    with pytest.raises(ValueError, match="invalid province DGUID"):
        load_2021_small_area_jurisdictions(dgrf, "da")


def test_execute_national_plan_validates_state_and_stops_on_failure(
    tmp_path: Path,
) -> None:
    plan_path, _ = _prepare(tmp_path)

    with pytest.raises(RuntimeError, match="stop"):
        execute_canada_small_area_plan(
            plan_path,
            lambda _batch, _root: (_ for _ in ()).throw(RuntimeError("stop")),
        )
    persisted = json.loads(plan_path.read_text())
    assert persisted["status"] == "failed"

    batch_path = plan_path.parent / persisted["batches"][0]["manifest"]
    batch = json.loads(batch_path.read_text())
    batch["attempts"] = "once"
    batch_path.write_text(json.dumps(batch))
    with pytest.raises(ValueError, match="attempts"):
        execute_canada_small_area_plan(plan_path, lambda _batch, _root: {})

    persisted["batches"][0] = {"manifest": 42}
    plan_path.write_text(json.dumps(persisted))
    with pytest.raises(ValueError, match="record is invalid"):
        execute_canada_small_area_plan(plan_path, lambda _batch, _root: {})


def test_national_plan_internal_validation_and_batch_partitioning(
    tmp_path: Path,
) -> None:
    controls = {
        "10000001": {"hhsize": {"1": 8}, "tenure": {"1": 8}},
        "10000002": {"hhsize": {"1": 7}, "tenure": {"1": 7}},
    }
    assert national_small_area_module._partition_controls(controls, 10) == [
        ["10000001"],
        ["10000002"],
    ]

    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-canada-small-area-plan-v1",
                "batches": "not-a-list",
            }
        )
    )
    with pytest.raises(ValueError, match="batches must be a list"):
        execute_canada_small_area_plan(plan, lambda _batch, _root: {})

    plan.write_text("[]")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        execute_canada_small_area_plan(plan, lambda _batch, _root: {})

    plan_path, payload = _prepare(tmp_path / "valid")
    batch_path = plan_path.parent / payload["batches"][0]["manifest"]
    batch = json.loads(batch_path.read_text())
    batch["schema_version"] = "old"
    batch_path.write_text(json.dumps(batch))
    with pytest.raises(ValueError, match="unsupported batch schema"):
        execute_canada_small_area_plan(plan_path, lambda _batch, _root: {})

    with pytest.raises(ValueError, match="batches must be a list"):
        national_small_area_module._refresh_plan_status({"batches": "bad"}, tmp_path)
    with pytest.raises(ValueError, match="record is invalid"):
        national_small_area_module._refresh_plan_status({"batches": [{}]}, tmp_path)


def test_cli_fetches_only_missing_regional_profiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    existing = profiles / "2021-census-profile-da-atlantic.csv"
    existing.write_text("existing")
    calls: list[str] = []

    def fake_fetch(key: str, out_dir: Path, *, census_year: int) -> Path:
        calls.append(key)
        out_dir.mkdir(parents=True, exist_ok=True)
        destination = out_dir / f"{census_year}-census-profile-{key}.csv"
        destination.write_text(key)
        return destination

    monkeypatch.setattr("synthpopcan.statcan.fetch_census_profile", fake_fetch)

    assert (
        main(["geo", "national-da", "fetch-profiles", "--out-dir", str(profiles)]) == 0
    )
    assert calls == list(required_2021_da_profile_keys()[1:])
    assert existing.read_text() == "existing"


def test_cli_national_profile_fetch_reports_download_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "synthpopcan.statcan.fetch_census_profile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    with pytest.raises(ClickException, match="Could not download"):
        main(
            [
                "geo",
                "national-da",
                "fetch-profiles",
                "--out-dir",
                str(tmp_path),
            ]
        )


def test_cli_prepares_national_plan_from_conventional_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    for key in required_2021_da_profile_keys():
        (profiles / f"2021-census-profile-{key}.csv").write_text(key)
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text("{}")
    relationships = tmp_path / "relationships.csv"
    relationships.write_text("header\n")
    output = tmp_path / "out"
    captured = {}

    def fake_prepare(profile_paths, boundary_path, relationship_path, out, **options):
        captured.update(
            {
                "profiles": profile_paths,
                "boundaries": boundary_path,
                "relationships": relationship_path,
                "out": out,
                **options,
            }
        )
        out.mkdir()
        (out / "plan.json").write_text("{}")
        return {
            "coverage": {
                "jurisdictions": 13,
                "expected_geographies": 57_000,
                "usable_geographies": 56_000,
            },
            "batches": [{}, {}],
        }

    monkeypatch.setattr(
        "synthpopcan.national_small_area.prepare_canada_small_area_plan",
        fake_prepare,
    )

    assert (
        main(
            [
                "geo",
                "national-da",
                "prepare",
                "--profiles-dir",
                str(profiles),
                "--boundaries",
                str(boundaries),
                "--relationships",
                str(relationships),
                "--out",
                str(output),
                "--max-households-per-batch",
                "50000",
            ]
        )
        == 0
    )
    assert captured["out"] == output
    assert captured["max_households_per_batch"] == 50_000
    assert set(captured["profiles"]) == set(required_2021_da_profile_keys())


def test_cli_national_prepare_reports_missing_profiles(tmp_path: Path) -> None:
    boundaries = tmp_path / "boundaries.geojson"
    boundaries.write_text("{}")
    relationships = tmp_path / "relationships.csv"
    relationships.write_text("header\n")
    with pytest.raises(UsageError, match="Missing required profile files"):
        main(
            [
                "geo",
                "national-da",
                "prepare",
                "--profiles-dir",
                str(tmp_path),
                "--boundaries",
                str(boundaries),
                "--relationships",
                str(relationships),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def _mock_national_acceleration(
    monkeypatch,
    *,
    condition_key: str,
) -> dict[str, object]:
    captured: dict[str, object] = {}
    package = {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "household_size_column": "household_size",
    }
    monkeypatch.setattr(
        "synthpopcan.cli_tree._read_package_path_or_id",
        lambda _value: (package, "model-id", None),
    )
    monkeypatch.setattr(
        "synthpopcan.cli_tree.validate_package_allows_generation",
        lambda _package: None,
    )
    monkeypatch.setattr(
        "synthpopcan.cli_tree.package_models",
        lambda _package: ("household-model", "person-model"),
    )

    def fake_prepare(_plan_path, **options):
        captured["prepare"] = options
        return {
            condition_key: {
                "rows": {"households": 10_000, "persons": 24_000},
            }
        }

    monkeypatch.setattr(
        "synthpopcan.national_execution.prepare_national_candidate_pools",
        fake_prepare,
    )
    monkeypatch.setattr(
        "synthpopcan.national_execution.build_national_geography_summary",
        lambda _path: {
            "geographies": 1,
            "assigned_households": 1,
            "assigned_persons": 2,
        },
    )
    monkeypatch.setattr(
        "synthpopcan.cli_geo._render_deferred_national_maps",
        lambda *_args, **kwargs: captured.setdefault("maps", kwargs),
    )
    return captured


def test_cli_national_run_uses_cached_pool_workers_and_deferred_maps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured = _mock_national_acceleration(monkeypatch, condition_key="10")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan_identity()))

    def fake_execute(path, runner, **options):
        assert path == plan_path
        configuration = runner.keywords["configuration"]
        captured["configuration"] = configuration
        captured["execute"] = options
        return {
            "batches": [],
            "last_execution": {"attempted_batches": 1},
        }

    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        fake_execute,
    )

    assert (
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
                "--limit",
                "1",
                "--jurisdiction",
                "NL",
                "--candidate-pool-size",
                "5000",
                "--workers",
                "2",
                "--fit-workers",
                "3",
                "--maps",
            ]
        )
        == 0
    )
    prepare = captured["prepare"]
    assert prepare["requested_pool_size"] == 5_000
    assert prepare["condition_by_jurisdiction"] is True
    assert prepare["pumf_pr_values"] == {"10"}
    assert captured["execute"] == {
        "limit": 1,
        "continue_on_error": False,
        "jurisdiction_pruids": {"10"},
        "workers": 2,
    }
    configuration = captured["configuration"]
    assert configuration.geography_level == "da"
    assert configuration.fit_workers == 3
    assert configuration.pool_manifests["10"].endswith(
        "candidate-pools/pr-10/manifest.json"
    )
    assert captured["maps"]["geography_level"] == "da"


def test_cli_national_run_reuses_verified_local_pool_without_model_load(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model_path = tmp_path / "model.json"
    model_path.write_text("{}")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan_identity()))
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "synthpopcan.national_execution.find_cached_national_candidate_pools",
        lambda *_args, **_options: {"10": {"rows": {"households": 10, "persons": 20}}},
    )
    monkeypatch.setattr(
        "synthpopcan.cli_tree._read_package_path_or_id",
        lambda _value: pytest.fail("verified cache should skip model loading"),
    )

    def fake_execute(_path, runner, **options):
        captured["configuration"] = runner.keywords["configuration"]
        captured["options"] = options
        return {
            "status": "completed",
            "batches": [],
            "last_execution": {"attempted_batches": 0},
        }

    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        fake_execute,
    )
    monkeypatch.setattr(
        "synthpopcan.national_execution.build_national_geography_summary",
        lambda _path: {
            "geographies": 1,
            "assigned_households": 2,
            "assigned_persons": 5,
        },
    )
    monkeypatch.setattr(
        "synthpopcan.cli_geo._render_national_summary_map",
        lambda *_args, **_options: {
            "geographies": 1,
            "assigned_households": 2,
            "assigned_persons": 5,
        },
    )

    assert (
        main(
            [
                "geo",
                "national-da",
                "run",
                str(model_path),
                "--plan",
                str(plan_path),
            ]
        )
        == 0
    )
    assert (
        captured["configuration"]
        .pool_manifests["10"]
        .endswith("candidate-pools/pr-10/manifest.json")
    )


@pytest.mark.parametrize(
    "plan",
    [
        {},
        {
            "geography": {
                "geography_level": "da",
                "identifier_column": None,
                "identifier_namespace": None,
            }
        },
    ],
)
def test_cli_national_run_rejects_incomplete_geography_identity(
    tmp_path: Path,
    plan: dict[str, object],
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(UsageError, match="geography identity"):
        main(
            [
                "geo",
                "national-da",
                "run",
                "model",
                "--plan",
                str(plan_path),
            ]
        )


def test_cli_national_ada_run_uses_shared_synthesis_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured = _mock_national_acceleration(monkeypatch, condition_key="70")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan_identity("ada")))

    def fake_execute(_path, runner, **options):
        captured["configuration"] = runner.keywords["configuration"]
        assert options["jurisdiction_pruids"] == {"62"}
        return {"batches": [], "last_execution": {"attempted_batches": 1}}

    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        fake_execute,
    )

    assert (
        main(
            [
                "geo",
                "national-ada",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
                "--jurisdiction",
                "NU",
                "--no-maps",
            ]
        )
        == 0
    )
    configuration = captured["configuration"]
    assert configuration.geography_level == "ada"
    assert configuration.identifier_column == "ADAUID"
    assert configuration.identifier_namespace == "statcan:census:2021:ada"
    assert configuration.pool_manifests["70"].endswith(
        "candidate-pools/pr-70/manifest.json"
    )


def test_national_commands_reject_the_other_geography_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan_identity("da")))
    with pytest.raises(UsageError, match="requires a ADA plan"):
        main(
            [
                "geo",
                "national-ada",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
            ]
        )


def test_cli_national_run_refuses_insufficient_disk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                **_plan_identity(),
                "storage_estimate": {
                    "recommended_free_space_bytes": 10 * 1024**3,
                },
            }
        )
    )
    disk_usage = __import__("shutil")._ntuple_diskusage(100, 99, 1)
    monkeypatch.setattr("shutil.disk_usage", lambda _path: disk_usage)

    with pytest.raises(UsageError, match="recommends"):
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
            ]
        )


def test_cli_national_run_supports_unconditioned_mapless_batches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured = _mock_national_acceleration(monkeypatch, condition_key="all")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                **_plan_identity(),
                "storage_estimate": {"recommended_free_space_bytes": 1},
            }
        )
    )

    def fake_execute(_path, runner, **options):
        captured["configuration"] = runner.keywords["configuration"]
        assert options["jurisdiction_pruids"] is None
        return {"batches": [], "last_execution": {"attempted_batches": 1}}

    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        fake_execute,
    )

    assert (
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
                "--no-condition-by-jurisdiction",
                "--no-maps",
            ]
        )
        == 0
    )
    prepare = captured["prepare"]
    assert prepare["condition_by_jurisdiction"] is False
    configuration = captured["configuration"]
    assert set(configuration.pool_manifests.values()) == {
        "candidate-pools/all/manifest.json"
    }
    assert "maps" not in captured


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"controls": "bad"}, "controls must be an object"),
        ({"target_households": "one"}, "target_households must be an integer"),
        ({"jurisdiction": "bad"}, "jurisdiction must be an object"),
        ({"batch_id": ""}, "batch_id must be a non-empty string"),
    ],
)
def test_cli_national_run_rejects_malformed_batches(
    tmp_path: Path,
    monkeypatch,
    change: dict[str, object],
    message: str,
) -> None:
    _mock_national_acceleration(monkeypatch, condition_key="35")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan_identity()))
    batch = {
        "batch_id": "35-0001",
        "jurisdiction": {"pruid": "35", "pumf_pr": "35"},
        "controls": {"path": "controls.csv"},
        "boundaries": "boundaries.geojson",
        "output_directory": "population",
        "target_households": 1,
        **change,
    }

    def fake_execute(_path, runner, **_options):
        runner(batch, tmp_path)
        return {}

    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        fake_execute,
    )
    with pytest.raises(ClickException, match=message):
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(plan_path),
            ]
        )


def test_cli_national_run_reports_plan_io_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ClickException, match="Could not read"):
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(missing),
            ]
        )

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(_plan_identity()))
    _mock_national_acceleration(monkeypatch, condition_key="10")
    monkeypatch.setattr(
        "synthpopcan.national_small_area.execute_canada_small_area_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read only")),
    )
    with pytest.raises(ClickException, match="Could not read or write"):
        main(
            [
                "geo",
                "national-da",
                "run",
                "model-id",
                "--plan",
                str(plan),
            ]
        )
