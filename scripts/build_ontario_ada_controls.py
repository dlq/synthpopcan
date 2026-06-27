"""Build Ontario ADA control tables for small-area synthesis.

Extracts household_size and tenure margins from the 2016 ADA Census Profile
for Ontario (PR 35), scales both to a target household count, and writes a
combined control CSV for ``synthpopcan geo calibrate-linked``.

Usage
-----
    uv run python scripts/build_ontario_ada_controls.py \\
        --target 5500000 \\
        --households data/private/benchmarks/ontario-2016-all-fields/synthetic-households-5.5m.csv \\
        --out-dir data/private/small-area
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ADA_PROFILE_PATH = Path(
    "data/raw/statcan/census-profile/2016/2016-census-profile-ada.csv"
)

HHSIZE_MEMBER_IDS: dict[str, str] = {
    "52": "1",
    "53": "2",
    "54": "3",
    "55": "4",
    "56": "5",
}
TENURE_MEMBER_IDS: dict[str, str] = {
    "1618": "1",  # Owner
    "1619": "2",  # Renter
}

PROVINCE_PREFIX = "35"
ADA_LEVEL = "3"


def _find_col(fields: list[str], fragment: str) -> str:
    return next(c for c in fields if fragment in c)


def extract_ada_controls(profile_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """Return {ada: {hhsize: {cat: count}, tenure: {cat: count}}} for Ontario."""
    data: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"hhsize": {}, "tenure": {}}
    )
    with profile_path.open(newline="", encoding="latin-1") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        mem_col = _find_col(fields, "Member ID")
        val_col = _find_col(fields, "[1]: Total")
        geo_col = _find_col(fields, "GEO_CODE")

        for row in reader:
            if row["GEO_LEVEL"].strip() != ADA_LEVEL:
                continue
            geo = row[geo_col].strip()
            if not geo.startswith(PROVINCE_PREFIX):
                continue
            mid = row[mem_col].strip()
            raw = row[val_col].strip().replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            if mid in HHSIZE_MEMBER_IDS:
                data[geo]["hhsize"][HHSIZE_MEMBER_IDS[mid]] = val
            elif mid in TENURE_MEMBER_IDS:
                data[geo]["tenure"][TENURE_MEMBER_IDS[mid]] = val

    return dict(data)


def scale_controls(
    raw: dict[str, dict[str, dict[str, float]]],
    target_total: int,
) -> dict[str, dict[str, dict[str, int]]]:
    hhsize_grand = sum(
        sum(v.values()) for d in raw.values() for k, v in d.items() if k == "hhsize"
    )
    if hhsize_grand == 0:
        raise ValueError("no household-size totals found")
    scale = target_total / hhsize_grand

    out: dict[str, dict[str, dict[str, int]]] = {}
    for ada in sorted(raw):
        hhsize_cats = raw[ada].get("hhsize", {})
        hhsize_scaled = {
            cat: round(count * scale) for cat, count in hhsize_cats.items()
        }
        hhsize_total = sum(hhsize_scaled.values())

        tenure_cats = raw[ada].get("tenure", {})
        tenure_raw_total = sum(tenure_cats.values())

        if tenure_raw_total == 0 or hhsize_total == 0:
            out[ada] = {
                "hhsize": {cat: 0 for cat in hhsize_scaled},
                "tenure": {cat: 0 for cat in tenure_cats}
                if tenure_cats
                else {"1": 0, "2": 0},
            }
            continue

        tenure_scale = hhsize_total / tenure_raw_total
        tenure_scaled = {
            cat: round(count * tenure_scale) for cat, count in tenure_cats.items()
        }
        # Fix rounding drift
        diff = hhsize_total - sum(tenure_scaled.values())
        if diff != 0:
            largest = max(tenure_scaled, key=lambda c: tenure_scaled[c])
            tenure_scaled[largest] += diff

        out[ada] = {"hhsize": hhsize_scaled, "tenure": tenure_scaled}
    return out


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
                if int(row[hhsize_col]) > cap:
                    row[hhsize_col] = str(cap)
            except (ValueError, KeyError):
                pass
            writer.writerow(row)
            n += 1
    return n


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=5_500_000)
    parser.add_argument(
        "--households",
        type=Path,
        default=Path(
            "data/private/benchmarks/ontario-2016-all-fields/synthetic-households-5.5m.csv"
        ),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/private/small-area"))
    parser.add_argument("--profile", type=Path, default=ADA_PROFILE_PATH)
    args = parser.parse_args(argv)

    suffix = str(args.target)

    print(f"Extracting controls from ADA profile: {args.profile}")
    raw = extract_ada_controls(args.profile)
    n_hhsize = sum(1 for d in raw.values() if d.get("hhsize"))
    n_tenure = sum(1 for d in raw.values() if d.get("tenure"))
    print(f"  ADAs with hhsize: {n_hhsize}  tenure: {n_tenure}")

    # Drop ADAs missing either margin — they cause IPF dimension mismatches
    complete = {
        ada: d
        for ada, d in raw.items()
        if d.get("hhsize")
        and sum(d["hhsize"].values()) > 0
        and d.get("tenure")
        and sum(d["tenure"].values()) > 0
    }
    dropped = len(raw) - len(complete)
    if dropped:
        print(f"  Dropped {dropped} ADA(s) missing hhsize or tenure data")
    raw = complete

    print(f"Scaling to {args.target:,} households")
    scaled = scale_controls(raw, args.target)

    hhsize_total = sum(sum(m["hhsize"].values()) for m in scaled.values())
    tenure_total = sum(sum(m["tenure"].values()) for m in scaled.values())
    print(f"  Scaled hhsize total: {hhsize_total:,}  (target: {args.target:,})")
    print(f"  Scaled tenure total: {tenure_total:,}")

    controls_out = args.out_dir / f"ontario-ada-controls-{suffix}.csv"
    write_combined_controls(scaled, controls_out)
    print(f"Controls → {controls_out}")

    persons_path = Path(str(args.households).replace("households", "persons"))
    candidates_out = args.out_dir / "ontario-ada-candidates-households-recoded.csv"
    n = write_recoded_candidates(args.households, candidates_out)
    print(
        f"Recoded candidates ({n:,} rows, household_size capped at 5) → {candidates_out}"
    )

    print("\nNext step:")
    print("  uv run synthpopcan geo calibrate-linked \\")
    print(f"    --households {candidates_out} \\")
    print(f"    --persons {persons_path} \\")
    print(f"    --controls {controls_out} \\")
    print("    --geo-dimension ada \\")
    print("    --geo-column ada \\")
    print("    --pool-size 10000 \\")
    print(
        f"    --households-out {args.out_dir}/ontario-ada-synthetic-households-{suffix}.csv \\"
    )
    print(
        f"    --persons-out {args.out_dir}/ontario-ada-synthetic-persons-{suffix}.csv \\"
    )
    print(f"    --report {args.out_dir}/ontario-ada-calibration-report-{suffix}.json")


if __name__ == "__main__":
    main()
