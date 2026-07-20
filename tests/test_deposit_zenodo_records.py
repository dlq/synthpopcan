import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

SCRIPT = Path(__file__).parents[1] / "scripts/deposit_zenodo_records.py"
SPEC = importlib.util.spec_from_file_location("deposit_zenodo_records", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _deposition(payload: bytes = b"payload") -> dict:
    return {
        "metadata": {
            "title": "SynthPopCan prepared model: Ontario",
            "upload_type": "dataset",
        },
        "synthpopcan": {
            "model_id": "ontario-2021-all-fields",
            "asset_url": "https://example.invalid/ontario.json.gz",
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
    }


def test_sandbox_is_the_default_target() -> None:
    assert "sandbox.zenodo.org" in MODULE.SANDBOX_API
    assert MODULE.PRODUCTION_API == "https://zenodo.org/api"


def test_deposit_creates_draft_and_does_not_publish_by_default(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, *, token, payload=None, data=None):
        calls.append((method, url))
        if url.endswith("/deposit/depositions"):
            return {
                "id": 4242,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/abc",
                    "html": "https://sandbox.zenodo.org/deposit/4242",
                },
            }
        return {"metadata": {"prereserve_doi": {"doi": "10.5072/zenodo.4242"}}}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: b"payload")

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

    def fake_request(method, url, *, token, payload=None, data=None):
        if url.endswith("/deposit/depositions"):
            return {"id": 7, "links": {"bucket": "b", "html": "h"}}
        if "actions/publish" in url:
            published.append(url)
            return {"doi": "10.5072/zenodo.7", "conceptdoi": "10.5072/zenodo.6"}
        return {"metadata": {}}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: b"x")

    result = MODULE.deposit_one(
        _deposition(b"x"), api=MODULE.SANDBOX_API, token="t", publish=True
    )

    assert len(published) == 1
    assert result["state"] == "published"
    assert result["concept_doi"] == "10.5072/zenodo.6"


def test_uploads_asset_to_the_bucket_endpoint(monkeypatch) -> None:
    puts: list[str] = []

    def fake_request(method, url, *, token, payload=None, data=None):
        if method == "PUT" and "files" in url:
            puts.append(url)
            return {}
        if url.endswith("/deposit/depositions"):
            return {
                "id": 1,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/xyz",
                    "html": "h",
                },
            }
        return {"metadata": {}}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: b"gz")

    MODULE.deposit_one(
        _deposition(b"gz"), api=MODULE.SANDBOX_API, token="t", publish=False
    )

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

    assert existing["first"]["deposition_id"] == 1


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


def test_deposit_checkpoints_every_irreversible_state(monkeypatch) -> None:
    states: list[str] = []

    def fake_request(method, url, *, token, payload=None, data=None):
        if url.endswith("/deposit/depositions"):
            return {"id": 7, "links": {"bucket": "b", "html": "h"}}
        if "actions/publish" in url:
            return {"doi": "10.5072/zenodo.7", "conceptdoi": "10.5072/zenodo.6"}
        if method == "PUT" and url == "b/ontario-2021-all-fields-package.json.gz":
            return {"size": 7}
        return {"metadata": {"prereserve_doi": {"doi": "10.5072/zenodo.7"}}}

    monkeypatch.setattr(MODULE, "_request", fake_request)
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d: b"payload")

    MODULE.deposit_one(
        _deposition(),
        api=MODULE.SANDBOX_API,
        token="t",
        publish=True,
        checkpoint=lambda result: states.append(result["state"]),
    )

    assert states == ["created", "uploaded", "draft", "published"]


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
    assert set(MODULE._existing_results("sandbox")) == {"sandbox-model"}
    assert set(MODULE._existing_results("PRODUCTION")) == {"production-model"}


def test_main_skips_an_already_recorded_model(tmp_path, monkeypatch) -> None:
    results = tmp_path / "deposited.json"
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    monkeypatch.setattr(MODULE, "RESULTS_PATH", results)
    MODULE._write_results(
        "sandbox",
        MODULE.SANDBOX_API,
        {
            "ontario-2021-all-fields": {
                "model_id": "ontario-2021-all-fields",
                "deposition_id": 42,
                "state": "published",
            }
        },
    )
    monkeypatch.setattr(MODULE, "_load_depositions", lambda only: [_deposition()])
    monkeypatch.setattr(
        MODULE,
        "deposit_one",
        lambda *args, **kwargs: pytest.fail("existing record must not be redeposited"),
    )

    result = CliRunner().invoke(
        MODULE.main,
        [],
        env={"ZENODO_SANDBOX_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Skipping ontario-2021-all-fields" in result.output
