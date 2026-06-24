import json
from pathlib import Path

import pytest
from click.exceptions import ClickException

from synthpopcan.cli import (
    main,
    run_statcan_census_profile_fetch,
    search_wds_tables_for_cli,
)
from synthpopcan.cli import (
    parse_columns as parse_cli_columns,
)
from synthpopcan.statcan import (
    _CENSUS_PROFILE_2016_DOWNLOADS,
    WDSTableSearchResult,
    classify_wds_ipf_suitability,
    download_url,
    extract_wds_dimension_names,
    extract_wds_dimension_previews,
    fetch_census_profile_2016,
    fetch_json,
    fetch_wds_metadata,
    fetch_wds_table,
    normalize_language,
    normalize_product_id,
    post_json,
    search_wds_tables,
    summarize_wds_metadata,
    wds_download_url,
)


def test_wds_download_url_uses_statcan_endpoint() -> None:
    assert wds_download_url("14100287", "en") == (
        "https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/14100287/en"
    )


def test_cli_fetches_wds_table_zip(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, Path]] = []

    def fake_json(url: str) -> dict[str, str]:
        assert url.endswith("/getFullTableDownloadCSV/14100287/en")
        return {
            "status": "SUCCESS",
            "object": "https://www150.statcan.gc.ca/n1/tbl/csv/14100287-eng.zip",
        }

    def fake_download(url: str, destination: Path) -> None:
        calls.append((url, destination))
        destination.write_bytes(b"zip bytes")

    monkeypatch.setattr("synthpopcan.statcan.fetch_json", fake_json)
    monkeypatch.setattr("synthpopcan.statcan.download_url", fake_download)

    assert (
        main(
            [
                "statcan",
                "wds",
                "fetch",
                "14100287",
                "--out-dir",
                str(tmp_path),
            ]
        )
        == 0
    )

    assert calls == [
        (
            "https://www150.statcan.gc.ca/n1/tbl/csv/14100287-eng.zip",
            tmp_path / "14100287-eng.zip",
        )
    ]
    assert (tmp_path / "14100287-eng.zip").read_bytes() == b"zip bytes"
    manifest = json.loads((tmp_path / "14100287-eng.json").read_text())
    assert manifest["product_id"] == "14100287"
    assert manifest["source_url"].endswith("/getFullTableDownloadCSV/14100287/en")


