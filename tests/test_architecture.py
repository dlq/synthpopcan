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
    "exchange",
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
    "synthpopcan.jobs",
    "synthpopcan.runs",
    "synthpopcan.web",
    "synthpopcan.webapi",
    "synthpopcan.webapp",
    "synthpopcan.workflows",
)

API_BOUNDARY_IMPORTS = tuple(
    root
    for root in UI_BOUNDARY_IMPORTS
    if root not in {"synthpopcan.jobs", "synthpopcan.runs", "synthpopcan.workflows"}
)

ADAPTER_MODULES = ("cli", "webapi", "webapp")

WORKFLOW_BOUNDARY_IMPORTS = (
    "click",
    "fastapi",
    "rich",
    "synthpopcan.cli",
    "synthpopcan.cli_output",
    "synthpopcan.console",
    "synthpopcan.jobs",
    "synthpopcan.runs",
    "synthpopcan.web",
    "synthpopcan.webapi",
    "synthpopcan.webapp",
)

RUNTIME_BOUNDARY_IMPORTS = (
    "click",
    "fastapi",
    "rich",
    "synthpopcan.cli",
    "synthpopcan.cli_output",
    "synthpopcan.console",
    "synthpopcan.web",
    "synthpopcan.webapi",
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


def test_ci_exposes_a_stable_required_check_for_the_python_matrix() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "  python-summary:\n    name: Python\n" in workflow
    assert "    if: ${{ always() }}\n    needs: python\n" in workflow
    assert 'run: test "$PYTHON_MATRIX_RESULT" = "success"' in workflow


def test_beginner_api_does_not_depend_on_cli_or_web_adapters() -> None:
    imports = module_imports(PACKAGE_ROOT / "api.py")

    assert forbidden_imports(imports, API_BOUNDARY_IMPORTS) == []


def test_core_modules_do_not_depend_on_cli_or_ui_modules() -> None:
    violations: dict[str, list[str]] = {}

    for module_name in CORE_MODULES:
        imports = module_imports(PACKAGE_ROOT / f"{module_name}.py")
        forbidden = forbidden_imports(imports, UI_BOUNDARY_IMPORTS)
        if forbidden:
            violations[f"synthpopcan.{module_name}"] = forbidden

    assert violations == {}


def test_adapter_modules_do_not_import_each_other_backwards() -> None:
    forbidden_by_module = {
        "cli": ("synthpopcan.webapi",),
        "webapi": ("synthpopcan.cli", "synthpopcan.webapp"),
        "webapp": ("synthpopcan.cli",),
    }
    violations = {
        module_name: forbidden_imports(
            module_imports(PACKAGE_ROOT / f"{module_name}.py"),
            forbidden_by_module[module_name],
        )
        for module_name in ADAPTER_MODULES
    }

    assert violations == {module_name: [] for module_name in ADAPTER_MODULES}


def test_workflows_do_not_depend_on_ui_or_runtime_adapters() -> None:
    violations = {
        str(path): forbidden_imports(
            module_imports(path),
            WORKFLOW_BOUNDARY_IMPORTS,
        )
        for path in sorted((PACKAGE_ROOT / "workflows").glob("*.py"))
    }

    assert violations == {path: [] for path in violations}


def test_run_store_and_job_runner_do_not_depend_on_ui_adapters() -> None:
    violations = {
        module_name: forbidden_imports(
            module_imports(PACKAGE_ROOT / f"{module_name}.py"),
            RUNTIME_BOUNDARY_IMPORTS,
        )
        for module_name in ("runs", "jobs")
    }

    assert violations == {"runs": [], "jobs": []}


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
