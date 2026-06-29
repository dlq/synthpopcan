"""Packaged and downloadable linked model artifacts.

The installed package intentionally bundles only tiny demo data. Larger
publishable-candidate model packages are listed in a registry and fetched into a
local cache only when a user asks for them.
"""

from __future__ import annotations

import gzip
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

_RELEASE_BASE_URL = "https://github.com/dlq/synthpopcan/releases/download/v0.2.1"

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
        "size_bytes": 1_009_496,
        "sha256": "94ff771884ead36b604d05c8e4043e36869da85c75aa1919f31adf21fd4aee97",
        "uncompressed_size_bytes": 64_234_759,
        "uncompressed_sha256": (
            "ebad14c83bf2aef47e3ac6e0684c1994ea0fa8cd83df7eaeb78a76077174ef91"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/montreal-cma-2016-all-fields-package.json.gz",
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
        "size_bytes": 1_770_789,
        "sha256": "1f03b9c5e72c5641f31159f0af3d4c3839e142445f17c81d3fd2f969c74a0628",
        "uncompressed_size_bytes": 122_079_409,
        "uncompressed_sha256": (
            "7fbfa64e29ae5539f382475c472cb1fe48b988161e0b3a10ecd81fcaa942a7d7"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/quebec-2016-all-fields-package.json.gz",
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
        "size_bytes": 3_005_146,
        "sha256": "7477a7161b8243aba5ef64c902a9db303290733edb5b2832210c1fd7075ff879",
        "uncompressed_size_bytes": 205_757_139,
        "uncompressed_sha256": (
            "0967ba99c4179e3de1d8436a14e0b3082bd4a7353c68b9c59a4c32977711e7ed"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/ontario-2016-all-fields-package.json.gz",
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
        "size_bytes": 1_198_845,
        "sha256": "13b04e77c3aab726aaf1ef9164ec5ef1c2ed16d710f275f3b3dcfa09ca476f6a",
        "uncompressed_size_bytes": 75_781_376,
        "uncompressed_sha256": (
            "76e855c2d2bd6b62ef7e7073c4df5ea288fe0f8e060c5e36859c24047a56fb54"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/bc-2016-all-fields-package.json.gz",
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
        "size_bytes": 1_008_748,
        "sha256": "da034db035a0ebc8d96cf012b3698fd6c14b648967389832446fe10c48b73ce8",
        "uncompressed_size_bytes": 63_448_287,
        "uncompressed_sha256": (
            "0f0f61fc0a3e188b1c64ea02acc3f05fbfdb0d993ffee3a901b5b51f7fe81814"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/alberta-2016-all-fields-package.json.gz",
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
        "size_bytes": 1_478_757,
        "sha256": "157778bc2bd095d65b1fab91fdbcb0385ed5de76baad20abe82817211b0735c2",
        "uncompressed_size_bytes": 93_385_062,
        "uncompressed_sha256": (
            "dd0caf299c852ed526861b9bc6e6a2d654bf0bbe51809d76c9b5e30da0381ae0"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/toronto-cma-2016-all-fields-package.json.gz",
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
        "size_bytes": 687_436,
        "sha256": "a92cbb27f0e149bd7b83da2055b43d3a4fa1e5bc1567a29208c335f10fba49c6",
        "uncompressed_size_bytes": 40_937_245,
        "uncompressed_sha256": (
            "3e3565c2ba4dbfdab28bf907e256d48bb766971270dde09fde597afb57c210cf"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/vancouver-cma-2016-all-fields-package.json.gz",
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
        "size_bytes": 336_929,
        "sha256": "70ca5e7944ff135813d1aaff04f2f7c9a25f98bd3ecc27c069124aad784ffa6d",
        "uncompressed_size_bytes": 20_186_538,
        "uncompressed_sha256": (
            "82e8f03152568a3898c80de36705827f8a22101a1390a2b9f381df366a9088f4"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/manitoba-2016-all-fields-package.json.gz",
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
        "size_bytes": 391_581,
        "sha256": "0ed93270044c97fbd2d6b8e6222192dc438e990f2c5f70dbeb1ed9ada51b7500",
        "uncompressed_size_bytes": 22_635_036,
        "uncompressed_sha256": (
            "d55fe22cfa66c5b78545b65e3275972ebc2f37e714f9a6b266040ec9a0a407a2"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/calgary-cma-2016-all-fields-package.json.gz",
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
        "size_bytes": 369_262,
        "sha256": "b600f19ffe7e257c4afbe618fb50d21a4ecadd2c498c14159c97f5179ee4d554",
        "uncompressed_size_bytes": 21_367_337,
        "uncompressed_sha256": (
            "c18b593c93fd02cc30ee07a956ace912b0072a8c14c6a538e94087592c27818a"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/edmonton-cma-2016-all-fields-package.json.gz",
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
        "size_bytes": 287_123,
        "sha256": "2b4430944d18d8161d22c2ce5dcfce0f6720aed4259197769971c62d3d320b70",
        "uncompressed_size_bytes": 17_458_623,
        "uncompressed_sha256": (
            "1bcb91caf412ba6c1b760fc51fb57ffcdc95608bdf20fb854237a4d5751f1a8f"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/saskatchewan-2016-all-fields-package.json.gz",
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
        "size_bytes": 244_276,
        "sha256": "f8212b336645225653b01f6976791efd7d58947bab4b95553978c62632686871",
        "uncompressed_size_bytes": 15_356_566,
        "uncompressed_sha256": (
            "70062e8d721d8ff29da0dbbfdbb455b9a9e519f9a69465898c571c6f799f06a4"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/nova-scotia-2016-all-fields-package.json.gz",
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
        "size_bytes": 202_698,
        "sha256": "167b5bd5a0398d48ceb50f01ef715add4c7e4d61c62713348a00f01e436787f1",
        "uncompressed_size_bytes": 12_499_103,
        "uncompressed_sha256": (
            "607a7a368746b755fb2e6b345a69219b6e655c3dd9f41aac670e6cbf1dd94876"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/new-brunswick-2016-all-fields-package.json.gz",
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
        "size_bytes": 138_661,
        "sha256": "b552c09faca4ac1e51510c3464fd480ace6a50ed60eb77e739832acdff6393f7",
        "uncompressed_size_bytes": 8_537_569,
        "uncompressed_sha256": (
            "c107a61c85d2f12b3c4b95656229e191287d6af927c53a7f18ad33ba8e9fe7c7"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/newfoundland-2016-all-fields-package.json.gz",
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
        "size_bytes": 4_486,
        "sha256": "60fedf9fedddc13848338b006a70efb04cef4f6aee300c4d2f3ffd6acf1f5bcb",
        "uncompressed_size_bytes": 65_948,
        "uncompressed_sha256": (
            "b9733fb70d83020444e811b3597fbb4621164290aa4982255a940b702f31a4ff"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/pei-2016-minimal-package.json.gz",
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
        "size_bytes": 8_286_186,
        "sha256": "2db0629d01ad91e050acfa956097ee48abb7ee07f2007a40df91786981127b04",
        "uncompressed_size_bytes": 531_314_980,
        "uncompressed_sha256": (
            "ce0bffe4945ccebd962010593d3b316dc7f6d7b7b5803271a54e3da94b7073ab"
        ),
        "compression": "gzip",
        "url": f"{_RELEASE_BASE_URL}/canada-2016-all-fields-package.json.gz",
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
    download_path = destination.with_suffix(destination.suffix + ".download")
    temporary_path = destination.with_suffix(destination.suffix + ".part")
    url = str(metadata["url"])
    try:
        with urlopen(url, timeout=60) as response:
            total_bytes = _download_size(response, metadata)
            if progress_callback:
                progress_callback(0, total_bytes)
            with download_path.open("wb") as handle:
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes)
        _verify_download_checksum(download_path, metadata)
        _unpack_downloaded_model(download_path, temporary_path, metadata)
        _verify_model_checksum(temporary_path, metadata)
        temporary_path.replace(destination)
    finally:
        if download_path.exists():
            download_path.unlink()
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
    expected = metadata.get("uncompressed_sha256") or metadata.get("sha256")
    if not expected:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(
            f"downloaded model checksum did not match for {metadata.get('filename')}"
        )


def _verify_download_checksum(path: Path, metadata: dict[str, Any]) -> None:
    expected = metadata.get("sha256")
    if not expected:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(
            f"downloaded model checksum did not match for {metadata.get('filename')}"
        )


def _unpack_downloaded_model(
    download_path: Path,
    destination: Path,
    metadata: dict[str, Any],
) -> None:
    compression = metadata.get("compression")
    if compression == "gzip":
        with gzip.open(download_path, "rb") as source, destination.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        return
    if compression:
        raise ValueError(f"unsupported model package compression: {compression}")
    download_path.replace(destination)


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
