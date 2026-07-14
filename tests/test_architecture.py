from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

PACKAGE_ROOT = Path("src/synthpopcan")

CORE_MODULES = (
    "benchmarks",
    "calibration",
    "controls",
    "diagnostics",
    "ipf",
    "localdata",
    "map_render",
    "microdata",
    "small_area_controls",
    "small_area_synthesis",
    "sources",
    "statcan",
    "tabular",
    "tree",
    "tree_benchmark",
    "validation",
    "web_wds",
)

UI_BOUNDARY_IMPORTS = (
    "click",
    "rich",
    "synthpopcan.cli",
    "synthpopcan.cli_geo",
    "synthpopcan.cli_ipf",
    "synthpopcan.cli_microdata",
    "synthpopcan.cli_output",
    "synthpopcan.cli_tree",
    "synthpopcan.console",
    "synthpopcan.web",
    "synthpopcan.webapp",
)


def test_top_level_package_only_reexports_beginner_api() -> None:
    imports = module_imports(PACKAGE_ROOT / "__init__.py")

    forbidden = sorted(
        imported
        for imported in imports
        if imported.startswith("synthpopcan.") and imported != "synthpopcan.api"
    )

    assert forbidden == []


def test_package_declares_inline_typing_support() -> None:
    assert (PACKAGE_ROOT / "py.typed").is_file()


def test_beginner_api_does_not_depend_on_cli_or_web_adapters() -> None:
    imports = module_imports(PACKAGE_ROOT / "api.py")

    assert forbidden_imports(imports, UI_BOUNDARY_IMPORTS) == []


def test_core_modules_do_not_depend_on_cli_or_ui_modules() -> None:
    violations: dict[str, list[str]] = {}

    for module_name in CORE_MODULES:
        imports = module_imports(PACKAGE_ROOT / f"{module_name}.py")
        forbidden = forbidden_imports(imports, UI_BOUNDARY_IMPORTS)
        if forbidden:
            violations[f"synthpopcan.{module_name}"] = forbidden

    assert violations == {}


def module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    return imports


def forbidden_imports(
    imports: Iterable[str],
    forbidden_roots: Iterable[str],
) -> list[str]:
    return sorted(
        imported
        for imported in imports
        if any(
            imported == root or imported.startswith(f"{root}.")
            for root in forbidden_roots
        )
    )
