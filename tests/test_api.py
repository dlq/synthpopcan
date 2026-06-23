from __future__ import annotations

import csv
import json
from pathlib import Path

import synthpopcan as spc
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


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))
