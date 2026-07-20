import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/deposit_zenodo_records.py"
SPEC = importlib.util.spec_from_file_location("deposit_zenodo_records", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _deposition() -> dict:
    return {
        "metadata": {
            "title": "SynthPopCan prepared model: Ontario",
            "upload_type": "dataset",
        },
        "synthpopcan": {
            "model_id": "ontario-2021-all-fields",
            "asset_url": "https://example.invalid/ontario.json.gz",
            "size_bytes": 2_989_767,
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
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d, *, token: b"payload")

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
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d, *, token: b"x")

    result = MODULE.deposit_one(
        _deposition(), api=MODULE.SANDBOX_API, token="t", publish=True
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
    monkeypatch.setattr(MODULE, "_asset_bytes", lambda d, *, token: b"gz")

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

    loaded = MODULE._load_depositions(())

    assert len(loaded) == 1
    assert loaded[0]["synthpopcan"]["model_id"] == "ontario-2021-all-fields"
