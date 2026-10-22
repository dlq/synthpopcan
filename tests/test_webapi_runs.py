"""Durable API runs, reproduction, and terminal-event delivery."""

from __future__ import annotations

import asyncio
import csv
import shlex
from io import StringIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from support.webapi_fixtures import (
    controls_csv,
    ipf_request,
    seed_csv,
    store_upload,
    upload,
    wait_for_terminal,
)

from synthpopcan.cli import main
from synthpopcan.webapi import (
    create_web_app,
)
from synthpopcan.webapp import get_webapp_root


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


def test_run_events_drain_terminal_event_after_manifest_transition(
    tmp_path: Path,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )
    store = app.state.run_store
    seed = store_upload(store, "seed.csv", seed_csv())
    controls = store_upload(store, "controls.csv", controls_csv())
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    store.transition_run(run_id, "cancelled")

    async def exercise() -> str:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")

            async def append_terminal_event() -> None:
                await asyncio.sleep(0.05)
                store.append_event(run_id, "cancelled", "Run cancelled")

            append_task = asyncio.create_task(append_terminal_event())
            events = await client.get(f"/api/runs/{run_id}/events")
            await append_task
            return events.text

    try:
        event_stream = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert '"stage":"cancelled"' in event_stream


def test_run_events_emit_terminal_event_appended_between_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_web_app(
        static_root=get_webapp_root(),
        workspace=tmp_path / "workspace",
        session_secret="test-session",
    )
    store = app.state.run_store
    seed = store_upload(store, "seed.csv", seed_csv())
    controls = store_upload(store, "controls.csv", controls_csv())
    manifest = store.create_ipf_run(ipf_request(seed, controls))
    run_id = str(manifest["run_id"])
    original_read_events = store.read_events
    injected_terminal_event = False

    def racing_read_events(
        requested_run_id: str,
        *,
        after_id: int = 0,
    ) -> list[dict[str, Any]]:
        nonlocal injected_terminal_event
        events = original_read_events(requested_run_id, after_id=after_id)
        if not injected_terminal_event:
            injected_terminal_event = True
            store.transition_run(run_id, "cancelled")
            store.append_event(run_id, "cancelled", "Run cancelled")
        return events

    monkeypatch.setattr(store, "read_events", racing_read_events)

    async def exercise() -> str:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            await client.get("/api/app")
            events = await client.get(f"/api/runs/{run_id}/events")
            return events.text

    try:
        event_stream = asyncio.run(exercise())
    finally:
        app.state.job_manager.shutdown()

    assert event_stream.count('"stage":"cancelled"') == 1


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
