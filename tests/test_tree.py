import csv
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from synthpopcan.cli import main
from synthpopcan.cli_tree import (
    apply_target_profile,
    classify_linked_release_readiness,
    filter_training_sample_by_geography,
    format_audit_summary,
    format_bytes_or_blank,
    format_geography_filter,
    format_int_or_blank,
    format_model_summary,
    format_number_or_blank,
    format_privacy_summary,
    format_source_label,
    geography_filter_manifest,
    linked_release_next_steps,
    package_models,
    parse_column_list,
    read_linked_model_package,
    read_linked_training_manifest,
    read_model_release_manifest,
    read_source_provenance,
    release_blocking_issues,
    release_manifest_matches_model_paths,
    train_tree_sample,
    tree_model_from_payload,
    validate_linked_model_package_inputs,
    validate_package_allows_generation,
)
from synthpopcan.tree import (
    CartTreeModel,
    FrequencyTreeModel,
    TreeGenerationRequest,
    TreeModelSpec,
    TreeTrainingSample,
    audit_tree_model,
    choose_group,
    dominant_cart_outcome,
    dominant_frequency_outcome,
    encode_conditions,
    generate_frequency_rows,
    generate_linked_population,
    generate_tree_rows,
    outcome_purity,
    parse_conditions,
    read_cart_model,
    read_frequency_model,
    read_record_weight,
    read_tree_model,
    read_tree_training_sample,
    train_cart_model,
    train_frequency_model,
    validate_condition_columns,
    validate_linked_population,
    validate_tree_roles,
    weighted_choice,
    write_frequency_model,
    write_generated_rows,
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


def test_tree_model_deserializers_reject_bad_payloads(tmp_path) -> None:
    freq_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "age_group": "adult"},),
    )
    cart_source = tmp_path / "cart-training.csv"
    cart_source.write_text(
        "geo,age_group,weight\n"
        "QC,adult,1\n"
        "ON,child,1\n"
    )
    cart_sample = read_tree_training_sample(
        cart_source,
        level="person",
        target_columns=("age_group",),
        conditioning_columns=("geo",),
        weight_column="weight",
    )
    cart_model = train_cart_model(cart_sample, min_samples_leaf=1)

    with pytest.raises(ValueError, match="unsupported tree model schema"):
        FrequencyTreeModel.from_dict({"schema_version": "old"})
    with pytest.raises(ValueError, match="unsupported tree model type"):
        FrequencyTreeModel.from_dict(
            {**freq_model.to_dict(), "model_type": "cart"}
        )
    with pytest.raises(ValueError, match="tree model spec must be an object"):
        FrequencyTreeModel.from_dict({**freq_model.to_dict(), "spec": "bad"})
    with pytest.raises(ValueError, match="unsupported tree model schema"):
        CartTreeModel.from_dict({"schema_version": "old"})
    with pytest.raises(ValueError, match="unsupported tree model type"):
        CartTreeModel.from_dict(
            {**cart_model.to_dict(), "model_type": "conditional-frequency"}
        )
    with pytest.raises(ValueError, match="tree model spec must be an object"):
        CartTreeModel.from_dict({**cart_model.to_dict(), "spec": "bad"})
    with pytest.raises(ValueError, match="cart model payload must be an object"):
        CartTreeModel.from_dict({**cart_model.to_dict(), "cart": "bad"})
    with pytest.raises(ValueError, match="privacy payload must be an object"):
        CartTreeModel.from_dict({**cart_model.to_dict(), "privacy": "bad"})
    with pytest.raises(ValueError, match="feature categories must be an object"):
        CartTreeModel.from_dict({**cart_model.to_dict(), "feature_categories": "bad"})


def test_tree_model_readers_validate_json_and_model_family(tmp_path) -> None:
    freq_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "age_group": "adult"},),
    )
    freq_path = tmp_path / "frequency.json"
    cart_path = tmp_path / "cart.json"
    invalid_json_path = tmp_path / "invalid.json"
    unsupported_path = tmp_path / "unsupported.json"
    cart_source = tmp_path / "cart-training.csv"
    cart_source.write_text(
        "geo,age_group,weight\n"
        "QC,adult,1\n"
        "ON,child,1\n"
    )
    cart_sample = read_tree_training_sample(
        cart_source,
        level="person",
        target_columns=("age_group",),
        conditioning_columns=("geo",),
        weight_column="weight",
    )
    cart_model = train_cart_model(cart_sample, min_samples_leaf=1)
    write_tree_model(freq_path, freq_model)
    write_frequency_model(tmp_path / "frequency-writer.json", freq_model)
    write_tree_model(cart_path, cart_model)
    invalid_json_path.write_text("{")
    unsupported_path.write_text(json.dumps({"model_type": "other"}))

    assert isinstance(read_tree_model(freq_path), FrequencyTreeModel)
    assert isinstance(read_tree_model(cart_path), CartTreeModel)
    assert isinstance(read_frequency_model(freq_path), FrequencyTreeModel)
    assert isinstance(read_cart_model(cart_path), CartTreeModel)
    with pytest.raises(ValueError, match="not valid JSON"):
        read_tree_model(invalid_json_path)
    with pytest.raises(ValueError, match="unsupported tree model type"):
        read_tree_model(unsupported_path)
    with pytest.raises(ValueError, match="not a conditional-frequency"):
        read_frequency_model(cart_path)
    with pytest.raises(ValueError, match="not a CART"):
        read_cart_model(freq_path)


