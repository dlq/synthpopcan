"""Independent probability and round-trip checks for prepared tree models."""

from __future__ import annotations

import csv
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    TreeModelSpec,
    TreeTrainingSample,
    generate_linked_population,
    generate_linked_population_to_csv,
    generate_tree_rows,
    read_tree_model,
    train_cart_model,
    train_frequency_model,
    validate_linked_population,
    write_tree_model,
)


def _sample(
    records: list[dict[str, str]],
    *,
    conditioning: tuple[str, ...] = ("geo",),
) -> TreeTrainingSample:
    return TreeTrainingSample(
        level="person",
        source_format="correctness-fixture-v1",
        records=tuple(records),
        columns=tuple(records[0]),
        target_columns=("outcome",),
        conditioning_columns=conditioning,
        weight_column="weight",
    )


def test_frequency_model_matches_analytical_weighted_probabilities() -> None:
    sample = _sample(
        [
            {"geo": "QC", "outcome": "adult", "weight": "3"},
            {"geo": "QC", "outcome": "child", "weight": "1"},
            {"geo": "ON", "outcome": "adult", "weight": "1"},
            {"geo": "ON", "outcome": "child", "weight": "3"},
        ]
    )

    model = train_frequency_model(sample, random_seed=17, min_support=1)

    groups = {group.conditions["geo"]: group for group in model.groups}
    assert groups["QC"].support == 4.0
    assert {
        outcome.values["outcome"]: outcome.weight for outcome in groups["QC"].outcomes
    } == {
        "adult": 3.0,
        "child": 1.0,
    }
    assert groups["ON"].support == 4.0
    assert {
        outcome.values["outcome"]: outcome.weight for outcome in model.global_outcomes
    } == {
        "adult": 4.0,
        "child": 4.0,
    }

    counts: Counter[str] = Counter()
    seed_count = 50 if os.environ.get("SYNTHPOPCAN_CORRECTNESS_EXTENDED") else 10
    for seed in range(seed_count):
        rows = generate_tree_rows(
            model, rows=1000, conditions={"geo": "QC"}, random_seed=seed
        )
        counts.update(row["outcome"] for row in rows)
    assert counts["adult"] / counts.total() == pytest.approx(0.75, abs=0.02)

    fallback = generate_tree_rows(
        model, rows=4000, conditions={"geo": "unknown"}, random_seed=11
    )
    fallback_counts = Counter(row["outcome"] for row in fallback)
    assert fallback_counts["adult"] / len(fallback) == pytest.approx(0.5, abs=0.03)


def _manual_one_hot(
    records: list[dict[str, str]],
    conditioning: tuple[str, ...],
    categories: dict[str, tuple[str, ...]],
) -> np.ndarray:
    return np.asarray(
        [
            [
                1.0 if record[column] == category else 0.0
                for column in conditioning
                for category in categories[column]
            ]
            for record in records
        ],
        dtype=float,
    )


def _serialized_leaf(model: CartTreeModel, encoded: np.ndarray) -> int:
    node = 0
    while model.children_left[node] != model.children_right[node]:
        node = (
            model.children_left[node]
            if encoded[model.feature[node]] <= model.threshold[node]
            else model.children_right[node]
        )
    return node


