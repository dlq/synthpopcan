import os

import pytest

from synthpopcan.statcan import (
    fetch_json,
    fetch_wds_metadata,
    search_wds_tables,
    summarize_wds_metadata,
    wds_download_url,
)

LIVE_STATCAN_ENABLED = os.environ.get("SYNTHPOPCAN_LIVE_STATCAN") == "1"
LIVE_STATCAN_REASON = "set SYNTHPOPCAN_LIVE_STATCAN=1 to call live StatCan WDS"
POPULATION_DWELLING_PRODUCT_ID = "98100001"

pytestmark = [
    pytest.mark.live_statcan,
    pytest.mark.skipif(not LIVE_STATCAN_ENABLED, reason=LIVE_STATCAN_REASON),
]


def test_live_wds_search_finds_population_dwelling_table() -> None:
    results = search_wds_tables("population dwelling", limit=10)

    assert any(
        result.product_id == POPULATION_DWELLING_PRODUCT_ID for result in results
    )


def test_live_wds_metadata_supports_explain_summary() -> None:
    metadata = fetch_wds_metadata(POPULATION_DWELLING_PRODUCT_ID)
    summary = summarize_wds_metadata(metadata)

    assert summary["product_id"] == POPULATION_DWELLING_PRODUCT_ID
    assert summary["title_en"]
    assert summary["dimensions"]
    assert summary["dimension_previews"]
    assert summary["ipf_suitability"]["status"] in {
        "likely_age_sex_controls",
        "possible_totals_only",
        "unclear",
    }


def test_live_wds_download_endpoint_resolves_zip_url() -> None:
    response = fetch_json(wds_download_url(POPULATION_DWELLING_PRODUCT_ID))

    assert response["status"] == "SUCCESS"
    assert response["object"].endswith(f"{POPULATION_DWELLING_PRODUCT_ID}-eng.zip")
