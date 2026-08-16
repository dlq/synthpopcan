import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from synthpopcan.model_licensing import statcan_prepared_model_licensing

SCRIPT = Path(__file__).parents[1] / "scripts/deposit_zenodo_records.py"
SPEC = importlib.util.spec_from_file_location("deposit_zenodo_records", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUILD_SCRIPT = Path(__file__).parents[1] / "scripts/build_zenodo_depositions.py"
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_zenodo_depositions_for_deposit_test", BUILD_SCRIPT
)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
BUILD_MODULE = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD_MODULE)

_HISTORICAL_BYTES = b"historical!!"
_HISTORICAL_SHA256 = hashlib.sha256(_HISTORICAL_BYTES).hexdigest()
_HISTORICAL_URL = (
    "data:application/octet-stream;base64,"
    + base64.b64encode(_HISTORICAL_BYTES).decode()
)


def _payload(deposition: dict) -> tuple[bytes, bytes]:
    unpacked = json.dumps(
        {
            "licensing": deposition["synthpopcan"]["licensing"],
            "models": {"test": {}},
        },
        sort_keys=True,
    ).encode()
    return gzip.compress(unpacked, mtime=0), unpacked


def _deposition(*, licensing: dict | None = None) -> dict:
    licensing = licensing or statcan_prepared_model_licensing(2021)
    unpacked = json.dumps(
        {"licensing": licensing, "models": {"test": {}}}, sort_keys=True
    ).encode()
    payload = gzip.compress(unpacked, mtime=0)
    return {
        "metadata": {
            "title": "SynthPopCan prepared model: Ontario",
            "upload_type": "dataset",
            "version": "1.0.0",
            "creators": [{"name": "Quesnel, Darcy"}],
            "license": "other-open",
        },
        "synthpopcan": {
            "model_id": "ontario-2021-all-fields",
            "deposit_operation": "create-new-record",
            "asset_ready": True,
            "asset_url": "https://example.invalid/ontario.json.gz",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "uncompressed_size_bytes": len(unpacked),
            "uncompressed_sha256": hashlib.sha256(unpacked).hexdigest(),
            "licensing": licensing,
        },
    }


def _existing_record() -> dict:
    return {
        "id": 100,
        "doi": "10.5072/zenodo.100",
        "conceptdoi": "10.5072/zenodo.90",
        "metadata": {
            "title": "SynthPopCan prepared model: Ontario",
            "resource_type": {"id": "dataset", "title": "Dataset"},
            "version": "0.9.0",
            "publication_date": "2026-07-20",
            "creators": [
                {
                    "name": "Quesnel, Darcy",
                    "affiliation": None,
                    "orcid": None,
                    "gnd": None,
                }
            ],
            "license": {"id": "other-open", "title": "Other (Open)"},
        },
        "links": {
            "latest": ("https://sandbox.zenodo.org/api/records/100/versions/latest"),
            "html": "https://sandbox.zenodo.org/records/100",
        },
        "files": [
            {
                "id": "historical-file-id",
                "filename": "ontario-historical.json.gz",
                "size": len(_HISTORICAL_BYTES),
                "checksum": "md5:" + "0" * 32,
                "links": {"download": _HISTORICAL_URL},
            }
        ],
    }


def _new_version_deposition(
    *, census_year: int = 2021, model_id: str = "ontario-2021-all-fields"
) -> dict:
    licensing = statcan_prepared_model_licensing(census_year)
    deposition = _deposition(licensing=licensing)
    metadata = deposition["metadata"]
    metadata["version"] = "1.0.0-corrected"
    metadata["related_identifiers"] = [
        {
            "relation": "isNewVersionOf",
            "identifier": "10.5072/zenodo.100",
            "resource_type": "dataset",
        }
    ]
    synthpopcan = deposition["synthpopcan"]
    synthpopcan.update(
        {
            "deposit_operation": "create-new-version",
            "filename": "ontario-1.0.0-corrected.json.gz",
            "existing_record_id": 100,
            "existing_concept_doi": "10.5072/zenodo.90",
            "existing_version_doi": "10.5072/zenodo.100",
            "existing_package_version": "0.9.0",
            "historical_asset": {
                "filename": "ontario-historical.json.gz",
                "sha256": _HISTORICAL_SHA256,
                "size_bytes": len(_HISTORICAL_BYTES),
                "uncompressed_size_bytes": 24,
                "uncompressed_sha256": "5" * 64,
            },
            "supersession": {
                "preserve_existing_version": True,
                "record_id": 100,
                "version_doi": "10.5072/zenodo.100",
            },
            "production_ready": True,
            "build_scope": "complete-catalogue",
            "candidate_envelope_schema": (
                "synthpopcan-zenodo-correction-candidates-v1"
            ),
            "transformation": "rights-metadata-only-top-level-field-insertion",
            "model_retrained": False,
            "historical_json_preserved_except_inserted_licensing": True,
            "package_schema_version": "synthpopcan-linked-tree-package-v1",
            "package_type": "linked_household_person",
            "census_vintage": f"{census_year} Census",
            "licensing_schema_version": synthpopcan["licensing"]["schema_version"],
        }
    )
    synthpopcan["model_id"] = model_id
    synthpopcan["historical_asset"]["contains_embedded_licensing"] = False
    synthpopcan["candidate_asset"] = {
        "filename": synthpopcan["filename"],
        "asset_url": synthpopcan["asset_url"],
        "size_bytes": synthpopcan["size_bytes"],
        "sha256": synthpopcan["sha256"],
        "uncompressed_size_bytes": synthpopcan["uncompressed_size_bytes"],
        "uncompressed_sha256": synthpopcan["uncompressed_sha256"],
        "contains_embedded_licensing": True,
    }
    return deposition


def _metadata_correction_deposition(
    *, census_year: int = 2021, model_id: str = "ontario-2021-all-fields"
) -> dict:
    licensing = statcan_prepared_model_licensing(census_year)
    deposition = _deposition(licensing=licensing)
    synthpopcan = deposition["synthpopcan"]
    synthpopcan.clear()
    synthpopcan.update(
        {
            "model_id": model_id,
            "deposit_operation": "correct-existing-metadata",
            "metadata_ready": True,
            "existing_record_id": 100,
            "existing_concept_doi": "10.5072/zenodo.90",
            "existing_version_doi": "10.5072/zenodo.100",
            "existing_package_version": "0.9.0",
            "historical_asset": {
                "filename": "ontario-historical.json.gz",
                "sha256": _HISTORICAL_SHA256,
                "size_bytes": len(_HISTORICAL_BYTES),
                "uncompressed_size_bytes": 24,
                "uncompressed_sha256": "5" * 64,
                "contains_embedded_licensing": False,
            },
            "licensing": licensing,
            "production_ready": True,
            "build_scope": "complete-catalogue",
            "candidate_envelope_schema": (
                "synthpopcan-zenodo-correction-candidates-v1"
            ),
            "transformation": "rights-metadata-only-top-level-field-insertion",
            "model_retrained": False,
            "historical_json_preserved_except_inserted_licensing": True,
            "package_schema_version": "synthpopcan-linked-tree-package-v1",
            "package_type": "linked_household_person",
            "census_vintage": f"{census_year} Census",
            "licensing_schema_version": licensing["schema_version"],
        }
    )
    deposition["metadata"]["description"] = (
        "Corrected rights metadata; the historical package remains unchanged."
    )
    deposition["metadata"]["version"] = "0.9.0"
    return deposition


def _correction_pair() -> tuple[dict, dict]:
    """Return correction/new-version manifests with the real authority binding."""

    new_version = _new_version_deposition()
    new_version_operation_id = MODULE._operation_identity(new_version)
    correction = _metadata_correction_deposition()
    correction["metadata"]["notes"] = "\n\n".join(
        (
            "Rights metadata correction for this historical package.",
            MODULE._logical_newversion_authority_marker(new_version_operation_id),
        )
    )
    correction["metadata"]["related_identifiers"] = [
        {
            "identifier": "10.5072/zenodo.90",
            "relation": "isPartOf",
            "resource_type": "software",
        },
        {
            "identifier": "https://example.invalid/source",
            "relation": "isDerivedFrom",
            "resource_type": "dataset",
        },
    ]
    return correction, new_version


