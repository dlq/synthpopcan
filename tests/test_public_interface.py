from __future__ import annotations

import copy
import json
import subprocess
import sys
import typing
from pathlib import Path

import pytest
from click.testing import CliRunner

import synthpopcan
import synthpopcan._interface as interface
from synthpopcan._interface import (
    load_public_interface_baseline,
    load_public_interface_contract,
    validate_installed_public_interface,
    validate_public_interface_compatibility,
)
from synthpopcan.cli import cli


def test_packaged_public_interface_is_current_and_semantically_valid() -> None:
    contract = load_public_interface_contract()

    check = subprocess.run(
        [sys.executable, "scripts/build_public_interface.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr or check.stdout
    assert contract["schema_version"] == "synthpopcan-public-interface-v1"
    assert contract["effective_from"] == "1.0.0"
    validate_public_interface_compatibility(load_public_interface_baseline(), contract)
    validate_installed_public_interface()


def test_public_interface_baseline_cannot_be_refrozen() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_public_interface.py", "--freeze-baseline"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "must not be replaced" in result.stderr


def test_contract_covers_every_documented_advanced_api_member() -> None:
    contract = load_public_interface_contract()
    top_level = contract["python"]["top_level"]
    advanced = contract["python"]["advanced"]

    assert [item["name"] for item in top_level] == synthpopcan.__all__
    assert len(advanced) == 166
    assert len({item["import_path"] for item in advanced}) == len(advanced)
    assert all(item["module"].startswith("synthpopcan.") for item in advanced)
    modules = {item["module"] for item in advanced}
    assert "synthpopcan.national_small_area" in modules
    assert "synthpopcan.da_proof" not in modules
    assert "synthpopcan.national_execution" not in modules


def test_contract_freezes_python_annotations_and_click_flag_semantics() -> None:
    contract = load_public_interface_contract()
    symbols = [
        *contract["python"]["top_level"],
        *contract["python"]["advanced"],
    ]
    callables = [item for item in symbols if item["kind"] in {"class", "function"}]

    assert callables
    assert all("return_annotation" in item for item in callables)
    assert all(
        "annotation" in parameter
        for item in callables
        for parameter in item["parameters"]
    )
    fit_ipf = next(
        item
        for item in contract["python"]["top_level"]
        if item["import_path"] == "synthpopcan.fit_ipf"
    )
    assert fit_ipf["return_annotation"] == "IPFResult"
    assert fit_ipf["parameters"][0]["annotation"] == (
        "str | Path | Sequence[Mapping[str, object]]"
    )

    root = next(
        item for item in contract["cli"]["commands"] if item["path"] == "synthpopcan"
    )
    version = next(item for item in root["parameters"] if item["name"] == "version")
    assert version["is_flag"] is True
    assert version["flag_value"] is True
    assert version["count"] is False
    assert all(
        {"is_flag", "flag_value", "count"} <= option.keys()
        for command in contract["cli"]["commands"]
        for option in command["parameters"]
        if option["kind"] == "option"
    )


@pytest.mark.parametrize(
    "annotation",
    [
        "Annotated[str, 'scope']",
        "typing.Annotated[str, 'scope']",
        "typing_extensions.Annotated[str, 'scope']",
        typing.Annotated[str, "scope"],
    ],
)
def test_annotation_labels_are_canonical_across_supported_python_versions(
    annotation: object,
) -> None:
    assert interface._annotation_label(annotation) == "Annotated[str, 'scope']"
    assert (
        interface._annotation_label("typing.Literal['typing.Annotated']")
        == "Literal['typing.Annotated']"
    )
    assert (
        interface._canonical_annotation_text("namespace.typing.Annotated[str, 'scope']")
        == "namespace.typing.Annotated[str, 'scope']"
    )


def test_compatibility_validator_rejects_frozen_interface_breaks() -> None:
    baseline = load_public_interface_baseline()

    removed_command = copy.deepcopy(load_public_interface_contract())
    removed_command["cli"]["commands"] = removed_command["cli"]["commands"][1:]
    with pytest.raises(RuntimeError, match="command was removed"):
        validate_public_interface_compatibility(baseline, removed_command)

    changed_flag = copy.deepcopy(load_public_interface_contract())
    root = next(
        item
        for item in changed_flag["cli"]["commands"]
        if item["path"] == "synthpopcan"
    )
    version = next(item for item in root["parameters"] if item["name"] == "version")
    version["is_flag"] = False
    with pytest.raises(RuntimeError, match="is_flag"):
        validate_public_interface_compatibility(baseline, changed_flag)

    changed_annotation = copy.deepcopy(load_public_interface_contract())
    fit_ipf = next(
        item
        for item in changed_annotation["python"]["top_level"]
        if item["import_path"] == "synthpopcan.fit_ipf"
    )
    fit_ipf["parameters"][0]["annotation"] = "str"
    with pytest.raises(RuntimeError, match="annotation"):
        validate_public_interface_compatibility(baseline, changed_annotation)


def test_compatibility_validator_allows_additive_1x_extensions() -> None:
    baseline = load_public_interface_baseline()
    candidate = copy.deepcopy(load_public_interface_contract())
    root = next(
        item for item in candidate["cli"]["commands"] if item["path"] == "synthpopcan"
    )
    root["parameters"].append(
        {
            "count": False,
            "default": None,
            "flag_value": None,
            "is_flag": False,
            "kind": "option",
            "multiple": False,
            "name": "future_option",
            "names": ["--future-option"],
            "nargs": 1,
            "required": False,
            "type": {"name": "text"},
        }
    )
    candidate["python"]["top_level"].append(
        {
            "import_path": "synthpopcan.future_symbol",
            "kind": "value",
            "name": "future_symbol",
        }
    )
    fit_ipf = next(
        item
        for item in candidate["python"]["top_level"]
        if item["import_path"] == "synthpopcan.fit_ipf"
    )
    fit_ipf["parameters"].append(
        {
            "annotation": "str | None",
            "default": None,
            "kind": "keyword_only",
            "name": "future_parameter",
            "required": False,
        }
    )
    candidate["persisted_schemas"]["supported"].append(
        {
            "documentation": "docs/compatibility.md",
            "identifier": "synthpopcan-future-v1",
            "purpose": "future additive contract",
        }
    )

    validate_public_interface_compatibility(baseline, candidate)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "must be a JSON object"),
        ({"schema_version": "future"}, "unsupported public-interface"),
    ],
)
def test_contract_loader_rejects_invalid_packaged_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
    message: str,
) -> None:
    resource = tmp_path / "contract.json"
    resource.write_text(json.dumps(payload))
    monkeypatch.setattr(interface, "files", lambda _package: tmp_path)

    with pytest.raises(ValueError, match=message):
        interface._load_public_interface_resource(resource.name)


