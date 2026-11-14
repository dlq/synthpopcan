"""Webapi small area behaviour and regression tests."""

from __future__ import annotations

import asyncio
import csv
import json
import shlex
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

from synthpopcan.geography import statcan_geography_universe
from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore
from synthpopcan.webapi import (
    _preflight_small_area_run,
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root
from synthpopcan.workflows.models import LOCAL_RUN_MAX_HOUSEHOLDS


@pytest.mark.parametrize("year", [2016, 2021])
def test_conditional_joint_durable_run_and_reproduction(tmp_path, monkeypatch, year):
    tract = "4620053.00"
    if year == 2016:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "GEO_CODE (POR)",
            "Member ID: Profile of Census Tracts (2247)",
            "Dim: Sex (3): Member ID: [1]: Total - Sex",
        ]
        prefix = [year, 2, tract]
        members = [
            1135,
            1683,
            672,
            1684,
            1685,
            1688,
            1689,
            1690,
            1691,
            1693,
            1694,
            1695,
            1696,
            1697,
        ]
    else:
        header = [
            "CENSUS_YEAR",
            "GEO_LEVEL",
            "ALT_GEO_CODE",
            "DGUID",
            "CHARACTERISTIC_ID",
            "C1_COUNT_TOTAL",
            "SYMBOL",
        ]
        prefix = [year, "Census tract", tract, f"2021S0507{tract}"]
        members = [
            1522,
            1998,
            126,
            1999,
            2000,
            2004,
            2005,
            2006,
            2007,
            2009,
            2010,
            2011,
            2012,
            2013,
        ]
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    for member, value in zip(
        members, [20, 15, 15, 5, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0], strict=True
    ):
        writer.writerow([*prefix, member, value, *([""] if year == 2021 else [])])
    extra = (
        {1865: 15, 1867: 5, 1868: 5, 1869: 0, 1873: 15, 1874: 5, 1876: 5, 1877: 0}
        if year == 2016
        else {2223: 15, 2225: 5, 2226: 5, 2227: 0, 2231: 15, 2232: 5, 2234: 5, 2235: 0}
    )
    for member, value in extra.items():
        writer.writerow([*prefix, member, value, *([""] if year == 2021 else [])])
    marital = StringIO(newline="")
    marital_writer = csv.writer(marital)
    marital_writer.writerow(["ct", "marital_status", "age_20", "value"])
    observed = {(1, 1): 20, (1, 2): 5, (1, 3): 15, (3, 3): 5, (6, 3): 5}
    for status in (1, 3, 4, 6, 7, 8, 9):
        ages = (1, 2, 3, *range(6, 16)) if status == 1 else (3, *range(6, 16))
        for age in ages:
            marital_writer.writerow(
                [tract, status, age, observed.get((status, age), 0)]
            )
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )
    store = app.state.run_store
    education_source = buffer.getvalue().encode()
    if year == 2021:
        from io import BytesIO
        from zipfile import ZipFile

        archive = BytesIO()
        with ZipFile(archive, "w") as zipped:
            zipped.writestr("test_English_CSV_data.csv", education_source)
        writer = store.begin_upload(
            "profile.zip",
            media_type="application/zip",
            max_bytes=len(archive.getvalue()),
        )
        writer.write(archive.getvalue())
        education_upload = writer.finish()["upload_id"]
    else:
        education_upload = store_upload(store, "profile.csv", education_source)
    inputs = {
        "candidate_households_upload_id": store_upload(
            store, "hh.csv", b"synthetic_household_id,household_size\na,1\nb,1\nc,2\n"
        ),
        "candidate_persons_upload_id": store_upload(
            store,
            "pp.csv",
            (
                "synthetic_person_id,synthetic_household_id,AGEGRP,HDGREE,"
                f"{'LFTAG' if year == 2016 else 'LFACT'},WRKACT,"
                f"{'MarStH' if year == 2016 else 'MARSTH'},group\n"
                "p1,a,3,1,1,2,1,all\np2,b,12,8,8,11,2,all\np3,c,3,1,1,2,1,all\np4,c,2,99,99,99,8,all\n"
            ).encode(),
        ),
        "controls_upload_id": store_upload(
            store,
            "hc.csv",
            f'margin,dimensions,ct,household_size,count\nsize,"ct,household_size",{tract},1,10\nsize,"ct,household_size",{tract},2,5\n'.encode(),
        ),
        "person_controls_upload_id": store_upload(
            store,
            "pc.csv",
            f'margin,dimensions,ct,group,count\npeople,"ct,group",{tract},all,20\n'.encode(),
        ),
        "education_profile_upload_id": education_upload,
        "education_pack": f"statcan-{year}-education-ct-v1",
        "labour_force_profile_upload_id": store_upload(
            store, "labour.csv", buffer.getvalue().encode()
        ),
        "labour_force_pack": f"statcan-{year}-labour-force-status-ct-v1",
        "work_activity_profile_upload_id": store_upload(
            store, "work.csv", buffer.getvalue().encode()
        ),
        "work_activity_pack": f"statcan-{year}-work-activity-ct-v1",
        "marital_status_controls_upload_id": store_upload(
            store, "marital.csv", marital.getvalue().encode()
        ),
        "marital_status_pack": f"statcan-{year}-marital-status-ct-v1",
    }
    request = {
        "workflow": "small_area",
        "inputs": inputs,
        "options": {
            "geography_dimension": "ct",
            "geography_universe": statcan_geography_universe(
                year, "ct", "ct"
            ).as_dict(),
            "integerization": "swap",
        },
    }
    wrong_vintage = deepcopy(request)
    wrong_vintage["inputs"]["education_pack"] = (
        f"statcan-{2021 if year == 2016 else 2016}-education-ct-v1"
    )
    with pytest.raises(ValueError, match="matching Statistics Canada CT geography"):
        _preflight_small_area_run(store, wrong_vintage)
    assert store.get_upload(inputs["education_profile_upload_id"])["claimed_by"] is None
    incomplete = deepcopy(request)
    incomplete["inputs"].pop("education_profile_upload_id")
    with pytest.raises(ValueError, match="requires its matching source upload"):
        _preflight_small_area_run(store, incomplete)
    invalid = deepcopy(request)
    invalid["inputs"]["education_profile_upload_id"] = store_upload(
        store, "invalid.csv", b"CENSUS_YEAR,GEO_LEVEL\n"
    )
    with pytest.raises(ValueError, match="Expected the .* Census Profile"):
        _preflight_small_area_run(store, invalid)
    assert (
        store.get_upload(invalid["inputs"]["education_profile_upload_id"])["claimed_by"]
        is None
    )

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            if year == 2021:
                uploaded = await client.post(
                    "/api/uploads",
                    content=archive.getvalue(),
                    headers={
                        "x-filename": "profile.zip",
                        "content-type": "application/zip",
                    },
                )
                assert uploaded.status_code == 201, uploaded.text
            rejected = await client.post("/api/preflight", json=wrong_vintage)
            assert rejected.status_code == 400
            assert "matching Statistics Canada CT geography" in rejected.json()["error"]
            preflight = await client.post("/api/preflight", json=request)
            assert preflight.status_code == 200, preflight.text
            assert (
                preflight.json()["request"]["inputs"]["education_pack"]
                == inputs["education_pack"]
            )
            original = store.create_small_area_run(preflight.json()["request"])
            original_id = original["run_id"]
            rejected = await client.post(f"/api/runs/{original_id}/restart")
            assert rejected.status_code == 400
            assert "Only interrupted" in rejected.json()["error"]
            store.transition_run(original_id, "running")
            partial = store.run_dir(original_id) / "work" / "partial-output.csv"
            partial.write_text("incomplete\n")
            published = store.run_dir(original_id) / "artifacts" / "households.csv"
            published.write_text("published-before-crash\n")
            store.transition_run(original_id, "interrupted")
            saved_path = store.resolve_managed_path(original["inputs"][0]["path"])
            saved_bytes = saved_path.read_bytes()
            saved_path.write_bytes(b"tampered\n")
            rejected = await client.post(f"/api/runs/{original_id}/restart")
            assert rejected.status_code == 400
            assert "changed" in rejected.json()["error"]
            saved_path.write_bytes(saved_bytes)
            from unittest.mock import patch

            with patch.object(
                app.state.job_manager,
                "enqueue",
                side_effect=OSError("queue unavailable"),
            ):
                rejected = await client.post(f"/api/runs/{original_id}/restart")
            assert rejected.status_code == 400
            failed = next(run for run in store.list_runs() if run["status"] == "failed")
            assert failed["error"]["kind"] == "restart_queue_error"
            assert store.load_run(original_id)["status"] == "interrupted"
            response = await client.post(f"/api/runs/{original_id}/restart")
            assert response.status_code == 202, response.text
            restarted = await wait_for_terminal(client, response.json()["run_id"])
            assert restarted["restarted_from"] == original_id
            assert store.load_run(original_id)["status"] == "interrupted"
            assert partial.read_text() == "incomplete\n"
            assert published.read_text() == "published-before-crash\n"
            return restarted

    try:
        manifest = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()
    assert manifest["status"] == "succeeded", manifest
    assert any(
        item["logical_name"] == "education_profile" for item in manifest["inputs"]
    )
    assert {
        "education_profile",
        "labour_force_profile",
        "work_activity_profile",
        "marital_status_controls",
    }.issubset({item["logical_name"] for item in manifest["inputs"]})
    assert store.verify_assurance(str(manifest["run_id"])) == {
        "passed": True,
        "issues": [],
    }
    replay = shlex.split(manifest["reproduction"]["shell"])
    assert replay[replay.index("--education-profile") + 1] == (
        "inputs/education-profile.zip"
        if year == 2021
        else "inputs/education-profile.csv"
    )
    assert replay[replay.index("--integerization") + 1] == "swap"
    monkeypatch.chdir(store.run_dir(str(manifest["run_id"])))
    from synthpopcan.cli import main

    assert main(replay[1:]) == 0

    # Exercise the generated-candidate CLI adapter against the same source cells.
    # The generator is replaced only to make its output the same deterministic
    # linked pool as the durable run; calibration and validation remain real.
    def generate_candidates(*args, households_path, persons_path, **kwargs):
        households_path.write_bytes(Path("inputs/households.csv").read_bytes())
        persons_path.write_bytes(Path("inputs/persons.csv").read_bytes())

    monkeypatch.setattr(
        "synthpopcan.tree.generate_linked_population_to_csv", generate_candidates
    )
    cli_args = replay[1:]
    assert cli_args[:2] == ["geo", "calibrate"]
    cli_args = [
        "geo",
        "synthesize",
        "demo-linked-household-person",
        "--households",
        "3",
    ] + cli_args[3:]
    persons_index = cli_args.index("--persons")
    del cli_args[persons_index : persons_index + 2]
    out_index = cli_args.index("--out")
    cli_args[out_index + 1] = "generated-replay"
    assert main(cli_args) == 0