def _action_intent_resume(deposition: dict) -> dict:
    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    return {
        "operation_id": operation_id,
        "deposit_operation": "correct-existing-metadata",
        "model_id": synthpopcan["model_id"],
        "package_version": synthpopcan["existing_package_version"],
        "asset_sha256": synthpopcan["historical_asset"]["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": synthpopcan["existing_record_id"],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }


def _newversion_action_intent_resume(deposition: dict) -> dict:
    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    return {
        "operation_id": operation_id,
        "deposit_operation": "create-new-version",
        "model_id": synthpopcan["model_id"],
        "package_version": deposition["metadata"]["version"],
        "asset_sha256": synthpopcan["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": synthpopcan["existing_record_id"],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }


def _authorize_legacy_fixture(monkeypatch, deposition: dict) -> None:
    """Bind the production-only recovery allow-list to a synthetic test record."""

    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    monkeypatch.setattr(
        MODULE,
        "_LEGACY_STRIPPED_MARKER_RECOVERY_OPERATION_ID",
        operation_id,
    )
    monkeypatch.setattr(
        MODULE,
        "_LEGACY_STRIPPED_MARKER_RECOVERY_RECORD_ID",
        synthpopcan["existing_record_id"],
    )
    monkeypatch.setattr(
        MODULE,
        "_LEGACY_STRIPPED_MARKER_RECOVERY_VERSION_DOI",
        synthpopcan["existing_version_doi"],
    )
    monkeypatch.setattr(
        MODULE,
        "_LEGACY_STRIPPED_MARKER_RECOVERY_CONCEPT_DOI",
        synthpopcan["existing_concept_doi"],
    )
    monkeypatch.setattr(
        MODULE, "_production_licensing_gates_are_complete", lambda: True
    )
    monkeypatch.setattr(
        MODULE, "_require_production_correction_authority", lambda *args: None
    )


def _authorize_interrupted_newversion_fixture(
    monkeypatch, deposition: dict, fake
) -> dict:
    """Bind the one-time PEI new-version recovery to a synthetic fixture."""

    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    inherited_owner = MODULE._draft_ownership(fake.existing)
    assert inherited_owner is not None
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_OPERATION_ID",
        operation_id,
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_SOURCE_RECORD_ID",
        synthpopcan["existing_record_id"],
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_SOURCE_VERSION_DOI",
        synthpopcan["existing_version_doi"],
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_CONCEPT_DOI",
        synthpopcan["existing_concept_doi"],
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_DRAFT_ID",
        fake.draft["id"],
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_DRAFT_DOI",
        fake.draft["doi"],
    )
    monkeypatch.setattr(
        MODULE,
        "_INTERRUPTED_NEWVERSION_RECOVERY_INHERITED_OWNER",
        inherited_owner,
    )
    monkeypatch.setattr(
        MODULE, "_production_licensing_gates_are_complete", lambda: True
    )
    monkeypatch.setattr(
        MODULE, "_require_production_correction_authority", lambda *args: None
    )
    return _newversion_action_intent_resume(deposition)


def _interrupted_newversion_snapshot(fake) -> dict:
    """Model the exact full inherited snapshot observed for draft 21960090."""

    fake.draft["metadata"]["publication_date"] = "2026-08-16"
    fake.draft["metadata"].pop("version", None)
    fake.draft["metadata"].pop("doi", None)
    fake.draft["metadata"].pop("conceptdoi", None)
    fake.draft["metadata"]["imprint_publisher"] = "Zenodo"
    fake.draft["metadata"]["prereserve_doi"] = {
        "doi": fake.draft["doi"],
        "recid": fake.draft["id"],
    }
    fake.draft["state"] = "unsubmitted"
    fake.draft["submitted"] = False
    return fake.draft


def _draft_listing_summary(draft: dict) -> dict:
    """Return the authenticated list shape, which omits draft files."""

    summary = json.loads(json.dumps(draft))
    summary.pop("files", None)
    return summary


def _terminal_predecessor_summary(fake) -> dict:
    return {
        **fake.existing,
        "conceptrecid": 90,
        "state": "done",
        "submitted": True,
    }


def _legacy_html_stripped_draft(
    fake, deposition: dict, *, advertise: bool = True
) -> dict:
    """Model the exact legacy edit response observed after Zenodo sanitization."""

    operation_id = MODULE._operation_identity(deposition)
    transported = MODULE._metadata_with_ownership(deposition["metadata"], operation_id)
    metadata = MODULE._remove_exact_transport_markers(
        transported,
        ownership_operation_id=operation_id,
    )
    metadata["doi"] = fake.existing["doi"]
    metadata["publication_date"] = "2026-08-16"
    metadata["imprint_publisher"] = "Zenodo"
    metadata["prereserve_doi"] = {
        "doi": fake.existing["doi"],
        "recid": fake.existing["id"],
    }
    for item in metadata.get("related_identifiers", []):
        item["scheme"] = MODULE._expected_identifier_scheme(item["identifier"])
    fake.draft["metadata"] = metadata
    fake.draft["submitted"] = True
    fake.draft["state"] = "inprogress"
    fake.edit_open = True
    if advertise:
        fake.existing["links"]["latest_draft"] = (
            f"https://sandbox.zenodo.org/api/deposit/depositions/{fake.draft['id']}"
        )
    return fake.draft


class _FakeZenodo:
    def __init__(self, deposition: dict, *, new_version: bool) -> None:
        self.deposition = deposition
        self.new_version = new_version
        self.edit_open = False
        self.calls: list[tuple[str, str]] = []
        self.existing = _existing_record()
        if new_version:
            operation_id = MODULE._operation_identity(deposition)
            source_owner = (
                "correct-existing-metadata:ontario-2021-all-fields:0.9.0:"
                + "1" * 64
                + ":"
                + "2" * 64
            )
            self.existing["metadata"]["notes"] = "\n".join(
                (
                    MODULE._ownership_marker(source_owner),
                    MODULE._durable_newversion_authority_marker(operation_id),
                )
            )
        self.draft = {
            "id": 101 if new_version else 100,
            "doi": ("10.5072/zenodo.101" if new_version else "10.5072/zenodo.100"),
            "conceptdoi": "10.5072/zenodo.90",
            "conceptrecid": 90,
            "metadata": dict(self.existing["metadata"]),
            "links": {
                "bucket": "https://sandbox.zenodo.org/api/files/new-bucket",
                "html": "https://sandbox.zenodo.org/deposit/101",
            },
            "files": [dict(item) for item in self.existing["files"]],
        }
        self.published: dict | None = None

    def request(self, method, url, *, token, payload=None, data=None):
        self.calls.append((method, url))
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return []
        if method == "GET" and url.endswith("/records/100"):
            return self.existing
        if method == "GET" and url.endswith("/records/100/versions/latest"):
            if self.new_version and self.published is not None:
                return self.published
            return self.existing
        if method == "POST" and url.endswith("/100/actions/newversion"):
            return {
                MODULE._HTTP_STATUS_KEY: 201,
                "links": {
                    "latest_draft": "https://sandbox.zenodo.org/api/deposit/depositions/101"
                },
            }
        if method == "POST" and url.endswith("/100/actions/edit"):
            self.edit_open = True
            self.draft["submitted"] = True
            self.draft["state"] = "inprogress"
            return {**self.draft, MODULE._HTTP_STATUS_KEY: 201}
        if method == "GET" and url.endswith("/deposit/depositions/101"):
            return self.draft
        if method == "GET" and url.endswith("/deposit/depositions/100"):
            if self.edit_open:
                return self.draft
            return {**self.existing, "submitted": True, "state": "done"}
        if method == "DELETE" and "/files/" in url:
            file_id = url.rsplit("/", 1)[-1]
            self.draft["files"] = [
                item for item in self.draft["files"] if str(item.get("id")) != file_id
            ]
            return {}
        if method == "PUT" and "/api/files/new-bucket/" in url:
            assert isinstance(data, bytes)
            filename = url.rsplit("/", 1)[-1]
            uploaded = {
                "id": "candidate-file-id",
                "filename": filename,
                "size": len(data),
                "checksum": "md5:"
                + hashlib.md5(data, usedforsecurity=False).hexdigest(),
                "links": {
                    "download": f"https://sandbox.zenodo.org/records/101/files/{filename}"
                },
            }
            self.draft["files"].append(uploaded)
            return uploaded
        if method == "PUT" and "/deposit/depositions/" in url:
            self.draft["metadata"] = dict(payload["metadata"])
            return self.draft
        if method == "POST" and url.endswith("/actions/publish"):
            record_id = int(url.split("/deposit/depositions/", 1)[1].split("/", 1)[0])
            public_metadata = dict(self.draft["metadata"])
            upload_type = public_metadata.pop("upload_type", None)
            if upload_type is not None:
                public_metadata["resource_type"] = {
                    "id": upload_type,
                    "title": "Dataset",
                }
            if isinstance(public_metadata.get("license"), str):
                public_metadata["license"] = {
                    "id": public_metadata["license"],
                    "title": "Other (Open)",
                }
            public_metadata["creators"] = [
                {**creator, "affiliation": None, "orcid": None, "gnd": None}
                for creator in public_metadata["creators"]
            ]
            self.published = {
                **self.draft,
                "id": record_id,
                "doi": f"10.5072/zenodo.{record_id}",
                "conceptdoi": "10.5072/zenodo.90",
                "submitted": True,
                "state": "done",
                "metadata": public_metadata,
                "links": {"html": f"https://sandbox.zenodo.org/records/{record_id}"},
            }
            if record_id == 100:
                self.existing = self.published
            return self.published
        if method == "GET" and url.endswith("/records/101"):
            assert self.published is not None
            return self.published
        raise AssertionError(f"unexpected fake Zenodo request: {method} {url}")


def test_sandbox_is_the_default_target() -> None:
    assert "sandbox.zenodo.org" in MODULE.SANDBOX_API
    assert MODULE.PRODUCTION_API == "https://zenodo.org/api"


def test_marker_transport_preserves_manifest_authority_and_operation_identity() -> None:
    correction, new_version = _correction_pair()
    operation_id = MODULE._operation_identity(correction)
    new_version_operation_id = MODULE._operation_identity(new_version)
    logical = MODULE._logical_newversion_authority_marker(new_version_operation_id)

    assert logical in correction["metadata"]["notes"]
    transported = MODULE._metadata_with_ownership(correction["metadata"], operation_id)

    assert MODULE._operation_identity(correction) == operation_id
    assert logical not in transported["notes"]
    assert MODULE._ownership_marker(operation_id) in transported["notes"]
    assert (
        MODULE._durable_newversion_authority_marker(new_version_operation_id)
        in transported["notes"]
    )
    assert MODULE._canonical_metadata(transported) == MODULE._canonical_metadata(
        correction["metadata"]
    )


@pytest.mark.parametrize(
    "notes",
    [
        MODULE._DURABLE_OWNERSHIP_PREFIX + "forged",
        MODULE._DURABLE_OWNERSHIP_PREFIX + "create-new-version:model:1.0:" + "0" * 64,
    ],
)
def test_executor_ownership_rejects_malformed_visible_markers(notes) -> None:
    with pytest.raises(MODULE.ZenodoError, match="malformed executor ownership"):
        MODULE._draft_ownership({"metadata": {"notes": notes}})


def test_executor_ownership_rejects_multiple_markers_and_ignores_forged_prose() -> None:
    operation_id = MODULE._operation_identity(_new_version_deposition())
    marker = MODULE._ownership_marker(operation_id)
    with pytest.raises(MODULE.ZenodoError, match="ambiguous executor ownership"):
        MODULE._draft_ownership({"metadata": {"notes": f"{marker}\n{marker}"}})

    forged_prose = f"Not a marker: {marker}"
    assert MODULE._draft_ownership({"metadata": {"notes": forged_prose}}) is None
    assert MODULE._canonical_metadata({"notes": forged_prose}) == {
        "notes": forged_prose
    }


def test_newversion_authority_requires_one_exact_visible_marker() -> None:
    operation_id = MODULE._operation_identity(_new_version_deposition())
    exact = MODULE._durable_newversion_authority_marker(operation_id)
    existing = {"metadata": {"notes": exact}}
    MODULE._require_newversion_authority(existing, operation_id)

    existing["metadata"]["notes"] = f"{exact}\n{exact}"
    with pytest.raises(MODULE.ZenodoError, match="ambiguous.*authority"):
        MODULE._require_newversion_authority(existing, operation_id)

    existing["metadata"]["notes"] = (
        MODULE._DURABLE_NEWVERSION_AUTHORITY_PREFIX + "forged"
    )
    with pytest.raises(MODULE.ZenodoError, match="malformed.*authority"):
        MODULE._require_newversion_authority(existing, operation_id)

    existing["metadata"]["notes"] = MODULE._logical_newversion_authority_marker(
        operation_id
    )
    with pytest.raises(MODULE.ZenodoError, match="does not authorize"):
        MODULE._require_newversion_authority(existing, operation_id)


def test_production_is_blocked_while_model_licensing_review_is_open(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MODULE, "_load_depositions", lambda only, directory=None: [_deposition()]
    )
    monkeypatch.setattr(MODULE, "_model_licensing_review_is_accepted", lambda: False)

    result = CliRunner().invoke(MODULE.main, ["--production"])

    assert result.exit_code == 2
    assert "ADR-0014" in result.output
    assert "archive-correction" in result.output


def test_production_dry_run_remains_available_during_licensing_review(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MODULE, "_load_depositions", lambda only, directory=None: [_deposition()]
    )
    monkeypatch.setattr(MODULE, "_model_licensing_review_is_accepted", lambda: False)

    result = CliRunner().invoke(MODULE.main, ["--production", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run against PRODUCTION" in result.output
    assert "no requests will be sent" in result.output


def test_model_licensing_review_requires_an_exact_accepted_status(
    tmp_path, monkeypatch
) -> None:
    decision = tmp_path / "licensing.md"
    monkeypatch.setattr(MODULE, "LICENSING_ADR", decision)

    decision.write_text("- **Status:** Proposed — review required\n")
    assert not MODULE._model_licensing_review_is_accepted()

    decision.write_text("- **Status:** Accepted\n")
    assert MODULE._model_licensing_review_is_accepted()


def test_archive_implementation_requires_a_separate_exact_completed_marker(
    tmp_path, monkeypatch
) -> None:
    decision = tmp_path / "licensing.md"
    monkeypatch.setattr(MODULE, "LICENSING_ADR", decision)

    decision.write_text(
        "- **Status:** Accepted\n- **Archive correction implementation:** Pending\n"
    )
    assert MODULE._model_licensing_review_is_accepted()
    assert not MODULE._production_licensing_gates_are_complete()

    decision.write_text(
        "- **Status:** Accepted\n- **Archive correction implementation:** Completed\n"
    )
    assert MODULE._production_licensing_gates_are_complete()


def test_adr_gates_reject_duplicate_status_and_implementation_markers(
    tmp_path, monkeypatch
) -> None:
    decision = tmp_path / "licensing.md"
    monkeypatch.setattr(MODULE, "LICENSING_ADR", decision)

    decision.write_text(
        "- **Status:** Accepted\n"
        "- **Status:** Proposed\n"
        "- **Archive correction implementation:** Completed\n"
        "- **Archive correction implementation:** Pending\n"
    )

    assert not MODULE._model_licensing_review_is_accepted()
    assert not MODULE._archive_correction_implementation_is_completed()
    assert not MODULE._production_licensing_gates_are_complete()


def test_review_only_manifest_is_rejected_before_asset_fetch(monkeypatch) -> None:
    deposition = _deposition()
    deposition["synthpopcan"]["asset_ready"] = False
    deposition["synthpopcan"]["deposit_operation"] = "review-metadata-only"
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="review-only"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert fetched == []


def test_builder_output_cannot_upload_historical_assets(monkeypatch) -> None:
    deposition = BUILD_MODULE.build_deposition(
        "ontario-2021-all-fields", concept_doi=None
    )
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="review-only"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert fetched == []


def test_test_subset_correction_manifest_is_never_executable(monkeypatch) -> None:
    deposition = _new_version_deposition()
    deposition["synthpopcan"]["production_ready"] = False
    deposition["synthpopcan"]["build_scope"] = "test-subset"
    deposition["synthpopcan"]["asset_ready"] = False
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="not production-ready"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert fetched == []


def _production_candidate(entry: dict, *, record_id: int) -> dict:
    model_id = str(entry["id"])
    historical = BUILD_MODULE.model_registry_entry(model_id)
    historical_filename = BUILD_MODULE._archive_filename(historical)
    new_version = "v1.0.0-rights.1"
    candidate_filename = (
        f"{historical_filename.removesuffix('.json.gz')}-{new_version}.json.gz"
    )
    candidate_asset = {
        "filename": candidate_filename,
        "asset_url": f"file:///tmp/{candidate_filename}",
        "size_bytes": 123,
        "sha256": "7" * 64,
        "uncompressed_size_bytes": 456,
        "uncompressed_sha256": "8" * 64,
        "contains_embedded_licensing": True,
    }
    return {
        "model_id": model_id,
        "census_vintage": str(entry["census_vintage"]),
        "package_schema_version": "synthpopcan-linked-tree-package-v1",
        "package_type": "linked_household_person",
        "existing_package_version": str(entry["release_version"]),
        "existing_record_id": record_id,
        "existing_concept_doi": str(entry["doi"]),
        "existing_version_doi": f"10.5281/zenodo.{record_id}",
        "new_package_version": new_version,
        "licensing_schema_version": entry["licensing"]["schema_version"],
        "licensing": entry["licensing"],
        "historical_asset": {
            "filename": historical_filename,
            "size_bytes": historical["size_bytes"],
            "sha256": historical["sha256"],
            "uncompressed_size_bytes": historical["uncompressed_size_bytes"],
            "uncompressed_sha256": historical["uncompressed_sha256"],
            "contains_embedded_licensing": False,
        },
        "candidate_asset": candidate_asset,
        **{
            field: candidate_asset[field]
            for field in (
                "filename",
                "asset_url",
                "size_bytes",
                "sha256",
                "uncompressed_size_bytes",
                "uncompressed_sha256",
            )
        },
        "transformation": "rights-metadata-only-top-level-field-insertion",
        "model_retrained": False,
        "historical_json_preserved_except_inserted_licensing": True,
    }


def test_all_64_generated_correction_shapes_pass_readiness(monkeypatch) -> None:
    entries = [
        entry
        for entry in BUILD_MODULE.model_catalogue()
        if entry["census_vintage"] in {"2016 Census", "2021 Census"}
    ]
    legacy_entries = []
    legacy_registry = {}
    for entry in entries:
        legacy_entry = dict(entry)
        legacy_entry["release_version"] = (
            "v0.2.1" if entry["census_vintage"] == "2016 Census" else "v0.6.0"
        )
        legacy_entries.append(legacy_entry)
        registry = BUILD_MODULE.model_registry_entry(str(entry["id"])).copy()
        registry["release_version"] = legacy_entry["release_version"]
        registry["contains_embedded_licensing"] = False
        legacy_registry[str(entry["id"])] = registry
    monkeypatch.setattr(BUILD_MODULE, "model_catalogue", lambda: legacy_entries)
    monkeypatch.setattr(
        BUILD_MODULE,
        "model_registry_entry",
        lambda model_id: legacy_registry[model_id],
    )
    manifests = []
    for index, entry in enumerate(legacy_entries, start=30_000_000):
        manifests.extend(
            BUILD_MODULE.build_correction_depositions(
                str(entry["id"]),
                _production_candidate(entry, record_id=index),
                concept_doi="10.5281/zenodo.21461463",
                production_ready=True,
                build_scope="complete-catalogue",
                envelope_new_version="v1.0.0-rights.1",
            )
        )

    assert len(legacy_entries) == 32
    assert len(manifests) == 64
    for manifest in manifests:
        MODULE._validate_correction_manifest_readiness(manifest)


@pytest.mark.parametrize(
    ("vintage", "reference_year", "model_id", "message"),
    [
        ("2021", 2021, "ontario-2021-all-fields", "vintage binding"),
        ("2020 Census", 2020, "ontario-2020-all-fields", "vintage binding"),
        ("2021 Census", "2021", "ontario-2021-all-fields", "vintage binding"),
        ("2021 Census", 2016, "ontario-2021-all-fields", "vintage binding"),
        ("2021 Census", 2021, "ontario-2016-all-fields", "model identity"),
    ],
)
def test_correction_readiness_rejects_noncanonical_vintage_bindings(
    vintage, reference_year, model_id, message
) -> None:
    deposition = _metadata_correction_deposition()
    synthpopcan = deposition["synthpopcan"]
    synthpopcan["census_vintage"] = vintage
    synthpopcan["model_id"] = model_id
    synthpopcan["licensing"]["source_information"]["product"]["reference_year"] = (
        reference_year
    )

    with pytest.raises(MODULE.ZenodoError, match=message):
        MODULE._validate_correction_manifest_readiness(deposition)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--production", "--dry-run"],
        ["--dry-run"],
    ],
)
def test_ready_correction_dry_run_preflights_before_token_or_network(
    arguments, monkeypatch
) -> None:
    invalid = _metadata_correction_deposition()
    invalid["synthpopcan"]["census_vintage"] = "2021"
    requests: list[tuple] = []
    monkeypatch.setattr(
        MODULE, "_load_depositions", lambda only, directory=None: [invalid]
    )
    monkeypatch.setattr(MODULE, "_read_correction_execution_index", lambda source: {})
    monkeypatch.setattr(
        MODULE, "_request", lambda *args, **kwargs: requests.append(args)
    )

    result = CliRunner().invoke(MODULE.main, arguments)

    assert result.exit_code == 2
    assert "correction manifest preflight failed" in result.output
    assert "Census vintage binding does not match" in result.output
    assert "ZENODO_TOKEN" not in result.output
    assert requests == []


def test_nonproduction_subset_is_sandbox_dry_run_only(monkeypatch) -> None:
    subset = _metadata_correction_deposition()
    subset["synthpopcan"]["production_ready"] = False
    subset["synthpopcan"]["build_scope"] = "test-subset"
    subset["synthpopcan"]["metadata_ready"] = False
    requests: list[tuple] = []
    monkeypatch.setattr(
        MODULE, "_load_depositions", lambda only, directory=None: [subset]
    )
    monkeypatch.setattr(MODULE, "_read_correction_execution_index", lambda source: {})
    monkeypatch.setattr(
        MODULE, "_request", lambda *args, **kwargs: requests.append(args)
    )

    review = CliRunner().invoke(MODULE.main, ["--dry-run"])
    write = CliRunner().invoke(MODULE.main, [])

    assert review.exit_code == 0
    assert "Dry run against sandbox" in review.output
    assert "review-only metadata" in review.output
    assert write.exit_code == 2
    assert "bounded bundles are dry-run only" in write.output
    assert "ZENODO_SANDBOX_TOKEN" not in write.output
    assert requests == []


def test_new_version_rejects_overwriting_the_historical_filename(monkeypatch) -> None:
    deposition = _new_version_deposition()
    deposition["synthpopcan"]["filename"] = "ontario-historical.json.gz"
    deposition["synthpopcan"]["candidate_asset"]["filename"] = (
        "ontario-historical.json.gz"
    )
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="must not overwrite"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert fetched == []


def test_new_version_uses_existing_record_action_and_preserves_predecessor(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    historical_verifications: list[dict] = []
    monkeypatch.setattr(
        MODULE,
        "_verify_remote_download",
        lambda *args, **kwargs: historical_verifications.append(kwargs),
    )

    result = MODULE.deposit_one(
        deposition, api=MODULE.SANDBOX_API, token="t", publish=True
    )

    assert result["state"] == "verified"
    assert result["concept_doi"] == "10.5072/zenodo.90"
    assert result["doi"] == "10.5072/zenodo.101"
    assert result["supersedes"]["version_doi"] == "10.5072/zenodo.100"
    assert any(url.endswith("/100/actions/newversion") for _, url in fake.calls)
    assert any(
        method == "DELETE" and url.endswith("/101/files/historical-file-id")
        for method, url in fake.calls
    )
    assert fake.existing["files"][0]["filename"] == "ontario-historical.json.gz"
    assert [item["filename"] for item in fake.published["files"]] == [
        "ontario-1.0.0-corrected.json.gz"
    ]
    assert result["registry_update"]["url"].endswith("/ontario-1.0.0-corrected.json.gz")
    assert len(historical_verifications) == 3
    assert {
        "expected_size": len(payload),
        "expected_sha256": hashlib.sha256(payload).hexdigest(),
    } in historical_verifications
    publish_index = next(
        index
        for index, (_, url) in enumerate(fake.calls)
        if url.endswith("/actions/publish")
    )
    latest_indices = [
        index
        for index, (_, url) in enumerate(fake.calls)
        if url.endswith("/records/100/versions/latest")
    ]
    assert latest_indices[0] < publish_index < latest_indices[-1]


def test_metadata_correction_preserves_record_identity_and_never_fetches_asset(
    monkeypatch,
) -> None:
    deposition = _metadata_correction_deposition()
    fake = _FakeZenodo(deposition, new_version=False)
    fetched: list[bool] = []
    historical_verifications: list[dict] = []
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: fetched.append(True))
    monkeypatch.setattr(
        MODULE,
        "_verify_remote_download",
        lambda *args, **kwargs: historical_verifications.append(kwargs),
    )

    result = MODULE.deposit_one(
        deposition, api=MODULE.SANDBOX_API, token="t", publish=True
    )

    assert fetched == []
    assert result["state"] == "verified"
    assert result["deposition_id"] == 100
    assert result["doi"] == "10.5072/zenodo.100"
    assert result["concept_doi"] == "10.5072/zenodo.90"
    assert "registry_update" not in result
    assert any(url.endswith("/100/actions/edit") for _, url in fake.calls)
    assert len(historical_verifications) == 2


def test_metadata_correction_rejects_unrelated_creator_change(monkeypatch) -> None:
    deposition = _metadata_correction_deposition()
    deposition["metadata"]["creators"] = [{"name": "Unrelated Person"}]
    fake = _FakeZenodo(deposition, new_version=False)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="preserve existing creators"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any("actions/edit" in url for _, url in fake.calls)


def test_new_version_preserves_concept_identity_metadata(monkeypatch) -> None:
    deposition = _new_version_deposition()
    deposition["metadata"]["creators"] = [{"name": "Unrelated Person"}]
    fake = _FakeZenodo(deposition, new_version=True)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="preserve existing creators"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any("actions/newversion" in url for _, url in fake.calls)


def test_newversion_binds_predecessor_package_version_before_action(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    fake.existing["metadata"]["version"] = "unexpected-source-version"
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError, match="predecessor package version"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_unowned_latest_draft_is_never_claimed_or_mutated(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    fake.existing["links"]["latest_draft"] = (
        "https://sandbox.zenodo.org/api/deposit/depositions/101"
    )
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="not owned"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_newversion_action_must_prove_it_created_the_unclaimed_draft(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)

    def request(method, url, **kwargs):
        response = fake.request(method, url, **kwargs)
        if method == "POST" and url.endswith("/100/actions/newversion"):
            response[MODULE._HTTP_STATUS_KEY] = 200
        return response

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="did not prove creation"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_repeated_newversion_201_cannot_claim_a_modified_unowned_draft(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    fake.draft["metadata"]["description"] = "Unrelated draft owner's change"
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="not an exact source snapshot"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_repeated_newversion_201_cannot_claim_untouched_preauthorization_draft(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    notes = fake.draft["metadata"]["notes"].splitlines()
    fake.draft["metadata"]["notes"] = "\n".join(
        line
        for line in notes
        if not line.startswith(MODULE._DURABLE_NEWVERSION_AUTHORITY_PREFIX)
    )
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="not an exact source snapshot"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_action_created_newversion_accepts_only_date_advance_and_missing_version(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    _interrupted_newversion_snapshot(fake)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=False,
    )

    assert result["state"] == "draft"
    assert sum(url.endswith("/100/actions/newversion") for _, url in fake.calls) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("publication_date", "2026-07-19"),
        ("publication_date", "2026-13-01"),
        ("publication_date", None),
        ("version", "unrelated-version"),
    ],
)
def test_action_created_newversion_rejects_other_snapshot_differences(
    field,
    value,
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    _interrupted_newversion_snapshot(fake)
    if value is None:
        fake.draft["metadata"].pop(field, None)
    else:
        fake.draft["metadata"][field] = value
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert sum(url.endswith("/100/actions/newversion") for _, url in fake.calls) == 1
    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_untouched_snapshot_normalizes_legacy_filesize() -> None:
    existing = _existing_record()
    draft = json.loads(json.dumps(existing))
    size = draft["files"][0].pop("size")
    draft["files"][0]["filesize"] = size

    MODULE._assert_unclaimed_draft_snapshot(draft, existing)


def test_untouched_snapshot_accepts_real_legacy_edit_draft_shape() -> None:
    existing = _existing_record()
    draft = json.loads(json.dumps(existing))
    existing["metadata"]["relations"] = {
        "version": [
            {
                "index": 0,
                "is_last": True,
                "parent": {"pid_type": "recid", "pid_value": "90"},
            }
        ]
    }
    draft["metadata"]["imprint_publisher"] = "Zenodo"
    draft["metadata"]["prereserve_doi"] = {"doi": existing["doi"]}
    draft["files"][0]["filesize"] = draft["files"][0].pop("size")
    draft["files"][0]["checksum"] = draft["files"][0]["checksum"].removeprefix("md5:")

    MODULE._assert_unclaimed_draft_snapshot(draft, existing)


@pytest.mark.parametrize(
    "draft_checksum",
    [
        "MD5:" + "0" * 32,
        "sha256:" + "0" * 32,
        "md5:" + "0" * 31,
        "md5:" + "0" * 31 + "1",
        "1" * 32,
    ],
)
def test_unclaimed_snapshot_rejects_nonexact_or_changed_md5_forms(
    draft_checksum,
) -> None:
    existing = _existing_record()
    draft = json.loads(json.dumps(existing))
    draft["files"][0]["checksum"] = draft_checksum

    with pytest.raises(MODULE.ZenodoError, match="untouched source snapshot"):
        MODULE._assert_unclaimed_draft_snapshot(draft, existing)


@pytest.mark.parametrize(
    ("side", "field"),
    [("draft", "relations"), ("existing", "imprint_publisher")],
)
def test_unclaimed_snapshot_rejects_derived_fields_on_the_wrong_side(
    side, field
) -> None:
    existing = _existing_record()
    draft = json.loads(json.dumps(existing))
    record = draft if side == "draft" else existing
    record["metadata"][field] = {"unexpected": "substantive"}

    with pytest.raises(MODULE.ZenodoError, match="not an untouched snapshot"):
        MODULE._assert_unclaimed_draft_snapshot(draft, existing)


@pytest.mark.parametrize("extra", ["malformed", None])
def test_unclaimed_snapshot_rejects_extra_or_malformed_files(extra) -> None:
    existing = _existing_record()
    draft = json.loads(json.dumps(existing))
    draft["files"].append(
        json.loads(json.dumps(draft["files"][0])) if extra is None else extra
    )

    with pytest.raises(
        MODULE.ZenodoError, match="source snapshot|malformed source files"
    ):
        MODULE._assert_unclaimed_draft_snapshot(draft, existing)


def test_action_intent_does_not_claim_an_advertised_unowned_edit(
    monkeypatch,
) -> None:
    deposition = _metadata_correction_deposition()
    fake = _FakeZenodo(deposition, new_version=False)
    fake.existing["links"]["latest_draft"] = (
        "https://sandbox.zenodo.org/api/deposit/depositions/100"
    )
    fake.existing["metadata"]["relations"] = {
        "version": [{"index": 0, "is_last": True}]
    }
    fake.draft["metadata"]["imprint_publisher"] = "Zenodo"
    fake.draft["metadata"]["prereserve_doi"] = {"doi": fake.draft["doi"]}
    fake.draft["files"][0]["checksum"] = fake.draft["files"][0][
        "checksum"
    ].removeprefix("md5:")
    operation_id = MODULE._operation_identity(deposition)
    resume = {
        "operation_id": operation_id,
        "deposit_operation": "correct-existing-metadata",
        "model_id": deposition["synthpopcan"]["model_id"],
        "package_version": deposition["synthpopcan"]["existing_package_version"],
        "asset_sha256": deposition["synthpopcan"]["historical_asset"]["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": 100,
        "source_publication_date": "2026-07-20",
        "state": "action-intent",
        "uploaded_bytes": 0,
    }
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="not owned"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            resume=resume,
        )

    assert not any("actions/edit" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_action_intent_refuses_a_modified_unowned_edit(monkeypatch) -> None:
    deposition = _metadata_correction_deposition()
    fake = _FakeZenodo(deposition, new_version=False)
    fake.existing["links"]["latest_draft"] = (
        "https://sandbox.zenodo.org/api/deposit/depositions/100"
    )
    fake.draft["metadata"]["title"] = "Someone else's draft"
    operation_id = MODULE._operation_identity(deposition)
    resume = {
        "operation_id": operation_id,
        "deposit_operation": "correct-existing-metadata",
        "model_id": deposition["synthpopcan"]["model_id"],
        "package_version": deposition["synthpopcan"]["existing_package_version"],
        "asset_sha256": deposition["synthpopcan"]["historical_asset"]["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": 100,
        "source_publication_date": "2026-07-20",
        "state": "action-intent",
        "uploaded_bytes": 0,
    }
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="not owned"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            resume=resume,
        )

    assert not any(method in {"PUT", "DELETE"} for method, _ in fake.calls)


def test_exact_legacy_html_stripped_claim_is_recovered_without_an_edit_action(
    monkeypatch,
) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(fake, deposition, advertise=False)
    operation_id = MODULE._operation_identity(deposition)
    _authorize_legacy_fixture(monkeypatch, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.PRODUCTION_API,
        token="t",
        publish=False,
        resume=_action_intent_resume(deposition),
    )

    assert result["state"] == "draft"
    assert result["source_publication_date"] == "2026-07-20"
    assert not any("actions/edit" in url for _, url in fake.calls)
    assert MODULE._draft_ownership(fake.draft) == operation_id
    assert fake.draft["metadata"]["publication_date"] == "2026-07-20"
    new_version_operation_id = MODULE._operation_identity(_correction_pair()[1])
    MODULE._require_newversion_authority(fake.draft, new_version_operation_id)


def test_exact_legacy_recovery_reads_known_draft_before_any_repeat_edit(
    monkeypatch,
) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(fake, deposition, advertise=False)
    _authorize_legacy_fixture(monkeypatch, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.PRODUCTION_API,
        token="t",
        publish=False,
        resume=_action_intent_resume(deposition),
    )

    assert result["state"] == "draft"
    assert any(
        method == "GET" and url.endswith("/deposit/depositions/100")
        for method, url in fake.calls
    )
    assert not any("actions/edit" in url for _, url in fake.calls)
    assert fake.draft["metadata"]["publication_date"] == "2026-07-20"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Someone else's draft"),
        ("imprint_publisher", "Untrusted archive"),
        ("doi", "10.5072/zenodo.999"),
    ],
)
def test_legacy_recovery_refuses_any_metadata_delta(field, value, monkeypatch) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    draft = _legacy_html_stripped_draft(fake, deposition, advertise=False)
    draft["metadata"][field] = value
    _authorize_legacy_fixture(monkeypatch, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="legacy recovery"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=_action_intent_resume(deposition),
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


@pytest.mark.parametrize(
    "missing",
    ["doi", "publication_date", "imprint_publisher", "prereserve_doi", "scheme"],
)
def test_legacy_recovery_requires_the_exact_observed_server_shape(
    missing, monkeypatch
) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    draft = _legacy_html_stripped_draft(fake, deposition, advertise=False)
    if missing == "scheme":
        draft["metadata"]["related_identifiers"][0].pop("scheme")
    else:
        draft["metadata"].pop(missing)
    _authorize_legacy_fixture(monkeypatch, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="legacy recovery"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=_action_intent_resume(deposition),
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


@pytest.mark.parametrize(
    ("state", "submitted"),
    [("done", True), ("inprogress", False), (None, True)],
)
def test_legacy_recovery_requires_the_exact_open_edit_envelope(
    state, submitted, monkeypatch
) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    draft = _legacy_html_stripped_draft(fake, deposition, advertise=False)
    draft["state"] = state
    draft["submitted"] = submitted
    _authorize_legacy_fixture(monkeypatch, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    with pytest.raises(MODULE.ZenodoError, match="exact open edit state"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=_action_intent_resume(deposition),
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_legacy_recovery_refuses_changed_files_or_checkpoint(monkeypatch) -> None:
    deposition, _ = _correction_pair()
    _authorize_legacy_fixture(monkeypatch, deposition)

    changed_file = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(changed_file, deposition, advertise=False)
    changed_file.draft["files"][0]["size"] += 1
    monkeypatch.setattr(MODULE, "_request", changed_file.request)
    with pytest.raises(MODULE.ZenodoError, match="untouched source snapshot"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=_action_intent_resume(deposition),
        )
    assert not any(
        method in {"PUT", "DELETE", "POST"} for method, _ in changed_file.calls
    )

    changed_checkpoint = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(changed_checkpoint, deposition, advertise=False)
    monkeypatch.setattr(MODULE, "_request", changed_checkpoint.request)
    resume = _action_intent_resume(deposition)
    resume["uploaded_bytes"] = 1
    with pytest.raises(MODULE.ZenodoError, match="exact action intent"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=resume,
        )
    assert not any(
        method in {"PUT", "DELETE", "POST"} for method, _ in changed_checkpoint.calls
    )


def test_legacy_recovery_does_not_adopt_an_unlisted_operation(monkeypatch) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(fake, deposition)
    monkeypatch.setattr(MODULE, "_request", fake.request)

    resume = _action_intent_resume(deposition)
    resume["source_publication_date"] = "2026-07-20"
    with pytest.raises(MODULE.ZenodoError, match="not owned"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            resume=resume,
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_legacy_claim_crash_resumes_from_durable_owner_without_new_edit(
    monkeypatch,
) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)
    _legacy_html_stripped_draft(fake, deposition, advertise=False)
    operation_id = MODULE._operation_identity(deposition)
    _authorize_legacy_fixture(monkeypatch, deposition)
    interrupted = False

    class Interrupted(RuntimeError):
        pass

    def request(method, url, **kwargs):
        nonlocal interrupted
        response = fake.request(method, url, **kwargs)
        if method == "PUT" and not interrupted:
            interrupted = True
            raise Interrupted
        return response

    monkeypatch.setattr(MODULE, "_request", request)
    resume = _action_intent_resume(deposition)
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=False,
            resume=resume,
        )
    assert MODULE._draft_ownership(fake.draft) == operation_id
    fake.draft["metadata"]["doi"] = fake.existing["doi"]
    fake.draft["metadata"]["imprint_publisher"] = "Zenodo"
    fake.draft["metadata"]["prereserve_doi"] = {
        "doi": fake.existing["doi"],
        "recid": fake.existing["id"],
    }
    for item in fake.draft["metadata"]["related_identifiers"]:
        item["scheme"] = MODULE._expected_identifier_scheme(item["identifier"])

    monkeypatch.setattr(MODULE, "_request", fake.request)
    result = MODULE.deposit_one(
        deposition,
        api=MODULE.PRODUCTION_API,
        token="t",
        publish=False,
        resume=resume,
    )

    assert result["state"] == "draft"
    assert not any("actions/edit" in url for _, url in fake.calls)


def test_published_metadata_authority_enables_the_bound_newversion(monkeypatch) -> None:
    correction, new_version = _correction_pair()
    correction_fake = _FakeZenodo(correction, new_version=False)
    monkeypatch.setattr(MODULE, "_request", correction_fake.request)
    corrected = MODULE.deposit_one(
        correction,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
    )
    assert corrected["state"] == "verified"
    new_version_operation_id = MODULE._operation_identity(new_version)
    MODULE._require_newversion_authority(
        correction_fake.existing, new_version_operation_id
    )

    new_fake = _FakeZenodo(new_version, new_version=True)
    new_fake.existing = json.loads(json.dumps(correction_fake.existing))
    new_fake.existing["links"]["latest"] = (
        "https://sandbox.zenodo.org/api/records/100/versions/latest"
    )
    new_fake.draft["metadata"] = json.loads(json.dumps(new_fake.existing["metadata"]))
    new_fake.draft["files"] = json.loads(json.dumps(new_fake.existing["files"]))
    monkeypatch.setattr(MODULE, "_request", new_fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    versioned = MODULE.deposit_one(
        new_version,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
    )

    assert versioned["state"] == "verified"
    assert versioned["concept_doi"] == "10.5072/zenodo.90"


def test_submitted_inprogress_metadata_edit_resume_publishes_once(monkeypatch) -> None:
    deposition = _metadata_correction_deposition()
    fake = _FakeZenodo(deposition, new_version=False)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    draft = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=False,
    )
    assert draft["state"] == "draft"
    fake.draft["submitted"] = True
    fake.draft["state"] = "inprogress"
    fake.calls.clear()

    verified = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=draft,
    )

    assert verified["state"] == "verified"
    assert sum(url.endswith("/actions/publish") for _, url in fake.calls) == 1
    assert verified["source_publication_date"] == "2026-07-20"


def test_final_metadata_put_that_loses_owner_is_never_published(monkeypatch) -> None:
    deposition, _ = _correction_pair()
    fake = _FakeZenodo(deposition, new_version=False)

    def request(method, url, **kwargs):
        response = fake.request(method, url, **kwargs)
        if method == "PUT" and "/deposit/depositions/" in url:
            notes = fake.draft["metadata"]["notes"].splitlines()
            fake.draft["metadata"]["notes"] = "\n".join(
                line
                for line in notes
                if not line.startswith(MODULE._DURABLE_OWNERSHIP_PREFIX)
            )
            return fake.draft
        return response

    monkeypatch.setattr(MODULE, "_request", request)
    with pytest.raises(MODULE.ZenodoError, match="not owned"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
        )

    assert not any(url.endswith("/actions/publish") for _, url in fake.calls)


def test_owned_newversion_with_extra_file_fails_before_mutation(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    checkpoints: list[dict] = []

    class Interrupted(RuntimeError):
        pass

    def stop_created(result):
        checkpoints.append(result)
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=stop_created,
        )
    fake.draft["files"].append(
        {
            "id": "unrelated",
            "filename": "unrelated.txt",
            "size": 1,
            "checksum": "0" * 32,
        }
    )
    fake.calls.clear()

    with pytest.raises(MODULE.ZenodoError, match="unexpected inherited file"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=checkpoints[-1],
        )

    assert not any(method in {"DELETE", "PUT", "POST"} for method, _ in fake.calls)


def test_resume_rejects_wrong_bare_candidate_md5_before_delete(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    checkpoints: list[dict] = []
    payload = _payload(deposition)[0]

    class Interrupted(RuntimeError):
        pass

    def stop_created(result):
        checkpoints.append(result)
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=stop_created,
        )
    filename = deposition["synthpopcan"]["filename"]
    fake.request(
        "PUT",
        f"{fake.draft['links']['bucket']}/{filename}",
        token="t",
        data=payload,
    )
    fake.draft["files"][-1]["checksum"] = "0" * 32
    fake.calls.clear()

    with pytest.raises(MODULE.ZenodoError, match="checksum mismatch"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=checkpoints[-1],
        )

    assert not any(method in {"DELETE", "PUT", "POST"} for method, _ in fake.calls)


def test_metadata_publish_before_checkpoint_resumes_without_republishing(
    monkeypatch,
) -> None:
    deposition = _metadata_correction_deposition()
    fake = _FakeZenodo(deposition, new_version=False)
    checkpoints: list[dict] = []
    interrupted = False

    class Interrupted(RuntimeError):
        pass

    def request(method, url, **kwargs):
        nonlocal interrupted
        response = fake.request(method, url, **kwargs)
        if method == "POST" and url.endswith("/actions/publish") and not interrupted:
            interrupted = True
            assert fake.published is not None
            fake.draft = {**fake.published, "submitted": True, "state": "done"}
            raise Interrupted
        return response

    monkeypatch.setattr(MODULE, "_request", request)
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=lambda result: checkpoints.append(result),
        )
    assert checkpoints[-1]["state"] == "draft"

    verified = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=checkpoints[-1],
    )

    assert verified["state"] == "verified"
    assert sum(url.endswith("/actions/publish") for _, url in fake.calls) == 1
    assert verified["source_publication_date"] == "2026-07-20"


def test_newversion_preflight_rejects_an_unowned_concept_draft(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [fake.draft]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    with pytest.raises(MODULE.ZenodoError, match="unowned or ambiguous"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any("actions/newversion" in url for _, url in fake.calls)


def test_newversion_preflight_ignores_exact_submitted_terminal_predecessor(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    terminal_predecessor = {
        **fake.existing,
        "conceptrecid": 90,
        "state": "done",
        "submitted": True,
    }

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [terminal_predecessor]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=False,
    )

    assert result["state"] == "draft"
    assert sum(url.endswith("/100/actions/newversion") for _, url in fake.calls) == 1


@pytest.mark.parametrize(
    "terminal_change",
    [
        {"id": 999},
        {"doi": "10.5072/zenodo.999"},
        {"conceptdoi": "10.5072/zenodo.999"},
        {"conceptrecid": 999},
        {"submitted": False},
        {"state": "published"},
    ],
)
def test_newversion_preflight_rejects_mismatched_terminal_listing_before_action(
    terminal_change,
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    terminal_predecessor = {
        **fake.existing,
        "conceptrecid": 90,
        "state": "done",
        "submitted": True,
        **terminal_change,
    }

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [terminal_predecessor]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_newversion_preflight_rejects_duplicate_terminal_predecessor(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    terminal_predecessor = {
        **fake.existing,
        "conceptrecid": 90,
        "state": "done",
        "submitted": True,
    }

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [terminal_predecessor, terminal_predecessor]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError, match="unexpected terminal"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any("actions/newversion" in url for _, url in fake.calls)


def test_terminal_predecessor_does_not_mask_an_unowned_open_draft(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    terminal_predecessor = {
        **fake.existing,
        "conceptrecid": 90,
        "state": "done",
        "submitted": True,
    }

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [terminal_predecessor, fake.draft]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError, match="unowned or ambiguous"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any("actions/newversion" in url for _, url in fake.calls)
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_exact_interrupted_newversion_fetches_full_summary_then_claims(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    _interrupted_newversion_snapshot(fake)
    resume = _authorize_interrupted_newversion_fixture(
        monkeypatch,
        deposition,
        fake,
    )
    summary = _draft_listing_summary(fake.draft)
    checkpoints: list[dict] = []

    class Interrupted(RuntimeError):
        pass

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [_terminal_predecessor_summary(fake), summary]
        return fake.request(method, url, **kwargs)

    def stop_after_claim(result):
        checkpoints.append(result)
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=True,
            resume=resume,
            checkpoint=stop_after_claim,
        )

    assert checkpoints[-1]["deposition_id"] == fake.draft["id"]
    assert MODULE._draft_ownership(fake.draft) == MODULE._operation_identity(deposition)
    assert (
        sum(
            url.endswith(f"/deposit/depositions/{fake.draft['id']}")
            for method, url in fake.calls
            if method == "GET"
        )
        >= 2
    )
    assert (
        sum(
            url.endswith(f"/deposit/depositions/{fake.draft['id']}")
            for method, url in fake.calls
            if method == "PUT"
        )
        == 1
    )
    assert not any(method == "DELETE" for method, _ in fake.calls)
    assert not any(
        "/api/files/" in url for method, url in fake.calls if method == "PUT"
    )
    assert not any("actions/publish" in url for _, url in fake.calls)


def test_current_owner_newversion_summary_is_refetched_before_resume(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    operation_id = MODULE._operation_identity(deposition)
    fake.draft["metadata"] = MODULE._metadata_with_ownership(
        deposition["metadata"],
        operation_id,
    )
    fake.draft["state"] = "unsubmitted"
    fake.draft["submitted"] = False
    summary = _draft_listing_summary(fake.draft)

    class Interrupted(RuntimeError):
        pass

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [_terminal_predecessor_summary(fake), summary]
        return fake.request(method, url, **kwargs)

    def stop_at_created(result):
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=_newversion_action_intent_resume(deposition),
            checkpoint=stop_at_created,
        )

    assert (
        sum(
            url.endswith(f"/deposit/depositions/{fake.draft['id']}")
            for method, url in fake.calls
            if method == "GET"
        )
        >= 2
    )
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


@pytest.mark.parametrize(
    "tampering",
    [
        "draft-id",
        "draft-doi",
        "publication-date",
        "version",
        "state",
        "submitted",
        "files",
        "owner",
        "checkpoint",
        "metadata-doi",
        "metadata-conceptdoi",
        "imprint-missing",
        "imprint-wrong",
        "prereserve-missing",
        "prereserve-wrong",
    ],
)
def test_interrupted_newversion_recovery_rejects_every_nonexact_binding(
    tampering,
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    _interrupted_newversion_snapshot(fake)
    resume = _authorize_interrupted_newversion_fixture(
        monkeypatch,
        deposition,
        fake,
    )
    if tampering == "draft-id":
        fake.draft["id"] += 1
    elif tampering == "draft-doi":
        fake.draft["doi"] = "10.5072/zenodo.999"
    elif tampering == "publication-date":
        fake.draft["metadata"]["publication_date"] = "2026-08-17"
    elif tampering == "version":
        fake.draft["metadata"]["version"] = fake.existing["metadata"]["version"]
    elif tampering == "state":
        fake.draft["state"] = "inprogress"
    elif tampering == "submitted":
        fake.draft["submitted"] = True
    elif tampering == "files":
        fake.draft["files"][0]["size"] += 1
    elif tampering == "owner":
        inherited_owner = MODULE._draft_ownership(fake.existing)
        assert inherited_owner is not None
        fake.draft["metadata"]["notes"] = fake.draft["metadata"]["notes"].replace(
            MODULE._ownership_marker(inherited_owner),
            MODULE._ownership_marker(MODULE._operation_identity(deposition)),
        )
    elif tampering == "checkpoint":
        resume["uploaded_bytes"] = 1
    elif tampering == "metadata-doi":
        fake.draft["metadata"]["doi"] = fake.draft["doi"]
    elif tampering == "metadata-conceptdoi":
        fake.draft["metadata"]["conceptdoi"] = fake.draft["conceptdoi"]
    elif tampering == "imprint-missing":
        fake.draft["metadata"].pop("imprint_publisher")
    elif tampering == "imprint-wrong":
        fake.draft["metadata"]["imprint_publisher"] = "Other"
    elif tampering == "prereserve-missing":
        fake.draft["metadata"].pop("prereserve_doi")
    elif tampering == "prereserve-wrong":
        fake.draft["metadata"]["prereserve_doi"]["recid"] += 1
    else:  # pragma: no cover - parameter exhaustiveness
        raise AssertionError(tampering)
    summary = _draft_listing_summary(fake.draft)

    def request(method, url, **kwargs):
        if method == "GET" and "/deposit/depositions?status=draft" in url:
            return [_terminal_predecessor_summary(fake), summary]
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError):
        MODULE.deposit_one(
            deposition,
            api=MODULE.PRODUCTION_API,
            token="t",
            publish=True,
            resume=resume,
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_newversion_action_intent_with_no_remote_draft_claims_created_action(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    resume = {
        "operation_id": operation_id,
        "deposit_operation": "create-new-version",
        "model_id": synthpopcan["model_id"],
        "package_version": deposition["metadata"]["version"],
        "asset_sha256": synthpopcan["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": synthpopcan["existing_record_id"],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=False,
        resume=resume,
    )

    assert result["state"] == "draft"
    assert MODULE._draft_ownership(fake.draft) == operation_id
    assert sum(url.endswith("/100/actions/newversion") for _, url in fake.calls) == 1


def test_resume_rejects_tampered_static_operation_before_remote_mutation(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    operation_id = MODULE._operation_identity(deposition)
    synthpopcan = deposition["synthpopcan"]
    resume = {
        "operation_id": operation_id,
        "deposit_operation": "create-new-record",
        "model_id": synthpopcan["model_id"],
        "package_version": deposition["metadata"]["version"],
        "asset_sha256": synthpopcan["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": synthpopcan["existing_record_id"],
        "state": "action-intent",
        "uploaded_bytes": 0,
    }
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(MODULE.ZenodoError, match="checkpoint deposit_operation"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=resume,
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_owned_resume_rebinds_parent_before_file_mutation(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    checkpoints: list[dict] = []

    class Interrupted(RuntimeError):
        pass

    def stop_at_created(result):
        checkpoints.append(result)
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            checkpoint=stop_at_created,
        )

    fake.calls.clear()
    fake.draft["conceptrecid"] = 999
    with pytest.raises(MODULE.ZenodoError, match="parent concept"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            resume=checkpoints[-1],
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_owned_resume_rejects_mismatched_bucket_before_file_mutation(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    checkpoints: list[dict] = []

    class Interrupted(RuntimeError):
        pass

    def stop_at_created(result):
        checkpoints.append(result)
        if result["state"] == "created":
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            checkpoint=stop_at_created,
        )

    resume = checkpoints[-1].copy()
    resume["bucket_url"] = "https://attacker.invalid/api/files/stolen"
    fake.calls.clear()
    with pytest.raises(MODULE.ZenodoError, match="checkpoint upload bucket"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
            resume=resume,
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)
    assert not any("attacker.invalid" in url for _, url in fake.calls)


@pytest.mark.parametrize("interrupted_state", ["created", "uploaded"])
def test_new_version_resumes_interrupted_created_and_uploaded_states(
    interrupted_state, monkeypatch
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    checkpoints: list[dict] = []
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    class Interrupted(RuntimeError):
        pass

    def stop_at(result):
        checkpoints.append(result)
        if result["state"] == interrupted_state:
            raise Interrupted

    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=stop_at,
        )

    resume = checkpoints[-1]
    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=resume,
    )

    assert result["state"] == "verified"
    assert sum(url.endswith("/100/actions/newversion") for _, url in fake.calls) == 1
    assert sum("/api/files/new-bucket/" in url for _, url in fake.calls) == 1


@pytest.mark.parametrize("interrupted_state", ["created", "uploaded", "draft"])
def test_nonterminal_newversion_resume_requires_predecessor_still_latest(
    interrupted_state,
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    checkpoints: list[dict] = []

    class Interrupted(RuntimeError):
        pass

    def stop_at(result):
        checkpoints.append(result)
        if result["state"] == interrupted_state:
            raise Interrupted

    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)
    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=stop_at,
        )

    def stale_latest_request(method, url, **kwargs):
        if method == "GET" and url.endswith("/records/100/versions/latest"):
            fake.calls.append((method, url))
            return {
                "id": 999,
                "doi": "10.5072/zenodo.999",
                "conceptdoi": "10.5072/zenodo.90",
            }
        return fake.request(method, url, **kwargs)

    monkeypatch.setattr(MODULE, "_request", stale_latest_request)
    fake.calls.clear()
    with pytest.raises(MODULE.ZenodoError, match="latest record"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=checkpoints[-1],
        )

    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_resume_recovers_upload_that_preceded_its_checkpoint(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    operation_id = MODULE._operation_identity(deposition)
    fake.draft["metadata"] = MODULE._metadata_with_ownership(
        deposition["metadata"], operation_id
    )
    resume = {
        "operation_id": operation_id,
        "deposit_operation": "create-new-version",
        "model_id": deposition["synthpopcan"]["model_id"],
        "package_version": deposition["metadata"]["version"],
        "asset_sha256": deposition["synthpopcan"]["sha256"],
        "metadata_sha256": operation_id.rsplit(":", 1)[-1],
        "source_record_id": deposition["synthpopcan"]["existing_record_id"],
        "deposition_id": 101,
        "state": "created",
        "bucket_url": fake.draft["links"]["bucket"],
        "uploaded_bytes": 0,
    }
    filename = deposition["synthpopcan"]["filename"]
    # Model the real crash window: inherited files were deleted, the candidate
    # upload succeeded, and the uploaded checkpoint was not yet persisted.
    fake.draft["files"] = []
    fake.request(
        "PUT",
        f"{fake.draft['links']['bucket']}/{filename}",
        token="t",
        data=payload,
    )

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=resume,
    )

    assert result["state"] == "verified"
    assert sum("/api/files/new-bucket/" in url for _, url in fake.calls) == 1


def test_resume_detects_publish_that_preceded_its_checkpoint(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    payload = _payload(deposition)[0]
    checkpoints: list[dict] = []
    publish_interrupted = False

    class Interrupted(RuntimeError):
        pass

    def request(method, url, **kwargs):
        nonlocal publish_interrupted
        response = fake.request(method, url, **kwargs)
        if (
            method == "POST"
            and url.endswith("/actions/publish")
            and not publish_interrupted
        ):
            publish_interrupted = True
            assert fake.published is not None
            fake.draft = {**fake.published, "submitted": True, "state": "done"}
            raise Interrupted
        return response

    monkeypatch.setattr(MODULE, "_request", request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: payload)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    with pytest.raises(Interrupted):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            checkpoint=lambda result: checkpoints.append(result),
        )
    assert checkpoints[-1]["state"] == "draft"

    result = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=checkpoints[-1],
    )

    assert result["state"] == "verified"
    assert sum(url.endswith("/actions/publish") for _, url in fake.calls) == 1


@pytest.mark.parametrize(
    ("deposition_factory", "new_version", "rolled_back_state"),
    [
        (_metadata_correction_deposition, False, "editing"),
        (_metadata_correction_deposition, False, "draft"),
        (_new_version_deposition, True, "created"),
        (_new_version_deposition, True, "uploaded"),
        (_new_version_deposition, True, "draft"),
    ],
)
def test_terminal_remote_recovers_from_any_mutable_checkpoint_without_writes(
    monkeypatch,
    deposition_factory,
    new_version,
    rolled_back_state,
) -> None:
    deposition = deposition_factory()
    fake = _FakeZenodo(deposition, new_version=new_version)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)
    verified = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
    )
    assert fake.published is not None
    fake.draft = {**fake.published, "submitted": True, "state": "done"}
    resume = {**verified, "state": rolled_back_state}
    resume.pop("verified", None)

    fake.calls.clear()
    recovered = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=resume,
    )

    assert recovered["state"] == "verified"
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_draft_checkpoint_keeps_durable_ownership_for_resume(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    first = MODULE.deposit_one(
        deposition, api=MODULE.SANDBOX_API, token="t", publish=False
    )
    operation_id = MODULE._operation_identity(deposition)
    assert first["state"] == "draft"
    assert MODULE._draft_ownership(fake.draft) == operation_id

    fake.calls.clear()
    resumed = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=False,
        resume=first,
    )

    assert resumed["state"] == "draft"
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_verified_checkpoint_is_reverified_and_verified_false_is_rejected(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)
    verified = MODULE.deposit_one(
        deposition, api=MODULE.SANDBOX_API, token="t", publish=True
    )

    fake.calls.clear()
    reverified = MODULE.deposit_one(
        deposition,
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        resume=verified,
    )
    assert reverified["verified"] is True
    assert any(url.endswith("/records/101") for _, url in fake.calls)

    stale = {**verified, "verified": False}
    with pytest.raises(MODULE.ZenodoError, match="verified=true"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=True,
            resume=stale,
        )


def test_operation_identity_changes_with_version_asset_or_metadata() -> None:
    original = _new_version_deposition()
    original_identity = MODULE._operation_identity(original)

    changed_version = _new_version_deposition()
    changed_version["metadata"]["version"] = "1.0.1-corrected"
    changed_version["synthpopcan"]["filename"] = "ontario-1.0.1-corrected.json.gz"
    changed_hash = _new_version_deposition()
    changed_hash["synthpopcan"]["sha256"] = "2" * 64
    changed_metadata = _new_version_deposition()
    changed_metadata["metadata"]["description"] = "Revised correction wording"

    assert MODULE._operation_identity(changed_version) != original_identity
    assert MODULE._operation_identity(changed_hash) != original_identity
    assert MODULE._operation_identity(changed_metadata) != original_identity


def test_new_version_rejects_mismatched_concept_before_mutation(monkeypatch) -> None:
    deposition = _new_version_deposition()
    fake = _FakeZenodo(deposition, new_version=True)
    fake.existing["conceptdoi"] = "10.5072/zenodo.other"
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="different concept DOI"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any("actions/newversion" in url for _, url in fake.calls)


@pytest.mark.parametrize(
    ("deposition_factory", "new_version"),
    [
        (_metadata_correction_deposition, False),
        (_new_version_deposition, True),
    ],
)
def test_historical_hash_mismatch_fails_before_edit_or_newversion(
    monkeypatch, deposition_factory, new_version
) -> None:
    deposition = deposition_factory()
    deposition["synthpopcan"]["historical_asset"]["sha256"] = "0" * 64
    fake = _FakeZenodo(deposition, new_version=new_version)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    if new_version:
        monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="SHA-256 changed"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert not any(
        "actions/edit" in url or "actions/newversion" in url for _, url in fake.calls
    )
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


@pytest.mark.parametrize(
    ("deposition_factory", "new_version"),
    [
        (_metadata_correction_deposition, False),
        (_new_version_deposition, True),
    ],
)
def test_extra_historical_file_fails_before_edit_or_newversion(
    monkeypatch, deposition_factory, new_version
) -> None:
    deposition = deposition_factory()
    fake = _FakeZenodo(deposition, new_version=new_version)
    fake.existing["files"].append(
        {
            "id": "unrelated",
            "filename": "unrelated.txt",
            "size": 1,
            "checksum": "md5:" + "0" * 32,
            "links": {"download": _HISTORICAL_URL},
        }
    )
    monkeypatch.setattr(MODULE, "_request", fake.request)
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)
    if new_version:
        monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: _payload(item)[0])

    with pytest.raises(MODULE.ZenodoError, match="one historical asset"):
        MODULE.deposit_one(
            deposition,
            api=MODULE.SANDBOX_API,
            token="t",
            publish=False,
        )

    assert not any(
        "actions/edit" in url or "actions/newversion" in url for _, url in fake.calls
    )
    assert not any(method in {"PUT", "DELETE", "POST"} for method, _ in fake.calls)


def test_deposit_creates_draft_and_does_not_publish_by_default(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    remote_metadata: dict = {}
    remote_file: dict = {}

    def fake_request(method, url, *, token, payload=None, data=None):
        calls.append((method, url))
        if url.endswith("/deposit/depositions"):
            return {
                "id": 4242,
                MODULE._HTTP_STATUS_KEY: 201,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/abc",
                    "html": "https://sandbox.zenodo.org/deposit/4242",
                },
            }
        if method == "PUT" and "/files/abc/" in url:
            remote_file.update(
                {
                    "filename": url.rsplit("/", 1)[-1],
                    "size": len(data),
                    "checksum": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                }
            )
            return remote_file
        if method == "PUT" and "/deposit/depositions/4242" in url:
            remote_metadata.update(payload["metadata"])
            return {
                "id": 4242,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/abc",
                    "html": "https://sandbox.zenodo.org/deposit/4242",
                },
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.4242"},
                },
            }
        if method == "GET" and url.endswith("/deposit/depositions/4242"):
            return {
                "id": 4242,
                "links": {"bucket": "https://sandbox.zenodo.org/api/files/abc"},
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.4242"},
                },
                "files": [remote_file],
            }
        return {"metadata": {"prereserve_doi": {"doi": "10.5072/zenodo.4242"}}}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: _payload(d)[0])

    result = MODULE.deposit_one(
        _deposition(), api=MODULE.SANDBOX_API, token="t", publish=False
    )

    assert result["state"] == "draft"
    assert result["deposition_id"] == 4242
    assert result["doi"] == "10.5072/zenodo.4242"
    assert not any("actions/publish" in url for _, url in calls), (
        "must never publish unless explicitly requested"
    )


def test_deposit_publishes_only_when_requested(monkeypatch) -> None:
    published: list[str] = []
    remote_metadata: dict = {}
    remote_file: dict = {}
    bucket = "https://sandbox.zenodo.org/api/files/publish-test"

    def fake_request(method, url, *, token, payload=None, data=None):
        if url.endswith("/deposit/depositions"):
            return {
                "id": 7,
                MODULE._HTTP_STATUS_KEY: 201,
                "links": {"bucket": bucket, "html": "h"},
            }
        if method == "PUT" and url.startswith(f"{bucket}/"):
            remote_file.update(
                {
                    "filename": url.rsplit("/", 1)[-1],
                    "size": len(data),
                    "checksum": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                    "links": {"download": "https://sandbox.invalid/model.gz"},
                }
            )
            return remote_file
        if method == "PUT" and url.endswith("/deposit/depositions/7"):
            remote_metadata.update(payload["metadata"])
            return {
                "id": 7,
                "links": {"bucket": bucket, "html": "h"},
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.7"},
                },
            }
        if method == "GET" and url.endswith("/deposit/depositions/7"):
            return {
                "id": 7,
                "links": {"bucket": bucket, "html": "h"},
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.7"},
                },
                "files": [remote_file],
            }
        if "actions/publish" in url:
            published.append(url)
            return {"doi": "10.5072/zenodo.7", "conceptdoi": "10.5072/zenodo.6"}
        if method == "GET" and url.endswith("/records/7"):
            return {
                "id": 7,
                "doi": "10.5072/zenodo.7",
                "conceptdoi": "10.5072/zenodo.6",
                "metadata": remote_metadata,
                "files": [remote_file],
                "links": {"html": "https://sandbox.invalid/records/7"},
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: _payload(d)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    result = MODULE.deposit_one(
        _deposition(), api=MODULE.SANDBOX_API, token="t", publish=True
    )

    assert len(published) == 1
    assert result["state"] == "verified"
    assert result["concept_doi"] == "10.5072/zenodo.6"


def test_uploads_asset_to_the_bucket_endpoint(monkeypatch) -> None:
    puts: list[str] = []
    remote_metadata: dict = {}
    remote_file: dict = {}

    def fake_request(method, url, *, token, payload=None, data=None):
        if method == "PUT" and "files" in url:
            puts.append(url)
            remote_file.update(
                {
                    "filename": url.rsplit("/", 1)[-1],
                    "size": len(data),
                    "checksum": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                }
            )
            return remote_file
        if url.endswith("/deposit/depositions"):
            return {
                "id": 1,
                MODULE._HTTP_STATUS_KEY: 201,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/xyz",
                    "html": "h",
                },
            }
        if method == "PUT" and "/deposit/depositions/1" in url:
            remote_metadata.update(payload["metadata"])
            return {
                "id": 1,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/xyz",
                    "html": "h",
                },
                "metadata": remote_metadata,
            }
        if method == "GET" and url.endswith("/deposit/depositions/1"):
            return {
                "id": 1,
                "links": {"bucket": "https://sandbox.zenodo.org/api/files/xyz"},
                "metadata": remote_metadata,
                "files": [remote_file],
            }
        return {}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: _payload(d)[0])

    MODULE.deposit_one(_deposition(), api=MODULE.SANDBOX_API, token="t", publish=False)

    assert puts == [
        "https://sandbox.zenodo.org/api/files/xyz/"
        "ontario-2021-all-fields-package.json.gz"
    ]