@pytest.mark.parametrize(
    ("surface", "message"),
    [
        ("exports", "top-level Python exports"),
        ("top-level-signature", "top-level Python signatures"),
        ("advanced-signature", "advanced Python API"),
        ("cli", "CLI command tree"),
    ],
)
def test_installed_interface_validator_reports_each_drift_surface(
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    message: str,
) -> None:
    candidate = copy.deepcopy(load_public_interface_contract())
    if surface == "exports":
        candidate["python"]["top_level"] = candidate["python"]["top_level"][:-1]
    elif surface == "top-level-signature":
        symbol = next(
            item for item in candidate["python"]["top_level"] if item.get("parameters")
        )
        symbol["parameters"][0]["annotation"] = "drifted"
    elif surface == "advanced-signature":
        symbol = next(
            item for item in candidate["python"]["advanced"] if item.get("parameters")
        )
        symbol["parameters"][0]["annotation"] = "drifted"
    else:
        command = candidate["cli"]["commands"][0]
        option = next(
            item for item in command["parameters"] if item["kind"] == "option"
        )
        option["is_flag"] = not option["is_flag"]

    monkeypatch.setattr(interface, "load_public_interface_contract", lambda: candidate)
    monkeypatch.setattr(
        interface,
        "validate_public_interface_compatibility",
        lambda _baseline, _candidate: None,
    )

    with pytest.raises(RuntimeError, match=message):
        validate_installed_public_interface()


