"""Tests for verified prepared-boundary distribution."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from synthpopcan.geodata import fetch_display_boundaries


def _write_catalogue(tmp_path: Path, *, compressed_sha: str | None = None) -> Path:
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
                "uncompressed_sha256": hashlib.sha256(content).hexdigest(),
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
