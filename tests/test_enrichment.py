from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

import synthpopcan as spc
import synthpopcan.enrichment as enrichment_module
from synthpopcan.cli import cli
from synthpopcan.enrichment import (
    EnrichmentLayer,
    EnrichmentManifest,
    ResourceRecord,
    SourceProfile,
    acquire_public_resource,
    build_enrichment_manifest,
    import_normalized_layer,
    read_enrichment_manifest,
    register_resource,
    validate_normalized_layer,
    verify_enrichment_manifest,
    write_enrichment_manifest,
)
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.linked_schema import write_linked_population_contract


def _source(*, acquisition_mode: str = "public-download") -> SourceProfile:
    return SourceProfile(
        source_id="example.area-context.v1",
        publisher_id="example.publisher",
        titles={"en": "Example area context", "fr": "Contexte régional exemple"},
        descriptions={
            "en": "Synthetic fixture for contract tests.",
            "fr": "Données synthétiques pour les essais de contrat.",
        },
        canonical_url="https://example.invalid/dataset",
        acquisition_mode=acquisition_mode,
        authority="Synthetic public fixture created by the project.",
        licence_id="CC0-1.0",
        source_version="2026-07",
        publication_date="2026-07-01",
        observation_period={"start": "2026-01-01", "end": "2026-06-30"},
        unit_of_observation="2021 dissemination area",
        access_classification=(
            "public" if acquisition_mode == "public-download" else "restricted"
        ),
        redistribution_status="Synthetic fixture may be redistributed.",
        geography=statcan_geography_universe(2021, "da", "DAUID"),
        translation_provenance={
            "en": "authoritative",
            "fr": "project-supplied synthetic translation",
        },
        known_limitations=("Not real-world research data.",),
    )


def _linked_population(directory: Path) -> tuple[Path, Path, Path]:
    households = directory / "households.csv"
    persons = directory / "persons.csv"
    manifest = directory / "manifest.json"
    households.write_text("synthetic_household_id,DAUID\nh1,24660244\nh2,24660245\n")
    persons.write_text("synthetic_person_id,synthetic_household_id\np1,h1\np2,h2\n")
    write_linked_population_contract(
        manifest,
        households,
        persons,
        geography_column="DAUID",
    )
    return households, persons, manifest


def _layer(
    path: Path, source: SourceProfile, resource: ResourceRecord
) -> EnrichmentLayer:
    contents = (
        "DAUID,food_environment\n24660244,higher-density\n24660245,lower-density\n"
    )
    path.write_text(contents)
    return EnrichmentLayer(
        layer_id="example.area-context.normalized.v1",
        layer_class="area-attributes",
        table_path=path.name,
        sha256=hashlib.sha256(contents.encode()).hexdigest(),
        row_count=2,
        key_columns=("DAUID",),
        variables=("food_environment",),
        source_id=source.source_id,
        resource_id=resource.resource_id,
        observed_status="observed",
        geography=source.geography,
    )


def test_source_profile_round_trips_bilingual_authority_metadata() -> None:
    source = _source()

    assert SourceProfile.from_dict(source.as_dict()) == source
    assert source.as_dict()["titles"] == {
        "en": "Example area context",
        "fr": "Contexte régional exemple",
    }


def test_restricted_resource_registration_never_exposes_local_path(
    tmp_path: Path,
) -> None:
    private = tmp_path / "data" / "private" / "source.csv"
    private.parent.mkdir(parents=True)
    private.write_text("secret\nvalue\n")

    resource = register_resource(
        private,
        _source(acquisition_mode="restricted"),
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=str(private),
    )

    payload = resource.as_dict()
    assert payload["public_locator"] is None
    assert payload["opaque_local_id"].startswith("local:")
    assert str(private) not in json.dumps(payload)
    assert ResourceRecord.from_dict(payload) == resource


