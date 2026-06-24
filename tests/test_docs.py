from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path


def test_helper_modules_declare_public_exports() -> None:
    for module_name in (
        "synthpopcan.cli_ipf",
        "synthpopcan.cli_output",
        "synthpopcan.console",
        "synthpopcan.controls",
        "synthpopcan.localdata",
        "synthpopcan.sources",
    ):
        module = importlib.import_module(module_name)
        exports = getattr(module, "__all__", None)

        assert exports, f"{module_name} should declare public exports"
        for name in exports:
            assert not name.startswith("_"), f"{module_name} exports private {name}"
            assert hasattr(module, name), f"{module_name}.{name} is missing"


def test_api_reference_members_exist_and_have_docstrings() -> None:
    members_by_module = parse_api_reference_members(Path("docs/api.rst"))

    assert members_by_module
    for module_name, member_names in members_by_module.items():
        module = importlib.import_module(module_name)
        for member_name in member_names:
            assert hasattr(module, member_name), (
                f"{module_name}.{member_name} is missing"
            )
            docstring = inspect.getdoc(getattr(module, member_name))
            assert docstring, f"{module_name}.{member_name} has no docstring"
            assert len(docstring.split()) >= 8, (
                f"{module_name}.{member_name} docstring is too thin"
            )


def parse_api_reference_members(path: Path) -> dict[str, list[str]]:
    """Return explicit autodoc members declared in ``docs/api.rst``."""

    members_by_module: dict[str, list[str]] = {}
    current_module: str | None = None
    collecting_members = False
    for line in path.read_text().splitlines():
        module_match = re.match(r"^\.\. automodule::\s+(\S+)", line)
        if module_match:
            current_module = module_match.group(1)
            collecting_members = False
            continue
        if current_module is None:
            continue
        stripped = line.strip()
        if stripped.startswith(":members:"):
            collecting_members = True
            members_by_module.setdefault(current_module, []).extend(
                split_members(stripped.removeprefix(":members:"))
            )
            continue
        if collecting_members and line.startswith("             "):
            members_by_module.setdefault(current_module, []).extend(
                split_members(stripped)
            )
            continue
        if stripped.startswith(":") or not stripped:
            continue
        collecting_members = False
    return {
        module_name: member_names
        for module_name, member_names in members_by_module.items()
        if member_names
    }


def split_members(raw_members: str) -> list[str]:
    return [member.strip() for member in raw_members.split(",") if member.strip()]
