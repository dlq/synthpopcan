from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import synthpopcan.exchange as exchange
from synthpopcan.exchange import (
    EXCHANGE_SCHEMA_VERSION,
    create_exchange_bundle,
    read_exchange_manifest,
    validate_exchange_bundle,
)
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.linked_schema import write_linked_population_contract


def test_exchange_bundle_round_trips_and_preserves_source_bytes(
    tmp_path: Path,
) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"

    bundle = create_exchange_bundle(
        population,
        output,
        geography_universe=statcan_geography_universe(2021, "csd", "csd"),
        reproduction={"interface": "test", "command": ["create", "exchange"]},
        temporal_coverage={"census_vintage": "2021"},
        access_classification="public",
        redistribution_status="permitted",
        limitations=("Fictional test records only.",),
    )

    assert bundle.report["passed"] is True
    assert validate_exchange_bundle(output)["passed"] is True
    assert (
        bundle.households.read_bytes() == (population / "households.csv").read_bytes()
    )
    assert bundle.persons.read_bytes() == (population / "persons.csv").read_bytes()
    manifest = read_exchange_manifest(bundle.manifest)
    assert manifest["schema_version"] == EXCHANGE_SCHEMA_VERSION
    assert manifest["bundle_kind"] == "population-contribution"
    assert manifest["geography"]["census_vintage"] == 2021
    assert manifest["temporal_coverage"] == {"census_vintage": "2021"}
    assert (
        "activities, schedules, and locations" in manifest["missing_simulation_inputs"]
    )
    assert "Fictional test records only." in manifest["limitations"]
    assert {item["logical_name"] for item in manifest["files"]} == {
        "households",
        "persons",
        "linked_population",
        "data_dictionary",
        "provenance",
        "validation",
    }
    assert all(item["access_classification"] == "public" for item in manifest["files"])


def test_exchange_dictionary_covers_columns_and_missing_values(tmp_path: Path) -> None:
    population = _population(tmp_path / "population", missing=True)

    bundle = create_exchange_bundle(population, tmp_path / "exchange")

    dictionary = json.loads(bundle.data_dictionary.read_text())
    households = next(
        table for table in dictionary["tables"] if table["name"] == "households"
    )
    by_name = {column["name"]: column for column in households["columns"]}
    assert by_name["synthetic_household_id"]["role"] == "primary-key"
    assert by_name["csd"]["role"] == "geography-identifier"
    assert by_name["weight"]["role"] == "weight"
    assert by_name["note"]["missing_value"] == "empty-string"
    assert all(column["value_status"] == "modeled" for column in by_name.values())


def test_exchange_accepts_nested_generation_descriptor(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    contract = json.loads((population / "manifest.json").read_text())
    (population / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-tree-generation-manifest-v1",
                "linked_population": contract,
            }
        )
    )

    bundle = create_exchange_bundle(population, tmp_path / "exchange")

    assert bundle.report["passed"] is True


def test_exchange_accepts_successful_durable_run_provenance(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    run = tmp_path / "run.json"
    run.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-run-v1",
                "run_id": "20260807T120000Z-abcdef123456",
                "workflow": "model",
                "status": "succeeded",
                "created_at": "2026-08-07T12:00:00Z",
                "started_at": "2026-08-07T12:00:01Z",
                "finished_at": "2026-08-07T12:00:02Z",
                "synthpopcan_version": "0.8.0",
                "request": {"workflow": "model", "options": {"random_seed": 7}},
                "random_seed": 7,
                "inputs": [],
                "artifacts": [],
                "summary": {},
                "error": None,
                "reproduction": {"interface": "cli", "command": ["models", "generate"]},
                "assurance": {"schema_version": "synthpopcan-assurance-v1"},
            }
        )
    )

    bundle = create_exchange_bundle(
        population,
        tmp_path / "exchange",
        run_manifest=run,
    )

    provenance = json.loads(bundle.provenance.read_text())
    assert provenance["origin"]["kind"] == "durable-run"
    assert provenance["origin"]["run_id"] == "20260807T120000Z-abcdef123456"
    assert provenance["origin"]["run_manifest_sha256"] == _sha256(run)
    assert provenance["reproduction"]["interface"] == "cli"


@pytest.mark.parametrize("status", ["queued", "failed", "cancelled"])
def test_exchange_rejects_non_successful_durable_runs(
    tmp_path: Path, status: str
) -> None:
    population = _population(tmp_path / "population")
    run = tmp_path / "run.json"
    run.write_text(
        json.dumps({"schema_version": "synthpopcan-run-v1", "status": status})
    )

    with pytest.raises(ValueError, match="successful durable run"):
        create_exchange_bundle(population, tmp_path / "exchange", run_manifest=run)