def test_load_depositions_rejects_unknown_model_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "DEPOSITIONS_DIR", tmp_path)
    (tmp_path / "known.json").write_text(json.dumps(_deposition()))

    with pytest.raises(Exception, match="Unknown model IDs"):
        MODULE._load_depositions(("does-not-exist",))


def test_load_depositions_skips_index_and_results_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "DEPOSITIONS_DIR", tmp_path)
    (tmp_path / "model.json").write_text(json.dumps(_deposition()))
    (tmp_path / "index.json").write_text("{}")
    (tmp_path / MODULE.RESULTS_PATH.name).write_text("{}")
    (tmp_path / MODULE.CORRECTION_PLAN_NAME).write_text("{}")

    loaded = MODULE._load_depositions(())

    assert len(loaded) == 1
    assert loaded[0]["synthpopcan"]["model_id"] == "ontario-2021-all-fields"


def test_results_accumulate_across_partial_runs(tmp_path, monkeypatch) -> None:
    results = tmp_path / "deposited.json"
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results)
    results.write_text(
        json.dumps(
            {
                "target": "sandbox",
                "results": [{"model_id": "first", "deposition_id": 1}],
            }
        )
    )

    existing = MODULE._existing_results("sandbox")

    assert existing["legacy:first:unknown:1"]["deposition_id"] == 1


