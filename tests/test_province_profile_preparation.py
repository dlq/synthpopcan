"""Province-wide observed ADA controls retain complete geography coverage evidence."""

from __future__ import annotations

import csv
import hashlib
import json

import pytest

from synthpopcan._profile_preparation import (
    AGE_CONTROL,
    observed_count,
    prepare_profile_controls,
    select_province_profile,
    workflow_controls,
)
from synthpopcan.controls import read_control_table

FIELDS = [
    "CENSUS_YEAR",
    "DGUID",
    "ALT_GEO_CODE",
    "GEO_LEVEL",
    "CHARACTERISTIC_ID",
    "C1_COUNT_TOTAL",
    "C2_COUNT_MEN+",
    "C3_COUNT_WOMEN+",
]


def source_rows(geo, level, households, private, population):
    pack, definitions = workflow_controls("ada")
    counts = {}
    for margin in pack.margins:
        control = definitions[margin.control_identifier]
        for axis in control.source_axes:
            for category in axis.categories:
                for member in category.source_characteristic_ids:
                    counts[member] = 0
        first = control.source_axes[0].categories[0].source_characteristic_ids[0]
        count = 5 if margin.entity_level == "household" else private
        if control.identifier == AGE_CONTROL:
            count = population
        counts[first] = count
        counts[control.source.root_characteristic_id] = count
    counts.update(
        {
            "1": population,
            "4": households + 2,
            "5": households,
            "8": population,
            "50": 5,
            "56": private,
        }
    )
    dguid = f"2021A0002{geo}" if level == "Province" else f"2021S0516{geo}"
    return [
        {
            "CENSUS_YEAR": "2021",
            "DGUID": dguid,
            "ALT_GEO_CODE": geo,
            "GEO_LEVEL": level,
            "CHARACTERISTIC_ID": member,
            "C1_COUNT_TOTAL": str(counts[member]),
            "C2_COUNT_MEN+": "0",
            "C3_COUNT_WOMEN+": str(counts[member]),
        }
        for member in sorted(counts, key=int)
    ]


def write_profile(path, rows):
    with path.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def fixture_rows(scope="ada"):
    parent, first, second = (
        ("24", "24010001", "24010002")
        if scope == "ada"
        else ("462", "4620001.00", "4620002.00")
    )
    level = "Aggregate dissemination area" if scope == "ada" else "Census tract"
    root_level = "Province" if scope == "ada" else "Census metropolitan area"
    parents = source_rows(parent, root_level, 9, 25, 30)
    areas = [
        *source_rows(first, level, 4, 10, 10),
        *source_rows(second, level, 5, 15, 20),
        *source_rows("35010001", "Aggregate dissemination area", 90, 200, 200),
        *source_rows("2401001", "Census subdivision", 100, 200, 200),
    ]
    return parents, areas


@pytest.fixture
def profiles(tmp_path):
    parents, areas = fixture_rows()
    source, parent = tmp_path / "areas.csv", tmp_path / "province.csv"
    write_profile(source, areas)
    write_profile(parent, parents)
    return source, parent, parents, areas


def prepared(source, parent, output, *, policy="error"):
    return prepare_profile_controls(
        source,
        None,
        output,
        policy,
        province="24",
        geo_level="ada",
        province_profile=parent,
    )


def test_province_uses_exact_each_ada_household_count_and_separate_person_totals(
    tmp_path, profiles
):
    source, parent, _parents, _areas = profiles
    output = tmp_path / "controls"
    plan = prepared(source, parent, output)
    assert plan["target_households"] == plan["province_households"] == 9
    assert plan["target_persons"] == plan["province_private_persons"] == 25
    assert plan["province_total_persons"] == 30
    assert plan["geographies"] == ["24010001", "24010002"]
    assert plan["geography_level"] == plan["geography_dimension"] == "ada"
    assert plan["coverage"]["household_coverage_complete"]
    assert "tracts" not in plan and "excluded_tracts" not in plan
    batches = {b["name"]: b for b in plan["batches"]}
    assert batches["zero-collective"]["geographies"] == ["24010001"]
    assert batches["private-households"]["geographies"] == ["24010002"]
    assert batches["zero-collective"]["target_households"] == 4
    assert batches["private-households"]["target_households"] == 5
    table = read_control_table(output / "zero-collective/household-controls.csv")
    assert all(sum(c.count for c in m.cells) == 4 for m in table.margins)
    assert all(m.name.startswith("ada ") for m in table.margins)
    assert "ada" in table.dimensions and "ct" not in table.dimensions
    normalization = json.loads(
        (output / "zero-collective/normalization.json").read_text()
    )
    assert all("ada" in record and "ct" not in record for record in normalization)


def test_same_file_province_root_is_supported(tmp_path, profiles):
    source, _parent, parents, areas = profiles
    write_profile(source, [*parents, *areas])
    assert prepared(source, None, tmp_path / "controls")["target_households"] == 9


