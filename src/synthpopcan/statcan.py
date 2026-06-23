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

__all__ = [
    "CensusProfileDownload",
    "WDSTableSearchResult",
    "classify_wds_ipf_suitability",
    "extract_wds_dimension_names",
    "extract_wds_dimension_previews",
    "fetch_census_profile_2016",
    "fetch_wds_metadata",
    "fetch_wds_table",
    "normalize_language",
    "normalize_product_id",
    "search_wds_tables",
    "summarize_wds_metadata",
    "wds_all_cubes_lite_url",
    "wds_download_url",
    "wds_metadata_url",
]


@dataclass(frozen=True)
class CensusProfileDownload:
    """Metadata for one supported 2016 Census Profile bulk download.

    Instances describe the geography level, display label, download parameters,
    and local filename for a supported Census Profile CSV.
    """

    geo_level: str
    label: str
    filetype: str
    geono: str

    @property
    def url(self) -> str:
        """Return the Statistics Canada download URL for this entry."""

        return (
            f"{CENSUS_PROFILE_2016_BASE_URL}?FILETYPE={self.filetype}"
            f"&GEONO={self.geono}&Lang=E"
        )

    @property
    def filename(self) -> str:
        """Return the local filename used for this download."""

        return f"2016-census-profile-{self.geo_level}.csv"