def test_existing_results_are_scoped_by_target(tmp_path, monkeypatch) -> None:
    results = tmp_path / "deposited.json"
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results)
    results.write_text(
        json.dumps(
            {
                "target": "sandbox",
                "results": [{"model_id": "first", "deposition_id": 1}],
            }
        )
    )

    assert MODULE._existing_results("PRODUCTION") == {}


def test_upload_response_must_match_the_uploaded_payload() -> None:
    with pytest.raises(MODULE.ZenodoError, match="uploaded bytes"):
        MODULE._verify_upload_response({"size": 8}, b"payload")

    with pytest.raises(MODULE.ZenodoError, match="checksum mismatch"):
        MODULE._verify_upload_response({"checksum": "md5:" + "0" * 32}, b"payload")


@pytest.mark.parametrize(
    "checksum",
    [
        123,
        "MD5:" + "0" * 32,
        "md5:" + "A" * 32,
        "sha256:" + "0" * 64,
        "md5:" + "0" * 31,
    ],
)
def test_upload_response_rejects_non_exact_md5_forms(checksum) -> None:
    with pytest.raises(MODULE.ZenodoError, match="checksum"):
        MODULE._verify_upload_response({"checksum": checksum}, b"payload")


def test_upload_response_accepts_real_legacy_filesize_and_bare_md5() -> None:
    payload = b"payload"
    checksum = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    uploaded = {
        "filename": "candidate.json.gz",
        "filesize": len(payload),
        "checksum": checksum,
    }

    MODULE._verify_upload_response(uploaded, payload)
    assert (
        MODULE._verify_remote_asset(
            {"files": [uploaded]}, filename="candidate.json.gz", payload=payload
        )
        is uploaded
    )