def test_public_acquisition_is_bounded_atomic_and_content_addressed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contents = b"DAUID,value\n001,a\n"

    class Response:
        headers = {"Content-Length": str(len(contents))}

        def __init__(self) -> None:
            self._read = False

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            del size
            if self._read:
                return b""
            self._read = True
            return contents

    monkeypatch.setattr(
        enrichment_module,
        "urlopen",
        lambda *args, **kwargs: Response(),
    )
    expected = hashlib.sha256(contents).hexdigest()

    first_path, first_record = acquire_public_resource(
        _source(),
        tmp_path / "cache",
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        max_bytes=len(contents),
        publisher_sha256=expected,
    )
    second_path, second_record = acquire_public_resource(
        _source(),
        tmp_path / "cache",
        acquired_at="2026-07-29T12:01:00Z",
        media_type="text/csv",
        max_bytes=len(contents),
    )

    assert first_path == second_path
    assert first_path.read_bytes() == contents
    assert first_record.resource_id == second_record.resource_id
    assert first_record.publisher_checksum == f"sha256:{expected}"
    assert not list((tmp_path / "cache").glob("*.part"))

    with pytest.raises(ValueError, match="size limit"):
        acquire_public_resource(
            _source(),
            tmp_path / "cache",
            acquired_at="2026-07-29T12:02:00Z",
            media_type="text/csv",
            max_bytes=len(contents) - 1,
        )


def test_layer_validation_reports_coverage_without_person_level_claims(
    tmp_path: Path,
) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    layer_path = tmp_path / "area-context.csv"
    layer = _layer(layer_path, source, resource)

    report = validate_normalized_layer(
        layer_path,
        layer,
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        base_identifiers=("24660244", "24660246"),
    )

    assert report["passed"] is True
    assert report["unmatched_layer_identifiers"] == ["24660245"]
    assert report["unmatched_base_identifiers"] == ["24660246"]


def test_facility_layer_uses_stable_facility_keys_and_keeps_coordinates(
    tmp_path: Path,
) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    facilities = tmp_path / "facilities.csv"
    facilities.write_text(
        "facility_id,DAUID,facility_type,latitude,longitude\n"
        "school-1,24660244,school,45.50,-73.57\n"
        "clinic-1,24660244,clinic,45.51,-73.58\n"
    )

    layer = enrichment_module.build_enrichment_layer(
        facilities,
        layer_id="example.facilities.normalized.v1",
        layer_class="facilities-points",
        key_columns=("facility_id",),
        variables=("DAUID", "facility_type", "latitude", "longitude"),
        source=source,
        resource=resource,
        observed_status="observed",
        geography=source.geography,
    )
    report = validate_normalized_layer(
        facilities,
        layer,
        base_geography=source.geography,
        base_identifiers=("24660244",),
    )

    assert report["passed"] is True
    assert report["unmatched_layer_identifiers"] == []
    assert layer.key_columns == ("facility_id",)
    assert layer.layer_class == "facilities-points"


def test_layer_validation_rejects_cross_vintage_and_duplicate_keys(
    tmp_path: Path,
) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    layer_path = tmp_path / "area-context.csv"
    layer_path.write_text("DAUID,value\n001,a\n001,b\n")
    layer = EnrichmentLayer(
        layer_id="example.duplicate.v1",
        layer_class="area-attributes",
        table_path=layer_path.name,
        sha256=hashlib.sha256(layer_path.read_bytes()).hexdigest(),
        row_count=2,
        key_columns=("DAUID",),
        variables=("value",),
        source_id=source.source_id,
        resource_id=resource.resource_id,
        observed_status="observed",
        geography=source.geography,
    )

    report = validate_normalized_layer(
        layer_path,
        layer,
        base_geography=statcan_geography_universe(2016, "da", "DAUID"),
        base_identifiers=("001",),
    )

    assert report["passed"] is False
    assert {issue["code"] for issue in report["issues"]} == {
        "duplicate-keys",
        "incompatible-geography-universe",
    }


def test_manifest_composes_sidecars_without_mutating_base_population(
    tmp_path: Path,
) -> None:
    households, persons, linked_manifest = _linked_population(tmp_path)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    layer = _layer(tmp_path / "area-context.csv", source, resource)
    before = {
        path.name: path.read_bytes() for path in (households, persons, linked_manifest)
    }

    enrichment = build_enrichment_manifest(
        households,
        persons,
        linked_population_manifest_path=linked_manifest,
        sources=(source,),
        resources=(resource,),
        layers=(layer,),
        reproduction_request={
            "workflow": "enrichment",
            "operation": "import-normalized-layer",
        },
        limitations=("Area context is not person-level exposure.",),
    )
    write_enrichment_manifest(tmp_path / "enrichment-manifest.json", enrichment)

    assert EnrichmentManifest.from_dict(enrichment.as_dict()) == enrichment
    assert {
        path.name: path.read_bytes() for path in (households, persons, linked_manifest)
    } == before
    assert verify_enrichment_manifest(enrichment, tmp_path) == {
        "schema_version": "synthpopcan-enrichment-verification-v1",
        "passed": True,
        "base_population_unchanged": True,
        "issues": [],
    }

    households.write_text(households.read_text() + "h3,24660246\n")
    verification = verify_enrichment_manifest(enrichment, tmp_path)
    assert verification["passed"] is False
    assert verification["base_population_unchanged"] is False