def test_compatibility_validator_rejects_remaining_break_classes() -> None:
    baseline = load_public_interface_baseline()
    contract = load_public_interface_contract()

    def reject(candidate: dict[str, object], message: str) -> None:
        with pytest.raises((RuntimeError, ValueError), match=message):
            validate_public_interface_compatibility(baseline, candidate)

    candidate = copy.deepcopy(contract)
    command = next(
        item
        for item in candidate["cli"]["commands"]
        if any(parameter["kind"] == "argument" for parameter in item["parameters"])
    )
    argument = next(
        item for item in command["parameters"] if item["kind"] == "argument"
    )
    argument["name"] = f"{argument['name']}_renamed"
    reject(candidate, "positional arguments changed")

    candidate = copy.deepcopy(contract)
    command = candidate["cli"]["commands"][0]
    option = next(item for item in command["parameters"] if item["kind"] == "option")
    command["parameters"].remove(option)
    reject(candidate, "option was removed")

    candidate = copy.deepcopy(contract)
    candidate["cli"]["commands"][0]["parameters"].append(
        {"kind": "option", "name": "required_future", "required": True}
    )
    reject(candidate, "new options must be optional")

    candidate = copy.deepcopy(contract)
    option = next(
        parameter
        for command in candidate["cli"]["commands"]
        for parameter in command["parameters"]
        if parameter["kind"] == "option" and parameter["required"] is False
    )
    option["required"] = True
    reject(candidate, "optional input became required")

    candidate = copy.deepcopy(contract)
    option = next(
        parameter
        for command in candidate["cli"]["commands"]
        for parameter in command["parameters"]
        if parameter["kind"] == "option"
    )
    option["type"].pop("name")
    reject(candidate, "type constraint was removed")

    candidate = copy.deepcopy(contract)
    candidate["python"]["top_level"] = candidate["python"]["top_level"][1:]
    reject(candidate, "symbol was removed")

    candidate = copy.deepcopy(contract)
    symbol = next(
        item
        for item in candidate["python"]["top_level"]
        if len(item.get("parameters", [])) >= 2
    )
    symbol["parameters"] = symbol["parameters"][1:]
    reject(candidate, "parameter was removed")

    candidate = copy.deepcopy(contract)
    symbol = next(
        item
        for item in candidate["python"]["top_level"]
        if len(item.get("parameters", [])) >= 2
    )
    symbol["parameters"][0], symbol["parameters"][1] = (
        symbol["parameters"][1],
        symbol["parameters"][0],
    )
    reject(candidate, "parameter order changed")

    candidate = copy.deepcopy(contract)
    parameter = next(
        parameter
        for symbol in candidate["python"]["top_level"]
        for parameter in symbol.get("parameters", [])
        if parameter["required"] is False
    )
    parameter["required"] = True
    reject(candidate, "optional parameter became required")

    candidate = copy.deepcopy(contract)
    symbol = next(
        item for item in candidate["python"]["top_level"] if item.get("parameters")
    )
    symbol["parameters"].append(
        {
            "annotation": "str",
            "default": None,
            "kind": "positional_or_keyword",
            "name": "required_future",
            "required": True,
        }
    )
    reject(candidate, "new parameters must be optional keyword-only")

    candidate = copy.deepcopy(contract)
    candidate["persisted_schemas"]["supported"] = candidate["persisted_schemas"][
        "supported"
    ][1:]
    reject(candidate, "supported schema was removed")

    candidate = copy.deepcopy(contract)
    candidate["cli"]["commands"][0]["path"] = ""
    reject(candidate, "must be a non-empty string")

    candidate = copy.deepcopy(contract)
    candidate["cli"]["commands"].append(copy.deepcopy(candidate["cli"]["commands"][0]))
    reject(candidate, "contains duplicate path")

    candidate = copy.deepcopy(contract)
    candidate["cli"]["commands"][0]["output_modes"] = []
    reject(candidate, "removed supported value")


def test_interface_snapshot_defensive_helpers() -> None:
    assert interface._snapshot_signature(object()) == ([], None)
    assert interface._json_default(lambda: None) == {"dynamic": True}
    assert interface._canonical_annotation_text("typing.Annotated[") == (
        "typing.Annotated["
    )
    with pytest.raises(ValueError, match="must be an object"):
        interface._mapping(None, "mapping")
    with pytest.raises(ValueError, match="must be an array"):
        interface._sequence(None, "sequence")


