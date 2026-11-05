"""Rare whole-household witnesses preserve source targets and the seeded pool."""

from __future__ import annotations

import builtins
import csv
import json

import numpy as np
import pytest

from synthpopcan import _candidate_preparation as preparation
from synthpopcan.controls import read_control_table
from synthpopcan.linked_schema import build_linked_population_contract
from synthpopcan.small_area_synthesis import (
    _LinkedCalibrationIndex,
    controls_by_geography,
)


def _write(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def witness_inputs(tmp_path):
    households = [
        dict(synthetic_household_id="h0", household_size="1", TENUR="0"),
        dict(synthetic_household_id="h1", household_size="2", TENUR="1"),
        dict(synthetic_household_id="h2", household_size="2", TENUR="1"),
        dict(synthetic_household_id="h3", household_size="1", TENUR="2"),
    ]
    persons = [
        dict(synthetic_person_id=f"p{i}", synthetic_household_id=hh, GENDER=gender)
        for i, (hh, gender) in enumerate(
            [
                ("h0", "1"),
                ("h1", "1"),
                ("h1", "2"),
                ("h2", "1"),
                ("h2", "1"),
                ("h3", "2"),
            ]
        )
    ]
    files = []
    for entity, field, counts in (
        ("household", "TENUR", [("0", 0), ("1", 2), ("2", 0)]),
        ("person", "GENDER", [("1", 3), ("2", 0)]),
    ):
        path = tmp_path / f"{entity}-controls.csv"
        _write(
            path,
            [
                {
                    "margin": f"ada {field}",
                    "dimensions": f"ada,{field}",
                    "ada": "24010001",
                    field: category,
                    "count": count,
                }
                for category, count in counts
            ],
        )
        files.append(path)
    return households, persons, files


def _select(inputs, **kwargs):
    households, persons, files = inputs
    return preparation.select_structural_support(
        households,
        persons,
        *files,
        pool_size=1,
        seed=42,
        geography_dimension="ada",
        **kwargs,
    )


def test_witnesses_preserve_seed_and_cover_cells_without_claiming_feasibility(
    witness_inputs, monkeypatch
):
    original_import = builtins.__import__

    def no_scipy(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            pytest.fail("Witness-only selection must not import SciPy")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_scipy)
    original_controls = [path.read_bytes() for path in witness_inputs[2]]
    seeded = set(np.random.default_rng(42).choice(4, size=1, replace=False))
    assert seeded == {0}
    first = _select(witness_inputs)
    assert _select(witness_inputs) == first
    selected, reports = first
    assert selected == seeded | {2}
    report = reports[0]
    assert report["ada"] == "24010001"
    assert report["strategy"] == "structural-witness"
    assert report["added_household_ids"] == ["h2"]
    assert report["witnesses"] == [
        {
            "household_id": "h2",
            "kind": "structural-compatible",
            "violated_zero_controls": [],
        }
    ]
    assert report["support_households"] == 1
    assert report["structural_support_complete"] is True
    assert report["unsupported_positive_controls"] == []
    assert "feasible" not in report
    assert "simultaneous linear feasibility has not been tested" in report["message"]
    assert [path.read_bytes() for path in witness_inputs[2]] == original_controls
    # Only h2 survives structural zeros; its two members imply four people
    # at the household target of two, so the person target of three is infeasible.


def test_full_source_unsupported_cell_is_reported_without_changing_target(
    witness_inputs,
):
    person_controls = witness_inputs[2][1]
    with person_controls.open("a", newline="") as handle:
        csv.writer(handle).writerow(["ada GENDER", "ada,GENDER", "24010001", "3", "7"])
    original = person_controls.read_bytes()
    selected, reports = _select(witness_inputs)
    assert selected == {0, 2}
    assert reports[0]["structural_support_complete"] is False
    assert reports[0]["unsupported_positive_controls"] == [
        {
            "unit": "person",
            "margin": "ada GENDER",
            "categories": {"GENDER": "3"},
            "target": 7.0,
        }
    ]
    assert person_controls.read_bytes() == original


def test_missing_category_retains_observed_only_donor_and_reports_zero_conflicts(
    witness_inputs,
):
    households, persons, files = witness_inputs
    persons[4]["GENDER"] = "2"
    originals = [path.read_bytes() for path in files]
    selected, reports = _select((households, persons, files))
    assert selected == {0, 1}
    report = reports[0]
    assert report["structural_support_complete"] is False
    assert report["witnesses"] == [
        {
            "household_id": "h1",
            "kind": "observed-only",
            "violated_zero_controls": [
                {
                    "unit": "person",
                    "margin": "ada GENDER",
                    "categories": {"GENDER": "2"},
                    "target": 0.0,
                }
            ],
        }
    ]
    assert report["unsupported_positive_controls"] == [
        {
            "unit": "household",
            "margin": "ada TENUR",
            "categories": {"TENUR": "1"},
            "target": 2.0,
        },
        {
            "unit": "person",
            "margin": "ada GENDER",
            "categories": {"GENDER": "1"},
            "target": 3.0,
        },
    ]
    assert "feasible" not in report
    assert [path.read_bytes() for path in files] == originals


def test_one_appended_household_can_supply_multiple_geographies(witness_inputs):
    for path in witness_inputs[2]:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        _write(path, [*rows, *[{**row, "ada": "24020001"} for row in rows]])
    selected, reports = _select(witness_inputs)
    assert selected == {0, 2}
    assert [report["ada"] for report in reports] == ["24010001", "24020001"]
    assert [report["support_households"] for report in reports] == [1, 0]
    assert all(report["structural_support_complete"] for report in reports)


def test_boolean_support_matches_count_index_for_joint_cells_and_orphans(
    witness_inputs,
):
    households, persons, files = witness_inputs
    persons = [
        {**row, "age": "young" if i % 2 else "old"} for i, row in enumerate(persons)
    ] + [dict(synthetic_household_id="orphan", GENDER="1", age="young")]
    _write(
        files[1],
        [
            {
                "margin": "ada GENDER age",
                "dimensions": "ada,GENDER,age",
                "ada": "24010001",
                "GENDER": gender,
                "age": age,
                "count": 1,
            }
            for gender in ("1", "2")
            for age in ("young", "old")
        ],
    )
    controls = [
        controls_by_geography(read_control_table(path), geography_dimension="ada")[
            "24010001"
        ]
        for path in files
    ]
    index = _LinkedCalibrationIndex.build(
        households, persons, *controls, household_id_column="synthetic_household_id"
    )
    presence = preparation._structural_presence(households, persons, index.specs)
    np.testing.assert_array_equal(presence, index.contributions > 0)
    assert presence.dtype == bool


def test_preparation_keeps_every_member_of_appended_household(
    witness_inputs, tmp_path, monkeypatch
):
    households, persons, files = witness_inputs
    source = tmp_path / "source"
    source.mkdir()
    _write(source / "households.csv", households)
    _write(source / "persons.csv", persons)
    preparation.write_json(
        source / "manifest.json",
        build_linked_population_contract(
            source / "households.csv", source / "persons.csv"
        ),
    )
    monkeypatch.setattr(
        preparation,
        "screen_candidates",
        lambda *_: (list(households[0]), list(persons[0]), households, persons, {}),
    )
    output = tmp_path / "prepared"
    result = preparation.prepare_candidates(
        source,
        output,
        pool_size=1,
        augment_support=True,
        controls_path=files[0],
        person_controls_path=files[1],
        geography_dimension="ada",
        support_strategy="witness",
    )
    assert result["selected_households"] == 2
    assert result["selected_persons"] == 3
    _, kept_households = preparation.read_records(output / "households.csv")
    _, kept_persons = preparation.read_records(output / "persons.csv")
    assert kept_households == [households[0], households[2]]
    assert kept_persons == [persons[0], persons[3], persons[4]]
    assert json.loads((output / "report.json").read_text()) == result
    assert (
        json.loads((output / "manifest.json").read_text())["candidate_preparation"]
        == result
    )


def test_support_requires_matching_geographies(witness_inputs):
    path = witness_inputs[2][1]
    path.write_text(path.read_text().replace("24010001", "24020001"))
    with pytest.raises(
        ValueError, match="matching nonempty household and person control geographies"
    ):
        _select(witness_inputs)


@pytest.mark.parametrize(
    ("strategy", "augment", "message"),
    [
        ("unknown", True, "support strategy must be 'linear' or 'witness'"),
        ("witness", False, "Witness support selection requires --augment-support"),
    ],
    ids=["unknown-strategy", "witness-requires-augmentation"],
)
def test_invalid_support_strategy_is_rejected_before_source_io(
    tmp_path, strategy, augment, message
):
    with pytest.raises(ValueError, match=message):
        preparation.prepare_candidates(
            tmp_path / "absent",
            tmp_path / "output",
            augment_support=augment,
            support_strategy=strategy,
        )
    assert not (tmp_path / "output").exists()