def test_interrupted_conditional_run_preserves_claimed_source(tmp_path):
    store = RunStore(tmp_path / "workspace")
    inputs = {
        "candidate_households_upload_id": store_upload(store, "hh.csv", b"id\nh1\n"),
        "candidate_persons_upload_id": store_upload(store, "pp.csv", b"id\np1\n"),
        "controls_upload_id": store_upload(store, "controls.csv", b"control\n1\n"),
        "education_pack": "statcan-2021-education-ct-v1",
        "education_profile_upload_id": store_upload(
            store, "profile.csv", b"profile\n1\n"
        ),
    }
    request = {"workflow": "small_area", "inputs": inputs, "options": {}}
    run = store.create_small_area_run(request)
    run_id = str(run["run_id"])
    store.transition_run(run_id, "running")
    recovered = RunStore(tmp_path / "workspace")
    interrupted = recovered.load_run(run_id)
    assert interrupted["status"] == "interrupted"
    assert interrupted["error"]["kind"] == "interrupted"
    profile = next(
        i for i in interrupted["inputs"] if i["logical_name"] == "education_profile"
    )
    assert (
        recovered.resolve_managed_path(profile["path"]).read_bytes() == b"profile\n1\n"
    )
    assert (
        interrupted["request"]["inputs"]["education_pack"] == inputs["education_pack"]
    )


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


