from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

import synthpopcan as spc
import synthpopcan.api as api_module
import synthpopcan.canfed as canfed_module
import synthpopcan.odef as odef_module
import synthpopcan.workflows.enrichment as workflow_module
from synthpopcan.canfed import (
    CanFedAdapter,
    can_fed_source_profile,
    normalize_can_fed_archive,
)
from synthpopcan.cli import cli
from synthpopcan.enrichment import (
    ResourceRecord,
    read_enrichment_manifest,
    verify_enrichment_manifest,
)
from synthpopcan.geography import statcan_geography_universe
from synthpopcan.linked_schema import write_linked_population_contract
from synthpopcan.odef import OdefAdapter, normalize_odef_archive, odef_source_profile

_FIXTURES = Path(__file__).parent / "fixtures" / "enrichment"


def _zip_fixture(source: Path, destination: Path) -> Path:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))
    return destination


def _zip_members(destination: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return destination


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _population(
    directory: Path,
    *,
    geography_column: str | None = None,
    identifiers: tuple[str, ...] = ("A", "B"),
) -> Path:
    directory.mkdir(parents=True)
    household_columns = ["synthetic_household_id"]
    if geography_column is not None:
        household_columns.append(geography_column)
    with (directory / "households.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=household_columns)
        writer.writeheader()
        for index, identifier in enumerate(identifiers, start=1):
            row = {"synthetic_household_id": f"h{index}"}
            if geography_column is not None:
                row[geography_column] = identifier
            writer.writerow(row)
    with (directory / "persons.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["synthetic_person_id", "synthetic_household_id"],
        )
        writer.writeheader()
        for index in range(1, len(identifiers) + 1):
            writer.writerow(
                {
                    "synthetic_person_id": f"p{index}",
                    "synthetic_household_id": f"h{index}",
                }
            )
    write_linked_population_contract(
        directory / "manifest.json",
        directory / "households.csv",
        directory / "persons.csv",
        geography_column=geography_column,
    )
    return directory


def _canfed_archive(tmp_path: Path) -> Path:
    return _zip_fixture(
        _FIXTURES / "can_fed_v2",
        tmp_path / "canfed.zip",
    )


def _odef_archive(tmp_path: Path) -> Path:
    return _zip_fixture(
        _FIXTURES / "odef_v3",
        tmp_path / "odef.zip",
    )


def test_can_fed_profile_and_adapter_contract() -> None:
    source = can_fed_source_profile()
    adapter = CanFedAdapter(buffer="1km")

    assert source.source_version == "2.0-public-general-use-2024"
    assert source.geography is not None
    assert source.geography.canonical_key == (2021, "da", "statcan:census:2021:da")
    assert adapter.layer_id.endswith(".1km")
    assert adapter.layer_filename == "canfed-v2-1km.csv"
    assert len(adapter.variables) == 8
    assert adapter.reproduction_parameters() == {"buffer": "1km"}
    assert adapter.describe() == source
    assert "project-written" in source.translation_provenance["en"]
    with pytest.raises(ValueError, match="buffer must"):
        CanFedAdapter(buffer="wide")  # type: ignore[arg-type]


def test_normalize_can_fed_both_buffers(tmp_path: Path) -> None:
    archive = _canfed_archive(tmp_path)
    output = tmp_path / "normalized.csv"

    report = normalize_can_fed_archive(archive, output)

    rows = list(csv.DictReader(output.open()))
    assert report["passed"] is True
    assert report["product_rows"] == {"1km": 2, "3km": 2}
    assert report["normalized_rows"] == 2
    assert report["only_1km_dauids"] == []
    assert rows[0]["DAUID"] == "99990001"
    assert rows[0]["modified_retail_food_environment_index_class_1km"] == (
        "not_applicable"
    )
    assert rows[1]["restaurant_mix_class_1km"] == "not_applicable"
    assert rows[1]["restaurant_mix_class_3km"] == "4"


def test_normalize_can_fed_one_buffer_and_unequal_coverage(tmp_path: Path) -> None:
    fixture = _FIXTURES / "can_fed_v2" / "canfed_public_data"
    one = (fixture / "dens_thresholds_1km.csv").read_text()
    three = (
        (fixture / "dens_thresholds_3km.csv")
        .read_text()
        .replace(
            "99990002,3,2,1,0,4,3,..,4\n",
            "99990003,3,2,1,0,4,3,..,4\n",
        )
    )
    archive = _zip_members(
        tmp_path / "coverage.zip",
        {
            "nested/dens_thresholds_1km.csv": one,
            "nested/dens_thresholds_3km.csv": three,
        },
    )

    combined = normalize_can_fed_archive(archive, tmp_path / "both.csv")
    one_only = normalize_can_fed_archive(
        archive,
        tmp_path / "one.csv",
        buffer="1km",
    )

    assert combined["only_1km_dauids"] == ["99990002"]
    assert combined["only_3km_dauids"] == ["99990003"]
    assert combined["normalized_rows"] == 3
    assert combined["coverage_accounting"] == {
        "union_rows": 3,
        "intersection_rows": 1,
        "only_1km_rows": 1,
        "only_3km_rows": 1,
    }
    assert one_only["buffer_products"] == ["1km"]
    assert len(list(csv.DictReader((tmp_path / "one.csv").open()))) == 2


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("99990001", "9999000", "malformed DAuid"),
        ("99990002", "99990001", "duplicate DAuid"),
        (",0,1,2,3,4,0,..,1", ",9,1,2,3,4,0,..,1", "unsupported"),
        (",0,1,2,3,4,0,..,1", ",0,1,..,3,4,0,..,1", "unsupported"),
    ],
)
def test_can_fed_rejects_bad_rows(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    fixture = _FIXTURES / "can_fed_v2" / "canfed_public_data"
    one = (fixture / "dens_thresholds_1km.csv").read_text().replace(old, new, 1)
    archive = _zip_members(
        tmp_path / "bad.zip",
        {"dens_thresholds_1km.csv": one},
    )
    with pytest.raises(ValueError, match=message):
        normalize_can_fed_archive(
            archive,
            tmp_path / "out.csv",
            buffer="1km",
        )


def test_can_fed_rejects_bad_archive_shape(tmp_path: Path) -> None:
    bad_header = "DAuid,wrong\n99990001,0\n"
    archive = _zip_members(
        tmp_path / "shape.zip",
        {"dens_thresholds_1km.csv": bad_header},
    )
    with pytest.raises(ValueError, match="columns"):
        normalize_can_fed_archive(archive, tmp_path / "out.csv", buffer="1km")
    with pytest.raises(ValueError, match="valid ZIP"):
        normalize_can_fed_archive(
            _write_text(tmp_path / "not.zip", "not a zip"),
            tmp_path / "out.csv",
        )
    with pytest.raises(ValueError, match="must contain"):
        normalize_can_fed_archive(
            _zip_members(tmp_path / "empty.zip", {"other.csv": "a\n"}),
            tmp_path / "out.csv",
            buffer="1km",
        )
    header = _FIXTURES / "can_fed_v2" / "canfed_public_data" / "dens_thresholds_1km.csv"
    header = header.read_text().splitlines()[0] + "\n"
    with pytest.raises(ValueError, match="product is empty"):
        normalize_can_fed_archive(
            _zip_members(
                tmp_path / "empty-product.zip",
                {"dens_thresholds_1km.csv": header},
            ),
            tmp_path / "out.csv",
            buffer="1km",
        )
    with pytest.raises(ValueError, match="buffer must"):
        normalize_can_fed_archive(
            archive,
            tmp_path / "out.csv",
            buffer="wide",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("row_change", ["short", "long"])
def test_can_fed_rejects_ragged_rows(tmp_path: Path, row_change: str) -> None:
    source = (
        _FIXTURES / "can_fed_v2" / "canfed_public_data" / "dens_thresholds_1km.csv"
    ).read_text()
    header, row, *_ = source.splitlines()
    changed = row.rsplit(",", 1)[0] if row_change == "short" else f"{row},extra"
    archive = _zip_members(
        tmp_path / f"{row_change}.zip",
        {"dens_thresholds_1km.csv": f"{header}\n{changed}\n"},
    )

    with pytest.raises(ValueError, match="column count"):
        normalize_can_fed_archive(
            archive,
            tmp_path / "out.csv",
            buffer="1km",
        )


def test_odef_profile_and_normalization(tmp_path: Path) -> None:
    source = odef_source_profile()
    adapter = OdefAdapter()
    archive = _odef_archive(tmp_path)
    output = tmp_path / "facilities.csv"

    report = adapter.normalize_archive(archive, output)
    rows = list(csv.DictReader(output.open()))

    assert source.source_version == "3.0.1"
    assert source.publication_date == "2024-12-13"
    assert "project-written" in source.translation_provenance["en"]
    assert source.geography is not None
    assert source.geography.canonical_key == (
        2021,
        "csd",
        "statcan:census:2021:csd",
    )
    assert adapter.describe() == source
    assert adapter.reproduction_parameters()["source_revision"] == "3.0.1"
    assert adapter.reproduction_parameters()["correction_notice_date"] == ("2025-11-17")
    assert report["source_rows"] == 3
    assert report["ungeocoded_count"] == 1
    assert report["missing_csd_count"] == 1
    assert len(report["duplicate_source_identifier_groups"]) == 1
    assert len(report["candidate_duplicate_groups"]) == 1
    assert report["duplicate_coordinate_row_count"] == 1
    first = rows[0]
    assert first["CSDUID"] == "2466001"
    assert first["CSDDGUID"] == "2021A00052466001"
    assert first["longitude"] == "-73.5"
    assert first["latitude"] == "45.5"
    assert first["isced_010"] == "true"
    assert rows[-1]["official_language_minority_school"] == ""


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("synthetic-facility-0002", "synthetic-facility-0001", "duplicate"),
        ("synthetic-facility-0001", "..", "missing unique_id"),
        ("2021A00052466001", "bad-dguid", "malformed CSD"),
        ("POINT (-73.5 45.5)", "LINESTRING (0 0 1 1)", "geometry WKT"),
        ("POINT (-73.5 45.5)", "POINT (-273.5 45.5)", "out-of-range"),
        (",1,1,1,0,0,0,1,1,1,0,0,", ",2,1,1,0,0,0,1,1,1,0,0,", "unsupported ISCED010"),
    ],
)
def test_odef_rejects_invalid_source_values(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    fixture = (_FIXTURES / "odef_v3" / "ODEF_v3.0.1" / "odef_v3_0_1.csv").read_text()
    archive = _zip_members(
        tmp_path / "bad.zip",
        {"ODEF_v3.0.1/odef_v3_0_1.csv": fixture.replace(old, new, 1)},
    )
    with pytest.raises(ValueError, match=message):
        normalize_odef_archive(archive, tmp_path / "out.csv")


def test_odef_rejects_bad_archive_shape(tmp_path: Path) -> None:
    archive = _zip_members(
        tmp_path / "bad.zip",
        {"ODEF_v3.0.1/odef_v3_0_1.csv": "unique_id,wrong\na,b\n"},
    )
    with pytest.raises(ValueError, match="columns"):
        normalize_odef_archive(archive, tmp_path / "out.csv")
    with pytest.raises(ValueError, match="valid ZIP"):
        normalize_odef_archive(
            _write_text(tmp_path / "not.zip", "not a zip"),
            tmp_path / "out.csv",
        )
    with pytest.raises(ValueError, match="must contain"):
        normalize_odef_archive(
            _zip_members(tmp_path / "empty.zip", {"other.csv": "a\n"}),
            tmp_path / "out.csv",
        )
    source_header = (
        (_FIXTURES / "odef_v3" / "ODEF_v3.0.1" / "odef_v3_0_1.csv")
        .read_text()
        .splitlines()[0]
    )
    with pytest.raises(ValueError, match="table is empty"):
        normalize_odef_archive(
            _zip_members(
                tmp_path / "empty-table.zip",
                {"odef_v3_0_1.csv": source_header + "\n"},
            ),
            tmp_path / "out.csv",
        )


@pytest.mark.parametrize("row_change", ["short", "long"])
def test_odef_rejects_ragged_rows(tmp_path: Path, row_change: str) -> None:
    source = (_FIXTURES / "odef_v3" / "ODEF_v3.0.1" / "odef_v3_0_1.csv").read_text()
    header, row, *_ = source.splitlines()
    changed = row.rsplit(",", 1)[0] if row_change == "short" else f"{row},extra"
    archive = _zip_members(
        tmp_path / f"{row_change}.zip",
        {"odef_v3_0_1.csv": f"{header}\n{changed}\n"},
    )

    with pytest.raises(ValueError, match="column count"):
        normalize_odef_archive(archive, tmp_path / "out.csv")


def test_reference_adapters_bound_expanded_archives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canfed = _canfed_archive(tmp_path)
    odef = _odef_archive(tmp_path)
    monkeypatch.setattr(canfed_module, "_MAX_EXPANDED_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        normalize_can_fed_archive(canfed, tmp_path / "canfed.csv")
    monkeypatch.setattr(odef_module, "_MAX_EXPANDED_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        normalize_odef_archive(odef, tmp_path / "odef.csv")


def test_can_fed_api_runs_end_to_end_and_reconciles_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _canfed_archive(tmp_path)
    monkeypatch.setattr(api_module, "CANFED_V2_ARCHIVE_SHA256", _sha256(archive))
    population = _population(
        tmp_path / "population",
        geography_column="DAUID",
        identifiers=("99990001", "99990003"),
    )
    base_hashes = {
        path.name: _sha256(path) for path in population.iterdir() if path.is_file()
    }

    result = spc.enrich_can_fed(
        population,
        output_dir=tmp_path / "canfed-output",
        resource=archive,
        acquired_at="2026-08-02T12:00:00Z",
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
    )

    assert result.validation["passed"] is True
    layer_validation = result.validation["layer_validation"]
    assert layer_validation["unmatched_layer_identifiers"] == ["99990002"]
    assert layer_validation["unmatched_base_identifiers"] == ["99990003"]
    assert result.source_profile is not None and result.source_profile.is_file()
    assert result.resource_record is not None and result.resource_record.is_file()
    assert result.validation_report is not None and result.validation_report.is_file()
    manifest = read_enrichment_manifest(result.manifest)
    assert (
        verify_enrichment_manifest(
            manifest,
            result.manifest.parent,
            base_directory=population,
        )["passed"]
        is True
    )
    assert base_hashes == {
        path.name: _sha256(path) for path in population.iterdir() if path.is_file()
    }


def test_reference_api_rejects_unreviewed_and_incompatible_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _canfed_archive(tmp_path)
    population = _population(
        tmp_path / "population",
        geography_column="DAUID",
        identifiers=("99990001",),
    )
    with pytest.raises(ValueError, match="not reviewed"):
        spc.enrich_can_fed(
            population,
            output_dir=tmp_path / "bad-revision",
            resource=archive,
            base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        )
    monkeypatch.setattr(api_module, "CANFED_V2_ARCHIVE_SHA256", _sha256(archive))
    with pytest.raises(ValueError, match="requires 2021 DA.*received 2016 DA"):
        spc.enrich_can_fed(
            population,
            output_dir=tmp_path / "bad-vintage",
            resource=archive,
            base_geography=statcan_geography_universe(2016, "da", "DAUID"),
        )
    with pytest.raises(ValueError, match="buffer must"):
        spc.enrich_can_fed(
            population,
            output_dir=tmp_path / "bad-buffer",
            resource=archive,
            base_geography=statcan_geography_universe(2021, "da", "DAUID"),
            buffer="wide",
        )


def test_odef_api_supports_unlinked_and_csd_linked_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _odef_archive(tmp_path)
    monkeypatch.setattr(api_module, "ODEF_V3_ARCHIVE_SHA256", _sha256(archive))
    unlinked_population = _population(tmp_path / "unlinked-population")

    unlinked = spc.enrich_odef(
        unlinked_population,
        output_dir=tmp_path / "odef-unlinked",
        resource=archive,
        acquired_at="2026-08-02T12:00:00Z",
    )
    assert unlinked.validation["base_linkage"] == "not-requested"
    assert unlinked.validation["source_validation"]["missing_csd_count"] == 1

    csd_population = _population(
        tmp_path / "csd-population",
        geography_column="csd",
        identifiers=("2466001", "2466002"),
    )
    linked = spc.enrich_odef(
        csd_population,
        output_dir=tmp_path / "odef-linked",
        resource=archive,
        base_geography=statcan_geography_universe(2021, "csd", "csd"),
    )
    layer_validation = linked.validation["layer_validation"]
    assert linked.validation["base_linkage"] == "validated"
    assert layer_validation["unmatched_base_identifiers"] == ["2466002"]
    assert layer_validation["unmatched_layer_identifiers"] == []

    with pytest.raises(ValueError, match="requires 2021 CSD.*received 2021 DA"):
        spc.enrich_odef(
            csd_population,
            output_dir=tmp_path / "odef-bad-link",
            resource=archive,
            base_geography=statcan_geography_universe(2021, "da", "csd"),
        )


def test_reference_workflow_can_use_bounded_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _canfed_archive(tmp_path)
    digest = _sha256(archive)
    source = can_fed_source_profile()
    record = ResourceRecord(
        resource_id=f"resource:{digest}",
        source_id=source.source_id,
        source_version=source.source_version,
        acquisition_mode="public-download",
        acquired_at="2026-08-02T12:00:00Z",
        media_type="application/zip",
        byte_size=archive.stat().st_size,
        sha256=digest,
        public_locator=CanFedAdapter.resource_url,
    )
    monkeypatch.setattr(
        workflow_module,
        "acquire_public_resource",
        lambda *args, **kwargs: (archive, record),
    )
    population = _population(
        tmp_path / "population",
        geography_column="DAUID",
        identifiers=("99990001",),
    )
    artifacts = workflow_module.run_reference_enrichment(
        population,
        tmp_path / "output",
        CanFedAdapter(expected_sha256=digest),
        cache_directory=tmp_path / "cache",
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
    )
    assert artifacts.validation["passed"] is True


def test_reference_workflow_reuses_reviewed_cached_bytes_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _canfed_archive(tmp_path)
    digest = _sha256(archive)
    cache = tmp_path / "cache"
    cached_archive = cache / "objects" / digest[:2] / digest
    cached_archive.parent.mkdir(parents=True)
    cached_archive.write_bytes(archive.read_bytes())
    monkeypatch.setattr(
        workflow_module,
        "acquire_public_resource",
        lambda *args, **kwargs: pytest.fail("offline cache hit used the network"),
    )
    population = _population(
        tmp_path / "population",
        geography_column="DAUID",
        identifiers=("99990001",),
    )

    artifacts = workflow_module.run_reference_enrichment(
        population,
        tmp_path / "output",
        CanFedAdapter(expected_sha256=digest),
        cache_directory=cache,
        acquired_at="2026-08-02T12:00:00Z",
        base_geography=statcan_geography_universe(2021, "da", "DAUID"),
    )

    resource = json.loads(artifacts.resource_record.read_text())
    assert resource["sha256"] == digest
    assert resource["acquired_at"] == "2026-08-02T12:00:00Z"


@pytest.mark.parametrize("acquired_at", ["not-a-date", "2026-08-02T12:00:00"])
def test_reference_workflow_requires_timezone_aware_acquisition_time(
    tmp_path: Path,
    acquired_at: str,
) -> None:
    population = _population(
        tmp_path / "population",
        geography_column="DAUID",
        identifiers=("99990001",),
    )
    with pytest.raises(ValueError, match="timezone-aware ISO 8601"):
        workflow_module.run_reference_enrichment(
            population,
            tmp_path / "output",
            CanFedAdapter(),
            resource_path=tmp_path / "unused.zip",
            acquired_at=acquired_at,
            base_geography=statcan_geography_universe(2021, "da", "DAUID"),
        )


def test_reference_workflow_requires_declared_can_fed_geography(
    tmp_path: Path,
) -> None:
    population = _population(tmp_path / "population")
    with pytest.raises(ValueError, match="requires an explicit base geography"):
        workflow_module.run_reference_enrichment(
            population,
            tmp_path / "output",
            CanFedAdapter(),
            resource_path=tmp_path / "unused.zip",
        )


def test_reference_cli_commands_are_coherent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canfed = _canfed_archive(tmp_path)
    odef = _odef_archive(tmp_path)
    monkeypatch.setattr(api_module, "CANFED_V2_ARCHIVE_SHA256", _sha256(canfed))
    monkeypatch.setattr(api_module, "ODEF_V3_ARCHIVE_SHA256", _sha256(odef))
    da_population = _population(
        tmp_path / "da-population",
        geography_column="DAUID",
        identifiers=("99990001",),
    )
    plain_population = _population(tmp_path / "plain-population")
    runner = CliRunner()

    canfed_result = runner.invoke(
        cli,
        [
            "enrich",
            "can-fed",
            str(da_population),
            "--resource",
            str(canfed),
            "--base-census-vintage",
            "2021",
            "--out",
            str(tmp_path / "canfed-cli"),
            "--format",
            "json",
        ],
    )
    assert canfed_result.exit_code == 0, canfed_result.output
    canfed_payload = json.loads(canfed_result.output)
    assert canfed_payload["validation"]["dataset_id"] == (
        "statcan.canfed.v2.general-use"
    )
    assert canfed_payload["artifacts"]["layer"].endswith("canfed-v2-both.csv")
    assert canfed_payload["artifacts"]["validation_report"].endswith("validation.json")

    odef_result = runner.invoke(
        cli,
        [
            "enrich",
            "odef",
            str(plain_population),
            "--resource",
            str(odef),
            "--out",
            str(tmp_path / "odef-cli"),
        ],
    )
    assert odef_result.exit_code == 0, odef_result.output
    assert "Validated 3 normalized rows" in odef_result.output

    rejected = runner.invoke(
        cli,
        [
            "enrich",
            "can-fed",
            str(da_population),
            "--resource",
            str(canfed),
            "--base-census-vintage",
            "2016",
            "--out",
            str(tmp_path / "rejected"),
        ],
    )
    assert rejected.exit_code != 0
    assert "requires 2021 DA" in rejected.output


@pytest.mark.parametrize("dataset", ["can-fed", "odef"])
@pytest.mark.parametrize("use_symlink", [False, True])
def test_reference_adapters_reject_population_directory_as_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dataset: str,
    use_symlink: bool,
) -> None:
    archive = (
        _canfed_archive(tmp_path) if dataset == "can-fed" else _odef_archive(tmp_path)
    )
    if dataset == "can-fed":
        monkeypatch.setattr(api_module, "CANFED_V2_ARCHIVE_SHA256", _sha256(archive))
        population = _population(
            tmp_path / "population",
            geography_column="DAUID",
            identifiers=("99990001",),
        )
    else:
        monkeypatch.setattr(api_module, "ODEF_V3_ARCHIVE_SHA256", _sha256(archive))
        population = _population(tmp_path / "population")
    output = population
    if use_symlink:
        output = tmp_path / "population-alias"
        output.symlink_to(population, target_is_directory=True)
    manifest_before = (population / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match="must differ"):
        if dataset == "can-fed":
            spc.enrich_can_fed(
                population,
                output_dir=output,
                resource=archive,
                base_geography=statcan_geography_universe(2021, "da", "DAUID"),
            )
        else:
            spc.enrich_odef(
                population,
                output_dir=output,
                resource=archive,
            )

    assert (population / "manifest.json").read_bytes() == manifest_before


def test_reference_api_rejects_nonstandard_linked_population_filenames(
    tmp_path: Path,
) -> None:
    population = _population(tmp_path / "population")
    files = spc.LinkedPopulationFiles(
        households=population / "custom-households.csv",
        persons=population / "custom-persons.csv",
        manifest=population / "manifest.json",
    )

    with pytest.raises(ValueError, match="standard linked-population filenames"):
        spc.enrich_odef(
            files,
            output_dir=tmp_path / "output",
            resource=tmp_path / "unused.zip",
        )


def test_enrichment_cache_dir_respects_platform_and_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_ENRICHMENT_CACHE", str(tmp_path / "override"))
    assert workflow_module.enrichment_cache_dir() == tmp_path / "override"
    monkeypatch.delenv("SYNTHPOPCAN_ENRICHMENT_CACHE")
    monkeypatch.setattr(workflow_module.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert workflow_module.enrichment_cache_dir() == (
        tmp_path / "Library" / "Caches" / "synthpopcan" / "enrichment"
    )
    monkeypatch.setattr(workflow_module.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert workflow_module.enrichment_cache_dir() == (
        tmp_path / "xdg" / "synthpopcan" / "enrichment"
    )


def _write_text(path: Path, value: str) -> Path:
    path.write_text(value)
    return path