def test_upload_response_rejects_conflicting_size_fields() -> None:
    with pytest.raises(MODULE.ZenodoError, match="size and filesize fields conflict"):
        MODULE._verify_upload_response(
            {"size": 7, "filesize": 8},
            b"payload",
        )


def test_asset_is_verified_before_a_deposition_is_created(monkeypatch) -> None:
    requests: list[str] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: b"wrong")
    monkeypatch.setattr(
        MODULE,
        "_request",
        lambda method, url, **kwargs: requests.append(url),
    )

    with pytest.raises(MODULE.ZenodoError, match="size mismatch"):
        MODULE.deposit_one(
            _deposition(), api=MODULE.SANDBOX_API, token="t", publish=False
        )

    assert requests == [], "bad bytes must be rejected before creating a draft"


def test_legacy_asset_without_exact_licensing_is_rejected_before_creation(
    monkeypatch,
) -> None:
    deposition = _deposition()
    unpacked = json.dumps({"models": {"legacy": {}}}, sort_keys=True).encode()
    payload = gzip.compress(unpacked, mtime=0)
    metadata = deposition["synthpopcan"]
    metadata["size_bytes"] = len(payload)
    metadata["sha256"] = hashlib.sha256(payload).hexdigest()
    metadata["uncompressed_size_bytes"] = len(unpacked)
    metadata["uncompressed_sha256"] = hashlib.sha256(unpacked).hexdigest()
    requests: list[str] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: payload)
    monkeypatch.setattr(
        MODULE,
        "_request",
        lambda method, url, **kwargs: requests.append(url),
    )

    with pytest.raises(MODULE.ZenodoError, match="exact top-level licensing"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert requests == [], "legacy package bytes must never create a deposition"


def test_asset_verifier_streams_and_rejects_late_or_corrupt_licensing(
    monkeypatch,
) -> None:
    deposition = _deposition()
    payload, _ = _payload(deposition)
    monkeypatch.setattr(
        gzip,
        "decompress",
        lambda value: pytest.fail("full-buffer gzip decompression is forbidden"),
    )
    MODULE._verify_asset(payload, deposition)

    licensing = deposition["synthpopcan"]["licensing"]
    late_unpacked = json.dumps(
        {"large_prefix": "x" * (10 * 1024 * 1024), "licensing": licensing},
        sort_keys=True,
    ).encode()
    late_payload = gzip.compress(late_unpacked, mtime=0)
    metadata = deposition["synthpopcan"]
    metadata["size_bytes"] = len(late_payload)
    metadata["sha256"] = hashlib.sha256(late_payload).hexdigest()
    metadata["uncompressed_size_bytes"] = len(late_unpacked)
    metadata["uncompressed_sha256"] = hashlib.sha256(late_unpacked).hexdigest()
    MODULE._verify_asset(late_payload, deposition)

    corrupt = b"not gzip"
    metadata["size_bytes"] = len(corrupt)
    metadata["sha256"] = hashlib.sha256(corrupt).hexdigest()
    metadata["uncompressed_size_bytes"] = 1
    metadata["uncompressed_sha256"] = "0" * 64
    with pytest.raises(MODULE.ZenodoError, match="valid gzip"):
        MODULE._verify_asset(corrupt, deposition)


def test_verified_correction_tail_is_hashed_without_python_semantic_parsing(
    monkeypatch,
) -> None:
    deposition = _new_version_deposition()
    licensing = deposition["synthpopcan"]["licensing"]
    unpacked = (
        b'{"licensing":'
        + json.dumps(licensing, sort_keys=True).encode()
        + b',"large_preserved_field":"'
        + b"x" * (10 * 1024 * 1024)
        + b'"}'
    )
    payload = gzip.compress(unpacked, mtime=0)
    metadata = deposition["synthpopcan"]
    metadata["size_bytes"] = len(payload)
    metadata["sha256"] = hashlib.sha256(payload).hexdigest()
    metadata["uncompressed_size_bytes"] = len(unpacked)
    metadata["uncompressed_sha256"] = hashlib.sha256(unpacked).hexdigest()

    original = MODULE._StreamingLicensingJsonParser
    fed_characters = 0

    class CountingParser(original):
        def feed(self, text: str) -> None:
            nonlocal fed_characters
            fed_characters += len(text)
            super().feed(text)

    monkeypatch.setattr(MODULE, "_StreamingLicensingJsonParser", CountingParser)

    MODULE._verify_asset(payload, deposition)

    assert fed_characters <= 2 * MODULE._STREAM_CHUNK_BYTES


@pytest.mark.parametrize(
    "unpacked, message",
    [
        (
            lambda licensing: (
                b'{"licensing":' + json.dumps(licensing).encode() + b',"licensing":{}}'
            ),
            "duplicate top-level licensing",
        ),
        (
            lambda licensing: (
                b'{"models":{},"licensing":'
                + json.dumps(licensing).encode()
                + b"} trailing"
            ),
            "invalid",
        ),
    ],
)
def test_full_streaming_parser_rejects_duplicate_or_trailing_json(
    unpacked, message
) -> None:
    raw = unpacked(statcan_prepared_model_licensing(2021))
    payload = gzip.compress(raw, mtime=0)

    with pytest.raises(MODULE.ZenodoError, match=message):
        MODULE._stream_uncompressed_licensing(
            payload,
            expected_size=len(raw),
            expected_sha256=hashlib.sha256(raw).hexdigest(),
        )


def test_streaming_verifier_rejects_uncompressed_size_and_hash_drift() -> None:
    deposition = _deposition()
    payload, unpacked = _payload(deposition)
    metadata = deposition["synthpopcan"]

    metadata["uncompressed_size_bytes"] = len(unpacked) - 1
    with pytest.raises(MODULE.ZenodoError, match="exceeds declared"):
        MODULE._verify_asset(payload, deposition)

    metadata["uncompressed_size_bytes"] = len(unpacked)
    metadata["uncompressed_sha256"] = "0" * 64
    with pytest.raises(MODULE.ZenodoError, match="uncompressed asset SHA-256"):
        MODULE._verify_asset(payload, deposition)


def test_legacy_deposition_manifest_is_rejected_before_asset_fetch(monkeypatch) -> None:
    deposition = _deposition()
    deposition["synthpopcan"].pop("licensing")
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="exact prepared-model licensing"):
        MODULE.deposit_one(deposition, api=MODULE.SANDBOX_API, token="t", publish=False)

    assert fetched == []