def test_cli_fetches_2016_census_profile_by_registry_key(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[tuple[str, Path]] = []

    def fake_download(url: str, destination: Path) -> None:
        calls.append((url, destination))
        destination.write_bytes(b"csv bytes")

    monkeypatch.setattr("synthpopcan.statcan.download_url", fake_download)

    assert (
        main(
            [
                "statcan",
                "census-profile",
                "fetch",
                "--year",
                "2016",
                "--geo-level",
                "pt",
                "--out-dir",
                str(tmp_path),
            ]
        )
        == 0
    )

    entry = _CENSUS_PROFILE_2016_DOWNLOADS["pt"]
    assert calls == [(entry.url, tmp_path / entry.filename)]
    manifest = json.loads((tmp_path / "2016-census-profile-pt.json").read_text())
    assert manifest["geo_level"] == "pt"
    assert manifest["source_url"] == entry.url


def test_cli_fetch_census_profile_rejects_unknown_geo_level(tmp_path: Path) -> None:
    with pytest.raises(ClickException) as excinfo:
        main(
            [
                "statcan",
                "census-profile",
                "fetch",
                "--year",
                "2016",
                "--geo-level",
                "unknown",
                "--out-dir",
                str(tmp_path),
            ]
        )

    message = str(excinfo.value)
    assert "Unknown 2016 Census Profile geography level" in message
    assert "Use one of:" in message


def test_search_wds_tables_filters_inventory(monkeypatch) -> None:
    def fake_json(url: str) -> list[dict[str, object]]:
        assert url.endswith("/getAllCubesListLite")
        return [
            {
                "productId": 98100001,
                "cansimId": "",
                "cubeTitleEn": "Population and dwelling counts: Canada",
                "cubeTitleFr": "Chiffres de population et des logements : Canada",
                "cubeStartDate": "2016-01-01",
                "cubeEndDate": "2016-01-01",
            },
            {
                "productId": 14100287,
                "cansimId": "282-0087",
                "cubeTitleEn": "Labour force characteristics by province",
                "cubeTitleFr": "Caracteristiques de la population active",
                "cubeStartDate": "1976-01-01",
                "cubeEndDate": "2026-01-01",
            },
        ]

    monkeypatch.setattr("synthpopcan.statcan.fetch_json", fake_json)

    results = search_wds_tables("population dwelling")

    assert [result.product_id for result in results] == ["98100001"]
    assert results[0].title_en == "Population and dwelling counts: Canada"


def test_wds_search_results_serialize_and_stop_at_limit(monkeypatch) -> None:
    def fake_json(_url: str) -> list[dict[str, object]]:
        return [
            {
                "productId": 98100001,
                "cansimId": "",
                "cubeTitleEn": "Population and dwelling counts: Canada",
                "cubeTitleFr": "",
                "cubeStartDate": "2021-01-01",
                "cubeEndDate": "2021-01-01",
            },
            {
                "productId": 98100002,
                "cansimId": "",
                "cubeTitleEn": "Population by age and sex",
                "cubeTitleFr": "",
                "cubeStartDate": "2021-01-01",
                "cubeEndDate": "2021-01-01",
            },
        ]

    monkeypatch.setattr("synthpopcan.statcan.fetch_json", fake_json)

    results = search_wds_tables("population", limit=1)

    assert len(results) == 1
    assert results[0].as_dict() == {
        "product_id": "98100001",
        "cansim_id": "",
        "title_en": "Population and dwelling counts: Canada",
        "start_date": "2021-01-01",
        "end_date": "2021-01-01",
    }
    assert WDSTableSearchResult(
        product_id="1",
        cansim_id="2",
        title_en="Title",
        start_date="2020",
        end_date="2021",
    ).as_dict()["title_en"] == "Title"


def test_search_wds_tables_rejects_empty_query_and_bad_limit() -> None:
    with pytest.raises(ValueError, match="at least one term"):
        search_wds_tables("   ")
    with pytest.raises(ValueError, match="limit must be at least 1"):
        search_wds_tables("population", limit=0)


def test_cli_searches_wds_tables(capsys, monkeypatch) -> None:
    def fake_search(query: str, limit: int):
        assert query == "labour"
        assert limit == 1
        return [
            {
                "product_id": "14100287",
                "cansim_id": "282-0087",
                "title_en": "Labour force characteristics by province",
                "start_date": "1976-01-01",
                "end_date": "2026-01-01",
            }
        ]

    monkeypatch.setattr("synthpopcan.cli.search_wds_tables_for_cli", fake_search)

    assert (
        main(["statcan", "wds", "search", "labour", "--limit", "1", "--format", "tsv"])
        == 0
    )

    assert capsys.readouterr().out == (
        "product_id\tcansim_id\tstart_date\tend_date\ttitle_en\n"
        "14100287\t282-0087\t1976-01-01\t2026-01-01\t"
        "Labour force characteristics by province\n"
    )


def test_cli_searches_wds_tables_as_json(capsys, monkeypatch) -> None:
    def fake_search(query: str, limit: int):
        assert query == "population"
        assert limit == 1
        return [
            {
                "product_id": "98100001",
                "cansim_id": "",
                "title_en": "Population and dwelling counts",
                "start_date": "2021-01-01",
                "end_date": "2021-01-01",
            }
        ]

    monkeypatch.setattr("synthpopcan.cli.search_wds_tables_for_cli", fake_search)

    assert (
        main(
            [
                "statcan",
                "wds",
                "search",
                "population",
                "--limit",
                "1",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["product_id"] == "98100001"
    assert payload[0]["title_en"] == "Population and dwelling counts"


def test_cli_searches_wds_tables_as_rich_table(capsys, monkeypatch) -> None:
    def fake_search(query: str, limit: int):
        assert query == "population"
        assert limit == 1
        return [
            {
                "product_id": "98100001",
                "cansim_id": "",
                "title_en": "Population and dwelling counts",
                "start_date": "2021-01-01",
                "end_date": "2021-01-01",
            }
        ]

    monkeypatch.setattr("synthpopcan.cli.search_wds_tables_for_cli", fake_search)

    assert main(["statcan", "wds", "search", "population", "--limit", "1"]) == 0

    output = capsys.readouterr().out
    assert "Product ID" in output
    assert "98100001" in output
    assert "Population and dwelling counts" in output


def test_cli_wds_search_helper_uses_statcan_results(monkeypatch) -> None:
    def fake_search(query: str, limit: int):
        assert query == "population"
        assert limit == 2
        return [
            WDSTableSearchResult(
                product_id="98100001",
                cansim_id="",
                title_en="Population and dwelling counts",
                start_date="2021-01-01",
                end_date="2021-01-01",
            )
        ]

    monkeypatch.setattr("synthpopcan.cli.search_wds_tables", fake_search)

    assert search_wds_tables_for_cli("population", 2) == [
        {
            "product_id": "98100001",
            "cansim_id": "",
            "title_en": "Population and dwelling counts",
            "start_date": "2021-01-01",
            "end_date": "2021-01-01",
        }
    ]


def test_cli_parse_columns_and_census_profile_year_guard() -> None:
    assert parse_cli_columns(" age , sex ") == ("age", "sex")
    with pytest.raises(Exception, match="at least one column"):
        parse_cli_columns(" , ")
    with pytest.raises(ClickException, match="Only the 2016 Census Profile"):
        run_statcan_census_profile_fetch.callback("2021", "pt", Path("out"))


def test_cli_wds_explain_wraps_bad_metadata(monkeypatch) -> None:
    from click import ClickException

    monkeypatch.setattr("synthpopcan.cli.fetch_wds_metadata", lambda _product_id: {})

    with pytest.raises(ClickException, match="product ID"):
        main(["statcan", "wds", "explain", "98100001"])


def test_fetch_wds_metadata_posts_product_id(monkeypatch) -> None:
    calls: list[tuple[str, list[dict[str, int]]]] = []

    def fake_post(url: str, payload: list[dict[str, int]]) -> list[dict[str, object]]:
        calls.append((url, payload))
        return [
            {
                "status": "SUCCESS",
                "object": {
                    "productId": "14100287",
                    "cubeTitleEn": "Labour force characteristics by province",
                    "dimension": [{"dimensionNameEn": "Geography"}],
                },
            }
        ]

    monkeypatch.setattr("synthpopcan.statcan.post_json", fake_post)

    metadata = fetch_wds_metadata("14100287")

    assert calls == [
        (
            "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata",
            [{"productId": 14100287}],
        )
    ]
    assert metadata["cubeTitleEn"] == "Labour force characteristics by province"


def test_fetch_wds_metadata_rejects_empty_or_failed_responses(monkeypatch) -> None:
    monkeypatch.setattr("synthpopcan.statcan.post_json", lambda _url, _payload: [])
    with pytest.raises(ValueError, match="returned no metadata"):
        fetch_wds_metadata("14100287")

    monkeypatch.setattr(
        "synthpopcan.statcan.post_json",
        lambda _url, _payload: [{"status": "FAILED", "object": None}],
    )
    with pytest.raises(ValueError, match="metadata lookup failed"):
        fetch_wds_metadata("14100287")


def test_cli_writes_wds_metadata_json(tmp_path: Path, monkeypatch) -> None:
    def fake_metadata(product_id: str) -> dict[str, object]:
        assert product_id == "14100287"
        return {
            "productId": "14100287",
            "cubeTitleEn": "Labour force characteristics by province",
            "dimension": [{"dimensionNameEn": "Geography"}],
        }

    output_path = tmp_path / "metadata.json"
    monkeypatch.setattr("synthpopcan.cli.fetch_wds_metadata", fake_metadata)

    assert (
        main(
            [
                "statcan",
                "wds",
                "metadata",
                "14100287",
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text())
    assert payload["productId"] == "14100287"
    assert payload["dimension"][0]["dimensionNameEn"] == "Geography"


def test_cli_prints_wds_metadata_json(capsys, monkeypatch) -> None:
    def fake_metadata(product_id: str) -> dict[str, object]:
        assert product_id == "14100287"
        return {"productId": "14100287", "dimension": []}

    monkeypatch.setattr("synthpopcan.cli.fetch_wds_metadata", fake_metadata)

    assert main(["statcan", "wds", "metadata", "14100287"]) == 0

    assert json.loads(capsys.readouterr().out)["productId"] == "14100287"


def test_summarizes_wds_metadata_for_ipf_use() -> None:
    summary = summarize_wds_metadata(
        {
            "productId": "98100001",
            "cubeTitleEn": "Population and dwelling counts: Canada",
            "cubeStartDate": "2021-01-01",
            "cubeEndDate": "2021-01-01",
            "dimension": [
                {"dimensionNameEn": "Geography"},
                {"dimensionNameEn": "Age group"},
                {"dimensionNameEn": "Sex"},
            ],
        }
    )

    assert summary == {
        "product_id": "98100001",
        "title_en": "Population and dwelling counts: Canada",
        "date_range": "2021-01-01 to 2021-01-01",
        "dimensions": ["Geography", "Age group", "Sex"],
        "dimension_previews": [
            {
                "name": "Geography",
                "member_count": 0,
                "members": [],
                "truncated": False,
            },
            {
                "name": "Age group",
                "member_count": 0,
                "members": [],
                "truncated": False,
            },
            {"name": "Sex", "member_count": 0, "members": [], "truncated": False},
        ],
        "ipf_suitability": {
            "status": "likely_age_sex_controls",
            "reasons": [
                "Metadata includes geography.",
                "Metadata includes age.",
                "Metadata includes sex.",
            ],
        },
        "ipf_hint": (
            "Plausible IPF control table: choose dimensions that match your "
            "seed columns, then inspect the downloaded ZIP before normalizing."
        ),
        "next_commands": [
            "synthpopcan statcan wds fetch 98100001 --out-dir data/raw/statcan/wds",
            ("synthpopcan controls wds inspect data/raw/statcan/wds/98100001-eng.zip"),
            (
                "synthpopcan controls from-wds "
                "data/raw/statcan/wds/98100001-eng.zip "
                "--dimensions 'Geography,Age group,Sex' "
                "--count-column VALUE "
                "--out controls.csv"
            ),
            "synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv",
        ],
    }


def test_summarizes_wds_metadata_with_member_previews() -> None:
    summary = summarize_wds_metadata(
        {
            "productId": "98100001",
            "cubeTitleEn": "Population and dwelling counts: Canada",
            "cubeStartDate": "2021-01-01",
            "cubeEndDate": "2021-01-01",
            "dimension": [
                {
                    "dimensionNameEn": "Geography",
                    "member": [
                        {"memberNameEn": "Canada"},
                        {"memberNameEn": "Newfoundland and Labrador"},
                        {"memberNameEn": "Prince Edward Island"},
                        {"memberNameEn": "Nova Scotia"},
                    ],
                },
                {
                    "dimensionNameEn": "Characteristics",
                    "member": [
                        {"memberNameEn": "Population, 2021"},
                        {"memberNameEn": "Total private dwellings"},
                    ],
                },
            ],
        }
    )

    assert summary["dimension_previews"] == [
        {
            "name": "Geography",
            "member_count": 4,
            "members": ["Canada", "Newfoundland and Labrador", "Prince Edward Island"],
            "truncated": True,
        },
        {
            "name": "Characteristics",
            "member_count": 2,
            "members": ["Population, 2021", "Total private dwellings"],
            "truncated": False,
        },
    ]
    assert summary["ipf_suitability"] == {
        "status": "possible_totals_only",
        "reasons": [
            "Metadata includes geography.",
            "Metadata does not show age and sex dimensions.",
        ],
    }
    assert summary["ipf_hint"] == (
        "Possible source for total controls, but metadata does not show age and "
        "sex dimensions. Fetch and inspect the ZIP before normalizing."
    )


def test_wds_metadata_helpers_tolerate_alternate_and_invalid_shapes() -> None:
    assert extract_wds_dimension_names({"dimension": "not-a-list"}) == []
    assert extract_wds_dimension_names(
        {
            "dimensions": [
                "ignored",
                {"dimensionName": "Age"},
                {"name": "Sex"},
                {"dimensionNameEn": ""},
            ]
        }
    ) == ["Age", "Sex"]
    previews = extract_wds_dimension_previews(
        {
            "dimensions": [
                "ignored",
                {"dimensionName": "Age", "members": "not-a-list"},
                {
                    "name": "Sex",
                    "dimensionMembers": [
                        "ignored",
                        {"memberName": "Female"},
                        {"name": "Male"},
                        {"memberNameEn": ""},
                    ],
                },
                {"member": [{"memberNameEn": "No dimension name"}]},
            ]
        },
        member_limit=1,
    )
    assert previews == [
        {"name": "Age", "member_count": 0, "members": [], "truncated": False},
        {"name": "Sex", "member_count": 2, "members": ["Female"], "truncated": True},
    ]
    assert classify_wds_ipf_suitability(["Topic"]) == {
        "status": "unclear",
        "reasons": ["Metadata does not show age and sex dimensions."],
    }
    assert summarize_wds_metadata({"productId": "98100001", "dimension": "not-a-list"})[
        "ipf_hint"
    ] == (
        "Unclear IPF fit from metadata alone. Fetch and inspect the ZIP before "
        "using it as controls."
    )
    assert extract_wds_dimension_previews({"dimension": "not-a-list"}) == []


def test_fetch_wds_table_rejects_failed_download_lookup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "synthpopcan.statcan.fetch_json",
        lambda _url: {"status": "FAILED", "object": ""},
    )

    with pytest.raises(ValueError, match="did not return a download URL"):
        fetch_wds_table("14100287", tmp_path)


def test_fetch_census_profile_rejects_unknown_geo_level(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown 2016 Census Profile geography level"):
        fetch_census_profile_2016("unknown", tmp_path)


def test_low_level_download_helpers_use_urlopen(tmp_path: Path, monkeypatch) -> None:
    calls: list[object] = []

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, _size: int = -1) -> bytes:
            body = self.body
            self.body = b""
            return body

    def fake_urlopen(request):
        calls.append(request)
        return FakeResponse(b'{"status": "SUCCESS"}')

    monkeypatch.setattr("synthpopcan.statcan.urlopen", fake_urlopen)

    assert fetch_json("https://example.test/data.json") == {"status": "SUCCESS"}
    assert post_json("https://example.test/post", [{"productId": 1}]) == {
        "status": "SUCCESS"
    }
    destination = tmp_path / "download.json"
    download_url("https://example.test/download.json", destination)
    assert destination.read_bytes() == b'{"status": "SUCCESS"}'
    assert calls[0] == "https://example.test/data.json"
    assert calls[1].full_url == "https://example.test/post"
    assert calls[1].data == b'[{"productId": 1}]'


def test_normalizers_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="product ID"):
        normalize_product_id("14A")
    with pytest.raises(ValueError, match="language"):
        normalize_language("es")


def test_cli_explains_wds_metadata_as_json(capsys, monkeypatch) -> None:
    def fake_metadata(product_id: str) -> dict[str, object]:
        assert product_id == "98100001"
        return {
            "productId": "98100001",
            "cubeTitleEn": "Population and dwelling counts: Canada",
            "cubeStartDate": "2021-01-01",
            "cubeEndDate": "2021-01-01",
            "dimension": [
                {
                    "dimensionNameEn": "Geography",
                    "member": [{"memberNameEn": "Canada"}],
                },
                {
                    "dimensionNameEn": "Age group",
                    "member": [{"memberNameEn": "0 to 4 years"}],
                },
                {"dimensionNameEn": "Sex", "member": [{"memberNameEn": "Female"}]},
            ],
        }

    monkeypatch.setattr("synthpopcan.cli.fetch_wds_metadata", fake_metadata)

    assert main(["statcan", "wds", "explain", "98100001", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["product_id"] == "98100001"
    assert payload["dimensions"] == ["Geography", "Age group", "Sex"]
    assert payload["dimension_previews"][0]["members"] == ["Canada"]
    assert payload["ipf_suitability"]["status"] == "likely_age_sex_controls"
    assert payload["next_commands"][-1] == (
        "synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv"
    )


def test_cli_explains_wds_metadata_table_with_member_preview(
    capsys,
    monkeypatch,
) -> None:
    def fake_metadata(product_id: str) -> dict[str, object]:
        assert product_id == "98100001"
        return {
            "productId": "98100001",
            "cubeTitleEn": "Population and dwelling counts: Canada",
            "dimension": [
                {
                    "dimensionNameEn": "Geography",
                    "member": [
                        {"memberNameEn": "Canada"},
                        {"memberNameEn": "Quebec"},
                    ],
                },
                {
                    "dimensionNameEn": "Age group",
                    "member": [{"memberNameEn": "0 to 4 years"}],
                },
                {"dimensionNameEn": "Sex", "member": [{"memberNameEn": "Female"}]},
            ],
        }

    monkeypatch.setattr("synthpopcan.cli.fetch_wds_metadata", fake_metadata)

    assert main(["statcan", "wds", "explain", "98100001"]) == 0

    output = capsys.readouterr().out
    assert "Dimension Preview" in output
    assert "Geography" in output
    assert "Canada" in output
    assert "Quebec" in output
