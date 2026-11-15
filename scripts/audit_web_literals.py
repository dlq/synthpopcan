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
        "e4e54f6efe37ca421f5facef296c8ae58231d736c65407c185f1d76cb0f9d7f4",
        "machine-data-or-protocol-preserve",
        frozenset({16}),
    ),
    "run-events.mjs": (
        "a5d3f7d0e893951cb37416c5c1e791d1a196a70fa94724e56984daf32b7d1d01",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "small-area-request.mjs": (
        "c1468a9e64e7f819a848f15b94244e26608ccddb3263fca1d0c281b6556ca63b",
        "machine-data-or-protocol-preserve",
        frozenset({4, 21, 8, 24, 10, 12, 15}),
    ),
    "starter-files.mjs": (
        "44262810ba6e9e604245825dbf62a2c228bb4bc4650fb0c708958e1c57698520",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "http.mjs": (
        "89ae5fe7877e1d2e00f11fa56a39d18ecef4a42b306d58a0d1b1d21efd1b6bef",
        "machine-data-or-protocol-preserve",
        frozenset({11}),
    ),
    "form-utils.mjs": (
        "be827e2bf3974227adb336e65b042a8f028abac41116096db8bda3c2628be6c4",
        "machine-data-or-protocol-preserve",
        frozenset({49, 35}),
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
        "136df4283d81f20d8697078d1d67550db0ca535e1263d0ea3fb7c674024b047d",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "small-area-workflow.mjs": (
        "e89c1510f680194374f90a8c9976b743821b5d6c8343cb249b8da5f319bdfbad",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "app.mjs": (
        "30c9c0fbf44df45d1600e1291e1ac3c8619c2982e8b3fa60a73b653668e1662e",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "result-ui.mjs": (
        "60e80c2aac42d28e1db2ecdac51197ee35f15c1e082ae7cb17fb491bbcfbbc06",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "localization.mjs": (
        "c674e5724f0e99b201024adb2ae532fbe1061d7a24dba85c6eac951b8a54a01f",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "localization-ui.mjs": (
        "c2ef3549e4a592b19c85d08a9d39583f52c26d1a8b476505560858dc6677b99c",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
}

_REVIEWED_PRESENTATION = {
    "run-list.mjs": {(32, '"Model"'), (34, '"IPF"'), (33, '"Small area"')}
}

_REVIEWED_PRESENTATION_LINES = {
    "run-workbench-model.mjs": frozenset(
        {
            41,
            52,
            53,
            54,
            56,
            58,
            59,
            60,
            61,
            63,
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
            170,
            171,
            172,
            176,
            177,
            178,
            182,
            186,
            187,
        }
    ),
    "runs-workbench.mjs": frozenset(
        {
            180,
            216,
            230,
            242,
            252,
            274,
            289,
            299,
            301,
            310,
            311,
            337,
            338,
            351,
            382,
            390,
            396,
            459,
            507,
            516,
            536,
            544,
            682,
            687,
            688,
            692,
            720,
            756,
            765,
            775,
            777,
            778,
        }
    ),
    "small-area-workflow.mjs": frozenset(
        {18, 39, 86, 162, 163, 167, 168, 169, 170, 171, 174, 176, 181, 193}
    ),
    "result-ui.mjs": frozenset({160, 157, 159}),
    "localization.mjs": frozenset({290, 3}),
}

_REVIEWED_MACHINE_EXCEPTIONS = {
    "run-workbench-model.mjs": {(177, '"small_area"'), (176, '"model"')},
    "runs-workbench.mjs": {
        (216, '"success"'),
        (230, '"warning"'),
        (242, '""'),
        (252, '"success"'),
        (274, '"warning"'),
        (289, '""'),
        (299, '"success"'),
        (301, '"error"'),
        (311, '""'),
        (382, '""'),
        (396, '"success"'),
        (459, '"warning"'),
        (516, '"success"'),
        (544, '"success"'),
        (687, '""'),
        (688, '""'),
        (692, '""'),
        (720, '""'),
    },
    "result-ui.mjs": {(159, '""')},
}

_REVIEWED_MIXED_LINES = {
    "runs-workbench.mjs": frozenset(),
    "small-area-workflow.mjs": frozenset({112, 109, 110, 111}),
    "app.mjs": frozenset({21}),
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