@pytest.mark.scenario("SCN-ENRICH-001")
def test_generic_import_publishes_only_sidecars_and_reuses_shared_contracts(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    households, persons, linked_manifest = _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    normalized = tmp_path / "area-context.csv"
    _layer(normalized, source, resource)
    before = {
        path.name: path.read_bytes() for path in (households, persons, linked_manifest)
    }

    manifest, validation = import_normalized_layer(
        population,
        normalized,
        tmp_path / "enrichment",
        source=source,
        resource=resource,
        layer_id="example.area-context.normalized.v1",
        layer_class="area-attributes",
        key_columns=("DAUID",),
        variables=("food_environment",),
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        limitations=("Area values are not person-level exposure.",),
    )

    assert validation["passed"] is True
    assert (tmp_path / "enrichment" / "area-context.csv").is_file()
    assert (
        read_enrichment_manifest(tmp_path / "enrichment" / "manifest.json") == manifest
    )
    assert {
        path.name: path.read_bytes() for path in (households, persons, linked_manifest)
    } == before
    assert (
        verify_enrichment_manifest(
            manifest,
            tmp_path / "enrichment",
            base_directory=population,
        )["passed"]
        is True
    )


def test_cli_imports_and_revalidates_researcher_supplied_layer(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    source_path = tmp_path / "source-profile.json"
    source_path.write_text(json.dumps(source.as_dict()))
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    resource_path = tmp_path / "resource-record.json"
    resource_path.write_text(json.dumps(resource.as_dict()))
    normalized = tmp_path / "area-context.csv"
    _layer(normalized, source, resource)
    output = tmp_path / "enrichment"
    runner = CliRunner()

    imported = runner.invoke(
        cli,
        [
            "enrich",
            "import",
            str(population),
            str(normalized),
            "--source-profile",
            str(source_path),
            "--resource-record",
            str(resource_path),
            "--layer-id",
            "example.area-context.normalized.v1",
            "--layer-class",
            "area-attributes",
            "--key-column",
            "DAUID",
            "--variable",
            "food_environment",
            "--base-census-vintage",
            "2021",
            "--base-geo-level",
            "da",
            "--base-geo-namespace",
            "statcan:census:2021:da",
            "--base-geo-column",
            "DAUID",
            "--limitation",
            "Area context is not person-level exposure.",
            "--out",
            str(output),
        ],
    )

    assert imported.exit_code == 0, imported.output
    assert "base population was not modified" in imported.output
    verified = runner.invoke(
        cli,
        [
            "enrich",
            "validate",
            str(output / "manifest.json"),
            "--population",
            str(population),
        ],
    )
    assert verified.exit_code == 0, verified.output
    assert "hashes are valid" in verified.output


def test_beginner_api_imports_normalized_layer(tmp_path: Path) -> None:
    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    normalized = tmp_path / "area-context.csv"
    _layer(normalized, source, resource)

    result = spc.enrich_population(
        spc.LinkedPopulationFiles(
            households=population / "households.csv",
            persons=population / "persons.csv",
            manifest=population / "manifest.json",
        ),
        normalized,
        source_profile=source,
        resource_record=resource,
        layer_id="example.area-context.normalized.v1",
        layer_class="area-attributes",
        key_columns=("DAUID",),
        variables=("food_environment",),
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        output_dir=tmp_path / "enrichment",
    )

    assert isinstance(result, spc.EnrichmentResult)
    assert result.validation["passed"] is True
    assert result.layer.is_file()
    assert result.manifest.is_file()

    path_result = spc.enrich_population(
        population,
        normalized,
        source_profile=source,
        resource_record=resource,
        layer_id="example.area-context.path-input.v1",
        layer_class="area-attributes",
        key_columns=("DAUID",),
        variables=("food_environment",),
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        output_dir=tmp_path / "enrichment-path-input",
    )
    assert path_result.validation["passed"] is True


def test_generic_import_rejects_unreviewed_cross_vintage_join(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    normalized = tmp_path / "area-context.csv"
    _layer(normalized, source, resource)

    with pytest.raises(ValueError, match="incompatible-geography-universe"):
        import_normalized_layer(
            population,
            normalized,
            tmp_path / "enrichment",
            source=source,
            resource=resource,
            layer_id="example.area-context.normalized.v1",
            layer_class="area-attributes",
            key_columns=("DAUID",),
            variables=("food_environment",),
            base_geography=statcan_geography_universe(2016, "da", "DAUID"),
        )


def test_manifest_rejects_unknown_resource_lineage(tmp_path: Path) -> None:
    households, persons, linked_manifest = _linked_population(tmp_path)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("source\nfixture\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator=source.canonical_url,
    )
    layer = _layer(tmp_path / "area-context.csv", source, resource)
    invalid = EnrichmentLayer(
        **{
            **layer.__dict__,
            "resource_id": "resource:" + "0" * 64,
        }
    )

    with pytest.raises(ValueError, match="resource lineage"):
        build_enrichment_manifest(
            households,
            persons,
            linked_population_manifest_path=linked_manifest,
            sources=(source,),
            resources=(resource,),
            layers=(invalid,),
            reproduction_request={},
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"source_id": "Bad ID"}, "stable identifier"),
        ({"titles": {}}, "English and/or French"),
        ({"titles": {"de": "Titel"}}, "English and/or French"),
        ({"canonical_url": " url "}, "trimmed"),
        ({"acquisition_mode": "unknown"}, "acquisition_mode"),
        ({"access_classification": "unknown"}, "access_classification"),
        (
            {"access_classification": "restricted"},
            "public acquisition requires public",
        ),
        (
            {
                "acquisition_mode": "licensed",
                "access_classification": "restricted",
            },
            "matching access",
        ),
        ({"observation_period": {"start": " bad "}}, "string-to-string"),
        ({"translation_provenance": {"fr": " bad "}}, "string-to-string"),
        ({"known_limitations": (" bad ",)}, "trimmed"),
    ],
)
def test_source_profile_rejects_invalid_governance_metadata(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_source(), **updates)


