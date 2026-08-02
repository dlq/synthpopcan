"""Maintained adapter for Statistics Canada's corrected ODEF v3.0.1 archive."""

from __future__ import annotations

__all__ = [
    "ODEF_V3_ARCHIVE_SHA256",
    "ODEF_V3_ARCHIVE_URL",
    "OdefAdapter",
    "normalize_odef_archive",
    "odef_source_profile",
]

import csv
import io
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from synthpopcan.enrichment import SourceProfile
from synthpopcan.geography import statcan_geography_universe

ODEF_V3_ARCHIVE_URL = (
    "https://www150.statcan.gc.ca/n1/en/pub/37-26-0001/2022001/ODEF_v3.0.zip"
)
ODEF_V3_ARCHIVE_SHA256 = (
    "a9ead09cc099fc36534a0e1da94883f18c8b3e814e4688dc2c5e191285f6d765"
)
_DATA_PAGE = "https://www150.statcan.gc.ca/n1/pub/37-26-0001/372600012022001-eng.htm"
_SOURCE_COLUMNS = (
    "unique_id",
    "province_code",
    "geocode",
    "source_id",
    "provider",
    "authority_id",
    "authority_name",
    "full_address",
    "school_id",
    "facility_name",
    "streetAddress",
    "postalCode",
    "addressLocality",
    "min_grade",
    "max_grade",
    "ISCED010",
    "ISCED020",
    "ISCED1",
    "ISCED2",
    "ISCED3",
    "ISCED4Plus",
    "is_OLMS",
    "french_immersion",
    "early_immersion",
    "middle_immersion",
    "late_immersion",
    "facility_type",
    "dguid",
    "csdname",
    "geometry",
    "date_updated",
)
_FLAG_COLUMNS = {
    "ISCED010": "isced_010",
    "ISCED020": "isced_020",
    "ISCED1": "isced_1",
    "ISCED2": "isced_2",
    "ISCED3": "isced_3",
    "ISCED4Plus": "isced_4_plus",
    "is_OLMS": "official_language_minority_school",
    "french_immersion": "french_immersion",
    "early_immersion": "early_immersion",
    "middle_immersion": "middle_immersion",
    "late_immersion": "late_immersion",
}
_VARIABLES = (
    "province_code",
    "province_numeric_code",
    "source_id",
    "provider",
    "authority_id",
    "authority_name",
    "source_address",
    "source_facility_id",
    "facility_name",
    "street_address",
    "postal_code",
    "locality",
    "min_grade",
    "max_grade",
    *_FLAG_COLUMNS.values(),
    "facility_type",
    "CSDUID",
    "CSDDGUID",
    "csd_name",
    "longitude",
    "latitude",
    "geometry_wkt",
    "source_updated_date",
)
_MISSING = frozenset({"", ".."})
_CSD_DGUID = re.compile(r"^2021A0005([0-9]{7})$")
_NUMBER = r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][-+]?[0-9]+)?"
_POINT = re.compile(rf"^POINT\s*\(\s*({_NUMBER})\s+({_NUMBER})\s*\)$", re.I)
_MAX_EXPANDED_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class OdefAdapter:
    """Reviewed source contract and normalizer for ODEF v3.0.1."""

    expected_sha256: str = ODEF_V3_ARCHIVE_SHA256

    dataset_id = "statcan.odef.v3.0.1"
    resource_url = ODEF_V3_ARCHIVE_URL
    layer_id = "statcan.odef.v3.0.1.facilities"
    layer_class = "facilities-points"
    layer_filename = "odef-v3.0.1-facilities.csv"
    key_columns = ("facility_id",)
    variables = _VARIABLES
    limitations = (
        "ODEF is a harmonized facility inventory, not evidence of capacity, "
        "catchment, quality, eligibility, accessibility, or service use.",
        "Provider reference dates and provincial coverage vary; the 2024 "
        "collection period is not a common observation date for every facility.",
        "Missing coordinates and CSD assignments are retained rather than "
        "treated as absence of a facility.",
        "Facility type is a provider-supplied value, not a common controlled "
        "classification.",
    )
    requires_base_geography = False
    max_download_bytes = 32 * 1024 * 1024

    def describe(self) -> SourceProfile:
        """Return the reviewed Statistics Canada ODEF source profile."""

        return odef_source_profile()

    def normalize_archive(
        self,
        archive_path: Path,
        output_path: Path,
    ) -> Mapping[str, object]:
        """Normalize the pinned corrected ODEF archive into a facility CSV."""

        return normalize_odef_archive(archive_path, output_path)

    def reproduction_parameters(self) -> Mapping[str, object]:
        """Record the corrected source revision consumed by the workflow."""

        return {
            "source_revision": "3.0.1",
            "correction_notice_date": "2025-11-17",
            "coordinate_source": "geometry WKT",
        }


