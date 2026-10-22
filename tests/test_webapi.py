"""Webapi behaviour and regression tests."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest
from support.webapi_fixtures import (
    seed_csv,
)

from synthpopcan.webapi import (
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root


def test_web_app_factory_preserves_state_and_route_order(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=workspace,
        session_secret="test-session",
    )

    try:
        assert app.state.workspace == workspace.resolve()
        assert app.state.session_token
        assert app.state.run_store.root == workspace.resolve()
        assert app.state.job_manager.store is app.state.run_store
        assert [
            (
                route.path,
                tuple(sorted(getattr(route, "methods", None) or ())),
                route.name,
            )
            for route in app.routes
        ] == [
            ("/api/app", ("GET",), "app_bootstrap"),
            ("/api/models", ("GET",), "get_models"),
            ("/api/control-packs", ("GET",), "get_control_packs"),
            ("/api/uploads", ("POST",), "upload_file"),
            ("/api/preflight", ("POST",), "preflight_run"),
            ("/api/runs", ("GET",), "list_runs"),
            ("/api/runs", ("POST",), "create_run"),
            ("/api/runs/{run_id}", ("GET",), "get_run"),
            ("/api/runs/{run_id}/events", ("GET",), "get_run_events"),
            ("/api/runs/{run_id}/cancel", ("POST",), "cancel_run"),
            (
                "/api/runs/{run_id}/artifacts/{artifact_id}/preview",
                ("GET",),
                "preview_artifact",
            ),
            (
                "/api/runs/{run_id}/artifacts/{artifact_id}",
                ("GET",),
                "get_artifact",
            ),
            ("/api/models/{model_id}/fetch", ("POST",), "fetch_model"),
            ("/api/models/{model_id}/install", ("POST",), "install_model"),
            ("/api/models/{model_id}", ("DELETE",), "remove_model"),
            ("/api/models/{model_id}", ("GET",), "get_model"),
            ("/api/wds/seed-controls", ("POST",), "prepare_wds_seed_controls"),
            ("/api/small-area/estimate", ("POST",), "small_area_estimate"),
            (
                "/api/{path:path}",
                ("DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"),
                "missing_api",
            ),
            ("", (), "web"),
        ]
    finally:
        app.state.job_manager.shutdown()


@pytest.mark.parametrize(
    ("failure", "status", "message"),
    [
        (ValueError("upload is malformed"), 400, "upload is invalid"),
        (
            OSError("/private/workspace/upload.bin: disk error"),
            507,
            "upload could not be stored in the local workspace",
        ),
    ],
)
def test_upload_api_returns_safe_writer_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    status: int,
    message: str,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )

    class BrokenWriter:
        aborted = False

        def write(self, chunk: bytes) -> None:
            pass

        def finish(self) -> dict[str, object]:
            raise failure

        def abort(self) -> None:
            self.aborted = True

    writer = BrokenWriter()
    monkeypatch.setattr(
        app.state.run_store,
        "begin_upload",
        lambda *args, **kwargs: writer,
    )

    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            return await client.post(
                "/api/uploads",
                content=b"value\n1\n",
                headers={"Content-Type": "text/csv"},
            )

    try:
        response = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert response.status_code == status
    assert response.json() == {"error": message}
    assert writer.aborted is True
    assert "/private/workspace" not in response.text


def test_control_pack_catalogue_api_lists_reviewed_builtins(tmp_path: Path) -> None:
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
            return await client.get("/api/control-packs")

    try:
        response = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert response.status_code == 200
    packs = response.json()["control_packs"]
    assert len(packs) == 24
    assert {item["census_vintage"] for item in packs} == {2016, 2021}
    assert {item["geography_level"] for item in packs} == {
        "csd",
        "ct",
        "ada",
        "da",
    }
    assert all(len(item["definition_sha256"]) == 64 for item in packs)


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
