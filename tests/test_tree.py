import csv
import json

import pytest

from synthpopcan.cli import main
from synthpopcan.tree import (
    TreeGenerationRequest,
    TreeModelSpec,
    TreeTrainingSample,
    audit_tree_model,
    generate_frequency_rows,
    generate_linked_population,
    generate_tree_rows,
    read_tree_training_sample,
    train_cart_model,
    train_frequency_model,
    validate_linked_population,
    write_tree_model,
)


def test_reads_tree_training_sample_contract(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "person_id,geo,age_group,sex,household_size,weight\n"
        "p1,QC,adult,F,2,1.5\n"
        "p2,QC,child,M,2,1.5\n"
    )

    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )

    assert sample.level == "person"
    assert sample.source_format == "csv-v1"
    assert sample.target_columns == ("age_group", "sex")
    assert sample.conditioning_columns == ("geo", "household_size")
    assert sample.geography_column == "geo"
    assert sample.weight_column == "weight"
    assert sample.columns == (
        "person_id",
        "geo",
        "age_group",
        "sex",
        "household_size",
        "weight",
    )
    assert len(sample.records) == 2
    assert sample.as_summary() == {
        "level": "person",
        "source_format": "csv-v1",
        "records": 2,
        "columns": [
            "person_id",
            "geo",
            "age_group",
            "sex",
            "household_size",
            "weight",
        ],
        "target_columns": ["age_group", "sex"],
        "conditioning_columns": ["geo", "household_size"],
        "geography_column": "geo",
        "weight_column": "weight",
    }