def test_source_profile_payload_validation_paths() -> None:
    payload = _source().as_dict()
    with pytest.raises(ValueError, match="unsupported source profile"):
        SourceProfile.from_dict({})
    with pytest.raises(ValueError, match="known_limitations"):
        SourceProfile.from_dict({**payload, "known_limitations": [1]})
    with pytest.raises(ValueError, match="geography must be an object"):
        SourceProfile.from_dict({**payload, "geography": []})
    with pytest.raises(ValueError, match="titles must be an object"):
        SourceProfile.from_dict({**payload, "titles": []})
    with pytest.raises(ValueError, match="descriptions must be a string-to-string"):
        SourceProfile.from_dict({**payload, "descriptions": {"en": 1}})


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"resource_id": "Bad ID"}, "stable identifier"),
        ({"source_version": ""}, "non-empty"),
        ({"acquisition_mode": "unknown"}, "acquisition_mode"),
        ({"byte_size": -1}, "non-negative"),
        ({"sha256": "bad"}, "SHA-256"),
        ({"status": "unknown"}, "status"),
        ({"public_locator": None}, "require public_locator"),
        ({"opaque_local_id": "Bad ID"}, "stable identifier"),
        ({"publisher_checksum": ""}, "non-empty"),
        ({"derived_from": ("Bad ID",)}, "stable identifier"),
    ],
)
def test_resource_record_rejects_invalid_revision_metadata(
    tmp_path: Path,
    updates: dict[str, object],
    message: str,
) -> None:
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        _source(),
        acquired_at="2026-07-29T12:00:00Z",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    with pytest.raises(ValueError, match=message):
        replace(resource, **updates)