def test_contract_covers_the_complete_click_tree_and_common_process_rules(
    tmp_path: Path,
) -> None:
    contract = load_public_interface_contract()
    cli_contract = contract["cli"]
    commands = cli_contract["commands"]
    runner = CliRunner()

    assert cli_contract["entry_point"] == "synthpopcan"
    assert cli_contract["exit_codes"] == {
        "0": "successful command",
        "1": "documented input, data, filesystem, or runtime failure",
        "2": "command-line usage error",
    }
    assert len(commands) >= 60
    assert len({item["path"] for item in commands}) == len(commands)

    for item in commands:
        args = item["path"].split()[1:]
        result = runner.invoke(cli, [*args, "--help"])
        assert result.exit_code == 0, (item["path"], result.output, result.exception)

    json_result = runner.invoke(cli, ["models", "list", "--format", "json"])
    assert json_result.exit_code == 0
    assert isinstance(json.loads(json_result.stdout), dict)
    assert json_result.stderr == ""

    narrated = runner.invoke(
        cli,
        ["data", "example", "ipf", "--out-dir", str(tmp_path / "example")],
    )
    assert narrated.exit_code == 0
    assert "fictional ipf teaching example" in narrated.stdout
    assert "Wrote" in narrated.stderr

    validation_failure = runner.invoke(
        cli,
        ["bundle", "validate", str(tmp_path / "empty"), "--format", "json"],
    )
    assert validation_failure.exit_code == 1
    assert json.loads(validation_failure.stdout)["passed"] is False
    assert "Exchange bundle validation failed" in validation_failure.stderr

    usage_error = runner.invoke(cli, ["--not-a-real-option"])
    assert usage_error.exit_code == 2
    assert usage_error.stdout == ""
    assert "no such option" in usage_error.stderr.lower()

    domain_error = runner.invoke(cli, ["models", "show", "not-a-real-model"])
    assert domain_error.exit_code == 1
    assert domain_error.stdout == ""
    assert "unknown model package" in domain_error.stderr.lower()


def test_persisted_schema_registry_is_disjoint_and_documented() -> None:
    schemas = load_public_interface_contract()["persisted_schemas"]
    supported = schemas["supported"]
    internal = schemas["internal"]
    supported_ids = {item["identifier"] for item in supported}
    internal_ids = {item["identifier"] for item in internal}

    assert len(supported_ids) == len(supported)
    assert len(internal_ids) == len(internal)
    assert supported_ids.isdisjoint(internal_ids)
    assert "synthpopcan-linked-population-v1" in supported_ids
    assert "synthpopcan-exchange-v1" in supported_ids
    assert "synthpopcan-hierarchical-pumf-field-eligibility-v1" in supported_ids
    assert "synthpopcan-public-interface-v1" in supported_ids
    assert "synthpopcan-small-area-linked-calibration-v1" in internal_ids
    for item in supported:
        documentation = Path(item["documentation"])
        assert documentation.is_file(), (item["identifier"], documentation)


def test_public_field_eligibility_inventory_is_complete_and_decodable() -> None:
    path = Path("docs/_static/hierarchical-pumf-field-eligibility-v1.json")
    text = path.read_text()
    inventory = json.loads(text)

    assert inventory["schema_version"] == (
        "synthpopcan-hierarchical-pumf-field-eligibility-v1"
    )
    assert len(inventory["fields"]) == 238
    decoded = json.dumps(inventory, ensure_ascii=False)
    assert "\N{REPLACEMENT CHARACTER}" not in decoded


def test_public_compatibility_policy_names_each_frozen_surface() -> None:
    policy = Path("docs/compatibility.md").read_text()
    normalized_policy = " ".join(policy.split())

    for phrase in (
        "Command-Line Contract",
        "Python Contract",
        "Persisted Artifact Contract",
        "Deprecation and Breaking Changes",
        "synthpopcan-public-interface-v1",
        "standard output",
        "standard error",
        "Exit status",
    ):
        assert phrase in normalized_policy