def test_production_requires_accepted_adr_and_completed_implementation(
    monkeypatch,
) -> None:
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: fetched.append(True))
    monkeypatch.setattr(
        MODULE, "_production_licensing_gates_are_complete", lambda: False
    )

    with pytest.raises(MODULE.ZenodoError, match="accepted ADR-0014"):
        MODULE.deposit_one(
            _deposition(), api=MODULE.PRODUCTION_API, token="t", publish=False
        )

    monkeypatch.setattr(
        MODULE, "_production_licensing_gates_are_complete", lambda: True
    )
    monkeypatch.setattr(
        MODULE, "_archive_correction_execution_is_completed", lambda: False
    )
    with pytest.raises(MODULE.ZenodoError, match="fresh production model records"):
        MODULE.deposit_one(
            _deposition(), api=MODULE.PRODUCTION_API, token="t", publish=False
        )

    assert fetched == []


def test_execution_gate_blocks_fresh_records_but_not_correction_work(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MODULE, "_production_licensing_gates_are_complete", lambda: True
    )
    monkeypatch.setattr(
        MODULE, "_archive_correction_execution_is_completed", lambda: False
    )
    monkeypatch.setattr(MODULE, "_validated_licensing", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        MODULE, "_require_production_correction_authority", lambda *args: None
    )
    fetched: list[bool] = []
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda item: fetched.append(True))

    with pytest.raises(MODULE.ZenodoError, match="fresh production model records"):
        MODULE.deposit_one(
            _deposition(), api=MODULE.PRODUCTION_API, token="t", publish=False
        )
    assert fetched == []

    correction = _metadata_correction_deposition()
    fake = _FakeZenodo(correction, new_version=False)
    monkeypatch.setattr(MODULE, "_request", fake.request)
    result = MODULE.deposit_one(
        correction, api=MODULE.PRODUCTION_API, token="t", publish=False
    )
    assert result["state"] == "draft"