def odef_source_profile() -> SourceProfile:
    """Describe the corrected ODEF v3.0.1 public source revision."""

    return SourceProfile(
        source_id="statcan.odef.v3.0.1",
        publisher_id="statistics-canada",
        titles={
            "en": "Open Database of Educational Facilities, version 3",
            "fr": (
                "Base de données ouvertes sur les établissements "
                "d'enseignement, version 3"
            ),
        },
        descriptions={
            "en": (
                "Project summary of the corrected v3.0.1 harmonized national "
                "inventory of educational facilities compiled from public "
                "government sources; the correction notice is dated "
                "2025-11-17."
            ),
            "fr": (
                "Résumé du projet décrivant la version corrigée 3.0.1 de "
                "l'inventaire national harmonisé des établissements "
                "d'enseignement, compilé à partir de sources gouvernementales "
                "publiques; l'avis de correction est daté du 2025-11-17."
            ),
        },
        canonical_url=_DATA_PAGE,
        acquisition_mode="public-download",
        authority="Statistics Canada Linkable Open Data Environment",
        licence_id="Open Government Licence - Canada 2.0",
        source_version="3.0.1",
        publication_date="2024-12-13",
        observation_period={
            "collection_start": "2024-07",
            "collection_end": "2024-11",
            "provider_reference_dates": "vary by source",
        },
        unit_of_observation="educational facility point with 2021 CSD context",
        access_classification="public",
        redistribution_status="permitted with source acknowledgement",
        geography=statcan_geography_universe(
            2021,
            "csd",
            "CSDUID",
            dguid_column="CSDDGUID",
        ),
        translation_provenance={
            "en": "Official title; project-written source summary.",
            "fr": "Official title; project translation of the source summary.",
        },
        known_limitations=OdefAdapter.limitations,
    )


