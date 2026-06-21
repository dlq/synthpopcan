import pytest

from synthpopcan.tree import (
    TreeGenerationRequest,
    TreeModelSpec,
    read_tree_training_sample,
)


def test_reads_tree_training_sample_contract(tmp_path) -> None:
    source = tmp_path / "people.csv"
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
    source = tmp_path / "people.csv"
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
    source = tmp_path / "people.csv"
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
