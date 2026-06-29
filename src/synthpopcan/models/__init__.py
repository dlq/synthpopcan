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
from typing import Any
from urllib.request import urlopen

ProgressCallback = Callable[[int, int | None], None]

_RELEASE_BASE_URL = "https://github.com/dlq/synthpopcan/releases/download/v0.2.0"
_RELEASE_021_BASE_URL = "https://github.com/dlq/synthpopcan/releases/download/v0.2.1"

_MODEL_PACKAGES: dict[str, dict[str, Any]] = {
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
        "sha256": "7fbfa64e29ae5539f382475c472cb1fe48b988161e0b3a10ecd81fcaa942a7d7",
        "url": f"{_RELEASE_BASE_URL}/quebec-2016-all-fields-package.json",
    },
    "ontario-2016-all-fields": {
        "filename": "ontario-2016-all-fields-package.json",
        "name": "Ontario 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Ontario (PR 35)."
        ),
        "geography": "Ontario (PR 35)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 205_757_139,
        "sha256": "0967ba99c4179e3de1d8436a14e0b3082bd4a7353c68b9c59a4c32977711e7ed",
        "url": f"{_RELEASE_BASE_URL}/ontario-2016-all-fields-package.json",
    },
    "bc-2016-all-fields": {
        "filename": "bc-2016-all-fields-package.json",
        "name": "British Columbia 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for British Columbia (PR 59)."
        ),
        "geography": "British Columbia (PR 59)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 75_781_376,
        "sha256": "76e855c2d2bd6b62ef7e7073c4df5ea288fe0f8e060c5e36859c24047a56fb54",
        "url": f"{_RELEASE_BASE_URL}/bc-2016-all-fields-package.json",
    },
    "alberta-2016-all-fields": {
        "filename": "alberta-2016-all-fields-package.json",
        "name": "Alberta 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Alberta (PR 48)."
        ),
        "geography": "Alberta (PR 48)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 63_448_287,
        "sha256": "0f0f61fc0a3e188b1c64ea02acc3f05fbfdb0d993ffee3a901b5b51f7fe81814",
        "url": f"{_RELEASE_BASE_URL}/alberta-2016-all-fields-package.json",
    },
    "toronto-cma-2016-all-fields": {
        "filename": "toronto-cma-2016-all-fields-package.json",
        "name": "Toronto CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Toronto CMA (CMA 535)."
        ),
        "geography": "Toronto CMA (CMA 535)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 93_385_062,
        "sha256": "dd0caf299c852ed526861b9bc6e6a2d654bf0bbe51809d76c9b5e30da0381ae0",
        "url": f"{_RELEASE_BASE_URL}/toronto-cma-2016-all-fields-package.json",
    },
    "vancouver-cma-2016-all-fields": {
        "filename": "vancouver-cma-2016-all-fields-package.json",
        "name": "Vancouver CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Vancouver CMA (CMA 933)."
        ),
        "geography": "Vancouver CMA (CMA 933)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 40_937_245,
        "sha256": "3e3565c2ba4dbfdab28bf907e256d48bb766971270dde09fde597afb57c210cf",
        "url": f"{_RELEASE_BASE_URL}/vancouver-cma-2016-all-fields-package.json",
    },
    "manitoba-2016-all-fields": {
        "filename": "manitoba-2016-all-fields-package.json",
        "name": "Manitoba 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Manitoba (PR 46)."
        ),
        "geography": "Manitoba (PR 46)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 20_186_538,
        "sha256": "82e8f03152568a3898c80de36705827f8a22101a1390a2b9f381df366a9088f4",
        "url": f"{_RELEASE_BASE_URL}/manitoba-2016-all-fields-package.json",
    },
    "calgary-cma-2016-all-fields": {
        "filename": "calgary-cma-2016-all-fields-package.json",
        "name": "Calgary CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Calgary CMA (CMA 825)."
        ),
        "geography": "Calgary CMA (CMA 825)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 22_635_036,
        "sha256": "d55fe22cfa66c5b78545b65e3275972ebc2f37e714f9a6b266040ec9a0a407a2",
        "url": f"{_RELEASE_BASE_URL}/calgary-cma-2016-all-fields-package.json",
    },
    "edmonton-cma-2016-all-fields": {
        "filename": "edmonton-cma-2016-all-fields-package.json",
        "name": "Edmonton CMA 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Edmonton CMA (CMA 835)."
        ),
        "geography": "Edmonton CMA (CMA 835)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["CMA", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 21_367_337,
        "sha256": "c18b593c93fd02cc30ee07a956ace912b0072a8c14c6a538e94087592c27818a",
        "url": f"{_RELEASE_BASE_URL}/edmonton-cma-2016-all-fields-package.json",
    },
    "saskatchewan-2016-all-fields": {
        "filename": "saskatchewan-2016-all-fields-package.json",
        "name": "Saskatchewan 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Saskatchewan (PR 47)."
        ),
        "geography": "Saskatchewan (PR 47)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 17_458_623,
        "sha256": "1bcb91caf412ba6c1b760fc51fb57ffcdc95608bdf20fb854237a4d5751f1a8f",
        "url": f"{_RELEASE_BASE_URL}/saskatchewan-2016-all-fields-package.json",
    },
    "nova-scotia-2016-all-fields": {
        "filename": "nova-scotia-2016-all-fields-package.json",
        "name": "Nova Scotia 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Nova Scotia (PR 12)."
        ),
        "geography": "Nova Scotia (PR 12)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 15_356_566,
        "sha256": "70062e8d721d8ff29da0dbbfdbb455b9a9e519f9a69465898c571c6f799f06a4",
        "url": f"{_RELEASE_BASE_URL}/nova-scotia-2016-all-fields-package.json",
    },
    "new-brunswick-2016-all-fields": {
        "filename": "new-brunswick-2016-all-fields-package.json",
        "name": "New Brunswick 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for New Brunswick (PR 13)."
        ),
        "geography": "New Brunswick (PR 13)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 12_499_103,
        "sha256": "607a7a368746b755fb2e6b345a69219b6e655c3dd9f41aac670e6cbf1dd94876",
        "url": f"{_RELEASE_BASE_URL}/new-brunswick-2016-all-fields-package.json",
    },
    "newfoundland-2016-all-fields": {
        "filename": "newfoundland-2016-all-fields-package.json",
        "name": "Newfoundland and Labrador 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Newfoundland and Labrador (PR 10)."
        ),
        "geography": "Newfoundland and Labrador (PR 10)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 8_537_569,
        "sha256": "c107a61c85d2f12b3c4b95656229e191287d6af927c53a7f18ad33ba8e9fe7c7",
        "url": f"{_RELEASE_BASE_URL}/newfoundland-2016-all-fields-package.json",
    },
    "pei-2016-minimal": {
        "filename": "pei-2016-minimal-package.json",
        "name": "Prince Edward Island 2016 minimal linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for Prince Edward Island (PR 11). "
            "Uses a minimal column profile due to small sample size."
        ),
        "geography": "Prince Edward Island (PR 11)",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 100,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 65_948,
        "sha256": "b9733fb70d83020444e811b3597fbb4621164290aa4982255a940b702f31a4ff",
        "url": f"{_RELEASE_BASE_URL}/pei-2016-minimal-package.json",
    },
    "canada-2016-all-fields": {
        "filename": "canada-2016-all-fields-package.json",
        "name": "Canada 2016 broad linked package",
        "description": (
            "Publishable-candidate linked household/person model trained from "
            "the local 2016 hierarchical PUMF for all Canada."
        ),
        "geography": "Canada",
        "provenance": "Statistics Canada 2016 Census hierarchical PUMF.",
        "conditions": ["PR", "household_size", "TENUR"],
        "default_generation": {
            "households": 1000,
            "conditions": "",
        },
        "safe_demo": False,
        "distribution": "download",
        "size_bytes": 531_314_980,
        "sha256": "ce0bffe4945ccebd962010593d3b316dc7f6d7b7b5803271a54e3da94b7073ab",
        "url": f"{_RELEASE_021_BASE_URL}/canada-2016-all-fields-package.json",
    },
}


def model_catalogue() -> list[dict[str, Any]]:
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


def model_payload(model_id: str) -> dict[str, Any]:
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


def model_registry_entry(model_id: str) -> dict[str, Any]:
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


def _verify_model_checksum(path: Path, metadata: dict[str, Any]) -> None:
    expected = metadata.get("sha256")
    if not expected:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(
            f"downloaded model checksum did not match for {metadata.get('filename')}"
        )


def _download_size(response: object, metadata: dict[str, Any]) -> int | None:
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
