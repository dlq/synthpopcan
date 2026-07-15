from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import synthpopcan as spc
import synthpopcan.api as api
from synthpopcan.controls import ControlCell, ControlMargin, ControlTable
from synthpopcan.ipf import IPFResult
from synthpopcan.models import model_payload
from synthpopcan.tree import read_tree_training_sample, train_cart_model

STABLE_API_NAMES = (
    "ControlTable",
    "IPFResult",
    "LinkedPopulation",
    "LinkedPopulationFiles",
    "PopulationRows",
    "SmallAreaResult",
    "calibrate_small_area",
    "expand_population",
    "fetch_model",
    "fit_ipf",
    "generate_from_model",
    "read_controls",
    "read_model_package",
    "read_seed",
    "render_small_area_map",
    "write_linked_population",
    "write_population",
    "write_weights",
)


def test_stable_api_contract_is_explicit() -> None:
    assert tuple(api.__all__) == STABLE_API_NAMES
    assert tuple(spc.__all__) == (
        *STABLE_API_NAMES[:6],
        "__version__",
        *STABLE_API_NAMES[6:],
    )
    expected_parameters = {
        "fit_ipf": ("seed", "controls", "weight_field", "max_iterations", "tolerance"),
        "generate_from_model": (
            "package",
            "households",
            "conditions",
            "random_seed",
            "household_size_column",
            "require_publishable",
        ),
        "calibrate_small_area": (
            "population",
            "controls",
            "geography_dimension",
            "output_dir",
            "person_controls",
            "geography_column",
            "max_iterations",
            "tolerance",
            "pool_size",
            "subsample_seed",
            "include_weights",
        ),
    }
    for name, parameters in expected_parameters.items():
        assert tuple(inspect.signature(getattr(spc, name)).parameters) == parameters


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
    assert spc.write_weights(fit, weights_path) == weights_path
    assert spc.write_population(expanded, expanded_path) == expanded_path

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
        json.dumps(model_payload("demo-linked-household-person")),
    )

    package = spc.read_model_package(package_path)
    population = spc.generate_from_model(
        package,
        households=3,
        conditions={"geo": "Demo North"},
        random_seed=11,
    )
    files = spc.write_linked_population(population, output_dir)

    assert isinstance(population, spc.LinkedPopulation)
    assert isinstance(files, spc.LinkedPopulationFiles)
    assert files.households == output_dir / "households.csv"
    assert files.persons == output_dir / "persons.csv"
    assert len(population.households) == 3
    assert len(population.persons) >= 3
    assert (output_dir / "households.csv").is_file()
    assert (output_dir / "persons.csv").is_file()


def test_top_level_api_fetches_bundled_demo_model() -> None:
    package = spc.fetch_model("demo-linked-household-person")

    population = spc.generate_from_model(
        package,
        households=2,
        conditions={"geo": "Demo North"},
        random_seed=11,
    )

    assert len(population.households) == 2
    assert len(population.persons) >= 2


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

    assert fit.converged is True
    assert fit.margin_totals(("age",)) == {("young",): 5, ("old",): 7}


def test_top_level_api_writes_custom_weight_column(tmp_path: Path) -> None:
    result = IPFResult(
        records=[{"id": 1, "weight": "original"}],
        weights=[2.5],
        converged=True,
        iterations=1,
        max_abs_error=0,
    )
    output_path = tmp_path / "nested" / "weights.csv"

    assert spc.write_weights(result, output_path) == output_path
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
    with pytest.raises(TypeError, match="write_linked_population"):
        spc.write_population(  # type: ignore[arg-type]
            spc.LinkedPopulation(
                households=[{"synthetic_household_id": "h1"}],
                persons=[
                    {
                        "synthetic_household_id": "h1",
                        "synthetic_person_id": "p1",
                    }
                ],
            ),
            tmp_path / "wrong-output.csv",
        )

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
    with pytest.raises(ValueError, match="unsupported linked model package schema"):
        spc.generate_from_model(
            {"schema_version": "old"},
            households=1,
            require_publishable=False,
        )

    package = model_payload("demo-linked-household-person")
    package["privacy"] = {"publishable_candidate": False}

    with pytest.raises(ValueError, match="not marked as a publishable candidate"):
        spc.generate_from_model(package, households=1)

    package_without_models = model_payload("demo-linked-household-person")
    package_without_models.pop("models")
    with pytest.raises(ValueError, match="must include models"):
        spc.generate_from_model(
            package_without_models,
            households=1,
            require_publishable=False,
        )

    package_without_person = model_payload("demo-linked-household-person")
    models = dict(package_without_person["models"])  # type: ignore[arg-type]
    models.pop("person")
    package_without_person["models"] = models
    with pytest.raises(ValueError, match="household and person models"):
        spc.generate_from_model(
            package_without_person,
            households=1,
            require_publishable=False,
        )

    unsupported_model = model_payload("demo-linked-household-person")
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
    package = model_payload("demo-linked-household-person")
    package.pop("household_size_column", None)
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(package))

    population = spc.generate_from_model(package_path, households=2, random_seed=1)

    assert len(population.households) == 2
    assert len(population.persons) >= 2


