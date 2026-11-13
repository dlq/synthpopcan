"""Export the verified IVT tract cells used by the conditional packs."""

import argparse
import csv
import hashlib
import re
from pathlib import Path

SOURCES = {
    2016: ("2d4df7fcf4b77ba97f2c31c1438f02a07b7537f488651ef07c3aca798291b215", "sex_3"),
    2021: (
        "01c2b85e3cd9dfb75dc41294fa5d31ba850fc4ae0956ca3933e6e08784e3331b",
        "gender_3",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vintage", type=int, choices=SOURCES)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    expected, sex = SOURCES[args.vintage]
    with args.source.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
            parser.error("IVT SHA-256 differs from the reviewed deposit")
    import pyivt  # type: ignore[import-not-found]

    table = pyivt.open(args.source)
    geographies = {}
    for row in table.members()["geography"].to_pylist():
        if args.vintage == 2016:
            identifier = row["UID/IDU"]
        else:
            match = re.match(r"^(\d{7}\.\d{2})\s+\(CT\)", row["label"])
            identifier = match[1] if match else None
        if identifier and re.fullmatch(r"\d{7}\.\d{2}", identifier):
            geographies[row["code"]] = identifier
    if len(geographies) != len(set(geographies.values())):
        parser.error("Duplicate Census tract identifiers in IVT")
    cells = table.to_arrow(
        geography=list(geographies),
        marital_status=[1, 3, 4, 6, 7, 8, 9],
        age_20=[1, 2, 3, *range(6, 16)],
        disability_3=[1],
        household_type=[1],
        **{sex: [1]},
    )
    with args.output.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ct", "marital_status", "age_20", "value"])
        for batch in cells.to_batches():
            for row in batch.to_pylist():
                value = row["value"]
                writer.writerow(
                    [
                        geographies[row["geography"]],
                        row["marital_status"],
                        row["age_20"],
                        "" if value is None else format(value, ".17g"),
                    ]
                )


if __name__ == "__main__":
    main()
