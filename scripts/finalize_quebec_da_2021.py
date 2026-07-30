"""Finalize validation evidence for the bounded Québec 2021 DA proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from synthpopcan.da_proof import finalize_quebec_da_proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--population", type=Path, default=None)
    parser.add_argument("--synthesis-seconds", type=float, default=None)
    args = parser.parse_args()
    manifest = finalize_quebec_da_proof(
        args.proof,
        population_directory=args.population,
        synthesis_seconds=args.synthesis_seconds,
    )
    print(json.dumps(manifest["synthesis_evidence"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