def test_cart_serialization_matches_sklearn_leaves_and_probabilities() -> None:
    records = [
        {"geo": "ON", "size": "1", "outcome": "A", "weight": "1"},
        {"geo": "ON", "size": "1", "outcome": "A", "weight": "2"},
        {"geo": "ON", "size": "2", "outcome": "B", "weight": "1"},
        {"geo": "ON", "size": "2", "outcome": "B", "weight": "3"},
        {"geo": "QC", "size": "1", "outcome": "B", "weight": "1"},
        {"geo": "QC", "size": "1", "outcome": "B", "weight": "2"},
        {"geo": "QC", "size": "2", "outcome": "A", "weight": "1"},
        {"geo": "QC", "size": "2", "outcome": "A", "weight": "3"},
    ]
    conditioning = ("geo", "size")
    sample = _sample(records, conditioning=conditioning)
    model = train_cart_model(sample, random_seed=17, min_samples_leaf=1, max_depth=3)

    categories = {
        column: tuple(sorted({record[column] for record in records}))
        for column in conditioning
    }
    x = _manual_one_hot(records, conditioning, categories)
    class_names = tuple(sorted({record["outcome"] for record in records}))
    class_ids = {name: index for index, name in enumerate(class_names)}
    y = np.asarray([class_ids[record["outcome"]] for record in records])
    weights = np.asarray([float(record["weight"]) for record in records])
    classifier = DecisionTreeClassifier(
        random_state=17, min_samples_leaf=1, max_depth=3
    ).fit(x, y, sample_weight=weights)

    grid = [
        {"geo": geo, "size": size}
        for geo in ("ON", "QC", "unknown")
        for size in ("1", "2", "unknown")
    ]
    grid_x = _manual_one_hot(grid, conditioning, categories)
    expected_leaves = classifier.apply(grid_x)
    expected_probabilities = classifier.predict_proba(grid_x)

    for encoded, expected_leaf, expected_probability in zip(
        grid_x, expected_leaves, expected_probabilities, strict=True
    ):
        leaf = _serialized_leaf(model, encoded)
        serialized_values = np.asarray(model.value[leaf])
        serialized_probability = serialized_values / serialized_values.sum()
        assert leaf == expected_leaf
        assert serialized_probability == pytest.approx(expected_probability)


@pytest.mark.parametrize("family", ["frequency", "cart"])
def test_tree_model_round_trip_preserves_fixed_seed_semantics(
    tmp_path: Path, family: str
) -> None:
    sample = _sample(
        [
            {"geo": "QC", "outcome": "adult", "weight": "3"},
            {"geo": "QC", "outcome": "child", "weight": "1"},
            {"geo": "ON", "outcome": "adult", "weight": "1"},
            {"geo": "ON", "outcome": "child", "weight": "3"},
        ]
    )
    model: FrequencyTreeModel | CartTreeModel
    if family == "frequency":
        model = train_frequency_model(sample, random_seed=13, min_support=1)
    else:
        model = train_cart_model(
            sample, random_seed=13, min_samples_leaf=1, max_depth=2
        )
    path = tmp_path / f"{family}.json"
    write_tree_model(path, model)

    restored = read_tree_model(path)

    assert restored.to_dict() == model.to_dict()
    assert generate_tree_rows(
        restored, rows=200, conditions={"geo": "QC"}, random_seed=29
    ) == generate_tree_rows(model, rows=200, conditions={"geo": "QC"}, random_seed=29)


@pytest.mark.parametrize("invalid", ["nan", "inf", "-inf", "-1"])
def test_model_training_rejects_invalid_frequency_weights(invalid: str) -> None:
    sample = _sample([{"geo": "QC", "outcome": "adult", "weight": invalid}])

    with pytest.raises(ValueError, match="weight"):
        train_frequency_model(sample)


def _train_linked_models(
    family: str,
) -> tuple[FrequencyTreeModel | CartTreeModel, FrequencyTreeModel | CartTreeModel]:
    household_records = [
        {
            "source_household_id": "raw-h1",
            "geo": "QC",
            "household_size": "1",
            "tenure": "owner",
            "weight": "1",
        },
        {
            "source_household_id": "raw-h2",
            "geo": "QC",
            "household_size": "2",
            "tenure": "renter",
            "weight": "2",
        },
        {
            "source_household_id": "raw-h3",
            "geo": "QC",
            "household_size": "3",
            "tenure": "owner",
            "weight": "1",
        },
    ]
    person_records = [
        {
            "source_person_id": "raw-p1",
            "geo": "QC",
            "household_size": size,
            "tenure": tenure,
            "age": age,
            "weight": "1",
        }
        for size, tenure, age in (
            ("1", "owner", "adult"),
            ("2", "renter", "adult"),
            ("3", "owner", "child"),
        )
    ]
    household_sample = TreeTrainingSample(
        level="household",
        source_format="correctness-fixture-v1",
        records=tuple(household_records),
        columns=tuple(household_records[0]),
        target_columns=("household_size", "tenure"),
        conditioning_columns=("geo",),
        weight_column="weight",
    )
    person_sample = TreeTrainingSample(
        level="person",
        source_format="correctness-fixture-v1",
        records=tuple(person_records),
        columns=tuple(person_records[0]),
        target_columns=("age",),
        conditioning_columns=("geo", "household_size", "tenure"),
        weight_column="weight",
    )
    if family == "frequency":
        return (
            train_frequency_model(household_sample, random_seed=7, min_support=1),
            train_frequency_model(person_sample, random_seed=11, min_support=1),
        )
    return (
        train_cart_model(
            household_sample, random_seed=7, min_samples_leaf=1, max_depth=3
        ),
        train_cart_model(
            person_sample, random_seed=11, min_samples_leaf=1, max_depth=4
        ),
    )