def test_accepted_project_policy_is_required_for_production(
    monkeypatch,
) -> None:
    licensing = statcan_prepared_model_licensing(2021)

    assert (
        MODULE._validated_licensing(
            _deposition(licensing=licensing),
            require_accepted_policy=True,
        )
        == licensing
    )

    unresolved = json.loads(json.dumps(licensing))
    unresolved["policy_decision"]["status"] = "unresolved"
    monkeypatch.setattr(
        MODULE, "validate_prepared_model_licensing", lambda value: value
    )
    with pytest.raises(MODULE.ZenodoError, match="accepted project rights policy"):
        MODULE._validated_licensing(
            _deposition(licensing=unresolved),
            require_accepted_policy=True,
        )


def test_deposit_checkpoints_every_irreversible_state(monkeypatch) -> None:
    states: list[str] = []
    remote_metadata: dict = {}
    remote_file: dict = {}
    bucket = "https://sandbox.zenodo.org/api/files/checkpoint-test"

    def fake_request(method, url, *, token, payload=None, data=None):
        if url.endswith("/deposit/depositions"):
            return {
                "id": 7,
                MODULE._HTTP_STATUS_KEY: 201,
                "links": {"bucket": bucket, "html": "h"},
            }
        if "actions/publish" in url:
            return {"doi": "10.5072/zenodo.7", "conceptdoi": "10.5072/zenodo.6"}
        if method == "PUT" and url == (
            f"{bucket}/ontario-2021-all-fields-package.json.gz"
        ):
            remote_file.update(
                {
                    "filename": "ontario-2021-all-fields-package.json.gz",
                    "size": len(data),
                    "checksum": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                    "links": {"download": "https://sandbox.invalid/model.gz"},
                }
            )
            return remote_file
        if method == "PUT" and url.endswith("/deposit/depositions/7"):
            remote_metadata.update(payload["metadata"])
            return {
                "id": 7,
                "links": {"bucket": bucket, "html": "h"},
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.7"},
                },
            }
        if method == "GET" and url.endswith("/deposit/depositions/7"):
            return {
                "id": 7,
                "links": {"bucket": bucket, "html": "h"},
                "metadata": {
                    **remote_metadata,
                    "prereserve_doi": {"doi": "10.5072/zenodo.7"},
                },
                "files": [remote_file],
            }
        if method == "GET" and url.endswith("/records/7"):
            return {
                "id": 7,
                "doi": "10.5072/zenodo.7",
                "conceptdoi": "10.5072/zenodo.6",
                "metadata": remote_metadata,
                "files": [remote_file],
                "links": {"html": "https://sandbox.invalid/records/7"},
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: _payload(d)[0])
    monkeypatch.setattr(MODULE, "_verify_remote_download", lambda *args, **kwargs: None)

    MODULE.deposit_one(
        _deposition(),
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        checkpoint=lambda result: states.append(result["state"]),
    )

    assert states == [
        "action-intent",
        "created",
        "uploaded",
        "draft",
        "published",
        "verified",
    ]


