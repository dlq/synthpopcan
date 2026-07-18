from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import synthpopcan as spc
from synthpopcan.cli_tree import tree_training_sample_from_export
from synthpopcan.linked_schema import (
    LINKED_POPULATION_SCHEMA_VERSION,
    adopt_linked_population_directory,
    build_linked_population_contract,
    read_linked_population_contract,
    validate_linked_population_contract,
    write_linked_population_contract,
)
from synthpopcan.microdata import (
    export_training_rows,
    read_statcan_hierarchical_seed_sample,
)
from synthpopcan.tree import train_frequency_model, validate_linked_population_files


def test_build_linked_population_contract_matches_golden_fixture(
    tmp_path: Path,
) -> None:
    households, persons = _write_linked_fixture(tmp_path)

    contract = build_linked_population_contract(
        households,
        persons,
        geography_column="csd",
    )

    expected_path = (
        Path(__file__).parent / "fixtures" / "schemas" / "linked-population-v1.json"
    )
    assert contract == json.loads(expected_path.read_text())


def test_linked_population_contract_round_trips(tmp_path: Path) -> None:
    households, persons = _write_linked_fixture(tmp_path)
    manifest = tmp_path / "manifest.json"

    written = write_linked_population_contract(
        manifest,
        households,
        persons,
        geography_column="csd",
    )

    assert read_linked_population_contract(manifest) == written
    assert written["schema_version"] == LINKED_POPULATION_SCHEMA_VERSION


def test_linked_population_contract_allows_extension_columns(
    tmp_path: Path,
) -> None:
    households, persons = _write_linked_fixture(tmp_path)
    contract = build_linked_population_contract(households, persons)

    assert contract["geography"] is None
    validate_linked_population_contract(contract)


def test_linked_population_contract_rejects_incompatible_artifacts(
    tmp_path: Path,
) -> None:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text("household_size\n1\n")
    persons.write_text("synthetic_person_id,synthetic_household_id\np1,h1\n")

    with pytest.raises(ValueError, match="synthetic_household_id"):
        build_linked_population_contract(households, persons)

    with pytest.raises(ValueError, match="unsupported linked population schema"):
        validate_linked_population_contract({"schema_version": "legacy"})