def test_non_public_resource_requires_opaque_identity() -> None:
    with pytest.raises(ValueError, match="opaque_local_id"):
        ResourceRecord(
            resource_id="resource:" + "a" * 64,
            source_id="example.source",
            source_version="1",
            acquisition_mode="restricted",
            acquired_at="2026-07-29",
            media_type="text/csv",
            byte_size=1,
            sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="cannot expose"):
        ResourceRecord(
            resource_id="resource:" + "a" * 64,
            source_id="example.source",
            source_version="1",
            acquisition_mode="restricted",
            acquired_at="2026-07-29",
            media_type="text/csv",
            byte_size=1,
            sha256="a" * 64,
            public_locator="https://example.invalid",
            opaque_local_id="local:a",
        )


def test_resource_payload_validation_paths(tmp_path: Path) -> None:
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        _source(),
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    payload = resource.as_dict()
    with pytest.raises(ValueError, match="unsupported resource"):
        ResourceRecord.from_dict({})
    with pytest.raises(ValueError, match="byte_size must be an integer"):
        ResourceRecord.from_dict({**payload, "byte_size": True})
    with pytest.raises(ValueError, match="derived_from"):
        ResourceRecord.from_dict({**payload, "derived_from": [1]})
    with pytest.raises(ValueError, match="string or null"):
        ResourceRecord.from_dict({**payload, "publisher_checksum": 1})


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"layer_class": "unknown"}, "layer class"),
        ({"table_path": "../layer.csv"}, "filename"),
        ({"row_count": -1}, "non-negative"),
        ({"key_columns": ()}, "non-empty"),
        ({"key_columns": ("id", "id")}, "unique"),
        ({"variables": ("value", "value")}, "unique"),
        ({"variables": ("DAUID",)}, "distinct"),
        ({"observed_status": "guessed"}, "observed_status"),
    ],
)
def test_enrichment_layer_rejects_invalid_schema(
    tmp_path: Path,
    updates: dict[str, object],
    message: str,
) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    layer = _layer(tmp_path / "layer.csv", source, resource)
    with pytest.raises(ValueError, match=message):
        replace(layer, **updates)


def test_enrichment_layer_payload_validation_paths(
    tmp_path: Path,
) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    payload = _layer(tmp_path / "layer.csv", source, resource).as_dict()
    with pytest.raises(ValueError, match="unsupported enrichment layer"):
        EnrichmentLayer.from_dict({})
    with pytest.raises(ValueError, match="requires CSV"):
        EnrichmentLayer.from_dict({**payload, "media_type": "application/json"})
    with pytest.raises(ValueError, match="row_count must be an integer"):
        EnrichmentLayer.from_dict({**payload, "row_count": True})
    with pytest.raises(ValueError, match="key_columns must be a list"):
        EnrichmentLayer.from_dict({**payload, "key_columns": "DAUID"})


def test_layer_validation_accumulates_structural_issues(tmp_path: Path) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    path = tmp_path / "broken.csv"
    path.write_text("DAUID\n\n001\n")
    layer = EnrichmentLayer(
        layer_id="example.broken",
        layer_class="area-attributes",
        table_path=path.name,
        sha256="0" * 64,
        row_count=9,
        key_columns=("DAUID",),
        variables=("missing",),
        source_id=source.source_id,
        resource_id=resource.resource_id,
        observed_status="observed",
        geography=None,
    )
    report = validate_normalized_layer(
        path,
        layer,
        base_geography=source.geography,
        base_identifiers=("001",),
    )
    assert {issue["code"] for issue in report["issues"]} >= {
        "checksum-mismatch",
        "missing-columns",
        "row-count-mismatch",
        "missing-geography-context",
    }


def test_build_layer_rejects_empty_missing_and_wrong_lineage(tmp_path: Path) -> None:
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(ValueError, match="empty"):
        enrichment_module.build_enrichment_layer(
            empty,
            layer_id="example.layer",
            layer_class="area-attributes",
            key_columns=("id",),
            variables=(),
            source=source,
            resource=resource,
            observed_status="observed",
        )
    missing = tmp_path / "missing.csv"
    missing.write_text("id\n1\n")
    with pytest.raises(ValueError, match="missing columns"):
        enrichment_module.build_enrichment_layer(
            missing,
            layer_id="example.layer",
            layer_class="area-attributes",
            key_columns=("id",),
            variables=("value",),
            source=source,
            resource=resource,
            observed_status="observed",
        )
    with pytest.raises(ValueError, match="share source_id"):
        enrichment_module.build_enrichment_layer(
            missing,
            layer_id="example.layer",
            layer_class="area-attributes",
            key_columns=("id",),
            variables=(),
            source=replace(source, source_id="other.source"),
            resource=resource,
            observed_status="observed",
        )


