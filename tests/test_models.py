from __future__ import annotations

import hashlib
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from synthpopcan import models


class FakeResponse(BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_model_catalogue_marks_large_models_downloadable(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))

    catalogue = models.model_catalogue()
    demo = catalogue[0]
    montreal = catalogue[1]

    assert demo["id"] == "demo-linked-household-person"
    assert demo["distribution"] == "bundled"
    assert demo["installed"] is True
    assert montreal["id"] == "montreal-cma-2016-all-fields"
    assert montreal["distribution"] == "download"
    assert montreal["installed"] is False
    assert "cache_path" not in montreal


def test_fetch_model_package_downloads_and_verifies(
    monkeypatch,
    tmp_path,
) -> None:
    content = b'{"schema_version": "synthpopcan-linked-tree-package-v1"}'
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(
        models,
        "urlopen",
        lambda url, timeout: FakeResponse(content),
    )
    metadata = models.model_registry_entry("montreal-cma-2016-all-fields")
    original_sha = metadata["sha256"]
    metadata["sha256"] = hashlib.sha256(content).hexdigest()
    try:
        path = models.fetch_model_package("montreal-cma-2016-all-fields")
    finally:
        metadata["sha256"] = original_sha

    assert path == tmp_path / "montreal-cma-2016-all-fields-package.json"
    assert path.read_bytes() == content
    assert models.model_is_installed("montreal-cma-2016-all-fields") is True
    assert models.remove_cached_model("montreal-cma-2016-all-fields") is True
    assert models.model_is_installed("montreal-cma-2016-all-fields") is False


def test_fetch_model_package_reports_progress(
    monkeypatch,
    tmp_path,
) -> None:
    content = b'{"schema_version": "synthpopcan-linked-tree-package-v1"}'
    response = FakeResponse(content)
    response.headers = {"Content-Length": str(len(content))}
    progress_events: list[tuple[int, int | None]] = []
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(models, "urlopen", lambda url, timeout: response)
    metadata = models.model_registry_entry("montreal-cma-2016-all-fields")
    original_sha = metadata["sha256"]
    metadata["sha256"] = hashlib.sha256(content).hexdigest()
    try:
        models.fetch_model_package(
            "montreal-cma-2016-all-fields",
            progress_callback=lambda done, total: progress_events.append((done, total)),
        )
    finally:
        metadata["sha256"] = original_sha

    assert progress_events[0] == (0, len(content))
    assert progress_events[-1] == (len(content), len(content))


def test_model_payload_requires_download_for_large_models(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))

    try:
        models.model_payload("quebec-2016-all-fields")
    except FileNotFoundError as exc:
        assert "synthpopcan models fetch quebec-2016-all-fields" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")


# ---------------------------------------------------------------------------
# models/__init__.py gaps (from test_coverage_gaps2.py)
# ---------------------------------------------------------------------------


def test_model_payload_raises_for_non_dict_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    list_json = tmp_path / "montreal-cma-2016-all-fields-package.json"
    list_json.write_text("[1, 2, 3]")

    with patch.object(models, "model_cache_path", return_value=list_json):
        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(ValueError, match="must be a JSON object"):
                models.model_payload("montreal-cma-2016-all-fields")


def test_model_cache_dir_win32_with_localappdata(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with patch.object(sys, "platform", "win32"):
        result = models.model_cache_dir()
    assert result == tmp_path / "SynthPopCan" / "models"


def test_model_cache_dir_win32_without_localappdata_falls_to_xdg(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with patch.object(sys, "platform", "win32"):
        result = models.model_cache_dir()
    assert result == tmp_path / "synthpopcan" / "models"


def test_model_cache_dir_linux_with_xdg_cache_home(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with patch.object(sys, "platform", "linux"):
        result = models.model_cache_dir()
    assert result == tmp_path / "synthpopcan" / "models"


def test_model_cache_dir_linux_without_xdg_falls_to_home_cache(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHPOPCAN_MODEL_CACHE", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    with patch.object(sys, "platform", "linux"):
        result = models.model_cache_dir()
    assert result == Path.home() / ".cache" / "synthpopcan" / "models"


def test_fetch_model_package_returns_early_for_bundled_model(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    result = models.fetch_model_package("demo-linked-household-person")
    assert result.exists()
    assert result.name == "demo-linked-household-person-package.json"


def test_fetch_model_package_returns_cached_file_without_redownloading(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    content = b'{"schema_version": "synthpopcan-linked-tree-package-v1"}'
    cached = tmp_path / "montreal-cma-2016-all-fields-package.json"
    cached.write_bytes(content)

    with patch.object(models, "_verify_model_checksum"):
        result = models.fetch_model_package("montreal-cma-2016-all-fields")

    assert result == cached


def test_fetch_model_package_cleans_up_temp_file_on_exception(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(
        models,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("network failure")),
    )

    with pytest.raises(OSError, match="network failure"):
        models.fetch_model_package("montreal-cma-2016-all-fields")

    temp_files = list(tmp_path.glob("*.part"))
    assert temp_files == []


def test_remove_cached_model_returns_false_for_bundled_model(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    assert models.remove_cached_model("demo-linked-household-person") is False


def test_remove_cached_model_returns_false_when_not_downloaded(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SYNTHPOPCAN_MODEL_CACHE", str(tmp_path))
    assert models.remove_cached_model("montreal-cma-2016-all-fields") is False


def test_verify_model_checksum_skips_when_no_expected_sha256(tmp_path) -> None:
    from synthpopcan.models import _verify_model_checksum

    f = tmp_path / "model.json"
    f.write_bytes(b"content")
    _verify_model_checksum(f, {"filename": "model.json"})


def test_verify_model_checksum_raises_on_mismatch(tmp_path) -> None:
    from synthpopcan.models import _verify_model_checksum

    f = tmp_path / "model.json"
    f.write_bytes(b"actual content")
    with pytest.raises(ValueError, match="checksum did not match"):
        _verify_model_checksum(f, {"filename": "model.json", "sha256": "0" * 64})


def test_download_size_ignores_non_integer_content_length() -> None:
    from synthpopcan.models import _download_size

    class _FakeResponse:
        headers = {"Content-Length": "not-a-number"}

    assert _download_size(_FakeResponse(), {"size_bytes": 42}) == 42


def test_download_size_ignores_bad_header_and_missing_size_bytes() -> None:
    from synthpopcan.models import _download_size

    class _FakeResponse:
        headers = {"Content-Length": "bad"}

    assert _download_size(_FakeResponse(), {}) is None