def test_tree_generation_and_sampling_helper_edges(tmp_path) -> None:
    model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "age_group": "adult"},),
    )
    rng = random.Random(7)

    with pytest.raises(ValueError, match="rows must be greater than zero"):
        generate_tree_rows(model, rows=0)
    with pytest.raises(ValueError, match="unknown conditioning columns"):
        generate_frequency_rows(model, rows=1, conditions={"bad": "value"})
    fallback = generate_frequency_rows(model, rows=1, conditions={"geo": "ON"})
    assert fallback == [
        {"synthetic_id": "1", "geo": "ON", "age_group": "adult"}
    ]
    assert parse_conditions(("geo=QC", "household_size=2")) == {
        "geo": "QC",
        "household_size": "2",
    }
    with pytest.raises(ValueError, match="must use COLUMN=VALUE"):
        parse_conditions(("bad",))
    with pytest.raises(ValueError, match="must include a column name"):
        parse_conditions(("=QC",))
    assert encode_conditions(
        {"geo": "QC"},
        ("geo",),
        {"geo": ("ON", "QC")},
    ) == [0.0, 1.0]
    assert choose_group(model, {}, rng).conditions == {"geo": "QC"}
    assert outcome_purity(()) == 0.0
    with pytest.raises(ValueError, match="non-positive weights"):
        weighted_choice(["x"], [0.0], rng)
    with pytest.raises(ValueError, match="cannot write empty generated output"):
        write_generated_rows(tmp_path / "empty.csv", [])


def test_cli_tree_parser_and_formatter_helpers_cover_edges() -> None:
    assert parse_column_list(" age , sex ", "target columns") == ("age", "sex")
    with pytest.raises(ValueError, match="at least one target columns"):
        parse_column_list(" , ", "target columns")

    assert release_blocking_issues(
        {
            "issues": [
                {"kind": "private_working_release_class"},
                {"kind": "below_min_support"},
                "ignored",
            ]
        }
    ) == [{"kind": "below_min_support"}]
    with pytest.raises(ValueError, match="issues must be a list"):
        release_blocking_issues({"issues": "bad"})

    assert format_source_label({"provider": "StatCan", "title": "Census"}) == (
        "StatCan: Census"
    )
    assert format_source_label({"title": "Census"}) == "Census"
    assert format_geography_filter({"column": "PR", "value": "24"}) == "PR=24"
    assert format_geography_filter("bad") == ""
    assert format_geography_filter({"column": "PR"}) == ""
    assert format_privacy_summary(
        {
            "publishable_candidate": True,
            "contains_raw_rows": False,
            "contains_source_identifiers": False,
        }
    ) == "publishable_candidate; raw_rows=False; source_ids=False"
    assert format_model_summary(
        {
            "release_class": "publishable_candidate",
            "records_trained": 1200,
            "bytes": 2048,
            "target_columns": ["age", "sex"],
        }
    ) == "publishable_candidate; 1,200 records; 2.0 KiB; 2 targets"
    assert format_model_summary("bad") == ";  records; ; 0 targets"
    assert format_audit_summary(
        {
            "passed": True,
            "issue_count": 0,
            "minimum_support": 12.5,
            "above_max_purity": 1,
        }
    ) == "passed=True; issues=0; min_support=12.5; high_purity=1"
    assert format_bytes_or_blank("bad") == ""
    assert format_bytes_or_blank(1_048_576) == "1.0 MiB"
    assert format_int_or_blank("bad") == ""
    assert format_int_or_blank(12.8) == "12"
    assert format_number_or_blank("bad") == ""
    assert format_number_or_blank(12.3456789) == "12.3457"


def test_cli_tree_manifest_and_package_helpers_cover_edges(tmp_path) -> None:
    valid_training_manifest = tmp_path / "training.json"
    valid_training_manifest.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-linked-tree-training-v1",
                "source": {"path": "source.csv"},
                "column_source": {"mode": "profile"},
                "geography_filter": {"column": "PR", "value": "24"},
                "target_profile": "minimal",
                "models": {
                    "household": {"path": str(tmp_path / "household.json")},
                    "person": {"path": str(tmp_path / "person.json")},
                },
            }
        )
    )
    assert read_linked_training_manifest(None) is None
    assert read_linked_training_manifest(valid_training_manifest)["target_profile"] == (
        "minimal"
    )
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{")
    with pytest.raises(ValueError, match="not valid JSON"):
        read_linked_training_manifest(invalid_json)
    array_json = tmp_path / "array.json"
    array_json.write_text("[]")
    with pytest.raises(ValueError, match="must be a JSON object"):
        read_linked_training_manifest(array_json)
    wrong_schema = tmp_path / "wrong-schema.json"
    wrong_schema.write_text(json.dumps({"schema_version": "old"}))
    with pytest.raises(ValueError, match="unsupported linked tree training"):
        read_linked_training_manifest(wrong_schema)

    release_manifest = tmp_path / "release.json"
    release_manifest.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-tree-release-manifest-v1",
                "source_model": "source.json",
                "output_model": "output.json",
            }
        )
    )
    assert read_model_release_manifest(None) is None
    assert read_model_release_manifest(release_manifest)["source_model"] == (
        "source.json"
    )
    with pytest.raises(ValueError, match="model release manifest"):
        read_model_release_manifest(array_json)
    with pytest.raises(ValueError, match="unsupported tree release"):
        read_model_release_manifest(wrong_schema)

    provenance = tmp_path / "source-provenance.json"
    provenance.write_text(
        json.dumps(
                {
                    "schema_version": "synthpopcan-source-provenance-v1",
                    "title": "2016 Census",
                    "provider": "Statistics Canada",
                    "access_class": "restricted",
                    "citation": "Synthetic fixture citation.",
                    "redistribution_note": "Synthetic fixture only.",
                }
            )
        )
    assert read_source_provenance(provenance)["title"] == "2016 Census"
    with pytest.raises(ValueError, match="source provenance"):
        read_source_provenance(array_json)
    with pytest.raises(ValueError, match="unsupported source provenance"):
        read_source_provenance(wrong_schema)
    missing_required = tmp_path / "missing-source-field.json"
    missing_required.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "2016 Census",
                "provider": "Statistics Canada",
            }
        )
    )
    with pytest.raises(ValueError, match="access_class"):
        read_source_provenance(missing_required)

    package = tmp_path / "package.json"
    package.write_text(
        json.dumps({"schema_version": "synthpopcan-linked-tree-package-v1"})
    )
    assert read_linked_model_package(package)["schema_version"].endswith("package-v1")
    with pytest.raises(ValueError, match="linked model package"):
        read_linked_model_package(array_json)
    with pytest.raises(ValueError, match="unsupported linked model package"):
        read_linked_model_package(wrong_schema)

    assert release_manifest_matches_model_paths(
        {
            "source_model": "source.json",
            "output_model": "output.json",
        },
        source_model_path=Path("source.json"),
        output_model_path=Path("output.json"),
    )
    assert not release_manifest_matches_model_paths(
        None,
        source_model_path=Path("source.json"),
        output_model_path=Path("output.json"),
    )
    assert not release_manifest_matches_model_paths(
        {"source_model": 1, "output_model": "output.json"},
        source_model_path=Path("source.json"),
        output_model_path=Path("output.json"),
    )