def test_province_extract_retains_each_duplicate_symbol_cell(tmp_path, profiles):
    source, parent, parents, areas = profiles
    columns = [
        *FIELDS[:5],
        "C1_COUNT_TOTAL",
        "SYMBOL",
        "C2_COUNT_MEN+",
        "SYMBOL",
        "C3_COUNT_WOMEN+",
        "SYMBOL",
    ]

    def positional(row):
        return [
            *(row[name] for name in FIELDS[:5]),
            row["C1_COUNT_TOTAL"],
            "..",
            row["C2_COUNT_MEN+"],
            "x",
            row["C3_COUNT_WOMEN+"],
            "...",
        ]

    for path, rows in [(source, areas), (parent, parents)]:
        with path.open("w", encoding="latin-1", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(positional(row) for row in rows)
    output = tmp_path / "selected.csv"
    cells = select_province_profile(source, "24", output, parent)
    with output.open(encoding="latin-1", newline="") as handle:
        retained = list(csv.reader(handle))
    assert retained[0] == columns
    expected = [
        positional(row)
        for row in [*areas, *parents]
        if row["ALT_GEO_CODE"] in {"24", "24010001", "24010002"}
    ]
    assert retained[1:] == expected
    assert retained[1][6::2] == ["..", "x", "..."]
    assert observed_count(cells, "24", "5") == 9
    assert observed_count(cells, "24010001", "5") == 4
    assert observed_count(cells, "24010002", "5") == 5


def test_overwide_selected_province_rows_are_rejected(tmp_path, profiles):
    source, parent, _parents, areas = profiles
    with source.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerow([*(areas[0][name] for name in FIELDS), "unexpected"])
    with pytest.raises(ValueError, match="extra fields: geography 24010001"):
        select_province_profile(source, "24", tmp_path / "selected.csv", parent)


def test_provincial_person_root_does_not_rewrite_rounded_area_totals(
    tmp_path, profiles
):
    source, parent, parents, _areas = profiles
    for row in parents:
        if row["CHARACTERISTIC_ID"] == "56":
            row["C1_COUNT_TOTAL"] = "30"
    write_profile(parent, parents)
    plan = prepared(source, parent, tmp_path / "controls")
    assert plan["target_persons"] == 25 and plan["province_private_persons"] == 30
    assert plan["coverage"]["household_coverage_complete"]


def test_zero_household_area_does_not_create_households_or_false_shortfall(
    tmp_path, profiles
):
    source, parent, _parents, areas = profiles
    areas.extend(source_rows("24010003", "Aggregate dissemination area", 0, 0, 0))
    write_profile(source, areas)
    plan = prepared(source, parent, tmp_path / "controls")
    assert plan["target_households"] == 9
    assert plan["coverage"]["selected_geographies"] == 3
    assert plan["coverage"]["household_target_shortfall"] == 0
    assert plan["coverage"]["household_coverage_complete"]
    assert plan["excluded_geographies"] == [
        {"ada": "24010003", "reason": "zero published private households"}
    ]


def test_ada_only_profile_requires_authoritative_province_root(tmp_path, profiles):
    source, _parent, _parents, _areas = profiles
    with pytest.raises(ValueError, match="Supply --province-profile"):
        prepared(source, None, tmp_path / "controls")


def test_excluded_positive_households_are_never_reassigned(tmp_path, profiles):
    source, parent, _parents, areas = profiles
    for row in areas:
        if row["ALT_GEO_CODE"] == "24010002" and row["CHARACTERISTIC_ID"] == "51":
            row["C1_COUNT_TOTAL"] = "..."
    write_profile(source, areas)
    plan = prepared(source, parent, tmp_path / "controls", policy="exclude")
    assert plan["target_households"] == 4 and plan["province_households"] == 9
    assert plan["target_persons"] == 10 and plan["province_private_persons"] == 25
    assert plan["coverage"]["household_target_shortfall"] == 5
    assert plan["coverage"]["known_excluded_households"] == 5
    assert not plan["coverage"]["household_coverage_complete"]
    assert plan["excluded_geographies"][0]["ada"] == "24010002"
    assert "characteristic 51" in plan["excluded_geographies"][0]["reason"]


def test_unavailable_area_total_stays_unknown(tmp_path, profiles):
    source, parent, _parents, areas = profiles
    for row in areas:
        if row["ALT_GEO_CODE"] == "24010002" and row["CHARACTERISTIC_ID"] == "5":
            row["C1_COUNT_TOTAL"] = "x"
    write_profile(source, areas)
    coverage = prepared(source, parent, tmp_path / "controls", policy="exclude")[
        "coverage"
    ]
    assert coverage["observed_area_households"] is None
    assert coverage["unavailable_household_geographies"] == ["24010002"]
    assert (
        coverage["covered_households"] == 4
        and coverage["known_excluded_households"] == 0
    )


def test_missing_whole_area_is_reported_as_partial_coverage(tmp_path, profiles):
    source, parent, _parents, areas = profiles
    write_profile(source, [r for r in areas if r["ALT_GEO_CODE"] != "24010002"])
    with pytest.raises(
        ValueError, match="do not cover the published province household total"
    ):
        prepared(source, parent, tmp_path / "error")
    coverage = prepared(source, parent, tmp_path / "partial", policy="exclude")[
        "coverage"
    ]
    assert coverage["household_target_shortfall"] == 5
    assert not coverage["household_coverage_complete"]


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("CENSUS_YEAR", "2016", "not Census 2021"),
        ("GEO_LEVEL", "Country", "must identify a province"),
        ("DGUID", "2021A000235", "DGUID does not match"),
        ("C1_COUNT_TOTAL", "...", "Missing, suppressed or invalid"),
    ],
)
def test_invalid_province_roots_are_rejected(tmp_path, profiles, field, value, message):
    source, parent, parents, _areas = profiles
    for row in parents:
        if row["CHARACTERISTIC_ID"] == "5":
            row[field] = value
    write_profile(parent, parents)
    with pytest.raises(ValueError, match=message):
        prepared(source, parent, tmp_path / "controls")


