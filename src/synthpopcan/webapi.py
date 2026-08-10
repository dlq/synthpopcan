"""FastAPI adapter for the packaged local SynthPopCan web application."""

from __future__ import annotations

__all__ = ["create_web_app"]

import csv
import hmac
import json
import secrets
import shutil
from collections import Counter
from collections.abc import AsyncGenerator, AsyncIterator
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
from starlette.middleware.base import RequestResponseEndpoint

from synthpopcan import __version__
from synthpopcan._runtime_schemas import (
    RUN_REQUEST_ADAPTER,
    IPFRunRequest,
    ModelRunRequest,
    SmallAreaEstimateRequest,
    SmallAreaRunRequest,
    WDSSeedControlsRequest,
)
from synthpopcan.control_packs import (
    ControlPackEvidence,
    ControlPackManifest,
    control_table_sha256,
    list_builtin_control_packs,
    load_compatibility_registry,
    load_control_pack,
    load_control_pack_evidence,
    plan_control_pack,
    validate_control_pack_compatibility,
)
from synthpopcan.controls import ControlTable, parse_control_table, read_control_table
from synthpopcan.geography import GeographyUniverse, statcan_geography_universe
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
from synthpopcan.tree import validate_linked_population_files
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
    secret = (session_secret or secrets.token_urlsafe(32)).encode()
    session_token = hmac.new(
        secret,
        b"synthpopcan-local-browser-session",
        "sha256",
    ).hexdigest()
    resolved_workspace = workspace.resolve()
    run_store = RunStore(resolved_workspace)
    job_manager = JobManager(run_store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
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
    app.state.session_token = session_token
    app.state.run_store = run_store
    app.state.job_manager = job_manager

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
            if not hmac.compare_digest(cookie, app.state.session_token):
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
            app.state.session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @app.get("/api/models")
    async def get_models() -> Response:
        return JSONResponse({"models": model_catalogue()})

    @app.get("/api/control-packs")
    async def get_control_packs() -> Response:
        return JSONResponse({"control_packs": list_builtin_control_packs()})

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
            if shutil.disk_usage(app.state.workspace).free < declared_bytes * 2:
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
        except ValueError as exc:
            writer.abort()
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)
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
        except (KeyError, TypeError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)

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

        async def stream_events() -> AsyncIterator[str]:
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
        except OSError:
            return _error_response("model download failed", HTTPStatus.BAD_GATEWAY)
        except ValueError as exc:
            return _error_response(str(exc), HTTPStatus.BAD_GATEWAY)

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
        except ValueError as exc:
            return _error_response(str(exc), HTTPStatus.BAD_GATEWAY)

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
        except OverflowError as exc:
            return _error_response(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except FileNotFoundError:
            return _error_response(
                "model package is not installed; run "
                f"synthpopcan models fetch {model_id}",
                HTTPStatus.CONFLICT,
            )

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
        except (KeyError, TypeError, ValueError) as exc:
            return _error_response(str(exc), HTTPStatus.BAD_REQUEST)
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


def _csv_columns(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames
    if fieldnames is None:
        raise ValueError("CSV input has no header row")
    return list(fieldnames)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV input has no header row")
        return [dict(row) for row in reader]


def _pack_derived_dimensions(
    pack: ControlPackManifest,
    entity_level: str,
) -> set[str]:
    registry = load_compatibility_registry()
    controls = {control.identifier: control for control in registry.controls}
    return {
        derivation.output_field
        for margin in pack.margins
        if margin.entity_level == entity_level
        for derivation in controls[margin.control_identifier].candidate_derivations
        if derivation.output_field != derivation.source_field
    }


def _validate_control_pack_tables(
    pack: ControlPackManifest,
    household_controls: ControlTable,
    person_controls: ControlTable,
) -> set[str]:
    registry = load_compatibility_registry()
    definitions = {control.identifier: control for control in registry.controls}
    tables = {"household": household_controls, "person": person_controls}
    geography_sets: dict[str, set[str]] = {}
    totals: dict[str, dict[str, float]] = {}
    for entity_level, table in tables.items():
        required = [
            margin for margin in pack.margins if margin.entity_level == entity_level
        ]
        expected_dimensions = sorted(tuple(margin.dimensions) for margin in required)
        actual_dimensions = sorted(tuple(margin.dimensions) for margin in table.margins)
        if actual_dimensions != expected_dimensions:
            raise ValueError(
                f"{entity_level} controls do not match the selected control pack "
                "margin structure"
            )
        for pack_margin in required:
            definition = definitions[pack_margin.control_identifier]
            expected_cells: set[tuple[str, ...]] = {()}
            for axis in definition.source_axes:
                expected_cells = {
                    (*prefix, category.target_category)
                    for prefix in expected_cells
                    for category in axis.categories
                }
            margin = next(
                item
                for item in table.margins
                if item.dimensions == tuple(pack_margin.dimensions)
            )
            seen: Counter[tuple[str, ...]] = Counter()
            actual_by_geography: dict[str, set[tuple[str, ...]]] = {}
            for cell in margin.cells:
                geography = cell.categories.get(pack.geography_column, "")
                categories = tuple(
                    cell.categories.get(dimension, "")
                    for dimension in pack_margin.dimensions[1:]
                )
                seen[(geography, *categories)] += 1
                actual_by_geography.setdefault(geography, set()).add(categories)
                totals.setdefault(pack_margin.control_identifier, {}).setdefault(
                    geography, 0.0
                )
                totals[pack_margin.control_identifier][geography] += cell.count
            if any(count > 1 for count in seen.values()):
                raise ValueError(
                    f"control {pack_margin.control_identifier!r} contains duplicate "
                    "geography/category cells"
                )
            if "" in actual_by_geography:
                raise ValueError(
                    f"control {pack_margin.control_identifier!r} has an empty "
                    "geography identifier"
                )
            for geography, actual_cells in actual_by_geography.items():
                if actual_cells != expected_cells:
                    raise ValueError(
                        f"control {pack_margin.control_identifier!r} geography "
                        f"{geography!r} does not contain its complete category vector"
                    )
            geography_sets[pack_margin.control_identifier] = set(actual_by_geography)
    if not geography_sets:
        raise ValueError("control pack inputs contain no target geographies")
    first_geographies = next(iter(geography_sets.values()))
    if any(geographies != first_geographies for geographies in geography_sets.values()):
        raise ValueError(
            "every required control-pack margin must cover the same geographies"
        )
    household_margin_ids = [
        margin.control_identifier
        for margin in pack.margins
        if margin.entity_level == "household"
    ]
    for geography in sorted(first_geographies):
        household_totals = [
            totals[identifier][geography] for identifier in household_margin_ids
        ]
        if max(household_totals) != min(household_totals):
            raise ValueError(
                f"household control totals for geography {geography!r} must "
                "reconcile exactly before calibration"
            )
    return first_geographies


def _validate_control_pack_evidence_binding(
    pack: ControlPackManifest,
    evidence: ControlPackEvidence,
    household_controls: ControlTable,
    person_controls: ControlTable,
    geographies: set[str],
) -> None:
    comparisons = (
        ("pack identifier", pack.identifier, evidence.pack_identifier),
        (
            "pack checksum",
            pack.definition_sha256,
            evidence.pack_definition_sha256,
        ),
        ("Census vintage", pack.census_vintage, evidence.census_vintage),
        ("geography level", pack.geography_level, evidence.geography_level),
        (
            "identifier namespace",
            pack.identifier_namespace,
            evidence.identifier_namespace,
        ),
        (
            "source revisions",
            list(pack.source_revisions),
            list(evidence.controls_source_revisions),
        ),
        (
            "household controls checksum",
            control_table_sha256(household_controls),
            evidence.household_controls_sha256,
        ),
        (
            "person controls checksum",
            control_table_sha256(person_controls),
            evidence.person_controls_sha256,
        ),
        ("eligible geography set", geographies, set(evidence.geographies)),
    )
    for label, expected, actual in comparisons:
        if expected != actual:
            raise ValueError(
                f"control-pack evidence {label} does not match the selected "
                "pack or normalized controls"
            )
    person_totals: dict[str, float] = {}
    for margin in person_controls.margins:
        for cell in margin.cells:
            geography = cell.categories[pack.geography_column]
            person_totals[geography] = person_totals.get(geography, 0.0) + cell.count
    for geography, universe in evidence.geographies.items():
        total = float(universe.total_population)
        private = float(universe.persons_in_private_households)
        if total != private:
            raise ValueError(
                f"control-pack geography {geography!r} has non-zero collective "
                "population"
            )
        if private != person_totals.get(geography):
            raise ValueError(
                f"control-pack geography {geography!r} person-control total does "
                "not match its private-household universe evidence"
            )


def _inspection_string_list(
    inspection: dict[str, Any],
    key: str,
) -> list[str]:
    value = inspection.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"model inspection {key} must be a list of strings")
    return value


def _csv_category_support(path: Path, dimensions: set[str]) -> dict[str, set[str]]:
    support = {dimension: set() for dimension in dimensions}
    if not dimensions:
        return support
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = dimensions - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                "candidate CSV is missing columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            for dimension in dimensions:
                support[dimension].add(str(row[dimension]))
    return support


def _model_category_support(
    package: dict[str, Any], level: str, dimensions: set[str]
) -> dict[str, set[str]]:
    support = {dimension: set() for dimension in dimensions}
    models = package.get("models")
    model = models.get(level) if isinstance(models, dict) else None
    if not isinstance(model, dict):
        return support

    def collect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in support:
                    values = child if isinstance(child, list) else [child]
                    support[key].update(
                        str(item)
                        for item in values
                        if isinstance(item, str | int | float)
                    )
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(model)
    return support


def _unsupported_control_categories(
    controls: Any,
    support: dict[str, set[str]],
    *,
    ignored_dimensions: set[str],
) -> list[str]:
    problems = []
    for dimension in sorted(set(support) - ignored_dimensions):
        requested = controls.categories_for(dimension)
        missing = sorted(requested - support[dimension])
        if missing:
            problems.append(f"{dimension}: {', '.join(missing)}")
    return problems


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
    inputs = request_data.inputs
    options = request_data.options
    model_id = inputs.model_id
    package_upload_id = inputs.package_upload_id
    candidate_households_id = inputs.candidate_households_upload_id
    candidate_persons_id = inputs.candidate_persons_upload_id
    has_model_source = bool(model_id) ^ bool(package_upload_id)
    has_candidate_source = bool(candidate_households_id) and bool(candidate_persons_id)
    if bool(candidate_households_id) != bool(candidate_persons_id):
        raise ValueError("provide both candidate household and person uploads")
    if has_model_source == has_candidate_source:
        raise ValueError("provide one model/package or one linked candidate pair")
    candidate_validation: dict[str, Any] | None = None
    candidate_households_path: Path | None = None
    candidate_persons_path: Path | None = None
    package: dict[str, Any] | None = None
    inspection: dict[str, Any]
    if model_id:
        package = model_payload(str(model_id))
        normalized_inputs: dict[str, str] = {"model_id": str(model_id)}
        inspection = inspect_prepared_model(package)
    elif package_upload_id:
        package_path = store.upload_path(str(package_upload_id), require_unclaimed=True)
        package = read_prepared_model_package(package_path)
        normalized_inputs = {"package_upload_id": str(package_upload_id)}
        inspection = inspect_prepared_model(package)
    else:
        candidate_households_path = store.upload_path(
            str(candidate_households_id), require_unclaimed=True
        )
        candidate_persons_path = store.upload_path(
            str(candidate_persons_id), require_unclaimed=True
        )
        candidate_validation = validate_linked_population_files(
            candidate_households_path, candidate_persons_path
        )
        if not candidate_validation["passed"]:
            raise ValueError("uploaded linked candidates failed validation")
        normalized_inputs = {
            "candidate_households_upload_id": str(candidate_households_id),
            "candidate_persons_upload_id": str(candidate_persons_id),
        }
        inspection = {
            "ready": True,
            "name": "Uploaded linked candidates",
            "conditions": [],
            "household_targets": _csv_columns(candidate_households_path),
            "person_targets": _csv_columns(candidate_persons_path),
            "privacy": {"publishable_candidate": None},
            "provenance": {},
        }

    controls_id = inputs.controls_upload_id
    controls_path = store.upload_path(controls_id, require_unclaimed=True)
    controls = read_control_table(controls_path)
    if not controls.margins:
        raise ValueError("controls CSV has no control rows")
    normalized_inputs["controls_upload_id"] = controls_id
    person_controls_id = inputs.person_controls_upload_id
    person_controls = None
    if person_controls_id:
        person_controls_path = store.upload_path(
            str(person_controls_id), require_unclaimed=True
        )
        person_controls = read_control_table(person_controls_path)
        if not person_controls.margins:
            raise ValueError("person controls CSV has no control rows")
        normalized_inputs["person_controls_upload_id"] = str(person_controls_id)
    control_pack_id = inputs.control_pack_id
    control_pack_evidence_id = inputs.control_pack_evidence_upload_id
    if bool(control_pack_id) != bool(control_pack_evidence_id):
        raise ValueError("select a control pack and upload its evidence JSON")
    control_pack = None
    control_pack_evidence: ControlPackEvidence | None = None
    if control_pack_id:
        if person_controls is None:
            raise ValueError("control packs require a person controls CSV")
        control_pack = load_control_pack(str(control_pack_id))
        evidence_path = store.upload_path(
            str(control_pack_evidence_id), require_unclaimed=True
        )
        control_pack_evidence = load_control_pack_evidence(evidence_path)
        normalized_inputs["control_pack_id"] = control_pack.identifier
        normalized_inputs["control_pack_evidence_upload_id"] = str(
            control_pack_evidence_id
        )
    boundaries_id = inputs.boundaries_upload_id
    if boundaries_id:
        boundaries_path = store.upload_path(str(boundaries_id), require_unclaimed=True)
        boundaries = json.loads(boundaries_path.read_text())
        if (
            not isinstance(boundaries, dict)
            or boundaries.get("type") != "FeatureCollection"
        ):
            raise ValueError("boundaries must be a GeoJSON FeatureCollection")
        normalized_inputs["boundaries_upload_id"] = str(boundaries_id)

    geography_dimension = options.geography_dimension.strip()
    if not geography_dimension:
        raise ValueError("geography dimension is required")
    if (
        control_pack is not None
        and geography_dimension != control_pack.geography_column
    ):
        raise ValueError(
            f"control pack {control_pack.identifier!r} requires geography "
            f"dimension {control_pack.geography_column!r}"
        )
    candidate_households = options.candidate_households
    if candidate_validation is not None:
        candidate_households = int(candidate_validation["summary"]["households"])
    if candidate_households <= 0:
        raise ValueError("candidate households must be positive")
    if candidate_households > LOCAL_RUN_MAX_HOUSEHOLDS:
        raise ValueError(
            f"local web runs are limited to {LOCAL_RUN_MAX_HOUSEHOLDS:,} candidate "
            "households; use the CLI for a reviewed larger run"
        )
    pool_size = options.pool_size
    estimate = estimate_small_area_run(
        controls,
        geography_dimension=geography_dimension,
        candidate_households=candidate_households,
        pool_size=pool_size,
        average_persons_per_household=options.average_persons_per_household,
    )
    conditions = options.conditions
    inspection_conditions = _inspection_string_list(inspection, "conditions")
    inspection_household_targets = _inspection_string_list(
        inspection, "household_targets"
    )
    inspection_person_targets = _inspection_string_list(inspection, "person_targets")
    unsupported = sorted(set(conditions) - set(inspection_conditions))
    if unsupported:
        raise ValueError(
            "unsupported model condition columns: " + ", ".join(unsupported)
        )
    chunk_size = options.chunk_size
    if chunk_size <= 0:
        raise ValueError("chunk size must be positive")
    max_household_size = options.max_household_size
    if max_household_size is not None and max_household_size <= 0:
        raise ValueError("maximum household size must be positive")
    group_column = options.household_size_group_column
    household_columns = {
        *inspection_conditions,
        *inspection_household_targets,
        geography_dimension,
    }
    if control_pack is not None:
        household_columns.update(
            dimension
            for margin in control_pack.margins
            if margin.entity_level == "household"
            for dimension in margin.dimensions
        )
    if max_household_size is not None:
        household_columns.add(group_column)
    unsupported_household_dimensions = sorted(
        {
            dimension
            for margin in controls.margins
            for dimension in margin.dimensions
            if dimension not in household_columns
        }
    )
    if unsupported_household_dimensions:
        raise ValueError(
            "household controls require unsupported candidate columns: "
            + ", ".join(unsupported_household_dimensions)
        )
    controlled_household_dimensions = {
        dimension
        for margin in controls.margins
        for dimension in margin.dimensions
        if dimension != geography_dimension
    }
    derived_household_dimensions = (
        _pack_derived_dimensions(control_pack, "household")
        if control_pack is not None
        else set()
    )
    household_support_dimensions = (
        controlled_household_dimensions - derived_household_dimensions
    )
    if candidate_households_path is not None:
        household_support = _csv_category_support(
            candidate_households_path, household_support_dimensions
        )
    else:
        household_support = _model_category_support(
            package or {}, "household", household_support_dimensions
        )
    unsupported_household_categories = _unsupported_control_categories(
        controls,
        household_support,
        ignored_dimensions=(
            ({group_column} if max_household_size is not None else set())
            | (derived_household_dimensions)
        ),
    )
    if unsupported_household_categories:
        raise ValueError(
            "household controls contain categories absent from candidates: "
            + "; ".join(unsupported_household_categories)
        )
    if person_controls is not None:
        person_columns = {
            *household_columns,
            *inspection_person_targets,
        }
        if control_pack is not None:
            person_columns.update(
                dimension
                for margin in control_pack.margins
                if margin.entity_level == "person"
                for dimension in margin.dimensions
            )
        unsupported_person_dimensions = sorted(
            {
                dimension
                for margin in person_controls.margins
                for dimension in margin.dimensions
                if dimension not in person_columns
            }
        )
        if unsupported_person_dimensions:
            raise ValueError(
                "person controls require unsupported candidate columns: "
                + ", ".join(unsupported_person_dimensions)
            )
        controlled_person_dimensions = {
            dimension
            for margin in person_controls.margins
            for dimension in margin.dimensions
            if dimension != geography_dimension
        }
        derived_person_dimensions = (
            _pack_derived_dimensions(control_pack, "person")
            if control_pack is not None
            else set()
        )
        person_support_dimensions = (
            controlled_person_dimensions - derived_person_dimensions
        )
        if candidate_persons_path is not None:
            person_support = _csv_category_support(
                candidate_persons_path, person_support_dimensions
            )
        else:
            person_support = _model_category_support(
                package or {}, "person", person_support_dimensions
            )
        unsupported_person_categories = _unsupported_control_categories(
            person_controls,
            person_support,
            ignored_dimensions=(derived_person_dimensions),
        )
        if unsupported_person_categories:
            raise ValueError(
                "person controls contain categories absent from candidates: "
                + "; ".join(unsupported_person_categories)
            )
    estimated_bytes = max(8192, int(estimate["estimated_total_output_rows"]) * 256)
    disk_free = shutil.disk_usage(store.root).free
    enough_disk = disk_free >= estimated_bytes * 2
    geography_column = options.geography_column or geography_dimension
    geography_payload = options.geography_universe
    if geography_payload is not None:
        if not isinstance(geography_payload, dict):
            raise ValueError("geography_universe must be an object")
        geography_universe = GeographyUniverse.from_dict(geography_payload)
        if geography_universe.identifier_column != geography_column:
            raise ValueError(
                "geography universe identifier column must match geography_column"
            )
    else:
        geography_universe = None
    control_pack_plan: dict[str, Any] | None = None
    if control_pack is not None:
        assert control_pack_evidence is not None
        assert person_controls is not None
        expected_universe = statcan_geography_universe(
            control_pack.census_vintage,
            control_pack.geography_level,
            geography_column,
        )
        if (
            geography_universe is not None
            and geography_universe.canonical_key != expected_universe.canonical_key
        ):
            raise ValueError(
                "geography universe is incompatible with the selected control pack"
            )
        geography_universe = expected_universe
        control_geographies = _validate_control_pack_tables(
            control_pack, controls, person_controls
        )
        _validate_control_pack_evidence_binding(
            control_pack,
            control_pack_evidence,
            controls,
            person_controls,
            control_geographies,
        )
        household_fields = (
            _csv_columns(candidate_households_path)
            if candidate_households_path is not None
            else [*inspection_conditions, *inspection_household_targets]
        )
        person_fields = (
            _csv_columns(candidate_persons_path)
            if candidate_persons_path is not None
            else [*inspection_conditions, *inspection_person_targets]
        )
        compatibility = validate_control_pack_compatibility(
            control_pack,
            census_vintage=control_pack_evidence.census_vintage,
            geography_level=control_pack_evidence.geography_level,
            linked_schema_version=control_pack.linked_schema_version,
            household_fields=household_fields,
            person_fields=person_fields,
        )
        if not compatibility["passed"]:
            raise ValueError(str(compatibility["issues"][0]["message"]))
        if candidate_households_path is not None and candidate_persons_path is not None:
            control_pack_plan = plan_control_pack(
                control_pack,
                _read_csv_rows(candidate_households_path),
                _read_csv_rows(candidate_persons_path),
                controls,
                person_controls,
                evidence=control_pack_evidence,
            )
            if not control_pack_plan["passed"]:
                raise ValueError(str(control_pack_plan["issues"][0]["message"]))
        else:
            control_pack_plan = {
                "schema_version": "synthpopcan-control-pack-web-preflight-v1",
                "passed": True,
                "pack": {
                    "identifier": control_pack.identifier,
                    "definition_sha256": control_pack.definition_sha256,
                    "census_vintage": control_pack.census_vintage,
                    "geography_level": control_pack.geography_level,
                    "identifier_namespace": control_pack.identifier_namespace,
                },
                "compatibility": compatibility,
                "deferred_checks": [
                    "candidate category support after deterministic generation",
                    "post-subsample structural support and whole-household "
                    "contribution",
                ],
            }
    normalized_options = {
        "candidate_households": candidate_households,
        "geography_dimension": geography_dimension,
        "geography_column": geography_column,
        "geography_universe": (
            geography_universe.as_dict() if geography_universe is not None else None
        ),
        "conditions": conditions,
        "random_seed": options.random_seed,
        "pool_size": pool_size,
        "subsample_seed": options.subsample_seed,
        "max_household_size": max_household_size,
        "household_size_group_column": group_column,
        "include_weights": options.include_weights,
        "chunk_size": chunk_size,
        "geography_id_field": options.geography_id_field,
        "map_title": options.map_title,
    }
    return {
        "ready": enough_disk,
        "request": {
            "workflow": "small_area",
            "inputs": normalized_inputs,
            "options": normalized_options,
        },
        "model_diagnostics": inspection,
        "estimate": {
            **estimate,
            "output_bytes": estimated_bytes,
            "disk_free_bytes": disk_free,
            "enough_disk": enough_disk,
        },
        "control_pack_plan": control_pack_plan,
        "expected_artifacts": [
            "households",
            "persons",
            "linked_population_manifest",
            "small_area_report",
            *(["map"] if boundaries_id else []),
        ],
    }
