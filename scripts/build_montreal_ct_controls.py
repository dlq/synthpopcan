"""Build Montreal CT control tables for small-area synthesis.

Extracts tenure and household-size margins from the 2016 Census Tract Profile
for the Montreal CMA (code 462), scales them to a target household count, and
writes a combined control CSV suitable for ``synthpopcan small-area
calibrate-linked``.

Also writes a recoded candidate households CSV capping household_size at 5 so
that sizes 5, 6, and 7 all map to the census "5 or more persons" category.

Usage
-----
    uv run python scripts/build_montreal_ct_controls.py \\
        --target 1830000 \\
        --households data/private/small-area/montreal-candidates-households.csv \\
        --out-dir data/private/small-area
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

PROFILE_PATH = Path(
    "data/raw/statcan/2016-census"
    "/Census Tract Summaries 2016"
    "/98-401-X2016043_eng_CSV"
    "/98-401-X2016043_English_montreal.csv"
)

# Census Profile member IDs → control category value
# Household size (100% data, member IDs 52-56)
HHSIZE_MEMBER_IDS: dict[str, str] = {
    "52": "1",
    "53": "2",
    "54": "3",
    "55": "4",
    "56": "5",  # "5 or more persons" — candidates are recoded to cap at 5
}
# Tenure (25% sample data, member IDs 1618-1619)
TENURE_MEMBER_IDS: dict[str, str] = {
    "1618": "1",  # Owner
    "1619": "2",  # Renter
    # 1620 = Band housing, always 0 in Montreal — omitted
}

DIM_COL = "DIM: Profile of Census Tracts (2247)"
MEMBER_COL = "Member ID: Profile of Census Tracts (2247)"
VAL_COL = "Dim: Sex (3): Member ID: [1]: Total - Sex"
GEO_COL = "GEO_CODE (POR)"
GEO_LVL = "GEO_LEVEL"

CT_LEVEL = "2"


def extract_ct_controls(profile_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """Return {ct: {margin: {category: raw_count}}} from the Census Profile CSV."""
    ct: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"tenure": {}, "hhsize": {}}
    )
    with profile_path.open(newline="", encoding="latin-1") as fh:
        for row in csv.DictReader(fh):
            if row[GEO_LVL].strip() != CT_LEVEL:
                continue
            geo = row[GEO_COL].strip()
            mid = row[MEMBER_COL].strip()
            raw = row[VAL_COL].strip().replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            if mid in HHSIZE_MEMBER_IDS:
                ct[geo]["hhsize"][HHSIZE_MEMBER_IDS[mid]] = val
            elif mid in TENURE_MEMBER_IDS:
                ct[geo]["tenure"][TENURE_MEMBER_IDS[mid]] = val
    return dict(ct)


def scale_controls(
    ct_controls: dict[str, dict[str, dict[str, float]]],
    target_total: int,
) -> dict[str, dict[str, dict[str, int]]]:
    """Scale raw Census Profile counts so household_size totals sum to target_total.

    Uses the CMA-level household_size totals as the denominator so scaling is
    consistent across both margins.
    """
    raw_total = sum(
        sum(cats.get("hhsize", {}).values()) for cats in ct_controls.values()
    )
    if raw_total == 0:
        raise ValueError("no household-size totals found in controls")
    scale = target_total / raw_total

    scaled: dict[str, dict[str, dict[str, int]]] = {}
    for geo, margins in ct_controls.items():
        # Scale household_size (100% data) to the target first — it is the anchor.
        hhsize_raw = margins.get("hhsize", {})
        hhsize_scaled = {cat: round(count * scale) for cat, count in hhsize_raw.items()}
        hhsize_total = sum(hhsize_scaled.values())

        # Normalize tenure (25% sample) per CT so both margins share the same
        # total. Without this, IPF cannot converge because the two sources
        # (100% data vs 25% sample) produce different household counts per CT.
        tenure_raw = margins.get("tenure", {})
        tenure_raw_total = sum(tenure_raw.values())
        if tenure_raw_total > 0 and hhsize_total > 0:
            tenure_scale = hhsize_total / tenure_raw_total
            tenure_scaled = {
                cat: round(count * tenure_scale) for cat, count in tenure_raw.items()
            }
            # Fix rounding so tenure sums exactly to hhsize_total
            tenure_diff = hhsize_total - sum(tenure_scaled.values())
            if tenure_diff != 0:
                # Add remainder to the largest category
                largest_cat = max(tenure_scaled, key=lambda c: tenure_scaled[c])
                tenure_scaled[largest_cat] += tenure_diff
        else:
            tenure_scaled = {cat: 0 for cat in tenure_raw}

        scaled[geo] = {"hhsize": hhsize_scaled, "tenure": tenure_scaled}
    return scaled


def write_combined_controls(
    scaled: dict[str, dict[str, dict[str, int]]],
    out_path: Path,
) -> None:
    """Write a combined tenure + household_size control CSV."""
    fieldnames = ["margin", "dimensions", "ct", "TENUR", "household_size", "count"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for ct in sorted(scaled):
            margins = scaled[ct]
            # tenure margin
            for cat, count in sorted(margins.get("tenure", {}).items()):
                writer.writerow(
                    {
                        "margin": "ct tenure",
                        "dimensions": "ct,TENUR",
                        "ct": ct,
                        "TENUR": cat,
                        "household_size": "",
                        "count": count,
                    }
                )
            # household_size margin
            for cat, count in sorted(margins.get("hhsize", {}).items()):
                writer.writerow(
                    {
                        "margin": "ct hhsize",
                        "dimensions": "ct,household_size",
                        "ct": ct,
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
    """Write households CSV with household_size capped at cap.

    Returns the number of rows written.
    """
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


def _suffix(target: int) -> str:
    return str(target)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=int,
        default=1_830_000,
        help="Target total households (default: 1830000)",
    )
    parser.add_argument(
        "--households",
        type=Path,
        default=Path("data/private/small-area/montreal-candidates-households.csv"),
        help="Candidate households CSV to recode",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/private/small-area"),
        help="Output directory",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROFILE_PATH,
        help="Montreal CT Census Profile CSV",
    )
    args = parser.parse_args(argv)

    suffix = _suffix(args.target)

    print(f"Reading Census Profile: {args.profile}")
    ct_controls = extract_ct_controls(args.profile)
    print(f"  CTs found: {len(ct_controls)}")

    # Validate completeness
    incomplete = [
        ct
        for ct, m in ct_controls.items()
        if len(m.get("hhsize", {})) < 5 or len(m.get("tenure", {})) < 2
    ]
    if incomplete:
        print(
            f"  WARNING: {len(incomplete)} CTs have incomplete controls: {incomplete[:5]}"
        )

    print(f"Scaling to {args.target:,} households")
    scaled = scale_controls(ct_controls, args.target)

    # Verify totals
    hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
    tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
    print(f"  Scaled hhsize total: {hhsize_total:,}  (target: {args.target:,})")
    print(f"  Scaled tenure total: {tenure_total:,}")

    controls_out = args.out_dir / f"montreal-ct-controls-{suffix}.csv"
    write_combined_controls(scaled, controls_out)
    print(f"Controls written → {controls_out}")

    candidates_out = args.out_dir / "montreal-candidates-households-recoded.csv"
    n = write_recoded_candidates(args.households, candidates_out)
    print(
        f"Recoded candidates ({n:,} rows, household_size capped at 5) → {candidates_out}"
    )

    print("\nNext step:")
    print("  uv run synthpopcan geo calibrate-linked \\")
    print(f"    --households {candidates_out} \\")
    print("    --persons data/private/small-area/montreal-candidates-persons.csv \\")
    print(f"    --controls {controls_out} \\")
    print("    --geo-dimension ct \\")
    print("    --geo-column ct \\")
    print(
        f"    --households-out data/private/small-area/montreal-ct-synthetic-households-{suffix}.csv \\"
    )
    print(
        f"    --persons-out data/private/small-area/montreal-ct-synthetic-persons-{suffix}.csv \\"
    )
    print(
        f"    --report data/private/small-area/montreal-ct-calibration-report-{suffix}.json"
    )


if __name__ == "__main__":
    main()
