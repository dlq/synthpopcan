import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from synthpopcan.model_licensing import statcan_prepared_model_licensing

SCRIPT = Path(__file__).parents[1] / "scripts/build_corrected_model_assets.py"
SPEC = importlib.util.spec_from_file_location("build_corrected_model_assets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ZENODO_SCRIPT = Path(__file__).parents[1] / "scripts/build_zenodo_depositions.py"
ZENODO_SPEC = importlib.util.spec_from_file_location(
    "correction_asset_zenodo_builder", ZENODO_SCRIPT
)
assert ZENODO_SPEC is not None and ZENODO_SPEC.loader is not None
ZENODO_MODULE = importlib.util.module_from_spec(ZENODO_SPEC)
ZENODO_SPEC.loader.exec_module(ZENODO_MODULE)

DEPOSITOR_SCRIPT = Path(__file__).parents[1] / "scripts/deposit_zenodo_records.py"
DEPOSITOR_SPEC = importlib.util.spec_from_file_location(
    "correction_asset_depositor", DEPOSITOR_SCRIPT
)
assert DEPOSITOR_SPEC is not None and DEPOSITOR_SPEC.loader is not None
DEPOSITOR_MODULE = importlib.util.module_from_spec(DEPOSITOR_SPEC)
DEPOSITOR_SPEC.loader.exec_module(DEPOSITOR_MODULE)


def _gzip_bytes(payload: bytes) -> bytes:
    from io import BytesIO

    output = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as archive:
        archive.write(payload)
    return output.getvalue()


def _model_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: bytes = (
        b'{"schema_version":"synthpopcan-linked-tree-package-v1",'
        b'"package_type":"linked_household_person","name":"fixture",'
        b'"values":[1,true,null,{"nested":"ok"}]}'
    ),
    model_id: str = "fixture-2021",
    census_year: int = 2021,
) -> dict[str, Any]:
    licensing = statcan_prepared_model_licensing(census_year)
    concept_doi = "10.5281/zenodo.123456"
    filename = f"{model_id}-package.json.gz"
    compressed = _gzip_bytes(payload)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / filename).write_bytes(compressed)
    entry = {
        "id": model_id,
        "name": "Fixture model",
        "description": "Small prepared-model fixture.",
        "distribution": "download",
        "census_vintage": f"{census_year} Census",
        "release_version": "v0.6.0",
        "doi": concept_doi,
        "licensing": licensing,
        "geography": "Fixture geography",
        "conditions": ["PR"],
        "provenance": licensing["source_information"]["prescribed_notice"],
        "source_licence": licensing["source_information"]["licence"]["url"],
        "privacy": "No raw source rows.",
        "privacy_review_status": "test fixture",
        "known_limitations": "Test fixture only.",
        "generation_limits": "Tiny tests only.",
    }
    registry = {
        "url": f"https://example.invalid/{filename}",
        "compression": "gzip",
        "size_bytes": len(compressed),
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "uncompressed_size_bytes": len(payload),
        "uncompressed_sha256": hashlib.sha256(payload).hexdigest(),
    }
    monkeypatch.setattr(MODULE, "model_catalogue", lambda: [entry])
    monkeypatch.setattr(MODULE, "model_registry_entry", lambda _model_id: registry)
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-record-index-v1",
                "records": {
                    model_id: {
                        "latest_record_id": 654321,
                        "concept_doi": concept_doi,
                        "version_doi": "10.5281/zenodo.654321",
                    }
                },
            }
        )
    )
    licensing_path = tmp_path / f"licensing-{census_year}.json"
    licensing_path.write_text(json.dumps(licensing))
    return {
        "model_id": model_id,
        "payload": payload,
        "compressed": compressed,
        "assets": assets,
        "entry": entry,
        "registry": registry,
        "records": records,
        "licensing": licensing,
        "licensing_path": licensing_path,
    }


def _build(
    tmp_path: Path,
    inputs: dict[str, Any],
    *,
    output_name: str = "output",
    licensing_path: Path | None = None,
) -> Path:
    return MODULE.build_correction_candidates(
        assets_dir=inputs["assets"],
        record_index_path=inputs["records"],
        licensing_paths={
            int(inputs["entry"]["census_vintage"].split()[0]): (
                licensing_path or inputs["licensing_path"]
            )
        },
        new_package_version="v1.0.0-rights.1",
        output_dir=tmp_path / output_name,
        test_subset=[inputs["model_id"]],
    )