def test_duplicate_parent_roots_are_rejected(tmp_path, profiles):
    source, parent, parents, areas = profiles
    write_profile(source, [*parents, *areas])
    with pytest.raises(ValueError, match="Duplicate Profile cell"):
        prepared(source, parent, tmp_path / "controls")


def test_area_totals_cannot_exceed_province_root(tmp_path, profiles):
    source, parent, parents, _areas = profiles
    for row in parents:
        if row["CHARACTERISTIC_ID"] == "5":
            row["C1_COUNT_TOTAL"] = "8"
    write_profile(parent, parents)
    with pytest.raises(ValueError, match="exceed the provincial total"):
        prepared(source, parent, tmp_path / "controls", policy="exclude")


def test_cma_default_keeps_legacy_file_bytes(tmp_path):
    parents, areas = fixture_rows("ct")
    source = tmp_path / "ct.csv"
    write_profile(source, [*parents, *areas])
    output = tmp_path / "controls"
    prepare_profile_controls(source, "462", output)
    actual = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.rglob("*")
        if p.is_file()
    }
    assert actual == LEGACY_CMA_HASHES


# Frozen pre-extension output: every legacy CMA artifact must stay byte-identical.
LEGACY_CMA_HASHES = {
    "plan.json": ("2701beb431f4e7fc116fdba92252701dd28e8b85857d479cc447ea038bf0232e"),
    "private-households/household-controls.csv": (
        "e4b5e960b0206295ae5d5f7330986a25ea11dab07eec34b8bbc3b878edbc9e35"
    ),
    "private-households/normalization.json": (
        "816485fc0fc36b4d7800d85148b3017b517be3f7ca13bbb980bf4fefeb04b29c"
    ),
    "private-households/person-controls.csv": (
        "99d44172373d3d5116a3c9fd182c38268615fe6d98482f97fea1badbb4d18428"
    ),
    "selected-profile.csv": (
        "3fe5a6e868651c466452722cd2a977ff5f815c427717485d695c2ae5556a0618"
    ),
    "zero-collective/household-controls.csv": (
        "bff12a58e5f8355b9aaef701e5750f145dddf2df96b6d3c1db7ef2758da3209e"
    ),
    "zero-collective/normalization.json": (
        "3e190cbb4587eb7a2d8769fd4ca8fd8d41ccb9b36d4ef1456586294b1c4489a8"
    ),
    "zero-collective/person-controls.csv": (
        "7ee6015789192c33f2ef9437ad7b9ab9b0a93a012c666577b0dbbfae2412202f"
    ),
}


def test_canada_preparation_selects_multiple_provinces_and_country_root(tmp_path):
    root = source_rows("01", "Country", 9, 25, 30)
    for row in root:
        row["DGUID"] = "2021A000011124"
    profile = tmp_path / "canada.csv"
    write_profile(
        profile,
        [
            *root,
            *source_rows("24010001", "Aggregate dissemination area", 4, 10, 10),
            *source_rows("35010001", "Aggregate dissemination area", 5, 15, 20),
        ],
    )
    output = tmp_path / "controls"
    summary = prepare_profile_controls(
        profile, None, output, canada=True, geo_level="ada"
    )
    assert summary["country"] == "01"
    assert "province" not in summary
    assert summary["country_households"] == summary["target_households"] == 9
    assert summary["target_persons"] == 25
    assert summary["geographies"] == ["24010001", "35010001"]
    assert summary["coverage"]["official_country_households"] == 9
    assert json.loads((output / "plan.json").read_text()) == summary
