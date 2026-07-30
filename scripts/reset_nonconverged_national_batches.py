"""Reset completed national batches that contain nonconverged geography fits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from synthpopcan.national_execution import reset_nonconverged_national_batches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--jurisdiction", action="append", default=[])
    args = parser.parse_args()
    reset = reset_nonconverged_national_batches(
        args.plan,
        jurisdiction_pruids=set(args.jurisdiction) or None,
    )
    print(json.dumps({"reset_batches": reset, "count": len(reset)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