def test_builder_streams_preserved_json_and_emits_compatible_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(
        MODULE.gzip,
        "decompress",
        lambda _value: pytest.fail("builder must not materialize the gzip payload"),
    )

    index_path = _build(tmp_path, inputs)

    document = json.loads(index_path.read_text())
    assert document["schema_version"] == ("synthpopcan-zenodo-correction-candidates-v1")
    assert document["build_scope"] == "test-subset"
    assert document["production_ready"] is False
    assert "never eligible for production" in document["non_production_reason"]
    assert document["network_writes"] is False
    assert document["model_retrained"] is False
    candidate = document["candidates"][inputs["model_id"]]
    assert candidate["existing_record_id"] == 654321
    assert candidate["existing_concept_doi"] == inputs["entry"]["doi"]
    assert candidate["existing_version_doi"] == "10.5281/zenodo.654321"
    assert "v1.0.0-rights.1" in candidate["filename"]
    assert candidate["model_id"] == inputs["model_id"]
    assert candidate["package_schema_version"] == ("synthpopcan-linked-tree-package-v1")
    assert candidate["package_type"] == "linked_household_person"
    assert candidate["existing_package_version"] == "v0.6.0"
    assert candidate["licensing_schema_version"] == (
        "synthpopcan-prepared-model-licensing-v1"
    )
    assert candidate["model_retrained"] is False
    assert candidate["historical_asset"]["sha256"] == inputs["registry"]["sha256"]
    assert candidate["historical_asset"]["contains_embedded_licensing"] is False
    assert candidate["candidate_asset"]["sha256"] == candidate["sha256"]
    assert candidate["candidate_asset"]["contains_embedded_licensing"] is True
    corrected = (index_path.parent / candidate["filename"]).read_bytes()
    assert len(corrected) == candidate["size_bytes"]
    assert hashlib.sha256(corrected).hexdigest() == candidate["sha256"]
    with gzip.open(index_path.parent / candidate["filename"], "rb") as archive:
        corrected_json = archive.read()
    insertion = (
        b'"licensing":'
        + json.dumps(
            inputs["licensing"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b","
    )
    root_open = inputs["payload"].index(b"{") + 1
    assert (
        corrected_json[:root_open] + corrected_json[root_open + len(insertion) :]
        == inputs["payload"]
    )
    assert corrected_json == (
        inputs["payload"][:root_open] + insertion + inputs["payload"][root_open:]
    )
    assert json.loads(corrected_json)["licensing"] == inputs["licensing"]

    monkeypatch.setattr(ZENODO_MODULE, "model_catalogue", lambda: [inputs["entry"]])
    monkeypatch.setattr(
        ZENODO_MODULE,
        "model_registry_entry",
        lambda _model_id: inputs["registry"],
    )
    metadata, new_version = ZENODO_MODULE.build_correction_depositions(
        inputs["model_id"],
        candidate,
        concept_doi="10.5281/zenodo.999999",
        production_ready=document["production_ready"],
        build_scope=document["build_scope"],
        envelope_new_version=document["new_package_version"],
    )
    assert metadata["synthpopcan"]["deposit_operation"] == ("correct-existing-metadata")
    assert new_version["synthpopcan"]["deposit_operation"] == "create-new-version"


def test_corrected_archives_are_deterministic_across_output_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)

    first = json.loads(_build(tmp_path, inputs, output_name="first").read_text())
    second = json.loads(_build(tmp_path, inputs, output_name="second").read_text())

    first_candidate = first["candidates"][inputs["model_id"]]
    second_candidate = second["candidates"][inputs["model_id"]]
    assert first_candidate["sha256"] == second_candidate["sha256"]
    assert (
        first_candidate["uncompressed_sha256"]
        == (second_candidate["uncompressed_sha256"])
    )
    assert (tmp_path / "first" / first_candidate["filename"]).read_bytes() == (
        tmp_path / "second" / second_candidate["filename"]
    ).read_bytes()


def test_large_package_uses_early_licensing_and_passes_depositor_streaming_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = (
        b'{"schema_version":"synthpopcan-linked-tree-package-v1",'
        b'"package_type":"linked_household_person","large_prefix":"'
        + b"x" * (8 * 1024 * 1024 + 512)
        + b'"}'
    )
    inputs = _model_inputs(tmp_path, monkeypatch, payload=payload)

    document = json.loads(_build(tmp_path, inputs).read_text())
    candidate = document["candidates"][inputs["model_id"]]
    corrected_path = tmp_path / "output" / candidate["filename"]
    with gzip.open(corrected_path, "rb") as archive:
        corrected_json = archive.read()
    assert len(corrected_json) > 8 * 1024 * 1024
    assert corrected_json.index(b'"licensing"') < 1024

    extracted = DEPOSITOR_MODULE._stream_uncompressed_licensing(
        corrected_path.read_bytes(),
        expected_size=candidate["uncompressed_size_bytes"],
        expected_sha256=candidate["uncompressed_sha256"],
    )
    assert extracted == inputs["licensing"]


def test_source_is_reverified_during_transformation_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    original = MODULE._write_corrected_asset

    def mutate_after_preflight(prepared: Any) -> Any:
        changed = inputs["payload"][:-1] + b',"changed":true}'
        prepared.historical_path.write_bytes(_gzip_bytes(changed))
        return original(prepared)

    monkeypatch.setattr(MODULE, "_write_corrected_asset", mutate_after_preflight)

    with pytest.raises(MODULE.CorrectionAssetError, match="changed after preflight"):
        _build(tmp_path, inputs)

    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob(".output.*.staging"))


