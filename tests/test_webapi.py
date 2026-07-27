from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import shlex
import shutil
import time
from io import StringIO
from pathlib import Path

import httpx
import pytest

from synthpopcan.cli import main
from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore
from synthpopcan.webapi import (
    _model_category_support,
    _preflight_model_run,
    _preflight_small_area_run,
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root
from synthpopcan.workflows.models import LOCAL_RUN_MAX_HOUSEHOLDS


def test_ipf_api_upload_preflight_run_events_artifacts_and_reproduction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    async def exercise() -> tuple[dict, bytes, dict, str, str]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            seed_upload = await upload(client, "seed.csv", seed_csv())
            controls_upload = await upload(client, "controls.csv", controls_csv())
            request = ipf_request(seed_upload, controls_upload)
            preflight = await client.post("/api/preflight", json=request)
            assert preflight.status_code == 200
            assert preflight.json()["ready"] is True
            assert preflight.json()["estimate"]["compact_output_rows"] == 4
            assert preflight.json()["estimate"]["population_total"] == 100
            created = await client.post("/api/runs", json=request)
            assert created.status_code == 202
            run_id = created.json()["run_id"]
            manifest = await wait_for_terminal(client, run_id)
            events = await client.get(f"/api/runs/{run_id}/events")
            replay_after_end = await client.get(
                f"/api/runs/{run_id}/events",
                headers={"last-event-id": "999"},
            )
            weights = next(
                item
                for item in manifest["artifacts"]
                if item["logical_name"] == "weights"
            )
            artifact = await client.get(
                f"/api/runs/{run_id}/artifacts/{weights['artifact_id']}"
            )
            preview = await client.get(
                f"/api/runs/{run_id}/artifacts/{weights['artifact_id']}/preview",
                params={"rows": 2},
            )
            assert preview.status_code == 200
            assert artifact.status_code == 200
            assert artifact.headers["content-disposition"].endswith(
                'filename="weights.csv"'
            )
            listed = await client.get("/api/runs")
            assert listed.json()["runs"][0]["run_id"] == run_id
            return (
                manifest,
                artifact.content,
                preview.json(),
                events.text,
                replay_after_end.text,
            )

    try:
        manifest, weights_bytes, preview, event_stream, replay_after_end = asyncio.run(
            exercise()
        )
    finally:
        app.state.job_manager.shutdown()

    assert manifest["status"] == "succeeded"
    assert manifest["reproduction"]["request"]["workflow"] == "ipf"
    assert "event: progress" in event_stream
    assert '"stage":"succeeded"' in event_stream
    assert replay_after_end == ""
    rows = list(csv.DictReader(StringIO(weights_bytes.decode())))
    assert len(rows) == 4
    assert sum(float(row["weight"]) for row in rows) == 100
    assert preview["columns"] == ["id", "age", "sex", "weight"]
    assert len(preview["rows"]) == 2
    assert preview["limit"] == 2
    rendered = shlex.split(manifest["reproduction"]["shell"])
    assert rendered[0] == "synthpopcan"
    assert rendered[rendered.index("--seed") + 1] == "inputs/seed.csv"
    assert rendered[rendered.index("--controls") + 1] == "inputs/controls.csv"
    monkeypatch.chdir(app.state.run_store.run_dir(str(manifest["run_id"])))
    assert main(rendered[1:]) == 0


def test_model_install_and_removal_return_bounded_catalogue_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def fetch(model_id: str) -> Path:
        if model_id == "missing":
            raise KeyError(model_id)
        if model_id == "broken":
            raise OSError("download failed")
        calls.append(("install", model_id))
        return tmp_path / "model.json"

    def remove(model_id: str) -> bool:
        calls.append(("remove", model_id))
        return True

    def entry(model_id: str) -> dict[str, object]:
        if model_id == "missing":
            raise KeyError(model_id)
        return {
            "id": model_id,
            "installed": calls[-1][0] == "install",
            "distribution": "download",
        }

    monkeypatch.setattr("synthpopcan.webapi.fetch_model_package", fetch)
    monkeypatch.setattr("synthpopcan.webapi.remove_cached_model", remove)
    monkeypatch.setattr("synthpopcan.webapi.model_catalogue_entry", entry)
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    async def exercise() -> tuple[httpx.Response, ...]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            installed = await client.post("/api/models/large-model/install")
            removed = await client.delete("/api/models/large-model")
            missing = await client.delete("/api/models/missing")
            missing_install = await client.post("/api/models/missing/install")
            broken_install = await client.post("/api/models/broken/install")
            return installed, removed, missing, missing_install, broken_install

    try:
        installed, removed, missing, missing_install, broken_install = asyncio.run(
            exercise()
        )
    finally:
        app.state.job_manager.shutdown()

    assert installed.status_code == 200
    assert installed.json() == {
        "model": {
            "id": "large-model",
            "installed": True,
            "distribution": "download",
        }
    }
    assert removed.status_code == 200
    assert removed.json()["removed"] is True
    assert "payload" not in removed.json()["model"]
    assert missing.status_code == 404
    assert missing_install.status_code == 404
    assert broken_install.status_code == 502
    assert calls == [("install", "large-model"), ("remove", "large-model")]


def test_model_category_support_handles_absent_model_level() -> None:
    assert _model_category_support({"models": {}}, "person", {"sex"}) == {"sex": set()}


def test_upload_is_streamed_hashed_sanitized_and_session_protected(
    tmp_path: Path,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path,
        session_secret="test-session",
    )
    body = seed_csv()

    async def chunks():
        yield body[:10]
        yield body[10:]

    async def exercise() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            forbidden = await client.post(
                "/api/uploads",
                content=body,
                headers={"x-filename": "seed.csv"},
            )
            await client.get("/api/app")
            uploaded = await client.post(
                "/api/uploads",
                content=chunks(),
                headers={"x-filename": "../../private/seed.csv"},
            )
            return forbidden, uploaded

    try:
        forbidden, uploaded = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert forbidden.status_code == 403
    assert uploaded.status_code == 201
    assert uploaded.json()["display_name"] == "seed.csv"
    assert uploaded.json()["byte_size"] == len(body)
    assert uploaded.json()["sha256"] == hashlib.sha256(body).hexdigest()


def test_prepared_model_api_preflight_run_preview_and_reproduction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            request = {
                "workflow": "model",
                "inputs": {"model_id": "demo-linked-household-person"},
                "options": {
                    "households": 6,
                    "conditions": {"geo": "Demo North"},
                    "random_seed": 13,
                    "chunk_size": 2,
                },
            }
            preflight = await client.post("/api/preflight", json=request)
            assert preflight.status_code == 200
            assert preflight.json()["ready"] is True
            estimate = preflight.json()["estimate"]
            assert estimate["households"] == 6
            assert estimate["output_bytes"] == 24_576
            assert estimate["storage_basis"] == "4 KiB per requested household"
            assert estimate["enough_disk"] is True
            assert (
                preflight.json()["model_diagnostics"]["privacy"][
                    "publishable_candidate"
                ]
                is True
            )
            created = await client.post("/api/runs", json=request)
            assert created.status_code == 202
            manifest = await wait_for_terminal(client, created.json()["run_id"])
            households = next(
                artifact
                for artifact in manifest["artifacts"]
                if artifact["logical_name"] == "households"
            )
            preview = await client.get(
                f"/api/runs/{manifest['run_id']}/artifacts/"
                f"{households['artifact_id']}/preview"
            )
            assert len(preview.json()["rows"]) == 6
            return manifest

    try:
        manifest = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert manifest["status"] == "succeeded"
    assert manifest["summary"]["generated_households"] == 6
    assert manifest["summary"]["linked_validation_passed"] is True
    assert manifest["assurance"]["model"]["identity"] == (
        "demo-linked-household-person"
    )
    assert app.state.run_store.verify_assurance(str(manifest["run_id"])) == {
        "passed": True,
        "issues": [],
    }
    rendered = shlex.split(manifest["reproduction"]["shell"])
    assert rendered[:4] == [
        "synthpopcan",
        "models",
        "generate",
        "demo-linked-household-person",
    ]
    assert rendered[rendered.index("--out") + 1] == "reproduced"
    monkeypatch.chdir(app.state.run_store.run_dir(str(manifest["run_id"])))
    assert main(rendered[1:]) == 0


def test_prepared_model_preflight_rejects_non_positive_chunk_size(
    tmp_path: Path,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            return await client.post(
                "/api/preflight",
                json={
                    "workflow": "model",
                    "inputs": {"model_id": "demo-linked-household-person"},
                    "options": {"households": 2, "chunk_size": 0},
                },
            )

    response = asyncio.run(exercise())
    assert response.status_code == 400
    assert response.json()["error"] == "chunk size must be positive"


def test_prepared_model_preflight_accepts_claimable_json_upload(tmp_path: Path) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path,
        session_secret="test-session",
    )

    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            body = json.dumps(model_payload("demo-linked-household-person")).encode()
            uploaded = await client.post(
                "/api/uploads",
                content=body,
                headers={
                    "x-filename": "package.json",
                    "content-type": "application/json",
                },
            )
            return await client.post(
                "/api/preflight",
                json={
                    "workflow": "model",
                    "inputs": {"package_upload_id": uploaded.json()["upload_id"]},
                    "options": {"households": 3},
                },
            )

    try:
        preflight = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()
    assert preflight.status_code == 200
    assert preflight.json()["ready"] is True


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


def test_model_preflight_caps_local_household_output(tmp_path: Path) -> None:
    store = RunStore(tmp_path)

    with pytest.raises(ValueError, match="local web runs are limited"):
        _preflight_model_run(
            store,
            {
                "workflow": "model",
                "inputs": {"model_id": "demo-linked-household-person"},
                "options": {"households": LOCAL_RUN_MAX_HOUSEHOLDS + 1},
            },
        )


def test_small_area_preflight_optional_inputs_and_validation(tmp_path: Path) -> None:
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

    preflight = _preflight_small_area_run(store, base)
    assert preflight["ready"] is True
    assert preflight["request"]["inputs"]["package_upload_id"] == package
    assert preflight["request"]["options"]["max_household_size"] == 5
    assert "map" in preflight["expected_artifacts"]

    bad_boundaries = store_upload(store, "bad.geojson", b'{"type":"Feature"}')
    with pytest.raises(ValueError, match="GeoJSON FeatureCollection"):
        _preflight_small_area_run(
            store,
            {
                **base,
                "inputs": {
                    **base["inputs"],
                    "boundaries_upload_id": bad_boundaries,
                },
            },
        )
    with pytest.raises(ValueError, match="model conditions must be an object"):
        _preflight_small_area_run(
            store,
            {**base, "options": {**base["options"], "conditions": []}},
        )
    with pytest.raises(ValueError, match="unsupported model condition"):
        _preflight_small_area_run(
            store,
            {**base, "options": {**base["options"], "conditions": {"bad": "x"}}},
        )
    with pytest.raises(ValueError, match="maximum household size"):
        _preflight_small_area_run(
            store,
            {**base, "options": {**base["options"], "max_household_size": 0}},
        )
    with pytest.raises(ValueError, match="local web runs are limited"):
        _preflight_small_area_run(
            store,
            {
                **base,
                "options": {
                    **base["options"],
                    "candidate_households": LOCAL_RUN_MAX_HOUSEHOLDS + 1,
                },
            },
        )

    unsupported_controls = store_upload(
        store,
        "unsupported.csv",
        b'margin,dimensions,tract,unknown,count\nx,"tract,unknown",001,x,1\n',
    )
    with pytest.raises(ValueError, match="unsupported candidate columns: unknown"):
        _preflight_small_area_run(
            store,
            {
                **base,
                "inputs": {
                    "model_id": "demo-linked-household-person",
                    "controls_upload_id": unsupported_controls,
                },
            },
        )

    candidate_households = store_upload(
        store,
        "candidate-households.csv",
        b"synthetic_household_id,household_size,tenure\nh1,1,owner\nh2,1,renter\n",
    )
    candidate_persons = store_upload(
        store,
        "candidate-persons.csv",
        b"synthetic_person_id,synthetic_household_id,sex\np1,h1,F\np2,h2,M\n",
    )
    candidate_preflight = _preflight_small_area_run(
        store,
        {
            "workflow": "small_area",
            "inputs": {
                "candidate_households_upload_id": candidate_households,
                "candidate_persons_upload_id": candidate_persons,
                "controls_upload_id": controls,
            },
            "options": {
                "candidate_households": 999,
                "geography_dimension": "tract",
            },
        },
    )
    assert candidate_preflight["request"]["options"]["candidate_households"] == 2
    assert candidate_preflight["model_diagnostics"]["name"] == (
        "Uploaded linked candidates"
    )
    unsupported_categories = store_upload(
        store,
        "unsupported-categories.csv",
        (
            b"margin,dimensions,tract,tenure,count\n"
            b'tenure,"tract,tenure",001,cooperative,1\n'
        ),
    )
    with pytest.raises(ValueError, match="tenure: cooperative"):
        _preflight_small_area_run(
            store,
            {
                "workflow": "small_area",
                "inputs": {
                    "candidate_households_upload_id": candidate_households,
                    "candidate_persons_upload_id": candidate_persons,
                    "controls_upload_id": unsupported_categories,
                },
                "options": {
                    "candidate_households": 2,
                    "geography_dimension": "tract",
                },
            },
        )


def test_preflight_blocks_invalid_inputs_and_run_rechecks_claimed_uploads(
    tmp_path: Path,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path,
        session_secret="test-session",
    )

    async def exercise() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            seed_upload = await upload(client, "seed.csv", b"id,age\n1,young\n")
            controls_upload = await upload(
                client,
                "controls.csv",
                b"margin,dimensions,age,count\nage,age,old,1\n",
            )
            request = ipf_request(seed_upload, controls_upload)
            preflight = await client.post("/api/preflight", json=request)
            blocked = await client.post("/api/runs", json=request)

            valid_controls = await upload(
                client,
                "valid-controls.csv",
                b"margin,dimensions,age,count\nage,age,young,1\n",
            )
            valid_request = ipf_request(seed_upload, valid_controls)
            created = await client.post("/api/runs", json=valid_request)
            assert created.status_code == 202
            stale = await client.post("/api/runs", json=valid_request)
            return preflight, blocked, stale

    try:
        preflight, blocked, stale = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert preflight.status_code == 200
    assert preflight.json()["ready"] is False
    assert blocked.status_code == 400
    assert "blocking input diagnostics" in blocked.json()["error"]
    assert stale.status_code == 400
    assert "already been claimed" in stale.json()["error"]


def test_run_api_rejects_unknown_workflows_ids_and_artifacts(tmp_path: Path) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path,
        session_secret="test-session",
    )

    async def exercise() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            return [
                await client.post(
                    "/api/preflight", json={"workflow": "tree", "inputs": {}}
                ),
                await client.post(
                    "/api/preflight",
                    json={
                        "workflow": "ipf",
                        "inputs": {
                            "seed_upload_id": "0" * 32,
                            "controls_upload_id": "1" * 32,
                        },
                    },
                ),
                await client.get("/api/runs/not-a-run"),
                await client.post("/api/runs/not-a-run/cancel"),
                await client.get("/api/runs/not-a-run/artifacts/../../private.csv"),
            ]

    try:
        responses = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert [response.status_code for response in responses] == [
        400,
        400,
        404,
        404,
        404,
    ]