def test_adopt_legacy_linked_population_validates_relationships(
    tmp_path: Path,
) -> None:
    _write_linked_fixture(tmp_path)

    contract = adopt_linked_population_directory(
        tmp_path,
        geography_column="csd",
    )

    assert (tmp_path / "manifest.json").is_file()
    assert contract["tables"]["persons"]["rows"] == 3

    (tmp_path / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id\np1,missing\n"
    )
    with pytest.raises(ValueError, match="unknown households"):
        adopt_linked_population_directory(tmp_path)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("format",), "json", "requires CSV tables"),
        (("tables",), [], "tables must be an object"),
        (("tables", "households"), [], "households table must be an object"),
        (("tables", "households", "path"), "../households.csv", "filename"),
        (("tables", "households", "path"), "", "filename"),
        (("tables", "households", "rows"), -1, "non-negative"),
        (("tables", "households", "rows"), True, "non-negative"),
        (("tables", "households", "primary_key"), "legacy_id", "primary key"),
        (("tables", "households", "columns"), "id", "columns must be strings"),
        (("tables", "households", "columns"), [""], "columns must be strings"),
        (
            ("tables", "households", "columns"),
            ["synthetic_household_id", "synthetic_household_id"],
            "columns must be unique",
        ),
        (("tables", "households", "columns"), ["household_size"], "missing"),
        (("relationships",), {}, "missing the household link"),
        (("relationships",), [], "missing the household link"),
        (("geography",), [], "geography must be an object"),
        (("geography", "household_column"), "", "non-empty string"),
        (("geography", "household_column"), 1, "non-empty string"),
        (("geography", "household_column"), "ada", "missing from"),
        (("geography", "person_assignment"), "copied", "unsupported"),
    ],
)
def test_contract_validation_rejects_each_invalid_contract_shape(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    households, persons = _write_linked_fixture(tmp_path)
    payload = build_linked_population_contract(
        households,
        persons,
        geography_column="csd",
    )
    _replace_nested(payload, path, value)

    with pytest.raises(ValueError, match=message):
        validate_linked_population_contract(payload)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("", "is empty"),
        (",household_size\nh1,1\n", "invalid header"),
        (
            "synthetic_household_id,synthetic_household_id\nh1,h1\n",
            "duplicate columns",
        ),
    ],
)
def test_contract_builder_rejects_invalid_csv_headers(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    households, persons = _write_linked_fixture(tmp_path)
    households.write_text(contents)

    with pytest.raises(ValueError, match=message):
        build_linked_population_contract(households, persons)


def test_contract_builder_requires_declared_geography(tmp_path: Path) -> None:
    households, persons = _write_linked_fixture(tmp_path)

    with pytest.raises(ValueError, match="missing required columns: ada"):
        build_linked_population_contract(
            households,
            persons,
            geography_column="ada",
        )


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("{", "is not valid JSON"),
        ("[]", "must be a JSON object"),
    ],
)
def test_contract_reader_rejects_invalid_json_documents(
    tmp_path: Path,
    contents: str,
    message: str,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(contents)

    with pytest.raises(ValueError, match=message):
        read_linked_population_contract(manifest)


def test_legacy_adoption_reports_fallback_validation_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_linked_fixture(tmp_path)
    monkeypatch.setattr(
        "synthpopcan.tree.validate_linked_population_files",
        lambda *args, **kwargs: {"passed": False, "issues": []},
    )

    with pytest.raises(ValueError, match="identifiers failed validation"):
        adopt_linked_population_directory(tmp_path)


@pytest.mark.parametrize(
    ("census_year", "person_columns"),
    [
        (2016, ("AGEGRP", "SEX")),
        (2021, ("AGEGRP", "GENDER")),
    ],
)
def test_census_vintages_generate_the_shared_linked_population_schema(
    tmp_path: Path,
    census_year: int,
    person_columns: tuple[str, ...],
) -> None:
    """Exercise each Census adapter from PUMF-shaped rows to v1 artifacts."""

    source_format = f"statcan-{census_year}-hierarchical"
    fixture = (
        Path(__file__).parent / "fixtures" / "census" / f"linked-{census_year}.csv"
    )
    sample = read_statcan_hierarchical_seed_sample(
        fixture,
        source_format=source_format,
    )
    household_rows, household_export = export_training_rows(
        sample,
        level="household",
        target_columns=("household_size", "TENUR"),
        conditioning_columns=("PR",),
    )
    person_rows, person_export = export_training_rows(
        sample,
        level="person",
        target_columns=person_columns,
        conditioning_columns=("PR", "household_size", "TENUR"),
    )
    household_model = train_frequency_model(
        tree_training_sample_from_export(
            rows=household_rows,
            export=household_export,
        ),
        min_support=1,
    )
    person_model = train_frequency_model(
        tree_training_sample_from_export(rows=person_rows, export=person_export),
        min_support=1,
    )
    package = {
        "schema_version": "synthpopcan-linked-tree-package-v1",
        "household_size_column": "household_size",
        "source": {
            "census_year": census_year,
            "source_format": source_format,
        },
        "privacy": {"publishable_candidate": True},
        "models": {
            "household": household_model.to_dict(),
            "person": person_model.to_dict(),
        },
    }

    population = spc.generate_from_model(
        package,
        households=4,
        conditions={"PR": "24"},
        random_seed=13,
    )
    files = spc.write_linked_population(
        population,
        tmp_path / str(census_year),
    )
    contract = read_linked_population_contract(files.manifest)
    validation = validate_linked_population_files(files.households, files.persons)

    assert sample.metadata["census_year"] == census_year
    assert household_model.source_format == source_format
    assert person_model.source_format == source_format
    assert contract["schema_version"] == LINKED_POPULATION_SCHEMA_VERSION
    assert contract["tables"]["households"]["primary_key"] == ("synthetic_household_id")
    assert contract["tables"]["persons"]["primary_key"] == "synthetic_person_id"
    assert contract["relationships"] == [
        {
            "from_table": "persons",
            "from_column": "synthetic_household_id",
            "to_table": "households",
            "to_column": "synthetic_household_id",
            "cardinality": "many-to-one",
        }
    ]
    assert set(person_columns) <= set(contract["tables"]["persons"]["columns"])
    assert contract["tables"]["households"]["rows"] == 4
    assert contract["tables"]["persons"]["rows"] == len(population.persons)
    assert validation["passed"] is True


def _write_linked_fixture(tmp_path: Path) -> tuple[Path, Path]:
    households = tmp_path / "households.csv"
    persons = tmp_path / "persons.csv"
    households.write_text(
        "synthetic_household_id,household_size,csd\nh1,2,2466023\nh2,1,2466023\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,age_group\n"
        "p1,h1,adult\n"
        "p2,h1,child\n"
        "p3,h2,adult\n"
    )
    return households, persons


def _replace_nested(
    payload: dict[str, Any],
    path: tuple[str, ...],
    value: object,
) -> None:
    target: dict[str, Any] = payload
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = value
