"""Local web-app serving helpers."""

from __future__ import annotations

import csv
import json
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import urlopen
from zipfile import ZipFile

from synthpopcan.statcan import fetch_json, normalize_product_id, wds_download_url

WDS_METADATA_COLUMNS = {
    "STATUS",
    "SYMBOL",
    "TERMINATED",
    "DECIMALS",
    "SCALAR_FACTOR",
    "SCALAR_ID",
    "VECTOR",
    "COORDINATE",
    "DGUID",
    "UOM",
    "UOM_ID",
}
WDS_FETCH_TIMEOUT_SECONDS = 30
WdsRow = tuple[int, dict[str, str]]


class WebAppServer(Protocol):
    server_address: tuple[str, int]

    def serve_forever(self) -> None: ...

    def server_close(self) -> None: ...


def get_webapp_root() -> Path:
    """Return the packaged static web app directory."""
    return Path(str(files("synthpopcan.web")))


class SynthPopCanWebHandler(SimpleHTTPRequestHandler):
    """Static file handler with small localhost API helpers."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/models":
            self._send_json({"models": demo_model_catalogue()})
            return
        if path.startswith("/api/models/"):
            self._handle_demo_model(path.rsplit("/", 1)[-1])
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/wds/seed-controls":
            self._handle_wds_seed_controls()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_demo_model(self, model_id: str) -> None:
        try:
            self._send_json(demo_model_payload(model_id))
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown demo model")

    def _handle_wds_seed_controls(self) -> None:
        try:
            payload = self._read_json_body()
            product_id = normalize_product_id(str(payload.get("productId", "")))
            zip_bytes, download_url = fetch_wds_zip_bytes(product_id)
            generated = generate_wds_seed_controls_from_zip_bytes(
                zip_bytes,
                dimensions=parse_dimensions(payload.get("dimensions", [])),
                count_column=str(payload.get("countColumn") or "VALUE"),
            )
            self._send_json(
                {
                    "productId": product_id,
                    "downloadUrl": download_url,
                    **generated,
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(
        self, payload: dict[str, object], *, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_webapp_server(host: str, port: int) -> ThreadingHTTPServer:
    """Build a local HTTP server for the packaged web app."""
    root = get_webapp_root()
    handler = partial(SynthPopCanWebHandler, directory=str(root))
    return ThreadingHTTPServer((host, port), handler)


def webapp_url(server: WebAppServer) -> str:
    """Return the browser URL for a local server."""
    host, port = server.server_address
    browser_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}/"


def serve_webapp(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = True,
    opener=webbrowser.open,
    server_factory=build_webapp_server,
) -> str:
    """Serve the packaged web app and optionally open it in a browser."""
    server = server_factory(host, port)
    url = webapp_url(server)
    if open_browser:
        opener(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return url


def fetch_wds_zip_bytes(product_id: str, lang: str = "en") -> tuple[bytes, str]:
    """Fetch a StatCan WDS ZIP through Python to avoid browser CORS limits."""
    source_url = wds_download_url(product_id, lang)
    response = fetch_json(source_url)
    if response.get("status") != "SUCCESS" or not response.get("object"):
        raise ValueError(f"StatCan WDS did not return a download URL for {product_id}")
    download_url = str(response["object"])
    with urlopen(download_url, timeout=WDS_FETCH_TIMEOUT_SECONDS) as handle:
        return handle.read(), download_url


def demo_model_catalogue() -> list[dict[str, object]]:
    """Return safe demo models served by the local app."""
    return [
        {
            "id": "demo-linked-household-person",
            "name": "Safe demo household/person package",
            "description": (
                "Tiny linked model trained from synthetic toy rows; not derived "
                "from Census microdata."
            ),
            "kind": "linked_household_person",
            "geography": "Demo regions",
            "safe_demo": True,
        }
    ]


def demo_model_payload(model_id: str) -> dict[str, object]:
    """Return a prepared demo model package.

    The package is intentionally trained from toy synthetic rows so it can be
    bundled and served without disclosure risk.
    """
    if model_id != "demo-linked-household-person":
        raise KeyError(model_id)
    household_model = demo_household_model()
    person_model = demo_person_model()
    return {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "name": "Safe demo household/person package",
        "description": (
            "Demonstration package trained from synthetic toy rows. It exercises "
            "linked household/person generation without using restricted data."
        ),
        "household_size_column": "household_size",
        "privacy": {
            "publishable_candidate": True,
            "safe_demo": True,
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "source": "synthetic toy rows only",
        },
        "provenance": {
            "source": "SynthPopCan bundled demo",
            "training_data": "hand-authored synthetic toy distribution",
            "contains_real_microdata": False,
        },
        "models": {"household": household_model, "person": person_model},
    }


def demo_household_model() -> dict[str, object]:
    return {
        "schema_version": "synthpopcan-tree-model-v1",
        "model_type": "conditional-frequency",
        "release_class": "publishable_candidate",
        "spec": {
            "level": "household",
            "model_family": "tree-based",
            "target_columns": ["household_size", "tenure"],
            "conditioning_columns": ["geo"],
            "geography_column": "geo",
            "weight_column": None,
            "random_seed": 101,
        },
        "source_format": "synthetic-demo-v1",
        "records_trained": 96,
        "groups": [
            {
                "conditions": {"geo": "Demo North"},
                "support": 48,
                "outcomes": [
                    {
                        "values": {"household_size": "1", "tenure": "renter"},
                        "weight": 10,
                    },
                    {
                        "values": {"household_size": "2", "tenure": "owner"},
                        "weight": 24,
                    },
                    {
                        "values": {"household_size": "3", "tenure": "owner"},
                        "weight": 14,
                    },
                ],
            },
            {
                "conditions": {"geo": "Demo South"},
                "support": 48,
                "outcomes": [
                    {
                        "values": {"household_size": "1", "tenure": "renter"},
                        "weight": 18,
                    },
                    {
                        "values": {"household_size": "2", "tenure": "renter"},
                        "weight": 16,
                    },
                    {
                        "values": {"household_size": "4", "tenure": "owner"},
                        "weight": 14,
                    },
                ],
            },
        ],
        "global_outcomes": [
            {"values": {"household_size": "1", "tenure": "renter"}, "weight": 28},
            {"values": {"household_size": "2", "tenure": "owner"}, "weight": 24},
            {"values": {"household_size": "3", "tenure": "owner"}, "weight": 14},
            {"values": {"household_size": "2", "tenure": "renter"}, "weight": 16},
            {"values": {"household_size": "4", "tenure": "owner"}, "weight": 14},
        ],
        "privacy": {
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "minimum_support": 48,
            "min_support_threshold": 5,
            "groups_below_threshold": 0,
            "publishable": True,
            "safe_demo": True,
        },
    }


def demo_person_model() -> dict[str, object]:
    person_outcomes = [
        {"values": {"age_group": "child", "sex": "F"}, "weight": 1},
        {"values": {"age_group": "adult", "sex": "F"}, "weight": 2},
        {"values": {"age_group": "adult", "sex": "M"}, "weight": 2},
        {"values": {"age_group": "older", "sex": "F"}, "weight": 1},
    ]
    groups = []
    for geo in ("Demo North", "Demo South"):
        for household_size in ("1", "2", "3", "4"):
            for tenure in ("owner", "renter"):
                groups.append(
                    {
                        "conditions": {
                            "geo": geo,
                            "household_size": household_size,
                            "tenure": tenure,
                        },
                        "support": 12,
                        "outcomes": person_outcomes,
                    }
                )
    return {
        "schema_version": "synthpopcan-tree-model-v1",
        "model_type": "conditional-frequency",
        "release_class": "publishable_candidate",
        "spec": {
            "level": "person",
            "model_family": "tree-based",
            "target_columns": ["age_group", "sex"],
            "conditioning_columns": ["geo", "household_size", "tenure"],
            "geography_column": "geo",
            "weight_column": None,
            "random_seed": 202,
        },
        "source_format": "synthetic-demo-v1",
        "records_trained": 192,
        "groups": groups,
        "global_outcomes": person_outcomes,
        "privacy": {
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
            "minimum_support": 12,
            "min_support_threshold": 5,
            "groups_below_threshold": 0,
            "publishable": True,
            "safe_demo": True,
        },
    }


def generate_wds_seed_controls_from_zip_bytes(
    zip_bytes: bytes,
    *,
    dimensions: tuple[str, ...],
    count_column: str,
) -> dict[str, object]:
    """Normalize a WDS ZIP into browser-ready seed and control CSV strings."""
    with ZipFile(BytesIO(zip_bytes)) as archive:
        csv_member = choose_wds_data_csv_member(archive)
        with archive.open(csv_member) as raw_handle:
            handle = TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
            rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("WDS table has no rows")
    numbered_rows = list(enumerate(rows, start=2))
    resolved_dimensions = resolve_wds_dimensions(rows, dimensions)
    if not resolved_dimensions:
        resolved_dimensions = suggest_wds_dimensions(rows, count_column)
    snapshot_rows, reference_period = snapshot_wds_rows(
        numbered_rows, resolved_dimensions
    )
    control_rows = normalize_wds_rows(
        snapshot_rows,
        dimensions=resolved_dimensions,
        count_column=count_column,
    )
    seed_rows = build_seed_rows(control_rows)
    return {
        "csvMember": csv_member,
        "referencePeriod": reference_period,
        "dimensions": list(resolved_dimensions),
        "countColumn": count_column,
        "seedRows": len(seed_rows),
        "controlRows": len(control_rows),
        "seedCsv": write_csv(seed_rows),
        "controlsCsv": write_csv(control_rows),
    }


def choose_wds_data_csv_member(archive: ZipFile) -> str:
    csv_names = [
        name
        for name in archive.namelist()
        if not name.endswith("/") and name.lower().endswith(".csv")
    ]
    data_names = [name for name in csv_names if "metadata" not in name.lower()]
    selected = data_names[0] if data_names else (csv_names[0] if csv_names else None)
    if selected is None:
        raise ValueError("WDS ZIP does not contain a CSV file")
    return selected


def parse_dimensions(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        items = value.replace("|", ",").split(",")
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    return tuple(item.strip() for item in items if item.strip())


def resolve_wds_dimensions(
    rows: list[dict[str, str]], dimensions: tuple[str, ...]
) -> tuple[str, ...]:
    columns = list(rows[0])
    columns_by_lower = {column.lower(): column for column in columns}
    resolved: list[str] = []
    for dimension in dimensions:
        if dimension in columns:
            resolved.append(dimension)
        elif dimension.lower() == "geography" and "GEO" in columns:
            resolved.append("GEO")
        else:
            resolved.append(columns_by_lower.get(dimension.lower(), dimension))
    return tuple(resolved)


def suggest_wds_dimensions(
    rows: list[dict[str, str]], count_column: str
) -> tuple[str, ...]:
    return tuple(
        column
        for column in rows[0]
        if column != count_column
        and column != "REF_DATE"
        and column.upper() not in WDS_METADATA_COLUMNS
    )


def snapshot_wds_rows(
    rows: list[WdsRow], dimensions: tuple[str, ...]
) -> tuple[list[WdsRow], str | None]:
    first_row = rows[0][1]
    if "REF_DATE" not in first_row or "REF_DATE" in dimensions:
        return rows, None
    reference_periods = sorted(
        {row["REF_DATE"] for _, row in rows if row.get("REF_DATE")},
        key=reference_period_sort_key,
    )
    if not reference_periods:
        return rows, None
    reference_period = reference_periods[-1]
    snapshot_rows = [
        (row_number, row)
        for row_number, row in rows
        if row.get("REF_DATE") == reference_period
    ]
    return snapshot_rows, reference_period


def reference_period_sort_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except ValueError:
        return (1, value)


def normalize_wds_rows(
    rows: list[WdsRow], *, dimensions: tuple[str, ...], count_column: str
) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    control_rows: list[dict[str, str]] = []
    for row_number, row in rows:
        if row.get(count_column, "") == "":
            continue
        missing = [
            column for column in (*dimensions, count_column) if column not in row
        ]
        if missing:
            raise ValueError(
                f"WDS row {row_number} is missing columns: {', '.join(missing)}"
            )
        key = tuple(row[dimension] for dimension in dimensions)
        if key in seen:
            raise ValueError(f"WDS row {row_number} duplicates control cell {key!r}")
        seen.add(key)
        try:
            count = float(row[count_column])
        except ValueError as exc:
            raise ValueError(f"WDS row {row_number} has invalid count") from exc
        control_rows.append(
            {
                "margin": "wds",
                "dimensions": ",".join(dimensions),
                **{dimension: row[dimension] for dimension in dimensions},
                "count": format_count(count),
            }
        )
    return control_rows


def build_seed_rows(control_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    seed_rows: list[dict[str, str]] = []
    for row in control_rows:
        dimensions = parse_dimensions(row["dimensions"])
        values = {dimension: row.get(dimension, "") for dimension in dimensions}
        key = tuple(values.items())
        if key not in seen:
            seen.add(key)
            seed_rows.append({"id": f"seed-{len(seed_rows) + 1}", **values})
    return seed_rows


def write_csv(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def format_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
