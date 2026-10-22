"""Shared synthetic data and assertions for test_control_packs.py."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from itertools import product
from pathlib import Path

from synthpopcan.control_packs import (
    ControlPackEvidence,
    apply_control_pack_derivations,
    build_control_pack_evidence,
    load_compatibility_registry,
    load_control_pack,
)
from synthpopcan.controls import (
    ControlCell,
    ControlMargin,
    ControlTable,
)

_GEOGRAPHY_IDS = {
    "csd": "2466023",
    "ct": "4620055.00",
    "ada": "24660239",
    "da": "24660244",
}


_RELEASED_CORE_PACK_HASHES = {
    "statcan-2016-core-private-household-csd-v1": (
        "4209134e304bf7fb1d240e1d238c9e352fc7f7d6ab4cb66585a2426bd91a4820"
    ),
    "statcan-2016-core-private-household-ct-v1": (
        "5bd972460b1ebb18ddfff43ad0ef9d1681eedf6250d5f5a268386b08698d88b4"
    ),
    "statcan-2016-core-private-household-ada-v1": (
        "8b9cde2c15acada5941dd62f3efe050fdc923f02db1d93eb3c0fd518efaf6948"
    ),
    "statcan-2016-core-private-household-da-v1": (
        "48d47e976e8ef1deef0ae080120763c7dd405e663ebcd4a5007212bda929086f"
    ),
    "statcan-2021-core-private-household-csd-v1": (
        "725cb1b151c18182f76fb8c06dfab8ccb0f32ec0530663d3189f9fc5630b10ff"
    ),
    "statcan-2021-core-private-household-ct-v1": (
        "65c54ab30692638bed6b98989c3b12521d1eb0798e0191bb966d96ea59babb7e"
    ),
    "statcan-2021-core-private-household-ada-v1": (
        "11f0fa365b60a83b1e446df77b225265bf8822195d47c22bf28c2fac6c95fb22"
    ),
    "statcan-2021-core-private-household-da-v1": (
        "0fa1e1810aebfe88799210aac5d85da22428f9ecbc405445728e8c299b5fce00"
    ),
}


def _population(vintage: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sex_field = "SEX" if vintage == 2016 else "GENDER"
    households: list[dict[str, str]] = []
    persons: list[dict[str, str]] = []
    person_index = 0
    for size in range(1, 6):
        household_id = f"h{size}"
        households.append(
            {
                "synthetic_household_id": household_id,
                "household_size": str(size),
                "TENUR": "1" if size % 2 else "2",
                "DTYPE": str((size - 1) % 3 + 1),
                "CONDO": str(size % 2),
                "BEDRM": str(size - 1),
                "ROOM": str((1, 5, 6, 7, 8)[size - 1]),
                "NOS": (
                    str(1 if size % 2 else 2)
                    if vintage == 2016
                    else str(1 if size % 2 else 0)
                ),
                "BUILT": str((1, 4, 6, 8, 11)[size - 1]),
                "REPAIR": str((size - 1) % 3 + 1),
            }
        )
        for _member in range(size):
            age = ("1", "4", "14")[person_index % 3]
            sex = ("1", "2")[(person_index // 3) % 2]
            persons.append(
                {
                    "synthetic_person_id": f"p{person_index + 1}",
                    "synthetic_household_id": household_id,
                    "AGEGRP": age,
                    sex_field: sex,
                    "TOTINC": str(person_index % 4),
                    "CITIZEN": str(person_index % 3 + 1),
                    "IMMSTAT": str(person_index % 3 + 1),
                    "GENSTAT": str(person_index % 4 + 1),
                    "VISMIN": str(
                        (1, 2)[person_index % 2]
                        if vintage == 2016
                        else (1, 0)[person_index % 2]
                    ),
                }
            )
            person_index += 1
    return households, persons


def _expanded_population(
    vintage: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Cover every category in each reviewed expanded-pack margin."""

    sex_field = "SEX" if vintage == 2016 else "GENDER"
    sizes = (1, 2, 3, 4, 5, 1, 2, 3)
    built_codes = (
        ("1", "4", "6", "7", "9", "10", "11", "1")
        if vintage == 2016
        else ("1", "3", "5", "6", "8", "9", "10", "11")
    )
    households: list[dict[str, str]] = []
    persons: list[dict[str, str]] = []
    person_index = 0
    for index, (size, built) in enumerate(
        zip(sizes, built_codes, strict=True), start=1
    ):
        household_id = f"eh{index}"
        households.append(
            {
                "synthetic_household_id": household_id,
                "household_size": str(size),
                "TENUR": str(1 if index % 2 else 2),
                "DTYPE": str((index - 1) % 3 + 1),
                "CONDO": str(index % 2),
                "BEDRM": str((index - 1) % 5),
                "ROOM": str((1, 5, 6, 7, 8)[(index - 1) % 5]),
                "NOS": str(1 if index % 2 else (2 if vintage == 2016 else 0)),
                "BUILT": built,
                "REPAIR": str(3 if index % 3 == 0 else 1),
            }
        )
        for _member in range(size):
            age, sex = (
                ("1", "1"),
                ("1", "2"),
                ("4", "1"),
                ("4", "2"),
                ("14", "1"),
                ("14", "2"),
            )[person_index % 6]
            persons.append(
                {
                    "synthetic_person_id": f"ep{person_index + 1}",
                    "synthetic_household_id": household_id,
                    "AGEGRP": age,
                    sex_field: sex,
                    "TOTINC": str(person_index % 4),
                    "CITIZEN": str(person_index % 3 + 1),
                    "IMMSTAT": str(person_index % 3 + 1),
                    "GENSTAT": str(person_index % 4 + 1),
                    "VISMIN": str(
                        (1, 2)[person_index % 2]
                        if vintage == 2016
                        else (1, 0)[person_index % 2]
                    ),
                }
            )
            person_index += 1
    return households, persons


