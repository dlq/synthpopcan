from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import synthpopcan as spc
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.ipf import IPFResult
from synthpopcan.tree import read_tree_training_sample, train_cart_model
from synthpopcan.web_demo_models import demo_model_payload


def test_top_level_api_runs_path_based_ipf_workflow(tmp_path: Path) -> None:
    seed_path = tmp_path / "seed.csv"
    controls_path = tmp_path / "controls.csv"
    weights_path = tmp_path / "weights.csv"
    expanded_path = tmp_path / "expanded.csv"
    write_csv(
        seed_path,
        ["id", "age", "sex"],
        [
            {"id": "1", "age": "young", "sex": "F"},
            {"id": "2", "age": "young", "sex": "M"},
            {"id": "3", "age": "old", "sex": "F"},
            {"id": "4", "age": "old", "sex": "M"},
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "age", "sex", "count"],
        [
            {"margin": "age", "dimensions": "age", "age": "young", "count": "60"},
            {"margin": "age", "dimensions": "age", "age": "old", "count": "40"},
            {"margin": "sex", "dimensions": "sex", "sex": "F", "count": "50"},
            {"margin": "sex", "dimensions": "sex", "sex": "M", "count": "50"},
        ],
    )

    fit = spc.fit_ipf(seed_path, controls_path)
    expanded = spc.expand_population(fit)
    spc.write_weights(fit, weights_path)
    spc.write_population(expanded, expanded_path)

    assert fit.converged is True
    assert [row["weight"] for row in read_csv(weights_path)] == [
        "30",
        "30",
        "20",
        "20",
    ]
    assert len(read_csv(expanded_path)) == 100


def test_top_level_api_generates_from_linked_model_package(tmp_path: Path) -> None:
    package_path = tmp_path / "demo-package.json"
    output_dir = tmp_path / "population"
    package_path.write_text(
        json.dumps(demo_model_payload("demo-linked-household-person")),
    )

    package = spc.read_model_package(package_path)
    population = spc.generate_from_model(
        package,
        households=3,
        conditions={"geo": "Demo North"},
        random_seed=11,
    )
    spc.write_population(population, output_dir)

    assert isinstance(population, spc.LinkedPopulation)
    assert len(population.households) == 3
    assert len(population.persons) >= 3
    assert (output_dir / "households.csv").is_file()
    assert (output_dir / "persons.csv").is_file()


def test_top_level_api_accepts_in_memory_ipf_inputs() -> None:
    seed = [
        {"age": "young", "sex": "F"},
        {"age": "old", "sex": "M"},
    ]
    controls = ControlTable(
        margins=(
            ControlMargin(
                name="age",
                dimensions=("age",),
                cells=(
                    ControlCell(categories={"age": "young"}, count=5),
                    ControlCell(categories={"age": "old"}, count=7),
                ),
            ),
        ),
        dimensions=("age",),
    )

    fit = spc.fit_ipf(seed, controls)
    fit_from_margins = spc.fit_ipf(seed, controls.to_ipf_margins())

    assert fit.converged is True
    assert fit.margin_totals(("age",)) == {("young",): 5, ("old",): 7}
    assert fit_from_margins.margin_totals(("age",)) == fit.margin_totals(("age",))


def test_top_level_api_writes_custom_weight_column(tmp_path: Path) -> None:
    result = IPFResult(
        records=[{"id": 1, "weight": "original"}],
        weights=[2.5],
        converged=True,
        iterations=1,
        max_abs_error=0,
    )
    output_path = tmp_path / "weights.csv"

    spc.write_weights(result, output_path)
    spc.write_weights(result, tmp_path / "custom.csv", weight_column="synthetic_weight")

    assert read_csv(output_path) == [
        {"id": "1", "weight": "original", "fitted_weight": "2.5"}
    ]
    assert read_csv(tmp_path / "custom.csv") == [
        {"id": "1", "weight": "original", "synthetic_weight": "2.5"}
    ]