def test_cli_tree_generation_package_and_geography_helpers_cover_edges(
    tmp_path,
) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    household_model = read_tree_model(household_model_path)
    person_model = read_tree_model(person_model_path)
    package = {
        "privacy": {"publishable_candidate": True},
        "models": {
            "household": household_model.to_dict(),
            "person": person_model.to_dict(),
        },
    }

    validate_package_allows_generation(package)
    with pytest.raises(ValueError, match="publishable candidate"):
        validate_package_allows_generation(
            {"privacy": {"publishable_candidate": False}}
        )
    assert package_models(package) == (household_model, person_model)
    with pytest.raises(ValueError, match="household and person models"):
        package_models({"models": {"household": household_model.to_dict()}})
    with pytest.raises(ValueError, match="unsupported tree model type"):
        tree_model_from_payload({"model_type": "other"})

    sample_path = tmp_path / "household-training.csv"
    sample_path.write_text("geo,household_size\nQC,2\nON,1\n")
    sample = read_tree_training_sample(
        sample_path,
        level="household",
        target_columns=("household_size",),
        conditioning_columns=("geo",),
    )
    assert filter_training_sample_by_geography(
        sample,
        geography_column=None,
        geography_value=None,
    ) == sample
    filtered = filter_training_sample_by_geography(
        sample,
        geography_column="geo",
        geography_value="QC",
    )
    assert filtered.metadata["geography_filter"] == {"column": "geo", "value": "QC"}
    with pytest.raises(ValueError, match="provided together"):
        filter_training_sample_by_geography(
            sample,
            geography_column="geo",
            geography_value=None,
        )
    with pytest.raises(ValueError, match="missing required columns"):
        filter_training_sample_by_geography(
            sample,
            geography_column="missing",
            geography_value="QC",
        )
    with pytest.raises(ValueError, match="no records matched"):
        filter_training_sample_by_geography(
            sample,
            geography_column="geo",
            geography_value="BC",
        )

    assert apply_target_profile(
        household_target_columns=("household_size", "TENUR", "VALUE"),
        person_target_columns=("AGEGRP", "SEX", "TOTINC"),
        target_profile="full",
    ) == (("household_size", "TENUR", "VALUE"), ("AGEGRP", "SEX", "TOTINC"))
    assert apply_target_profile(
        household_target_columns=("household_size", "TENUR", "VALUE"),
        person_target_columns=("AGEGRP", "SEX", "TOTINC"),
        target_profile="reduced",
    ) == (("household_size", "TENUR"), ("AGEGRP", "SEX"))
    assert apply_target_profile(
        household_target_columns=("household_size", "TENUR", "VALUE"),
        person_target_columns=("AGEGRP", "SEX", "TOTINC"),
        target_profile="minimal",
    ) == (("household_size", "TENUR"), ("AGEGRP", "SEX"))
    assert geography_filter_manifest(None, None) is None
    assert geography_filter_manifest("PR", "24") == {"column": "PR", "value": "24"}
    with pytest.raises(ValueError, match="provided together"):
        geography_filter_manifest("PR", None)

    validate_linked_model_package_inputs(
        household_model,
        person_model,
        household_size_column="household_size",
    )
    with pytest.raises(ValueError, match="household model must have level"):
        validate_linked_model_package_inputs(
            person_model,
            person_model,
            household_size_column="household_size",
        )
    with pytest.raises(ValueError, match="person model must have level"):
        validate_linked_model_package_inputs(
            household_model,
            household_model,
            household_size_column="household_size",
        )

    cart_model = train_tree_sample(
        sample,
        method="cart",
        random_seed=1,
        min_support=1,
        min_samples_leaf=1,
        max_depth=None,
    )
    assert cart_model.model_type == "cart"


def test_cli_tree_release_readiness_helpers_cover_edges() -> None:
    clean_private = {
        "issues": [{"kind": "private_working_release_class"}],
        "publishable_candidate": False,
    }
    clean_publishable = {"issues": [], "publishable_candidate": True}
    blocked = {
        "issues": [{"kind": "below_min_support"}],
        "publishable_candidate": False,
    }

    assert (
        classify_linked_release_readiness(
            household_audit=blocked,
            person_audit=clean_publishable,
        )
        == "needs_changes"
    )
    assert (
        classify_linked_release_readiness(
            household_audit=clean_publishable,
            person_audit=clean_publishable,
        )
        == "likely_publishable"
    )
    assert (
        classify_linked_release_readiness(
            household_audit=clean_private,
            person_audit=clean_publishable,
        )
        == "private_working"
    )
    assert linked_release_next_steps("likely_publishable") == [
        "Package the reviewed models with `tree package-linked-models`."
    ]
    assert linked_release_next_steps("needs_changes")[0].startswith(
        "Review audit issues"
    )
    assert linked_release_next_steps("private_working")[0].startswith(
        "Prepare reviewed"
    )


