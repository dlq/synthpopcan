from __future__ import annotations

import hashlib
from io import BytesIO

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
