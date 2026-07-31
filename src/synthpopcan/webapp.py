"""Uvicorn lifecycle helpers for the packaged local web application."""

from __future__ import annotations

__all__ = [
    "build_webapp_server",
    "get_webapp_root",
    "serve_webapp",
    "validate_loopback_host",
    "webapp_url",
]

import ipaddress
import socket
import threading
import webbrowser
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Protocol

import uvicorn

from synthpopcan.webapi import create_web_app

DEFAULT_WORKSPACE = Path("synthpopcan-runs")


class _WebAppServer(Protocol):
    @property
    def server_address(self) -> tuple[str, int]: ...

    def serve_forever(self) -> None: ...

    def shutdown(self) -> None: ...

    def server_close(self) -> None: ...


class UvicornWebAppServer:
    """Compatibility wrapper exposing the previous local-server lifecycle."""

    def __init__(self, host: str, port: int, *, workspace: Path) -> None:
        app = create_web_app(
            static_root=get_webapp_root(),
            workspace=workspace,
        )
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self._host = host
        self._port = port
        self._server = uvicorn.Server(config)
        self._server_address = (host, port)
        self._started = threading.Event()

    @property
    def server_address(self) -> tuple[str, int]:
        if self._port != 0:
            return self._host, self._port
        self._started.wait(timeout=2)
        return self._server_address

    def serve_forever(self) -> None:
        family = socket.AF_INET6 if ":" in self._host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self._host, self._port))
            listener.listen()
            host, port = listener.getsockname()[:2]
            self._server_address = (str(host), int(port))
            self._started.set()
            self._server.run(sockets=[listener])

    def shutdown(self) -> None:
        self._server.should_exit = True

    def server_close(self) -> None:
        self._server.should_exit = True


def get_webapp_root() -> Path:
    """Return the packaged static web app directory."""
    return Path(str(files("synthpopcan.web")))


def validate_loopback_host(host: str) -> str:
    """Return a normalized loopback host or reject network exposure."""
    candidate = host.strip().lower()
    if candidate == "localhost":
        return candidate
    try:
        if ipaddress.ip_address(candidate).is_loopback:
            return candidate
    except ValueError:
        pass
    raise ValueError(
        "the local web app only accepts loopback hosts (127.0.0.1, ::1, or localhost)"
    )


def build_webapp_server(
    host: str,
    port: int,
    *,
    workspace: Path = DEFAULT_WORKSPACE,
) -> UvicornWebAppServer:
    """Build the FastAPI/Uvicorn server for the packaged web app."""
    return UvicornWebAppServer(
        validate_loopback_host(host),
        port,
        workspace=workspace,
    )


def webapp_url(server: _WebAppServer) -> str:
    """Return the browser URL for a local server."""
    host, port = server.server_address
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1" if host == "0.0.0.0" else "::1"
    browser_host = f"[{host}]" if ":" in host else host
    return f"http://{browser_host}:{port}/"


def serve_webapp(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    workspace: Path = DEFAULT_WORKSPACE,
    open_browser: bool = True,
    opener: Callable[[str], object] = webbrowser.open,
    server_factory: Callable[[str, int], _WebAppServer] | None = None,
) -> str:
    """Serve the packaged web app and optionally open it in a browser."""
    normalized_host = validate_loopback_host(host)
    if server_factory is None:
        server = build_webapp_server(
            normalized_host,
            port,
            workspace=workspace,
        )
    else:
        server = server_factory(normalized_host, port)
    url = webapp_url(server)
    if open_browser:
        opener(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown = getattr(server, "shutdown", None)
        if shutdown is not None:
            shutdown()
        server.server_close()

    return url