def test_tree_low_level_validation_and_cart_edges(tmp_path) -> None:
    cart_source = tmp_path / "cart-training.csv"
    cart_source.write_text(
        "geo,age_group,weight\n"
        "QC,adult,1\n"
        "ON,child,1\n"
    )
    cart_sample = read_tree_training_sample(
        cart_source,
        level="person",
        target_columns=("age_group",),
        conditioning_columns=("geo",),
        weight_column="weight",
    )
    cart_model = train_cart_model(cart_sample, min_samples_leaf=1)
    zero_probability_cart = replace(
        cart_model,
        value=tuple(
            tuple(0.0 for _class in cart_model.target_classes)
            for _node in cart_model.value
        ),
    )

    with pytest.raises(ValueError, match="rows must be greater than zero"):
        generate_tree_rows(cart_model, rows=0)
    with pytest.raises(ValueError, match="no positive target probabilities"):
        generate_tree_rows(zero_probability_cart, rows=1, conditions={"geo": "QC"})
    with pytest.raises(ValueError, match="at least one target column"):
        validate_tree_roles(target_columns=(), conditioning_columns=("geo",))
    with pytest.raises(ValueError, match="at least one conditioning column"):
        validate_tree_roles(target_columns=("age_group",), conditioning_columns=())
    with pytest.raises(ValueError, match="unknown conditioning columns"):
        validate_condition_columns(("geo",), {"bad": "value"})
    with pytest.raises(ValueError, match="invalid weight"):
        read_record_weight({"weight": "bad"}, "weight", 2)
    assert dominant_frequency_outcome(()) is None
    assert dominant_cart_outcome(replace(cart_model, value=((),)), 0) is None

    class HighUniform:
        def uniform(self, _start: float, total: float) -> float:
            return total + 1

    assert weighted_choice(["fallback"], [1.0], HighUniform()) == "fallback"


def test_cli_trains_and_generates_tree_model(tmp_path) -> None:
    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-model.json"
    output_path = tmp_path / "synthetic-people.csv"
    manifest_path = tmp_path / "synthetic-people.manifest.json"
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
                "--manifest-out",
                str(manifest_path),
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
    manifest = json.loads(manifest_path.read_text())
    assert manifest == {
        "schema_version": "synthpopcan-tree-generation-manifest-v1",
        "command": "tree generate",
        "outputs": {"rows": str(output_path)},
        "rows": 2,
        "conditions": {"geo": "QC", "household_size": "2"},
        "random_seed": None,
        "effective_random_seed": 7,
        "model": {
            "path": str(model_path),
            "model_type": "conditional-frequency",
            "release_class": "private_working",
            "level": "person",
            "records_trained": 2,
            "source_format": "csv-v1",
            "target_columns": ["age_group", "sex"],
            "conditioning_columns": ["geo", "household_size"],
        },
    }


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


def test_audit_tree_model_rejects_invalid_thresholds() -> None:
    model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "age_group": "adult"},),
    )

    with pytest.raises(ValueError, match="min_support"):
        audit_tree_model(model, min_support=0)
    with pytest.raises(ValueError, match="max_purity"):
        audit_tree_model(model, max_purity=0)
    with pytest.raises(ValueError, match="max_purity"):
        audit_tree_model(model, max_purity=1.1)
    with pytest.raises(ValueError, match="min_samples_leaf"):
        train_cart_model(
            TreeTrainingSample(
                level="person",
                source_format="test",
                records=(),
                columns=("geo", "age_group"),
                target_columns=("age_group",),
                conditioning_columns=("geo",),
                geography_column=None,
                weight_column=None,
            ),
            min_samples_leaf=0,
        )


def test_audit_tree_model_flags_privacy_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "age_group": "adult"},),
    )
    original_to_dict = FrequencyTreeModel.to_dict

    def to_dict_with_sensitive_metadata(
        self: FrequencyTreeModel,
    ) -> dict[str, object]:
        payload = original_to_dict(self)
        payload["privacy"] = {
            **payload["privacy"],  # type: ignore[arg-type]
            "contains_raw_rows": True,
            "contains_source_identifiers": True,
        }
        return payload

    monkeypatch.setattr(FrequencyTreeModel, "to_dict", to_dict_with_sensitive_metadata)

    report = audit_tree_model(model, min_support=1)

    assert {"contains_raw_rows", "contains_source_identifiers"}.issubset(
        {issue["kind"] for issue in report["issues"]}
    )
    assert report["summary"]["contains_raw_rows"] is True
    assert report["summary"]["contains_source_identifiers"] is True


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


def test_cli_packages_model_after_clean_audit(tmp_path, capsys) -> None:
    source = tmp_path / "derived-person-training.csv"
    model_path = tmp_path / "person-model.json"
    package_path = tmp_path / "person-model-package.json"
    source.write_text(
        "geo,age_group,sex\n"
        "QC,adult,F\n"
        "QC,adult,F\n"
    )
    sample = read_tree_training_sample(
        source,
        level="person",
        target_columns=("age_group", "sex"),
        conditioning_columns=("geo",),
    )
    model = replace(
        train_frequency_model(sample, min_support=1),
        release_class="publishable_candidate",
    )
    write_tree_model(model_path, model)

    assert (
        main(
            [
                "tree",
                "package-model",
                str(model_path),
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )

    assert json.loads(package_path.read_text())["schema_version"] == (
        "synthpopcan-tree-package-v1"
    )


def test_cli_tree_commands_wrap_bad_model_json(tmp_path) -> None:
    from click import ClickException

    bad_model = tmp_path / "bad-model.json"
    bad_model.write_text("{")

    with pytest.raises(ClickException, match="not valid JSON"):
        main(["tree", "audit-model", str(bad_model)])
    with pytest.raises(ClickException, match="not valid JSON"):
        main(
            [
                "tree",
                "package-model",
                str(bad_model),
                "--out",
                str(tmp_path / "package.json"),
            ]
        )
    with pytest.raises(ClickException, match="not valid JSON"):
        main(
            [
                "tree",
                "prepare-model-release",
                str(bad_model),
                "--out",
                str(tmp_path / "candidate.json"),
            ]
        )


def _write_publishable_linked_model_fixtures(tmp_path):
    household_model = replace(
        train_frequency_model_from_rows(
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
        ),
        release_class="publishable_candidate",
    )
    person_model = replace(
        train_frequency_model_from_rows(
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
        ),
        release_class="publishable_candidate",
    )
    household_model_path = tmp_path / "household-model.json"
    person_model_path = tmp_path / "person-model.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    return household_model_path, person_model_path


def _write_linked_training_manifest(
    path,
    *,
    household_model_path=None,
    person_model_path=None,
) -> None:
    payload = {
        "schema_version": "synthpopcan-linked-tree-training-v1",
        "source": {
            "path": "data/private/census/hierarchical.csv",
            "source_format": "statcan-2016-hierarchical",
            "records": 100,
            "households": 40,
        },
        "target_profile": "minimal",
        "geography_filter": {"column": "PR", "value": "24"},
        "method": "conditional-frequency",
        "random_seed": 7,
        "training": {
            "household": {"records": 40},
            "person": {"records": 100},
        },
    }
    if household_model_path is not None or person_model_path is not None:
        payload["models"] = {}
        if household_model_path is not None:
            payload["models"]["household"] = {"path": str(household_model_path)}
        if person_model_path is not None:
            payload["models"]["person"] = {"path": str(person_model_path)}
    path.write_text(json.dumps(payload) + "\n")


def _write_model_release_manifest(
    path, *, source_model_path, output_model_path
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-tree-release-manifest-v1",
                "command": "tree prepare-model-release",
                "source_model": str(source_model_path),
                "output_model": str(output_model_path),
                "release_class": "publishable_candidate",
                "review_note": "reviewed fixture model",
            }
        )
        + "\n"
    )


