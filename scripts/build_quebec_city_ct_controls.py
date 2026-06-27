"""Build Quebec City CMA CT control tables for small-area synthesis.

Extracts tenure and household-size margins from the 2016 Census Tract Profile
(national CSV) for the Quebec City CMA (code 421), scales them to a target
household count, and writes a combined control CSV suitable for

    synthpopcan geo synthesize-from-package

Usage
-----
    uv run python scripts/build_quebec_city_ct_controls.py
    uv run python scripts/build_quebec_city_ct_controls.py --target 338000
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROFILE_PATH = (
    ROOT
    / "data/raw/statcan/2016-census"
    / "Census Tract Summaries 2016"
    / "98-401-X2016043_eng_CSV"
    / "98-401-X2016043_English_CSV_data.csv"
)

# Quebec City CMA geo code prefix (CMA=421)
CMA_PREFIX = "421"

# Census Profile member IDs → control category value
# Household size (100% data, member IDs 52-56)
HHSIZE_MEMBER_IDS: dict[str, str] = {
    "52": "1",
    "53": "2",
    "54": "3",
    "55": "4",
    "56": "5",  # "5 or more persons" — candidates capped at 5 before calibration
}
# Tenure (25% sample data, member IDs 1618-1620)
TENURE_MEMBER_IDS: dict[str, str] = {
    "1618": "1",  # Owner
    "1619": "2",  # Renter
    # 1620 = Band housing — very small count, omitted like Montreal
}

DIM_COL = "DIM: Profile of Census Tracts (2247)"
MEMBER_COL = "Member ID: Profile of Census Tracts (2247)"
VAL_COL = "Dim: Sex (3): Member ID: [1]: Total - Sex"
GEO_COL = "GEO_CODE (POR)"
GEO_LVL = "GEO_LEVEL"

CT_LEVEL = "2"


def extract_ct_controls(
    profile_path: Path,
) -> dict[str, dict[str, dict[str, float]]]:
    """Return {ct: {margin: {category: raw_count}}} from the Census Profile CSV."""
    ct: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"tenure": {}, "hhsize": {}}
    )
    with profile_path.open(newline="", encoding="latin-1") as fh:
        for row in csv.DictReader(fh):
            if row[GEO_LVL].strip() != CT_LEVEL:
                continue
            geo = row[GEO_COL].strip()
            if not geo.startswith(CMA_PREFIX):
                continue
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
    """Scale raw Census Profile counts so household_size totals sum to target_total."""
    raw_total = sum(
        sum(cats.get("hhsize", {}).values()) for cats in ct_controls.values()
    )
    if raw_total == 0:
        raise ValueError("no household-size totals found in controls")
    scale = target_total / raw_total

    scaled: dict[str, dict[str, dict[str, int]]] = {}
    for geo, margins in ct_controls.items():
        hhsize_raw = margins.get("hhsize", {})
        hhsize_scaled = {cat: round(count * scale) for cat, count in hhsize_raw.items()}
        hhsize_total = sum(hhsize_scaled.values())

        # Normalize tenure (25% sample) per CT so both margins share the same total.
        tenure_raw = margins.get("tenure", {})
        tenure_raw_total = sum(tenure_raw.values())
        if tenure_raw_total > 0 and hhsize_total > 0:
            tenure_scale = hhsize_total / tenure_raw_total
            tenure_scaled = {
                cat: round(count * tenure_scale) for cat, count in tenure_raw.items()
            }
            tenure_diff = hhsize_total - sum(tenure_scaled.values())
            if tenure_diff != 0:
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=int,
        default=338_000,
        help="Target total households (default: 338000, ~2016 Quebec City CMA count)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data/private/small-area",
        help="Output directory",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROFILE_PATH,
        help="National CT Census Profile CSV (98-401-X2016043_English_CSV_data.csv)",
    )
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    target: int = args.target

    print(f"Reading Census Profile: {args.profile.relative_to(ROOT)}")
    ct_controls = extract_ct_controls(args.profile)
    print(f"  Quebec City CTs found: {len(ct_controls)}")

    incomplete = [
        ct
        for ct, m in ct_controls.items()
        if len(m.get("hhsize", {})) < 5 or len(m.get("tenure", {})) < 2
    ]
    if incomplete:
        print(
            f"  WARNING: {len(incomplete)} CTs have incomplete controls: "
            f"{incomplete[:5]}"
        )

    raw_total = sum(sum(m.get("hhsize", {}).values()) for m in ct_controls.values())
    print(f"  Raw Census household total: {raw_total:,.0f}")
    print(f"Scaling to {target:,} households")
    scaled = scale_controls(ct_controls, target)

    hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
    tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
    print(f"  Scaled hhsize total: {hhsize_total:,}  (target: {target:,})")
    print(f"  Scaled tenure total: {tenure_total:,}")

    controls_out = out_dir / f"quebec-city-ct-controls-{target}.csv"
    write_combined_controls(scaled, controls_out)
    print(f"Controls written → {controls_out.relative_to(ROOT)}")

    package = (
        ROOT / "data/private/model-release-assets/quebec-2016-all-fields-package.json"
    )
    hh_out = out_dir / f"quebec-city-ct-synthetic-households-{target}.csv"
    persons_out = out_dir / f"quebec-city-ct-synthetic-persons-{target}.csv"
    report_out = out_dir / f"quebec-city-ct-calibration-report-{target}.json"

    print("\nNext step:")
    print("  uv run synthpopcan geo synthesize-from-package \\")
    print(f"    {package.relative_to(ROOT)} \\")
    print(f"    --households {target} \\")
    print(f"    --controls {controls_out.relative_to(ROOT)} \\")
    print("    --geo-dimension ct \\")
    print("    --geo-column ct \\")
    print("    --max-household-size 5 \\")
    print(f"    --households-out {hh_out.relative_to(ROOT)} \\")
    print(f"    --persons-out {persons_out.relative_to(ROOT)} \\")
    print(f"    --report {report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
