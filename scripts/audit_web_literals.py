"""Inventory JavaScript string and template expressions using the locked Biome parser.

Run after ``npm ci``. Entries are candidates for human review, not translations
or an automatic determination that a value is safe to localize.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NODE = re.compile(
    r"\b(JS_STRING_LITERAL_EXPRESSION|JS_TEMPLATE_EXPRESSION)@(\d+)\.\.(\d+)"
)
_PRESENTATION_ASSIGNMENT = re.compile(
    r"(?:^|[;{}])\s*[\w.$\[\]]+\.(?:textContent|innerText)\s*=\s*$"
)
_MACHINE_ASSIGNMENT = re.compile(
    r"(?:^|[;{}])\s*[\w.$\[\]]+\.(?:className|id|type|href|download)\s*=\s*$"
)
_DOM_MACHINE_CALL = re.compile(
    r"\b(?:createElement|getElementById|querySelector|querySelectorAll)\(\s*$"
)

# Each module review is bound to its exact source hash. Changed files fall back
# to syntax-based classification and cannot inherit a stale human review.
_REVIEWED_MODULES = {
    "cli-commands.mjs": (
        "cf34a05e4df4f7cf237cb9b139ef7d696fe21445e294b7ec108f92b7a062780a",
        "generated-shell-mixed-preserve",
        frozenset(),
    ),
    "csv.mjs": (
        "8e88d5bd7222c3823da398cc11a666b32d5775bb2cb02c93be32d8068c07802e",
        "machine-data-or-protocol-preserve",
        frozenset({82}),
    ),
    "preview.mjs": (
        "b9d9579e016ff44cedba75175a5ebaca6c51e2b9d1cc007a753c179247eb4913",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "run-api.mjs": (
        "77ee17fa9b9ee826a54d08152f7b3ad2c5c7e3eff0bce9c2d2f5721db6b16f22",
        "machine-data-or-protocol-preserve",
        frozenset({16}),
    ),
    "run-events.mjs": (
        "2a8d10560cd88dc5e61106da9774cdfa1bb0295b9dfd2e42582cc5b03d72827b",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "small-area-request.mjs": (
        "c1468a9e64e7f819a848f15b94244e26608ccddb3263fca1d0c281b6556ca63b",
        "machine-data-or-protocol-preserve",
        frozenset({4, 8, 10, 12, 15, 21, 24}),
    ),
    "starter-files.mjs": (
        "44262810ba6e9e604245825dbf62a2c228bb4bc4650fb0c708958e1c57698520",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "http.mjs": (
        "01286aaf1228e533ea1095498ef9de7ce32d5698ec41e15c02921fea6c7539f4",
        "machine-data-or-protocol-preserve",
        frozenset({4}),
    ),
    "form-utils.mjs": (
        "be827e2bf3974227adb336e65b042a8f028abac41116096db8bda3c2628be6c4",
        "machine-data-or-protocol-preserve",
        frozenset({35, 49}),
    ),
    "run-list.mjs": (
        "0bc822cef7bc07bbdf6f371cc4fb6e5985196fe0ee17c445d9cb52846cf7cee3",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "run-workbench-model.mjs": (
        "777f28d3246b7bb576138c3976fed27a28e1f71f5685d85dd1c1679578c91844",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "runs-workbench.mjs": (
        "2906b0c39cd0e6de76d2b5ca84b540a69dc076e60d669d09000e44fb6710d80b",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "small-area-workflow.mjs": (
        "e89c1510f680194374f90a8c9976b743821b5d6c8343cb249b8da5f319bdfbad",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "app.mjs": (
        "36e731b109a5d4ea191ca5de5f45a5524df5b80334499198f412e024ff7656df",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "result-ui.mjs": (
        "e09a57e761df3841f26338efabaaf4bacc54b55773932c45c94f605b44a817fc",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
}

_REVIEWED_PRESENTATION = {
    "run-list.mjs": {(32, '"Model"'), (33, '"Small area"'), (34, '"IPF"')},
}

_REVIEWED_PRESENTATION_LINES = {
    "run-workbench-model.mjs": frozenset(
        {
            129,
            130,
            131,
            132,
            133,
            134,
            135,
            137,
            139,
            147,
            153,
            157,
            158,
            159,
            160,
            168,
            41,
            170,
            171,
            172,
            176,
            177,
            178,
            52,
            53,
            54,
            182,
            56,
            58,
            59,
            60,
            61,
            186,
            63,
            187,
            71,
            80,
            81,
            82,
            85,
            87,
            88,
            89,
            90,
            91,
            93,
            101,
            103,
            104,
            107,
            108,
            109,
            111,
            113,
            124,
            125,
            126,
        }
    ),
    "runs-workbench.mjs": frozenset(
        {
            387,
            520,
            265,
            328,
            329,
            525,
            207,
            657,
            662,
            663,
            280,
            342,
            730,
            667,
            221,
            290,
            739,
            292,
            233,
            171,
            491,
            749,
            301,
            751,
            752,
            243,
            500,
            373,
            695,
            443,
            381,
        }
    ),
    "small-area-workflow.mjs": frozenset(
        {193, 162, 163, 39, 168, 167, 169, 170, 171, 174, 176, 18, 181, 86}
    ),
    "result-ui.mjs": frozenset({154, 156, 157}),
}
_REVIEWED_MACHINE_EXCEPTIONS = {
    "run-workbench-model.mjs": {(176, '"model"'), (177, '"small_area"')},
    "runs-workbench.mjs": {
        (280, '""'),
        (221, '"warning"'),
        (265, '"warning"'),
        (207, '"success"'),
        (662, '""'),
        (290, '"success"'),
        (695, '""'),
        (233, '""'),
        (373, '""'),
        (302, '""'),
        (443, '"warning"'),
        (667, '""'),
        (525, '"success"'),
        (663, '""'),
        (500, '"success"'),
        (243, '"success"'),
        (387, '"success"'),
        (292, '"error"'),
    },
    "result-ui.mjs": {(156, '""')},
}
_REVIEWED_MIXED_LINES = {
    "runs-workbench.mjs": frozenset(),
    "small-area-workflow.mjs": frozenset({112, 109, 110, 111}),
    "app.mjs": frozenset({17}),
}


def reviewed_module_role(
    name: str, digest: str, line: int, text: str = ""
) -> str | None:
    """Apply a source-bound review; a modified file requires fresh review."""
    policy = _REVIEWED_MODULES.get(name)
    if policy is None or digest != policy[0]:
        return None
    if line in _REVIEWED_MIXED_LINES.get(name, frozenset()):
        return "web-presentation-and-control-mixed-preserve"
    if (line, text) in _REVIEWED_PRESENTATION.get(name, set()):
        return "web-presentation-candidate"
    if line in _REVIEWED_PRESENTATION_LINES.get(name, frozenset()) and (
        line,
        text,
    ) not in _REVIEWED_MACHINE_EXCEPTIONS.get(name, set()):
        return "web-presentation-candidate"
    return "web-error-message-candidate" if line in policy[2] else policy[1]


def expression_role(source: bytes, start: int) -> str:
    """Classify only direct, unambiguous sinks; keep other uses under review."""
    line_start = source.rfind(b"\n", 0, start) + 1
    prefix = source[line_start:start].decode("utf-8")
    if _PRESENTATION_ASSIGNMENT.search(prefix):
        return "direct-presentation-candidate"
    if _MACHINE_ASSIGNMENT.search(prefix) or _DOM_MACHINE_CALL.search(prefix):
        return "dom-identifier-or-structure-preserve"
    return "review-required"


def inventory_file(path: Path, parser: Path) -> dict[str, Any]:
    """Read parser byte ranges and preserve each expression's exact source text."""
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    result = subprocess.run(
        [str(parser), "inspect", "file", str(path), "--colors=off"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    entries = []
    for match in NODE.finditer(result.stdout):
        start, end = int(match[2]), int(match[3])
        if start >= end or end > len(source):
            raise ValueError(f"invalid parser range {start}..{end} for {path}")
        text = source[start:end].decode("utf-8").strip()
        if not text.startswith(('"', "'", "`")):
            raise ValueError(f"unexpected expression at {path}:{start}")
        line = source[:start].count(b"\n") + 1
        reviewed = reviewed_module_role(path.name, digest, line, text)
        syntax_role = expression_role(source, start)
        entries.append(
            {
                "line": line,
                "start_byte": start,
                "end_byte": end,
                "kind": "template"
                if match[1] == "JS_TEMPLATE_EXPRESSION"
                else "string",
                "source": text,
                "role": syntax_role
                if syntax_role == "direct-presentation-candidate"
                else reviewed or syntax_role,
            }
        )
    return {"source_sha256": digest, "entries": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    biome = ROOT / "node_modules/.bin/biome"
    if not biome.is_file():
        parser.error(
            "Biome is unavailable; run npm ci before generating this inventory"
        )
    report = {
        "scope": "JavaScript string and template expressions; roles require review",
        "files": {
            path.relative_to(ROOT).as_posix(): inventory_file(path, biome)
            for path in sorted((ROOT / "src/synthpopcan/web").rglob("*.mjs"))
        },
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
