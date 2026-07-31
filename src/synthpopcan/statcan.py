"""Statistics Canada download helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

_WDS_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
_CENSUS_PROFILE_2016_BASE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/"
    "details/download-telecharger/comp/GetFile.cfm"
)
_CENSUS_PROFILE_2021_BASE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/"
    "details/download-telecharger/comp/getFile.cfm"
)
# StatCan hosts 2016 boundary files under the 2011 geo program path.
_BOUNDARY_2016_BASE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2011/geo/bound-limit/"
    "files-fichiers/2016/"
)
_BOUNDARY_2021_BASE_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/"
    "boundary-limites/files-fichiers/"
)
_DGRF_2021_URL = (
    "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/"
    "dguid-idugd/files-fichiers/2021_98260004.zip"
)
_STATCAN_TIMEOUT_SECONDS = 60
_MAX_STATCAN_DOWNLOAD_BYTES = 8 * 1024 * 1024 * 1024
_MAX_CENSUS_PROFILE_EXTRACTED_BYTES = 32 * 1024 * 1024 * 1024

__all__ = [
    "BoundaryDownload",
    "CensusProfileDownload",
    "WDSTableSearchResult",
    "classify_wds_ipf_suitability",
    "extract_wds_dimension_names",
    "extract_wds_dimension_previews",
    "fetch_boundary_zip",
    "fetch_census_profile",
    "get_boundary_download",
    "fetch_census_profile_2016",
    "fetch_dgrf_2021",
    "fetch_wds_metadata",
    "fetch_wds_table",
    "file_integrity",
    "normalize_language",
    "normalize_product_id",
    "search_wds_tables",
    "summarize_wds_metadata",
    "wds_all_cubes_lite_url",
    "wds_download_url",
    "wds_metadata_url",
]

_STATCAN_RESOURCE_SCHEMA_VERSION = "synthpopcan-statcan-resource-v1"


@dataclass(frozen=True)
class CensusProfileDownload:
    """Metadata for one supported Census Profile bulk download.

    Instances describe the geography level, display label, download parameters,
    and local filename for a supported Census Profile CSV.
    """

    geo_level: str
    label: str
    filetype: str
    geono: str
    census_year: int = 2016

    @property
    def url(self) -> str:
        """Return the Statistics Canada download URL for this entry."""

        base_url = {
            2016: _CENSUS_PROFILE_2016_BASE_URL,
            2021: _CENSUS_PROFILE_2021_BASE_URL,
        }[self.census_year]
        if self.census_year == 2021:
            return f"{base_url}?LANG=E&GEONO={self.geono}&FILETYPE={self.filetype}"
        return f"{base_url}?FILETYPE={self.filetype}&GEONO={self.geono}&Lang=E"

    @property
    def filename(self) -> str:
        """Return the local filename used for this download."""

        return f"{self.census_year}-census-profile-{self.geo_level}.csv"


@dataclass(frozen=True)
class BoundaryDownload:
    """Metadata for one StatCan census boundary file download.

    Boundary files use the NAD83 / Statistics Canada Lambert projection. The
    2016 files are hosted under StatCan's 2011 geography program path — this is
    intentional on StatCan's end, not a typo.
    """

    geo_level: str
    description: str
    zip_name: str
    shp_name: str
    id_field: str
    property_fields: tuple[str, ...] = ()
    census_year: int = 2016
    base_url: str = _BOUNDARY_2016_BASE_URL

    @property
    def url(self) -> str:
        """Return the Statistics Canada download URL for this boundary file."""
        return f"{self.base_url}{self.zip_name}"


_BOUNDARY_2016_DOWNLOADS: dict[str, BoundaryDownload] = {
    "ct": BoundaryDownload(
        geo_level="ct",
        description="Census tracts (2016)",
        zip_name="lct_000b16a_e.zip",
        shp_name="lct_000b16a_e.shp",
        id_field="CTUID",
        property_fields=(
            "CTNAME",
            "PRUID",
            "PRNAME",
            "CMAUID",
            "CMAPUID",
            "CMANAME",
            "CMATYPE",
        ),
    ),
    "ada": BoundaryDownload(
        geo_level="ada",
        description="Aggregate dissemination areas (2016)",
        zip_name="lada000b16a_e.zip",
        shp_name="lada000b16a_e.shp",
        id_field="ADAUID",
        property_fields=("PRUID", "PRNAME", "CDUID", "CDNAME", "CDTYPE"),
    ),
    "da": BoundaryDownload(
        geo_level="da",
        description="Dissemination areas (2016)",
        zip_name="lda_000b16a_e.zip",
        shp_name="lda_000b16a_e.shp",
        id_field="DAUID",
    ),
    "csd": BoundaryDownload(
        geo_level="csd",
        description="Census subdivisions (2016)",
        zip_name="lcsd000b16a_e.zip",
        shp_name="lcsd000b16a_e.shp",
        id_field="CSDUID",
        property_fields=(
            "CSDNAME",
            "CSDTYPE",
            "PRUID",
            "PRNAME",
            "CDUID",
            "CDNAME",
            "CDTYPE",
        ),
    ),
    "cd": BoundaryDownload(
        geo_level="cd",
        description="Census divisions (2016)",
        zip_name="lcd_000b16a_e.zip",
        shp_name="lcd_000b16a_e.shp",
        id_field="CDUID",
    ),
    "pr": BoundaryDownload(
        geo_level="pr",
        description="Provinces and territories (2016)",
        zip_name="lpr_000b16a_e.zip",
        shp_name="lpr_000b16a_e.shp",
        id_field="PRUID",
    ),
}

_BOUNDARY_2021_DOWNLOADS: dict[str, BoundaryDownload] = {
    "ct": BoundaryDownload(
        geo_level="ct",
        description="Census tracts (2021 cartographic)",
        zip_name="lct_000b21a_e.zip",
        shp_name="lct_000b21a_e.shp",
        id_field="CTUID",
        property_fields=("DGUID", "LANDAREA", "PRUID"),
        census_year=2021,
        base_url=_BOUNDARY_2021_BASE_URL,
    ),
    "ada": BoundaryDownload(
        geo_level="ada",
        description="Aggregate dissemination areas (2021 cartographic)",
        zip_name="lada000b21a_e.zip",
        shp_name="lada000b21a_e.shp",
        id_field="ADAUID",
        property_fields=("DGUID", "LANDAREA", "PRUID"),
        census_year=2021,
        base_url=_BOUNDARY_2021_BASE_URL,
    ),
    "da": BoundaryDownload(
        geo_level="da",
        description="Dissemination areas (2021 cartographic)",
        zip_name="lda_000b21a_e.zip",
        shp_name="lda_000b21a_e.shp",
        id_field="DAUID",
        property_fields=("DGUID", "LANDAREA", "PRUID"),
        census_year=2021,
        base_url=_BOUNDARY_2021_BASE_URL,
    ),
    "csd": BoundaryDownload(
        geo_level="csd",
        description="Census subdivisions (2021 cartographic)",
        zip_name="lcsd000b21a_e.zip",
        shp_name="lcsd000b21a_e.shp",
        id_field="CSDUID",
        property_fields=(
            "DGUID",
            "CSDNAME",
            "CSDTYPE",
            "LANDAREA",
            "PRUID",
        ),
        census_year=2021,
        base_url=_BOUNDARY_2021_BASE_URL,
    ),
}

_BOUNDARY_DOWNLOADS: dict[int, dict[str, BoundaryDownload]] = {
    2016: _BOUNDARY_2016_DOWNLOADS,
    2021: _BOUNDARY_2021_DOWNLOADS,
}


def get_boundary_download(geo_level: str, census_year: int = 2016) -> BoundaryDownload:
    """Return registered metadata for a Census boundary product.

    ``geo_level`` is normalized to lowercase and interpreted within
    ``census_year``. Unknown years and unsupported year/level combinations
    raise :class:`ValueError` listing the registered choices. No network
    request is made.
    """

    try:
        downloads = _BOUNDARY_DOWNLOADS[census_year]
    except KeyError as exc:
        known_years = ", ".join(str(year) for year in sorted(_BOUNDARY_DOWNLOADS))
        raise ValueError(
            f"Unsupported census year {census_year!r} for boundary download. "
            f"Supported: {known_years}."
        ) from exc
    try:
        return downloads[geo_level.lower()]
    except KeyError as exc:
        known = ", ".join(sorted(downloads))
        raise ValueError(
            f"Unknown geography level {geo_level!r} for {census_year} boundary "
            f"download. Supported: {known}."
        ) from exc


def fetch_boundary_zip(
    geo_level: str,
    out_dir: Path,
    *,
    census_year: int = 2016,
    url: str | None = None,
) -> Path:
    """Download and extract a supported StatCan census boundary shapefile.

    Downloads the boundary ZIP for *geo_level* (one of ``ct``, ``ada``,
    ``da``, ``csd``, ``cd``, ``pr``) to *out_dir*, extracts all shapefile
    components (.shp, .dbf, .shx, .prj), and returns the path to the .shp.

    Pass *census_year* to select the boundary vintage. Pass *url* to override
    the default StatCan URL (useful for mirrors or cached copies).
    """
    entry = get_boundary_download(geo_level, census_year)

    out_dir.mkdir(parents=True, exist_ok=True)
    download_url_ = url or entry.url
    zip_path = out_dir / entry.zip_name
    download_url(download_url_, zip_path)

    try:
        with ZipFile(zip_path) as archive:
            shp_exts = {".shp", ".dbf", ".shx", ".prj", ".cpg"}
            for info in archive.infolist():
                member_name = Path(info.filename).name
                if not member_name or Path(member_name).suffix.lower() not in shp_exts:
                    continue
                with archive.open(info) as source:
                    _atomic_copy_stream(
                        source,
                        out_dir / member_name,
                        max_bytes=_MAX_STATCAN_DOWNLOAD_BYTES,
                    )
    finally:
        zip_path.unlink(missing_ok=True)

    shp_path = out_dir / entry.shp_name
    if not shp_path.exists():
        # Some ZIPs nest the files inside a subdirectory — find the .shp
        candidates = list(out_dir.rglob(entry.shp_name))
        if not candidates:
            raise FileNotFoundError(
                f"Could not find {entry.shp_name} after extracting {zip_path.name}"
            )
        shp_path = candidates[0]

    resources = []
    for suffix in (".shp", ".dbf", ".shx", ".prj", ".cpg"):
        component = shp_path.with_suffix(suffix)
        if component.exists():
            resources.append(
                {
                    "component": suffix.removeprefix("."),
                    "path": str(component),
                    **file_integrity(component),
                }
            )
    from synthpopcan.geography import statcan_geography_universe

    write_manifest(
        out_dir / f"{entry.census_year}-boundary-{entry.geo_level}.json",
        {
            "schema_version": _STATCAN_RESOURCE_SCHEMA_VERSION,
            "source": (
                f"Statistics Canada {entry.census_year} census cartographic "
                "boundary files"
            ),
            "source_revision": entry.zip_name,
            "census_year": entry.census_year,
            "geo_level": entry.geo_level,
            "description": entry.description,
            "source_url": download_url_,
            "shp_path": str(shp_path),
            "geography": statcan_geography_universe(
                entry.census_year,
                entry.geo_level,
                entry.id_field,
                dguid_column="DGUID" if "DGUID" in entry.property_fields else None,
            ).as_dict(),
            "resources": resources,
        },
    )
    return shp_path


def fetch_dgrf_2021(out_dir: Path, *, url: str | None = None) -> Path:
    """Download and extract the final 2021 geography relationship CSV.

    The official ZIP is bounded during retrieval, the expected
    ``2021_98260004.csv`` member is extracted atomically, the temporary archive
    is removed, and a versioned provenance and integrity manifest is written
    beside the CSV. ``url`` is reserved for a documented mirror.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    download_url_ = url or _DGRF_2021_URL
    zip_path = out_dir / "2021_98260004.zip"
    csv_path = out_dir / "2021_98260004.csv"
    download_url(download_url_, zip_path)
    try:
        with ZipFile(zip_path) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if Path(info.filename).name == csv_path.name
            ]
            if not candidates:
                raise FileNotFoundError(
                    f"Could not find {csv_path.name} in {zip_path.name}"
                )
            with archive.open(candidates[0]) as source:
                _atomic_copy_stream(
                    source,
                    csv_path,
                    max_bytes=_MAX_STATCAN_DOWNLOAD_BYTES,
                )
    finally:
        zip_path.unlink(missing_ok=True)

    write_manifest(
        out_dir / "2021-dissemination-geographies-relationship.json",
        {
            "schema_version": _STATCAN_RESOURCE_SCHEMA_VERSION,
            "source": "Statistics Canada 2021 Census",
            "source_revision": "98-26-0004-2021-final",
            "census_year": 2021,
            "product": "Dissemination Geographies Relationship File",
            "catalogue_number": "98-26-0004",
            "source_url": download_url_,
            "csv_path": str(csv_path),
            "resource": {
                "path": str(csv_path),
                **file_integrity(csv_path),
            },
        },
    )
    return csv_path


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

        return asdict(self)