def test_writing_one_target_preserves_the_other(tmp_path, monkeypatch) -> None:
    results = tmp_path / "deposited.json"
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results)

    MODULE._write_results(
        "sandbox", MODULE.SANDBOX_API, {"sandbox-model": {"model_id": "sandbox-model"}}
    )
    MODULE._write_results(
        "PRODUCTION",
        MODULE.PRODUCTION_API,
        {"production-model": {"model_id": "production-model"}},
    )

    assert set(MODULE._stored_targets()) == {"sandbox", "PRODUCTION"}
    assert set(MODULE._existing_results("sandbox")) == {
        "legacy:sandbox-model:unknown:unknown"
    }
    assert set(MODULE._existing_results("PRODUCTION")) == {
        "legacy:production-model:unknown:unknown"
    }


def _write_bound_correction_bundle(directory: Path) -> list[dict]:
    depositions = [_metadata_correction_deposition(), _new_version_deposition()]
    descriptors = sorted(
        (MODULE._correction_operation_descriptor(item) for item in depositions),
        key=lambda item: item["operation_id"],
    )
    index = {
        "schema_version": "synthpopcan-zenodo-correction-execution-index-v1",
        "build_scope": "test-subset",
        "production_ready": False,
        "candidate_count": 1,
        "candidate_model_ids": ["ontario-2021-all-fields"],
        "candidate_envelope_sha256": "6" * 64,
        "new_package_version": "1.0.0-corrected",
        "operations": descriptors,
    }
    index_sha256 = MODULE._canonical_document_sha256(index)
    by_operation = {
        item["deposit_operation"]: item["operation_id"] for item in descriptors
    }
    for deposition in depositions:
        synthpopcan = deposition["synthpopcan"]
        synthpopcan["candidate_envelope_sha256"] = index["candidate_envelope_sha256"]
        synthpopcan["execution_index_schema"] = index["schema_version"]
        synthpopcan["execution_index_sha256"] = index_sha256
        synthpopcan["execution_operation_id"] = by_operation[
            synthpopcan["deposit_operation"]
        ]
    directory.mkdir()
    for deposition in depositions:
        operation = deposition["synthpopcan"]["deposit_operation"]
        (directory / f"{operation}.json").write_text(json.dumps(deposition))
    (directory / "execution-index.json").write_text(json.dumps(index))
    return depositions


def test_manifest_index_drift_is_rejected_before_any_zenodo_write(
    tmp_path, monkeypatch
) -> None:
    bundle = tmp_path / "corrections"
    _write_bound_correction_bundle(bundle)
    assert len(MODULE._load_depositions((), bundle)) == 2

    manifest_path = bundle / "create-new-version.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata"]["description"] = "stale metadata from another bundle"
    manifest_path.write_text(json.dumps(manifest))
    calls: list[tuple] = []
    monkeypatch.setattr(MODULE, "_request", lambda *args, **kwargs: calls.append(args))

    result = CliRunner().invoke(
        MODULE.main,
        ["--manifests-dir", str(bundle)],
        env={"ZENODO_SANDBOX_TOKEN": "unused"},
    )

    assert result.exit_code == 2
    assert "do not exactly match the execution index" in result.output
    assert calls == []


def test_registry_update_output_requires_verified_production_result(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "registry-updates.json"
    monkeypatch.setattr(MODULE, "REGISTRY_UPDATES_PATH", output)
    deposition = _new_version_deposition()
    descriptor = MODULE._correction_operation_descriptor(deposition)
    operation_id = descriptor["operation_id"]
    update = {
        "model_id": descriptor["model_id"],
        "release_version": descriptor["package_version"],
        "record_id": 101,
        "version_doi": "10.5072/zenodo.101",
        "concept_doi": descriptor["existing_concept_doi"],
        "url": "https://zenodo.org/records/101/files/corrected.json.gz",
        "filename": descriptor["filename"],
        "size_bytes": descriptor["size_bytes"],
        "sha256": descriptor["sha256"],
        "uncompressed_size_bytes": descriptor["uncompressed_size_bytes"],
        "uncompressed_sha256": descriptor["uncompressed_sha256"],
    }
    result = {
        **descriptor,
        "state": "verified",
        "verified": True,
        "source_record_id": descriptor["existing_record_id"],
        "deposition_id": 101,
        "doi": "10.5072/zenodo.101",
        "concept_doi": descriptor["existing_concept_doi"],
        "registry_update": update,
    }
    fresh_result = {
        "state": "verified",
        "verified": True,
        "deposit_operation": "create-new-record",
        "registry_update": {"model_id": "fresh-model-must-not-be-emitted"},
    }
    execution_index = {"operations": [descriptor]}

    assert not MODULE._write_registry_updates(
        "sandbox",
        MODULE.SANDBOX_API,
        {operation_id: result},
        execution_index=execution_index,
    )
    assert not output.exists()
    assert MODULE._write_registry_updates(
        "PRODUCTION",
        MODULE.PRODUCTION_API,
        {operation_id: result, "fresh": fresh_result},
        execution_index=execution_index,
    )
    assert json.loads(output.read_text())["updates"] == [update]


def test_execution_gate_uses_tracked_evidence_not_ignored_checkpoints(
    tmp_path, monkeypatch
) -> None:
    adr = tmp_path / "adr.md"
    plan_path = tmp_path / "plan.json"
    index_path = tmp_path / "execution-index.json"
    results_path = tmp_path / "deposited.json"
    registry_path = tmp_path / "registry.json"
    monkeypatch.setattr(MODULE, "LICENSING_ADR", adr)
    monkeypatch.setattr(MODULE, "CORRECTION_PLAN_PATH", plan_path, raising=False)
    monkeypatch.setattr(
        MODULE, "CORRECTION_EXECUTION_INDEX_PATH", index_path, raising=False
    )
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results_path)
    monkeypatch.setattr(MODULE, "REGISTRY_UPDATES_PATH", registry_path)
    adr.write_text("- **Archive correction execution:** Completed\n")

    model_ids = [f"model-{index:02d}" for index in range(32)]
    plan_path.write_text(json.dumps({"actions": [{"model_id": x} for x in model_ids]}))
    operations = []
    results = {}
    updates = []
    for index, model_id in enumerate(model_ids):
        existing_record_id = 1_000 + index
        new_record_id = 2_000 + index
        existing_version_doi = f"10.5281/zenodo.{existing_record_id}"
        concept_doi = f"10.5281/zenodo.{3_000 + index}"
        new_version_doi = f"10.5281/zenodo.{new_record_id}"
        for operation in ("correct-existing-metadata", "create-new-version"):
            version = "v1-corrected" if operation == "create-new-version" else "v0"
            asset_sha256 = ("2" if operation == "create-new-version" else "1") * 64
            operation_id = (
                f"{operation}:{model_id}:{version}:{asset_sha256}:" + "3" * 64
            )
            descriptor = {
                "operation_id": operation_id,
                "deposit_operation": operation,
                "model_id": model_id,
                "package_version": version,
                "asset_sha256": asset_sha256,
                "metadata_sha256": "3" * 64,
                "existing_record_id": existing_record_id,
                "existing_version_doi": existing_version_doi,
                "existing_concept_doi": concept_doi,
            }
            if operation == "create-new-version":
                descriptor.update(
                    {
                        "filename": f"{model_id}-v1-corrected.json.gz",
                        "size_bytes": 101 + index,
                        "sha256": asset_sha256,
                        "uncompressed_size_bytes": 201 + index,
                        "uncompressed_sha256": "4" * 64,
                    }
                )
            operations.append(descriptor)
            results[operation_id] = {
                "operation_id": operation_id,
                "deposit_operation": operation,
                "model_id": model_id,
                "package_version": version,
                "asset_sha256": asset_sha256,
                "metadata_sha256": "3" * 64,
                "source_record_id": existing_record_id,
                "deposition_id": (
                    new_record_id
                    if operation == "create-new-version"
                    else existing_record_id
                ),
                "doi": (
                    new_version_doi
                    if operation == "create-new-version"
                    else existing_version_doi
                ),
                "concept_doi": concept_doi,
                "state": "verified",
                "verified": True,
            }
            if operation == "create-new-version":
                update = {
                    "model_id": model_id,
                    "release_version": version,
                    "record_id": new_record_id,
                    "version_doi": new_version_doi,
                    "concept_doi": concept_doi,
                    "url": (
                        f"https://zenodo.org/records/{new_record_id}/files/"
                        f"{descriptor['filename']}"
                    ),
                    "filename": descriptor["filename"],
                    "size_bytes": descriptor["size_bytes"],
                    "sha256": descriptor["sha256"],
                    "uncompressed_size_bytes": descriptor["uncompressed_size_bytes"],
                    "uncompressed_sha256": descriptor["uncompressed_sha256"],
                }
                results[operation_id]["registry_update"] = update
                updates.append(update)
    index_path.write_text(
        json.dumps(
            {
                "schema_version": ("synthpopcan-zenodo-correction-execution-index-v1"),
                "production_ready": True,
                "build_scope": "complete-catalogue",
                "candidate_count": 32,
                "candidate_model_ids": model_ids,
                "candidate_envelope_sha256": "6" * 64,
                "new_package_version": "v1-corrected",
                "operations": operations,
            }
        )
    )
    MODULE._write_results("PRODUCTION", MODULE.PRODUCTION_API, results)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "synthpopcan-verified-registry-updates-v1",
                "target": "PRODUCTION",
                "api": MODULE.PRODUCTION_API,
                "updates": updates,
            }
        )
    )

    assert MODULE._archive_correction_execution_is_completed()

    first = next(iter(results.values()))
    first["metadata_sha256"] = "4" * 64
    MODULE._write_results("PRODUCTION", MODULE.PRODUCTION_API, results)
    # Ignored executor state is deliberately no longer part of this clean-clone
    # gate; changing it cannot invalidate the tracked reviewed transaction.
    assert MODULE._archive_correction_execution_is_completed()


def test_main_revalidates_an_already_verified_operation(tmp_path, monkeypatch) -> None:
    results = tmp_path / "deposited.json"
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results)
    deposition = _deposition()
    operation_id = MODULE._operation_identity(deposition)
    MODULE._write_results(
        "sandbox",
        MODULE.SANDBOX_API,
        {
            operation_id: {
                "operation_id": operation_id,
                "model_id": "ontario-2021-all-fields",
                "deposition_id": 42,
                "state": "verified",
                "verified": True,
            }
        },
    )
    monkeypatch.setattr(
        MODULE, "_load_depositions", lambda only, directory=None: [deposition]
    )
    calls: list[dict] = []

    def revalidate(*args, **kwargs):
        calls.append(kwargs["resume"])
        return kwargs["resume"]

    monkeypatch.setattr(MODULE, "deposit_one", revalidate)

    result = CliRunner().invoke(
        MODULE.main,
        [],
        env={"ZENODO_SANDBOX_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Revalidating create-new-record for ontario-2021-all-fields" in result.output
    assert calls == [MODULE._existing_results("sandbox")[operation_id]]