def test_source_open_failure_closes_mkstemp_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    historical_path = inputs["assets"] / f"{inputs['model_id']}-package.json.gz"
    inspection = MODULE._inspect_gzip_json(
        historical_path,
        expected=inputs["registry"],
        expected_licensing_keys=0,
    )
    prepared = MODULE._PreparedModel(
        inputs["model_id"],
        2021,
        historical_path,
        inputs["registry"],
        {},
        inputs["licensing"],
        "corrected-v1.0.0.json.gz",
        tmp_path / "staging" / "corrected-v1.0.0.json.gz",
        inspection,
    )
    real_fdopen = MODULE.os.fdopen
    real_path_open = Path.open
    opened: list[Any] = []

    def tracked_fdopen(descriptor: int, mode: str) -> Any:
        handle = real_fdopen(descriptor, mode)
        opened.append(handle)
        return handle

    def fail_historical_open(path: Path, *args: object, **kwargs: object) -> Any:
        if path == historical_path:
            raise OSError("simulated source-open race")
        return real_path_open(path, *args, **kwargs)

    monkeypatch.setattr(MODULE.os, "fdopen", tracked_fdopen)
    monkeypatch.setattr(Path, "open", fail_historical_open)

    with pytest.raises(OSError, match="source-open race"):
        MODULE._write_corrected_asset(prepared)

    assert len(opened) == 1
    assert opened[0].closed
    assert not list((tmp_path / "staging").glob(".*.json.gz"))


def test_multi_model_failure_leaves_no_assets_or_candidate_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    second_id = "fixture-two-2021"
    second_filename = f"{second_id}-package.json.gz"
    (inputs["assets"] / second_filename).write_bytes(inputs["compressed"])
    second_entry = {
        **inputs["entry"],
        "id": second_id,
        "doi": "10.5281/zenodo.123457",
    }
    second_registry = {
        **inputs["registry"],
        "url": f"https://example.invalid/{second_filename}",
    }
    entries = [inputs["entry"], second_entry]
    registries = {
        inputs["model_id"]: inputs["registry"],
        second_id: second_registry,
    }
    monkeypatch.setattr(MODULE, "model_catalogue", lambda: entries)
    monkeypatch.setattr(
        MODULE, "model_registry_entry", lambda model_id: registries[model_id]
    )
    record_document = json.loads(inputs["records"].read_text())
    record_document["records"][second_id] = {
        "latest_record_id": 654322,
        "concept_doi": second_entry["doi"],
        "version_doi": "10.5281/zenodo.654322",
    }
    inputs["records"].write_text(json.dumps(record_document))
    original = MODULE._write_corrected_asset

    def fail_second(prepared: Any) -> Any:
        if prepared.model_id == second_id:
            raise MODULE.CorrectionAssetError("simulated second-model failure")
        return original(prepared)

    monkeypatch.setattr(MODULE, "_write_corrected_asset", fail_second)

    with pytest.raises(MODULE.CorrectionAssetError, match="second-model failure"):
        MODULE.build_correction_candidates(
            assets_dir=inputs["assets"],
            record_index_path=inputs["records"],
            licensing_paths={2021: inputs["licensing_path"]},
            new_package_version="v1.0.0-rights.1",
            output_dir=tmp_path / "transaction",
            test_subset=[inputs["model_id"], second_id],
        )

    assert not (tmp_path / "transaction").exists()
    assert not list(tmp_path.glob(".transaction.*.staging"))


