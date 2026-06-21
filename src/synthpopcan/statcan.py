"""Statistics Canada download helpers."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

WDS_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
CENSUS_PROFILE_2016_BASE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/"
    "details/download-telecharger/comp/GetFile.cfm"
)


@dataclass(frozen=True)
class CensusProfileDownload:
    geo_level: str
    label: str
    filetype: str
    geono: str

    @property
    def url(self) -> str:
        return (
            f"{CENSUS_PROFILE_2016_BASE_URL}?FILETYPE={self.filetype}"
            f"&GEONO={self.geono}&Lang=E"
        )

    @property
    def filename(self) -> str:
        return f"2016-census-profile-{self.geo_level}.csv"


@dataclass(frozen=True)
class WDSTableSearchResult:
    product_id: str
    cansim_id: str
    title_en: str
    start_date: str
    end_date: str

    def as_dict(self) -> dict[str, str]:
        return {
            "product_id": self.product_id,
            "cansim_id": self.cansim_id,
            "title_en": self.title_en,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


CENSUS_PROFILE_2016_DOWNLOADS: dict[str, CensusProfileDownload] = {
    "pt": CensusProfileDownload(
        "pt", "Canada, provinces and territories", "CSV", "059"
    ),
    "cma-ca": CensusProfileDownload(
        "cma-ca", "Census metropolitan areas and census agglomerations", "CSV", "001"
    ),
    "cma-ca-csd": CensusProfileDownload(
        "cma-ca-csd",
        "Census metropolitan areas, census agglomerations and census subdivisions",
        "CSV",
        "006",
    ),
    "cd": CensusProfileDownload("cd", "Census divisions", "CSV", "018"),
    "csd-all": CensusProfileDownload(
        "csd-all",
        "Canada, provinces, territories, census divisions and census subdivisions",
        "CSV",
        "016",
    ),
    "da-all": CensusProfileDownload(
        "da-all",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas",
        "CSV",
        "017",
    ),
    "ct": CensusProfileDownload(
        "ct",
        "Census metropolitan areas, tracted census agglomerations and census tracts",
        "CSV",
        "020",
    ),
    "er": CensusProfileDownload("er", "Economic regions", "CSV", "022"),
    "popctr": CensusProfileDownload("popctr", "Population centres", "CSV", "023"),
    "fed": CensusProfileDownload(
        "fed", "Federal electoral districts, 2013 Representation Order", "CSV", "024"
    ),
    "dpl": CensusProfileDownload("dpl", "Designated places", "CSV", "025"),
    "fsa": CensusProfileDownload("fsa", "Forward sortation areas", "CSV", "026"),
    "ada": CensusProfileDownload("ada", "Aggregate dissemination areas", "CSV", "027"),
    "hr": CensusProfileDownload("hr", "Health regions", "CSV", "029"),
}


def wds_download_url(product_id: str, lang: str = "en") -> str:
    product = normalize_product_id(product_id)
    language = normalize_language(lang)
    return f"{WDS_BASE_URL}/getFullTableDownloadCSV/{product}/{language}"


def wds_all_cubes_lite_url() -> str:
    return f"{WDS_BASE_URL}/getAllCubesListLite"


def wds_metadata_url() -> str:
    return f"{WDS_BASE_URL}/getCubeMetadata"


def search_wds_tables(query: str, limit: int = 10) -> list[WDSTableSearchResult]:
    terms = [term.lower() for term in query.split() if term.strip()]
    if not terms:
        raise ValueError("search query must contain at least one term")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    matches: list[WDSTableSearchResult] = []
    for row in fetch_json(wds_all_cubes_lite_url()):
        haystack = " ".join(
            str(row.get(field, ""))
            for field in (
                "productId",
                "cansimId",
                "cubeTitleEn",
                "cubeTitleFr",
                "cubeStartDate",
                "cubeEndDate",
            )
        ).lower()
        if all(term in haystack for term in terms):
            matches.append(
                WDSTableSearchResult(
                    product_id=str(row.get("productId", "")),
                    cansim_id=str(row.get("cansimId", "")),
                    title_en=str(row.get("cubeTitleEn", "")),
                    start_date=str(row.get("cubeStartDate", "")),
                    end_date=str(row.get("cubeEndDate", "")),
                )
            )
            if len(matches) >= limit:
                break
    return matches


def fetch_wds_metadata(product_id: str) -> dict[str, Any]:
    product = int(normalize_product_id(product_id))
    response = post_json(wds_metadata_url(), [{"productId": product}])
    if not response:
        raise ValueError(f"StatsCan WDS returned no metadata for {product_id}")
    first = response[0]
    if first.get("status") != "SUCCESS" or not first.get("object"):
        raise ValueError(f"StatsCan WDS metadata lookup failed for {product_id}")
    return dict(first["object"])


def fetch_wds_table(product_id: str, out_dir: Path, lang: str = "en") -> Path:
    source_url = wds_download_url(product_id, lang)
    response = fetch_json(source_url)
    if response.get("status") != "SUCCESS" or not response.get("object"):
        raise ValueError(f"StatsCan WDS did not return a download URL for {product_id}")

    download_source = str(response["object"])
    destination = out_dir / Path(download_source).name
    out_dir.mkdir(parents=True, exist_ok=True)
    download_url(download_source, destination)
    write_manifest(
        destination.with_suffix(".json"),
        {
            "source": "Statistics Canada WDS",
            "product_id": normalize_product_id(product_id),
            "language": normalize_language(lang),
            "source_url": source_url,
            "download_url": download_source,
            "path": str(destination),
        },
    )
    return destination


def fetch_census_profile_2016(geo_level: str, out_dir: Path) -> Path:
    try:
        entry = CENSUS_PROFILE_2016_DOWNLOADS[geo_level]
    except KeyError as exc:
        known = ", ".join(sorted(CENSUS_PROFILE_2016_DOWNLOADS))
        raise ValueError(
            f"unknown 2016 Census Profile geo level {geo_level!r}: {known}"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / entry.filename
    download_url(entry.url, destination)
    write_manifest(
        out_dir / f"2016-census-profile-{entry.geo_level}.json",
        {
            "source": "Statistics Canada 2016 Census Profile bulk download",
            **asdict(entry),
            "source_url": entry.url,
            "path": str(destination),
        },
    )
    return destination


def fetch_json(url: str) -> Any:
    with urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: Any) -> Any:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def download_url(url: str, destination: Path) -> None:
    with urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def normalize_product_id(product_id: str) -> str:
    product = product_id.strip()
    if not product.isdigit():
        raise ValueError("StatsCan product ID must contain only digits")
    return product


def normalize_language(lang: str) -> str:
    language = lang.lower().strip()
    if language not in {"en", "fr"}:
        raise ValueError("language must be 'en' or 'fr'")
    return language