def test_exchange_rejects_incompatible_geography(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")

    with pytest.raises(ValueError, match="identifier column does not match"):
        create_exchange_bundle(
            population,
            tmp_path / "exchange",
            geography_universe=statcan_geography_universe(2021, "da", "da"),
        )


def test_exchange_rejects_source_contract_drift(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    manifest = json.loads((population / "manifest.json").read_text())
    manifest["tables"]["households"]["rows"] = 999
    (population / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="does not match its CSVs"):
        create_exchange_bundle(population, tmp_path / "exchange")


def test_exchange_rejects_bad_linkage_before_writing(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    (population / "persons.csv").write_text(
        "synthetic_person_id,synthetic_household_id,age_group\np1,missing,adult\n"
    )
    write_linked_population_contract(
        population / "manifest.json",
        population / "households.csv",
        population / "persons.csv",
        geography_column="csd",
    )

    with pytest.raises(ValueError, match="linked-population validation failed"):
        create_exchange_bundle(population, tmp_path / "exchange")
    assert not (tmp_path / "exchange").exists()


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("households.csv", b"tampered", "households SHA-256"),
        ("persons.csv", b"tampered", "persons SHA-256"),
        ("data-dictionary.json", b"{}\n", "data_dictionary SHA-256"),
        ("provenance.json", b"{}\n", "provenance SHA-256"),
        ("validation.json", b"{}\n", "validation SHA-256"),
    ],
)
def test_exchange_validation_detects_tampering(
    tmp_path: Path, filename: str, contents: bytes, message: str
) -> None:
    population = _population(tmp_path / "population")
    create_exchange_bundle(population, tmp_path / "exchange")
    (tmp_path / "exchange" / filename).write_bytes(contents)

    report = validate_exchange_bundle(tmp_path / "exchange")

    assert report["passed"] is False
    assert any(message in issue for issue in report["issues"])


def test_exchange_validation_rejects_missing_and_extra_files(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"
    create_exchange_bundle(population, output)
    (output / "persons.csv").unlink()
    (output / "surprise.txt").write_text("not declared")

    report = validate_exchange_bundle(output)

    assert report["passed"] is False
    assert "unexpected bundle files: surprise.txt" in report["issues"]
    assert "missing bundle files: persons.csv" in report["issues"]


def test_exchange_manifest_reader_is_strict(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    bundle = create_exchange_bundle(population, tmp_path / "exchange")
    payload = json.loads(bundle.manifest.read_text())
    payload["unexpected"] = True
    bundle.manifest.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="invalid exchange manifest"):
        read_exchange_manifest(bundle.manifest)


def test_exchange_refuses_alias_existing_and_invalid_governance(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(ValueError, match="must not be the source"):
        create_exchange_bundle(population, population)
    with pytest.raises(FileExistsError, match="already exists"):
        create_exchange_bundle(population, existing)
    with pytest.raises(ValueError, match="access classification"):
        create_exchange_bundle(
            population, tmp_path / "bad-access", access_classification="open"
        )
    with pytest.raises(ValueError, match="redistribution status"):
        create_exchange_bundle(
            population, tmp_path / "bad-redistribution", redistribution_status="maybe"
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"limitations": ("",)}, "limitations"),
        ({"temporal_coverage": {"start": ""}}, "temporal coverage"),
        (
            {"geography_universe": {"schema_version": "old"}},
            "unsupported geography universe",
        ),
    ],
)
def test_exchange_rejects_invalid_optional_metadata(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    population = _population(tmp_path / "population")

    with pytest.raises(ValueError, match=message):
        create_exchange_bundle(population, tmp_path / "exchange", **kwargs)  # type: ignore[arg-type]


def test_exchange_rejects_missing_population_and_csvs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="directory not found"):
        create_exchange_bundle(tmp_path / "missing", tmp_path / "exchange")

    population = tmp_path / "population"
    population.mkdir()
    (population / "households.csv").write_text("synthetic_household_id\nh1\n")
    with pytest.raises(FileNotFoundError, match="person CSV"):
        create_exchange_bundle(population, tmp_path / "exchange")


def test_exchange_builds_descriptor_when_source_manifest_is_absent(
    tmp_path: Path,
) -> None:
    population = _population(tmp_path / "population")
    (population / "manifest.json").unlink()

    bundle = create_exchange_bundle(population, tmp_path / "exchange")

    provenance = json.loads(bundle.provenance.read_text())
    assert provenance["origin"]["linked_population_manifest_sha256"] is None


@pytest.mark.parametrize("contents", ["[]", "{}", '{"schema_version":"other"}'])
def test_exchange_rejects_invalid_source_manifests(
    tmp_path: Path, contents: str
) -> None:
    population = _population(tmp_path / "population")
    (population / "manifest.json").write_text(contents)

    with pytest.raises(ValueError):
        create_exchange_bundle(population, tmp_path / "exchange")


