"""Build an aggregate-only Nunavut comparison from two synthetic populations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_PINNED_EXTERNAL_SHA256 = (
    "0d06e1c2932c027d6750cc48615041d085c50b910a7334ed4e3a0487fc3fb935"
)
_PINNED_MEMBER = "Canada/nunavut/syn_pop/FA/synthetic_pop_2021_hh_.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external", type=Path, required=True)
    parser.add_argument("--households", type=Path, required=True)
    parser.add_argument("--persons", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Write JSON instead of printing it.")
    parser.add_argument(
        "--expected-external-sha256",
        default=_PINNED_EXTERNAL_SHA256,
        help="Fail unless the extracted external member has this SHA-256.",
    )
    return parser.parse_args()


def build_aggregate_comparison(
    external_path: Path,
    household_path: Path,
    person_path: Path,
    *,
    expected_external_sha256: str | None = _PINNED_EXTERNAL_SHA256,
) -> dict[str, Any]:
    """Return deterministic territory aggregates; never retain source rows."""

    external_sha256 = _sha256(external_path)
    if (
        expected_external_sha256 is not None
        and external_sha256 != expected_external_sha256
    ):
        raise ValueError("external extracted-member SHA-256 does not match the pin")
    external = _external_aggregates(external_path)
    local = _local_aggregates(household_path, person_path)
    comparison = _comparison_metrics(external, local)
    return _round_floats(
        {
            "schema_version": "synthpopcan-external-aggregate-comparison-v1",
            "comparison_id": "nunavut-fa-2021-territory-aggregate-v1",
            "scope": {
                "territory": "Nunavut",
                "territory_code": "62",
                "external_scenario": "FA",
                "external_dataset_year": 2021,
                "external_geography_basis": "2016 dissemination areas",
                "synthpopcan_dataset_year": 2021,
                "synthpopcan_geography_basis": "2021 dissemination areas",
                "comparison_level": "territory aggregate only",
                "da_join_performed": False,
                "reason_no_da_join": (
                    "The external projection retains 2016 DA identities while the "
                    "SynthPopCan output uses 2021 DA identities; no crosswalk was "
                    "applied in this bounded evidence."
                ),
            },
            "sources": {
                "external": {
                    "dataset": "Prédhumeau-Manley Canadian synthetic population v2.1.0",
                    "doi": "10.5281/zenodo.7572117",
                    "archive_member": _PINNED_MEMBER,
                    "archive_member_local_header_offset": 3391658460,
                    "archive_member_compressed_bytes": 318352,
                    "archive_member_uncompressed_bytes": 1617540,
                    "archive_member_compression": "deflate",
                    "extracted_sha256": external_sha256,
                    "scenario_note": (
                        "FA is compared here because this bounded member was "
                        "extracted; it is not the LG scenario used for validation "
                        "in the associated article."
                    ),
                },
                "synthpopcan": {
                    "households_sha256": _sha256(household_path),
                    "persons_sha256": _sha256(person_path),
                    "source_scope": "2021 Nunavut DA batch output",
                },
            },
            "external_aggregates": external,
            "synthpopcan_aggregates": local,
            "comparison": comparison,
            "interpretation": {
                "truth_status": (
                    "Both inputs are synthetic model outputs; neither is observed "
                    "record-level truth or an oracle."
                ),
                "allowed_use": (
                    "A deterministic method-to-method territory aggregate check of "
                    "scale, linkage, and household-size composition."
                ),
                "disallowed_use": (
                    "No DA-level agreement, national quality, scenario superiority, "
                    "or local-representativeness claim is supported."
                ),
                "category_crosswalk": (
                    "Sex/gender raw-code distributions are reported separately but "
                    "not compared because no vintage-aware semantic crosswalk was "
                    "approved."
                ),
            },
            "public_safety": {
                "contains_source_rows": False,
                "contains_direct_identifiers": False,
                "aggregate_only": True,
                "minimum_released_unit": "territory",
            },
        }
    )


def _external_aggregates(path: Path) -> dict[str, Any]:
    household_sizes: Counter[tuple[str, str]] = Counter()
    raw_sex: Counter[str] = Counter()
    areas: set[str] = set()
    total_persons = 0
    unlinked_persons = 0
    outside_scope = 0
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, {"HID", "sex", "area"}, "external")
        for row in reader:
            total_persons += 1
            area = row["area"]
            areas.add(area)
            outside_scope += not area.startswith("62")
            raw_sex[row["sex"]] += 1
            household_id = row["HID"]
            if not household_id or household_id == "-1":
                unlinked_persons += 1
                continue
            household_sizes[(area, household_id)] += 1
    size_distribution = _size_distribution(household_sizes.values())
    linked_persons = sum(household_sizes.values())
    households = len(household_sizes)
    return {
        "person_rows": total_persons,
        "linked_person_rows": linked_persons,
        "unlinked_person_rows": unlinked_persons,
        "derived_linked_households": households,
        "mean_linked_household_size": _ratio(linked_persons, households),
        "derived_household_size_distribution": size_distribution,
        "distinct_da_codes": len(areas),
        "rows_outside_territory_prefix": outside_scope,
        "raw_sex_code_counts_not_crosswalked": dict(sorted(raw_sex.items())),
    }


def _local_aggregates(household_path: Path, person_path: Path) -> dict[str, Any]:
    household_areas: dict[str, str] = {}
    declared_sizes: Counter[str] = Counter()
    with household_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(
            reader.fieldnames,
            {"synthetic_household_id", "DAUID", "household_size"},
            "SynthPopCan household",
        )
        for row in reader:
            household_id = row["synthetic_household_id"]
            if household_id in household_areas:
                raise ValueError(f"duplicate SynthPopCan household ID {household_id!r}")
            household_areas[household_id] = row["DAUID"]
            declared_sizes[row["household_size"]] += 1

    observed_sizes: Counter[str] = Counter()
    raw_gender: Counter[str] = Counter()
    person_areas: set[str] = set()
    person_rows = 0
    linked_person_rows = 0
    orphan_person_rows = 0
    geography_link_mismatches = 0
    persons_outside_scope = 0
    with person_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(
            reader.fieldnames,
            {"synthetic_household_id", "DAUID", "GENDER"},
            "SynthPopCan person",
        )
        for row in reader:
            person_rows += 1
            raw_gender[row["GENDER"]] += 1
            person_areas.add(row["DAUID"])
            persons_outside_scope += not row["DAUID"].startswith("62")
            household_id = row["synthetic_household_id"]
            household_area = household_areas.get(household_id)
            if household_area is None:
                orphan_person_rows += 1
                continue
            linked_person_rows += 1
            observed_sizes[household_id] += 1
            geography_link_mismatches += household_area != row["DAUID"]

    counts = [observed_sizes.get(household_id, 0) for household_id in household_areas]
    household_areas_set = set(household_areas.values())
    return {
        "person_rows": person_rows,
        "linked_person_rows": linked_person_rows,
        "orphan_person_rows": orphan_person_rows,
        "households": len(household_areas),
        "empty_households_from_linkage": sum(count == 0 for count in counts),
        "mean_linked_household_size": _ratio(linked_person_rows, len(household_areas)),
        "derived_household_size_distribution": _size_distribution(counts),
        "declared_household_size_code_counts": dict(sorted(declared_sizes.items())),
        "distinct_household_da_codes": len(household_areas_set),
        "distinct_person_da_codes": len(person_areas),
        "household_person_da_set_symmetric_difference": len(
            household_areas_set.symmetric_difference(person_areas)
        ),
        "household_person_geography_link_mismatches": geography_link_mismatches,
        "households_outside_territory_prefix": sum(
            not area.startswith("62") for area in household_areas.values()
        ),
        "persons_outside_territory_prefix": persons_outside_scope,
        "raw_gender_code_counts_not_crosswalked": dict(sorted(raw_gender.items())),
    }


def _comparison_metrics(
    external: Mapping[str, Any], local: Mapping[str, Any]
) -> dict[str, Any]:
    metrics = {
        "linked_person_rows": (
            int(external["linked_person_rows"]),
            int(local["linked_person_rows"]),
        ),
        "linked_households": (
            int(external["derived_linked_households"]),
            int(local["households"]),
        ),
        "mean_linked_household_size": (
            float(external["mean_linked_household_size"]),
            float(local["mean_linked_household_size"]),
        ),
    }
    deltas = {
        name: {
            "external": external_value,
            "synthpopcan": local_value,
            "synthpopcan_minus_external": local_value - external_value,
            "percent_relative_to_external": (
                100.0 * (local_value - external_value) / external_value
                if external_value
                else None
            ),
        }
        for name, (external_value, local_value) in metrics.items()
    }
    external_distribution = external["derived_household_size_distribution"]
    local_distribution = local["derived_household_size_distribution"]
    bands = ("0", "1", "2", "3", "4", "5+")
    band_deltas = {
        band: (
            float(local_distribution["proportions"][band])
            - float(external_distribution["proportions"][band])
        )
        for band in bands
    }
    return {
        "metric_deltas": deltas,
        "household_size_proportion_deltas": band_deltas,
        "household_size_total_variation_distance": (
            0.5 * sum(abs(delta) for delta in band_deltas.values())
        ),
    }


def _size_distribution(counts: Any) -> dict[str, Any]:
    bands = Counter({band: 0 for band in ("0", "1", "2", "3", "4", "5+")})
    for count in counts:
        band = str(count) if count < 5 else "5+"
        bands[band] += 1
    total = sum(bands.values())
    return {
        "counts": dict(sorted(bands.items())),
        "proportions": {
            band: _ratio(count, total) for band, count in sorted(bands.items())
        },
        "denominator_households": total,
    }


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 12) if denominator else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(columns: list[str] | None, required: set[str], label: str) -> None:
    missing = sorted(required - set(columns or ()))
    if missing:
        raise ValueError(f"{label} CSV is missing columns: {', '.join(missing)}")


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    return value


def render_comparison(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> None:
    args = parse_args()
    payload = build_aggregate_comparison(
        args.external,
        args.households,
        args.persons,
        expected_external_sha256=args.expected_external_sha256,
    )
    rendered = render_comparison(payload)
    if args.out is None:
        print(rendered, end="")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)


if __name__ == "__main__":
    main()