@pytest.mark.parametrize("family", ["frequency", "cart"])
def test_linked_generation_invariants_and_csv_equivalence(
    tmp_path: Path, family: str
) -> None:
    household_model, person_model = _train_linked_models(family)
    households, persons = generate_linked_population(
        household_model,
        person_model,
        households=60,
        household_conditions={"geo": "QC"},
        random_seed=23,
    )
    repeated = generate_linked_population(
        household_model,
        person_model,
        households=60,
        household_conditions={"geo": "QC"},
        random_seed=23,
    )
    assert repeated == (households, persons)

    household_ids = [row["synthetic_household_id"] for row in households]
    person_ids = [row["synthetic_person_id"] for row in persons]
    assert len(household_ids) == len(set(household_ids)) == 60
    assert len(person_ids) == len(set(person_ids))
    people_by_household = Counter(row["synthetic_household_id"] for row in persons)
    households_by_id = {row["synthetic_household_id"]: row for row in households}
    for household_id, household in households_by_id.items():
        assert people_by_household[household_id] == int(household["household_size"])
    for person in persons:
        household = households_by_id[person["synthetic_household_id"]]
        for inherited in ("geo", "household_size", "tenure"):
            assert person[inherited] == household[inherited]
    assert not any(
        column.startswith("source_")
        for row in (*households, *persons)
        for column in row
    )
    assert validate_linked_population(households, persons)["passed"] is True

    households_path = tmp_path / f"{family}-households.csv"
    persons_path = tmp_path / f"{family}-persons.csv"
    generated_counts = generate_linked_population_to_csv(
        household_model,
        person_model,
        households=60,
        household_conditions={"geo": "QC"},
        households_path=households_path,
        persons_path=persons_path,
        random_seed=23,
    )
    with households_path.open(newline="") as handle:
        csv_households = list(csv.DictReader(handle))
    with persons_path.open(newline="") as handle:
        csv_persons = list(csv.DictReader(handle))
    assert generated_counts == (len(households), len(persons))
    assert csv_households == households
    assert csv_persons == persons


def test_linked_validation_rejects_duplicate_and_missing_identifiers() -> None:
    report = validate_linked_population(
        households=[
            {"synthetic_household_id": "h1", "household_size": "1"},
            {"synthetic_household_id": "h1", "household_size": "1"},
            {"synthetic_household_id": "", "household_size": "1"},
        ],
        persons=[
            {"synthetic_person_id": "p1", "synthetic_household_id": "h1"},
            {"synthetic_person_id": "p1", "synthetic_household_id": "h1"},
            {"synthetic_person_id": "", "synthetic_household_id": "missing"},
        ],
    )

    assert report["passed"] is False
    assert {
        "missing_household_identifier",
        "duplicate_household_identifier",
        "missing_person_identifier",
        "duplicate_person_identifier",
        "unknown_person_household",
    }.issubset({issue["kind"] for issue in report["issues"]})


def test_generated_identifier_columns_are_reserved() -> None:
    with pytest.raises(ValueError, match="reserved generated identifiers"):
        TreeModelSpec(
            level="person",
            target_columns=("synthetic_person_id",),
            conditioning_columns=("geo",),
        )
