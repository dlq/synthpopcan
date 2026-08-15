from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

import synthpopcan
from synthpopcan._interface import (
    load_public_interface_contract,
    validate_installed_public_interface,
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
    validate_installed_public_interface()


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
