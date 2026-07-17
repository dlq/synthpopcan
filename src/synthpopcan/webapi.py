"""FastAPI adapter for the packaged local SynthPopCan web application."""

from __future__ import annotations

__all__ = ["create_web_app"]

import csv
import hmac
import json
import secrets
import shutil
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from synthpopcan import __version__
from synthpopcan.controls import parse_control_table, read_control_table
from synthpopcan.jobs import JobManager
from synthpopcan.models import (
    fetch_model_package,
    model_browser_compatible,
    model_catalogue,
    model_catalogue_entry,
    model_payload,
)
from synthpopcan.runs import RunStore
from synthpopcan.small_area_synthesis import estimate_small_area_run
from synthpopcan.statcan import normalize_product_id
from synthpopcan.web_wds import (
    fetch_wds_zip_bytes,
    generate_wds_seed_controls_from_zip_bytes,
    parse_dimensions,
)
from synthpopcan.workflows.ipf import check_ipf_inputs

_MAX_API_JSON_BYTES = 8 * 1024 * 1024
_MAX_WDS_JSON_BYTES = 64 * 1024
_MAX_UPLOAD_BYTES = 256 * 1024 * 1024
_SESSION_COOKIE = "synthpopcan_session"
_WDS_REQUEST_SLOTS = BoundedSemaphore(2)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def create_web_app(
    *,
    static_root: Path,
    workspace: Path,
    session_secret: str | None = None,
) -> FastAPI:
    """Create the loopback-only FastAPI application."""
    secret = session_secret or secrets.token_urlsafe(32)
    resolved_workspace = workspace.resolve()
    run_store = RunStore(resolved_workspace)
    job_manager = JobManager(run_store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            job_manager.shutdown()

    app = FastAPI(
        title="SynthPopCan local web app",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.workspace = resolved_workspace
    app.state.session_secret = secret
    app.state.run_store = run_store
    app.state.job_manager = job_manager

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        hostname = request.url.hostname
        if hostname not in _LOOPBACK_HOSTS:
            return _error_response(
                "request Host must be loopback", HTTPStatus.BAD_REQUEST
            )

        if request.url.path.startswith("/api/") and request.url.path != "/api/app":
            cookie = request.cookies.get(_SESSION_COOKIE, "")
            if not hmac.compare_digest(cookie, app.state.session_secret):
                return _error_response(
                    "local app session is missing or invalid", HTTPStatus.FORBIDDEN
                )
            origin_error = _origin_error(request)
            if origin_error is not None:
                return _error_response(origin_error, HTTPStatus.FORBIDDEN)

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/app")
    async def app_bootstrap() -> Response:
        response = JSONResponse(
            {
                "name": "SynthPopCan",
                "version": __version__,
                "workspace": str(app.state.workspace),
            }
        )
        response.set_cookie(
            _SESSION_COOKIE,
            app.state.session_secret,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @app.get("/api/models")
    async def get_models() -> Response:
        return JSONResponse({"models": model_catalogue()})

    @app.post("/api/uploads")
    async def upload_file(request: Request) -> Response:
        display_name = request.headers.get("x-filename", "upload.csv")
        declared_length = request.headers.get("content-length")
        if declared_length is not None:
            try:
                declared_bytes = int(declared_length)
            except ValueError:
                return _error_response(
                    "Content-Length must be an integer", HTTPStatus.BAD_REQUEST
                )
            if declared_bytes <= 0 or declared_bytes > _MAX_UPLOAD_BYTES:
                return _error_response(
                    f"upload must be between 1 and {_MAX_UPLOAD_BYTES} bytes",
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
            if shutil.disk_usage(app.state.workspace).free < declared_bytes * 2:
                return _error_response(
                    "insufficient workspace disk space for upload",
                    HTTPStatus.INSUFFICIENT_STORAGE,
                )
        writer = run_store.begin_upload(display_name, max_bytes=_MAX_UPLOAD_BYTES)
        try:
            async for chunk in request.stream():
                writer.write(chunk)
            metadata = writer.finish()
            return JSONResponse(
                {
                    "upload_id": metadata["upload_id"],
                    "display_name": metadata["display_name"],
                    "byte_size": metadata["byte_size"],
                    "sha256": metadata["sha256"],
                },
                status_code=HTTPStatus.CREATED,
            )
        except ValueError as exc:
            writer.abort()
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            writer.abort()
            return _error_response(str(exc), HTTPStatus.INSUFFICIENT_STORAGE)

    @app.post("/api/preflight")
    async def preflight_run(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            result = await run_in_threadpool(_preflight_ipf_run, run_store, payload)
            return JSONResponse(result)
        except (KeyError, TypeError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)

    @app.get("/api/runs")
    async def list_runs() -> Response:
        return JSONResponse({"runs": run_store.list_runs()})

    @app.post("/api/runs")
    async def create_run(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            preflight = await run_in_threadpool(_preflight_ipf_run, run_store, payload)
            if not preflight["ready"]:
                return _error_response(
                    "IPF preflight has blocking input diagnostics",
                    HTTPStatus.BAD_REQUEST,
                )
            manifest = run_store.create_ipf_run(preflight["request"])
            job_manager.enqueue(str(manifest["run_id"]))
            return JSONResponse(manifest, status_code=HTTPStatus.ACCEPTED)
        except (KeyError, TypeError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> Response:
        try:
            return JSONResponse(run_store.load_run(run_id))
        except (KeyError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.NOT_FOUND)

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str, request: Request) -> Response:
        try:
            run_store.load_run(run_id)
            last_event_id = int(request.headers.get("last-event-id", "0"))
        except (KeyError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.NOT_FOUND)

        async def stream_events():
            cursor = last_event_id
            while True:
                events = run_store.read_events(run_id, after_id=cursor)
                for event in events:
                    cursor = int(event["id"])
                    yield (
                        f"id: {cursor}\n"
                        "event: progress\n"
                        f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
                    )
                manifest = run_store.load_run(run_id)
                if manifest["status"] in {
                    "succeeded",
                    "failed",
                    "cancelled",
                    "interrupted",
                }:
                    return
                import asyncio

                await asyncio.sleep(0.1)

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> Response:
        try:
            run_store.load_run(run_id)
        except (KeyError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.NOT_FOUND)
        try:
            return JSONResponse(job_manager.cancel(run_id))
        except ValueError as exc:
            return _error_response(str(exc), HTTPStatus.CONFLICT)

    @app.get("/api/runs/{run_id}/artifacts/{artifact_id}/preview")
    async def preview_artifact(
        run_id: str, artifact_id: str, rows: int = 10
    ) -> Response:
        try:
            if rows < 1 or rows > 25:
                raise ValueError("preview rows must be between 1 and 25")
            path, artifact = run_store.artifact_path(run_id, artifact_id)
            if artifact["media_type"] != "text/csv":
                raise ValueError("only CSV artifacts can be previewed")
            preview = await run_in_threadpool(_read_csv_preview, path, rows)
            return JSONResponse(preview)
        except KeyError as exc:
            return _error_response(str(exc), HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)

    @app.get("/api/runs/{run_id}/artifacts/{artifact_id}")
    async def get_artifact(run_id: str, artifact_id: str) -> Response:
        try:
            path, artifact = run_store.artifact_path(run_id, artifact_id)
            return FileResponse(
                path,
                media_type=str(artifact["media_type"]),
                filename=str(artifact["filename"]),
            )
        except (KeyError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.NOT_FOUND)

    @app.post("/api/models/{model_id}/fetch")
    async def fetch_model(model_id: str) -> Response:
        try:
            _require_browser_compatible_model(model_id)
            await run_in_threadpool(fetch_model_package, model_id)
            return JSONResponse({"model": model_payload(model_id)})
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)
        except OverflowError as exc:
            return _error_response(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except (OSError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_GATEWAY)

    @app.get("/api/models/{model_id}")
    async def get_model(model_id: str) -> Response:
        try:
            _require_browser_compatible_model(model_id)
            return JSONResponse(model_payload(model_id))
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)
        except OverflowError as exc:
            return _error_response(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except FileNotFoundError as exc:
            return _error_response(str(exc), HTTPStatus.CONFLICT)

    @app.post("/api/wds/seed-controls")
    async def prepare_wds_seed_controls(request: Request) -> Response:
        if not _WDS_REQUEST_SLOTS.acquire(blocking=False):
            return _error_response(
                "too many WDS preparation requests are already running",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
        try:
            payload = await _read_json_body(request, max_bytes=_MAX_WDS_JSON_BYTES)
            product_id = normalize_product_id(str(payload.get("productId", "")))
            zip_bytes, download_url = await run_in_threadpool(
                fetch_wds_zip_bytes, product_id
            )
            generated = await run_in_threadpool(
                generate_wds_seed_controls_from_zip_bytes,
                zip_bytes,
                dimensions=parse_dimensions(payload.get("dimensions", [])),
                count_column=str(payload.get("countColumn") or "VALUE"),
            )
            return JSONResponse(
                {
                    "productId": product_id,
                    "downloadUrl": download_url,
                    **generated,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)
        finally:
            _WDS_REQUEST_SLOTS.release()

    @app.post("/api/small-area/estimate")
    async def small_area_estimate(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            controls = parse_control_table(str(payload.get("controlsCsv", "")))
            if not controls.margins:
                raise ValueError("controls CSV has no control rows")
            geography_dimension = str(payload.get("geographyDimension", "")).strip()
            if not geography_dimension:
                raise ValueError("geography dimension is required")
            estimate = await run_in_threadpool(
                estimate_small_area_run,
                controls,
                geography_dimension=geography_dimension,
                candidate_households=int(payload.get("candidateHouseholds", 0)),
                pool_size=_optional_int(payload.get("poolSize")),
                average_persons_per_household=float(
                    payload.get("averagePersonsPerHousehold", 2.22)
                ),
            )
            return JSONResponse(
                {
                    "estimate": estimate,
                    "controlDimensions": list(controls.dimensions),
                }
            )
        except (TypeError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def missing_api(path: str) -> Response:
        return _error_response("API endpoint not found", HTTPStatus.NOT_FOUND)

    app.mount("/", StaticFiles(directory=static_root, html=True), name="web")
    return app


async def _read_json_body(
    request: Request, *, max_bytes: int = _MAX_API_JSON_BYTES
) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if content_type and content_type.split(";", 1)[0].strip() != "application/json":
        raise ValueError("Content-Type must be application/json")
    declared_length = request.headers.get("content-length")
    if declared_length is not None and int(declared_length) > max_bytes:
        raise ValueError("request body exceeds the local API size limit")
    body = await request.body()
    if len(body) > max_bytes:
        raise ValueError("request body exceeds the local API size limit")
    payload = json.loads(body or b"{}")
    if not isinstance(payload, dict):
        raise ValueError("JSON request body must be an object")
    return payload


def _origin_error(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin is None:
        return None
    parsed = urlsplit(origin)
    request_port = request.url.port or 80
    origin_port = parsed.port or (80 if parsed.scheme == "http" else None)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.hostname != request.url.hostname
        or origin_port != request_port
    ):
        return "request Origin must match the local app"
    return None


def _error_response(message: str, status: HTTPStatus) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=int(status))


def _optional_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)  # type: ignore[arg-type]


def _read_csv_preview(path: Path, rows: int) -> dict[str, Any]:
    """Read at most a small fixed number of CSV records for the browser."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV artifact has no header row")
        preview_rows = []
        for row in reader:
            preview_rows.append(dict(row))
            if len(preview_rows) >= rows:
                break
    return {"columns": reader.fieldnames, "rows": preview_rows, "limit": rows}


def _require_browser_compatible_model(model_id: str) -> None:
    if model_browser_compatible(model_id):
        return
    entry = model_catalogue_entry(model_id)
    size = entry.get("uncompressed_size_bytes")
    limit = entry["browser_max_uncompressed_size_bytes"]
    raise OverflowError(
        f"model package {model_id} expands to {size} bytes, above the "
        f"{limit}-byte browser limit; use `synthpopcan models generate "
        f"{model_id} ...` from the CLI"
    )


def _preflight_ipf_run(store: RunStore, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("workflow") != "ipf":
        raise ValueError("only workflow 'ipf' is supported")
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("IPF inputs must be an object")
    seed_upload_id = str(inputs.get("seed_upload_id", ""))
    controls_upload_id = str(inputs.get("controls_upload_id", ""))
    seed_path = store.upload_path(seed_upload_id, require_unclaimed=True)
    controls_path = store.upload_path(controls_upload_id, require_unclaimed=True)
    diagnostics = check_ipf_inputs(seed_path, controls_path)
    controls = read_control_table(controls_path)
    margin_totals = [
        sum(cell.count for cell in margin.cells) for margin in controls.margins
    ]
    estimated_rows = round(max(margin_totals, default=0))
    estimated_output_bytes = max(4096, estimated_rows * 128)
    disk_free = shutil.disk_usage(store.root).free
    options_payload = payload.get("options", {})
    if not isinstance(options_payload, dict):
        raise ValueError("IPF options must be an object")
    max_iterations = int(options_payload.get("max_iterations", 100))
    tolerance = float(options_payload.get("tolerance", 1e-6))
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    normalized_request = {
        "workflow": "ipf",
        "inputs": {
            "seed_upload_id": seed_upload_id,
            "controls_upload_id": controls_upload_id,
        },
        "options": {
            "weight_column": options_payload.get("weight_column"),
            "max_iterations": max_iterations,
            "tolerance": tolerance,
            "allow_nonconverged": bool(
                options_payload.get("allow_nonconverged", False)
            ),
        },
    }
    enough_disk = disk_free >= estimated_output_bytes * 2
    return {
        "ready": bool(diagnostics["passed"]) and enough_disk,
        "request": normalized_request,
        "input_diagnostics": diagnostics,
        "estimate": {
            "output_rows": estimated_rows,
            "output_bytes": estimated_output_bytes,
            "disk_free_bytes": disk_free,
            "enough_disk": enough_disk,
        },
        "expected_artifacts": ["weights", "fit_report"],
    }