def test_top_level_api_generates_from_cart_model_package(tmp_path: Path) -> None:
    household_source = tmp_path / "cart-households.csv"
    household_source.write_text(
        "geo,household_size,tenure,weight\nQC,1,renter,1\nQC,2,owner,1\nON,3,owner,1\n"
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


def test_top_level_api_composes_generation_with_small_area_calibration(
    tmp_path: Path,
) -> None:
    controls_path = tmp_path / "controls.csv"
    person_controls_path = tmp_path / "person-controls.csv"
    population = spc.LinkedPopulation(
        households=[
            {"synthetic_household_id": "h1", "TENUR": "1"},
            {"synthetic_household_id": "h2", "TENUR": "2"},
        ],
        persons=[
            {
                "synthetic_person_id": "p1",
                "synthetic_household_id": "h1",
                "age_group": "adult",
            },
            {
                "synthetic_person_id": "p2",
                "synthetic_household_id": "h2",
                "age_group": "adult",
            },
        ],
    )
    write_csv(
        controls_path,
        ["margin", "dimensions", "ct", "TENUR", "count"],
        [
            {
                "margin": "ct_tenure",
                "dimensions": "ct,TENUR",
                "ct": "4620001",
                "TENUR": "1",
                "count": "2",
            },
            {
                "margin": "ct_tenure",
                "dimensions": "ct,TENUR",
                "ct": "4620001",
                "TENUR": "2",
                "count": "1",
            },
        ],
    )
    write_csv(
        person_controls_path,
        ["margin", "dimensions", "ct", "age_group", "count"],
        [
            {
                "margin": "ct_age",
                "dimensions": "ct,age_group",
                "ct": "4620001",
                "age_group": "adult",
                "count": "3",
            },
        ],
    )

    result = spc.calibrate_small_area(
        population,
        spc.read_controls(controls_path),
        person_controls=spc.read_controls(person_controls_path),
        geography_dimension="ct",
        output_dir=tmp_path / "small-area",
        include_weights=True,
    )

    assert isinstance(result, spc.SmallAreaResult)
    assert result.assigned_households == 3
    assert result.assigned_persons == 3
    assert result.total_geographies == 1
    assert result.converged is True
    assert result.max_abs_error == 0
    assert result.calibration_mode == "household_and_person"
    assert result.weights_path is not None and result.weights_path.is_file()
    assert result.report_path.is_file()
    assert {row["ct"] for row in read_csv(result.population.households)} == {"4620001"}
    assert {row["ct"] for row in read_csv(result.population.persons)} == {"4620001"}

    candidate_files = spc.write_linked_population(population, tmp_path / "candidates")
    file_result = spc.calibrate_small_area(
        candidate_files,
        controls_path,
        geography_dimension="ct",
        output_dir=tmp_path / "small-area-from-files",
    )
    assert file_result.assigned_households == 3
    assert file_result.population.households.is_file()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# api.py — render_small_area_map (from test_coverage_gaps2.py)
# ---------------------------------------------------------------------------


def test_render_small_area_map_delegates_to_render_synthesis_map(tmp_path) -> None:
    calls: list[dict] = []
    files = spc.LinkedPopulationFiles(
        households=tmp_path / "hh.csv",
        persons=tmp_path / "people.csv",
    )
    small_area = spc.SmallAreaResult(
        population=files,
        report_path=tmp_path / "report.json",
        weights_path=None,
        assigned_households=2,
        assigned_persons=3,
        total_geographies=1,
        converged=True,
        max_abs_error=0,
        calibration_mode="household_only",
        details={},
    )

    def _fake_render(**kwargs):
        calls.append(kwargs)
        return tmp_path / "out.html"

    with patch("synthpopcan.map_render.render_synthesis_map", _fake_render):
        result = api.render_small_area_map(
            households=small_area,
            boundaries=str(tmp_path / "bounds.shp"),
            geography_column="ct",
            geography_id_field="CTUID",
            out=str(tmp_path / "out.html"),
        )

    assert len(calls) == 1
    assert calls[0]["households_path"] == files.households
    assert calls[0]["persons_path"] == files.persons
    assert calls[0]["geography_column"] == "ct"
    assert calls[0]["geography_id_field"] == "CTUID"
    assert result == tmp_path / "out.html"
