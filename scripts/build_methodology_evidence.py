"""Render deterministic bounded calibration and integerization evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from synthpopcan.methodology import build_methodology_evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        help="Write the JSON evidence here instead of printing it.",
    )
    return parser.parse_args()


def render_evidence(evidence: dict[str, Any] | None = None) -> str:
    """Return canonical JSON for the supplied or freshly computed evidence."""

    payload = evidence if evidence is not None else build_methodology_evidence()
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> None:
    args = parse_args()
    rendered = render_evidence()
    if args.out is None:
        print(rendered, end="")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)


if __name__ == "__main__":
    main()
