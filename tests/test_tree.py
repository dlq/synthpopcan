import csv
import json

import pytest

from synthpopcan.cli import main
from synthpopcan.tree import (
    TreeGenerationRequest,
    TreeModelSpec,
    TreeTrainingSample,
    generate_frequency_rows,
    read_tree_training_sample,
    train_frequency_model,
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