def test_top_level_api_reports_empty_outputs_and_invalid_packages(
    tmp_path: Path,
) -> None:
    empty_result = IPFResult(
        records=[],
        weights=[],
        converged=True,
        iterations=0,
        max_abs_error=0,
    )

    with pytest.raises(ValueError, match="empty IPF result"):
        spc.write_weights(empty_result, tmp_path / "weights.csv")
    with pytest.raises(ValueError, match="empty rows"):
        spc.write_population([], tmp_path / "population.csv")

    invalid_json_path = tmp_path / "invalid.json"
    invalid_json_path.write_text("{")
    with pytest.raises(ValueError, match="not valid JSON"):
        spc.read_model_package(invalid_json_path)

    non_object_path = tmp_path / "array.json"
    non_object_path.write_text("[]")
    with pytest.raises(ValueError, match="must be a JSON object"):
        spc.read_model_package(non_object_path)

    wrong_schema_path = tmp_path / "wrong-schema.json"
    wrong_schema_path.write_text(json.dumps({"schema_version": "old"}))
    with pytest.raises(ValueError, match="unsupported linked model package schema"):
        spc.read_model_package(wrong_schema_path)


def test_top_level_api_rejects_unpublishable_and_malformed_packages() -> None:
    package = demo_model_payload("demo-linked-household-person")
    package["privacy"] = {"publishable_candidate": False}

    with pytest.raises(ValueError, match="not marked as a publishable candidate"):
        spc.generate_from_model(package, households=1)

    package_without_models = demo_model_payload("demo-linked-household-person")
    package_without_models.pop("models")
    with pytest.raises(ValueError, match="must include models"):
        spc.generate_from_model(
            package_without_models,
            households=1,
            require_publishable=False,
        )

    package_without_person = demo_model_payload("demo-linked-household-person")
    models = dict(package_without_person["models"])  # type: ignore[arg-type]
    models.pop("person")
    package_without_person["models"] = models
    with pytest.raises(ValueError, match="household and person models"):
        spc.generate_from_model(
            package_without_person,
            households=1,
            require_publishable=False,
        )

    unsupported_model = demo_model_payload("demo-linked-household-person")
    bad_models = dict(unsupported_model["models"])  # type: ignore[arg-type]
    bad_household = dict(bad_models["household"])  # type: ignore[index]
    bad_household["model_type"] = "neural-net"
    bad_models["household"] = bad_household
    unsupported_model["models"] = bad_models
    with pytest.raises(ValueError, match="unsupported tree model type"):
        spc.generate_from_model(
            unsupported_model,
            households=1,
            require_publishable=False,
        )


def test_top_level_api_accepts_package_path_and_default_household_size(
    tmp_path: Path,
) -> None:
    package = demo_model_payload("demo-linked-household-person")
    package.pop("household_size_column", None)
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(package))

    population = spc.generate_from_model(package_path, households=2, random_seed=1)

    assert len(population.households) == 2
    assert len(population.persons) >= 2


def test_top_level_api_generates_from_cart_model_package(tmp_path: Path) -> None:
    household_source = tmp_path / "cart-households.csv"
    household_source.write_text(
        "geo,household_size,tenure,weight\n"
        "QC,1,renter,1\n"
        "QC,2,owner,1\n"
        "ON,3,owner,1\n"
    )
    person_source = tmp_path / "cart-persons.csv"
    person_source.write_text(
        "geo,household_size,tenure,age_group,sex,weight\n"
        "QC,1,renter,adult,F,1\n"
        "QC,2,owner,child,M,1\n"
        "ON,3,owner,adult,M,1\n"
    )
    household_model = train_cart_model(
        read_tree_training_sample(
            household_source,
            level="household",
            target_columns=("household_size", "tenure"),
            conditioning_columns=("geo",),
            weight_column="weight",
        ),
        min_samples_leaf=1,
    )
    person_model = train_cart_model(
        read_tree_training_sample(
            person_source,
            level="person",
            target_columns=("age_group", "sex"),
            conditioning_columns=("geo", "household_size", "tenure"),
            weight_column="weight",
        ),
        min_samples_leaf=1,
    )
    package = {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "household_size_column": "household_size",
        "privacy": {"publishable_candidate": True},
        "models": {
            "household": household_model.to_dict(),
            "person": person_model.to_dict(),
        },
    }

    population = spc.generate_from_model(
        package,
        households=2,
        conditions={"geo": "QC"},
        random_seed=7,
    )

    assert len(population.households) == 2
    assert len(population.persons) >= 2
    assert {row["geo"] for row in population.households} == {"QC"}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))