@pytest.mark.parametrize("vintage", [2016, 2021])
def test_web_preflight_accepts_each_broad_person_margin_independently(
    tmp_path, vintage
):
    from support.control_pack_fixtures import (
        _GEOGRAPHY_IDS,
        _evidence,
        _expanded_population,
        _expanded_tables,
        _write_rows,
    )

    from synthpopcan.control_packs import plan_control_pack
    from synthpopcan.controls import write_control_table

    pack_id = f"statcan-{vintage}-broad-da-v1"
    geography = _GEOGRAPHY_IDS["da"]
    households, persons = _expanded_population(vintage)
    controls, person_controls = _expanded_tables(
        pack_id, households, persons, geography=geography
    )
    evidence = _evidence(
        pack_id, controls, person_controls, (geography,), private_people=len(persons)
    )
    assert plan_control_pack(
        pack_id, households, persons, controls, person_controls, evidence=evidence
    )["passed"]
    store = RunStore(tmp_path / "workspace")
    inputs = {"control_pack_id": pack_id}
    for name, rows in [
        ("candidate_households", households),
        ("candidate_persons", persons),
    ]:
        path = tmp_path / f"{name}.csv"
        _write_rows(path, rows)
        inputs[f"{name}_upload_id"] = store_upload(store, path.name, path.read_bytes())
    for name, table in [("controls", controls), ("person_controls", person_controls)]:
        path = tmp_path / f"{name}.csv"
        write_control_table(path, table)
        inputs[f"{name}_upload_id"] = store_upload(store, path.name, path.read_bytes())
    inputs["control_pack_evidence_upload_id"] = store_upload(
        store, "evidence.json", evidence.model_dump_json().encode()
    )
    result = _preflight_small_area_run(
        store,
        {
            "workflow": "small_area",
            "inputs": inputs,
            "options": {"geography_dimension": "da"},
        },
    )
    assert result["ready"] is True
    assert result["control_pack_plan"]["passed"] is True
    assert result["request"]["options"]["candidate_households"] == len(households)


@pytest.mark.parametrize(
    "selected",
    [
        (),
        ("households",),
        ("persons",),
        ("model", "package"),
        ("model", "households"),
        ("model", "persons"),
        ("package", "households"),
        ("package", "persons"),
        ("model", "package", "households"),
        ("model", "package", "persons"),
        ("model", "households", "persons"),
        ("package", "households", "persons"),
        ("model", "package", "households", "persons"),
    ],
    ids=lambda selected: "+".join(selected) or "no-source",
)
def test_small_area_rejects_all_ambiguous_or_incomplete_sources(
    small_area_preflight_inputs, selected
):
    store, request = small_area_preflight_inputs
    fields = {
        "model": "model_id",
        "package": "package_upload_id",
        "households": "candidate_households_upload_id",
        "persons": "candidate_persons_upload_id",
    }
    for field in fields.values():
        request["inputs"].pop(field, None)
    request["inputs"].update({fields[name]: "unused-source" for name in selected})
    with pytest.raises(ValueError, match="provide"):
        _preflight_small_area_run(store, request)