@dataclass(frozen=True)
class WDSTableSearchResult:
    """One table match from the Statistics Canada WDS cube list.

    Search results contain just enough metadata for a user or script to choose a
    candidate product ID and then request metadata or a full-table download.
    """

    product_id: str
    cansim_id: str
    title_en: str
    start_date: str
    end_date: str

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation for CLI output."""

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
    """Build the WDS endpoint URL that returns a full-table download link.

    This returns the service endpoint, not the final ZIP URL. Call
    :func:`fetch_wds_table` to resolve and download the file.
    """

    product = normalize_product_id(product_id)
    language = normalize_language(lang)
    return f"{WDS_BASE_URL}/getFullTableDownloadCSV/{product}/{language}"


def wds_all_cubes_lite_url() -> str:
    """Return the WDS endpoint URL for the all-cubes lite index."""

    return f"{WDS_BASE_URL}/getAllCubesListLite"


def wds_metadata_url() -> str:
    """Return the WDS endpoint URL for cube metadata lookup."""

    return f"{WDS_BASE_URL}/getCubeMetadata"


def search_wds_tables(query: str, limit: int = 10) -> list[WDSTableSearchResult]:
    """Search the WDS cube list for tables matching all query terms.

    The search is a simple case-insensitive term match over product ID, CANSIM
    ID, English and French titles, and date fields. It is useful for discovery,
    not as a ranked search engine.
    """

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
    """Fetch metadata for a WDS product ID.

    Raises ``ValueError`` when Statistics Canada returns no usable metadata for
    the requested product. Network and service errors from ``urllib`` are not
    wrapped so callers can decide how to retry or report them.
    """

    product = int(normalize_product_id(product_id))
    response = post_json(wds_metadata_url(), [{"productId": product}])
    if not response:
        raise ValueError(f"StatCan WDS returned no metadata for {product_id}")
    first = response[0]
    if first.get("status") != "SUCCESS" or not first.get("object"):
        raise ValueError(f"StatCan WDS metadata lookup failed for {product_id}")
    return dict(first["object"])


def summarize_wds_metadata(metadata: dict[str, Any]) -> dict[str, object]:
    """Summarize WDS metadata into dimensions, suitability hints, and commands.

    The summary is designed for display and JSON output. It includes dimension
    names, short member previews, a rough IPF suitability classification, and
    suggested next commands for downloading and normalizing controls.
    """

    product_id = normalize_product_id(str(metadata.get("productId", "")))
    dimensions = extract_wds_dimension_names(metadata)
    dimension_previews = extract_wds_dimension_previews(metadata)
    ipf_suitability = classify_wds_ipf_suitability(dimensions)
    ipf_hint = wds_ipf_hint(ipf_suitability["status"])
    dimensions_arg = ",".join(dimensions)
    zip_path = f"data/raw/statcan/wds/{product_id}-eng.zip"
    return {
        "product_id": product_id,
        "title_en": str(metadata.get("cubeTitleEn", "")),
        "date_range": format_metadata_date_range(
            metadata.get("cubeStartDate"),
            metadata.get("cubeEndDate"),
        ),
        "dimensions": dimensions,
        "dimension_previews": dimension_previews,
        "ipf_suitability": ipf_suitability,
        "ipf_hint": ipf_hint,
        "next_commands": [
            (
                f"synthpopcan statcan wds fetch {product_id} "
                "--out-dir data/raw/statcan/wds"
            ),
            f"synthpopcan controls wds inspect {zip_path}",
            (
                f"synthpopcan controls from-wds {zip_path} "
                f"--dimensions '{dimensions_arg}' "
                "--count-column VALUE "
                "--out controls.csv"
            ),
            "synthpopcan ipf check-inputs --seed seed.csv --controls controls.csv",
        ],
    }


def classify_wds_ipf_suitability(dimensions: list[str]) -> dict[str, object]:
    """Classify whether WDS dimensions look useful for simple IPF controls.

    This is a heuristic based only on dimension names. It can suggest that age
    and sex controls look plausible, but it cannot verify category compatibility
    with a seed sample.
    """

    normalized = {normalize_dimension_name(dimension) for dimension in dimensions}
    has_geography = any(dimension in normalized for dimension in ("geography", "geo"))
    has_age = any("age" in dimension for dimension in normalized)
    has_sex = any(dimension in normalized for dimension in ("sex", "gender"))

    reasons: list[str] = []
    if has_geography:
        reasons.append("Metadata includes geography.")
    if has_age:
        reasons.append("Metadata includes age.")
    if has_sex:
        reasons.append("Metadata includes sex.")
    if not has_age or not has_sex:
        reasons.append("Metadata does not show age and sex dimensions.")

    if has_age and has_sex:
        return {
            "status": "likely_age_sex_controls",
            "reasons": reasons,
        }
    if has_geography:
        return {
            "status": "possible_totals_only",
            "reasons": reasons,
        }
    return {
        "status": "unclear",
        "reasons": reasons or ["Metadata dimensions are not enough to assess IPF use."],
    }


def wds_ipf_hint(status: object) -> str:
    if status == "likely_age_sex_controls":
        return (
            "Plausible IPF control table: choose dimensions that match your "
            "seed columns, then inspect the downloaded ZIP before normalizing."
        )
    if status == "possible_totals_only":
        return (
            "Possible source for total controls, but metadata does not show age and "
            "sex dimensions. Fetch and inspect the ZIP before normalizing."
        )
    return (
        "Unclear IPF fit from metadata alone. Fetch and inspect the ZIP before "
        "using it as controls."
    )


def normalize_dimension_name(value: str) -> str:
    return value.strip().lower()


def extract_wds_dimension_names(metadata: dict[str, Any]) -> list[str]:
    """Extract English dimension names from WDS metadata.

    The helper tolerates small shape differences in WDS metadata payloads and
    returns an empty list when dimension names cannot be found.
    """

    names: list[str] = []
    dimensions = metadata.get("dimension") or metadata.get("dimensions", [])
    if not isinstance(dimensions, list):
        return names
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        name = (
            dimension.get("dimensionNameEn")
            or dimension.get("dimensionName")
            or dimension.get("name")
        )
        if isinstance(name, str) and name:
            names.append(name)
    return names


def extract_wds_dimension_previews(
    metadata: dict[str, Any],
    *,
    member_limit: int = 3,
) -> list[dict[str, object]]:
    """Extract short member previews for each WDS dimension.

    Each preview includes the dimension name, total member count, a short member
    sample, and a ``truncated`` flag.
    """

    previews: list[dict[str, object]] = []
    dimensions = metadata.get("dimension") or metadata.get("dimensions", [])
    if not isinstance(dimensions, list):
        return previews
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        name = extract_wds_dimension_name(dimension)
        if not name:
            continue
        members = extract_wds_member_names(dimension)
        previews.append(
            {
                "name": name,
                "member_count": len(members),
                "members": members[:member_limit],
                "truncated": len(members) > member_limit,
            }
        )
    return previews


def extract_wds_dimension_name(dimension: dict[str, Any]) -> str:
    name = (
        dimension.get("dimensionNameEn")
        or dimension.get("dimensionName")
        or dimension.get("name")
    )
    return name if isinstance(name, str) else ""


def extract_wds_member_names(dimension: dict[str, Any]) -> list[str]:
    members = (
        dimension.get("member")
        or dimension.get("members")
        or dimension.get("dimensionMembers")
        or []
    )
    if not isinstance(members, list):
        return []
    names: list[str] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        name = (
            member.get("memberNameEn") or member.get("memberName") or member.get("name")
        )
        if isinstance(name, str) and name:
            names.append(name)
    return names


def format_metadata_date_range(start: Any, end: Any) -> str:
    start_text = str(start or "")
    end_text = str(end or "")
    if start_text and end_text:
        return f"{start_text} to {end_text}"
    return start_text or end_text


def fetch_wds_table(product_id: str, out_dir: Path, lang: str = "en") -> Path:
    """Download a WDS full-table ZIP and write a small provenance manifest.

    Returns the path to the downloaded ZIP. A JSON manifest is written beside
    the ZIP with source, product ID, language, service URL, final download URL,
    and local path.
    """

    source_url = wds_download_url(product_id, lang)
    response = fetch_json(source_url)
    if response.get("status") != "SUCCESS" or not response.get("object"):
        raise ValueError(f"StatCan WDS did not return a download URL for {product_id}")

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
    """Download a supported 2016 Census Profile CSV and manifest.

    ``geo_level`` must be one of the supported keys in
    ``CENSUS_PROFILE_2016_DOWNLOADS``. The function returns the CSV path and
    writes a JSON provenance manifest beside it.
    """

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
    """Validate and normalize a Statistics Canada product ID.

    Product IDs must contain only digits. Leading and trailing whitespace is
    stripped, but the digit string is otherwise preserved.
    """

    product = product_id.strip()
    if not product.isdigit():
        raise ValueError("StatCan product ID must contain only digits")
    return product


def normalize_language(lang: str) -> str:
    """Normalize a WDS language code to ``en`` or ``fr``."""

    language = lang.lower().strip()
    if language not in {"en", "fr"}:
        raise ValueError("language must be 'en' or 'fr'")
    return language