def _write_source_provenance(path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "2016 Census Public Use Microdata File, hierarchical",
                "provider": "Statistics Canada",
                "access_class": "restricted",
                "citation": "Statistics Canada. 2016 Census PUMF, hierarchical.",
                "redistribution_note": "Do not redistribute source microdata.",
                "url": "https://www.statcan.gc.ca/",
            }
        )
        + "\n"
    )


def test_cli_packages_publishable_linked_models(tmp_path) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)

    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )

    package = json.loads(package_path.read_text())
    assert package["schema_version"] == "synthpopcan-linked-tree-package-v1"
    assert package["package_type"] == "linked_household_person"
    assert package["household_size_column"] == "household_size"
    assert package["review_note"] == "reviewed fixture package"
    assert package["thresholds"] == {"min_support": 1.0, "max_purity": 1.0}
    assert package["training_manifest"]["path"] == str(training_manifest_path)
    assert package["training_manifest"]["target_profile"] == "minimal"
    assert package["training_manifest"]["geography_filter"] == {
        "column": "PR",
        "value": "24",
    }
    assert package["source_provenance"]["path"] == str(source_provenance_path)
    assert package["source_provenance"]["provider"] == "Statistics Canada"
    assert package["source_provenance"]["access_class"] == "restricted"
    assert package["model_summaries"]["household"]["bytes"] > 0
    assert package["model_summaries"]["person"]["bytes"] > 0
    assert package["models"]["household"]["spec"]["level"] == "household"
    assert package["models"]["person"]["spec"]["level"] == "person"
    assert package["audits"]["household"]["passed"] is True
    assert package["audits"]["person"]["passed"] is True
    assert package["privacy"]["publishable_candidate"] is True


def test_cli_packages_release_copies_with_model_release_manifests(tmp_path) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    household_release_model_path = tmp_path / "household-model-publishable.json"
    person_release_model_path = tmp_path / "person-model-publishable.json"
    household_release_manifest_path = tmp_path / "household-release-manifest.json"
    person_release_manifest_path = tmp_path / "person-release-manifest.json"
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    household_release_model_path.write_text(household_model_path.read_text())
    person_release_model_path.write_text(person_model_path.read_text())
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    _write_model_release_manifest(
        household_release_manifest_path,
        source_model_path=household_model_path,
        output_model_path=household_release_model_path,
    )
    _write_model_release_manifest(
        person_release_manifest_path,
        source_model_path=person_model_path,
        output_model_path=person_release_model_path,
    )

    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_release_model_path),
                "--person-model",
                str(person_release_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--household-release-manifest",
                str(household_release_manifest_path),
                "--person-release-manifest",
                str(person_release_manifest_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )

    package = json.loads(package_path.read_text())
    assert package["release_manifests"]["household"]["source_model"] == str(
        household_model_path
    )
    assert package["release_manifests"]["household"]["output_model"] == str(
        household_release_model_path
    )
    assert package["release_manifests"]["person"]["source_model"] == str(
        person_model_path
    )
    assert package["release_manifests"]["person"]["output_model"] == str(
        person_release_model_path
    )


def test_cli_inspects_linked_model_package_as_json(tmp_path, capsys) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "tree",
                "inspect-package",
                str(package_path),
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "synthpopcan-linked-tree-package-inspection-v1"
    assert report["package_type"] == "linked_household_person"
    assert report["source"]["provider"] == "Statistics Canada"
    assert report["source"]["access_class"] == "restricted"
    assert (
        report["source"]["redistribution_note"]
        == "Do not redistribute source microdata."
    )
    assert report["training"]["target_profile"] == "minimal"
    assert report["training"]["geography_filter"] == {"column": "PR", "value": "24"}
    assert report["privacy"]["publishable_candidate"] is True
    assert report["models"]["household"]["level"] == "household"
    assert report["models"]["person"]["level"] == "person"
    assert report["audits"]["household"]["passed"] is True
    assert report["audits"]["person"]["passed"] is True
    assert report["review_note"] == "reviewed fixture package"
    assert "embedded_model_payloads" not in report


def test_cli_inspect_package_wraps_bad_package_json(tmp_path) -> None:
    from click import ClickException

    bad_package = tmp_path / "bad-package.json"
    bad_package.write_text("{")

    with pytest.raises(ClickException, match="not valid JSON"):
        main(["tree", "inspect-package", str(bad_package)])


def test_cli_inspects_linked_model_package_as_table(tmp_path, capsys) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["tree", "inspect-package", str(package_path)]) == 0

    output = capsys.readouterr().out
    assert "Linked Model Package" in output
    assert "Statistics Canada" in output
    assert "publishable_candidate" in output
    assert "Do not redistribute source microdata." in output


