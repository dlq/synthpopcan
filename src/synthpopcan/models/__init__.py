"""Packaged linked model artifacts available to the CLI and web app."""

from __future__ import annotations

import json
from importlib.resources import files

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
    },
}


def model_catalogue() -> list[dict[str, object]]:
    """Return model packages shipped with SynthPopCan."""

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
        }
        for model_id, metadata in _MODEL_PACKAGES.items()
    ]


def model_payload(model_id: str) -> dict[str, object]:
    """Return a packaged linked model package by ID."""

    try:
        metadata = _MODEL_PACKAGES[model_id]
    except KeyError as exc:
        raise KeyError(model_id) from exc
    model_file = files("synthpopcan.models").joinpath(str(metadata["filename"]))
    payload = json.loads(model_file.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"model package {model_id} must be a JSON object")
    payload.setdefault("name", metadata["name"])
    payload.setdefault("description", metadata["description"])
    payload.setdefault("generation_defaults", metadata["default_generation"])
    return payload