def test_exchange_rejects_wrong_run_schema(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    run = tmp_path / "run.json"
    run.write_text('{"schema_version":"old","status":"succeeded"}')

    with pytest.raises(ValueError, match="must use synthpopcan-run-v1"):
        create_exchange_bundle(population, tmp_path / "exchange", run_manifest=run)


def test_exchange_rejects_incomplete_successful_run_manifest(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    run = tmp_path / "run.json"
    run.write_text(
        json.dumps({"schema_version": "synthpopcan-run-v1", "status": "succeeded"})
    )

    with pytest.raises(ValueError, match="invalid durable-run manifest"):
        create_exchange_bundle(population, tmp_path / "exchange", run_manifest=run)


def test_exchange_rejects_empty_reproduction_request(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")

    with pytest.raises(ValueError, match="must not be empty"):
        create_exchange_bundle(
            population,
            tmp_path / "exchange",
            reproduction={},
        )


def test_exchange_rejects_non_json_reproduction_request(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")

    with pytest.raises(ValueError, match="JSON serializable"):
        create_exchange_bundle(
            population,
            tmp_path / "exchange",
            reproduction={"interface": "python", "path": tmp_path},
        )


def test_exchange_requires_geography_column_and_values(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    contract = json.loads((population / "manifest.json").read_text())
    contract["geography"] = None
    (population / "manifest.json").write_text(json.dumps(contract))
    geography = statcan_geography_universe(2021, "csd", "csd")

    with pytest.raises(ValueError, match="requires a household geography column"):
        create_exchange_bundle(
            population, tmp_path / "missing-context", geography_universe=geography
        )

    empty_population = _population(tmp_path / "empty-value")
    empty_households = empty_population / "households.csv"
    empty_households.write_text(
        "synthetic_household_id,household_size,csd,weight,note\nh1,1,,1,empty\n"
    )
    write_linked_population_contract(
        empty_population / "manifest.json",
        empty_households,
        empty_population / "persons.csv",
        geography_column="csd",
    )
    with pytest.raises(ValueError, match="identifier is empty"):
        create_exchange_bundle(
            empty_population,
            tmp_path / "empty-output",
            geography_universe=geography,
        )


def test_exchange_validates_declared_dguid(tmp_path: Path) -> None:
    population = _population(tmp_path / "population")
    universe = statcan_geography_universe(
        2021,
        "csd",
        "csd",
        dguid_column="DGUID",
    )

    with pytest.raises(ValueError, match="geography columns are missing"):
        create_exchange_bundle(
            population, tmp_path / "missing-dguid", geography_universe=universe
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("remove-record", "exactly the required"),
        ("wrong-path", "households path must"),
        ("wrong-media", "households media type"),
        ("wrong-size", "households byte size"),
        ("wrong-rows", "households row count"),
        ("relationships", "exchange relationships"),
    ],
)
def test_exchange_validation_detects_manifest_metadata_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"
    create_exchange_bundle(population, output)
    manifest = json.loads((output / "manifest.json").read_text())
    households = next(
        item for item in manifest["files"] if item["logical_name"] == "households"
    )
    if mutation == "remove-record":
        manifest["files"].pop()
    elif mutation == "wrong-path":
        households["path"] = "household-data.csv"
    elif mutation == "wrong-media":
        households["media_type"] = "application/json"
    elif mutation == "wrong-size":
        households["byte_size"] += 1
    elif mutation == "wrong-rows":
        households["row_count"] += 1
    else:
        manifest["relationships"] = []
    (output / "manifest.json").write_text(json.dumps(manifest))

    report = validate_exchange_bundle(output)

    assert report["passed"] is False
    assert any(message in issue for issue in report["issues"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("dictionary-schema", "invalid data dictionary"),
        ("dictionary-format", "invalid data dictionary"),
        ("dictionary-tables", "invalid data dictionary"),
        ("dictionary-names", "describe households and persons"),
        ("dictionary-columns", "dictionary columns do not match"),
        ("provenance-schema", "invalid provenance"),
        ("provenance-reproduction", "invalid provenance"),
        ("validation-schema", "invalid stored validation"),
        ("validation-passed", "invalid stored validation"),
        ("validation-reproduction", "invalid stored validation"),
    ],
)
def test_exchange_validation_rejects_semantic_metadata_drift(
    tmp_path: Path, mutation: str, message: str
) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"
    create_exchange_bundle(population, output)
    if mutation.startswith("dictionary"):
        path = output / "data-dictionary.json"
    elif mutation.startswith("provenance"):
        path = output / "provenance.json"
    else:
        path = output / "validation.json"
    payload = json.loads(path.read_text())
    if mutation == "dictionary-schema":
        payload["schema_version"] = "old"
    elif mutation == "dictionary-format":
        payload["format"] = "parquet"
    elif mutation == "dictionary-tables":
        payload["tables"] = {}
    elif mutation == "dictionary-names":
        payload["tables"].pop()
    elif mutation == "dictionary-columns":
        payload["tables"][0]["columns"].pop()
    elif mutation == "provenance-schema":
        payload["schema_version"] = "old"
    elif mutation == "provenance-reproduction":
        payload["reproduction"] = None
    elif mutation == "validation-schema":
        payload["schema_version"] = "old"
    elif mutation == "validation-passed":
        payload["passed"] = False
    else:
        payload["reproduction"] = None
    path.write_text(json.dumps(payload))

    report = validate_exchange_bundle(output)

    assert report["passed"] is False
    assert any(message in issue for issue in report["issues"])


@pytest.mark.parametrize(
    ("origin", "message"),
    [
        ({"kind": "unknown"}, "unsupported provenance origin"),
        (
            {
                "kind": "standalone-linked-population",
                "linked_population_manifest_sha256": "bad",
            },
            "standalone provenance manifest hash is invalid",
        ),
        (
            {"kind": "durable-run", "run_manifest_sha256": "bad"},
            "durable-run provenance is incomplete",
        ),
    ],
)
def test_exchange_validation_rejects_invalid_provenance_origins(
    tmp_path: Path, origin: dict[str, str], message: str
) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"
    create_exchange_bundle(population, output)
    path = output / "provenance.json"
    payload = json.loads(path.read_text())
    payload["origin"] = origin
    path.write_text(json.dumps(payload))

    report = validate_exchange_bundle(output)

    assert report["passed"] is False
    assert any(message in issue for issue in report["issues"])


@pytest.mark.parametrize("filename", ["data-dictionary.json", "validation.json"])
def test_exchange_validation_rejects_extra_metadata_fields(
    tmp_path: Path, filename: str
) -> None:
    population = _population(tmp_path / "population")
    output = tmp_path / "exchange"
    create_exchange_bundle(population, output)
    path = output / filename
    payload = json.loads(path.read_text())
    payload["undeclared"] = True
    path.write_text(json.dumps(payload))

    report = validate_exchange_bundle(output)

    assert report["passed"] is False
    assert any("Extra inputs are not permitted" in issue for issue in report["issues"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate-name", "logical names must be unique"),
        ("duplicate-path", "paths must be unique"),
        ("unsafe-path", "paths must be filenames"),
        ("bad-sha", "SHA-256 values are invalid"),
    ],
)
def test_exchange_manifest_rejects_unsafe_file_records(
    tmp_path: Path, mutation: str, message: str
) -> None:
    population = _population(tmp_path / "population")
    bundle = create_exchange_bundle(population, tmp_path / "exchange")
    manifest = json.loads(bundle.manifest.read_text())
    first, second = manifest["files"][:2]
    if mutation == "duplicate-name":
        second["logical_name"] = first["logical_name"]
    elif mutation == "duplicate-path":
        second["path"] = first["path"]
    elif mutation == "unsafe-path":
        first["path"] = "../households.csv"
    else:
        first["sha256"] = "nope"
    bundle.manifest.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match=message):
        read_exchange_manifest(bundle.manifest)


@pytest.mark.parametrize("contents", ["{", "[]"])
def test_exchange_manifest_reader_rejects_bad_json_documents(
    tmp_path: Path, contents: str
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(contents)

    with pytest.raises(ValueError):
        read_exchange_manifest(manifest)


def test_exchange_validator_reports_missing_manifest(tmp_path: Path) -> None:
    report = validate_exchange_bundle(tmp_path)

    assert report["passed"] is False
    assert report["checks"] == {}


def test_exchange_cleans_temporary_output_after_internal_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    population = _population(tmp_path / "population")
    monkeypatch.setattr(
        exchange,
        "validate_exchange_bundle",
        lambda _path: {"passed": False, "issues": ["forced failure"]},
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        create_exchange_bundle(population, tmp_path / "exchange")
    assert not (tmp_path / "exchange").exists()
    assert not list(tmp_path.glob(".exchange-*"))


def _population(directory: Path, *, missing: bool = False) -> Path:
    directory.mkdir()
    households = directory / "households.csv"
    persons = directory / "persons.csv"
    households.write_text(
        "synthetic_household_id,household_size,csd,weight,note\n"
        f"h1,2,2466023,1,{' ' if not missing else ''}\n"
        "h2,1,2466023,1,complete\n"
    )
    persons.write_text(
        "synthetic_person_id,synthetic_household_id,age_group\n"
        "p1,h1,adult\n"
        "p2,h1,child\n"
        "p3,h2,adult\n"
    )
    write_linked_population_contract(
        directory / "manifest.json",
        households,
        persons,
        geography_column="csd",
    )
    return directory


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