def test_geography_import_requires_explicit_matching_base_context(
    tmp_path: Path,
) -> None:
    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    layer = tmp_path / "layer.csv"
    _layer(layer, source, resource)
    kwargs = {
        "source": source,
        "resource": resource,
        "layer_id": "example.layer",
        "layer_class": "area-attributes",
        "key_columns": ("DAUID",),
        "variables": ("food_environment",),
    }
    with pytest.raises(ValueError, match="base_geography is required"):
        import_normalized_layer(
            population,
            layer,
            tmp_path / "out",
            **kwargs,
        )
    with pytest.raises(ValueError, match="identifier column"):
        import_normalized_layer(
            population,
            layer,
            tmp_path / "out",
            base_geography=statcan_geography_universe(2021, "da", "other"),
            **kwargs,
        )


def test_readers_and_verifier_report_invalid_or_missing_files(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{")
    with pytest.raises(ValueError, match="not valid JSON"):
        enrichment_module.read_source_profile(invalid)
    invalid.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        enrichment_module.read_resource_record(invalid)


def test_cli_registers_restricted_resource_without_path_disclosure(
    tmp_path: Path,
) -> None:
    source = _source(acquisition_mode="restricted")
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source.as_dict()))
    private = tmp_path / "private.csv"
    private.write_text("secret\nvalue\n")
    output = tmp_path / "resource.json"

    result = CliRunner().invoke(
        cli,
        [
            "enrich",
            "register-resource",
            str(private),
            "--source-profile",
            str(source_path),
            "--acquired-at",
            "2026-07-29T12:00:00Z",
            "--media-type",
            "text/csv",
            "--out",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert str(private) not in output.read_text()


def test_cli_enrichment_reports_bad_files_and_partial_geography(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    missing = runner.invoke(
        cli,
        [
            "enrich",
            "register-resource",
            str(tmp_path / "missing.csv"),
            "--source-profile",
            str(tmp_path / "missing-source.json"),
            "--acquired-at",
            "2026-07-29",
            "--media-type",
            "text/csv",
            "--out",
            str(tmp_path / "resource.json"),
        ],
    )
    assert missing.exit_code != 0

    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source.as_dict()))
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    resource_path = tmp_path / "resource.json"
    resource_path.write_text(json.dumps(resource.as_dict()))
    layer = tmp_path / "layer.csv"
    _layer(layer, source, resource)
    partial = runner.invoke(
        cli,
        [
            "enrich",
            "import",
            str(population),
            str(layer),
            "--source-profile",
            str(source_path),
            "--resource-record",
            str(resource_path),
            "--layer-id",
            "example.layer",
            "--layer-class",
            "area-attributes",
            "--key-column",
            "DAUID",
            "--base-census-vintage",
            "2021",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert partial.exit_code != 0
    assert "provided together" in partial.output


def test_cli_validate_reports_corrupted_layer(tmp_path: Path) -> None:
    population = tmp_path / "population"
    population.mkdir()
    _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    layer = tmp_path / "layer.csv"
    _layer(layer, source, resource)
    output = tmp_path / "enrichment"
    import_normalized_layer(
        population,
        layer,
        output,
        source=source,
        resource=resource,
        layer_id="example.layer",
        layer_class="area-attributes",
        key_columns=("DAUID",),
        variables=("food_environment",),
        base_geography=source.geography,
    )
    (output / "layer.csv").write_text("changed\n")

    result = CliRunner().invoke(
        cli,
        [
            "enrich",
            "validate",
            str(output / "manifest.json"),
            "--population",
            str(population),
        ],
    )

    assert result.exit_code != 0
    assert "checksum" in result.output


def test_manifest_rejects_duplicate_and_inconsistent_composition(
    tmp_path: Path,
) -> None:
    households, persons, linked_manifest = _linked_population(tmp_path)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    layer = _layer(tmp_path / "layer.csv", source, resource)
    manifest = build_enrichment_manifest(
        households,
        persons,
        linked_population_manifest_path=linked_manifest,
        sources=(source,),
        resources=(resource,),
        layers=(layer,),
        reproduction_request={},
    )
    with pytest.raises(ValueError, match="duplicate source IDs"):
        replace(manifest, sources=(source, source))
    with pytest.raises(ValueError, match="unknown source"):
        replace(manifest, resources=(replace(resource, source_id="other.source"),))
    with pytest.raises(ValueError, match="unknown source"):
        replace(manifest, layers=(replace(layer, source_id="other.source"),))
    with pytest.raises(ValueError, match="reproduction_request"):
        replace(manifest, reproduction_request=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="limitation"):
        replace(manifest, limitations=(" bad ",))

    payload = manifest.as_dict()
    with pytest.raises(ValueError, match="unsupported enrichment manifest"):
        EnrichmentManifest.from_dict({})
    with pytest.raises(ValueError, match="must not mutate"):
        EnrichmentManifest.from_dict({**payload, "base_population_mutated": True})
    with pytest.raises(ValueError, match="sources item"):
        EnrichmentManifest.from_dict({**payload, "sources": [1]})


def test_manifest_rejects_invalid_base_population_records(
    tmp_path: Path,
) -> None:
    households, persons, linked_manifest = _linked_population(tmp_path)
    manifest = build_enrichment_manifest(
        households,
        persons,
        linked_population_manifest_path=linked_manifest,
        sources=(),
        resources=(),
        layers=(),
        reproduction_request={},
    )
    base = dict(manifest.base_population)
    with pytest.raises(ValueError, match="requires linked-population"):
        replace(manifest, base_population={**base, "linked_population_schema": "bad"})
    bad_record = dict(base["households"])
    bad_record["path"] = "../households.csv"
    with pytest.raises(ValueError, match="path must be a filename"):
        replace(manifest, base_population={**base, "households": bad_record})
    bad_record = dict(base["households"])
    bad_record["byte_size"] = -1
    with pytest.raises(ValueError, match="byte_size"):
        replace(manifest, base_population={**base, "households": bad_record})


def test_public_acquisition_rejects_invalid_policy_and_empty_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="only public"):
        acquire_public_resource(
            _source(acquisition_mode="restricted"),
            tmp_path,
            acquired_at="2026-07-29",
            media_type="text/csv",
        )
    with pytest.raises(ValueError, match="positive"):
        acquire_public_resource(
            _source(),
            tmp_path,
            acquired_at="2026-07-29",
            media_type="text/csv",
            max_bytes=0,
        )
    with pytest.raises(ValueError, match="HTTPS"):
        acquire_public_resource(
            _source(),
            tmp_path,
            acquired_at="2026-07-29",
            media_type="text/csv",
            resource_url="http://example.invalid/data",
        )
    with pytest.raises(ValueError, match="SHA-256"):
        acquire_public_resource(
            _source(),
            tmp_path,
            acquired_at="2026-07-29",
            media_type="text/csv",
            publisher_sha256="bad",
        )

    class EmptyResponse:
        headers: dict[str, str] = {}

        def __enter__(self) -> EmptyResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b""

    monkeypatch.setattr(
        enrichment_module, "urlopen", lambda *args, **kwargs: EmptyResponse()
    )
    with pytest.raises(ValueError, match="empty"):
        acquire_public_resource(
            _source(),
            tmp_path,
            acquired_at="2026-07-29",
            media_type="text/csv",
        )


def test_verifier_reports_missing_base_and_sidecar_files(tmp_path: Path) -> None:
    population = tmp_path / "population"
    population.mkdir()
    households, persons, linked_manifest = _linked_population(population)
    source = _source()
    raw = tmp_path / "raw.csv"
    raw.write_text("x\n1\n")
    resource = register_resource(
        raw,
        source,
        acquired_at="2026-07-29",
        media_type="text/csv",
        public_locator="https://example.invalid/raw.csv",
    )
    layer = _layer(tmp_path / "layer.csv", source, resource)
    manifest = build_enrichment_manifest(
        households,
        persons,
        linked_population_manifest_path=linked_manifest,
        sources=(source,),
        resources=(resource,),
        layers=(layer,),
        reproduction_request={},
    )

    report = verify_enrichment_manifest(
        manifest,
        tmp_path / "missing-layers",
        base_directory=tmp_path / "missing-base",
    )

    assert report["passed"] is False
    assert any("cannot be read" in issue for issue in report["issues"])