def normalize_odef_archive(
    archive_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Normalize ODEF v3.0.1 while preserving missingness and source lineage.

    Parsing uses names instead of column positions because the bundled record
    layout declares a field absent from the corrected CSV. Coordinates are
    split from source WKT only after numeric and range validation; the original
    WKT remains in the sidecar because the publisher does not explicitly state
    a CRS in the accompanying methodology.
    """

    seen_ids: set[str] = set()
    missing_counts: Counter[str] = Counter()
    source_identifier_groups: defaultdict[tuple[str, str], list[str]] = defaultdict(
        list
    )
    candidate_groups: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    geometry_counts: Counter[str] = Counter()
    source_row_count = 0
    ungeocoded_count = 0
    missing_csd_count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            _validate_archive_size(archive)
            member = _member_by_basename(archive, "odef_v3_0_1.csv")
            with archive.open(member) as raw_handle:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="")
                )
                if reader.fieldnames != list(_SOURCE_COLUMNS):
                    raise ValueError(
                        "ODEF columns do not match the reviewed v3.0.1 schema"
                    )
                first_row = next(reader, None)
                if first_row is None:
                    raise ValueError("ODEF facility table is empty")
                with temporary.open("x", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["facility_id", *_VARIABLES],
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    for row_number, row in enumerate(
                        chain((first_row,), reader), start=2
                    ):
                        if None in row or any(value is None for value in row.values()):
                            raise ValueError(
                                f"ODEF row {row_number} does not match the "
                                "reviewed column count"
                            )
                        facility_id = _required(row, "unique_id", row_number)
                        if facility_id in seen_ids:
                            raise ValueError(
                                f"ODEF has duplicate unique_id {facility_id}"
                            )
                        seen_ids.add(facility_id)
                        normalized = _normalize_row(row, row_number)
                        writer.writerow(normalized)
                        source_row_count += 1
                        ungeocoded_count += not normalized["geometry_wkt"]
                        missing_csd_count += not normalized["CSDUID"]

                        for column in _SOURCE_COLUMNS:
                            if _value(row, column) == "":
                                missing_counts[column] += 1
                        source_key = (
                            normalized["source_id"],
                            normalized["source_facility_id"],
                        )
                        if all(source_key):
                            source_identifier_groups[source_key].append(facility_id)
                        candidate_key = (
                            normalized["facility_name"].casefold(),
                            normalized["geometry_wkt"],
                        )
                        if all(candidate_key):
                            candidate_groups[candidate_key].append(facility_id)
                        if normalized["geometry_wkt"]:
                            geometry_counts[normalized["geometry_wkt"]] += 1
        temporary.replace(output_path)
    except zipfile.BadZipFile as exc:
        raise ValueError("ODEF resource is not a valid ZIP archive") from exc
    finally:
        temporary.unlink(missing_ok=True)

    duplicate_source_groups = [
        {"source_id": key[0], "source_facility_id": key[1], "facility_ids": ids}
        for key, ids in sorted(source_identifier_groups.items())
        if len(ids) > 1
    ]
    candidate_duplicate_groups = [
        {
            "facility_name": key[0],
            "geometry_wkt": key[1],
            "facility_ids": ids,
        }
        for key, ids in sorted(candidate_groups.items())
        if len(ids) > 1
    ]
    return {
        "schema_version": "synthpopcan-odef-validation-v1",
        "passed": True,
        "source_rows": source_row_count,
        "normalized_rows": source_row_count,
        "unique_id_duplicate_count": 0,
        "duplicate_source_identifier_groups": duplicate_source_groups,
        "candidate_duplicate_groups": candidate_duplicate_groups,
        "duplicate_coordinate_row_count": sum(
            count - 1 for count in geometry_counts.values() if count > 1
        ),
        "ungeocoded_count": ungeocoded_count,
        "missing_csd_count": missing_csd_count,
        "missing_by_source_field": dict(sorted(missing_counts.items())),
        "coordinate_interpretation": (
            "Source geometry is preserved as WKT; longitude and latitude are "
            "parsed from POINT coordinate order. The publisher does not "
            "explicitly declare a CRS in the reviewed methodology."
        ),
        "warnings": [
            "The URL named v3.0 serves the corrected v3.0.1 archive.",
            "The bundled record layout declares postOfficeBoxNumber, but the "
            "facility CSV omits it.",
            "The current facility CSV contains no CMA columns or separate "
            "longitude/latitude source columns.",
            "Duplicate source identifiers, names, and coordinates are retained "
            "as diagnostics because colocated facilities can be legitimate.",
        ],
        "issues": [],
    }


def _normalize_row(row: Mapping[str, str], row_number: int) -> dict[str, str]:
    geometry = _value(row, "geometry")
    longitude, latitude = _coordinates(geometry, row_number)
    dguid = _value(row, "dguid")
    csduid = ""
    if dguid:
        match = _CSD_DGUID.fullmatch(dguid)
        if match is None:
            raise ValueError(f"ODEF row {row_number} has malformed CSD DGUID")
        csduid = match.group(1)
    output = {
        "facility_id": _required(row, "unique_id", row_number),
        "province_code": _value(row, "province_code"),
        "province_numeric_code": _value(row, "geocode"),
        "source_id": _value(row, "source_id"),
        "provider": _value(row, "provider"),
        "authority_id": _value(row, "authority_id"),
        "authority_name": _value(row, "authority_name"),
        "source_address": _value(row, "full_address"),
        "source_facility_id": _value(row, "school_id"),
        "facility_name": _value(row, "facility_name"),
        "street_address": _value(row, "streetAddress"),
        "postal_code": _value(row, "postalCode"),
        "locality": _value(row, "addressLocality"),
        "min_grade": _value(row, "min_grade"),
        "max_grade": _value(row, "max_grade"),
        "facility_type": _value(row, "facility_type"),
        "CSDUID": csduid,
        "CSDDGUID": dguid,
        "csd_name": _value(row, "csdname"),
        "longitude": longitude,
        "latitude": latitude,
        "geometry_wkt": geometry,
        "source_updated_date": _value(row, "date_updated"),
    }
    for source_column, output_column in _FLAG_COLUMNS.items():
        output[output_column] = _flag(
            _value(row, source_column),
            source_column,
            row_number,
        )
    return output


def _coordinates(geometry: str, row_number: int) -> tuple[str, str]:
    if not geometry:
        return "", ""
    match = _POINT.fullmatch(geometry)
    if match is None:
        raise ValueError(f"ODEF row {row_number} has unsupported geometry WKT")
    longitude = float(match.group(1))
    latitude = float(match.group(2))
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError(f"ODEF row {row_number} has out-of-range coordinates")
    return _format_coordinate(longitude), _format_coordinate(latitude)


def _flag(value: str, column: str, row_number: int) -> str:
    if not value:
        return ""
    if value == "1":
        return "true"
    if value == "0":
        return "false"
    raise ValueError(f"ODEF row {row_number} has unsupported {column} value {value!r}")


def _value(row: Mapping[str, str], column: str) -> str:
    raw_value = row.get(column, "")
    if raw_value is None:
        return ""
    value = str(raw_value).strip()
    return "" if value in _MISSING else value


def _required(row: Mapping[str, str], column: str, row_number: int) -> str:
    value = _value(row, column)
    if not value:
        raise ValueError(f"ODEF row {row_number} is missing {column}")
    return value


def _format_coordinate(value: float) -> str:
    return format(value, ".12g")


def _member_by_basename(archive: zipfile.ZipFile, basename: str) -> str:
    matches = [
        member.filename
        for member in archive.infolist()
        if not member.is_dir() and Path(member.filename).name == basename
    ]
    if len(matches) != 1:
        raise ValueError(f"ODEF archive must contain exactly one {basename} member")
    return matches[0]


def _validate_archive_size(archive: zipfile.ZipFile) -> None:
    expanded = sum(member.file_size for member in archive.infolist())
    if expanded > _MAX_EXPANDED_BYTES:
        raise ValueError("ODEF archive expands beyond the reviewed size limit")