def test_cli_generates_linked_population_from_package(tmp_path) -> None:
    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    households_path = tmp_path / "synthetic-households.csv"
    persons_path = tmp_path / "synthetic-persons.csv"
    manifest_path = tmp_path / "synthetic-linked-manifest.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "tree",
                "generate-from-package",
                str(package_path),
                "--households",
                "3",
                "--condition",
                "geo=QC",
                "--households-out",
                str(households_path),
                "--persons-out",
                str(persons_path),
                "--manifest-out",
                str(manifest_path),
                "--random-seed",
                "13",
            ]
        )
        == 0
    )

    with households_path.open(newline="") as handle:
        households = list(csv.DictReader(handle))
    with persons_path.open(newline="") as handle:
        persons = list(csv.DictReader(handle))
    report = validate_linked_population(
        households,
        persons,
        household_size_column="household_size",
    )
    manifest = json.loads(manifest_path.read_text())
    assert report["passed"] is True
    assert len(households) == 3
    assert len(persons) == 6
    assert manifest["command"] == "tree generate-from-package"
    assert manifest["package"]["package_path"] == str(package_path)
    assert manifest["package"]["source"]["provider"] == "Statistics Canada"
    assert manifest["household_conditions"] == {"geo": "QC"}
    assert manifest["effective_random_seed"] == 13


def test_cli_refuses_generation_from_non_publishable_package(tmp_path) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    households_path = tmp_path / "synthetic-households.csv"
    persons_path = tmp_path / "synthetic-persons.csv"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)
    assert (
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )
        == 0
    )
    package = json.loads(package_path.read_text())
    package["privacy"]["publishable_candidate"] = False
    package_path.write_text(json.dumps(package) + "\n")

    with pytest.raises(ClickException, match="publishable candidate"):
        main(
            [
                "tree",
                "generate-from-package",
                str(package_path),
                "--households",
                "3",
                "--households-out",
                str(households_path),
                "--persons-out",
                str(persons_path),
            ]
        )


def test_cli_requires_source_provenance_for_linked_model_packages(tmp_path) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )

    with pytest.raises(ClickException, match="requires --source-provenance"):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_validates_source_provenance_for_linked_model_packages(tmp_path) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    source_provenance_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-source-provenance-v1",
                "title": "2016 Census PUMF",
            }
        )
        + "\n"
    )

    with pytest.raises(
        ClickException,
        match="source provenance missing required fields",
    ):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_requires_training_manifest_for_linked_model_packages(tmp_path) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    package_path = tmp_path / "linked-model-package.json"

    with pytest.raises(ClickException, match="requires --training-manifest"):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_requires_review_note_for_linked_model_packages(tmp_path) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)

    with pytest.raises(ClickException, match="requires --review-note"):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "   ",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_checks_training_manifest_model_paths_for_linked_packages(
    tmp_path,
) -> None:
    from click import ClickException

    household_model_path, person_model_path = _write_publishable_linked_model_fixtures(
        tmp_path
    )
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=tmp_path / "other-household-model.json",
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)

    with pytest.raises(
        ClickException,
        match="training manifest household model path does not match",
    ):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_refuses_to_package_private_linked_models(tmp_path) -> None:
    from click import ClickException

    household_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "2", "tenure": "owner"},),
    )
    person_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo", "household_size", "tenure"),
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
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    source_provenance_path = tmp_path / "source-provenance.json"
    package_path = tmp_path / "linked-model-package.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    _write_linked_training_manifest(
        training_manifest_path,
        household_model_path=household_model_path,
        person_model_path=person_model_path,
    )
    _write_source_provenance(source_provenance_path)

    with pytest.raises(ClickException, match="Linked model audit did not pass"):
        main(
            [
                "tree",
                "package-linked-models",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--source-provenance",
                str(source_provenance_path),
                "--review-note",
                "reviewed fixture package",
                "--out",
                str(package_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
            ]
        )

    assert not package_path.exists()


def test_cli_reports_linked_model_release_readiness(tmp_path, capsys) -> None:
    household_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "2", "tenure": "owner"},),
    )
    person_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo", "household_size", "tenure"),
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
    training_manifest_path = tmp_path / "linked-training-manifest.json"
    write_tree_model(household_model_path, household_model)
    write_tree_model(person_model_path, person_model)
    training_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-linked-tree-training-v1",
                "source": {
                    "path": "data/private/census/hierarchical.csv",
                    "source_format": "statcan-2016-hierarchical",
                    "records": 100,
                    "households": 40,
                },
                "column_source": {
                    "household_block": "household_core",
                    "person_block": "person_demographics",
                },
                "target_profile": "minimal",
                "geography_filter": {"column": "PR", "value": "24"},
                "method": "conditional-frequency",
                "random_seed": 7,
                "training": {
                    "household": {"records": 40},
                    "person": {"records": 100},
                },
            }
        )
        + "\n"
    )

    assert (
        main(
            [
                "tree",
                "release-readiness",
                "--household-model",
                str(household_model_path),
                "--person-model",
                str(person_model_path),
                "--training-manifest",
                str(training_manifest_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "synthpopcan-linked-tree-readiness-v1"
    assert report["readiness"] == "private_working"
    assert report["package_allowed"] is False
    assert report["models"]["household"]["release_class"] == "private_working"
    assert report["models"]["person"]["release_class"] == "private_working"
    assert report["training_manifest"] == {
        "path": str(training_manifest_path),
        "schema_version": "synthpopcan-linked-tree-training-v1",
        "source": {
            "path": "data/private/census/hierarchical.csv",
            "source_format": "statcan-2016-hierarchical",
            "records": 100,
            "households": 40,
        },
        "column_source": {
            "household_block": "household_core",
            "person_block": "person_demographics",
        },
        "target_profile": "minimal",
        "geography_filter": {"column": "PR", "value": "24"},
        "method": "conditional-frequency",
        "random_seed": 7,
        "training": {
            "household": {"records": 40},
            "person": {"records": 100},
        },
    }
    assert report["audits"]["household"]["passed"] is True
    assert report["audits"]["person"]["passed"] is True
    assert report["next_steps"] == [
        (
            "Prepare reviewed publishable-candidate copies with "
            "`tree prepare-model-release`, then rerun this readiness report."
        )
    ]


def test_cli_release_readiness_wraps_bad_model_json(tmp_path) -> None:
    from click import ClickException

    bad_model = tmp_path / "bad-model.json"
    bad_model.write_text("{")

    with pytest.raises(ClickException, match="not valid JSON"):
        main(
            [
                "tree",
                "release-readiness",
                "--household-model",
                str(bad_model),
                "--person-model",
                str(bad_model),
            ]
        )


def test_cli_prepares_publishable_candidate_model(tmp_path) -> None:
    source_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "2", "tenure": "owner"},),
    )
    source_model_path = tmp_path / "household-model.json"
    candidate_model_path = tmp_path / "household-model-publishable.json"
    manifest_path = tmp_path / "household-model-publishable.manifest.json"
    write_tree_model(source_model_path, source_model)

    assert (
        main(
            [
                "tree",
                "prepare-model-release",
                str(source_model_path),
                "--out",
                str(candidate_model_path),
                "--manifest-out",
                str(manifest_path),
                "--min-support",
                "1",
                "--max-purity",
                "1",
                "--review-note",
                "fixture release review",
            ]
        )
        == 0
    )

    candidate_model = json.loads(candidate_model_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert candidate_model["release_class"] == "publishable_candidate"
    assert candidate_model["privacy"]["publishable"] is True
    assert manifest["schema_version"] == "synthpopcan-tree-release-manifest-v1"
    assert manifest["source_model"] == str(source_model_path)
    assert manifest["output_model"] == str(candidate_model_path)
    assert manifest["release_class"] == "publishable_candidate"
    assert manifest["review_note"] == "fixture release review"
    assert manifest["audit"]["issues"] == [
        {
            "severity": "warning",
            "kind": "private_working_release_class",
            "message": (
                "Model is not marked as a publishable candidate; keep it "
                "private unless a packaging workflow changes its release class."
            ),
        }
    ]


def test_cli_refuses_to_prepare_model_release_with_blocking_audit_issue(
    tmp_path,
) -> None:
    from click import ClickException

    source_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "2", "tenure": "owner"},),
    )
    source_model_path = tmp_path / "household-model.json"
    candidate_model_path = tmp_path / "household-model-publishable.json"
    write_tree_model(source_model_path, source_model)

    with pytest.raises(ClickException, match="Model release audit has blocking issues"):
        main(
            [
                "tree",
                "prepare-model-release",
                str(source_model_path),
                "--out",
                str(candidate_model_path),
                "--min-support",
                "2",
                "--max-purity",
                "1",
            ]
        )

    assert not candidate_model_path.exists()


