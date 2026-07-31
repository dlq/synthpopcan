"""Verified runtime retrieval of prepared display-boundary assets."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

__all__ = ["fetch_display_boundaries", "geodata_cache_dir", "load_geodata_catalogue"]


def geodata_cache_dir() -> Path:
    """Return the effective cache directory for prepared display boundaries.

    ``SYNTHPOPCAN_GEODATA_CACHE`` takes precedence. Without an override, macOS
    uses its conventional user cache tree and other platforms use
    ``XDG_CACHE_HOME`` or ``~/.cache``. The directory is not created until an
    asset is fetched.
    """

    override = os.environ.get("SYNTHPOPCAN_GEODATA_CACHE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "synthpopcan" / "geodata"
    root = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    return Path(root) / "synthpopcan" / "geodata"


def load_geodata_catalogue(catalogue: str | Path | None = None) -> dict[str, object]:
    """Load and validate a local or HTTP(S) geodata release catalogue.

    ``catalogue`` overrides ``SYNTHPOPCAN_GEODATA_CATALOGUE``. The returned
    mapping must use ``synthpopcan-geodata-catalogue-v1``; asset-level identity
    and checksums are validated when :func:`fetch_display_boundaries` selects a
    file.
    """

    source = catalogue or os.environ.get("SYNTHPOPCAN_GEODATA_CATALOGUE")
    if source is None:
        raise FileNotFoundError(
            "no geodata catalogue configured; set SYNTHPOPCAN_GEODATA_CATALOGUE "
            "to a release catalogue path or URL"
        )
    source_text = str(source)
    if source_text.startswith(("https://", "http://")):
        with urlopen(source_text, timeout=60) as response:
            payload = json.loads(response.read())
    else:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or (
        payload.get("schema_version") != "synthpopcan-geodata-catalogue-v1"
    ):
        raise ValueError("unsupported geodata catalogue")
    return payload


def fetch_display_boundaries(
    census_year: int,
    geography_level: str,
    *,
    pruid: str | None = None,
    catalogue: str | Path | None = None,
) -> Path:
    """Fetch one exact prepared display GeoJSON into the verified user cache.

    Selection requires a unique Census year, geography level, and optional
    PRUID match. The compressed download and unpacked GeoJSON are checked
    against their separate catalogue SHA-256 values before an atomic install.
    A valid existing unpacked file is reused. These display boundaries are not
    substitutes for canonical analytical geometry.
    """

    payload = load_geodata_catalogue(catalogue)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("geodata catalogue assets are invalid")
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("census_year") == census_year
        and asset.get("geography_level") == geography_level
        and asset.get("pruid") == pruid
    ]
    if len(matches) != 1:
        raise ValueError(
            "no unique prepared display boundary asset matches this request"
        )
    asset = matches[0]
    filename = asset.get("filename")
    if not isinstance(filename, str) or not filename.endswith(".gz"):
        raise ValueError("geodata asset filename is invalid")
    destination = geodata_cache_dir() / filename.removesuffix(".gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and (
        _sha256(destination) == asset.get("uncompressed_sha256")
    ):
        return destination
    url = asset.get("url")
    if not isinstance(url, str):
        raise ValueError("geodata asset has no release URL")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        archive = Path(temporary) / filename
        with urlopen(url, timeout=60) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if _sha256(archive) != asset.get("sha256"):
            raise ValueError("downloaded geodata asset checksum did not match")
        unpacked = Path(temporary) / destination.name
        with gzip.open(archive, "rb") as source, unpacked.open("wb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
        if _sha256(unpacked) != asset.get("uncompressed_sha256"):
            raise ValueError("unpacked geodata asset checksum did not match")
        unpacked.replace(destination)
    return destination


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()
