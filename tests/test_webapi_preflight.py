"""Webapi preflight behaviour and regression tests."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import httpx
import pytest
from support.webapi_fixtures import (
    controls_csv,
    ipf_request,
    seed_csv,
    upload,
)

from synthpopcan.webapi import (
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root


def test_preflight_api_does_not_expose_exception_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )
    monkeypatch.setattr(
        "synthpopcan.webapi._preflight_run",
        lambda *_: (_ for _ in ()).throw(
            ValueError("invalid file at /private/workspace/secret.csv")
        ),
    )

    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            return await client.post("/api/preflight", json={})

    try:
        response = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert response.status_code == 400
    assert response.json() == {"error": "preflight request is invalid"}
    assert "/private/workspace" not in response.text


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
    assert stale.json()["error"] == "run request is invalid"


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