def test_cli_trains_linked_models_from_suggested_blocks(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    household_model_path = tmp_path / "household-model.json"
    person_model_path = tmp_path / "person-model.json"
    manifest_path = tmp_path / "linked-training-manifest.json"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,DTYPE,ROOM,BEDRM,CONDO,"
        "PRESMORTG,VALUE,SHELCO,SUBSIDY,REPAIR,BUILT,AGEGRP,SEX,MarStH,IMMSTAT\n"
        "1,11,111,11101,1,24,owner,detached,6,3,no,yes,500000,1200,no,"
        "regular,1991,adult,F,married,non_immigrant\n"
        "1,11,111,11102,1,24,owner,detached,6,3,no,yes,500000,1200,no,"
        "regular,1991,child,M,never_married,non_immigrant\n"
        "2,21,211,21101,1,24,renter,apartment,4,2,yes,no,0,900,no,"
        "regular,2001,adult,F,single,immigrant\n"
    )

    assert (
        main(
            [
                "tree",
                "train-linked",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--suggested-blocks",
                "--household-model-out",
                str(household_model_path),
                "--person-model-out",
                str(person_model_path),
                "--manifest-out",
                str(manifest_path),
                "--random-seed",
                "7",
                "--min-support",
                "2",
            ]
        )
        == 0
    )

    household_model = json.loads(household_model_path.read_text())
    person_model = json.loads(person_model_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    assert household_model["spec"]["level"] == "household"
    assert household_model["spec"]["target_columns"] == [
        "household_size",
        "TENUR",
        "DTYPE",
        "ROOM",
        "BEDRM",
        "CONDO",
        "PRESMORTG",
        "VALUE",
        "SHELCO",
        "SUBSIDY",
        "REPAIR",
        "BUILT",
    ]
    assert person_model["spec"]["level"] == "person"
    assert person_model["spec"]["target_columns"] == [
        "AGEGRP",
        "SEX",
        "MarStH",
        "IMMSTAT",
    ]
    assert manifest["schema_version"] == "synthpopcan-linked-tree-training-v1"
    assert manifest["source"]["source_format"] == "statcan-2016-hierarchical"
    assert manifest["column_source"] == {
        "mode": "profile",
        "profile": "statcan-2016-hierarchical",
        "household_block": "household_core",
        "person_block": "person_demographics",
    }
    assert manifest["models"]["household"]["path"] == str(household_model_path)
    assert manifest["models"]["person"]["path"] == str(person_model_path)


def test_cli_trains_linked_models_with_geography_and_minimal_profile(tmp_path) -> None:
    source = tmp_path / "hierarchical.csv"
    household_model_path = tmp_path / "household-model.json"
    person_model_path = tmp_path / "person-model.json"
    manifest_path = tmp_path / "linked-training-manifest.json"
    source.write_text(
        "HH_ID,EF_ID,CF_ID,PP_ID,WEIGHT,PR,TENUR,DTYPE,ROOM,BEDRM,CONDO,"
        "PRESMORTG,VALUE,SHELCO,SUBSIDY,REPAIR,BUILT,AGEGRP,SEX,MarStH,IMMSTAT\n"
        "1,11,111,11101,1,24,owner,detached,6,3,no,yes,500000,1200,no,"
        "regular,1991,adult,F,married,non_immigrant\n"
        "2,21,211,21101,1,11,renter,apartment,4,2,yes,no,0,900,no,"
        "regular,2001,adult,F,single,immigrant\n"
    )

    assert (
        main(
            [
                "tree",
                "train-linked",
                str(source),
                "--input-format",
                "statcan-2016-hierarchical",
                "--suggested-blocks",
                "--geography-column",
                "PR",
                "--geography-value",
                "11",
                "--target-profile",
                "minimal",
                "--household-model-out",
                str(household_model_path),
                "--person-model-out",
                str(person_model_path),
                "--manifest-out",
                str(manifest_path),
                "--min-support",
                "1",
            ]
        )
        == 0
    )

    household_model = json.loads(household_model_path.read_text())
    person_model = json.loads(person_model_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    assert household_model["records_trained"] == 1
    assert household_model["spec"]["target_columns"] == ["household_size", "TENUR"]
    assert person_model["records_trained"] == 1
    assert person_model["spec"]["target_columns"] == ["AGEGRP", "SEX"]
    assert manifest["target_profile"] == "minimal"
    assert manifest["geography_filter"] == {"column": "PR", "value": "11"}
    assert manifest["source"]["records"] == 1
    assert manifest["source"]["households"] == 1


def test_cli_train_linked_requires_suggested_blocks(tmp_path) -> None:
    from click import ClickException

    source = tmp_path / "hierarchical.csv"
    source.write_text("HH_ID,WEIGHT\n1,1\n")

    with pytest.raises(ClickException, match="requires --suggested-blocks"):
        main(
            [
                "tree",
                "train-linked",
                str(source),
                "--household-model-out",
                str(tmp_path / "household.json"),
                "--person-model-out",
                str(tmp_path / "person.json"),
                "--manifest-out",
                str(tmp_path / "manifest.json"),
            ]
        )


def test_cli_train_linked_wraps_processing_errors(tmp_path) -> None:
    from click import ClickException

    source = tmp_path / "hierarchical.csv"
    source.write_text("HH_ID,WEIGHT\n1,1\n")

    with pytest.raises(ClickException, match="missing required columns"):
        main(
            [
                "tree",
                "train-linked",
                str(source),
                "--suggested-blocks",
                "--geography-column",
                "PR",
                "--geography-value",
                "24",
                "--household-model-out",
                str(tmp_path / "household.json"),
                "--person-model-out",
                str(tmp_path / "person.json"),
                "--manifest-out",
                str(tmp_path / "manifest.json"),
            ]
        )


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


def test_linked_population_reports_unknown_and_invalid_households() -> None:
    report = validate_linked_population(
        households=[
            {"synthetic_household_id": "1"},
            {"synthetic_household_id": "2", "household_size": "bad"},
            {"synthetic_household_id": "3", "household_size": "0"},
        ],
        persons=[
            {"synthetic_person_id": "1", "synthetic_household_id": "missing"},
        ],
    )

    assert report["passed"] is False
    assert report["summary"] == {
        "households": 3,
        "persons": 1,
        "households_with_size_mismatches": 0,
        "persons_with_unknown_households": 1,
    }
    assert [issue["kind"] for issue in report["issues"]] == [
        "invalid_household_size",
        "invalid_household_size",
        "invalid_household_size",
        "unknown_person_household",
    ]


def test_generate_linked_population_rejects_bad_models_and_links() -> None:
    household_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "1"},),
    )
    household_without_tenure = train_frequency_model_from_rows(
        TreeModelSpec(
            level="household",
            target_columns=("household_size",),
            conditioning_columns=("geo",),
        ),
        rows=({"geo": "QC", "household_size": "1"},),
    )
    person_model = train_frequency_model_from_rows(
        TreeModelSpec(
            level="person",
            target_columns=("age_group",),
            conditioning_columns=("geo", "household_size", "tenure"),
        ),
        rows=(
            {
                "geo": "QC",
                "household_size": "1",
                "tenure": "owner",
                "age_group": "adult",
            },
        ),
    )

    with pytest.raises(ValueError, match="household model must have level"):
        generate_linked_population(person_model, person_model, households=1)
    with pytest.raises(ValueError, match="person model must have level"):
        generate_linked_population(household_model, household_model, households=1)
    with pytest.raises(ValueError, match="households must be greater than zero"):
        generate_linked_population(household_model, person_model, households=0)
    with pytest.raises(ValueError, match="missing columns: tenure"):
        generate_linked_population(
            household_without_tenure,
            person_model,
            households=1,
            household_conditions={"geo": "QC"},
        )


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
    manifest_out = tmp_path / "synthetic-linked.manifest.json"
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
                "--manifest-out",
                str(manifest_out),
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
    manifest = json.loads(manifest_out.read_text())
    assert manifest["schema_version"] == "synthpopcan-tree-generation-manifest-v1"
    assert manifest["command"] == "tree generate-linked"
    assert manifest["outputs"] == {
        "households": str(households_out),
        "persons": str(persons_out),
    }
    assert manifest["households"] == 1
    assert manifest["household_conditions"] == {"geo": "QC"}
    assert manifest["random_seed"] is None
    assert manifest["effective_random_seed"] == 0
    assert manifest["household_size_column"] == "household_size"
    assert manifest["household_model"]["path"] == str(household_model_path)
    assert manifest["household_model"]["level"] == "household"
    assert manifest["person_model"]["path"] == str(person_model_path)
    assert manifest["person_model"]["level"] == "person"


def test_cli_generate_linked_wraps_bad_model_json(tmp_path) -> None:
    from click import ClickException

    bad_model = tmp_path / "bad-model.json"
    bad_model.write_text("{")

    with pytest.raises(ClickException, match="not valid JSON"):
        main(
            [
                "tree",
                "generate-linked",
                "--household-model",
                str(bad_model),
                "--person-model",
                str(bad_model),
                "--households",
                "1",
                "--households-out",
                str(tmp_path / "households.csv"),
                "--persons-out",
                str(tmp_path / "persons.csv"),
            ]
        )


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
