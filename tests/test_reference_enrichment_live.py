"""Opt-in checks against the exact public reference-adapter resources."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from synthpopcan.canfed import (
    CANFED_V2_ARCHIVE_SHA256,
    CANFED_V2_ARCHIVE_URL,
    can_fed_source_profile,
    normalize_can_fed_archive,
)
from synthpopcan.enrichment import acquire_public_resource
from synthpopcan.odef import (
    ODEF_V3_ARCHIVE_SHA256,
    ODEF_V3_ARCHIVE_URL,
    normalize_odef_archive,
    odef_source_profile,
)

LIVE_STATCAN_ENABLED = os.environ.get("SYNTHPOPCAN_LIVE_STATCAN") == "1"
LIVE_STATCAN_REASON = "set SYNTHPOPCAN_LIVE_STATCAN=1 to call live StatCan sources"

pytestmark = [
    pytest.mark.live_statcan,
    pytest.mark.skipif(not LIVE_STATCAN_ENABLED, reason=LIVE_STATCAN_REASON),
]


def test_live_can_fed_revision_and_schema(tmp_path: Path) -> None:
    archive, resource = acquire_public_resource(
        can_fed_source_profile(),
        tmp_path / "cache",
        acquired_at="live-test",
        media_type="application/zip",
        resource_url=CANFED_V2_ARCHIVE_URL,
        max_bytes=16 * 1024 * 1024,
    )

    assert resource.sha256 == CANFED_V2_ARCHIVE_SHA256
    report = normalize_can_fed_archive(archive, tmp_path / "canfed.csv")
    assert report["product_rows"] == {"1km": 57_936, "3km": 57_936}


def test_live_odef_revision_and_schema(tmp_path: Path) -> None:
    archive, resource = acquire_public_resource(
        odef_source_profile(),
        tmp_path / "cache",
        acquired_at="live-test",
        media_type="application/zip",
        resource_url=ODEF_V3_ARCHIVE_URL,
        max_bytes=32 * 1024 * 1024,
    )

    assert resource.sha256 == ODEF_V3_ARCHIVE_SHA256
    report = normalize_odef_archive(archive, tmp_path / "odef.csv")
    assert report["source_rows"] == 18_858
    assert report["ungeocoded_count"] == 3_106