_CENSUS_PROFILE_2016_DOWNLOADS: dict[str, CensusProfileDownload] = {
    "pt": CensusProfileDownload(
        "pt", "Canada, provinces and territories", "CSV", "059"
    ),
    "cma-ca": CensusProfileDownload(
        "cma-ca", "Census metropolitan areas and census agglomerations", "CSV", "041"
    ),
    "cma-ca-csd": CensusProfileDownload(
        "cma-ca-csd",
        "Census metropolitan areas, census agglomerations and census subdivisions",
        "CSV",
        "042",
    ),
    "cd": CensusProfileDownload("cd", "Census divisions", "CSV", "018"),
    "csd-all": CensusProfileDownload(
        "csd-all",
        "Canada, provinces, territories, census divisions and census subdivisions",
        "CSV",
        "055",
    ),
    "da-all": CensusProfileDownload(
        "da-all",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas",
        "CSV",
        "044",
    ),
    "ct": CensusProfileDownload(
        "ct",
        "Census metropolitan areas, tracted census agglomerations and census tracts",
        "CSV",
        "043",
    ),
    "er": CensusProfileDownload("er", "Economic regions", "CSV", "049"),
    "popctr": CensusProfileDownload("popctr", "Population centres", "CSV", "048"),
    "fed": CensusProfileDownload(
        "fed", "Federal electoral districts, 2013 Representation Order", "CSV", "045"
    ),
    "dpl": CensusProfileDownload("dpl", "Designated places", "CSV", "047"),
    "fsa": CensusProfileDownload("fsa", "Forward sortation areas", "CSV", "046"),
    "ada": CensusProfileDownload("ada", "Aggregate dissemination areas", "CSV", "050"),
    "hr": CensusProfileDownload("hr", "Health regions", "CSV", "058"),
}
CENSUS_PROFILE_2016_GEO_LEVELS = tuple(_CENSUS_PROFILE_2016_DOWNLOADS)

