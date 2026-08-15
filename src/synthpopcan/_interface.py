"""Installed-package helpers for the versioned public-interface contract.

This module is deliberately private.  The public contract is the packaged JSON
artifact; these helpers make that artifact reproducible and allow release
checks to validate an installed wheel without importing the source checkout.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping, Sequence
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

import click

PUBLIC_INTERFACE_RESOURCE = "contracts/public-interface-v1.json"


def load_public_interface_contract() -> dict[str, Any]:
    """Load the public-interface contract bundled in the installed package."""

    resource = files("synthpopcan").joinpath(PUBLIC_INTERFACE_RESOURCE)
    raw_payload: object = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, dict):
        raise ValueError("public-interface contract must be a JSON object")
    payload = cast(dict[str, Any], raw_payload)
    if payload.get("schema_version") != "synthpopcan-public-interface-v1":
        raise ValueError("unsupported public-interface contract schema")
    return payload


def snapshot_python_symbol(module_name: str, name: str) -> dict[str, Any]:
    """Describe the import and callable shape of one documented Python name."""

    module = import_module(module_name)
    value = getattr(module, name)
    if inspect.isclass(value):
        kind = "class"
    elif inspect.isfunction(value):
        kind = "function"
    else:
        kind = "value"
    snapshot: dict[str, Any] = {
        "import_path": f"{module_name}.{name}",
        "kind": kind,
        "name": name,
    }
    if kind in {"class", "function"}:
        snapshot["parameters"] = _snapshot_signature(value)
    return snapshot


def snapshot_click_interface(
    root: click.Command,
    *,
    program_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return a deterministic recursive snapshot of a Click command tree."""

    snapshots: list[dict[str, Any]] = []

    def visit(command: click.Command, path: tuple[str, ...]) -> None:
        entry: dict[str, Any] = {
            "kind": "group" if isinstance(command, click.Group) else "command",
            "parameters": [_snapshot_click_parameter(item) for item in command.params],
            "path": " ".join(path),
        }
        if isinstance(command, click.Group):
            entry["invoke_without_command"] = command.invoke_without_command
        format_option = next(
            (
                parameter
                for parameter in command.params
                if isinstance(parameter, click.Option) and "--format" in parameter.opts
            ),
            None,
        )
        if format_option is not None and isinstance(format_option.type, click.Choice):
            entry["output_modes"] = list(format_option.type.choices)
        else:
            entry["output_modes"] = ["human"]
        snapshots.append(entry)
        if isinstance(command, click.Group):
            for child_name, child in sorted(command.commands.items()):
                visit(child, (*path, child_name))

    visit(root, (program_name or root.name or "synthpopcan",))
    return snapshots


def validate_installed_public_interface() -> None:
    """Raise when the installed package no longer matches its bundled contract."""

    import synthpopcan
    from synthpopcan.cli import cli

    contract = load_public_interface_contract()
    python_contract = _mapping(contract.get("python"), "python")
    expected_top_level = _sequence(python_contract.get("top_level"), "python.top_level")
    expected_advanced = _sequence(python_contract.get("advanced"), "python.advanced")
    expected_names = [
        str(_mapping(item, "python.top_level item")["name"])
        for item in expected_top_level
    ]
    if list(synthpopcan.__all__) != expected_names:
        raise RuntimeError("top-level Python exports drifted from the public contract")

    actual_top_level = [
        snapshot_python_symbol("synthpopcan", name) for name in expected_names
    ]
    if actual_top_level != expected_top_level:
        raise RuntimeError(
            "top-level Python signatures drifted from the public contract"
        )

    actual_advanced = [
        snapshot_python_symbol(
            str(_mapping(item, "python.advanced item")["module"]),
            str(_mapping(item, "python.advanced item")["name"]),
        )
        | {
            "module": str(_mapping(item, "python.advanced item")["module"]),
        }
        for item in expected_advanced
    ]
    if actual_advanced != expected_advanced:
        raise RuntimeError("advanced Python API drifted from the public contract")

    cli_contract = _mapping(contract.get("cli"), "cli")
    expected_commands = _sequence(cli_contract.get("commands"), "cli.commands")
    if snapshot_click_interface(cli, program_name="synthpopcan") != expected_commands:
        raise RuntimeError("CLI command tree drifted from the public contract")


def _snapshot_signature(value: Any) -> list[dict[str, Any]]:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return []
    return [
        {
            "default": _json_default(parameter.default),
            "kind": parameter.kind.name.lower(),
            "name": parameter.name,
            "required": parameter.default is inspect.Parameter.empty,
        }
        for parameter in signature.parameters.values()
    ]


def _snapshot_click_parameter(parameter: click.Parameter) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "option" if isinstance(parameter, click.Option) else "argument",
        "multiple": parameter.multiple,
        "name": parameter.name,
        "nargs": parameter.nargs,
        "required": parameter.required,
        "type": _snapshot_click_type(parameter.type),
    }
    if isinstance(parameter, click.Option):
        entry["names"] = [*parameter.opts, *parameter.secondary_opts]
        if not parameter.required:
            entry["default"] = _json_default(parameter.default)
    return entry


def _snapshot_click_type(parameter_type: click.ParamType[Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": parameter_type.name or type(parameter_type).__name__
    }
    if isinstance(parameter_type, click.Choice):
        entry["case_sensitive"] = parameter_type.case_sensitive
        entry["choices"] = list(parameter_type.choices)
    if isinstance(parameter_type, (click.IntRange, click.FloatRange)):
        entry.update(
            {
                "clamp": parameter_type.clamp,
                "max": parameter_type.max,
                "max_open": parameter_type.max_open,
                "min": parameter_type.min,
                "min_open": parameter_type.min_open,
            }
        )
    if isinstance(parameter_type, click.Path):
        entry.update(
            {
                "dir_okay": parameter_type.dir_okay,
                "exists": parameter_type.exists,
                "file_okay": parameter_type.file_okay,
                "readable": parameter_type.readable,
                "writable": parameter_type.writable,
            }
        )
    return entry


def _json_default(value: object) -> object:
    if value is inspect.Parameter.empty:
        return None
    if isinstance(value, Path):
        return {"path": str(value)}
    if isinstance(value, tuple):
        return [_json_default(item) for item in cast(tuple[object, ...], value)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if callable(value):
        return {"dynamic": True}
    return {"type": type(value).__name__}


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return cast(Sequence[Any], value)
