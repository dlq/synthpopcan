"""Prepare the bounded Québec 2021 DA release-evidence workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from synthpopcan.da_proof import prepare_quebec_da_proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--relationships", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target-households", type=int, default=800)
    parser.add_argument("--per-area", type=int, default=4)
    parser.add_argument("--metro-csd", default="2466023")
    parser.add_argument("--rural-csd", default="2479088")
    args = parser.parse_args()

    manifest = prepare_quebec_da_proof(
        args.profile,
        args.boundaries,
        args.relationships,
        args.out,
        target_households=args.target_households,
        per_area=args.per_area,
        metro_csd=args.metro_csd,
        rural_csd=args.rural_csd,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
