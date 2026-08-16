"""Build or verify the packaged SynthPopCan 1.x public-interface contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import synthpopcan  # noqa: E402
from synthpopcan._interface import (  # noqa: E402
    snapshot_click_interface,
    snapshot_python_symbol,
    validate_public_interface_compatibility,
)
from synthpopcan.cli import cli  # noqa: E402

OUTPUT_PATH = ROOT / "src/synthpopcan/contracts/public-interface-v1.json"
BASELINE_PATH = ROOT / "src/synthpopcan/contracts/public-interface-v1-baseline.json"
SCHEMA_PATTERN = re.compile(r"synthpopcan-[a-z0-9-]+-v[0-9]+")

# These formats are accepted or emitted by documented CLI/Python workflows and
# are therefore part of the 1.x persisted-artifact compatibility commitment.
SUPPORTED_SCHEMAS: dict[str, tuple[str, str]] = {
    "synthpopcan-assurance-v1": ("run assurance record", "CORRECTNESS.md"),
    "synthpopcan-canada-small-area-plan-v1": (
        "resumable national small-area plan",
        "docs/small-area.md",
    ),
    "synthpopcan-control-compatibility-registry-v1": (
        "installed control-pack compatibility registry",
        "docs/small-area.md",
    ),
    "synthpopcan-control-pack-evidence-v1": (
        "study-specific control-pack evidence",
        "docs/small-area.md",
    ),
    "synthpopcan-control-pack-v1": (
        "reviewed control-pack definition",
        "docs/small-area.md",
    ),
    "synthpopcan-data-dictionary-v1": (
        "exchange-bundle data dictionary",
        "docs/exchange.md",
    ),
    "synthpopcan-enrichment-layer-v1": (
        "normalized enrichment layer",
        "docs/enrichment.md",
    ),
    "synthpopcan-enrichment-manifest-v1": (
        "enrichment sidecar manifest",
        "docs/enrichment.md",
    ),
    "synthpopcan-exchange-provenance-v1": (
        "exchange-bundle provenance",
        "docs/exchange.md",
    ),
    "synthpopcan-exchange-v1": ("portable exchange bundle", "docs/exchange.md"),
    "synthpopcan-exchange-validation-v1": (
        "exchange-bundle validation report",
        "docs/exchange.md",
    ),
    "synthpopcan-external-comparison-v1": (
        "external validation comparison descriptor",
        "docs/methodological-validation.md",
    ),
    "synthpopcan-geodata-catalogue-v1": (
        "prepared boundary catalogue",
        "docs/geodata.md",
    ),
    "synthpopcan-geography-identity-v1": (
        "Census geography identity",
        "docs/enrichment.md",
    ),
    "synthpopcan-geography-relationship-v1": (
        "Census geography relationship",
        "docs/enrichment.md",
    ),
    "synthpopcan-geography-universe-v1": (
        "Census geography universe",
        "docs/enrichment.md",
    ),
    "synthpopcan-hierarchical-pumf-field-eligibility-v1": (
        "reviewed cross-vintage PUMF field-eligibility inventory",
        "docs/field-eligibility.md",
    ),
    "synthpopcan-linked-population-v1": (
        "linked household/person population",
        "docs/linked-population.md",
    ),
    "synthpopcan-linked-tree-package-v1": (
        "linked household/person model package",
        "docs/tree.md",
    ),
    "synthpopcan-linked-tree-training-v1": (
        "linked-tree training manifest",
        "docs/tree.md",
    ),
    "synthpopcan-prepared-model-licensing-v1": (
        "layered prepared-model licensing presentation",
        "docs/tree.md",
    ),
    "synthpopcan-prepared-model-archive-correction-evidence-v1": (
        "verified prepared-model archive-correction transaction",
        "docs/records/prepared-model-archive-correction-2026-08-16.md",
    ),
    "synthpopcan-public-interface-v1": (
        "installed public-interface contract",
        "docs/compatibility.md",
    ),
    "synthpopcan-resource-record-v1": (
        "acquired enrichment resource record",
        "docs/enrichment.md",
    ),
    "synthpopcan-run-v1": ("durable local run manifest", "docs/web-app.md"),
    "synthpopcan-small-area-linked-calibration-v2": (
        "linked small-area calibration report",
        "docs/small-area.md",
    ),
    "synthpopcan-source-profile-v1": (
        "enrichment source profile",
        "docs/enrichment.md",
    ),
    "synthpopcan-source-provenance-v1": (
        "model source provenance",
        "docs/tree.md",
    ),
    "synthpopcan-statcan-resource-v1": (
        "cached Statistics Canada resource manifest",
        "docs/statcan.md",
    ),
    "synthpopcan-tree-generation-manifest-v1": (
        "tree-generation manifest",
        "docs/tree-generate.md",
    ),
    "synthpopcan-tree-model-v1": ("portable tree model", "docs/tree.md"),
    "synthpopcan-tree-release-manifest-v1": (
        "tree release-readiness manifest",
        "docs/tree.md",
    ),
    "synthpopcan-validation-profile-v1": (
        "methodological validation profile",
        "docs/methodological-validation.md",
    ),
    "synthpopcan-wds-selection-v1": (
        "Statistics Canada WDS category selection",
        "docs/controls.md",
    ),
}

# These identifiers make diagnostic, cache, benchmark, UI, or one-off proof
# artifacts self-describing. They are audited here so none can be mistaken for
# an undocumented stable interchange format.
INTERNAL_SCHEMAS: dict[str, str] = {
    "synthpopcan-boundary-partition-v1": "derived geodata build record",
    "synthpopcan-boundary-subset-v1": "derived geodata build record",
    "synthpopcan-canada-small-area-batch-v1": "restartable execution detail",
    "synthpopcan-canfed-validation-v1": "adapter diagnostic report",
    "synthpopcan-control-pack-compatibility-v1": "derived compatibility report",
    "synthpopcan-control-pack-plan-v1": "derived planning report",
    "synthpopcan-control-pack-web-preflight-v1": "web UI preflight response",
    "synthpopcan-enrichment-validation-v1": "derived validation report",
    "synthpopcan-enrichment-verification-v1": "derived verification report",
    "synthpopcan-external-aggregate-comparison-v1": "test evidence fixture",
    "synthpopcan-geography-validation-v1": "derived validation report",
    "synthpopcan-integerization-backend-decision-v1": "methodology evidence detail",
    "synthpopcan-ipf-control-suggestions-v1": "derived suggestion report",
    "synthpopcan-linked-tree-package-inspection-v1": "derived inspection report",
    "synthpopcan-linked-tree-readiness-v1": "derived readiness report",
    "synthpopcan-methodology-evidence-v1": "release evidence snapshot",
    "synthpopcan-national-candidate-pool-v1": "rebuildable execution cache",
    "synthpopcan-national-map-statistics-v1": "derived map data",
    "synthpopcan-national-small-area-summary-v1": "derived execution summary",
    "synthpopcan-odef-validation-v1": "adapter diagnostic report",
    "synthpopcan-prepared-model-report-v1": "derived workflow report",
    "synthpopcan-quebec-da-proof-v1": "bounded proof artifact",
    "synthpopcan-quebec-da-selection-v1": "bounded proof selection",
    "synthpopcan-reference-enrichment-validation-v1": "test evidence report",
    "synthpopcan-small-area-benchmark-v1": "benchmark result",
    "synthpopcan-small-area-linked-calibration-v1": "superseded pre-1.0 report",
    "synthpopcan-small-area-performance-estimate-v1": "derived estimate",
    "synthpopcan-tree-package-v1": "legacy single-table package",
}


def parse_api_reference_members(path: Path) -> list[tuple[str, str]]:
    """Return explicit curated members from the Sphinx API reference."""

    members: list[tuple[str, str]] = []
    current_module: str | None = None
    collecting = False
    for line in path.read_text().splitlines():
        module_match = re.match(r"^\.\. automodule::\s+(\S+)", line)
        if module_match:
            current_module = module_match.group(1)
            collecting = False
            continue
        if current_module is None:
            continue
        stripped = line.strip()
        if stripped.startswith(":members:"):
            collecting = True
            raw = stripped.removeprefix(":members:")
        elif collecting and line.startswith("             "):
            raw = stripped
        else:
            if stripped and not stripped.startswith(":"):
                collecting = False
            continue
        members.extend(
            (current_module, name.strip()) for name in raw.split(",") if name.strip()
        )
    return members


def source_schema_identifiers() -> set[str]:
    """Collect schema identifiers implemented by package source, excluding this contract."""

    identifiers: set[str] = set()
    package_root = ROOT / "src/synthpopcan"
    paths = [
        *package_root.rglob("*.py"),
        package_root / "models/demo-linked-household-person-package.json",
        ROOT / "docs/_static/hierarchical-pumf-field-eligibility-v1.json",
    ]
    for path in paths:
        identifiers.update(SCHEMA_PATTERN.findall(path.read_text()))
    return identifiers


def build_contract() -> dict[str, Any]:
    """Build the deterministic contract from the live source and public docs."""

    classified = set(SUPPORTED_SCHEMAS) | set(INTERNAL_SCHEMAS)
    implemented = source_schema_identifiers()
    if classified != implemented:
        missing = sorted(implemented - classified)
        stale = sorted(classified - implemented)
        raise RuntimeError(
            f"schema classification drift; missing={missing!r}, stale={stale!r}"
        )

    advanced = []
    for module_name, name in parse_api_reference_members(ROOT / "docs/api.rst"):
        advanced.append(
            snapshot_python_symbol(module_name, name) | {"module": module_name}
        )

    return {
        "schema_version": "synthpopcan-public-interface-v1",
        "effective_from": "1.0.0",
        "cli": {
            "commands": snapshot_click_interface(cli, program_name="synthpopcan"),
            "entry_point": "synthpopcan",
            "exit_codes": {
                "0": "successful command",
                "1": "documented input, data, filesystem, or runtime failure",
                "2": "command-line usage error",
            },
            "help_options": ["-h", "--help"],
            "output_contract": {
                "json": (
                    "After reaching result reporting, '--format json' writes one JSON "
                    "value to stdout; an earlier failure may produce no JSON."
                ),
                "stderr": (
                    "Click errors and usage messages, plus progress or status when a "
                    "command segregates it from results."
                ),
                "stdout": (
                    "Structured results, or human-mode results and workflow narration; "
                    "human mode may include progress and validation findings."
                ),
            },
        },
        "python": {
            "advanced": advanced,
            "top_level": [
                snapshot_python_symbol("synthpopcan", name)
                for name in synthpopcan.__all__
            ],
        },
        "persisted_schemas": {
            "internal": [
                {"identifier": identifier, "purpose": purpose}
                for identifier, purpose in sorted(INTERNAL_SCHEMAS.items())
            ],
            "supported": [
                {
                    "documentation": documentation,
                    "identifier": identifier,
                    "purpose": purpose,
                }
                for identifier, (purpose, documentation) in sorted(
                    SUPPORTED_SCHEMAS.items()
                )
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting when the committed contract has drifted",
    )
    mode.add_argument(
        "--freeze-baseline",
        action="store_true",
        help="create the immutable 1.0 compatibility baseline exactly once",
    )
    args = parser.parse_args()
    contract = build_contract()
    rendered = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    if args.freeze_baseline:
        if BASELINE_PATH.exists():
            raise SystemExit(
                "public-interface compatibility baseline already exists and must "
                "not be replaced"
            )
        OUTPUT_PATH.write_text(rendered)
        BASELINE_PATH.write_text(rendered)
        print(f"Wrote {OUTPUT_PATH}")
        print(f"Froze {BASELINE_PATH}")
        return 0
    if not BASELINE_PATH.is_file():
        raise SystemExit(
            "public-interface compatibility baseline is missing; use "
            "'--freeze-baseline' only for the initial 1.0 freeze"
        )
    baseline_value: object = json.loads(BASELINE_PATH.read_text())
    if not isinstance(baseline_value, dict):
        raise SystemExit("public-interface compatibility baseline must be an object")
    validate_public_interface_compatibility(baseline_value, contract)
    if args.check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_text() != rendered:
            raise SystemExit(
                "public-interface contract is stale; run "
                "'uv run python scripts/build_public_interface.py'"
            )
        print(f"Public-interface contract is current: {OUTPUT_PATH}")
        return 0
    OUTPUT_PATH.write_text(rendered)
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