def test_index_fsync_failure_cleans_untracked_staging_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(
        MODULE.os,
        "fsync",
        lambda _descriptor: (_ for _ in ()).throw(OSError("simulated fsync failure")),
    )

    with pytest.raises(MODULE.CorrectionAssetError, match="staged correction"):
        _build(tmp_path, inputs, output_name="fsync-output")

    assert not (tmp_path / "fsync-output").exists()
    assert not list(tmp_path.glob(".fsync-output.*.staging"))


def test_bundle_publication_uses_atomic_no_clobber_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    output = tmp_path / "race-output"
    real_link = MODULE.os.link
    injected: list[Path] = []

    def inject_concurrent_destination(source: object, destination: object) -> None:
        destination_path = Path(destination)
        if destination_path.parent == output and not injected:
            destination_path.write_bytes(b"concurrent-owner")
            injected.append(destination_path)
        real_link(source, destination)

    monkeypatch.setattr(MODULE.os, "link", inject_concurrent_destination)

    with pytest.raises(MODULE.CorrectionAssetError, match="refusing to overwrite"):
        MODULE.build_correction_candidates(
            assets_dir=inputs["assets"],
            record_index_path=inputs["records"],
            licensing_paths={2021: inputs["licensing_path"]},
            new_package_version="v1.0.0-rights.1",
            output_dir=output,
            test_subset=[inputs["model_id"]],
        )

    assert len(injected) == 1
    assert injected[0].read_bytes() == b"concurrent-owner"
    assert not (output / "correction-candidates.json").exists()
    assert not list(tmp_path.glob(".race-output.*.staging"))


def test_record_index_binds_version_doi_to_record_id_and_all_dois_are_unique(
    tmp_path: Path,
) -> None:
    records = tmp_path / "identity-records.json"
    records.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-record-index-v1",
                "records": {
                    "first": {
                        "latest_record_id": 654321,
                        "concept_doi": "10.5281/zenodo.100",
                        "version_doi": "10.5281/zenodo.999999",
                    }
                },
            }
        )
    )
    with pytest.raises(MODULE.CorrectionAssetError, match="latest_record_id"):
        MODULE._record_mapping(
            records,
            selected=["first"],
            known={"first": {"doi": "10.5281/zenodo.100"}},
        )

    records.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-zenodo-record-index-v1",
                "records": {
                    "first": {
                        "latest_record_id": 654321,
                        "concept_doi": "10.5281/zenodo.100",
                        "version_doi": "10.5281/zenodo.654321",
                    },
                    "second": {
                        "latest_record_id": 654322,
                        "concept_doi": "10.5281/zenodo.654321",
                        "version_doi": "10.5281/zenodo.654322",
                    },
                },
            }
        )
    )
    with pytest.raises(MODULE.CorrectionAssetError, match="duplicate record"):
        MODULE._record_mapping(
            records,
            selected=["first", "second"],
            known={
                "first": {"doi": "10.5281/zenodo.100"},
                "second": {"doi": "10.5281/zenodo.654321"},
            },
        )


