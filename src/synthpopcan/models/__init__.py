"""Packaged and downloadable linked model artifacts.

The installed package intentionally bundles only tiny demo data. Larger
publishable-candidate model packages are listed in a registry and fetched into a
local cache only when a user asks for them.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from urllib.request import urlopen

ProgressCallback = Callable[[int, int | None], None]

_RELEASE_BASE_URL = "https://github.com/dlq/synthpopcan/releases/download/v0.1.0"

_MODEL_PACKAGES: dict[str, dict[str, object]] = {
    "demo-linked-household-person": {
        "filename": "demo-linked-household-person-package.json",
        "name": "Safe demo household/person package",
        "description": (
            "Tiny linked model trained from synthetic toy rows; not derived "
            "from Census microdata."
        ),
        "geography": "Demo regions",
        "provenance": "Synthetic toy rows only; not Census microdata.",
        "conditions": ["geo"],
        "default_generation": {
            "households": 10,
            "conditions": "geo=Demo North",
        },
        "safe_demo": True,
        "distribution": "bundled",
    },
    "montreal-cma-2016-all-fields": {
        "filename": "montreal-cma-2016-all-fields-package.json",
        "name": "Montreal CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for CMA 462."
        ),
        "geography": "Montreal CMA (CMA 462)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 64_234_759,
        "sha256": ("ebad14c83bf2aef47e3ac6e0684c1994ea0fa8cd83df7eaeb78a76077174ef91"),
        "url": (f"{_RELEASE_BASE_URL}/montreal-cma-2016-all-fields-package.json"),
    },
    "quebec-2016-all-fields": {
        "filename": "quebec-2016-all-fields-package.json",
        "name": "Quebec 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Quebec (PR 24)."
        ),
        "geography": "Quebec (PR 24)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 122_079_409,
        "sha256": ("7fbfa64e29ae5539f382475c472cb1fe48b988161e0b3a10ecd81fcaa942a7d7"),
        "url": f"{_RELEASE_BASE_URL}/quebec-2016-all-fields-package.json",
    },
}


def model_catalogue() -> list[dict[str, object]]:
    """Return model packages known to SynthPopCan."""

    return [
        {
            "id": model_id,
            "name": str(metadata["name"]),
            "description": str(metadata["description"]),
            "kind": "linked_household_person",
            "geography": str(metadata["geography"]),
            "release_status": "publishable_candidate",
            "provenance": str(metadata["provenance"]),
            "privacy": "No raw rows or source identifiers.",
            "conditions": list(metadata["conditions"]),  # type: ignore[arg-type]
            "outputs": ["households.csv", "persons.csv"],
            "default_generation": metadata["default_generation"],
            "safe_demo": bool(metadata["safe_demo"]),
            "distribution": str(metadata["distribution"]),
            "installed": model_is_installed(model_id),
            "size_bytes": metadata.get("size_bytes"),
        }
        for model_id, metadata in _MODEL_PACKAGES.items()
    ]


def model_payload(model_id: str) -> dict[str, object]:
    """Return a linked model package by ID.

    Bundled demo packages load immediately. Downloadable packages must be
    fetched into the local model cache first.
    """

    metadata = model_registry_entry(model_id)
    payload = json.loads(_model_path(model_id).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"model package {model_id} must be a JSON object")
    payload.setdefault("name", metadata["name"])
    payload.setdefault("description", metadata["description"])
    payload.setdefault("generation_defaults", metadata["default_generation"])
    return payload


def model_registry_entry(model_id: str) -> dict[str, object]:
    """Return metadata for one registered model package."""

    try:
        return _MODEL_PACKAGES[model_id]
    except KeyError as exc:
        raise KeyError(model_id) from exc


def model_is_installed(model_id: str) -> bool:
    """Return whether a model package can be loaded without downloading."""

    try:
        _model_path(model_id)
    except FileNotFoundError:
        return False
    return True


def model_cache_path(model_id: str) -> Path:
    """Return the local cache path for a downloadable model package."""

    metadata = model_registry_entry(model_id)
    return model_cache_dir() / str(metadata["filename"])


def model_cache_dir() -> Path:
    """Return the directory used for downloaded model packages."""

    override = os.environ.get("SYNTHPOPCAN_MODEL_CACHE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "synthpopcan" / "models"
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "SynthPopCan" / "models"
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "synthpopcan" / "models"
    return Path.home() / ".cache" / "synthpopcan" / "models"


def fetch_model_package(
    model_id: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Download a registered model package into the local cache and verify it."""

    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") != "download":
        return _model_path(model_id)
    destination = model_cache_path(model_id)
    if destination.exists():
        _verify_model_checksum(destination, metadata)
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(destination.suffix + ".part")
    url = str(metadata["url"])
    try:
        with urlopen(url, timeout=60) as response:
            total_bytes = _download_size(response, metadata)
            if progress_callback:
                progress_callback(0, total_bytes)
            with temporary_path.open("wb") as handle:
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes)
        _verify_model_checksum(temporary_path, metadata)
        temporary_path.replace(destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return destination


def remove_cached_model(model_id: str) -> bool:
    """Remove a downloaded model package from the local cache."""

    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") != "download":
        return False
    path = model_cache_path(model_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def _model_path(model_id: str) -> Path:
    metadata = model_registry_entry(model_id)
    if metadata.get("distribution") == "bundled":
        return Path(
            str(files("synthpopcan.models").joinpath(str(metadata["filename"])))
        )
    path = model_cache_path(model_id)
    if path.exists():
        return path
    raise FileNotFoundError(
        f"model package {model_id} is not downloaded; run "
        f"`synthpopcan models fetch {model_id}`"
    )


def _verify_model_checksum(path: Path, metadata: dict[str, object]) -> None:
    expected = metadata.get("sha256")
    if not expected:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(
            f"downloaded model checksum did not match for {metadata.get('filename')}"
        )


def _download_size(response: object, metadata: dict[str, object]) -> int | None:
    headers = getattr(response, "headers", {})
    content_length = None
    if hasattr(headers, "get"):
        content_length = headers.get("Content-Length")
    if content_length:
        try:
            return int(content_length)
        except ValueError:
            pass
    size = metadata.get("size_bytes")
    return size if isinstance(size, int) else None
