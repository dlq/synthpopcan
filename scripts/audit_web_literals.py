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
    "model-messages.mjs": (
        "9f7697e929e03d60d3f31c162c78b187c181cecbbd75db0dcf3fe4da777e25ef",
        "web-presentation-and-control-mixed-preserve",
        frozenset(),
    ),
    "ipf-messages.mjs": (
        "df0d151399533cf39ec65786a909a579ddd2860a03baaff5a6eb493525df1c77",
        "web-presentation-and-control-mixed-preserve",
        frozenset(),
    ),
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
        "c92ce591394bfac3f4812d3ede866158312a6319ee33ad984edccd6644074a18",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "run-workbench-model.mjs": (
        "7c540045773eacfb1acf950d1d7841f4a76e3164172678047789663bc36b5652",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
    "runs-workbench.mjs": (
        "7e7e47e7127632f55d24040f0a2a4f7d79a70f0e8fc63f19713f33d04346725c",
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
        "98b6d67754992ca2d8bbf9d1e24fb50470d879f8bc5cc172a07ee4658b6a1d4c",
        "machine-data-or-protocol-preserve",
        frozenset(),
    ),
}

_REVIEWED_PRESENTATION = {
    "run-list.mjs": {
        (6, '"IPF"'),
        (7, '"Model"'),
        (8, '"Small area"'),
        (11, '"Draft"'),
        (12, '"Queued"'),
        (13, '"Running"'),
        (14, '"Cancelling"'),
        (15, '"Succeeded"'),
        (16, '"Failed"'),
        (17, '"Cancelled"'),
        (18, '"Interrupted"'),
        (75, '"No runs yet. Start with the demo or your own CSV files."'),
    }
}

_REVIEWED_PRESENTATION_LINES = {
    "run-workbench-model.mjs": frozenset(
        {
            41,
            55,
            56,
            57,
            59,
            61,
            62,
            63,
            64,
            66,
            74,
            162,
            163,
            164,
            167,
            169,
            170,
            171,
            172,
            173,
            175,
            183,
            185,
            186,
            189,
            190,
            191,
            193,
            195,
            206,
            207,
            208,
            211,
            212,
            213,
            214,
            215,
            216,
            217,
            219,
            221,
            229,
            235,
            239,
            240,
            241,
            242,
            250,
            252,
            253,
            254,
            258,
            259,
            260,
            264,
            268,
            269,
        }
    ),
    "runs-workbench.mjs": frozenset(
        {
            234,
            270,
            284,
            296,
            306,
            331,
            346,
            356,
            358,
            367,
            368,
            394,
            395,
            386,
            475,
            483,
            491,
            554,
            602,
            613,
            633,
            641,
            834,
            839,
            841,
            752,
            875,
            816,
            825,
            835,
            837,
            838,
        }
    ),
    "small-area-workflow.mjs": frozenset(
        {18, 39, 86, 162, 163, 167, 168, 169, 170, 171, 174, 176, 181, 193}
    ),
    "result-ui.mjs": frozenset({160, 157, 159}),
    "localization.mjs": frozenset({290, 3}),
}

_REVIEWED_MACHINE_EXCEPTIONS = {
    "run-workbench-model.mjs": {(259, '"small_area"'), (258, '"model"')},
    "runs-workbench.mjs": {
        (270, '"success"'),
        (284, '"warning"'),
        (296, '""'),
        (306, '"success"'),
        (331, '"warning"'),
        (346, '""'),
        (356, '"success"'),
        (358, '"error"'),
        (368, '""'),
        (475, '""'),
        (491, '"success"'),
        (554, '"warning"'),
        (613, '"success"'),
        (641, '"success"'),
        (839, '""'),
        (841, '""'),
        (752, '""'),
        (875, '""'),
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
