from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from pathlib import Path

PACKAGE_ROOT = Path("src/synthpopcan")

MODULE_LAYERS = {
    "facade": frozenset({"__init__", "api"}),
    "adapter": frozenset(
        {
            "cli",
            "cli_enrichment",
            "cli_exchange",
            "cli_geo",
            "cli_ipf",
            "cli_microdata",
            "cli_output",
            "cli_tree",
            "console",
            "web.__init__",
            "web_wds",
            "webapi",
            "webapp",
        }
    ),
    "workflow": frozenset(
        {
            "workflows.__init__",
            "workflows.enrichment",
            "workflows.ipf",
            "workflows.models",
            "workflows.small_area",
            "workflows.types",
        }
    ),
    "runtime": frozenset({"_runtime_schemas", "assurance", "jobs", "runs"}),
    "contract": frozenset(
        {
            "_archive_correction",
            "_census_profile",
            "_interface",
            "_version",
            "contracts.__init__",
            "linked_schema",
            "model_licensing",
            "models.__init__",
        }
    ),
    "domain": frozenset(
        {
            "benchmarks",
            "calibration",
            "canfed",
            "control_packs",
            "controls",
            "da_proof",
            "diagnostics",
            "enrichment",
            "exchange",
            "external_comparison",
            "geodata",
            "geography",
            "ipf",
            "localdata",
            "map_render",
            "methodological_validation",
            "methodology",
            "microdata",
            "national_da",
            "national_execution",
            "national_small_area",
            "odef",
            "small_area_controls",
            "small_area_synthesis",
            "sources",
            "statcan",
            "tabular",
            "tree",
            "tree_benchmark",
            "validation",
        }
    ),
}

FEATURE_CLI_MODULES = (
    "cli_enrichment",
    "cli_exchange",
    "cli_geo",
    "cli_ipf",
    "cli_microdata",
    "cli_tree",
)

EAGER_FACADE_IMPORT_EXCEPTIONS = frozenset({"_interface"})

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
        if imported.startswith("synthpopcan.")
        and imported not in {"synthpopcan._version", "synthpopcan.api"}
    )

    assert forbidden == []


def test_package_declares_inline_typing_support() -> None:
    assert (PACKAGE_ROOT / "py.typed").is_file()


def test_every_package_module_has_exactly_one_responsibility_layer() -> None:
    actual = {
        module_name(path)
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    assignments = {
        module: sorted(
            layer
            for layer, layer_modules in MODULE_LAYERS.items()
            if module in layer_modules
        )
        for module in actual | set().union(*MODULE_LAYERS.values())
    }

    invalid = {
        module: layers for module, layers in assignments.items() if len(layers) != 1
    }
    assert invalid == {}
    assert set(assignments) == actual


def test_feature_cli_modules_do_not_import_sibling_feature_adapters() -> None:
    violations: dict[str, list[str]] = {}
    for module_name_value in FEATURE_CLI_MODULES:
        forbidden = tuple(
            f"synthpopcan.{sibling}"
            for sibling in FEATURE_CLI_MODULES
            if sibling != module_name_value
        )
        imported = forbidden_imports(
            module_imports(PACKAGE_ROOT / f"{module_name_value}.py"),
            forbidden,
        )
        if imported:
            violations[module_name_value] = imported

    assert violations == {}


def test_internal_modules_do_not_import_the_eager_package_facade() -> None:
    violations = {
        module_name(path): ["synthpopcan"]
        for path in PACKAGE_ROOT.rglob("*.py")
        if module_name(path) != "__init__"
        and module_name(path) not in EAGER_FACADE_IMPORT_EXCEPTIONS
        and "synthpopcan" in module_imports(path)
    }

    assert violations == {}


def test_ci_exposes_a_stable_required_check_for_the_python_matrix() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    assert "  python-summary:\n    name: Python\n" in workflow
    assert "    if: ${{ always() }}\n    needs: [quality, python]\n" in workflow
    assert "run: uv run --locked pyright src scripts" in workflow
    pyright_config = json.loads(Path("pyrightconfig.json").read_text())
    assert "scripts" not in pyright_config["exclude"]
    assert 'test "$QUALITY_RESULT" = "success"' in workflow
    assert 'test "$PYTHON_MATRIX_RESULT" = "success"' in workflow


def test_ci_browser_install_is_bounded_and_headless_only() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    web_job = workflow.split("  web:\n", maxsplit=1)[1]
    assert "    timeout-minutes: 15\n" in web_job
    assert "      - name: Install Chromium\n        timeout-minutes: 6\n" in web_job
    assert "run: npx playwright install --with-deps --only-shell chromium" in web_job


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


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)


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
