"""Build Quebec ADA control tables for small-area synthesis.

Combines two control margins per ADA:
  - household_size (1–5) from the 2016 ADA Census Profile (100% data)
  - TENUR owner/renter from the existing tenure controls CSV (25% sample)

Scales both margins to a target household count and normalises tenure per ADA
to match the household_size anchor so IPF can converge.  Also writes a recoded
candidate households CSV capping household_size at 5.

Usage
-----
    uv run python scripts/build_quebec_ada_controls.py \\
        --target 3750000 \\
        --households data/private/benchmarks/tree-release-2016-pr24-all-fields/synthetic-households-3.75m.csv \\
        --out-dir data/private/small-area
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ADA_PROFILE_PATH = Path(
    "data/raw/statcan/2016-census/ADA-Profile-2016"
    "/98-401-X2016020_English_CSV_data.csv"
)
TENURE_CONTROLS_PATH = Path("data/private/small-area/quebec-ada-tenure-controls.csv")

# ADA profile member IDs for household size (100% data, same as CT profile)
HHSIZE_MEMBER_IDS: dict[str, str] = {
    "52": "1",
    "53": "2",
    "54": "3",
    "55": "4",
    "56": "5",  # "5 or more persons"
}

MEM_COL = "Member ID: Profile of Aggregate Dissemination Areas (660)"
VAL_COL = "Dim: Sex (3): Member ID: [1]: Total - Sex"
GEO_COL = "GEO_CODE (POR)"
GEO_LVL = "GEO_LEVEL"

ADA_LEVEL = "3"
PROVINCE_PREFIX = "24"  # Quebec


def extract_ada_hhsize(profile_path: Path) -> dict[str, dict[str, float]]:
    """Return {ada: {cat: raw_count}} for household size from the ADA profile."""
    hhsize: dict[str, dict[str, float]] = defaultdict(dict)
    with profile_path.open(newline="", encoding="latin-1") as fh:
        for row in csv.DictReader(fh):
            if row[GEO_LVL].strip() != ADA_LEVEL:
                continue
            geo = row[GEO_COL].strip()
            if not geo.startswith(PROVINCE_PREFIX):
                continue
            mid = row[MEM_COL].strip()
            if mid not in HHSIZE_MEMBER_IDS:
                continue
            raw = row[VAL_COL].strip().replace(",", "")
            try:
                hhsize[geo][HHSIZE_MEMBER_IDS[mid]] = float(raw)
            except ValueError:
                pass
    return dict(hhsize)


def read_tenure_controls(path: Path) -> dict[str, dict[str, float]]:
    """Return {ada: {cat: raw_count}} for tenure (owner=1, renter=2 only)."""
    tenure: dict[str, dict[str, float]] = defaultdict(dict)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            ada = row["ada"].strip()
            cat = row["TENUR"].strip()
            if cat not in ("1", "2"):  # skip band housing (8), always 0
                continue
            try:
                tenure[ada][cat] = float(row["count"])
            except ValueError:
                pass
    return dict(tenure)


def scale_controls(
    hhsize_raw: dict[str, dict[str, float]],
    tenure_raw: dict[str, dict[str, float]],
    target_total: int,
) -> dict[str, dict[str, dict[str, int]]]:
    """Scale and normalise both margins to target_total.

    household_size is the anchor (100% data).  tenure is normalised per ADA to
    match the scaled hhsize total so IPF converges without error.
    """
    raw_total = sum(sum(cats.values()) for cats in hhsize_raw.values())
    if raw_total == 0:
        raise ValueError("no household-size totals found")
    scale = target_total / raw_total

    scaled: dict[str, dict[str, dict[str, int]]] = {}
    for ada in sorted(set(hhsize_raw) | set(tenure_raw)):
        hhsize_cats = hhsize_raw.get(ada, {})
        hhsize_scaled = {
            cat: round(count * scale) for cat, count in hhsize_cats.items()
        }
        hhsize_total = sum(hhsize_scaled.values())

        tenure_cats = tenure_raw.get(ada, {})
        tenure_raw_total = sum(tenure_cats.values())
        if tenure_raw_total == 0:
            # No households by tenure (uninhabited ADA) — zero out hhsize too so
            # IPF isn't given contradictory zero-tenure / non-zero-hhsize targets.
            scaled[ada] = {
                "hhsize": {cat: 0 for cat in hhsize_scaled},
                "tenure": {cat: 0 for cat in tenure_cats},
            }
            continue
        if tenure_raw_total > 0 and hhsize_total > 0:
            tenure_scale = hhsize_total / tenure_raw_total
            tenure_scaled = {
                cat: round(count * tenure_scale) for cat, count in tenure_cats.items()
            }
            diff = hhsize_total - sum(tenure_scaled.values())
            if diff != 0:
                largest = max(tenure_scaled, key=lambda c: tenure_scaled[c])
                tenure_scaled[largest] += diff
        else:
            tenure_scaled = {cat: 0 for cat in tenure_cats}

        scaled[ada] = {"hhsize": hhsize_scaled, "tenure": tenure_scaled}
    return scaled


def write_combined_controls(
    scaled: dict[str, dict[str, dict[str, int]]],
    out_path: Path,
) -> None:
    fieldnames = ["margin", "dimensions", "ada", "TENUR", "household_size", "count"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for ada in sorted(scaled):
            for cat, count in sorted(scaled[ada].get("tenure", {}).items()):
                writer.writerow(
                    {
                        "margin": "ada tenure",
                        "dimensions": "ada,TENUR",
                        "ada": ada,
                        "TENUR": cat,
                        "household_size": "",
                        "count": count,
                    }
                )
            for cat, count in sorted(scaled[ada].get("hhsize", {}).items()):
                writer.writerow(
                    {
                        "margin": "ada hhsize",
                        "dimensions": "ada,household_size",
                        "ada": ada,
                        "TENUR": "",
                        "household_size": cat,
                        "count": count,
                    }
                )


def write_recoded_candidates(
    households_path: Path,
    out_path: Path,
    *,
    hhsize_col: str = "household_size",
    cap: int = 5,
) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with households_path.open(newline="") as src, out_path.open("w", newline="") as dst:
        reader = csv.DictReader(src)
        assert reader.fieldnames, "empty candidates file"
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            try:
                size = int(row[hhsize_col])
            except (ValueError, KeyError):
                pass
            else:
                if size > cap:
                    row[hhsize_col] = str(cap)
            writer.writerow(row)
            n += 1
    return n


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=3_750_000)
    parser.add_argument(
        "--households",
        type=Path,
        default=Path(
            "data/private/benchmarks/tree-release-2016-pr24-all-fields/synthetic-households-3.75m.csv"
        ),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/private/small-area"))
    parser.add_argument("--profile", type=Path, default=ADA_PROFILE_PATH)
    parser.add_argument("--tenure-controls", type=Path, default=TENURE_CONTROLS_PATH)
    args = parser.parse_args(argv)

    suffix = str(args.target)

    print(f"Extracting household_size from ADA profile: {args.profile}")
    hhsize_raw = extract_ada_hhsize(args.profile)
    print(f"  ADAs with hhsize data: {len(hhsize_raw)}")

    print(f"Reading tenure controls: {args.tenure_controls}")
    tenure_raw = read_tenure_controls(args.tenure_controls)
    print(f"  ADAs with tenure data: {len(tenure_raw)}")

    missing_hhsize = set(tenure_raw) - set(hhsize_raw)
    missing_tenure = set(hhsize_raw) - set(tenure_raw)
    if missing_hhsize:
        print(
            f"  WARNING: {len(missing_hhsize)} ADAs have tenure but no hhsize: {sorted(missing_hhsize)[:5]}"
        )
    if missing_tenure:
        print(
            f"  WARNING: {len(missing_tenure)} ADAs have hhsize but no tenure: {sorted(missing_tenure)[:5]}"
        )

    print(f"Scaling to {args.target:,} households")
    scaled = scale_controls(hhsize_raw, tenure_raw, args.target)

    hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
    tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
    print(f"  Scaled hhsize total: {hhsize_total:,}  (target: {args.target:,})")
    print(f"  Scaled tenure total: {tenure_total:,}")

    controls_out = args.out_dir / f"quebec-ada-controls-{suffix}.csv"
    write_combined_controls(scaled, controls_out)
    print(f"Controls written → {controls_out}")

    candidates_out = args.out_dir / "quebec-ada-candidates-households-recoded.csv"
    n = write_recoded_candidates(args.households, candidates_out)
    print(
        f"Recoded candidates ({n:,} rows, household_size capped at 5) → {candidates_out}"
    )

    persons_path = str(args.households).replace(
        "synthetic-households-3.75m.csv", "synthetic-persons-3.75m.csv"
    )
    print("\nNext step:")
    print("  uv run synthpopcan geo calibrate-linked \\")
    print(f"    --households {candidates_out} \\")
    print(f"    --persons {persons_path} \\")
    print(f"    --controls {controls_out} \\")
    print("    --geography-dimension ada \\")
    print("    --geography-column ada \\")
    print(
        f"    --households-out {args.out_dir}/quebec-ada-synthetic-households-{suffix}.csv \\"
    )
    print(
        f"    --persons-out {args.out_dir}/quebec-ada-synthetic-persons-{suffix}.csv \\"
    )
    print(f"    --report {args.out_dir}/quebec-ada-calibration-report-{suffix}.json")


if __name__ == "__main__":
    main()