def _tables(
    pack_id: str,
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    geographies: tuple[str, ...],
) -> tuple[ControlTable, ControlTable]:
    pack = load_control_pack(pack_id)
    derived_households, derived_persons = apply_control_pack_derivations(
        pack, households, persons
    )
    size_counts = Counter(row["household_size_group"] for row in derived_households)
    tenure_counts = Counter(row["TENUR"] for row in derived_households)
    sex_field = "SEX" if pack.census_vintage == 2016 else "GENDER"
    person_counts = Counter(
        (row["age_group_3"], row[sex_field]) for row in derived_persons
    )
    size_cells = tuple(
        ControlCell(
            {pack.geography_column: geography, "household_size_group": category},
            size_counts[category],
        )
        for geography in geographies
        for category in ("1", "2", "3", "4", "5")
    )
    tenure_cells = tuple(
        ControlCell(
            {pack.geography_column: geography, "TENUR": category},
            tenure_counts[category],
        )
        for geography in geographies
        for category in ("1", "2")
    )
    person_cells = tuple(
        ControlCell(
            {
                pack.geography_column: geography,
                "age_group_3": age,
                sex_field: sex,
            },
            person_counts[(age, sex)],
        )
        for geography in geographies
        for age in ("0_14", "15_64", "65_plus")
        for sex in ("1", "2")
    )
    household_controls = ControlTable(
        margins=(
            ControlMargin(
                "household size",
                (pack.geography_column, "household_size_group"),
                size_cells,
            ),
            ControlMargin(
                "tenure",
                (pack.geography_column, "TENUR"),
                tenure_cells,
            ),
        ),
        dimensions=(pack.geography_column, "household_size_group", "TENUR"),
    )
    person_controls = ControlTable(
        margins=(
            ControlMargin(
                "broad age by sex/gender",
                (pack.geography_column, "age_group_3", sex_field),
                person_cells,
            ),
        ),
        dimensions=(pack.geography_column, "age_group_3", sex_field),
    )
    return household_controls, person_controls


def _expanded_tables(
    pack_id: str,
    households: list[dict[str, str]],
    persons: list[dict[str, str]],
    *,
    geography: str,
) -> tuple[ControlTable, ControlTable]:
    pack = load_control_pack(pack_id)
    definitions = {
        control.identifier: control
        for control in load_compatibility_registry().controls
    }
    derived_households, derived_persons = apply_control_pack_derivations(
        pack, households, persons
    )
    household_margins: list[ControlMargin] = []
    household_dimensions: set[str] = {pack.geography_column}
    for margin in pack.margins:
        if margin.entity_level != "household":
            continue
        dimension = margin.dimensions[1]
        household_dimensions.add(dimension)
        counts = Counter(row[dimension] for row in derived_households)
        categories = tuple(
            category.target_category
            for category in definitions[margin.control_identifier]
            .source_axes[0]
            .categories
        )
        household_margins.append(
            ControlMargin(
                margin.control_identifier,
                tuple(margin.dimensions),
                tuple(
                    ControlCell(
                        {pack.geography_column: geography, dimension: category},
                        count,
                    )
                    for category in categories
                    for count in (counts[category],)
                ),
            )
        )
    person_margins: list[ControlMargin] = []
    person_dimensions: set[str] = {pack.geography_column}
    for margin in pack.margins:
        if margin.entity_level != "person":
            continue
        dimensions = tuple(margin.dimensions[1:])
        person_dimensions.update(dimensions)
        counts = Counter(
            tuple(row[dimension] for dimension in dimensions) for row in derived_persons
        )
        axes = definitions[margin.control_identifier].source_axes
        categories = tuple(
            tuple(category.target_category for category in axis.categories)
            for axis in axes
        )
        person_margins.append(
            ControlMargin(
                margin.control_identifier,
                tuple(margin.dimensions),
                tuple(
                    ControlCell(
                        {
                            pack.geography_column: geography,
                            **dict(zip(dimensions, combination, strict=True)),
                        },
                        counts[combination],
                    )
                    for combination in product(*categories)
                ),
            )
        )
    person_controls = ControlTable(
        margins=tuple(person_margins),
        dimensions=tuple(sorted(person_dimensions)),
    )
    return (
        ControlTable(
            margins=tuple(household_margins),
            dimensions=tuple(sorted(household_dimensions)),
        ),
        person_controls,
    )


def _evidence(
    pack_id: str,
    household_controls: ControlTable,
    person_controls: ControlTable,
    geographies: tuple[str, ...],
    *,
    collective_people: int = 0,
    private_people: int = 15,
) -> ControlPackEvidence:
    pack = load_control_pack(pack_id)
    return build_control_pack_evidence(
        pack,
        household_controls,
        person_controls,
        geographies={
            geography: {
                "total_population": private_people + collective_people,
                "persons_in_private_households": private_people,
            }
            for geography in geographies
        },
        controls_source_revisions=pack.source_revisions,
    )


def _semantic_checksum(payload: dict[str, object]) -> str:
    semantic = dict(payload)
    semantic.pop("definition_sha256", None)
    encoded = json.dumps(
        semantic,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _issue_kinds(plan: dict[str, object]) -> set[str]:
    issues = plan["issues"]
    assert isinstance(issues, list)
    return {str(issue["kind"]) for issue in issues}


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
