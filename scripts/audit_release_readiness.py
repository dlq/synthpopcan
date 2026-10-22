"""Reproduce the 1.2 preparation inventories without network or external writes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _run_json(arguments: list[str]) -> Any:
    result = subprocess.run(
        [sys.executable, "-m", *arguments], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def typing_inventory() -> dict[str, Any]:
    """Count strict findings by scope, rule, and file; omit unstable timings."""
    report = _run_json(
        ["pyright", "--project", "pyrightconfig.strict.json", "--outputjson"]
    )
    diagnostics = report["generalDiagnostics"]
    files: dict[str, Counter[str]] = {}
    for item in diagnostics:
        path = Path(item["file"]).relative_to(ROOT).as_posix()
        files.setdefault(path, Counter())[item.get("rule", item["severity"])] += 1
    return {
        "command": "uv run --locked pyright --project pyrightconfig.strict.json --outputjson",
        "pyright_version": report["version"],
        "files_analyzed": report["summary"]["filesAnalyzed"],
        "errors": report["summary"]["errorCount"],
        "files_with_diagnostics_by_scope": dict(
            Counter(path.split("/")[0] for path in files)
        ),
        "diagnostics_by_rule": dict(
            sorted(
                Counter(
                    item.get("rule", item["severity"]) for item in diagnostics
                ).items()
            )
        ),
        "diagnostics_by_file": {
            path: dict(sorted(counts.items())) for path, counts in sorted(files.items())
        },
        "blocking_strict_paths": json.loads((ROOT / "pyrightconfig.json").read_text())[
            "strict"
        ],
    }


def complexity_inventory() -> dict[str, Any]:
    """Record Ruff complexity for qualified functions and package concentration."""
    findings = _run_json(
        [
            "ruff",
            "check",
            "src",
            "scripts",
            "--select",
            "C901",
            "--ignore-noqa",
            "--config",
            "lint.mccabe.max-complexity=0",
            "--output-format",
            "json",
        ]
    )
    locations = {
        (item["filename"], item["location"]["row"]): int(
            item["message"].rsplit("(", 1)[1].split(" >", 1)[0]
        )
        for item in findings
    }
    functions: dict[str, int] = {}
    modules: dict[str, int] = {}
    for directory in ("src/synthpopcan", "scripts"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text()
            relative = path.relative_to(ROOT).as_posix()
            if directory.startswith("src"):
                modules[relative] = len(source.splitlines())

            def visit(
                node: ast.AST,
                parents: tuple[str, ...] = (),
                filename: str = str(path),
                relative_name: str = relative,
            ) -> None:
                for child in ast.iter_child_nodes(node):
                    if isinstance(
                        child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        names = (*parents, child.name)
                        key = (filename, child.lineno)
                        if key in locations:
                            functions[f"{relative_name}:{'.'.join(names)}"] = locations[
                                key
                            ]
                        visit(child, names)
                    else:
                        visit(child, parents)

            visit(ast.parse(source))
    largest = sorted(modules.items(), key=lambda item: (-item[1], item[0]))[:10]
    return {
        "command": "uv run --locked python scripts/audit_release_readiness.py complexity",
        "metric": "Ruff C901 (including noqa); physical package lines include docstrings/comments",
        "functions": dict(sorted(functions.items())),
        "module_lines": modules,
        "largest_ten_lines": sum(count for _, count in largest),
        "package_lines": sum(modules.values()),
        "above_ten": sum(value > 10 for value in functions.values()),
    }


def localization_inventory() -> dict[str, Any]:
    """Enumerate CLI paths, web routes, and files with explicit translation ownership."""
    return {
        "canonical_locales": ["en-CA", "fr-CA"],
        "default_locale": "en-CA",
        "translation_status": "inventory only; no reviewed product translations or catalogue yet",
        "scope": "All CLI groups/aliases/options, static web routes, package presentation/domain files, maintained docs and historical/source exclusions",
        "python_literals": _python_literal_inventory(),
        "commands": _cli_surfaces(),
        "routes": _web_routes(),
        "files": _file_ownership(),
    }


def _cli_surfaces() -> list[dict[str, Any]]:
    import click

    from synthpopcan.cli import cli

    commands: list[dict[str, Any]] = []

    def walk(command: click.Command, path: str) -> None:
        commands.append(
            {
                "path": path,
                "help": command.help,
                "options": [
                    {"names": option.opts, "help": getattr(option, "help", None)}
                    for option in command.params
                ],
                "human_text": "translate help, prompts, errors, tables; retain names and machine output",
            }
        )
        if isinstance(command, click.Group):
            for name, child in sorted(command.commands.items()):
                walk(child, f"{path} {name}")

    walk(cli, "synthpopcan")
    return commands


def _python_literal_inventory() -> dict[str, Any]:
    literals: dict[str, Any] = {}
    for path in sorted((ROOT / "src/synthpopcan").rglob("*.py")):
        source = path.read_text()
        parsed = ast.parse(source)
        parents = {
            child: parent
            for parent in ast.walk(parsed)
            for child in ast.iter_child_nodes(parent)
        }
        entries: list[tuple[int, str]] = []
        for node in ast.walk(parsed):
            if not isinstance(node, (ast.Constant, ast.JoinedStr)):
                continue
            if isinstance(node, ast.Constant) and not isinstance(node.value, str):
                continue
            parent = parents.get(node)
            if isinstance(parent, ast.JoinedStr):
                continue
            role = "human-or-source-review"
            if isinstance(parent, ast.Dict) and node in parent.keys:
                role = "machine-key-retain"
            elif isinstance(parent, ast.Expr) and isinstance(
                parents.get(parent),
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                role = "docstring-review-cli-help-or-maintainer"
            elif isinstance(parent, (ast.Import, ast.ImportFrom)):
                role = "machine-import-retain"
            entries.append((node.lineno, role))
        literals[path.relative_to(ROOT).as_posix()] = {
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "roles": {
                role: sorted({line for line, category in entries if category == role})
                for role in sorted({category for _, category in entries})
            },
        }
    return literals


def _web_routes() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    tree = ast.parse((ROOT / "src/synthpopcan/webapi.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr
                    in {"get", "post", "delete", "put", "patch", "api_route"}
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    methods = [decorator.func.attr.upper()]
                    if decorator.func.attr == "api_route":
                        methods = [
                            method
                            for keyword in decorator.keywords
                            if keyword.arg == "methods"
                            for method in ast.literal_eval(keyword.value)
                        ]
                    routes.append(
                        {
                            "method": ",".join(methods),
                            "path": decorator.args[0].value,
                            "handler": node.name,
                            "classification": "machine-stable route/JSON; translate human message values only",
                        }
                    )
    return sorted(routes, key=lambda route: (route["path"], route["method"]))


def _file_ownership() -> dict[str, str]:
    files: dict[str, str] = {}
    for directory in ("src/synthpopcan", "docs", "adr", "plans"):
        for path in sorted((ROOT / directory).rglob("*")):
            if not path.is_file() or any(
                part in {"_build", "__pycache__"} for part in path.parts
            ):
                continue
            if path.suffix not in {
                ".py",
                ".js",
                ".mjs",
                ".html",
                ".css",
                ".md",
                ".rst",
                ".json",
            }:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if directory in {"adr", "plans"} or relative.startswith("docs/records/"):
                category = "historical-or-maintainer: retain original evidence; translate separately if needed"
            elif directory == "docs":
                category = "user-documentation: translate prose; preserve commands, code, identifiers and verbatim source quotations"
            elif path.suffix == ".json":
                category = "machine-contract-or-source: preserve keys/IDs/counts; descriptive/source labels require provenance review"
            elif (
                path.name.startswith("cli")
                or path.name in {"console.py", "webapi.py", "webapp.py", "web_wds.py"}
                or "/web/" in relative
            ):
                category = "mixed-presentation: translate human prose; preserve machine keys, URLs, names, logs and identifiers"
            else:
                category = "domain-or-workflow: preserve machine results; inventory human exception/source-label text for adapter translation"
            files[relative] = category
    return files


def main() -> int:
    """Write deterministic inventories or check the complexity ratchet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("typing", "complexity", "localization"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--baseline", type=Path, help="Check complexity against this prior inventory"
    )
    arguments = parser.parse_args()
    report = {
        "typing": typing_inventory,
        "complexity": complexity_inventory,
        "localization": localization_inventory,
    }[arguments.kind]()
    if arguments.baseline:
        if arguments.kind != "complexity":
            parser.error("--baseline requires complexity")
        baseline = json.loads(arguments.baseline.read_text())["functions"]
        failures = [
            f"{name}: {value} > {baseline.get(name, 10)}"
            for name, value in report["functions"].items()
            if value > baseline.get(name, 10)
        ]
        if failures:
            print(
                "Complexity increases require review:\n" + "\n".join(failures),
                file=sys.stderr,
            )
            return 1
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if arguments.output:
        arguments.output.write_text(serialized)
    elif not arguments.baseline:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