_CENSUS_PROFILE_2021_DOWNLOADS: dict[str, CensusProfileDownload] = {
    "csd-all": CensusProfileDownload(
        "csd-all",
        "Canada, provinces, territories, census divisions and census subdivisions",
        "CSV",
        "005",
        census_year=2021,
    ),
    "ct": CensusProfileDownload(
        "ct",
        "Census metropolitan areas, tracted census agglomerations and census tracts",
        "CSV",
        "007",
        census_year=2021,
    ),
    "ada": CensusProfileDownload(
        "ada",
        "Aggregate dissemination areas",
        "CSV",
        "012",
        census_year=2021,
    ),
    "da-all": CensusProfileDownload(
        "da-all",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas",
        "CSV",
        "006",
        census_year=2021,
    ),
    "da-atlantic": CensusProfileDownload(
        "da-atlantic",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - Atlantic only",
        "CSV",
        "006_Atlantic_Atlantique",
        census_year=2021,
    ),
    "da-quebec": CensusProfileDownload(
        "da-quebec",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - Quebec only",
        "CSV",
        "006_Quebec",
        census_year=2021,
    ),
    "da-ontario": CensusProfileDownload(
        "da-ontario",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - Ontario only",
        "CSV",
        "006_Ontario",
        census_year=2021,
    ),
    "da-prairies": CensusProfileDownload(
        "da-prairies",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - Prairies only",
        "CSV",
        "006_Prairies",
        census_year=2021,
    ),
    "da-british-columbia": CensusProfileDownload(
        "da-british-columbia",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - British Columbia only",
        "CSV",
        "006_BC_CB",
        census_year=2021,
    ),
    "da-territories": CensusProfileDownload(
        "da-territories",
        "Canada, provinces, territories, census divisions, census subdivisions "
        "and dissemination areas - Territories only",
        "CSV",
        "006_Territories_Territoires",
        census_year=2021,
    ),
}

