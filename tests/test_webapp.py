from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import pytest

from synthpopcan.cli import main
from synthpopcan.web_demo_models import demo_model_catalogue, demo_model_payload
from synthpopcan.web_wds import (
    choose_wds_data_csv_member,
    fetch_wds_zip_bytes,
    generate_wds_seed_controls_from_zip_bytes,
    normalize_wds_rows,
    parse_dimensions,
    reference_period_sort_key,
    snapshot_wds_rows,
    write_csv,
)
from synthpopcan.webapp import (
    build_webapp_server,
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


def test_webapp_serves_demo_model_api_endpoints() -> None:
    server = build_webapp_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"{webapp_url(server)}api/models", timeout=2) as response:
            assert response.headers["Content-Type"] == "application/json"
            catalogue = json.loads(response.read().decode("utf-8"))
        with urlopen(
            f"{webapp_url(server)}api/models/demo-linked-household-person",
            timeout=2,
        ) as response:
            package = json.loads(response.read().decode("utf-8"))

        assert catalogue["models"][0]["id"] == "demo-linked-household-person"
        assert catalogue["models"][0]["release_status"] == "publishable_candidate"
        assert catalogue["models"][0]["provenance"] == (
            "Synthetic toy rows only; not Census microdata."
        )
        assert catalogue["models"][0]["outputs"] == [
            "households.csv",
            "persons.csv",
        ]
        assert catalogue["models"][0]["default_generation"] == {
            "households": 10,
            "conditions": "geo=Demo North",
        }
        assert package["schema_version"] == "synthpopcan-linked-tree-package-v1"
        assert package["review"]["status"] == "safe demo"
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"{webapp_url(server)}api/models/missing", timeout=2)
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_webapp_wds_seed_controls_api_uses_local_helper(monkeypatch) -> None:
    zip_bytes = b"fake-zip"

    monkeypatch.setattr(
        "synthpopcan.webapp.fetch_wds_zip_bytes",
        lambda product_id: (zip_bytes, f"https://example.test/{product_id}.zip"),
    )
    monkeypatch.setattr(
        "synthpopcan.webapp.generate_wds_seed_controls_from_zip_bytes",
        lambda data, *, dimensions, count_column: {
            "seedCsv": "id,age\nseed-1,young\n",
            "controlsCsv": "margin,dimensions,age,count\nage,age,young,1\n",
            "dimensions": list(dimensions),
            "countColumn": count_column,
        },
    )
    server = build_webapp_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"{webapp_url(server)}api/wds/seed-controls",
            data=json.dumps(
                {
                    "productId": "13100005",
                    "dimensions": "Age|Sex",
                    "countColumn": "VALUE",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        assert payload["productId"] == "13100005"
        assert payload["downloadUrl"] == "https://example.test/13100005.zip"
        assert payload["dimensions"] == ["Age", "Sex"]
        assert payload["countColumn"] == "VALUE"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_webapp_wds_seed_controls_api_reports_bad_requests(monkeypatch) -> None:
    monkeypatch.setattr(
        "synthpopcan.webapp.fetch_wds_zip_bytes",
        lambda product_id: (_ for _ in ()).throw(ValueError("download failed")),
    )
    server = build_webapp_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(
            f"{webapp_url(server)}api/wds/seed-controls",
            data=json.dumps({"productId": "13100005"}).encode("utf-8"),
            method="POST",
        )
        with pytest.raises(HTTPError) as exc_info:
            urlopen(request, timeout=2)
        assert exc_info.value.code == 400
        payload = json.loads(exc_info.value.read().decode("utf-8"))
        assert payload == {"error": "download failed"}

        missing = Request(f"{webapp_url(server)}api/missing", data=b"{}", method="POST")
        with pytest.raises(HTTPError) as missing_info:
            urlopen(missing, timeout=2)
        assert missing_info.value.code == 404

        no_body = Request(
            f"{webapp_url(server)}api/wds/seed-controls",
            data=None,
            method="POST",
        )
        with pytest.raises(HTTPError) as no_body_info:
            urlopen(no_body, timeout=2)
        assert no_body_info.value.code == 400
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


def test_webapp_wds_helper_edge_cases(monkeypatch) -> None:
    assert parse_dimensions("GEO|Sex, Age") == ("GEO", "Sex", "Age")
    assert parse_dimensions(["GEO", " Sex "]) == ("GEO", "Sex")
    assert parse_dimensions(None) == ()
    assert reference_period_sort_key("2020") == (0, 2020.0)
    assert reference_period_sort_key("2020/2021") == (1, "2020/2021")
    assert write_csv([]) == ""

    metadata_only_zip = build_wds_zip(
        {"table_MetaData.csv": "Cube Title,Product Id\nExample,13100005\n"}
    )
    with ZipFile(BytesIO(metadata_only_zip)) as archive:
        assert choose_wds_data_csv_member(archive) == "table_MetaData.csv"
    empty_zip = build_wds_zip({"readme.txt": "not a table"})
    with ZipFile(BytesIO(empty_zip)) as archive:
        with pytest.raises(ValueError, match="does not contain a CSV"):
            choose_wds_data_csv_member(archive)

    rows = [(2, {"GEO": "Canada", "VALUE": "1"})]
    assert snapshot_wds_rows(rows, ("GEO",)) == (rows, None)
    assert snapshot_wds_rows([(2, {"REF_DATE": "", "GEO": "Canada"})], ("GEO",)) == (
        [(2, {"REF_DATE": "", "GEO": "Canada"})],
        None,
    )
    generated_with_blank = generate_wds_seed_controls_from_zip_bytes(
        build_wds_zip({"table.csv": "GEO,Sex,VALUE\nCanada,Female,\n"}),
        dimensions=("GEO", "Unknown"),
        count_column="VALUE",
    )
    assert generated_with_blank["dimensions"] == ["GEO", "Unknown"]
    assert generated_with_blank["seedRows"] == 0
    assert generated_with_blank["controlRows"] == 0

    with pytest.raises(ValueError, match="has no rows"):
        generate_wds_seed_controls_from_zip_bytes(
            build_wds_zip({"table.csv": "GEO,Sex,VALUE\n"}),
            dimensions=("GEO", "Sex"),
            count_column="VALUE",
        )

    with pytest.raises(ValueError, match="missing columns"):
        normalize_wds_rows(rows, dimensions=("GEO", "Sex"), count_column="VALUE")
    with pytest.raises(ValueError, match="duplicates control cell"):
        normalize_wds_rows(
            [
                (2, {"GEO": "Canada", "VALUE": "1"}),
                (3, {"GEO": "Canada", "VALUE": "2"}),
            ],
            dimensions=("GEO",),
            count_column="VALUE",
        )

    monkeypatch.setattr(
        "synthpopcan.web_wds.fetch_json",
        lambda url: {"status": "FAILED", "object": None},
    )
    with pytest.raises(ValueError, match="did not return a download URL"):
        fetch_wds_zip_bytes("13100005")

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"zip-bytes"

    monkeypatch.setattr(
        "synthpopcan.web_wds.fetch_json",
        lambda url: {"status": "SUCCESS", "object": "https://example.test/table.zip"},
    )
    monkeypatch.setattr(
        "synthpopcan.web_wds.urlopen",
        lambda url, timeout: FakeResponse(),
    )

    assert fetch_wds_zip_bytes("13100005") == (
        b"zip-bytes",
        "https://example.test/table.zip",
    )


def test_webapp_demo_model_catalogue_serves_safe_linked_package() -> None:
    catalogue = demo_model_catalogue()

    assert len(catalogue) == 1
    model = catalogue[0]
    assert model["id"] == "demo-linked-household-person"
    assert model["name"] == "Safe demo household/person package"
    assert model["description"] == (
        "Tiny linked model trained from synthetic toy rows; not derived "
        "from Census microdata."
    )
    assert model["kind"] == "linked_household_person"
    assert model["geography"] == "Demo regions"
    assert model["safe_demo"] is True
    assert model["release_status"] == "publishable_candidate"
    assert model["provenance"] == "Synthetic toy rows only; not Census microdata."
    assert model["privacy"] == "No raw rows or source identifiers."
    assert model["conditions"] == ["geo"]
    assert model["outputs"] == ["households.csv", "persons.csv"]
    assert model["default_generation"] == {
        "households": 10,
        "conditions": "geo=Demo North",
    }

    payload = demo_model_payload("demo-linked-household-person")
    assert payload["schema_version"] == "synthpopcan-linked-tree-package-v1"
    assert payload["privacy"]["publishable_candidate"] is True  # type: ignore[index]
    assert payload["privacy"]["safe_demo"] is True  # type: ignore[index]
    assert payload["provenance"]["contains_real_microdata"] is False  # type: ignore[index]
    assert payload["review"]["status"] == "safe demo"  # type: ignore[index]
    assert payload["generation_defaults"] == {  # type: ignore[index]
        "households": 10,
        "conditions": "geo=Demo North",
    }
    assert set(payload["models"]) == {"household", "person"}  # type: ignore[arg-type]


def build_wds_zip(files: dict[str, str]) -> bytes:
    handle = BytesIO()
    with ZipFile(handle, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return handle.getvalue()


def read_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))
