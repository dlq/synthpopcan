"""Webapi small area behaviour and regression tests."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from support.webapi_fixtures import (
    control_pack_household_controls_csv,
    control_pack_request,
    store_upload,
    wait_for_terminal,
)

from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore
from synthpopcan.webapi import (
    _preflight_small_area_run,
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root
from synthpopcan.workflows.models import LOCAL_RUN_MAX_HOUSEHOLDS


def test_small_area_api_runs_generation_and_calibration_durably(tmp_path: Path) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    async def exercise() -> dict:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            controls = await client.post(
                "/api/uploads",
                content=(
                    b"margin,dimensions,tract,tenure,count\n"
                    b'tenure,"tract,tenure",001,owner,2\n'
                    b'tenure,"tract,tenure",001,renter,1\n'
                    b'tenure,"tract,tenure",002,owner,2\n'
                    b'tenure,"tract,tenure",002,renter,1\n'
                ),
                headers={"x-filename": "controls.csv", "content-type": "text/csv"},
            )
            request = {
                "workflow": "small_area",
                "inputs": {
                    "model_id": "demo-linked-household-person",
                    "controls_upload_id": controls.json()["upload_id"],
                },
                "options": {
                    "candidate_households": 20,
                    "geography_dimension": "tract",
                    "geography_column": "tract",
                    "conditions": {"geo": "Demo North"},
                    "random_seed": 13,
                    "pool_size": 20,
                    "subsample_seed": 7,
                    "chunk_size": 3,
                },
            }
            preflight = await client.post("/api/preflight", json=request)
            assert preflight.status_code == 200
            assert preflight.json()["estimate"]["target_geographies"] == 2
            created = await client.post("/api/runs", json=request)
            assert created.status_code == 202
            return await wait_for_terminal(client, created.json()["run_id"])

    try:
        manifest = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert manifest["status"] == "succeeded"
    assert manifest["summary"]["assigned_households"] == 6
    assert manifest["summary"]["total_geographies"] == 2
    assert manifest["summary"]["non_converged_count"] == 0
    assert {artifact["logical_name"] for artifact in manifest["artifacts"]} == {
        "households",
        "persons",
        "linked_population_manifest",
        "small_area_report",
    }
    assert "geo synthesize" in manifest["reproduction"]["shell"]
    assert "inputs/controls.csv" in manifest["reproduction"]["shell"]
    assert "reproduced" in manifest["reproduction"]["shell"]
    assert manifest["assurance"]["diagnostics"]["linked_population"]["passed"] is True
    assert app.state.run_store.verify_assurance(str(manifest["run_id"])) == {
        "passed": True,
        "issues": [],
    }


@pytest.fixture
def small_area_preflight_inputs(tmp_path: Path):
    store = RunStore(tmp_path)
    package = store_upload(
        store,
        "package.json",
        json.dumps(model_payload("demo-linked-household-person")).encode(),
    )
    controls = store_upload(
        store,
        "controls.csv",
        (
            b"margin,dimensions,tract,tenure,count\n"
            b'tenure,"tract,tenure",001,owner,1\n'
            b'tenure,"tract,tenure",001,renter,1\n'
        ),
    )
    person_controls = store_upload(
        store,
        "person-controls.csv",
        (
            b"margin,dimensions,tract,sex,count\n"
            b'sex,"tract,sex",001,F,1\n'
            b'sex,"tract,sex",001,M,1\n'
        ),
    )
    boundaries = store_upload(
        store,
        "boundaries.geojson",
        b'{"type":"FeatureCollection","features":[]}',
    )
    base = {
        "workflow": "small_area",
        "inputs": {
            "package_upload_id": package,
            "controls_upload_id": controls,
            "person_controls_upload_id": person_controls,
            "boundaries_upload_id": boundaries,
        },
        "options": {
            "candidate_households": 10,
            "geography_dimension": "tract",
            "conditions": {"geo": "Demo North"},
            "max_household_size": 5,
        },
    }

    return store, base


def test_small_area_preflight_preserves_optional_inputs(small_area_preflight_inputs):
    store, request = small_area_preflight_inputs
    result = _preflight_small_area_run(store, request)
    assert result["ready"] is True
    assert (
        result["request"]["inputs"]["package_upload_id"]
        == request["inputs"]["package_upload_id"]
    )
    assert result["request"]["options"]["max_household_size"] == 5
    assert "map" in result["expected_artifacts"]


def test_small_area_preflight_rejects_non_collection_boundaries(
    small_area_preflight_inputs,
):
    store, request = small_area_preflight_inputs
    request["inputs"]["boundaries_upload_id"] = store_upload(
        store, "bad.geojson", b'{"type":"Feature"}'
    )
    with pytest.raises(ValueError, match="GeoJSON FeatureCollection"):
        _preflight_small_area_run(store, request)


@pytest.mark.parametrize(
    "key,value,reason",
    [
        pytest.param(
            "conditions",
            [],
            "model conditions must be an object",
            id="non-object-conditions",
        ),
        pytest.param(
            "conditions",
            {"bad": "x"},
            "unsupported model condition",
            id="unknown-condition",
        ),
        pytest.param(
            "max_household_size", 0, "maximum household size", id="zero-maximum-size"
        ),
        pytest.param(
            "candidate_households",
            LOCAL_RUN_MAX_HOUSEHOLDS + 1,
            "local web runs are limited",
            id="local-size-limit",
        ),
    ],
)
def test_small_area_preflight_rejects_invalid_generation_options(
    small_area_preflight_inputs, key, value, reason
):
    store, request = small_area_preflight_inputs
    request["options"][key] = value
    with pytest.raises(ValueError, match=reason):
        _preflight_small_area_run(store, request)
    assert store.list_runs() == []


def test_small_area_preflight_rejects_unknown_household_dimensions(
    small_area_preflight_inputs,
):
    store, request = small_area_preflight_inputs
    controls = store_upload(
        store,
        "unsupported.csv",
        b'margin,dimensions,tract,unknown,count\nx,"tract,unknown",001,x,1\n',
    )
    request["inputs"] = {
        "model_id": "demo-linked-household-person",
        "controls_upload_id": controls,
    }
    with pytest.raises(ValueError, match="unsupported candidate columns: unknown"):
        _preflight_small_area_run(store, request)


@pytest.fixture
def candidate_preflight_inputs(small_area_preflight_inputs):
    store, base = small_area_preflight_inputs
    households = store_upload(
        store,
        "candidate-households.csv",
        b"synthetic_household_id,household_size,tenure\nh1,1,owner\nh2,1,renter\n",
    )
    persons = store_upload(
        store,
        "candidate-persons.csv",
        b"synthetic_person_id,synthetic_household_id,sex\np1,h1,F\np2,h2,M\n",
    )
    return store, {
        "workflow": "small_area",
        "inputs": {
            "candidate_households_upload_id": households,
            "candidate_persons_upload_id": persons,
            "controls_upload_id": base["inputs"]["controls_upload_id"],
        },
        "options": {"candidate_households": 999, "geography_dimension": "tract"},
    }


def test_uploaded_candidate_count_overrides_the_requested_generation_size(
    candidate_preflight_inputs,
):
    store, request = candidate_preflight_inputs
    result = _preflight_small_area_run(store, request)
    assert result["request"]["options"]["candidate_households"] == 2
    assert result["model_diagnostics"]["name"] == "Uploaded linked candidates"


def test_small_area_preflight_rejects_categories_absent_from_candidates(
    candidate_preflight_inputs,
):
    store, request = candidate_preflight_inputs
    request["inputs"]["controls_upload_id"] = store_upload(
        store,
        "unsupported-categories.csv",
        b'margin,dimensions,tract,tenure,count\ntenure,"tract,tenure",001,cooperative,1\n',
    )
    with pytest.raises(ValueError, match="tenure: cooperative"):
        _preflight_small_area_run(store, request)
    assert store.list_runs() == []


def test_small_area_control_pack_preflight_binds_candidates_controls_and_evidence(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path)
    request = control_pack_request(store)

    preflight = _preflight_small_area_run(store, request)

    assert preflight["ready"] is True
    assert preflight["control_pack_plan"]["passed"] is True
    assert preflight["control_pack_plan"]["pack"]["identifier"] == (
        "statcan-2021-core-private-household-da-v1"
    )
    assert preflight["request"]["inputs"]["control_pack_id"] == (
        "statcan-2021-core-private-household-da-v1"
    )
    assert preflight["request"]["options"]["geography_universe"] == {
        "schema_version": "synthpopcan-geography-universe-v1",
        "census_vintage": 2021,
        "geography_level": "da",
        "identifier_namespace": "statcan:census:2021:da",
        "identifier_column": "DAUID",
        "dguid_column": None,
    }

    missing_evidence = deepcopy(request)
    missing_evidence["inputs"].pop("control_pack_evidence_upload_id")
    with pytest.raises(ValueError, match="select a control pack and upload"):
        _preflight_small_area_run(store, missing_evidence)

    tampered_controls = store_upload(
        store,
        "tampered-household-controls.csv",
        control_pack_household_controls_csv(multiplier=2),
    )
    tampered = deepcopy(request)
    tampered["inputs"]["controls_upload_id"] = tampered_controls
    with pytest.raises(ValueError, match="household controls checksum"):
        _preflight_small_area_run(store, tampered)


@pytest.mark.parametrize(
    "section,key,value,message",
    [
        (None, "inputs", [], "small-area inputs must be an object"),
        (None, "options", [], "small-area options must be an object"),
        ("options", "geography_universe", [], "geography_universe must be an object"),
        ("options", "candidate_households", 0, "candidate households must be positive"),
        ("options", "chunk_size", 0, "chunk size must be positive"),
        ("options", "geography_dimension", " ", "geography dimension is required"),
        (
            "inputs",
            "candidate_households_upload_id",
            "unpaired",
            "provide both candidate",
        ),
        ("inputs", "model_id", None, "provide one model/package"),
        ("inputs", "control_pack_id", "unpaired", "select a control pack"),
    ],
    ids=[
        "non-object-inputs",
        "non-object-options",
        "non-object-geography",
        "zero-candidates",
        "zero-chunk-size",
        "blank-dimension",
        "unpaired-candidates",
        "missing-generation-source",
        "unpaired-pack-evidence",
    ],
)
def test_small_area_preflight_rejection_preserves_uploads_and_creates_no_run(
    tmp_path, section, key, value, message
):
    store = RunStore(tmp_path)
    controls_id = store_upload(
        store,
        "controls.csv",
        b'margin,dimensions,tract,tenure,count\ntenure,"tract,tenure",001,owner,1\n',
    )
    request = {
        "workflow": "small_area",
        "inputs": {
            "model_id": "demo-linked-household-person",
            "controls_upload_id": controls_id,
        },
        "options": {"candidate_households": 10, "geography_dimension": "tract"},
    }
    target = request if section is None else request[section]
    target[key] = value
    original = store.upload_path(controls_id, require_unclaimed=True).read_bytes()
    with pytest.raises(ValueError, match=message):
        _preflight_small_area_run(store, request)
    assert store.list_runs() == []
    assert (
        store.upload_path(controls_id, require_unclaimed=True).read_bytes() == original
    )


@pytest.mark.parametrize(
    "level,body,message",
    [
        (
            "household",
            b"margin,dimensions,tract,tenure,count\n",
            "controls CSV has no control rows",
        ),
        (
            "person",
            b"margin,dimensions,tract,sex,count\n",
            "person controls CSV has no control rows",
        ),
        (
            "person",
            b'margin,dimensions,tract,unknown,count\nx,"tract,unknown",001,x,1\n',
            "person controls require unsupported candidate columns",
        ),
        (
            "person",
            b'margin,dimensions,tract,sex,count\nsex,"tract,sex",001,X,1\n',
            "person controls contain categories absent",
        ),
    ],
    ids=[
        "empty-household-vector",
        "empty-person-vector",
        "unknown-person-dimension",
        "unsupported-person-category",
    ],
)
def test_small_area_preflight_rejects_invalid_control_vectors(
    tmp_path, level, body, message
):
    store = RunStore(tmp_path)
    controls_id = store_upload(
        store,
        "controls.csv",
        b'margin,dimensions,tract,tenure,count\ntenure,"tract,tenure",001,owner,1\n',
    )
    bad_id = store_upload(store, "bad.csv", body)
    inputs = {
        "model_id": "demo-linked-household-person",
        "controls_upload_id": controls_id,
    }
    inputs[
        "person_controls_upload_id" if level == "person" else "controls_upload_id"
    ] = bad_id
    with pytest.raises(ValueError, match=message):
        _preflight_small_area_run(
            store,
            {
                "workflow": "small_area",
                "inputs": inputs,
                "options": {"candidate_households": 10, "geography_dimension": "tract"},
            },
        )
    assert store.list_runs() == []
    assert store.upload_path(bad_id, require_unclaimed=True).read_bytes() == body