_CENSUS_PROFILE_DOWNLOADS = {
    2016: _CENSUS_PROFILE_2016_DOWNLOADS,
    2021: _CENSUS_PROFILE_2021_DOWNLOADS,
}
CENSUS_PROFILE_GEO_LEVELS = tuple(
    sorted(
        {key for downloads in _CENSUS_PROFILE_DOWNLOADS.values() for key in downloads}
    )
)


def wds_download_url(product_id: str, lang: str = "en") -> str:
    """Build the WDS endpoint URL that returns a full-table download link.

    This returns the service endpoint, not the final ZIP URL. Call
    :func:`fetch_wds_table` to resolve and download the file.
    """

    product = normalize_product_id(product_id)
    language = normalize_language(lang)
    return f"{_WDS_BASE_URL}/getFullTableDownloadCSV/{product}/{language}"


def wds_all_cubes_lite_url() -> str:
    """Return the WDS endpoint URL for the all-cubes lite index."""

    return f"{_WDS_BASE_URL}/getAllCubesListLite"


def wds_metadata_url() -> str:
    """Return the WDS endpoint URL for cube metadata lookup."""

    return f"{_WDS_BASE_URL}/getCubeMetadata"


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


def summarize_wds_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
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


def classify_wds_ipf_suitability(dimensions: list[str]) -> dict[str, Any]:
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


