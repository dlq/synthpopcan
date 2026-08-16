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
from typing import Any, Never, cast

import click

PUBLIC_INTERFACE_RESOURCE = "contracts/public-interface-v1.json"
PUBLIC_INTERFACE_BASELINE_RESOURCE = "contracts/public-interface-v1-baseline.json"


def load_public_interface_contract() -> dict[str, Any]:
    """Load the public-interface contract bundled in the installed package."""

    return _load_public_interface_resource(PUBLIC_INTERFACE_RESOURCE)


def load_public_interface_baseline() -> dict[str, Any]:
    """Load the immutable 1.0 compatibility baseline bundled in the package."""

    return _load_public_interface_resource(PUBLIC_INTERFACE_BASELINE_RESOURCE)


def _load_public_interface_resource(resource_name: str) -> dict[str, Any]:
    resource = files("synthpopcan").joinpath(resource_name)
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
        parameters, return_annotation = _snapshot_signature(value)
        snapshot["parameters"] = parameters
        snapshot["return_annotation"] = return_annotation
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
    validate_public_interface_compatibility(
        load_public_interface_baseline(),
        contract,
    )
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


def validate_public_interface_compatibility(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    """Reject a candidate that weakens the frozen 1.x interface baseline."""

    for field in ("schema_version", "effective_from"):
        _require_compatible_equal(baseline.get(field), candidate.get(field), field)
    _validate_cli_compatibility(
        _mapping(baseline.get("cli"), "baseline.cli"),
        _mapping(candidate.get("cli"), "candidate.cli"),
    )
    _validate_python_compatibility(
        _mapping(baseline.get("python"), "baseline.python"),
        _mapping(candidate.get("python"), "candidate.python"),
    )
    baseline_schemas = _mapping(
        baseline.get("persisted_schemas"), "baseline.persisted_schemas"
    )
    candidate_schemas = _mapping(
        candidate.get("persisted_schemas"), "candidate.persisted_schemas"
    )
    _validate_supported_schema_compatibility(
        _sequence(baseline_schemas.get("supported"), "baseline supported schemas"),
        _sequence(candidate_schemas.get("supported"), "candidate supported schemas"),
    )


def _validate_cli_compatibility(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> None:
    for field in ("entry_point", "exit_codes", "help_options", "output_contract"):
        _require_compatible_equal(
            baseline.get(field), candidate.get(field), f"cli.{field}"
        )
    baseline_commands = _index_contract_items(
        _sequence(baseline.get("commands"), "baseline.cli.commands"),
        key="path",
        path="baseline.cli.commands",
    )
    candidate_commands = _index_contract_items(
        _sequence(candidate.get("commands"), "candidate.cli.commands"),
        key="path",
        path="candidate.cli.commands",
    )
    for path, baseline_command in baseline_commands.items():
        candidate_command = candidate_commands.get(path)
        if candidate_command is None:
            _compatibility_break(f"cli.commands[{path}]", "command was removed")
        for field in ("kind", "invoke_without_command"):
            if field in baseline_command:
                _require_compatible_equal(
                    baseline_command[field],
                    candidate_command.get(field),
                    f"cli.commands[{path}].{field}",
                )
        _require_compatible_subset(
            _sequence(
                baseline_command.get("output_modes"),
                f"baseline output modes for {path}",
            ),
            _sequence(
                candidate_command.get("output_modes"),
                f"candidate output modes for {path}",
            ),
            f"cli.commands[{path}].output_modes",
        )
        _validate_click_parameters(
            _sequence(
                baseline_command.get("parameters"),
                f"baseline parameters for {path}",
            ),
            _sequence(
                candidate_command.get("parameters"),
                f"candidate parameters for {path}",
            ),
            command_path=path,
        )


def _validate_click_parameters(
    baseline: Sequence[Any],
    candidate: Sequence[Any],
    *,
    command_path: str,
) -> None:
    baseline_parameters = [
        _mapping(value, f"baseline parameter for {command_path}") for value in baseline
    ]
    candidate_parameters = [
        _mapping(value, f"candidate parameter for {command_path}")
        for value in candidate
    ]
    baseline_arguments = [
        value for value in baseline_parameters if value.get("kind") == "argument"
    ]
    candidate_arguments = [
        value for value in candidate_parameters if value.get("kind") == "argument"
    ]
    if [value.get("name") for value in candidate_arguments] != [
        value.get("name") for value in baseline_arguments
    ]:
        _compatibility_break(
            f"cli.commands[{command_path}].arguments",
            "positional arguments changed",
        )
    for baseline_argument, candidate_argument in zip(
        baseline_arguments, candidate_arguments, strict=True
    ):
        _validate_click_parameter(
            baseline_argument,
            candidate_argument,
            path=f"cli.commands[{command_path}].arguments[{baseline_argument['name']}]",
        )

    baseline_options = _index_contract_items(
        [value for value in baseline_parameters if value.get("kind") == "option"],
        key="name",
        path=f"baseline options for {command_path}",
    )
    candidate_options = _index_contract_items(
        [value for value in candidate_parameters if value.get("kind") == "option"],
        key="name",
        path=f"candidate options for {command_path}",
    )
    for name, baseline_option in baseline_options.items():
        candidate_option = candidate_options.get(name)
        if candidate_option is None:
            _compatibility_break(
                f"cli.commands[{command_path}].options[{name}]",
                "option was removed",
            )
        _validate_click_parameter(
            baseline_option,
            candidate_option,
            path=f"cli.commands[{command_path}].options[{name}]",
        )
        _require_compatible_subset(
            _sequence(
                baseline_option.get("names"), f"baseline option names for {name}"
            ),
            _sequence(
                candidate_option.get("names"), f"candidate option names for {name}"
            ),
            f"cli.commands[{command_path}].options[{name}].names",
        )
        for field in ("is_flag", "flag_value", "count"):
            _require_compatible_equal(
                baseline_option.get(field),
                candidate_option.get(field),
                f"cli.commands[{command_path}].options[{name}].{field}",
            )
    for name, candidate_option in candidate_options.items():
        if (
            name not in baseline_options
            and candidate_option.get("required") is not False
        ):
            _compatibility_break(
                f"cli.commands[{command_path}].options[{name}]",
                "new options must be optional",
            )


def _validate_click_parameter(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    path: str,
) -> None:
    for field in ("kind", "name", "multiple", "nargs"):
        _require_compatible_equal(
            baseline.get(field), candidate.get(field), f"{path}.{field}"
        )
    if baseline.get("required") is False and candidate.get("required") is not False:
        _compatibility_break(f"{path}.required", "an optional input became required")
    if "default" in baseline:
        _require_compatible_equal(
            baseline["default"], candidate.get("default"), f"{path}.default"
        )
    _validate_click_type(
        _mapping(baseline.get("type"), f"baseline type at {path}"),
        _mapping(candidate.get("type"), f"candidate type at {path}"),
        path=f"{path}.type",
    )


def _validate_click_type(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    path: str,
) -> None:
    for field, baseline_value in baseline.items():
        if field == "choices":
            _require_compatible_subset(
                _sequence(baseline_value, f"baseline choices at {path}"),
                _sequence(candidate.get(field), f"candidate choices at {path}"),
                f"{path}.choices",
            )
            continue
        if field not in candidate:
            _compatibility_break(f"{path}.{field}", "type constraint was removed")
        _require_compatible_equal(baseline_value, candidate[field], f"{path}.{field}")


def _validate_python_compatibility(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> None:
    for section in ("top_level", "advanced"):
        baseline_symbols = _index_contract_items(
            _sequence(baseline.get(section), f"baseline.python.{section}"),
            key="import_path",
            path=f"baseline.python.{section}",
        )
        candidate_symbols = _index_contract_items(
            _sequence(candidate.get(section), f"candidate.python.{section}"),
            key="import_path",
            path=f"candidate.python.{section}",
        )
        for import_path, baseline_symbol in baseline_symbols.items():
            candidate_symbol = candidate_symbols.get(import_path)
            if candidate_symbol is None:
                _compatibility_break(
                    f"python.{section}[{import_path}]", "symbol was removed"
                )
            for field in ("kind", "name", "module"):
                if field in baseline_symbol:
                    _require_compatible_equal(
                        baseline_symbol[field],
                        candidate_symbol.get(field),
                        f"python.{section}[{import_path}].{field}",
                    )
            if "parameters" in baseline_symbol:
                _validate_python_parameters(
                    _sequence(
                        baseline_symbol.get("parameters"),
                        f"baseline parameters for {import_path}",
                    ),
                    _sequence(
                        candidate_symbol.get("parameters"),
                        f"candidate parameters for {import_path}",
                    ),
                    import_path=import_path,
                )
                _require_compatible_equal(
                    baseline_symbol.get("return_annotation"),
                    candidate_symbol.get("return_annotation"),
                    f"python.{section}[{import_path}].return_annotation",
                )


def _validate_python_parameters(
    baseline: Sequence[Any],
    candidate: Sequence[Any],
    *,
    import_path: str,
) -> None:
    baseline_parameters = [
        _mapping(value, f"baseline parameter for {import_path}") for value in baseline
    ]
    candidate_parameters = [
        _mapping(value, f"candidate parameter for {import_path}") for value in candidate
    ]
    candidate_by_name = {
        str(value.get("name")): (index, value)
        for index, value in enumerate(candidate_parameters)
    }
    prior_index = -1
    baseline_names: set[str] = set()
    for baseline_parameter in baseline_parameters:
        name = str(baseline_parameter.get("name"))
        baseline_names.add(name)
        match = candidate_by_name.get(name)
        if match is None:
            _compatibility_break(
                f"python[{import_path}].parameters[{name}]", "parameter was removed"
            )
        index, candidate_parameter = match
        if index <= prior_index:
            _compatibility_break(
                f"python[{import_path}].parameters", "parameter order changed"
            )
        prior_index = index
        for field in ("kind", "annotation"):
            _require_compatible_equal(
                baseline_parameter.get(field),
                candidate_parameter.get(field),
                f"python[{import_path}].parameters[{name}].{field}",
            )
        if (
            baseline_parameter.get("required") is False
            and candidate_parameter.get("required") is not False
        ):
            _compatibility_break(
                f"python[{import_path}].parameters[{name}].required",
                "an optional parameter became required",
            )
        if baseline_parameter.get("required") is False:
            _require_compatible_equal(
                baseline_parameter.get("default"),
                candidate_parameter.get("default"),
                f"python[{import_path}].parameters[{name}].default",
            )
    for candidate_parameter in candidate_parameters:
        name = str(candidate_parameter.get("name"))
        if name in baseline_names:
            continue
        if (
            candidate_parameter.get("required") is not False
            or candidate_parameter.get("kind") != "keyword_only"
        ):
            _compatibility_break(
                f"python[{import_path}].parameters[{name}]",
                "new parameters must be optional keyword-only parameters",
            )


def _validate_supported_schema_compatibility(
    baseline: Sequence[Any], candidate: Sequence[Any]
) -> None:
    baseline_schemas = _index_contract_items(
        baseline, key="identifier", path="baseline persisted schemas"
    )
    candidate_schemas = _index_contract_items(
        candidate, key="identifier", path="candidate persisted schemas"
    )
    for identifier, baseline_schema in baseline_schemas.items():
        candidate_schema = candidate_schemas.get(identifier)
        if candidate_schema is None:
            _compatibility_break(
                f"persisted_schemas.supported[{identifier}]",
                "supported schema was removed",
            )
        _require_compatible_equal(
            baseline_schema,
            candidate_schema,
            f"persisted_schemas.supported[{identifier}]",
        )


def _index_contract_items(
    values: Sequence[Any],
    *,
    key: str,
    path: str,
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(values):
        item = _mapping(value, f"{path}[{index}]")
        identity = item.get(key)
        if not isinstance(identity, str) or not identity:
            raise ValueError(f"{path}[{index}].{key} must be a non-empty string")
        if identity in indexed:
            raise ValueError(f"{path} contains duplicate {key} {identity!r}")
        indexed[identity] = item
    return indexed


def _require_compatible_equal(baseline: object, candidate: object, path: str) -> None:
    if candidate != baseline:
        _compatibility_break(path, f"changed from {baseline!r} to {candidate!r}")


def _require_compatible_subset(
    baseline: Sequence[Any], candidate: Sequence[Any], path: str
) -> None:
    missing = [value for value in baseline if value not in candidate]
    if missing:
        _compatibility_break(path, f"removed supported value {missing[0]!r}")


def _compatibility_break(path: str, detail: str) -> Never:
    raise RuntimeError(f"public-interface compatibility break at {path}: {detail}")


def _snapshot_signature(value: Any) -> tuple[list[dict[str, Any]], str | None]:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return [], None
    parameters = [
        {
            "annotation": _annotation_label(parameter.annotation),
            "default": _json_default(parameter.default),
            "kind": parameter.kind.name.lower(),
            "name": parameter.name,
            "required": parameter.default is inspect.Parameter.empty,
        }
        for parameter in signature.parameters.values()
    ]
    return parameters, _annotation_label(signature.return_annotation)


def _annotation_label(value: object) -> str | None:
    if value is inspect.Parameter.empty:
        return None
    if isinstance(value, str):
        return value
    return inspect.formatannotation(value)


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
        entry["count"] = parameter.count
        entry["flag_value"] = _json_default(parameter.flag_value)
        entry["is_flag"] = parameter.is_flag
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