def test_preflight_blocks_run_when_workspace_disk_is_insufficient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path,
        session_secret="test-session",
    )

    async def exercise() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            seed_upload = await upload(client, "seed.csv", seed_csv())
            controls_upload = await upload(client, "controls.csv", controls_csv())
            monkeypatch.setattr(
                "synthpopcan.webapi.shutil.disk_usage",
                lambda _path: shutil._ntuple_diskusage(100, 100, 0),
            )
            request = ipf_request(seed_upload, controls_upload)
            return (
                await client.post("/api/preflight", json=request),
                await client.post("/api/runs", json=request),
            )

    try:
        preflight, blocked = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert preflight.status_code == 200
    assert preflight.json()["ready"] is False
    assert preflight.json()["estimate"]["enough_disk"] is False
    assert blocked.status_code == 400


def store_upload(store: RunStore, name: str, body: bytes) -> str:
    writer = store.begin_upload(name, max_bytes=len(body))
    writer.write(body)
    return str(writer.finish()["upload_id"])


async def upload(client: httpx.AsyncClient, name: str, body: bytes) -> str:
    response = await client.post(
        "/api/uploads",
        content=body,
        headers={"x-filename": name, "content-type": "text/csv"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["upload_id"])


async def wait_for_terminal(
    client: httpx.AsyncClient, run_id: str, timeout: float = 10
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(f"/api/runs/{run_id}")
        manifest = response.json()
        if manifest["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return manifest
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish")


def ipf_request(seed_upload_id: str, controls_upload_id: str) -> dict:
    return {
        "workflow": "ipf",
        "inputs": {
            "seed_upload_id": seed_upload_id,
            "controls_upload_id": controls_upload_id,
        },
        "options": {},
    }


def seed_csv() -> bytes:
    return b"id,age,sex\n1,young,F\n2,young,M\n3,old,F\n4,old,M\n"


def controls_csv() -> bytes:
    return (
        b"margin,dimensions,age,sex,count\n"
        b"age,age,young,,60\n"
        b"age,age,old,,40\n"
        b"sex,sex,,F,50\n"
        b"sex,sex,,M,50\n"
    )