def _iter_wds_dimensions(metadata: dict[str, Any]):
    """Yield each dict dimension entry from WDS metadata, tolerating shape drift."""

    dimensions = metadata.get("dimension") or metadata.get("dimensions", [])
    if not isinstance(dimensions, list):
        return
    for dimension in dimensions:
        if isinstance(dimension, dict):
            yield dimension


def extract_wds_dimension_names(metadata: dict[str, Any]) -> list[str]:
    """Extract English dimension names from WDS metadata.

    The helper tolerates small shape differences in WDS metadata payloads and
    returns an empty list when dimension names cannot be found.
    """

    names: list[str] = []
    for dimension in _iter_wds_dimensions(metadata):
        name = extract_wds_dimension_name(dimension)
        if name:
            names.append(name)
    return names


def extract_wds_dimension_previews(
    metadata: dict[str, Any],
    *,
    member_limit: int = 3,
) -> list[dict[str, Any]]:
    """Extract short member previews for each WDS dimension.

    Each preview includes the dimension name, total member count, a short member
    sample, and a ``truncated`` flag.
    """

    previews: list[dict[str, Any]] = []
    for dimension in _iter_wds_dimensions(metadata):
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


def fetch_census_profile(
    geo_level: str,
    out_dir: Path,
    *,
    census_year: int = 2016,
) -> Path:
    """Download a supported Census Profile CSV and provenance manifest.

    The supported geography products depend on ``census_year``. The function
    returns the extracted CSV path and writes a JSON manifest beside it.
    """

    try:
        downloads = _CENSUS_PROFILE_DOWNLOADS[census_year]
    except KeyError as exc:
        known_years = ", ".join(str(year) for year in sorted(_CENSUS_PROFILE_DOWNLOADS))
        raise ValueError(
            f"Unsupported Census Profile year {census_year!r}. "
            f"Use one of: {known_years}."
        ) from exc
    try:
        entry = downloads[geo_level]
    except KeyError as exc:
        known = ", ".join(sorted(downloads))
        raise ValueError(
            f"Unknown {census_year} Census Profile geography level {geo_level!r}. "
            f"Use one of: {known}."
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / entry.filename
    download_path = destination.with_suffix(destination.suffix + ".download")
    download_url(entry.url, download_path)
    try:
        extract_census_profile_csv(download_path, destination)
    finally:
        download_path.unlink(missing_ok=True)
    write_manifest(
        out_dir / f"{census_year}-census-profile-{entry.geo_level}.json",
        {
            "schema_version": _STATCAN_RESOURCE_SCHEMA_VERSION,
            "source": (f"Statistics Canada {census_year} Census Profile bulk download"),
            "source_revision": (f"census-profile-{census_year}-{entry.geono}-english"),
            **asdict(entry),
            "source_url": entry.url,
            "path": str(destination),
            "geography_scope": {
                "census_vintage": census_year,
                "requested_product": entry.geo_level,
                "note": (
                    "Census Profile products may contain parent geography rows; "
                    "row-level GEO_LEVEL and identifiers remain authoritative."
                ),
            },
            "resource": {
                "path": str(destination),
                **file_integrity(destination),
            },
        },
    )
    return destination


def fetch_census_profile_2016(geo_level: str, out_dir: Path) -> Path:
    """Backward-compatible wrapper for a 2016 Census Profile download."""

    return fetch_census_profile(geo_level, out_dir, census_year=2016)


def extract_census_profile_csv(download_path: Path, destination: Path) -> None:
    """Extract a Census Profile CSV when StatCan returns a ZIP payload."""

    try:
        with ZipFile(download_path) as archive:
            csv_members = _census_profile_csv_members(archive.namelist())
            if not csv_members:
                raise ValueError("Census Profile ZIP did not contain a data CSV")
            with archive.open(csv_members[0]) as source:
                _atomic_copy_stream(
                    source,
                    destination,
                    max_bytes=_MAX_CENSUS_PROFILE_EXTRACTED_BYTES,
                )
    except BadZipFile:
        prefix = download_path.read_bytes()[:512].lstrip().lower()
        if prefix.startswith((b"<!doctype html", b"<html")):
            raise ValueError(
                "Census Profile download returned HTML instead of CSV or ZIP"
            ) from None
        download_path.replace(destination)


def _census_profile_csv_members(names: list[str]) -> list[str]:
    """Return Census Profile data members in deterministic preference order.

    StatCan's bulk archives do not use one uniform filename across products.
    Prefer the established English data suffix, but accept a single CSV (or a
    clearly named English data CSV) when a regional archive uses another name.
    """

    csv_members = sorted(
        name
        for name in names
        if not name.endswith("/") and Path(name).suffix.casefold() == ".csv"
    )
    preferred = [
        name
        for name in csv_members
        if name.casefold().endswith("_english_csv_data.csv")
    ]
    if preferred:
        return preferred
    english_data = [
        name
        for name in csv_members
        if "english" in Path(name).name.casefold()
        and "data" in Path(name).name.casefold()
    ]
    if english_data:
        return english_data
    if len(csv_members) == 1:
        return csv_members
    return []


def fetch_json(url: str) -> Any:
    with urlopen(url, timeout=_STATCAN_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: Any) -> Any:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=_STATCAN_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def download_url(
    url: str,
    destination: Path,
    *,
    timeout: int = _STATCAN_TIMEOUT_SECONDS,
    max_bytes: int = _MAX_STATCAN_DOWNLOAD_BYTES,
) -> None:
    """Download to a unique sibling and atomically replace on completion."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_sibling(destination, ".download")
    try:
        with urlopen(url, timeout=timeout) as response:
            headers = getattr(response, "headers", {})
            content_length = (
                headers.get("Content-Length") if hasattr(headers, "get") else None
            )
            expected: int | None = None
            if content_length:
                try:
                    expected = int(content_length)
                except (TypeError, ValueError):
                    expected = None
                if expected is not None and expected > max_bytes:
                    raise ValueError(
                        f"StatCan download exceeds the {max_bytes}-byte safety limit"
                    )
            downloaded = 0
            with temporary.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise ValueError(
                            "StatCan download exceeded the "
                            f"{max_bytes}-byte safety limit"
                        )
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            if expected is not None and downloaded != expected:
                raise ValueError(
                    f"StatCan download ended after {downloaded} of {expected} bytes"
                )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _temporary_sibling(destination: Path, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=suffix, dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


def _atomic_copy_stream(source: Any, destination: Path, *, max_bytes: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_sibling(destination, ".part")
    copied = 0
    try:
        with temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                copied += len(chunk)
                if copied > max_bytes:
                    raise ValueError(
                        "extracted StatCan file exceeded the "
                        f"{max_bytes}-byte safety limit"
                    )
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def file_integrity(path: Path) -> dict[str, str | int]:
    """Return the byte length and lowercase SHA-256 digest of one file."""

    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
            byte_size += len(chunk)
    return {"byte_size": byte_size, "sha256": digest.hexdigest()}


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
