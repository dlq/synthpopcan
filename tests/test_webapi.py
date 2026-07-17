from __future__ import annotations

import asyncio
import csv
import hashlib
import shlex
import shutil
import time
from io import StringIO
from pathlib import Path

import httpx
import pytest

from synthpopcan.cli import main
from synthpopcan.webapi import create_web_app
from synthpopcan.webapp import get_webapp_root


def test_ipf_api_upload_preflight_run_events_artifacts_and_reproduction(
    tmp_path: Path,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    async def exercise() -> tuple[dict, bytes, str, str]:
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
            assert preflight.json()["estimate"]["output_rows"] == 100
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
            assert artifact.status_code == 200
            assert artifact.headers["content-disposition"].endswith(
                'filename="weights.csv"'
            )
            listed = await client.get("/api/runs")
            assert listed.json()["runs"][0]["run_id"] == run_id
            return manifest, artifact.content, events.text, replay_after_end.text

    try:
        manifest, weights_bytes, event_stream, replay_after_end = asyncio.run(
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
    rendered = shlex.split(manifest["reproduction"]["shell"])
    assert rendered[0] == "synthpopcan"
    assert main(rendered[1:]) == 0


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
