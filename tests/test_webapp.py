from __future__ import annotations

import csv
from io import BytesIO, StringIO
from threading import Thread
from urllib.request import urlopen
from zipfile import ZipFile

import pytest

from synthpopcan.cli import main
from synthpopcan.webapp import (
    build_webapp_server,
    demo_model_catalogue,
    demo_model_payload,
    generate_wds_seed_controls_from_zip_bytes,
    get_webapp_root,
    serve_webapp,
    webapp_url,
)


class FakeServer:
    def __init__(self) -> None:
        self.server_address = ("127.0.0.1", 8123)
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


class InterruptingServer(FakeServer):
    def serve_forever(self) -> None:
        self.served = True
        raise KeyboardInterrupt


def test_webapp_assets_include_index() -> None:
    root = get_webapp_root()

    assert root.is_dir()
    assert (root / "index.html").is_file()
    assert (root / "app.mjs").is_file()
    assert (root / "csv.mjs").is_file()
    assert (root / "ipf.mjs").is_file()
    assert (root / "preview.mjs").is_file()
    assert (root / "tree-model.mjs").is_file()
    assert (root / "starter-files.mjs").is_file()
    assert (root / "statcan.mjs").is_file()
    assert (root / "wds-normalize.mjs").is_file()
    assert (root / "zip.mjs").is_file()
    assert (root / "worker.mjs").is_file()
    assert (root / "synthpopcan-logo-256.png").is_file()


def test_webapp_url_uses_loopback_for_wildcard_host() -> None:
    server = FakeServer()
    server.server_address = ("0.0.0.0", 8123)

    assert webapp_url(server) == "http://127.0.0.1:8123/"


def test_serve_webapp_opens_browser_and_closes_server() -> None:
    server = FakeServer()
    opened_urls: list[str] = []

    url = serve_webapp(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        opener=opened_urls.append,
        server_factory=lambda host, port: server,
    )

    assert url == "http://127.0.0.1:8123/"
    assert opened_urls == [url]
    assert server.served is True
    assert server.closed is True


def test_serve_webapp_closes_quietly_on_keyboard_interrupt() -> None:
    server = InterruptingServer()

    url = serve_webapp(
        host="127.0.0.1",
        port=0,
        open_browser=False,
        server_factory=lambda host, port: server,
    )

    assert url == "http://127.0.0.1:8123/"
    assert server.served is True
    assert server.closed is True


def test_cli_serve_delegates_to_webapp_runner(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_serve_webapp(**kwargs: object) -> str:
        calls.append(kwargs)
        return "http://127.0.0.1:8123/"

    monkeypatch.setattr("synthpopcan.cli.serve_webapp", fake_serve_webapp)

    assert main(["serve", "--host", "127.0.0.1", "--port", "8123", "--no-open"]) == 0
    assert calls == [
        {"host": "127.0.0.1", "port": 8123, "open_browser": False},
    ]


def test_webapp_static_assets_are_not_browser_cached() -> None:
    server = build_webapp_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(webapp_url(server), timeout=2) as response:
            assert response.headers["Cache-Control"] == "no-store"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_webapp_generates_wds_seed_controls_from_statcan_zip_shape() -> None:
    zip_bytes = build_wds_zip(
        {
            "13100005-eng/13100005_MetaData.csv": (
                "Cube Title,Product Id\nExample,13100005\n"
            ),
            "13100005-eng/13100005.csv": (
                "REF_DATE,GEO,Sex,VALUE,STATUS\n"
                "1979,Canada,Female,100,\n"
                "1980,Canada,Female,110,\n"
                "1980,Canada,Male,112,\n"
            ),
        }
    )

    generated = generate_wds_seed_controls_from_zip_bytes(
        zip_bytes,
        dimensions=("Geography", "Sex"),
        count_column="VALUE",
    )

    assert generated["csvMember"] == "13100005-eng/13100005.csv"
    assert generated["referencePeriod"] == "1980"
    assert generated["dimensions"] == ["GEO", "Sex"]
    assert generated["seedRows"] == 2
    assert generated["controlRows"] == 2
    assert read_csv_text(str(generated["controlsCsv"])) == [
        {
            "margin": "wds",
            "dimensions": "GEO,Sex",
            "GEO": "Canada",
            "Sex": "Female",
            "count": "110",
        },
        {
            "margin": "wds",
            "dimensions": "GEO,Sex",
            "GEO": "Canada",
            "Sex": "Male",
            "count": "112",
        },
    ]


def test_webapp_wds_generation_defaults_to_latest_snapshot_without_ref_date() -> None:
    zip_bytes = build_wds_zip(
        {
            "table_MetaData.csv": "Cube Title,Product Id\nExample,13100005\n",
            "table.csv": (
                "REF_DATE,GEO,Sex,VALUE,STATUS\n"
                "1979,Canada,Female,,..\n"
                "1979,Canada,Male,,..\n"
                "1980,Canada,Female,110,\n"
                "1980,Canada,Male,112,\n"
            ),
        }
    )

    generated = generate_wds_seed_controls_from_zip_bytes(
        zip_bytes,
        dimensions=(),
        count_column="VALUE",
    )

    assert generated["referencePeriod"] == "1980"
    assert generated["dimensions"] == ["GEO", "Sex"]
    assert generated["seedRows"] == 2
    assert generated["controlRows"] == 2


def test_webapp_wds_generation_reports_original_row_after_snapshot() -> None:
    zip_bytes = build_wds_zip(
        {
            "table.csv": (
                "REF_DATE,GEO,Sex,VALUE,STATUS\n"
                "1979,Canada,Female,100,\n"
                "1980,Canada,Female,not-a-number,\n"
            ),
        }
    )

    with pytest.raises(ValueError, match="WDS row 3 has invalid count"):
        generate_wds_seed_controls_from_zip_bytes(
            zip_bytes,
            dimensions=("GEO", "Sex"),
            count_column="VALUE",
        )


def test_webapp_demo_model_catalogue_serves_safe_linked_package() -> None:
    catalogue = demo_model_catalogue()

    assert catalogue == [
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

    payload = demo_model_payload("demo-linked-household-person")
    assert payload["schema_version"] == "synthpopcan-linked-tree-package-v1"
    assert payload["privacy"]["publishable_candidate"] is True  # type: ignore[index]
    assert payload["privacy"]["safe_demo"] is True  # type: ignore[index]
    assert payload["provenance"]["contains_real_microdata"] is False  # type: ignore[index]
    assert set(payload["models"]) == {"household", "person"}  # type: ignore[arg-type]


def build_wds_zip(files: dict[str, str]) -> bytes:
    handle = BytesIO()
    with ZipFile(handle, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return handle.getvalue()


def read_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))
