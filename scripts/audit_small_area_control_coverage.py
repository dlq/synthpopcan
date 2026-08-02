"""Audit Census Profile coverage for all-fields small-area control candidates.

This is a source-availability screen, not approval of a statistical crosswalk.
It streams very large Profile CSVs, retaining only selected denominator rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class ControlFamily:
    """One Profile family that may control one or more all-fields columns."""

    name: str
    fields: tuple[str, ...]
    classification: str
    ids: dict[int, tuple[int, ...]]
    note: str


CONTROL_FAMILIES = (
    ControlFamily(
        "household_size",
        ("household_size",),
        "direct",
        {2016: (51,), 2021: (50,)},
        "Top-code generated household size at five or more.",
    ),
    ControlFamily(
        "tenure",
        ("TENUR",),
        "coarsened",
        {2016: (1617,), 2021: (1414,)},
        "Combine renter with band/local-government/First Nation housing.",
    ),
    ControlFamily(
        "structural_dwelling_type",
        ("DTYPE",),
        "coarsened",
        {2016: (41,), 2021: (41,)},
        "Requires a vintage-specific Profile-to-PUMF category crosswalk.",
    ),
    ControlFamily(
        "rooms",
        ("ROOM",),
        "coarsened",
        {2016: (1630,), 2021: (1427,)},
        "Profile groups one through four rooms and top-codes eight or more.",
    ),
    ControlFamily(
        "bedrooms",
        ("BEDRM",),
        "coarsened",
        {2016: (1624,), 2021: (1421,)},
        "Profile top-codes four or more bedrooms.",
    ),
    ControlFamily(
        "condominium_status",
        ("CONDO",),
        "direct",
        {2016: (1621,), 2021: (1418,)},
        "Applies to occupied private dwellings.",
    ),
    ControlFamily(
        "mortgage_status",
        ("PRESMORTG",),
        "derived-percentage",
        {2016: (1671, 1672), 2021: (1482, 1483)},
        "Would derive approximate counts from a rounded percentage of owners.",
    ),
    ControlFamily(
        "subsidized_housing",
        ("SUBSIDY",),
        "derived-percentage",
        {2016: (1678, 1679), 2021: (1490, 1491)},
        "Would derive approximate counts from a rounded percentage of tenants.",
    ),
    ControlFamily(
        "dwelling_condition",
        ("REPAIR",),
        "direct",
        {2016: (1651,), 2021: (1449,)},
        "Two Profile categories align with the generated repair field.",
    ),
    ControlFamily(
        "period_of_construction",
        ("BUILT",),
        "coarsened",
        {2016: (1643,), 2021: (1440,)},
        "Requires vintage-specific construction-period grouping.",
    ),
    ControlFamily(
        "housing_suitability",
        ("NOS",),
        "direct",
        {2016: (1640,), 2021: (1437,)},
        "Suitable versus not suitable.",
    ),
    ControlFamily(
        "age_and_gender",
        ("AGEGRP", "SEX/GENDER"),
        "coarsened-joint",
        {2016: (8,), 2021: (8,)},
        "Use broad age rows crossed with the Profile sex/gender count columns.",
    ),
    ControlFamily(
        "marital_status",
        ("MarStH/MARSTH",),
        "coarsened",
        {2016: (59,), 2021: (58,)},
        "Restrict to the shared population aged 15 years and over universe.",
    ),
    ControlFamily(
        "citizenship",
        ("CITIZEN",),
        "coarsened",
        {2016: (1135,), 2021: (1522,)},
        "Use a reviewed summary crosswalk for persons in private households.",
    ),
    ControlFamily(
        "immigration_status",
        ("IMMSTAT",),
        "coarsened",
        {2016: (1140,), 2021: (1527,)},
        "Separate status from period-of-immigration detail.",
    ),
    ControlFamily(
        "generation_status",
        ("GENSTAT",),
        "direct",
        {2016: (1278,), 2021: (1665,)},
        "First, second, and third-or-later generation.",
    ),
    ControlFamily(
        "place_of_birth",
        ("POB",),
        "conditional-coarsened",
        {2016: (1157,), 2021: (1544,)},
        "Profile detail is for immigrants; combine with immigration status.",
    ),
    ControlFamily(
        "visible_minority",
        ("VISMIN",),
        "coarsened",
        {2016: (1323,), 2021: (1683,)},
        "Requires a reviewed vintage-specific category crosswalk.",
    ),
    ControlFamily(
        "mother_tongue_components",
        ("MTNEn/MTNEN", "MTNFr/MTNFR", "MTNNO"),
        "derived-components",
        {2016: (112,), 2021: (393,)},
        "Derive component indicators while preserving multiple responses.",
    ),
    ControlFamily(
        "home_language_components",
        ("HLBEN/HLMOSTEN", "HLBFR/HLMOSTFR", "HLBNO/HLMOSTNO"),
        "derived-components",
        {2016: (381,), 2021: (735,)},
        "Derive component indicators while preserving multiple responses.",
    ),
    ControlFamily(
        "education",
        ("HDGREE",),
        "coarsened",
        {2016: (1683,), 2021: (1998,)},
        "Use the population aged 15 years and over universe.",
    ),
    ControlFamily(
        "labour_force_status",
        ("LFTAG/LFACT",),
        "coarsened",
        {2016: (1865,), 2021: (2223,)},
        "Use the population aged 15 years and over universe.",
    ),
    ControlFamily(
        "employment_income",
        ("EMPIN",),
        "banded",
        {2016: (724,), 2021: (187,)},
        "Recode generated numeric employment income to Profile bands.",
    ),
    ControlFamily(
        "work_activity",
        ("FPTWK", "WRKACT"),
        "coarsened",
        {2016: (1873,), 2021: (2231,)},
        "Did not work, full-year/full-time, or part-year/part-time.",
    ),
    ControlFamily(
        "total_income",
        ("TOTINC",),
        "banded",
        {2016: (691,), 2021: (155,)},
        "Recode generated numeric total income to Profile bands.",
    ),
)

UNSUPPORTED_FIELDS = {
    "VALUE": "Profile publishes summary value statistics, not a count distribution.",
    "SHELCO": "Profile publishes summary costs and affordability ratios, not matching cost bands.",
    "FCOND": "Profile does not publish a condominium-fee count distribution.",
    "HRSWRK": "Profile does not publish a matching hours-worked count distribution.",
    "WKSWRK": "Profile publishes average weeks, not a matching weeks-worked distribution.",
}

DEFAULT_PROFILES = (
    (
        2016,
        "csd",
        "data/raw/statcan/census/2016/profiles/csd/national/"
        "2016-census-profile-csd-all.csv",
    ),
    (
        2016,
        "ct",
        "data/raw/statcan/census/2016/profiles/ct/2016-census-profile-ct.csv",
    ),
    (
        2016,
        "ada",
        "data/raw/statcan/census/2016/profiles/ada/2016-census-profile-ada.csv",
    ),
    (
        2021,
        "csd",
        "data/raw/statcan/census/2021/profiles/csd/national/"
        "2021-census-profile-csd-all.csv",
    ),
    (
        2021,
        "ct",
        "data/raw/statcan/census/2021/profiles/ct/2021-census-profile-ct.csv",
    ),
    (
        2021,
        "ada",
        "data/raw/statcan/census/2021/profiles/ada/2021-census-profile-ada.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/atlantic/"
        "2021-census-profile-da-atlantic.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/quebec/"
        "2021-census-profile-da-quebec.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/ontario/"
        "2021-census-profile-da-ontario.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/prairies/"
        "2021-census-profile-da-prairies.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/british-columbia/"
        "2021-census-profile-da-british-columbia.csv",
    ),
    (
        2021,
        "da",
        "data/raw/statcan/census/2021/profiles/da/territories/"
        "2021-census-profile-da-territories.csv",
    ),
)

_LEVEL_VALUES = {
    (2016, "csd"): "3",
    (2016, "ct"): "2",
    (2016, "ada"): "3",
    (2016, "da"): "4",
    (2021, "csd"): "Census subdivision",
    (2021, "ct"): "Census tract",
    (2021, "ada"): "Aggregate dissemination area",
    (2021, "da"): "Dissemination area",
}


def _number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned in {"...", "..", ".", "x", "F"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _header_index(header: list[str], year: int) -> dict[str, int]:
    normalized = [item.lstrip("\ufeff") for item in header]
    if year == 2021:
        names = {
            "geo": "DGUID",
            "level": "GEO_LEVEL",
            "characteristic": "CHARACTERISTIC_ID",
            "value": "C1_COUNT_TOTAL",
        }
    else:
        member_name = next(
            item for item in normalized if item.startswith("Member ID: Profile of ")
        )
        total_name = next(
            item for item in normalized if item.endswith("Member ID: [1]: Total - Sex")
        )
        names = {
            "geo": "ALT_GEO_CODE",
            "level": "GEO_LEVEL",
            "characteristic": member_name,
            "value": total_name,
        }
    return {key: normalized.index(name) for key, name in names.items()}


def scan_profile(
    handle: BinaryIO,
    *,
    year: int,
    level: str,
) -> dict[str, object]:
    """Stream one Profile CSV and return denominator availability by family."""
    header_line = handle.readline()
    if not header_line:
        raise ValueError("Profile CSV is empty")
    header = next(csv.reader([header_line.decode("latin-1")]))
    index = _header_index(header, year)
    selected_ids = {1}
    for family in CONTROL_FAMILIES:
        selected_ids.update(family.ids[year])
    csv_field = rb'(?:"(?:[^"]|"")*"|[^,\r\n]*),'
    selected_pattern = re.compile(
        rb"^"
        + csv_field * index["characteristic"]
        + rb"(?:"
        + b"|".join(str(item).encode() for item in sorted(selected_ids))
        + rb"),[^\r\n]*",
        re.MULTILINE,
    )
    numeric_geographies: dict[int, set[str]] = defaultdict(set)
    positive_geographies: dict[int, set[str]] = defaultdict(set)
    target_geographies: set[str] = set()
    expected_level = _LEVEL_VALUES[(year, level)]

    process: subprocess.Popen[bytes] | None = None
    ripgrep = shutil.which("rg")
    path_name = getattr(handle, "name", None)
    if ripgrep is not None and isinstance(path_name, str) and Path(path_name).is_file():
        process = subprocess.Popen(  # noqa: S603
            [
                ripgrep,
                "--pcre2",
                "--no-line-number",
                "--no-filename",
                selected_pattern.pattern.decode(),
                path_name,
            ],
            stdout=subprocess.PIPE,
        )
        if process.stdout is None:
            raise RuntimeError("ripgrep did not provide an output stream")
        selected_lines = process.stdout
    else:
        selected_lines = (
            raw_line for raw_line in handle if selected_pattern.match(raw_line)
        )

    for raw_line in selected_lines:
        row = next(csv.reader([raw_line.decode("latin-1")]))
        if row[index["level"]] != expected_level:
            continue
        try:
            characteristic_id = int(row[index["characteristic"]])
        except ValueError:
            continue
        if characteristic_id not in selected_ids:
            continue
        geography_id = row[index["geo"]]
        if characteristic_id == 1:
            target_geographies.add(geography_id)
        value = _number(row[index["value"]])
        if value is not None:
            numeric_geographies[characteristic_id].add(geography_id)
            if value > 0:
                positive_geographies[characteristic_id].add(geography_id)

    if process is not None and process.wait() not in {0, 1}:
        raise RuntimeError("ripgrep failed while filtering the Profile CSV")

    families: dict[str, dict[str, int]] = {}
    for family in CONTROL_FAMILIES:
        required = family.ids[year]
        usable = set(positive_geographies[required[0]])
        for characteristic_id in required[1:]:
            usable.intersection_update(numeric_geographies[characteristic_id])
        families[family.name] = {
            "positive_denominator_geographies": len(usable),
        }
    return {
        "geographies": len(target_geographies),
        "positive_population_geographies": len(positive_geographies[1]),
        "families": families,
    }


def _parse_profile(value: str) -> tuple[int, str, str]:
    year_text, level, path = value.split(":", 2)
    year = int(year_text)
    if year not in {2016, 2021} or level not in {"csd", "ct", "ada", "da"}:
        raise argparse.ArgumentTypeError("profile must be YEAR:LEVEL:PATH")
    return year, level, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        action="append",
        type=_parse_profile,
        help="Profile input as YEAR:LEVEL:PATH; use - for decompressed stdin.",
    )
    parser.add_argument(
        "--no-defaults",
        action="store_true",
        help="Do not scan conventional local Profile paths.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profiles = [] if args.no_defaults else list(DEFAULT_PROFILES)
    profiles.extend(args.profile or [])
    results: dict[str, dict[str, object]] = {}
    missing_profiles: list[dict[str, object]] = []
    for year, level, path_text in profiles:
        if path_text != "-" and not Path(path_text).is_file():
            missing_profiles.append({"year": year, "level": level, "path": path_text})
            continue
        key = f"{year}-{level}"
        handle = sys.stdin.buffer if path_text == "-" else Path(path_text).open("rb")
        try:
            scanned = scan_profile(handle, year=year, level=level)
        finally:
            if path_text != "-":
                handle.close()
        if key not in results:
            results[key] = scanned
            continue
        current = results[key]
        current["geographies"] = int(current["geographies"]) + int(
            scanned["geographies"]
        )
        current["positive_population_geographies"] = int(
            current["positive_population_geographies"]
        ) + int(scanned["positive_population_geographies"])
        current_families = current["families"]
        scanned_families = scanned["families"]
        if not isinstance(current_families, dict) or not isinstance(
            scanned_families, dict
        ):
            raise TypeError("invalid family result")
        for family_name, family_result in scanned_families.items():
            if not isinstance(family_result, dict):
                raise TypeError("invalid family result")
            target = current_families[family_name]
            if not isinstance(target, dict):
                raise TypeError("invalid family result")
            target["positive_denominator_geographies"] = int(
                target["positive_denominator_geographies"]
            ) + int(family_result["positive_denominator_geographies"])

    supported_fields = sorted(
        field for family in CONTROL_FAMILIES for field in family.fields
    )
    count_based_fields = sorted(
        field
        for family in CONTROL_FAMILIES
        if family.classification != "derived-percentage"
        for field in family.fields
    )
    percentage_derived_fields = sorted(
        field
        for family in CONTROL_FAMILIES
        if family.classification == "derived-percentage"
        for field in family.fields
    )
    output = {
        "schema_version": "synthpopcan-small-area-control-coverage-audit-v1",
        "method": (
            "Positive Profile family denominators screen source availability; "
            "they do not approve category crosswalks or statistical fitness."
        ),
        "all_fields_count": len(supported_fields) + len(UNSUPPORTED_FIELDS),
        "candidate_field_count": len(supported_fields),
        "candidate_fields": supported_fields,
        "count_based_candidate_field_count": len(count_based_fields),
        "count_based_candidate_fields": count_based_fields,
        "percentage_derived_candidate_field_count": len(percentage_derived_fields),
        "percentage_derived_candidate_fields": percentage_derived_fields,
        "unsupported_field_count": len(UNSUPPORTED_FIELDS),
        "unsupported_fields": UNSUPPORTED_FIELDS,
        "missing_profiles": missing_profiles,
        "families": [
            {
                "name": family.name,
                "fields": family.fields,
                "classification": family.classification,
                "profile_characteristic_ids": family.ids,
                "note": family.note,
            }
            for family in CONTROL_FAMILIES
        ],
        "coverage": results,
    }
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