@pytest.mark.parametrize(
    "payload,match",
    [
        (b"[]", "top-level JSON object"),
        (b'{"a":1} trailing', "trailing JSON data"),
        (b'{"a":}', "malformed JSON"),
        (b'{"licensing":{}}', "existing or duplicate"),
        (
            b'{"licensing":{},"licensing":{}}',
            "existing or duplicate",
        ),
    ],
)
def test_builder_rejects_unsafe_historical_json_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    match: str,
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch, payload=payload)

    with pytest.raises(MODULE.CorrectionAssetError, match=match):
        _build(tmp_path, inputs)

    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("size_bytes", 1, "compressed size mismatch"),
        ("sha256", "0" * 64, "compressed SHA-256 mismatch"),
        ("uncompressed_size_bytes", 1, "uncompressed size mismatch"),
        ("uncompressed_sha256", "0" * 64, "uncompressed SHA-256 mismatch"),
    ],
)
def test_builder_verifies_every_registered_historical_integrity_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    match: str,
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    inputs["registry"][field] = value

    with pytest.raises(MODULE.CorrectionAssetError, match=match):
        _build(tmp_path, inputs)

    assert not (tmp_path / "output").exists()


def test_builder_rejects_missing_unknown_and_duplicate_record_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    inputs["records"].write_text(
        '{"schema_version":"synthpopcan-zenodo-record-index-v1",'
        '"records":{"unknown":{"latest_record_id":1,'
        '"concept_doi":"10.5281/zenodo.1",'
        '"version_doi":"10.5281/zenodo.2"}}}'
    )
    with pytest.raises(MODULE.CorrectionAssetError, match="model set mismatch"):
        _build(tmp_path, inputs)

    model_id = inputs["model_id"]
    identity = (
        '"latest_record_id":654321,'
        f'"concept_doi":"{inputs["entry"]["doi"]}",'
        '"version_doi":"10.5281/zenodo.654321"'
    )
    inputs["records"].write_text(
        '{"schema_version":"synthpopcan-zenodo-record-index-v1",'
        '"records":{"'
        + model_id
        + '":{'
        + identity
        + '},"'
        + model_id
        + '":{'
        + identity
        + "}}}"
    )
    with pytest.raises(MODULE.CorrectionAssetError, match="duplicate key"):
        _build(tmp_path, inputs)


def test_builder_rejects_conflicting_licensing_vintage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    wrong = tmp_path / "wrong-licensing.json"
    wrong.write_text(json.dumps(statcan_prepared_model_licensing(2016)))

    with pytest.raises(MODULE.CorrectionAssetError, match="catalogue vintage"):
        _build(tmp_path, inputs, licensing_path=wrong)


def test_complete_mode_requires_32_models_and_subset_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)

    with pytest.raises(MODULE.CorrectionAssetError, match="exactly the 32"):
        MODULE.build_correction_candidates(
            assets_dir=inputs["assets"],
            record_index_path=inputs["records"],
            licensing_paths={2021: inputs["licensing_path"]},
            new_package_version="v1.0.0-rights.1",
            output_dir=tmp_path / "complete",
        )
    with pytest.raises(MODULE.CorrectionAssetError, match="duplicate model IDs"):
        MODULE._selection(
            {inputs["model_id"]: object()},
            [inputs["model_id"], inputs["model_id"]],
        )
    with pytest.raises(MODULE.CorrectionAssetError, match="bounded to 8"):
        MODULE._selection(
            {f"model-{index}": object() for index in range(9)},
            [f"model-{index}" for index in range(9)],
        )


def test_builder_is_non_overwriting_and_cli_labels_local_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _model_inputs(tmp_path, monkeypatch)
    _build(tmp_path, inputs)

    with pytest.raises(MODULE.CorrectionAssetError, match="refusing to overwrite"):
        _build(tmp_path, inputs)

    fresh = tmp_path / "cli-output"
    result = CliRunner().invoke(
        MODULE.main,
        [
            "--assets-dir",
            str(inputs["assets"]),
            "--record-index",
            str(inputs["records"]),
            "--licensing-2021",
            str(inputs["licensing_path"]),
            "--new-package-version",
            "v1.0.0-rights.1",
            "--out",
            str(fresh),
            "--test-subset",
            inputs["model_id"],
        ],
    )
    assert result.exit_code == 0, result.output
    assert "no model was retrained" in result.output
    assert "no network or archive write" in result.output
