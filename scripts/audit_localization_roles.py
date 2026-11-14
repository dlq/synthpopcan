"""Record conservative Python string roles and output sinks for localization review."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def call_name(node: ast.Call) -> str:
    """Return the syntactic call target without evaluating it."""
    return ast.unparse(node.func)


def sink_role(name: str) -> str | None:
    """Classify known event, logging, and mixed console output boundaries."""
    if name in {"_error_response", "JSONResponse"}:
        return "http-json-response-preserve"
    if name.endswith(".append_event") or name in {
        "WorkflowProgress",
        "_emit",
        "progress",
    }:
        return "durable-or-callback-progress-preserve"
    if name in {
        "print",
        "click.echo",
        "click.secho",
        "sys.stdout.write",
        "sys.stderr.write",
    } or name.endswith(".print"):
        return "console-mixed-human-and-machine-preserve"
    if name.startswith("logging.") or name.startswith("logger."):
        return "automation-log-preserve"
    return None


def click_decorator_role(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    """Separate direct Click help text from names, options, and defaults."""
    parent = parents.get(node)
    call = parents.get(parent) if isinstance(parent, ast.keyword) else parent
    if not isinstance(call, ast.Call):
        return None
    owner = parents.get(call)
    if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    if call not in owner.decorator_list:
        return None
    name = call_name(call)
    if name not in {
        "click.option",
        "click.argument",
        "click.group",
        "click.command",
    } and not name.endswith((".command", ".group")):
        return None
    if isinstance(parent, ast.keyword):
        if parent.arg in {"help", "short_help", "prompt"}:
            return "click-help-or-prompt-candidate"
        return "click-parameter-machine-preserve"
    if node in call.args:
        return "click-parameter-machine-preserve"
    return None


def literal_role(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """Assign only context-backed roles; do not infer safety from English wording."""
    parent = parents.get(node)
    click_role = click_decorator_role(node, parents)
    if click_role:
        return click_role
    if isinstance(parent, ast.Dict) and node in parent.keys:
        return "mapping-key-preserve"
    if isinstance(parent, ast.Expr) and isinstance(
        parents.get(parent),
        (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        return "docstring-mixed-help-api-or-maintainer"
    current = parent
    while current is not None and not isinstance(
        current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
    ):
        if isinstance(current, ast.Call):
            role = sink_role(call_name(current))
            if role:
                return role
        if isinstance(current, ast.Raise):
            return "exception-mixed-api-cli-web-preserve"
        if isinstance(current, ast.Dict) and node in current.values:
            return "structured-value-mixed-preserve"
        current = parents.get(current)
    return "unresolved-preserve-until-reviewed"


def inventory_file(path: Path) -> dict[str, Any]:
    """Locate expressions and output sinks using the file's parsed syntax tree."""
    source = path.read_text()
    tree = ast.parse(source)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    literals = []
    sinks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = call_name(node)
            role = sink_role(name)
            if role:
                sinks.append(
                    {
                        "line": node.lineno,
                        "column": node.col_offset,
                        "call": name,
                        "role": role,
                    }
                )
        if not isinstance(node, (ast.Constant, ast.JoinedStr)):
            continue
        if isinstance(node, ast.Constant) and not isinstance(node.value, str):
            continue
        if isinstance(parents.get(node), ast.JoinedStr):
            continue
        literals.append(
            {
                "line": node.lineno,
                "column": node.col_offset,
                "role": literal_role(node, parents),
            }
        )
    literals.sort(key=lambda entry: (entry["line"], entry["column"]))
    sinks.sort(key=lambda entry: (entry["line"], entry["column"]))
    return {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "literals": literals,
        "output_sinks": sinks,
    }


def build_inventory(root: Path) -> dict[str, Any]:
    paths = sorted((root / "src/synthpopcan").rglob("*.py"))
    paths += sorted((root / "scripts").glob("*.py"))
    files = {path.relative_to(root).as_posix(): inventory_file(path) for path in paths}
    counts = Counter(
        entry["role"] for value in files.values() for entry in value["literals"]
    )
    return {
        "scope": "Python package and maintainer scripts; context-backed roles only",
        "counts": dict(sorted(counts.items())),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(build_inventory(ROOT), ensure_ascii=False, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
