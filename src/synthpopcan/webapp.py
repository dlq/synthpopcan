"""Local web-app serving helpers."""

from __future__ import annotations

__all__ = ["build_webapp_server", "get_webapp_root", "serve_webapp", "webapp_url"]

import json
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from synthpopcan.models import model_catalogue, model_payload
from synthpopcan.statcan import normalize_product_id
from synthpopcan.web_wds import (
    fetch_wds_zip_bytes,
    generate_wds_seed_controls_from_zip_bytes,
    parse_dimensions,
)


class _WebAppServer(Protocol):
    server_address: tuple[str, int]

    def serve_forever(self) -> None: ...

    def server_close(self) -> None: ...


def get_webapp_root() -> Path:
    """Return the packaged static web app directory."""
    return Path(str(files("synthpopcan.web")))


class _SynthPopCanWebHandler(SimpleHTTPRequestHandler):
    """Static file handler with small localhost API helpers."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/models":
            self._send_json({"models": model_catalogue()})
            return
        if path.startswith("/api/models/"):
            self._handle_model(path.rsplit("/", 1)[-1])
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/wds/seed-controls":
            self._handle_wds_seed_controls()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_model(self, model_id: str) -> None:
        try:
            self._send_json(model_payload(model_id))
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown model")
        except FileNotFoundError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)

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

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(
        self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK
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
    handler = partial(_SynthPopCanWebHandler, directory=str(root))
    return ThreadingHTTPServer((host, port), handler)


def webapp_url(server: _WebAppServer) -> str:
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
