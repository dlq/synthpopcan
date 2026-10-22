"""Webapi models behaviour and regression tests."""

from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path

import httpx
import pytest
from support.webapi_fixtures import (
    wait_for_terminal,
)

from synthpopcan.cli import main
from synthpopcan.models import model_payload
from synthpopcan.runs import RunStore
from synthpopcan.webapi import (
    _model_category_support,
    _preflight_model_run,
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root
from synthpopcan.workflows.models import LOCAL_RUN_MAX_HOUSEHOLDS


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
    assert response.json()["error"] == "preflight request is invalid"


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


@pytest.mark.parametrize(
    "options,reason",
    [
        pytest.param({"households": "10"}, "households", id="textual-household-count"),
        pytest.param(
            {"households": 10, "househodls": 10},
            "extra_forbidden",
            id="misspelled-option",
        ),
    ],
)
def test_model_preflight_strictly_validates_request_fields(
    tmp_path: Path, options, reason
):
    with pytest.raises(ValueError, match=reason):
        _preflight_model_run(
            RunStore(tmp_path),
            {
                "workflow": "model",
                "inputs": {"model_id": "demo-linked-household-person"},
                "options": options,
            },
        )
