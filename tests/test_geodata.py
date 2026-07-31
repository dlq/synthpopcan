"""Tests for verified prepared-boundary distribution."""

from __future__ import annotations

import gzip
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest

from synthpopcan import geodata
from synthpopcan.geodata import (
    fetch_display_boundaries,
    geodata_cache_dir,
    load_geodata_catalogue,
)


def _write_catalogue(
    tmp_path: Path,
    *,
    compressed_sha: str | None = None,
    uncompressed_sha: str | None = None,
) -> Path:
    content = b'{"type":"FeatureCollection","features":[]}'
    archive = tmp_path / "2021-boundary-da-24-display-topo.geojson.gz"
    archive.write_bytes(gzip.compress(content))
    catalogue = {
        "schema_version": "synthpopcan-geodata-catalogue-v1",
        "assets": [
            {
                "census_year": 2021,
                "geography_level": "da",
                "pruid": "24",
                "filename": archive.name,
                "url": archive.as_uri(),
                "sha256": compressed_sha
                or hashlib.sha256(archive.read_bytes()).hexdigest(),
                "uncompressed_sha256": uncompressed_sha
                or hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue))
    return path


def test_fetch_display_boundaries_downloads_and_reuses_verified_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_GEODATA_CACHE", str(tmp_path / "cache"))
    catalogue = _write_catalogue(tmp_path)
    path = fetch_display_boundaries(2021, "da", pruid="24", catalogue=catalogue)
    assert json.loads(path.read_text())["type"] == "FeatureCollection"
    # The archive is no longer needed once the verified cache exists.
    (tmp_path / "2021-boundary-da-24-display-topo.geojson.gz").unlink()
    assert fetch_display_boundaries(2021, "da", pruid="24", catalogue=catalogue) == path


def test_fetch_display_boundaries_rejects_bad_download_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_GEODATA_CACHE", str(tmp_path / "cache"))
    catalogue = _write_catalogue(tmp_path, compressed_sha="0" * 64)
    with pytest.raises(ValueError, match="checksum"):
        fetch_display_boundaries(2021, "da", pruid="24", catalogue=catalogue)


def test_geodata_cache_dir_honours_override_and_platform_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_GEODATA_CACHE", "~/custom-geodata")
    assert geodata_cache_dir() == Path("~/custom-geodata").expanduser()

    monkeypatch.delenv("SYNTHPOPCAN_GEODATA_CACHE")
    monkeypatch.setattr(geodata.sys, "platform", "darwin")
    assert geodata_cache_dir().parts[-4:] == (
        "Library",
        "Caches",
        "synthpopcan",
        "geodata",
    )

    monkeypatch.setattr(geodata.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/geodata-cache")
    assert geodata_cache_dir() == Path("/tmp/geodata-cache/synthpopcan/geodata")


def test_load_geodata_catalogue_validates_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_GEODATA_CATALOGUE", raising=False)
    with pytest.raises(FileNotFoundError, match="no geodata catalogue"):
        load_geodata_catalogue()

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]")
    with pytest.raises(ValueError, match="unsupported"):
        load_geodata_catalogue(invalid)


def test_load_geodata_catalogue_supports_https_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = BytesIO(b'{"schema_version":"synthpopcan-geodata-catalogue-v1"}')
    monkeypatch.setattr(geodata, "urlopen", lambda *_args, **_kwargs: response)

    assert load_geodata_catalogue("https://example.test/catalogue.json") == {
        "schema_version": "synthpopcan-geodata-catalogue-v1"
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda catalogue: catalogue.pop("assets"), "assets are invalid"),
        (lambda catalogue: catalogue["assets"].clear(), "no unique"),
        (
            lambda catalogue: catalogue["assets"][0].__setitem__("filename", "bad"),
            "filename",
        ),
        (lambda catalogue: catalogue["assets"][0].pop("url"), "release URL"),
    ],
)
def test_fetch_display_boundaries_rejects_invalid_catalogue_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    message: str,
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_GEODATA_CACHE", str(tmp_path / "cache"))
    catalogue_path = _write_catalogue(tmp_path)
    catalogue = json.loads(catalogue_path.read_text())
    mutation(catalogue)
    catalogue_path.write_text(json.dumps(catalogue))

    with pytest.raises(ValueError, match=message):
        fetch_display_boundaries(2021, "da", pruid="24", catalogue=catalogue_path)


def test_fetch_display_boundaries_rejects_bad_uncompressed_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_GEODATA_CACHE", str(tmp_path / "cache"))
    catalogue = _write_catalogue(tmp_path, uncompressed_sha="0" * 64)

    with pytest.raises(ValueError, match="unpacked"):
        fetch_display_boundaries(2021, "da", pruid="24", catalogue=catalogue)