def test_tree_training_sample_rejects_missing_columns(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text("age_group,sex\nadult,F\n")

    with pytest.raises(ValueError, match="missing required columns: geo"):
        read_tree_training_sample(
            source,
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo",),
            geography_column="geo",
            weight_column=None,
        )


def test_tree_training_sample_rejects_overlapping_roles(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text("geo,age_group,sex\nQC,adult,F\n")

    with pytest.raises(
        ValueError,
        match="target and conditioning columns must not overlap: geo",
    ):
        read_tree_training_sample(
            source,
            level="person",
            target_columns=("geo", "age_group"),
            conditioning_columns=("geo",),
        )


def test_tree_model_spec_records_contract() -> None:
    spec = TreeModelSpec(
        level="household",
        target_columns=("TENUR",),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="WEIGHT",
        random_seed=42,
    )

    assert spec.model_family == "tree-based"
    assert spec.as_summary() == {
        "level": "household",
        "model_family": "tree-based",
        "target_columns": ["TENUR"],
        "conditioning_columns": ["geo", "household_size"],
        "geography_column": "geo",
        "weight_column": "WEIGHT",
        "random_seed": 42,
    }


def test_tree_generation_request_requires_positive_rows() -> None:
    spec = TreeModelSpec(
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo",),
    )

    with pytest.raises(ValueError, match="rows must be greater than zero"):
        TreeGenerationRequest(model_spec=spec, rows=0)


def test_trains_frequency_model_without_raw_rows(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "person_id,geo,household_size,age_group,sex,weight\n"
        "p1,QC,2,adult,F,2\n"
        "p2,QC,2,adult,F,1\n"
        "p3,ON,1,senior,M,1\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )

    model = train_frequency_model(sample, random_seed=7, min_support=2)

    payload = model.to_dict()
    assert payload["model_type"] == "conditional-frequency"
    assert payload["release_class"] == "private_working"
    assert payload["privacy"] == {
        "contains_raw_rows": False,
        "contains_source_identifiers": False,
        "minimum_support": 1.0,
        "min_support_threshold": 2,
        "groups_below_threshold": 1,
        "publishable": False,
    }
    serialized = json.dumps(payload)
    assert "person_id" not in serialized
    assert "p1" not in serialized
    assert "p2" not in serialized
    assert "p3" not in serialized
    qc_group = next(
        group for group in payload["groups"] if group["conditions"]["geo"] == "QC"
    )
    assert qc_group == {
        "conditions": {"geo": "QC", "household_size": "2"},
        "support": 3.0,
        "outcomes": [{"values": {"age_group": "adult", "sex": "F"}, "weight": 3.0}],
    }


def test_generates_frequency_rows_for_condition() -> None:
    spec = TreeModelSpec(
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        random_seed=7,
    )
    model = train_frequency_model_from_rows(
        spec,
        rows=(
            {
                "geo": "QC",
                "household_size": "2",
                "age_group": "adult",
                "sex": "F",
            },
        ),
    )

    generated = generate_frequency_rows(
        model,
        rows=2,
        conditions={"geo": "QC", "household_size": "2"},
        random_seed=11,
    )

    assert generated == [
        {
            "synthetic_id": "1",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_id": "2",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
    ]


def test_trains_cart_model_without_raw_rows(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "person_id,geo,household_size,age_group,sex,weight\n"
        "p1,QC,2,adult,F,2\n"
        "p2,QC,2,adult,F,1\n"
        "p3,QC,1,child,M,1\n"
        "p4,ON,1,senior,F,1\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )

    model = train_cart_model(
        sample,
        random_seed=7,
        min_samples_leaf=2,
        max_depth=3,
    )

    payload = model.to_dict()
    assert payload["model_type"] == "cart"
    assert payload["privacy"]["contains_raw_rows"] is False
    assert payload["privacy"]["contains_source_identifiers"] is False
    assert payload["privacy"]["min_samples_leaf"] == 2
    assert payload["privacy"]["minimum_leaf_support"] >= 2
    serialized = json.dumps(payload)
    assert "person_id" not in serialized
    assert "p1" not in serialized
    assert payload["cart"]["feature_names"]
    assert payload["cart"]["children_left"]


def test_generates_cart_rows_for_condition(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "geo,household_size,age_group,sex,weight\n"
        "QC,2,adult,F,2\n"
        "QC,2,adult,F,1\n"
        "QC,1,child,M,1\n"
        "ON,1,senior,F,1\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )
    model = train_cart_model(sample, random_seed=7, min_samples_leaf=2, max_depth=3)

    generated = generate_tree_rows(
        model,
        rows=2,
        conditions={"geo": "QC", "household_size": "2"},
        random_seed=11,
    )

    assert generated == [
        {
            "synthetic_id": "1",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_id": "2",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
    ]


def test_cli_trains_and_generates_tree_model(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-model.json"
    output_path = tmp_path / "synthetic-people.csv"
    source.write_text(
        "person_id,geo,household_size,age_group,sex,weight\n"
        "p1,QC,2,adult,F,2\n"
        "p2,QC,2,adult,F,1\n"
    )

    assert (
        main(
            [
                "tree",
                "train",
                str(source),
                "--level",
                "person",
                "--target-columns",
                "age_group,sex",
                "--conditioning-columns",
                "geo,household_size",
                "--geography-column",
                "geo",
                "--weight-column",
                "weight",
                "--out",
                str(model_path),
                "--random-seed",
                "7",
            ]
        )
        == 0
    )
    assert model_path.exists()
    model_payload = json.loads(model_path.read_text())
    assert model_payload["privacy"]["contains_raw_rows"] is False

    assert (
        main(
            [
                "tree",
                "generate",
                str(model_path),
                "--rows",
                "2",
                "--condition",
                "geo=QC",
                "--condition",
                "household_size=2",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    with output_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "synthetic_id": "1",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_id": "2",
            "geo": "QC",
            "household_size": "2",
            "age_group": "adult",
            "sex": "F",
        },
    ]


def test_cli_trains_and_generates_cart_tree_model(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-cart-model.json"
    output_path = tmp_path / "synthetic-people.csv"
    source.write_text(
        "geo,household_size,age_group,sex,weight\n"
        "QC,2,adult,F,2\n"
        "QC,2,adult,F,1\n"
        "QC,1,child,M,1\n"
        "ON,1,senior,F,1\n"
    )

    assert (
        main(
            [
                "tree",
                "train",
                str(source),
                "--method",
                "cart",
                "--level",
                "person",
                "--target-columns",
                "age_group,sex",
                "--conditioning-columns",
                "geo,household_size",
                "--geography-column",
                "geo",
                "--weight-column",
                "weight",
                "--out",
                str(model_path),
                "--random-seed",
                "7",
                "--min-samples-leaf",
                "2",
                "--max-depth",
                "3",
            ]
        )
        == 0
    )
    model_payload = json.loads(model_path.read_text())
    assert model_payload["model_type"] == "cart"

    assert (
        main(
            [
                "tree",
                "generate",
                str(model_path),
                "--rows",
                "2",
                "--condition",
                "geo=QC",
                "--condition",
                "household_size=2",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    with output_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["age_group"] == "adult"
    assert rows[0]["sex"] == "F"


def test_audits_frequency_model_support_and_purity(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "geo,household_size,age_group,sex,weight\nQC,2,adult,F,3\nON,1,senior,M,1\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )
    model = train_frequency_model(sample, random_seed=7, min_support=2)

    report = audit_tree_model(model, min_support=2, max_purity=0.95)

    assert report["passed"] is False
    assert report["model_type"] == "conditional-frequency"
    assert report["release_class"] == "private_working"
    assert report["publishable_candidate"] is False
    assert report["summary"]["groups_or_leaves"] == 2
    assert report["summary"]["minimum_support"] == 1.0
    assert report["summary"]["below_min_support"] == 1
    assert report["summary"]["above_max_purity"] == 2
    assert {issue["kind"] for issue in report["issues"]} == {
        "private_working_release_class",
        "below_min_support",
        "above_max_purity",
    }
    purity_issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "above_max_purity"
        and issue["conditions"] == {"geo": "QC", "household_size": "2"}
    )
    assert purity_issue["support"] == 3.0
    assert purity_issue["dominant_outcome"] == {
        "age_group": "adult",
        "sex": "F",
    }
    assert purity_issue["conditions"] == {"geo": "QC", "household_size": "2"}


def test_audits_cart_model_support_and_purity(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    source.write_text(
        "geo,household_size,age_group,sex,weight\n"
        "QC,2,adult,F,2\n"
        "QC,2,adult,F,1\n"
        "QC,1,child,M,1\n"
        "ON,1,senior,F,1\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo", "household_size"),
        geography_column="geo",
        weight_column="weight",
    )
    model = train_cart_model(sample, random_seed=7, min_samples_leaf=2, max_depth=3)

    report = audit_tree_model(model, min_support=2, max_purity=0.99)

    assert report["model_type"] == "cart"
    assert report["summary"]["groups_or_leaves"] >= 1
    assert report["summary"]["minimum_support"] >= 2
    assert report["summary"]["contains_raw_rows"] is False
    assert report["summary"]["contains_source_identifiers"] is False


def test_cli_audits_tree_model_as_json(tmp_path, capsys) -> None:
    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-model.json"
    source.write_text(
        "geo,household_size,age_group,sex,weight\nQC,2,adult,F,3\nON,1,senior,M,1\n"
    )

    assert (
        main(
            [
                "tree",
                "train",
                str(source),
                "--level",
                "person",
                "--target-columns",
                "age_group,sex",
                "--conditioning-columns",
                "geo,household_size",
                "--weight-column",
                "weight",
                "--out",
                str(model_path),
                "--random-seed",
                "7",
                "--min-support",
                "2",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "tree",
                "audit-model",
                str(model_path),
                "--min-support",
                "2",
                "--max-purity",
                "0.95",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is False
    assert report["summary"]["below_min_support"] == 1


def test_cli_refuses_to_package_model_with_audit_warnings(tmp_path) -> None:
    from click import ClickException

    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-model.json"
    package_path = tmp_path / "person-model-package.json"
    source.write_text(
        "geo,household_size,age_group,sex,weight\nQC,2,adult,F,3\nON,1,senior,M,1\n"
    )
    assert (
        main(
            [
                "tree",
                "train",
                str(source),
                "--level",
                "person",
                "--target-columns",
                "age_group,sex",
                "--conditioning-columns",
                "geo,household_size",
                "--weight-column",
                "weight",
                "--out",
                str(model_path),
                "--min-support",
                "2",
            ]
        )
        == 0
    )

    with pytest.raises(ClickException, match="Model audit did not pass"):
        main(
            [
                "tree",
                "package-model",
                str(model_path),
                "--out",
                str(package_path),
                "--min-support",
                "2",
                "--max-purity",
                "0.95",
            ]
        )

    assert not package_path.exists()


def test_generates_linked_households_and_persons() -> None:
    household_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
            geography_column="geo",
            random_seed=7,
        ),
        rows=(
            {
                "geo": "QC",
                "household_size": "2",
                "tenure": "owner",
            },
        ),
    )
    person_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo", "household_size", "tenure"),
            geography_column="geo",
            random_seed=11,
        ),
        rows=(
            {
                "geo": "QC",
                "household_size": "2",
                "tenure": "owner",
                "age_group": "adult",
                "sex": "F",
            },
        ),
    )

    households, persons = generate_linked_population(
        household_model,
        person_model,
        households=2,
        household_conditions={"geo": "QC"},
        random_seed=13,
    )

    assert households == [
        {
            "synthetic_household_id": "1",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
        },
        {
            "synthetic_household_id": "2",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
        },
    ]
    assert persons == [
        {
            "synthetic_person_id": "1",
            "synthetic_household_id": "1",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_person_id": "2",
            "synthetic_household_id": "1",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_person_id": "3",
            "synthetic_household_id": "2",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
            "age_group": "adult",
            "sex": "F",
        },
        {
            "synthetic_person_id": "4",
            "synthetic_household_id": "2",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
            "age_group": "adult",
            "sex": "F",
        },
    ]


def test_validates_linked_population_household_sizes() -> None:
    report = validate_linked_population(
        households=[
            {"synthetic_household_id": "1", "household_size": "2"},
            {"synthetic_household_id": "2", "household_size": "1"},
        ],
        persons=[
            {"synthetic_person_id": "1", "synthetic_household_id": "1"},
            {"synthetic_person_id": "2", "synthetic_household_id": "2"},
        ],
    )

    assert report["passed"] is False
    assert report["summary"] == {
        "households": 2,
        "persons": 2,
        "households_with_size_mismatches": 1,
        "persons_with_unknown_households": 0,
    }
    assert report["issues"] == [
        {
            "severity": "error",
            "kind": "household_size_mismatch",
            "household_id": "1",
            "expected_persons": 2,
            "actual_persons": 1,
            "message": "household 1 expected 2 persons but has 1.",
        },
    ]


def test_cli_generates_linked_households_and_persons(tmp_path) -> None:
    household_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
            geography_column="geo",
        ),
        rows=(
            {
                "geo": "QC",
                "household_size": "2",
                "tenure": "owner",
            },
        ),
    )
    person_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo", "household_size", "tenure"),
            geography_column="geo",
        ),
        rows=(
            {
                "geo": "QC",
                "household_size": "2",
                "tenure": "owner",
                "age_group": "adult",
                "sex": "F",
            },
        ),
    )
    household_model_path = tmp_path / "household-model.json"
    person_model_path = tmp_path / "person-model.json"
    households_out = tmp_path / "synthetic-households.csv"
    persons_out = tmp_path / "synthetic-persons.csv"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)

    assert (
        main(
            [
                "tree",
                "generate-linked",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--households",
                "1",
                "--condition",
                "geo=QC",
                "--households-out",
                str(households_out),
                "--persons-out",
                str(persons_out),
            ]
        )
        == 0
    )

    with households_out.open(newline="") as handle:
        household_rows = list(csv.DictReader(handle))
    with persons_out.open(newline="") as handle:
        person_rows = list(csv.DictReader(handle))
    assert household_rows == [
        {
            "synthetic_household_id": "1",
            "geo": "QC",
            "household_size": "2",
            "tenure": "owner",
        },
    ]
    assert [person["synthetic_household_id"] for person in person_rows] == ["1", "1"]
    assert [person["synthetic_person_id"] for person in person_rows] == ["1", "2"]


def test_cli_validates_linked_output(tmp_path, capsys) -> None:
    households_path = tmp_path / "synthetic-households.csv"
    persons_path = tmp_path / "synthetic-persons.csv"
    households_path.write_text("synthetic_household_id,household_size\n1,2\n2,1\n")
    persons_path.write_text(
        "synthetic_person_id,synthetic_household_id\n1,1\n2,1\n3,2\n"
    )

    assert (
        main(
            [
                "validate",
                "linked-output",
                "--households",
                str(households_path),
                "--persons",
                str(persons_path),
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
    assert report["summary"] == {
        "households": 2,
        "persons": 3,
        "households_with_size_mismatches": 0,
        "persons_with_unknown_households": 0,
    }


def train_frequency_model_from_rows(
    spec: TreeModelSpec,
    *,
    rows: tuple[dict[str, str], ...],
):
    source = TreeTrainingSample(
        level=spec.level,
        source_format="csv-v1",
        records=rows,
        columns=(*spec.conditioning_columns, *spec.target_columns),
        target_columns=spec.target_columns,
        conditioning_columns=spec.conditioning_columns,
        geography_column=spec.geography_column,
        weight_column=spec.weight_column,
    )
    return train_frequency_model(source, random_seed=spec.random_seed)
