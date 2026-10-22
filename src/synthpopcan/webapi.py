"""FastAPI adapter for the packaged local SynthPopCan web application."""

from __future__ import annotations

__all__ = ["create_web_app"]

import csv
import hmac
import json
import secrets
import shutil
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import RequestResponseEndpoint

from synthpopcan._runtime_schemas import (
    RUN_REQUEST_ADAPTER,
    IPFRunRequest,
    ModelRunRequest,
    SmallAreaEstimateRequest,
    SmallAreaRunRequest,
    WDSSeedControlsRequest,
)
from synthpopcan._version import __version__
from synthpopcan.control_packs import (
    list_builtin_control_packs,
    validate_control_pack_evidence_binding,
    validate_control_pack_tables,
)
from synthpopcan.controls import parse_control_table, read_control_table
from synthpopcan.jobs import JobManager
from synthpopcan.models import (
    fetch_model_package,
    model_browser_compatible,
    model_catalogue,
    model_catalogue_entry,
    model_payload,
    remove_cached_model,
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
from synthpopcan.workflows.models import (
    LOCAL_RUN_MAX_HOUSEHOLDS,
    inspect_prepared_model,
    read_prepared_model_package,
)
from synthpopcan.workflows.preflight import (
    _csv_category_support as _csv_category_support,
)
from synthpopcan.workflows.preflight import (
    _csv_columns as _csv_columns,
)
from synthpopcan.workflows.preflight import (
    _inspection_string_list as _inspection_string_list,
)
from synthpopcan.workflows.preflight import (
    _model_category_support as _model_category_support,
)
from synthpopcan.workflows.preflight import (
    _pack_derived_dimensions as _pack_derived_dimensions,
)
from synthpopcan.workflows.preflight import (
    _read_csv_rows as _read_csv_rows,
)
from synthpopcan.workflows.preflight import (
    _unsupported_control_categories as _unsupported_control_categories,
)
from synthpopcan.workflows.preflight import (
    preflight_small_area_run,
)

_MAX_API_JSON_BYTES = 8 * 1024 * 1024
_MAX_WDS_JSON_BYTES = 64 * 1024
_MAX_UPLOAD_BYTES = 256 * 1024 * 1024
_SESSION_COOKIE = "synthpopcan_session"
_WDS_REQUEST_SLOTS = BoundedSemaphore(2)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
_TERMINAL_EVENT_GRACE_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class _WebAppContext:
    """Shared application services captured by the registered route groups."""

    workspace: Path
    session_token: str
    run_store: RunStore
    job_manager: JobManager


def create_web_app(
    *,
    static_root: Path,
    workspace: Path,
    session_secret: str | None = None,
) -> FastAPI:
    """Create the loopback-only FastAPI application."""
    secret = (session_secret or secrets.token_urlsafe(32)).encode()
    session_token = hmac.new(
        secret,
        b"synthpopcan-local-browser-session",
        "sha256",
    ).hexdigest()
    resolved_workspace = workspace.resolve()
    run_store = RunStore(resolved_workspace)
    context = _WebAppContext(
        workspace=resolved_workspace,
        session_token=session_token,
        run_store=run_store,
        job_manager=JobManager(run_store),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            context.job_manager.shutdown()

    app = FastAPI(
        title="SynthPopCan local web app",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.workspace = resolved_workspace
    app.state.session_token = session_token
    app.state.run_store = context.run_store
    app.state.job_manager = context.job_manager

    _register_security_and_bootstrap(app, context)
    _register_catalogue_routes(app)

    _register_run_routes(app, context)

    _register_model_routes(app)

    _register_data_preparation_routes(app)

    _register_fallback_and_static_routes(app, static_root)
    return app


def _register_security_and_bootstrap(
    app: FastAPI,
    context: _WebAppContext,
) -> None:
    """Register loopback/session protection and the session bootstrap route."""

    @app.middleware("http")
    async def local_security(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        hostname = request.url.hostname
        if hostname not in _LOOPBACK_HOSTS:
            return _error_response(
                "request Host must be loopback", HTTPStatus.BAD_REQUEST
            )

        if request.url.path.startswith("/api/") and request.url.path != "/api/app":
            cookie = request.cookies.get(_SESSION_COOKIE, "")
            if not hmac.compare_digest(cookie, context.session_token):
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
                "workspace": str(context.workspace),
            }
        )
        response.set_cookie(
            _SESSION_COOKIE,
            context.session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response


def _register_catalogue_routes(app: FastAPI) -> None:
    """Register the model and control-pack catalogue discovery routes."""

    @app.get("/api/models")
    async def get_models() -> Response:
        return JSONResponse({"models": model_catalogue()})

    @app.get("/api/control-packs")
    async def get_control_packs() -> Response:
        return JSONResponse({"control_packs": list_builtin_control_packs()})


def _register_run_routes(app: FastAPI, context: _WebAppContext) -> None:
    """Register uploads, preflight, durable runs, events, and artifacts."""

    run_store = context.run_store
    job_manager = context.job_manager

    @app.post("/api/uploads")
    async def upload_file(request: Request) -> Response:
        display_name = request.headers.get("x-filename", "upload.csv")
        media_type = request.headers.get("content-type", "text/csv").split(";", 1)[0]
        if media_type not in {"text/csv", "application/json"}:
            return _error_response(
                "upload Content-Type must be text/csv or application/json",
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )
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
            if shutil.disk_usage(context.workspace).free < declared_bytes * 2:
                return _error_response(
                    "insufficient workspace disk space for upload",
                    HTTPStatus.INSUFFICIENT_STORAGE,
                )
        writer = run_store.begin_upload(
            display_name,
            media_type=media_type,
            max_bytes=_MAX_UPLOAD_BYTES,
        )
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
        except ValueError:
            writer.abort()
            return _error_response("upload is invalid", HTTPStatus.BAD_REQUEST)
        except OSError:
            writer.abort()
            return _error_response(
                "upload could not be stored in the local workspace",
                HTTPStatus.INSUFFICIENT_STORAGE,
            )

    @app.post("/api/preflight")
    async def preflight_run(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            result = await run_in_threadpool(_preflight_run, run_store, payload)
            return JSONResponse(result)
        except (KeyError, TypeError, ValueError):
            return _error_response(
                "preflight request is invalid",
                HTTPStatus.BAD_REQUEST,
            )

    @app.get("/api/runs")
    async def list_runs() -> Response:
        return JSONResponse({"runs": run_store.list_runs()})

    @app.post("/api/runs")
    async def create_run(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            preflight = await run_in_threadpool(_preflight_run, run_store, payload)
            if not preflight["ready"]:
                message = (
                    "IPF preflight has blocking input diagnostics"
                    if payload.get("workflow") == "ipf"
                    else "run preflight has blocking diagnostics"
                )
                return _error_response(
                    message,
                    HTTPStatus.BAD_REQUEST,
                )
            if preflight["request"]["workflow"] == "ipf":
                manifest = run_store.create_ipf_run(preflight["request"])
            elif preflight["request"]["workflow"] == "model":
                manifest = run_store.create_model_run(preflight["request"])
            else:
                manifest = run_store.create_small_area_run(preflight["request"])
            job_manager.enqueue(str(manifest["run_id"]))
            return JSONResponse(manifest, status_code=HTTPStatus.ACCEPTED)
        except (KeyError, TypeError, ValueError):
            return _error_response("run request is invalid", HTTPStatus.BAD_REQUEST)

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> Response:
        try:
            return JSONResponse(run_store.load_run(run_id))
        except (KeyError, ValueError):
            return _error_response("run not found", HTTPStatus.NOT_FOUND)

    @app.get("/api/runs/{run_id}/events")
    async def get_run_events(run_id: str, request: Request) -> Response:
        try:
            run_store.load_run(run_id)
            last_event_id = int(request.headers.get("last-event-id", "0"))
        except (KeyError, ValueError):
            return _error_response("run not found", HTTPStatus.NOT_FOUND)

        async def stream_events() -> AsyncIterator[str]:
            cursor = last_event_id
            terminal_observed_at: float | None = None
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
                import asyncio

                terminal_status = str(manifest["status"])
                if terminal_status in _TERMINAL_RUN_STATUSES:
                    persisted_events = run_store.read_events(run_id)
                    terminal_event_ids = [
                        int(event["id"])
                        for event in persisted_events
                        if event["stage"] == terminal_status
                    ]
                    if terminal_event_ids and cursor >= max(terminal_event_ids):
                        return
                    loop_time = asyncio.get_running_loop().time()
                    if terminal_observed_at is None:
                        terminal_observed_at = loop_time
                    elif (
                        loop_time - terminal_observed_at
                        >= _TERMINAL_EVENT_GRACE_SECONDS
                    ):
                        return
                await asyncio.sleep(0.1)

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> Response:
        try:
            run_store.load_run(run_id)
        except (KeyError, ValueError):
            return _error_response("run not found", HTTPStatus.NOT_FOUND)
        try:
            return JSONResponse(job_manager.cancel(run_id))
        except ValueError:
            return _error_response(
                "run cannot be cancelled in its current state",
                HTTPStatus.CONFLICT,
            )

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
        except KeyError:
            return _error_response("artifact not found", HTTPStatus.NOT_FOUND)
        except ValueError:
            return _error_response(
                "artifact preview request is invalid",
                HTTPStatus.BAD_REQUEST,
            )

    @app.get("/api/runs/{run_id}/artifacts/{artifact_id}")
    async def get_artifact(run_id: str, artifact_id: str) -> Response:
        try:
            path, artifact = run_store.artifact_path(run_id, artifact_id)
            return FileResponse(
                path,
                media_type=str(artifact["media_type"]),
                filename=str(artifact["filename"]),
            )
        except (KeyError, ValueError):
            return _error_response("artifact not found", HTTPStatus.NOT_FOUND)


def _register_model_routes(app: FastAPI) -> None:
    """Register model installation, removal, fetch, and payload routes."""

    @app.post("/api/models/{model_id}/fetch")
    async def fetch_model(model_id: str) -> Response:
        try:
            _require_browser_compatible_model(model_id)
            await run_in_threadpool(fetch_model_package, model_id)
            return JSONResponse({"model": model_payload(model_id)})
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)
        except OverflowError:
            return _error_response(
                "model package is above the browser memory limit; run "
                f"synthpopcan models generate {model_id}",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except OSError:
            return _error_response("model download failed", HTTPStatus.BAD_GATEWAY)
        except ValueError:
            return _error_response(
                "model package failed validation",
                HTTPStatus.BAD_GATEWAY,
            )

    @app.post("/api/models/{model_id}/install")
    async def install_model(model_id: str) -> Response:
        """Install a catalogue model without loading its payload in the browser."""

        try:
            await run_in_threadpool(fetch_model_package, model_id)
            return JSONResponse({"model": model_catalogue_entry(model_id)})
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)
        except (OSError, TimeoutError):
            return _error_response("model download failed", HTTPStatus.BAD_GATEWAY)
        except ValueError:
            return _error_response(
                "model package failed validation",
                HTTPStatus.BAD_GATEWAY,
            )

    @app.delete("/api/models/{model_id}")
    async def remove_model(model_id: str) -> Response:
        """Remove a downloaded catalogue model from the local cache."""

        try:
            model_catalogue_entry(model_id)
            removed = await run_in_threadpool(remove_cached_model, model_id)
            return JSONResponse(
                {"removed": removed, "model": model_catalogue_entry(model_id)}
            )
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)

    @app.get("/api/models/{model_id}")
    async def get_model(model_id: str) -> Response:
        try:
            _require_browser_compatible_model(model_id)
            return JSONResponse(model_payload(model_id))
        except KeyError:
            return _error_response("Unknown model", HTTPStatus.NOT_FOUND)
        except OverflowError:
            return _error_response(
                "model package is above the browser memory limit; run "
                f"synthpopcan models generate {model_id}",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        except FileNotFoundError:
            return _error_response(
                "model package is not installed; run "
                f"synthpopcan models fetch {model_id}",
                HTTPStatus.CONFLICT,
            )


def _register_data_preparation_routes(app: FastAPI) -> None:
    """Register bounded WDS preparation and small-area estimation routes."""

    @app.post("/api/wds/seed-controls")
    async def prepare_wds_seed_controls(request: Request) -> Response:
        if not _WDS_REQUEST_SLOTS.acquire(blocking=False):
            return _error_response(
                "too many WDS preparation requests are already running",
                HTTPStatus.TOO_MANY_REQUESTS,
            )
        try:
            payload = await _read_json_body(request, max_bytes=_MAX_WDS_JSON_BYTES)
            request_data = WDSSeedControlsRequest.model_validate(payload)
            product_id = normalize_product_id(request_data.product_id)
            zip_bytes, download_url = await run_in_threadpool(
                fetch_wds_zip_bytes, product_id
            )
            generated = await run_in_threadpool(
                generate_wds_seed_controls_from_zip_bytes,
                zip_bytes,
                dimensions=parse_dimensions(request_data.dimensions),
                count_column=request_data.count_column or "VALUE",
            )
            return JSONResponse(
                {
                    "productId": product_id,
                    "downloadUrl": download_url,
                    **generated,
                }
            )
        except (KeyError, TypeError, ValueError):
            return _error_response("WDS request is invalid", HTTPStatus.BAD_REQUEST)
        except Exception:  # noqa: BLE001
            return _error_response(
                "WDS preparation failed; check the product ID and dimensions",
                HTTPStatus.BAD_REQUEST,
            )
        finally:
            _WDS_REQUEST_SLOTS.release()

    @app.post("/api/small-area/estimate")
    async def small_area_estimate(request: Request) -> Response:
        try:
            payload = await _read_json_body(request)
            request_data = SmallAreaEstimateRequest.model_validate(payload)
            controls = parse_control_table(request_data.controls_csv)
            if not controls.margins:
                raise ValueError("controls CSV has no control rows")
            geography_dimension = request_data.geography_dimension.strip()
            if not geography_dimension:
                raise ValueError("geography dimension is required")
            estimate = await run_in_threadpool(
                estimate_small_area_run,
                controls,
                geography_dimension=geography_dimension,
                candidate_households=request_data.candidate_households,
                pool_size=request_data.pool_size,
                average_persons_per_household=(
                    request_data.average_persons_per_household
                ),
            )
            return JSONResponse(
                {
                    "estimate": estimate,
                    "controlDimensions": list(controls.dimensions),
                }
            )
        except (TypeError, ValueError):
            return _error_response(
                "small-area estimate request is invalid",
                HTTPStatus.BAD_REQUEST,
            )


def _register_fallback_and_static_routes(app: FastAPI, static_root: Path) -> None:
    """Register the API fallback before the final static application mount."""

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def missing_api(path: str) -> Response:
        return _error_response("API endpoint not found", HTTPStatus.NOT_FOUND)

    app.mount("/", StaticFiles(directory=static_root, html=True), name="web")


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


def _validate_control_pack_tables(pack, household_controls, person_controls):
    return validate_control_pack_tables(pack, household_controls, person_controls)


def _validate_control_pack_evidence_binding(
    pack, evidence, household_controls, person_controls, geographies
):
    return validate_control_pack_evidence_binding(
        pack, evidence, household_controls, person_controls, geographies
    )


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


def _preflight_ipf_run(
    store: RunStore,
    payload: dict[str, Any] | IPFRunRequest,
) -> dict[str, Any]:
    if isinstance(payload, dict):
        if payload.get("workflow") != "ipf":
            raise ValueError("only workflow 'ipf' is supported")
        if not isinstance(payload.get("inputs"), dict):
            raise ValueError("IPF inputs must be an object")
        if not isinstance(payload.get("options", {}), dict):
            raise ValueError("IPF options must be an object")
    request_data = (
        payload
        if isinstance(payload, IPFRunRequest)
        else IPFRunRequest.model_validate(payload)
    )
    payload = request_data.model_dump()
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
    population_total = round(max(margin_totals, default=0))
    compact_output_rows = int(diagnostics["seed_records"])
    estimated_output_bytes = max(
        4096,
        seed_path.stat().st_size + compact_output_rows * 32,
    )
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
            "compact_output_rows": compact_output_rows,
            "population_total": population_total,
            "output_bytes": estimated_output_bytes,
            "disk_free_bytes": disk_free,
            "enough_disk": enough_disk,
        },
        "expected_artifacts": ["weights", "fit_report"],
    }


def _preflight_run(store: RunStore, payload: dict[str, Any]) -> dict[str, Any]:
    request_data = RUN_REQUEST_ADAPTER.validate_python(payload)
    if isinstance(request_data, IPFRunRequest):
        return _preflight_ipf_run(store, request_data)
    if isinstance(request_data, ModelRunRequest):
        return _preflight_model_run(store, request_data)
    return _preflight_small_area_run(store, request_data)


def _preflight_model_run(
    store: RunStore,
    payload: dict[str, Any] | ModelRunRequest,
) -> dict[str, Any]:
    if isinstance(payload, dict):
        if not isinstance(payload.get("inputs"), dict):
            raise ValueError("model inputs must be an object")
        raw_options = payload.get("options", {})
        if not isinstance(raw_options, dict):
            raise ValueError("model options must be an object")
        if not isinstance(raw_options.get("conditions", {}), dict):
            raise ValueError("model conditions must be an object")
    request_data = (
        payload
        if isinstance(payload, ModelRunRequest)
        else ModelRunRequest.model_validate(payload)
    )
    payload = request_data.model_dump()
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("model inputs must be an object")
    model_id = inputs.get("model_id")
    package_upload_id = inputs.get("package_upload_id")
    if bool(model_id) == bool(package_upload_id):
        raise ValueError("provide exactly one model_id or package_upload_id")
    if model_id:
        package = model_payload(str(model_id))
        normalized_inputs = {"model_id": str(model_id)}
    else:
        package_path = store.upload_path(str(package_upload_id), require_unclaimed=True)
        package = read_prepared_model_package(package_path)
        normalized_inputs = {"package_upload_id": str(package_upload_id)}
    inspection = inspect_prepared_model(package)
    options = payload.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("model options must be an object")
    households = int(options.get("households", 10))
    if households <= 0:
        raise ValueError("households must be positive")
    if households > LOCAL_RUN_MAX_HOUSEHOLDS:
        raise ValueError(
            f"local web runs are limited to {LOCAL_RUN_MAX_HOUSEHOLDS:,} households; "
            "use the CLI for a reviewed larger run"
        )
    chunk_size = int(options.get("chunk_size", 1000))
    if chunk_size <= 0:
        raise ValueError("chunk size must be positive")
    conditions_payload = options.get("conditions", {})
    if not isinstance(conditions_payload, dict):
        raise ValueError("model conditions must be an object")
    conditions = {
        str(key).strip(): str(value)
        for key, value in conditions_payload.items()
        if str(key).strip()
    }
    unsupported = sorted(set(conditions) - set(inspection["conditions"]))
    if unsupported:
        raise ValueError(
            "unsupported model condition columns: " + ", ".join(unsupported)
        )
    # Reserve a conservative amount per requested household without pretending
    # to know the package's generated household-size distribution in advance.
    estimated_output_bytes = max(8192, households * 4096)
    disk_free = shutil.disk_usage(store.root).free
    enough_disk = disk_free >= estimated_output_bytes * 2
    normalized_request = {
        "workflow": "model",
        "inputs": normalized_inputs,
        "options": {
            "households": households,
            "conditions": conditions,
            "random_seed": _optional_int(options.get("random_seed")),
            "household_size_column": options.get("household_size_column"),
            "chunk_size": chunk_size,
        },
    }
    return {
        "ready": enough_disk,
        "request": normalized_request,
        "model_diagnostics": inspection,
        "estimate": {
            "households": households,
            "output_bytes": estimated_output_bytes,
            "storage_basis": "4 KiB per requested household",
            "disk_free_bytes": disk_free,
            "enough_disk": enough_disk,
        },
        "expected_artifacts": ["households", "persons", "generation_report"],
    }


def _preflight_small_area_run(
    store: RunStore,
    payload: dict[str, Any] | SmallAreaRunRequest,
) -> dict[str, Any]:
    if isinstance(payload, dict):
        if not isinstance(payload.get("inputs"), dict):
            raise ValueError("small-area inputs must be an object")
        raw_options = payload.get("options", {})
        if not isinstance(raw_options, dict):
            raise ValueError("small-area options must be an object")
        if not isinstance(raw_options.get("conditions", {}), dict):
            raise ValueError("model conditions must be an object")
        geography_payload = raw_options.get("geography_universe")
        if geography_payload is not None and not isinstance(geography_payload, dict):
            raise ValueError("geography_universe must be an object")
    request_data = (
        payload
        if isinstance(payload, SmallAreaRunRequest)
        else SmallAreaRunRequest.model_validate(payload)
    )
    return preflight_small_area_run(store, request_data).as_dict()
